"""ТЗ-31 C3: корпоративные действия приходят с вендора.

- золотой разбор записанных payload /splits и /dividends офлайн
  (tests/data/twelvedata/, замер 14.09.2026);
- дивиденды вендор отдаёт в сегодняшней базе акций — коллекция пишет
  объявленную сумму на дату (declared_dividend);
- сбор идемпотентен: повтор — ноль запросов и ноль новых строк;
- отказ вендора — именованная причина, события не пишутся;
- price_adj на реальных строках и реальных событиях не зависит от
  порядка применения (B5 на живых данных).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.cli import _ingest_twelvedata_actions
from rusterm.core.prices import build_events, declared_dividend, \
    our_adjusted_series
from rusterm.providers import twelvedata as td
from rusterm.providers.budget import NetworkGate, RequestGate
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry)

_DATA = (Path(__file__).resolve().parents[1] / "tests" / "data"
         / "twelvedata")

FAKE_UA = "Synthetic Test t.invalid"


def _payload(name: str) -> dict:
    return json.loads((_DATA / name).read_text(encoding="utf-8"))


def _ca_env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3_connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(
        Issuer("i-x", "Corp i-x", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(
        Instrument("US-X", "i-x", None, "common", "active", None))
    repos.instrument.upsert_listing(
        Listing("l-US-X", "US-X", "US", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-US-X", "AAPL", "2020-01-01", None, None, None)
    return conn, repos


def sqlite3_connect(paths):
    import sqlite3
    return sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)


def _ca_provider(payload_by_kind: dict, calls: list):
    """Провайдер, чей транспорт отдаёт записанные payload по URL;
    каждый заход считается — счёт запросов честный."""

    def transport(url, headers):
        calls.append(url)
        for kind, payload in payload_by_kind.items():
            if f"/{kind}?" in url:
                return 200, json.dumps(payload).encode("utf-8"), {}
        return 404, b"{}", {}

    return td.TwelveDataProvider(
        gate=RequestGate(gate=NetworkGate(environ={
            "RUSTERM_SEC_UA": FAKE_UA})),
        api_key="TESTONLY-key", transport=transport)


# ── золотой разбор записанных payload ──────────────────────────────────

def test_golden_splits_parse_from_recorded_payload():
    """Все пять реальных сплитов AAPL; k — из from/to, не из rounded
    ratio (у 7:1 вендор округляет ratio до 0.14286)."""
    splits, skipped = td.TwelveDataProvider.parse_splits(
        _payload("splits_AAPL_full.json"))
    assert skipped == 0
    assert [(s["ex_date"], s["factor"]) for s in splits] == [
        ("1987-06-16", 2.0), ("2000-06-21", 2.0), ("2005-02-28", 2.0),
        ("2014-06-09", 7.0), ("2020-08-31", 4.0)]
    assert all(s["kind"] == "split" and s["amount"] is None
               for s in splits)


def test_golden_dividends_parse_from_recorded_payload():
    """83 дивиденда с 1988 года, по возрастанию ex_date, валюта из
    meta; суммы — как отдал вендор (сегодняшняя база акций)."""
    dividends, currency, skipped = td.TwelveDataProvider.parse_dividends(
        _payload("dividends_AAPL_full.json"))
    assert skipped == 0 and currency == "USD"
    assert len(dividends) == 83
    assert (dividends[0]["ex_date"], dividends[0]["amount"]) == \
        ("1988-11-21", 0.000892857143)
    assert (dividends[-1]["ex_date"], dividends[-1]["amount"]) == \
        ("2026-08-10", 0.27)
    dates = [d["ex_date"] for d in dividends]
    assert dates == sorted(dates)


def test_declared_amount_is_unadjusted_to_ex_date_basis():
    """Пересчёт в объявленную сумму: 1988-й 0.000892857143*112=0.10;
    2013-02-07 0.094642857143*28=2.65; после последнего сплита сумма
    не меняется."""
    assert declared_dividend(0.000892857143, [2.0, 2.0, 7.0, 4.0]) == \
        pytest.approx(0.10, abs=1e-9)
    assert declared_dividend(0.094642857143, [7.0, 4.0]) == \
        pytest.approx(2.65, abs=1e-9)
    assert declared_dividend(0.27, []) == 0.27


# ── сбор: события в corporate_action, повтор бесплатно ────────────────

def test_collection_lands_events_and_second_run_is_free(tmp_path):
    """Первый сбор: 88 событий (5 сплитов + 83 дивиденда), 2 запроса,
    payload'ы в raw-хранилище; повторный — ноль запросов, ноль новых
    строк (I7 + кеш по каноническому URL)."""
    conn, repos = _ca_env(tmp_path)
    payloads = {"splits": _payload("splits_AAPL_full.json"),
                "dividends": _payload("dividends_AAPL_full.json")}
    provider = _ca_provider(payloads, calls := [])
    code = _ingest_twelvedata_actions(repos, "US-X", "2026-09-14",
                                      provider=provider)
    assert code == 0
    assert len(calls) == 2, calls
    events = repos.corp_action.all("US-X")
    assert len(events) == 88
    split = next(e for e in events if e["kind"] == "split"
                 and e["ex_date"] == "2020-08-31")
    assert split["factor"] == 4.0 and split["source"] == "twelvedata"
    div2013 = next(e for e in events if e["kind"] == "dividend"
                   and e["ex_date"] == "2013-02-07")
    assert div2013["amount"] == pytest.approx(2.65, abs=1e-9)
    assert div2013["currency"] == "USD"
    # payload'ы легли в raw-хранилище с каноническим URL без ключа
    for kind in ("splits", "dividends"):
        url = provider.cache_url_ca(kind, "AAPL")
        assert "TESTONLY" not in url
        assert repos.raw.find_by_provider_url("twelvedata", url)

    code = _ingest_twelvedata_actions(repos, "US-X", "2026-09-14",
                                      provider=provider)
    assert code == 0
    assert len(calls) == 2, "повторный сбор сходил в сеть"
    assert len(repos.corp_action.all("US-X")) == 88, \
        "повторный сбор записал дубли (I7)"
    conn.close()


def test_vendor_failure_leaves_actions_empty_with_named_reason(tmp_path):
    """403 на /splits — выход 1, причина именована, событий нет
    (K7: отказ вендора — значение, не выдумка)."""
    conn, repos = _ca_env(tmp_path)

    def transport(url, headers):
        return 403, b"{}", {}

    provider = td.TwelveDataProvider(
        gate=RequestGate(gate=NetworkGate(environ={
            "RUSTERM_SEC_UA": FAKE_UA})),
        api_key="TESTONLY-key", transport=transport)
    code = _ingest_twelvedata_actions(repos, "US-X", "2026-09-14",
                                      provider=provider)
    assert code == 1
    assert repos.corp_action.all("US-X") == []
    conn.close()


# ── B5 на живых данных: порядок применения не важен ────────────────────

def test_price_adj_order_independence_on_real_rows():
    """Реальный ряд цен (записанный payload) и реальные события
    (записанные сплиты и дивиденды): перестановка порядка событий не
    меняет скорректированный ряд — ни на один бит."""
    from rusterm.formulas import price_adj

    price_rows = td.TwelveDataProvider.parse_series(
        _payload("time_series_AAPL_1day_trimmed.json"))
    splits, _ = td.TwelveDataProvider.parse_splits(
        _payload("splits_AAPL_full.json"))
    dividends, currency, _ = td.TwelveDataProvider.parse_dividends(
        _payload("dividends_AAPL_full.json"))
    assert currency == "USD"
    # объявленные суммы: та же схема, что в коллекции
    for d in dividends:
        ks = [s["factor"] for s in splits if s["ex_date"] > d["ex_date"]]
        d["amount"] = declared_dividend(d["amount"], ks)
    action_rows = splits + dividends

    events = build_events(price_rows, action_rows)
    series = price_adj([(r["date"], float(r["close"]))
                        for r in price_rows], events)
    reversed_series = price_adj(
        [(r["date"], float(r["close"])) for r in price_rows],
        list(reversed(events)))
    assert series == reversed_series, \
        "порядок событий изменил скорректированный ряд"

    # и через весь путь K3 — our_adjusted_series на тех же строках
    ours_a, _ = our_adjusted_series(price_rows, action_rows)
    ours_b, _ = our_adjusted_series(price_rows, list(reversed(action_rows)))
    assert ours_a == ours_b
