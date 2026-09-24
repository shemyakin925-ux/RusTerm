"""Дивидендная доходность из отчётности (координатор, 24.09.2026).

На базе пользователя div_yield был пуст у 43 из 44 бумаг: dps_ttm
брался только из корпоративных событий Twelve Data, а бесплатный тариф
отвечает на дивиденды 403. При этом 30 из 44 эмитентов подают
us-gaap:CommonStockDividendsPerShareDeclared, и карта концептов уже
размечает его как canonical «dps» (2 409 фактов в базе).

Правило (как ADR-0021 для прибыли и выручки): нет корпоративных событий
— берётся свежайший ГОДОВОЙ dps из отчётности, основание меры «annual».
Годовой dps, чей год кончился давно, — не «последние 12 месяцев»:
отказ stale_data (у Cleveland-Cliffs последние объявленные — 2020,
выплаты прекращены). Квартальные цифры за годовые не выдаются.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

TODAY = date.today()
AS_OF = TODAY.isoformat()


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-P", "i1", None, "common", "active", None))
    repos.price.put_rows("US-P", "twelvedata", [
        {"date": AS_OF, "close": 50.0, "currency": "USD"}])
    return conn, repos


def _dps(conn, start: date, end: date, value: float) -> None:
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, 'i1', 'us-gaap:CommonStockDividendsPerShareDeclared',
           ?, ?, 'duration', ?, 'USD/shares', 'USD', 'as_reported',
           'extracted', 's', '{}', 'companyfacts.v1', 'ok', 0, 'dps',
           'provider')""",
        (f"f-{start}-{end}", start.isoformat(), end.isoformat(),
         str(value)))


def _div_yield(repos):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build("US-P", "i1", AS_OF)
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-P"))
    m = next(r for r in rows if r[3] == "div_yield")
    return m[4], m[10]


def test_recent_annual_dps_gives_the_yield(env):
    conn, repos = env
    end = TODAY - timedelta(days=200)
    _dps(conn, end - timedelta(days=364), end, 1.0)
    value, reason = _div_yield(repos)
    assert reason is None
    assert float(value) == pytest.approx(1.0 / 50.0)


def test_stale_annual_dps_is_refused_not_used(env):
    conn, repos = env
    end = TODAY - timedelta(days=6 * 365)
    _dps(conn, end - timedelta(days=364), end, 1.0)
    value, reason = _div_yield(repos)
    assert value is None
    assert reason.startswith("stale_data: dps")


def test_quarterly_dps_is_not_passed_off_as_annual(env):
    conn, repos = env
    end = TODAY - timedelta(days=60)
    _dps(conn, end - timedelta(days=90), end, 0.25)
    value, reason = _div_yield(repos)
    assert value is None
    assert reason == "missing_data: dps_ttm"


def _quarters(conn, last_end: date, values: list[float],
              skip: int | None = None) -> None:
    """Подряд идущие кварталы, последний кончается last_end; skip —
    индекс квартала (0 = последний), который не подан."""
    end = last_end
    for idx, v in enumerate(values):
        start = end - timedelta(days=90)
        if idx != skip:
            _dps(conn, start, end, v)
        end = start - timedelta(days=1)


def test_four_consecutive_quarters_give_the_yield(env):
    """Bank of America, Capital One, Citi, Salesforce: свежие дивиденды
    подаются только поквартально, годовой dps старый или его нет."""
    conn, repos = env
    _quarters(conn, TODAY - timedelta(days=60), [0.28, 0.28, 0.28, 0.26])
    value, reason = _div_yield(repos)
    assert reason is None
    assert float(value) == pytest.approx((0.28 * 3 + 0.26) / 50.0)


def test_a_gap_in_the_quarters_is_refused(env):
    """Newmont: квартала нет — четыре подряд не набираются, суммы нет."""
    conn, repos = env
    _quarters(conn, TODAY - timedelta(days=60),
              [0.26, 0.26, 0.25, 0.25, 0.25], skip=2)
    value, reason = _div_yield(repos)
    assert value is None


def test_quarters_newer_than_a_stale_annual_win(env):
    """Годовой 2018 + свежие кварталы: берутся кварталы, а не отказ."""
    conn, repos = env
    old_end = TODAY - timedelta(days=7 * 365)
    _dps(conn, old_end - timedelta(days=364), old_end, 1.0)
    _quarters(conn, TODAY - timedelta(days=60), [0.3, 0.3, 0.3, 0.3])
    value, reason = _div_yield(repos)
    assert reason is None
    assert float(value) == pytest.approx(1.2 / 50.0)
