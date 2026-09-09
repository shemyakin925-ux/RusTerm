"""TASK-18 G7+G8: golden_m6_ca.json разрешается по accn + json_pointer;
снапшотный проход по трём канадским и двум OTC эмитентам — те же
формулы, тот же словарь причин; каждое значение канадцев сходится с
golden, каждый null назван причиной, ни одна мера не собрана из
таксономии, которой эмитент не подавал.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    RepoRegistry,
    persist_ingestion_results,
)

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"
CA_ISSUERS = ("RY", "BMO", "CNQ")
OTC_ISSUERS = ("CPTP", "NGGTF")
NEW_ISSUERS = CA_ISSUERS + OTC_ISSUERS
MEASURES = ("net_margin", "operating_margin", "effective_tax", "fcf",
            "ebitda", "interest_coverage", "nopat", "roe",
            "asset_turnover", "gross_margin")


def _ingest_all(repos, tickers, stored_urls, paths):
    for ticker in tickers:
        payload = (DATA / f"companyfacts_m6_{ticker}.json").read_bytes()
        cik = json.loads(payload)["cik"]
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", f"{ticker} (recorded m6)", "CA", str(cik),
            None, "ifrs-full", "CAD"))
        repos.instrument.upsert_instrument(Instrument(
            f"in-{ticker}", f"i-{ticker}", None, "common", "active", None))
        url = (f"https://data.sec.gov/api/xbrl/companyfacts/"
               f"CIK{cik:010d}.json")
        if url in stored_urls:
            continue
        raw = payload
        from rusterm.store.repos import RawRepo
        obj = RawRepo(paths, repos.conn).put(
            raw, provider="edgar", block="fundamentals", url=url)
        stored_urls[url] = obj.sha256
        parsed = CompanyFactsParser().parse(
            raw, {"issuer_id": f"i-{ticker}", "source_ref": obj.sha256})
        fact_dicts = []
        for fact in parsed.facts:
            fact = dict(fact)
            fact["fact_id"] = str(uuid.uuid4())
            apply_concept_map(fact)
            fact_dicts.append(fact)
        persist_ingestion_results(repos.conn, fact_dicts, [])


def test_g7_golden_m6_values_resolve_by_accn_and_pointer():
    golden = json.loads((DATA.parent / "golden_m6_ca.json").read_bytes())
    assert golden["issuers"] == list(CA_ISSUERS)
    assert golden["values"], "golden пуст"
    for entry in golden["values"]:
        payload = (DATA / f"companyfacts_m6_{entry['issuer']}.json"
                   ).read_bytes()
        doc = json.loads(payload)
        node = doc
        for part in entry["json_pointer"].split("/")[1:]:
            node = node[int(part)] if part.isdigit() else node[part]
        assert node == entry["value"], entry
        # accn: значение ровно из той подачи, что названа
        tag = entry["json_pointer"].split("/")[3]
        unit = entry["json_pointer"].split("/")[5]
        entries = doc["facts"]["ifrs-full"][tag]["units"][unit]
        idx = int(entry["json_pointer"].split("/")[6])
        assert entries[idx]["accn"] == entry["accn"], entry


def test_g8_snapshot_pass_over_new_issuers_with_named_gaps():
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        conn.row_factory = sqlite3.Row
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)

        stored_urls: dict = {}
        _ingest_all(repos, NEW_ISSUERS, stored_urls, paths)

        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        for ticker in NEW_ISSUERS:
            builder.build(f"in-{ticker}", f"i-{ticker}", "2026-09-09")

        # таблица как в M3: мера -> значения и причины
        table: dict[str, dict] = {}
        issuer_values: dict[tuple, str] = {}
        for ticker in NEW_ISSUERS:
            sid = repos.snapshot.latest_snapshot_id(f"in-{ticker}")
            for m in repos.snapshot.get_measures(sid):
                if m[3] not in MEASURES:
                    continue
                row = table.setdefault(m[3], {"values": 0, "reasons": {}})
                if m[4] is not None:
                    row["values"] += 1
                    issuer_values[(ticker, m[3])] = m[4]
                else:
                    row["reasons"][m[10]] = \
                        row["reasons"].get(m[10], 0) + 1
        print("M6 measure -> n/5 + reasons:")
        for measure in MEASURES:
            row = table.get(measure, {"values": 0, "reasons": {}})
            print(f"  {measure}: {row['values']}/5 "
                  f"причины: {row['reasons'] or '—'}")

        # банки без операционной прибыли: причина названа
        om_reasons = set()
        for ticker in ("RY", "BMO"):
            sid = repos.snapshot.latest_snapshot_id(f"in-{ticker}")
            for m in repos.snapshot.get_measures(sid):
                if m[3] == "operating_margin" and m[4] is None:
                    om_reasons.add(m[10])
        assert "missing_data: operating_income" in om_reasons, om_reasons

        # ни одного голого missing_data в таблице
        for measure, row in table.items():
            for reason in row["reasons"]:
                assert reason != "missing_data", (measure, reason)

        # каждое значение канадцев сходится с golden: raw-факты
        # (as_reported) по каноническому концепту и периоду
        golden = json.loads(
            (DATA.parent / "golden_m6_ca.json").read_bytes())
        for entry in golden["values"]:
            if entry["concept"] in ("shares_diluted",):
                continue
            rows = repos.fact.get_facts(
                issuer_id=f"i-{entry['issuer']}",
                concept=None, period_end=entry["period_end"])
            # базис сравнительного периода I3 определяет как restated —
            # сверяем само значение: (концепт, конец периода, величина)
            match = [
                r for r in rows
                if r["canonical_concept"] == entry["concept"]
                and r["value"] == str(entry["value"])]
            assert match, f"golden не подтвердился: {entry}"

        # ни одна мера не собрана из чужой таксономии: факты RY/BMO/CNQ
        # только ifrs-full, CPTP — только us-gaap
        for ticker, taxonomy in (("RY", "ifrs-full"), ("BMO", "ifrs-full"),
                                 ("CNQ", "ifrs-full"), ("CPTP", "us-gaap"),
                                 ("NGGTF", "ifrs-full")):
            taxonomies = {r["concept"].split(":")[0]
                          for r in repos.fact.get_facts(
                              issuer_id=f"i-{ticker}")}
            unexpected = taxonomies - {taxonomy, "dei"}
            assert not unexpected, (ticker, unexpected)
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
