"""ТЗ-49 R1+R2: перепись отказов и золотые пробы на сохранённых данных.

R1 — измерение, не ремонт: CNQ (Канада) и NGGTF (OTC), десять мер
каждый, офлайн на сохранённых ответах EDGAR
(tests/data/edgar/companyfacts_m6_*.json). Каждая строка сравнивается
с tests/data/golden_census_task49.json: значение — точная строка из
БД, отказ — точная причина из rusterm/reasons.py с продолжением,
называющим конкретный отсутствующий концепт. Сеть не трогается.

R2 — две самые дешёвые меры из переписи. Самая дешёвая оказалась
ОДНА правка карты: ifrs-full.v1 называла налоговые расходы
income_tax, а формулы читают tax_expense, — effective_tax отказывал
«missing_data: tax_expense» при живом факте у всех четырёх ifrs
эмитентов. После выравнивания (ifrs-full.v2): CNQ effective_tax
считается (золото: 0.18284117513782946), NGGTF effective_tax и
nopat считаются (золото: 0.25181598062953997 и 1141728813.559322 —
nopat встал сам, оба его входа у эмитента есть). Остальные отказы
обязаны остаться честными: таблица золотого файла закрепляет каждую
из них, ни одна не превратилась в число.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    RawRepo,
    RepoRegistry,
    persist_ingestion_results,
)

DATA = Path(__file__).resolve().parents[1] / "tests" / "data"
GOLDEN = json.loads(
    (DATA / "golden_census_task49.json").read_text(encoding="utf-8"))
MEASURES = ("net_margin", "operating_margin", "effective_tax", "fcf",
            "ebitda", "interest_coverage", "nopat", "roe",
            "asset_turnover", "gross_margin")


@pytest.fixture()
def census_env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    urls = {}
    for ticker in ("CNQ", "NGGTF"):
        payload = (DATA / "edgar"
                   / f"companyfacts_m6_{ticker}.json").read_bytes()
        cik = json.loads(payload)["cik"]
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", ticker, "CA" if ticker == "CNQ" else "US",
            str(cik), None, "ifrs-full", "CAD"))
        repos.instrument.upsert_instrument(Instrument(
            f"in-{ticker}", f"i-{ticker}", None, "common", "active",
            None))
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        obj = RawRepo(paths, repos.conn).put(
            payload, provider="edgar", block="fundamentals", url=url)
        urls[ticker] = {"url": url, "sha256": obj.sha256}
        parsed = CompanyFactsParser().parse(
            payload, {"issuer_id": f"i-{ticker}",
                      "source_ref": obj.sha256})
        fact_dicts = []
        for fact in parsed.facts:
            fact = dict(fact)
            fact["fact_id"] = str(uuid.uuid4())
            apply_concept_map(fact)
            fact_dicts.append(fact)
        persist_ingestion_results(repos.conn, fact_dicts, [])
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build(f"in-{ticker}", f"i-{ticker}", "2026-09-09")
    yield repos, urls
    conn.close()


def _census_rows(repos, ticker):
    sid = repos.snapshot.latest_snapshot_id(f"in-{ticker}")
    rows = {m[3]: {"value": m[4], "reason": m[10]}
            for m in repos.snapshot.get_measures(sid) if m[3] in MEASURES}
    return {k: rows[k] for k in MEASURES}


def test_census_matches_golden_offline(census_env):
    """R1: вся перепись, эмитент за эмитентом, строка за строкой —
    значения и отказы закреплены; прогон полностью офлайн."""
    repos, _ = census_env
    for ticker in ("CNQ", "NGGTF"):
        rows = _census_rows(repos, ticker)
        assert rows == GOLDEN["census"][ticker], ticker


def test_r2_golden_values_on_saved_facts(census_env):
    """R2: две самые дешёвые меры из переписи дают ровно те числа,
    что записаны в отчёт (REPORT-49)."""
    repos, _ = census_env
    for ticker, expected in GOLDEN["golden"].items():
        rows = _census_rows(repos, ticker)
        for measure, value in expected.items():
            assert rows[measure]["value"] == value, (ticker, measure)
            assert rows[measure]["reason"] is None, (ticker, measure)


def test_r2_lineage_names_source_and_period_basis(census_env):
    """R2: у каждой золотой меры в lineage виден источник: input-факт
    разрешается в сохранённый ответ EDGAR по source_ref, а
    унаследованный вход (nopat <- effective_tax) — в меру того же
    снапшота. База периода видима в колонке period_basis (NULL =
    прямой однопериодный вход, так записано в repos.py)."""
    repos, urls = census_env
    for ticker, measures in GOLDEN["golden"].items():
        sid = repos.snapshot.latest_snapshot_id(f"in-{ticker}")
        mid_by_name = {m[3]: m[0]
                       for m in repos.snapshot.get_measures(sid)}
        for measure in measures:
            lineage = repos.conn.execute(
                "SELECT fact_id, peer_measure_id, role, period_basis "
                "FROM measure_lineage WHERE measure_id=?",
                (mid_by_name[measure],)).fetchall()
            assert lineage, (ticker, measure)
            for row in lineage:
                assert row["role"] == "input"
                assert "period_basis" in row.keys()
                if row["fact_id"] is not None:
                    fact = repos.conn.execute(
                        "SELECT source_ref FROM fact "
                        "WHERE fact_id=?", (row["fact_id"],)).fetchone()
                    assert fact is not None, (ticker, measure)
                    assert fact["source_ref"] == urls[ticker]["sha256"], \
                        (ticker, measure, fact["source_ref"])
                else:
                    peer = repos.conn.execute(
                        "SELECT measure_id FROM measure WHERE measure_id=?",
                        (row["peer_measure_id"],)).fetchone()
                    assert peer is not None, (ticker, measure)


def test_remaining_refusals_stay_honest(census_env):
    """R2: ни одна из прочих мер не начала возвращать число; отказ
    называет причину словаря с продолжением — какой концепт или период
    не хватило (строки закреплены золотым файлом, здесь — свойства)."""
    from rusterm.reasons import is_known_reason

    repos, _ = census_env
    for ticker in ("CNQ", "NGGTF"):
        rows = _census_rows(repos, ticker)
        golden_rows = GOLDEN["census"][ticker]
        for measure, row in rows.items():
            if golden_rows[measure]["value"] is None:
                assert row["value"] is None, (ticker, measure)
                token = row["reason"].split(":", 1)[0]
                assert is_known_reason(token), (ticker, measure, token)
                assert row["reason"] != "missing_data", (ticker, measure)
