"""ТЗ-31 C2: шесть оценочных мер получают входы из реальных данных.

- булавка-преемник (карта): us-gaap вырос из состояния TASK-18 ровно
  на посылках ТЗ-31 C2, ни один прежний тег не тронут;
- золотой тест: реальные значения фактов Apple (companyfacts,
  14.09.2026) + записанный ряд цен + записанные дивиденды вендора —
  шесть мер считаются, числа закреплены;
- dps_ttm — по скользящему окну 365 дней из corporate_action
  (ADR-0020: база вендорских дивидендов = база цены);
- minority_interest: NCI ни разу не отчитан — 0.0 производно от
  набора фактов.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.normalize.concepts import CONCEPT_MAP, CONCEPT_MAP_VERSION
from rusterm.pipeline import apply_concept_map
from rusterm.providers import twelvedata as td
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry)

ROOT = Path(__file__).resolve().parents[1]
_DATA = ROOT / "tests" / "data" / "twelvedata"

FAKE_UA = "Synthetic Test t.invalid"


def _payload(name: str) -> dict:
    return json.loads((_DATA / name).read_text(encoding="utf-8"))


# ── булавка-преемник: карта выросла, не переписана ─────────────────────

def test_c2_map_grew_from_task_start():
    """Преемник булавки «карта байт-в-байт» (test_ifrs_map, xfail):
    карта TASK-18 (237a7) — подмножество текущей; дельта РОВНО
    посылки ТЗ-31 C2; версия us-gaap.v4."""
    old_src = subprocess.run(
        ["git", "show", "23737a7:rusterm/normalize/concepts.py"],
        capture_output=True, text=True, check=True).stdout
    namespace: dict = {}
    exec(compile(old_src, "task_start_concepts.py", "exec"), namespace)
    old_map = namespace["CONCEPT_MAP"]
    for concept, tags in old_map.items():
        assert concept in CONCEPT_MAP, f"концепт {concept} исчез"
        new_tags = CONCEPT_MAP[concept]
        assert tags == new_tags or (
            # единственное расширение дельты: теги дописываются В КОНЕЦ
            new_tags[:len(tags)] == tags
            and len(new_tags) > len(tags)), (concept, tags, new_tags)
    delta = {c for c in CONCEPT_MAP if c not in old_map}
    assert delta == {"total_debt", "shares_outstanding"}, delta
    # единственное расширенное кортеж — st_investments (ТЗ-31 C2)
    assert CONCEPT_MAP["st_investments"] == \
        old_map["st_investments"] + ("MarketableSecuritiesCurrent",)
    assert CONCEPT_MAP_VERSION == "us-gaap.v4"
    # новый тег штампует канонический концепт и версию карты
    fact = {"concept": "us-gaap:CommonStockSharesOutstanding"}
    apply_concept_map(fact)
    assert fact["canonical_concept"] == "shares_outstanding"
    assert fact["concept_map_version"] == "us-gaap.v4"


# ── золотой тест шести мер на реальных значениях ───────────────────────

_AS_OF = "2026-08-12"          # на следующий день после последней цены
_INSTANT = "2026-06-27"        # момент баланса Apple (10-Q)
_FY = ("2024-09-29", "2025-09-27")   # годовой период Apple (10-K)

# Реальные значения из companyfacts AAPL (сырьё в raw-хранилище
# ~/.rusterm, указатели /facts/us-gaap/<тег>/units/<unit>/...)
_FACTS = [
    # (canonical, value, unit, start, end, period_type)
    ("shares_outstanding", "14608963000", "shares", _INSTANT, _INSTANT,
     "instant"),
    ("total_debt", "82300000000", "USD", _INSTANT, _INSTANT, "instant"),
    ("cash", "39544000000", "USD", _INSTANT, _INSTANT, "instant"),
    ("st_investments", "22855000000", "USD", _INSTANT, _INSTANT,
     "instant"),
    ("total_equity", "107520000000", "USD", _INSTANT, _INSTANT,
     "instant"),
    ("operating_income", "133050000000", "USD", _FY[0], _FY[1],
     "duration"),
    ("d_and_a", "11698000000", "USD", _FY[0], _FY[1], "duration"),
    ("tax_expense", "20719000000", "USD", _FY[0], _FY[1], "duration"),
    ("pretax_income", "132729000000", "USD", _FY[0], _FY[1],
     "duration"),
]


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-g", "Apple Inc.", "US", "320193", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-G", "i-g", None, "common", "active", None))
    repos.instrument.upsert_listing = repos.instrument.upsert_listing
    obj = repos.raw.put(b'{"golden": 1}', provider="synthetic",
                        block="fundamentals")
    for canonical, value, unit, start, end, ptype in _FACTS:
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
               period_end, period_type, value, unit, currency, basis,
               origin, source_ref, locator, parser_version, status,
               ingested_at, canonical_concept, source_kind)
               VALUES (?, 'i-g', ?, ?, ?, ?, ?, ?, 'USD',
               'as_reported', 'extracted', ?, '{}',
               'companyfacts.v1', 'ok', 0, ?, 'provider')""",
            (f"f-g-{canonical}-{end}", canonical, start, end, ptype,
             value, unit, obj.sha256, canonical))
    conn.commit()
    # реальные строки цен и дивидендов из записанных payload
    price_rows = td.TwelveDataProvider.parse_series(
        _payload("time_series_AAPL_div_window.json"))
    repos.price.put_rows("US-G", "twelvedata", price_rows)
    dividends, currency, _skipped = td.TwelveDataProvider.parse_dividends(
        _payload("dividends_AAPL_full.json"))
    assert currency == "USD"
    for d in dividends:
        repos.corp_action.put("US-G", d["ex_date"], "dividend",
                              amount=d["amount"], currency=currency)
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price,
                              corp_action_repo=repos.corp_action)
    builder.build("US-G", "i-g", _AS_OF)
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-G"))
    return conn, {m[3]: m for m in rows}


