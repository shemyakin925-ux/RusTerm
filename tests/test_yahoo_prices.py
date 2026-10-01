"""ADR-0029: котировки, сплиты и дивиденды из Yahoo chart без ключа.

Решение пользователя 01.10.2026: ключ Twelve Data отвечает «неверный»,
корпоративные действия там только на платном тарифе. Офлайн: записанный
обрезанный ответ AAPL (300 дней, все события с 2020 г.), транспорт —
заглушка, считающая вызовы.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from rusterm import cli
from rusterm.providers import get_provider
from rusterm.providers.budget import NetworkGate, RequestGate
from rusterm.providers.yahoo import YahooProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, Listing, RepoRegistry

def _gate():
    return RequestGate(gate=NetworkGate({"RUSTERM_SEC_UA": "Test test@example.com"}))


FIXTURE = Path(__file__).parent / "data" / "yahoo" / "chart_AAPL_trimmed.json"
PAYLOAD = json.loads(FIXTURE.read_text(encoding="utf-8"))
AS_OF = "2026-09-30"


def test_parse_series_gives_daily_closes_in_usd():
    rows = YahooProvider.parse_series(PAYLOAD)
    assert len(rows) == 300
    assert rows == sorted(rows, key=lambda r: r["date"])
    assert all(r["currency"] == "USD" and r["close"] > 0 for r in rows)
    assert all(len(r["date"]) == 10 for r in rows)
    assert any("adjusted" in r for r in rows)


def test_parse_events_split_and_dividends():
    splits, skipped = YahooProvider.parse_splits(PAYLOAD)
    assert skipped == 0
    assert [(s["ex_date"], s["factor"]) for s in splits] == [
        ("2020-08-31", 4.0)]
    divs, currency, skipped = YahooProvider.parse_dividends(PAYLOAD)
    assert currency == "USD" and skipped == 0
    assert len(divs) >= 20
    # сумма в сегодняшней базе акций: февраль 2020 — 0.77 / 4
    assert divs[0]["amount"] == pytest.approx(0.1925)


def test_registry_gives_yahoo_as_an_open_channel():
    provider = get_provider("yahoo", gate=RequestGate())
    assert isinstance(provider, YahooProvider)


def test_bad_payload_is_a_value_not_an_exception():
    calls = []

    def transport(url, headers):
        calls.append(url)
        return 200, b"<html>not json</html>", {}

    p = YahooProvider(gate=_gate(), transport=transport)
    out = p.time_series("AAPL", end=AS_OF)
    assert getattr(out, "reason", "") == "yahoo_bad_response"


@pytest.fixture()
def repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    r = RepoRegistry(conn, paths)
    r.instrument.upsert_issuer(Issuer("i-AAPL", "Apple", "US", None, None,
                                      "us_gaap", "USD"))
    r.instrument.upsert_instrument(Instrument("US-AAPL", "i-AAPL", None,
                                              "common", "active", None))
    r.instrument.upsert_listing(Listing("l-AAPL", "US-AAPL", "XNAS", "USD",
                                        1, None, None))
    r.instrument.add_ticker_history("l-AAPL", "AAPL", "2000-01-01", None,
                                    None, None)
    return r


def _stub():
    calls = []

    def transport(url, headers):
        calls.append(url)
        assert "example.com" not in headers["User-Agent"]
        return 200, json.dumps(PAYLOAD).encode("utf-8"), {}

    return YahooProvider(gate=_gate(), transport=transport), calls


def test_ingest_writes_prices_and_repeat_costs_nothing(repos, capsys):
    provider, calls = _stub()
    assert cli._ingest_twelvedata_prices(repos, "US-AAPL", AS_OF,
                                         provider=provider) == 0
    assert len(calls) == 1
    assert cli._ingest_twelvedata_prices(repos, "US-AAPL", AS_OF,
                                         provider=provider) == 0
    assert len(calls) == 1, "повтор того же дня обязан взять кеш"
    out = capsys.readouterr().out
    assert "строк получено: 300" in out


def test_actions_use_one_request_for_splits_and_dividends(repos, capsys):
    provider, calls = _stub()
    assert cli._ingest_twelvedata_actions(repos, "US-AAPL", AS_OF,
                                          provider=provider) == 0
    assert len(calls) == 1
    out = capsys.readouterr().out
    assert "сплитов 1;" in out


def test_price_source_reads_the_setting(monkeypatch):
    monkeypatch.delenv("RUSTERM_PRICE_SOURCE", raising=False)
    assert cli.price_source() == "twelvedata"
    monkeypatch.setenv("RUSTERM_PRICE_SOURCE", "Yahoo")
    assert cli.price_source() == "yahoo"
    monkeypatch.setenv("RUSTERM_PRICE_SOURCE", "nonsense")
    assert cli.price_source() == "twelvedata"
