"""ТЗ-B1 B1.3: граница «ноль» против «нет данных».

Меры, у которых 0 достижим обоими путями (настоящий ноль входов и
отказ из-за нехватки), названы в REPORT-B1; до правок B1.1 различие
теряли три: invested_capital (нехватка cash/st_investments падала
TypeError, а не отказом), nopat (ставки нет, доход есть — (None, None)
без причины), drawdown (неположительные цены — молчаливый 0.0). Все
три закрыты отказом с именованной причиной, граничные тесты —
tests/test_b1_honesty.py.

Здесь — различимость В ВЫВОДЕ: два синтетических эмитента на одном
периоде, офлайн, без сети. ZERO подаёт operating_income=0 при живом
налоге — его nopat и fcf есть настоящие нули; NODATA подаёт тот же
налог и денежный поток, но молчит про operating_income — его nopat
обязан быть отказом «missing_data: operating_income» (цепочка C4
называет отвалившееся звено). Различие видно в строках меры (их читают
и census, и export --json) и в живом выводе `census --instrument …
--json`: у одного значение 0.0, у другого — причина из словаря.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    RepoRegistry,
    persist_ingestion_results,
)

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-09-19"
PERIOD = ("2025-01-01", "2025-12-31")


def _fact(issuer_id: str, concept: str, value: str) -> dict:
    return {
        "fact_id": str(uuid.uuid4()),
        "issuer_id": issuer_id,
        "listing_id": None,
        "concept": concept,
        "canonical_concept": concept,
        "concept_map_version": "synthetic.v1",
        "period_start": PERIOD[0],
        "period_end": PERIOD[1],
        "period_type": "duration",
        "value": value,
        "unit": "USD",
        "currency": "USD",
        "basis": "as_reported",
        "origin": "extracted",
        "source_ref": "synthetic-b1-3",
        "locator": {"kind": "synthetic",
                    "endpoint": "tests/test_b1_zero_vs_missing.py"},
        "parser_version": "synthetic.v1",
        "status": "ok",
    }


TAX = {"tax_expense": "20", "pretax_income": "100"}
CASH = {"ocf": "30", "capex": "30"}
FACTS = {
    # настоящий ноль: доход есть и он 0, налог и поток поданы
    "ZERO": {"operating_income": "0", **TAX, **CASH},
    # нет данных: тот же налог и поток, operating_income не подан
    "NODATA": {**TAX, **CASH},
}


@pytest.fixture()
def pair_env(tmp_path):
    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for ticker, facts in FACTS.items():
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", ticker, "US", "0000000000", None,
            "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            f"in-{ticker}", f"i-{ticker}", None, "common", "active",
            None))
        fact_dicts = [_fact(f"i-{ticker}", concept, value)
                      for concept, value in facts.items()]
        persist_ingestion_results(repos.conn, fact_dicts, [])
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build(f"in-{ticker}", f"i-{ticker}", AS_OF)
    yield repos, root
    conn.close()


def _measure_row(repos, ticker: str, measure: str) -> dict:
    sid = repos.snapshot.latest_snapshot_id(f"in-{ticker}")
    row = next((m for m in repos.snapshot.get_measures(sid)
                if m[3] == measure), None)
    assert row is not None, (ticker, measure)
    return {"value": row[4], "reason": row[10]}


def _cli_census(root: Path, ticker: str) -> dict:
    env = dict(os.environ, PYTHONPATH=str(ROOT),
               RUSTERM_ENV_FILE=str(root / "empty-env"))
    done = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(root),
         "census", "--instrument", f"in-{ticker}", "--json"],
        cwd=ROOT, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_pair_distinguishable_in_db_rows(pair_env):
    """Настоящий ноль и отсутствие входа различимы в строках меры."""
    repos, _ = pair_env
    zero_nopat = _measure_row(repos, "ZERO", "nopat")
    nodata_nopat = _measure_row(repos, "NODATA", "nopat")
    assert zero_nopat["reason"] is None
    assert float(zero_nopat["value"]) == 0.0
    assert nodata_nopat["value"] is None
    assert nodata_nopat["reason"] == "missing_data: operating_income"
    # effective_tax у обоих считается (0.2) — цепочке нечего вменять
    for ticker in ("ZERO", "NODATA"):
        row = _measure_row(repos, ticker, "effective_tax")
        assert row["reason"] is None
        assert float(row["value"]) == pytest.approx(0.2)
    # fcf = 30 - 30 = 0.0 — настоящий ноль у обоих
    for ticker in ("ZERO", "NODATA"):
        row = _measure_row(repos, ticker, "fcf")
        assert row["reason"] is None
        assert float(row["value"]) == 0.0


def test_pair_via_census_cli(pair_env):
    """Различие видно в живом выводе census --json: 0.0 против отказа.
    export --json читает те же строки меры (value/reason), отдельный
    прогон не добавляет различимости."""
    repos, root = pair_env
    zero = _cli_census(root, "ZERO")
    nodata = _cli_census(root, "NODATA")
    zero_nopat = next(m for m in zero["measures"]
                      if m["measure"] == "nopat")
    nodata_nopat = next(m for m in nodata["measures"]
                        if m["measure"] == "nopat")
    assert float(zero_nopat["value"]) == 0.0
    assert zero_nopat["reason"] is None
    assert nodata_nopat["value"] is None
    assert nodata_nopat["reason"] == "missing_data: operating_income"
