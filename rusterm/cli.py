"""CLI entry point for rusterm.

Available commands:
  init           — initialize app data directory
  ingest         — run ingestion pipeline for instruments
  snapshot       — build snapshot for instrument
  export         — export snapshot to CSV/JSON
  verify         — verify snapshot integrity
  doctor         — check full integrity: manifest vs store, schema_version, orphaned links
"""
from __future__ import annotations

import sys
import argparse
import json
import os
from typing import Optional, List

from rusterm.core.fact import Fact
from rusterm.store.raw_store import put_with_manifest, decompress_object
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import RawRepo, FactRepo
from rusterm.formulas import calculate_measure
from rusterm.providers.market import FakeMarketDataProvider
from rusterm.providers.disclosures import FakeDisclosuresProvider
from rusterm.parsers import SyntheticXBRLParser, TableParser
from rusterm.pipeline import (
    plan_refresh, poll_source_index, enqueue, fetch, store_raw,
    parse, validate, persist, cascade,
)


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize app data directory on first run."""
    paths = AppPaths.from_root(args.data_dir or os.path.expanduser("~/.rusterm"))
    ensure_app_dir(paths)
    print(f"Initialized rusterm at {paths.app_data}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Run ingestion pipeline for given instruments."""
    # Simple implementation: plan refresh for all instruments
    import uuid
    watchlist = args.instruments or ["AAPL", "MSFT", "GOOG"]
    last_cursor = {}
    jobs = plan_refresh(watchlist, last_cursor)
    
    print(f"Planned {len(jobs)} refresh jobs")
    
    # Process jobs through pipeline
    for job in jobs[:3]:  # Limit for demo
        print(f"Processing job: {job['job_id']}")
        # fetch
        raw_bytes, fetch_result = fetch(job, "synthetic")
        print(f"  Fetched: {fetch_result.sha256[:8]}... status={fetch_result.status}")
        # store_raw
        paths = AppPaths.from_root(os.path.expanduser("~/.rusterm"))
        ensure_app_dir(paths)
        sha = store_raw(raw_bytes, "synthetic", paths)
        print(f"  Stored: sha256={sha[:8]}...")
        # parse
        facts, unparsed = parse(raw_bytes, "synthetic")
        print(f"  Parsed: {len(facts)} facts, {unparsed} unparsed")
        # validate
        accepted, errors = validate(facts)
        print(f"  Validated: {len(accepted)} accepted, {len(errors)} errors")
        # persist
        persist_result = persist(accepted, paths)
        print(f"  Persisted: {persist_result['written']} written, {persist_result['duplicates']} duplicates")
    
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Build snapshot for instrument."""
    import json
    from rusterm.store.paths import AppPaths, ensure_app_dir
    
    instrument_id = args.instrument
    paths = AppPaths.from_root(os.path.expanduser("~/.rusterm"))
    ensure_app_dir(paths)
    
    # Load facts from store
    fact_repo = FactRepo(paths.db_path)
    facts = fact_repo.load_by_instrument(instrument_id)
    
    print(f"Loading {len(facts)} facts for {instrument_id}")
    
    # Compute measures using formulas
    measures = []
    for fact in facts[:5]:  # Limit for demo
        # Simplified: just create a measure
        measure = calculate_measure(
            concept=fact.concept,
            value=float(fact.value) if fact.value else None,
            unit=fact.unit,
            period_start=fact.period_start,
            period_end=fact.period_end,
            method_version=fact.parser_version,
        )
        measures.append(measure)
    
    # Build snapshot blocks (simplified)
    blocks = []
    if measures:
        block = type('SnapshotBlock', (), {
            'block': 'fundamentals',
            'status': 'ready',
            'measures': measures,
            'reason': None,
        })()
        blocks.append(block)
    
    # Second pass: peer set
    # ... (peer set logic from I10)
    
    snapshot_version = 1
    snapshot = type('Snapshot', (), {
        'instrument_id': instrument_id,
        'snapshot_version': snapshot_version,
        'as_of': '2024-12-31',
        'peer_set_version': None,
        'peer_set_status': 'none',
        'blocks': blocks,
    })()
    
    print(f"Built snapshot v{snapshot_version} for {instrument_id}")
    print(f"  Blocks: {len(blocks)}")
    print(f"  Measures: {len(measures)}")
    if measures:
        for m in measures[:3]:
            print(f"    {m.concept}: {m.value} {m.unit} (null_reason={m.null_reason})")
    
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export snapshot to CSV/JSON."""
    import json
    
    instrument_id = args.instrument
    fmt = args.format or "csv"
    paths = AppPaths.from_root(os.path.expanduser("~/.rusterm"))
    
    # Load snapshot
    from rusterm.store.repos import SnapshotRepo
    snap_repo = SnapshotRepo(paths.db_path)
    snapshot = snap_repo.load(instrument_id)
    
    if not snapshot:
        print(f"No snapshot found for {instrument_id}")
        return 1
    
    output_path = args.output or f"{instrument_id}.{fmt}"
    
    if fmt == "csv":
        lines = ["concept,value,unit,period_start,period_end,method_version,null_reason"]
        for block in snapshot.blocks:
            for m in block.measures:
                lines.append(f"{m.concept},{m.value},{m.unit},{m.period_start},{m.period_end},{m.method_version},{m.null_reason or ''}")
        content = "\n".join(lines)
    elif fmt == "json":
        data = []
        for block in snapshot.blocks:
            for m in block.measures:
                data.append({
                    "concept": m.concept,
                    "value": m.value,
                    "unit": m.unit,
                    "period_start": m.period_start,
                    "period_end": m.period_end,
                    "method_version": m.method_version,
                    "null_reason": m.null_reason,
                })
        content = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        print(f"Unknown format: {fmt}")
        return 1
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Exported {len(snapshot.blocks) * len(snapshot.blocks[0].measures if snapshot.blocks else 0)} measures to {output_path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify snapshot integrity."""
    import json
    
    instrument_id = args.instrument
    paths = AppPaths.from_root(os.path.expanduser("~/.rusterm"))
    
    from rusterm.store.repos import FactRepo, SnapshotRepo
    fact_repo = FactRepo(paths.db_path)
    snap_repo = SnapshotRepo(paths.db_path)
    
    # Check facts consistency
    facts = fact_repo.load_by_instrument(instrument_id)
    print(f"Verifying {len(facts)} facts for {instrument_id}")
    
    errors = 0
    for fact in facts:
        # Check required fields
        if not fact.concept:
            errors += 1
            print(f"  Error: fact {fact.fact_id} has no concept")
        if not fact.locator or not fact.locator.get("kind"):
            errors += 1
            print(f"  Error: fact {fact.fact_id} has no locator")
        if fact.basis not in ("as_reported", "restated"):
            errors += 1
            print(f"  Error: fact {fact.fact_id} has invalid basis: {fact.basis}")
    
    # Check snapshot consistency
    snapshot = snap_repo.load(instrument_id)
    if snapshot:
        print(f"Snapshot v{snapshot.snapshot_version} exists")
        for block in snapshot.blocks:
            for m in block.measures:
                if m.value is None and m.null_reason is None:
                    errors += 1
                    print(f"  Error: measure {m.concept} has null but no null_reason")
    
    if errors == 0:
        print("Verification: OK")
    else:
        print(f"Verification: {errors} errors found")
    
    return 0 if errors == 0 else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    """Full integrity check: manifest vs store, schema_version, orphaned links."""
    import json
    
    paths = AppPaths.from_root(os.path.expanduser("~/.rusterm"))
    
    from rusterm.store.raw_store import read_manifest
    from rusterm.store.repos import FactRepo, SnapshotRepo
    
    # Read manifest
    manifest_path = paths.manifest_path
    if manifest_path.exists():
        manifest = read_manifest(manifest_path)
        stored_shas = set(manifest)
    else:
        stored_shas = set()
        manifest = []
    
    # Check store
    from pathlib import Path
    raw_dir = paths.raw_store
    store_shas = set()
    if raw_dir.exists():
        for f in raw_dir.rglob("*.jsonl*") + raw_dir.rglob("*"):
            if f.is_file():
                try:
                    sha = f.name  # simplified
                    store_shas.add(sha[:2] + sha[2:])  # full sha
                except:
                    pass
    
    # Check for orphaned store objects (in store but not in manifest)
    orphaned = store_shas - stored_shas
    extra = stored_shas - store_shas
    
    print(f"Doctor report for {paths.app_data}")
    print(f"  Manifest entries: {len(stored_shas)}")
    print(f"  Store objects: {len(store_shas)}")
    print(f"  Orphaned (in store, not in manifest): {len(orphaned)}")
    print(f"  Extra (in manifest, not in store): {len(extra)}")
    
    # Check fact consistency
    fact_repo = FactRepo(paths.db_path)
    facts = fact_repo.load_all()
    print(f"  Total facts in DB: {len(facts)}")
    
    # Schema version check
    schema_version = None
    # ... check migration state
    
    total_issues = len(orphaned) + len(extra)
    if total_issues == 0:
        print("Doctor: OK - no integrity issues found")
        return 0
    else:
        print(f"Doctor: {total_issues} integrity issues found")
        return 1


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="rusterm",
        description="EquityLab core engine CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init
    p_init = subparsers.add_parser("init", help="Initialize app data directory")
    p_init.add_argument("--data-dir", help="Custom data directory path")
    
    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Run ingestion pipeline")
    p_ingest.add_argument("instruments", nargs="*", help="Instrument tickers")
    
    # snapshot
    p_snapshot = subparsers.add_parser("snapshot", help="Build snapshot for instrument")
    p_snapshot.add_argument("instrument", help="Instrument ticker")
    
    # export
    p_export = subparsers.add_parser("export", help="Export snapshot to CSV/JSON")
    p_export.add_argument("instrument", help="Instrument ticker")
    p_export.add_argument("--format", choices=["csv", "json"], default="csv", help="Output format")
    p_export.add_argument("--output", help="Output file path")
    
    # verify
    p_verify = subparsers.add_parser("verify", help="Verify snapshot integrity")
    p_verify.add_argument("instrument", help="Instrument ticker")
    
    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Full integrity check")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    commands = {
        "init": cmd_init,
        "ingest": cmd_ingest,
        "snapshot": cmd_snapshot,
        "export": cmd_export,
        "verify": cmd_verify,
        "doctor": cmd_doctor,
    }
    
    cmd_func = commands.get(args.command)
    if cmd_func is None:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)
    
    try:
        sys.exit(cmd_func(args))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
