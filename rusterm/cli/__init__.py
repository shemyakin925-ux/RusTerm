"""CLI: init, ingest, snapshot, export, verify, doctor.

Точка входа rusterm.cli:main (pyproject.toml). Ни строки Qt; SQL только
в rusterm/store — команды оркестрируют store и core, сами в базу не ходят.
Все операции офлайн, на синтетических данных.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

from rusterm.core.export import snapshot_to_csv, snapshot_to_json
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.pipeline import IngestionPipeline
from rusterm.providers import SyntheticDisclosuresProvider
from rusterm.store.db import apply_migrations, current_schema_version, open_connection
from rusterm.store.doctor import doctor_report
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RepoRegistry,
    SnapshotRepo,
)
from rusterm.store.raw_store import decompress_object

# Синтетическая цель сбора для CLI-прогонов (помечена synthetic).
DEMO_ISSUER = "issuer-cli-demo"
DEMO_INSTRUMENT = "US-CLI-DEMO"


def _open(root: str):
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    return paths, open_connection(paths)


def cmd_init(args) -> int:
    paths, conn = _open(args.root)
    applied = apply_migrations(conn)
    print(f"каталог: {args.root}")
    print(f"применено миграций: {len(applied)}; "
          f"schema_version={current_schema_version(conn)}")
    conn.close()
    return 0


def _ensure_demo_instrument(conn) -> None:
    instruments = InstrumentRepo(conn)
    instruments.upsert_issuer(Issuer(DEMO_ISSUER, "CLI Demo Corp (synthetic)",
                                     "US", None, None, "us_gaap", "USD"))
    instruments.upsert_instrument(Instrument(DEMO_INSTRUMENT, DEMO_ISSUER,
                                             None, "common", "active", None))


def cmd_ingest(args) -> int:
    paths, conn = _open(args.root)
    apply_migrations(conn)
    _ensure_demo_instrument(conn)
    repos = RepoRegistry(conn, paths)
    pipe = IngestionPipeline(repos, {"synthetic": SyntheticDisclosuresProvider()})
    result = pipe.run(DEMO_INSTRUMENT, DEMO_ISSUER, "synthetic")
    print(f"заданий закрыто: {result.jobs_done}; фактов: {result.facts_stored}; "
          f"дублей sha256: {result.duplicates}; неразобрано (E4): "
          f"{result.needs_verification}; suspect (E5): {result.suspects}")
    conn.close()
    return 0


def cmd_snapshot(args) -> int:
    paths, conn = _open(args.root)
    apply_migrations(conn)
    _ensure_demo_instrument(conn)
    builder = SnapshotBuilder(SnapshotRepo(conn), RepoRegistry(conn, paths).peer_set)
    result = builder.build(DEMO_INSTRUMENT, DEMO_ISSUER, args.as_of)
    print(f"снапшот v{result.version}: {result.snapshot_id}")
    print(f"мер: {result.measures}; перцентилей: {result.percentiles}")
    if result.diff.metric_changes:
        print("изменение метрик: " + "; ".join(
            f"{c}: {o} -> {n}" for c, o, n in result.diff.metric_changes))
    if result.diff.revisions:
        print("ревизии: " + "; ".join(f"{c} за {p}"
                                      for c, p in result.diff.revisions))
    conn.close()
    return 0


def cmd_export(args) -> int:
    paths, conn = _open(args.root)
    repo = SnapshotRepo(conn)
    snapshot_id = repo.latest_snapshot_id(DEMO_INSTRUMENT)
    if snapshot_id is None:
        print("снапшотов нет — сначала snapshot", file=sys.stderr)
        conn.close()
        return 1
    snapshot = repo.get_snapshot(snapshot_id)
    measures = repo.get_measures(snapshot_id)
    text = (snapshot_to_csv(measures) if args.format == "csv"
            else snapshot_to_json(snapshot, measures))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"экспорт снапшота v{snapshot['version']} -> {args.out}")
    else:
        print(text)
    conn.close()
    return 0


def cmd_verify(args) -> int:
    """Процесс 5, узел 2: ground truth с origin=manual; извлечённый факт
    не удаляется, получает superseded_by."""
    paths, conn = _open(args.root)
    fact_repo = RepoRegistry(conn, paths).fact
    facts = fact_repo.get_facts(issuer_id=DEMO_ISSUER, concept=args.concept)
    facts = [f for f in facts if f["status"] == "ok" and f["basis"] == "as_reported"]
    if not facts:
        print(f"фактов {args.concept} нет — править нечего", file=sys.stderr)
        conn.close()
        return 1
    old = facts[0]
    new_id = str(uuid.uuid4())
    fact_repo.insert_fact(
        fact_id=new_id, issuer_id=old["issuer_id"], listing_id=None,
        concept=old["concept"], period_start=old["period_start"],
        period_end=old["period_end"], period_type=old["period_type"],
        value=args.value, unit=old["unit"], currency=old["currency"],
        basis=old["basis"], origin="manual", source_ref=old["source_ref"],
        locator=dict(old["locator"] if isinstance(old["locator"], dict)
                     else json.loads(old["locator"])),
        parser_version="manual.v1", status="ok")
    fact_repo.mark_superseded(old["fact_id"], new_id)
    print(f"manual-факт {new_id} записан, {old['fact_id']} помечен superseded")
    conn.close()
    return 0


def cmd_doctor(args) -> int:
    paths, conn = _open(args.root)
    report = doctor_report(paths, conn)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    conn.close()
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rusterm", description="EquityLab: локальный терминал (ядро)")
    parser.add_argument("--root", default=".", help="каталог данных")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="создать каталог данных и применить миграции")
    sub.add_parser("ingest", help="сбор по синтетическому провайдеру")
    p_snap = sub.add_parser("snapshot", help="собрать снапшот")
    p_snap.add_argument("--as-of", default="2024-12-31")
    p_exp = sub.add_parser("export", help="экспорт последнего снапшота")
    p_exp.add_argument("--format", choices=("json", "csv"), default="json")
    p_exp.add_argument("--out", default=None)
    p_ver = sub.add_parser("verify", help="ручное исправление факта")
    p_ver.add_argument("--concept", required=True)
    p_ver.add_argument("--value", required=True)
    sub.add_parser("doctor", help="самопроверка базы и store")
    args = parser.parse_args(argv)

    commands = {
        "init": cmd_init, "ingest": cmd_ingest, "snapshot": cmd_snapshot,
        "export": cmd_export, "verify": cmd_verify, "doctor": cmd_doctor,
    }
    return commands[args.command](args)
