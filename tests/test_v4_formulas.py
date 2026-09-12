"""TASK-9 V4: формулы §3 считаются на настоящих данных (AAPL payload).

net_margin и баланс-мера (roe/asset_turnover) дают значения с правильным
периодом; каждая формула §3 присутствует в мерах — со значением или с
причиной из фиксированного набора; ни одна не пропадает молча.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.normalize.concepts import CONCEPT_MAP_VERSION
from rusterm.parsers import CompanyFactsParser
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RawRepo,
    RepoRegistry,
    persist_ingestion_results,
)
from rusterm.pipeline import apply_concept_map

DATA = Path(__file__).resolve().parents[1] / "tests" / "data"

# Формулы §3 data-dictionary (плюс percentile — он живёт в проходе 2
# с peer set и в этот реестр не входит)
FORMULAS_S3 = {
    "ebitda", "gross_margin", "operating_margin", "net_margin",
    "effective_tax", "nopat", "invested_capital", "roic", "roe",
    "asset_turnover", "net_debt", "net_debt_ebitda", "interest_coverage",
    "fcf", "fcf_yield", "market_cap", "market_cap_total", "ev", "pe",
    "pb", "ps", "ev_ebitda", "div_yield",
}

FIXED_REASONS = {
    "missing_data", "period_mismatch", "missing_prior_period",
    "concept_not_mapped", "denominator_zero", "negative_denominator",
}


def _setup_aapl():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "cik-320193", "Apple Inc.", "US", "320193", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAPL", "cik-320193", None, "common", "active", None))

    raw = (DATA / "edgar" / "companyfacts_m3_AAPL.json").read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    obj = repos.raw.put(raw, provider="edgar", block="fundamentals",
                        url="https://data.sec.gov/api/xbrl/companyfacts/"
                            "CIK0000320193.json")
    assert obj.sha256 == sha
    result = CompanyFactsParser().parse(raw, {"issuer_id": "cik-320193",
                                              "source_ref": sha})
    fact_dicts = []
    for fact in result.facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        fact_dicts.append(fact)
    persist_ingestion_results(conn, fact_dicts, [])
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    builder.build("US-AAPL", "cik-320193", "2026-09-08")
    return tmpdir, conn, repos


def test_v4_net_margin_and_balance_measure_non_null_with_period():
    tmpdir, conn, repos = _setup_aapl()
    try:
        snap = repos.snapshot.latest_snapshot_id("US-AAPL")
        measures = repos.snapshot.get_measures(snap)

        net_margin = next(m for m in measures if m[3] == "net_margin")
        assert net_margin[4] is not None, "net_margin пуст на реальных данных"
        assert net_margin[6] != "" and net_margin[7] != ""
        assert net_margin[6] < net_margin[7]  # годовой duration

        # баланс-мера: roe или asset_turnover (двухпериодные)
        balance = {m[3]: m for m in measures
                   if m[3] in ("roe", "asset_turnover")}
        non_null = [m for m in balance.values() if m[4] is not None]
        assert non_null, "ни одна баланс-мера не посчиталась"
        for m in non_null:
            assert m[6] != "" and m[7] != ""
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_v4_every_s3_formula_present_with_value_or_fixed_reason():
    tmpdir, conn, repos = _setup_aapl()
    try:
        snap = repos.snapshot.latest_snapshot_id("US-AAPL")
        measures = {m[3]: m for m in repos.snapshot.get_measures(snap)}
        missing = FORMULAS_S3 - set(measures)
        assert not missing, f"формулы §3 отсутствуют: {missing}"
        for name in FORMULAS_S3:
            m = measures[name]
            if m[4] is not None:
                continue
            assert m[10] in FIXED_REASONS or m[10].startswith(
                "missing_data: price_close"), (
                f"{name}: причина {m[10]!r} вне фиксированного набора")
        # ни одна не пропала молча: пустых причин нет
        for name, m in measures.items():
            if m[4] is None:
                assert m[10], f"{name}: null без причины"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_v4_nopat_chain_uses_computed_effective_tax():
    tmpdir, conn, repos = _setup_aapl()
    try:
        snap = repos.snapshot.latest_snapshot_id("US-AAPL")
        measures = {m[3]: m for m in repos.snapshot.get_measures(snap)}
        et = measures["effective_tax"]
        nopat = measures["nopat"]
        if et[4] is None:
            # ставки нет — nopat пуст с причиной, а не с выдуманной ставкой
            assert nopat[4] is None
            assert nopat[10] in FIXED_REASONS
        else:
            assert nopat[4] is not None
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