def test_six_valuation_measures_have_golden_values(env):
    """Шесть мер на реальных входах; числа закреплены за ночью.
    price_close = 304.91 (2026-08-11); dps_ttm = 0.26+0.26+0.27+0.27
    по окну 365 дней; ebitda/год = 133.05e9 + 11.698e9; minority = 0
    (NCI ни разу не отчитан)."""
    conn, by_concept = env

    def value(concept):
        row = by_concept[concept]
        assert row[4] is not None, (concept, row[10])
        return float(row[4])

    price = 304.91
    shares = 14_608_963_000.0
    mcap = price * shares
    ev = mcap + 82_300_000_000.0 - 39_544_000_000.0 \
        - 22_855_000_000.0 + 0.0
    ic = 107_520_000_000.0 + 0.0 + 82_300_000_000.0 \
        - 39_544_000_000.0 - 22_855_000_000.0
    rate = 20_719_000_000.0 / 132_729_000_000.0
    nopat = 133_050_000_000.0 * (1.0 - rate)
    ebitda_fy = 133_050_000_000.0 + 11_698_000_000.0
    dps_ttm = 0.26 + 0.26 + 0.27 + 0.27

    assert value("market_cap") == pytest.approx(mcap, rel=1e-12)
    assert value("market_cap_total") == pytest.approx(mcap, rel=1e-12)
    assert value("ev") == pytest.approx(ev, rel=1e-12)
    assert value("pb") == pytest.approx(mcap / 107_520_000_000.0,
                                        rel=1e-12)
    assert value("ev_ebitda") == pytest.approx(ev / ebitda_fy,
                                               rel=1e-12)
    assert value("div_yield") == pytest.approx(dps_ttm / price,
                                               rel=1e-12)
    assert value("roic") == pytest.approx(nopat / ic, rel=1e-12)
    conn.close()


def test_golden_units_currencies_and_periods(env):
    """Валюты и периоды: капитализация в USD цены; ev_ebitda/roic —
    ratio; годовой знаменатель виден в периоде фактов lineage."""
    conn, by_concept = env
    assert by_concept["market_cap"][5] == "USD"
    assert by_concept["market_cap_total"][5] == "USD"
    assert by_concept["ev"][5] == "USD"
    for concept in ("pb", "ev_ebitda", "div_yield", "roic"):
        assert by_concept[concept][5] == "ratio", concept
    # dps_ttm без факта: значение пришло из corporate_action
    assert by_concept["div_yield"][4] is not None
    # ТЗ-32 D6: база периода видна в lineage — годовое приближение
    # (annual) у ev_ebitda и roic, окно 365 дней (ttm) у div_yield
    for concept in ("ev_ebitda", "roic"):
        mid = by_concept[concept][0]
        bases = {r[0] for r in conn.execute(
            """SELECT period_basis FROM measure_lineage
               WHERE measure_id=? AND period_basis IS NOT NULL""",
            (mid,))}
        assert bases == {"annual"}, (concept, bases)
    div_mid = by_concept["div_yield"][0]
    bases = {r[0] for r in conn.execute(
        """SELECT period_basis FROM measure_lineage_ca
           WHERE measure_id=?""", (div_mid,))}
    assert bases == {"ttm"}, bases
    # годовой период назван: FY2025 у знаменателя ev_ebitda
    mid = by_concept["ev_ebitda"][0]
    periods = {r[0] for r in conn.execute(
        """SELECT f.period_end FROM measure_lineage l
           JOIN fact f ON f.fact_id = l.fact_id
           WHERE l.measure_id=? AND l.period_basis='annual'""", (mid,))}
    assert "2025-09-27" in periods, periods
    conn.close()


def test_dps_ttm_window_is_rolling_365_days(tmp_path):
    """Окно dps_ttm: дивиденд ровно на границе 365 дней не входит;
    сумма идёт по ex_date в (as_of-365, as_of]."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-w", "Corp w", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-W", "i-w", None, "common", "active", None))
    repos.corp_action.put("US-W", "2025-08-12", "dividend",
                          amount=9.99, currency="USD")   # граница — нет
    repos.corp_action.put("US-W", "2025-08-13", "dividend",
                          amount=1.0, currency="USD")
    repos.corp_action.put("US-W", "2026-08-12", "dividend",
                          amount=2.0, currency="USD")
    repos.price.put_rows("US-W", "twelvedata",
                         [{"date": "2026-08-12", "close": 100.0,
                           "currency": "USD"}])
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price,
                              corp_action_repo=repos.corp_action)
    builder.build("US-W", "i-w", "2026-08-12")
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-W"))
    dy = next(m for m in rows if m[3] == "div_yield")
    assert float(dy[4]) == pytest.approx(3.0 / 100.0, rel=1e-12), dy[10]
    # I4: входы мероприятия окна видны в lineage (миграция 42)
    ca_lineage = repos.snapshot.lineage_ca(
        next(m[0] for m in rows if m[3] == "div_yield"))
    assert [c["ex_date"] for c in ca_lineage] == \
        ["2025-08-13", "2026-08-12"], ca_lineage
    conn.close()
