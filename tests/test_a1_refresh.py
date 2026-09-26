"""ТЗ-90 A1: сбор цен и корпоративных событий обновляемый.

Болезнь была в ключе кеша: payload /time_series, /splits и /dividends
лежали в raw_object под недатированным URL, поэтому повторный сбор
находил объект первого запуска и тратил ноль запросов навсегда — цена
первого дня оставалась последней ценой. Канонический URL теперь
датированный (end_date=ас_оф): тот же as_of — ноль запросов (прежний
пин B2/K2 жив), следующий as_of — новый запрос и новые строки.

Свежесть проверяется на счётчике транспорта, не на словах: запросы
считает тот же фейк, что отдаёт payload по дате из URL (прошлый пин,
что запрос — ровно один, не чинит это; он его и не отменяет).
"""
from __future__ import annotations

import json
import sqlite3
from urllib.parse import parse_qs, urlparse

from rusterm.cli import _ingest_twelvedata_actions, _ingest_twelvedata_prices
from rusterm.providers import twelvedata as td
from rusterm.providers.budget import NetworkGate, RequestGate
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, Listing, RepoRegistry

FAKE_UA = "Synthetic Test t.invalid"

D1 = "2026-09-11"
D2 = "2026-09-14"
D0 = "2026-09-10"
DAYS = [D0, D1, D2]


def _provider(transport):
    return td.TwelveDataProvider(
        gate=RequestGate(gate=NetworkGate(environ={"RUSTERM_SEC_UA":
                                                   FAKE_UA})),
        api_key="TESTONLY-key", transport=transport)


def _env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
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


def _dates(conn):
    return [r[0] for r in conn.execute(
        "SELECT date FROM price WHERE instrument_id='US-X' ORDER BY date")]


def _series_payload(dates):
    return {"meta": {"currency": "USD"},
            "values": [{"datetime": d, "close": "10.5"} for d in dates]}


def _end_date(url: str) -> str:
    return parse_qs(urlparse(url).query)["end_date"][0]


def test_price_urls_carry_the_date_and_never_the_key():
    """A1 в чистом виде: ключ кеша различает даты, а `range=full` из
    запроса уходит (его замер 23.09.2026 заменил датированным
    диапазоном — tools/tz90_ca_range_check.py)."""
    for kind in ("splits", "dividends"):
        u1 = td.TwelveDataProvider.cache_url_ca(kind, "AAPL", D1)
        u2 = td.TwelveDataProvider.cache_url_ca(kind, "AAPL", D2)
        assert u1 != u2, f"{kind}: ключ кеша не различает даты"
        assert f"{kind}?" in u1 and "TESTONLY" not in u1
        assert "start_date=1900-01-01" in u1 and f"end_date={D1}" in u1
        assert "range=full" not in u1
    p1 = td.TwelveDataProvider.cache_url("AAPL", None, D1)
    assert p1 != td.TwelveDataProvider.cache_url("AAPL", None, D2)
    assert f"end_date={D1}" in p1 and "TESTONLY" not in p1


def test_same_day_prices_are_free_next_day_prices_ask(tmp_path):
    """Тот же as_of — ноль запросов (прежний пин K2/B2), следующий
    as_of — новый запрос и строка нового дня; дублей дат нет (I7)."""
    conn, repos = _env(tmp_path)
    calls: list[str] = []

    def transport(url, headers):
        calls.append(url)
        return (200, json.dumps(
            _series_payload([d for d in DAYS if d <= _end_date(url)])
        ).encode("utf-8"), {})

    provider = _provider(transport)
    assert _ingest_twelvedata_prices(repos, "US-X", D1,
                                     provider=provider) == 0
    assert len(calls) == 1, calls
    assert _dates(conn) == [D0, D1]

    assert _ingest_twelvedata_prices(repos, "US-X", D1,
                                     provider=provider) == 0
    assert len(calls) == 1, "повтор того же as_of сходил в сеть"
    assert _dates(conn) == [D0, D1]

    assert _ingest_twelvedata_prices(repos, "US-X", D2,
                                     provider=provider) == 0
    assert len(calls) == 2, "следующий as_of не попросил свежий payload"
    assert _dates(conn) == [D0, D1, D2], "новый день не дописан"

    # payload второго дня лёг отдельным объектом со своим URL
    assert repos.raw.find_by_provider_url(
        "twelvedata", provider.cache_url("AAPL", None, D2))
    assert repos.raw.find_by_provider_url(
        "twelvedata", provider.cache_url("AAPL", None, D1))
    conn.close()


def _dividends_payload(through: str):
    entries = [{"ex_date": "2026-08-10", "amount": "0.27"}]
    if through >= D2:
        # дивиденд, которого в payload первого дня не было
        entries.append({"ex_date": D2, "amount": "0.28"})
    return {"meta": {"currency": "USD"}, "dividends": entries}


def _splits_payload():
    return {"splits": [{"date": "2020-08-31", "from_factor": "4",
                        "to_factor": "1", "ratio": "4.0"}]}


def test_a_dividend_that_appears_next_day_lands(tmp_path):
    """Корпоративные действия тем же каналом: на D1 их два запроса,
    на D2 — ещё два, и дивиденд D2 появляется в corporate_action."""
    conn, repos = _env(tmp_path)
    calls: list[str] = []

    def transport(url, headers):
        calls.append(url)
        kind = "splits" if "/splits?" in url else "dividends"
        payload = (_splits_payload() if kind == "splits"
                   else _dividends_payload(_end_date(url)))
        return 200, json.dumps(payload).encode("utf-8"), {}

    provider = _provider(transport)
    assert _ingest_twelvedata_actions(repos, "US-X", D1,
                                     provider=provider) == 0
    assert len(calls) == 2, calls
    assert [e["ex_date"] for e in repos.corp_action.all("US-X")] == \
        ["2020-08-31", "2026-08-10"]

    assert _ingest_twelvedata_actions(repos, "US-X", D1,
                                      provider=provider) == 0
    assert len(calls) == 2, "повтор того же as_of сходил в сеть"

    assert _ingest_twelvedata_actions(repos, "US-X", D2,
                                      provider=provider) == 0
    assert len(calls) == 4, "следующий as_of не попросил свежие payload'ы"
    fresh = repos.corp_action.all("US-X")
    assert [e["ex_date"] for e in fresh] == \
        ["2020-08-31", "2026-08-10", D2], "новый дивиденд не дошёл"
    new = next(e for e in fresh if e["ex_date"] == D2)
    assert new["kind"] == "dividend" and new["amount"] == 0.28
    assert new["currency"] == "USD"
    conn.close()
