"""ADR-0029: полная доходность — с реинвестированием дивидендов, за год
до as_of; просадка — по тому же ряду (решение пользователя 01.10.2026)."""
from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from rusterm.core.snapshot import make_snapshot_builder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = "2026-09-30"


@pytest.fixture()
def repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    r = RepoRegistry(conn, paths)
    r.instrument.upsert_issuer(Issuer("i1", "Corp", "US", None, None,
                                      "us_gaap", "USD"))
    r.instrument.upsert_instrument(Instrument("US-TR", "i1", None,
                                              "common", "active", None))
    return r


def _flat_prices(repos, price=100.0, days=400):
    end = dt.date.fromisoformat(AS_OF)
    rows = [{"date": (end - dt.timedelta(days=i)).isoformat(),
             "close": price, "currency": "USD"} for i in range(days)]
    repos.price.put_rows("US-TR", "yahoo", rows)


def _measures(repos):
    sid = repos.snapshot.latest_snapshot_id("US-TR")
    return {m[3]: (m[4], m[10]) for m in repos.snapshot.get_measures(sid)}


def test_flat_price_with_dividend_reinvested_gives_the_yield(repos):
    """Цена стоит на 100, на середине года — дивиденд 5: без
    реинвестирования доходность 0, с реинвестированием — 5%."""
    _flat_prices(repos)
    repos.corp_action.put("US-TR", "2026-03-31", "dividend", amount=5.0,
                          currency="USD")
    make_snapshot_builder(repos, AS_OF).build("US-TR", "i1", AS_OF)
    m = _measures(repos)
    value = float(m["total_return"][0])
    assert value == pytest.approx(100 / 95 - 1, rel=1e-9)
    assert float(m["drawdown"][0]) == pytest.approx(0.0)


def test_no_dividend_flat_price_is_zero_return(repos):
    _flat_prices(repos)
    make_snapshot_builder(repos, AS_OF).build("US-TR", "i1", AS_OF)
    assert float(_measures(repos)["total_return"][0]) == pytest.approx(0.0)


def test_short_series_refuses_with_words(repos):
    _flat_prices(repos, days=60)
    make_snapshot_builder(repos, AS_OF).build("US-TR", "i1", AS_OF)
    value, reason = _measures(repos)["total_return"]
    assert value is None and reason == "missing_data: price_close"
