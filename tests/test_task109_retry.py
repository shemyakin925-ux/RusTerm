"""ТЗ-109 R2: ретраи транспорта с бэкоффом.

Измеренный повод: обрыв транспорта (`source_unreachable:transport:URLError`
на живом прогоне 03.10) ронял стадию с первой же попытки. Теперь обрыв
(URLError, тайм-аут, OSError), 5xx и 429 повторяются до трёх раз с
паузой 1 с, 4 с, 15 с; каждая попытка проходит через `RequestGate` и
считается бюджетом. Остальные 4xx (403, 404) — ответ вендора, а не
обрыв: одна попытка, ноль снов (N4).

Офлайн: транспорт подменяется на уровне провайдера, гейт настоящий —
счёт запросов честный. Сон подставной: провайдер получает sleeper-
коллектор, который записывает паузу вместо сна.
"""
from __future__ import annotations

import io
import urllib.error

import pytest

from rusterm.providers.budget import (NetworkGate, RequestGate,
                                      RETRY_DELAYS, TRANSIENT_STATUSES,
                                      retry_transport)
from rusterm.providers.edgar import EdgarProvider
from rusterm.providers.base import ProviderError
from rusterm.providers.twelvedata import TwelveDataProvider
from rusterm.providers.yahoo import YahooProvider

FAKE_UA = "Rusterm Test r.invalid"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def _gate():
    return RequestGate(gate=NetworkGate({"RUSTERM_SEC_UA": FAKE_UA}))


def _tickers_body() -> bytes:
    from pathlib import Path
    return (Path(__file__).resolve().parents[1]
            / "tests/data/edgar/company_tickers.json").read_bytes()


def _raising_twice_then_ok(body: bytes, code: int | None = None):
    """Транспорт: два транзиентных отказа (URLError либо HTTPError с
    кодом), третий вызов отдаёт записанное тело."""
    calls = {"n": 0}

    def transport(url, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            if code is None:
                raise urllib.error.URLError("connection reset")
            raise urllib.error.HTTPError(url, code, "later", {},
                                         io.BytesIO(b""))
        if calls["n"] == 2:
            if code is None:
                raise TimeoutError("read timed out")
            raise urllib.error.HTTPError(url, code, "later", {},
                                         io.BytesIO(b""))
        return 200, body, {}

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def _always(code: int):
    """Транспорт, который всегда отвечает кодом (не поднимая) — как
    Yahoo/Twelve Data возвращают статус вендора."""
    def transport(url, headers):
        return code, b"{}", {}
    return transport


# ── SEC EDGAR: транспорт поднимает, как настоящий urllib ────────────────

def test_urllib_errors_are_retried_twice_then_succeed():
    gate = _gate()
    sleeps: list[float] = []
    provider = EdgarProvider(
        gate=gate, cik=320193,
        transport=_raising_twice_then_ok(_tickers_body()),
        sleeper=sleeps.append)
    outcome = provider.resolve("AAPL", "US", "2026-10-03")

    assert isinstance(outcome, dict), outcome
    assert outcome["cik"] == 320193 and "Apple" in outcome["title"]
    assert gate.calls_made == 3, "три попытки — три списанных запроса"
    assert sleeps == [1.0, 4.0], sleeps


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_http_codes_are_retried(code):
    """429 и 5xx от SEC поднимаются транспортом, как urllib: повтор до
    трёх раз, после исчерпания — значение с той же причиной."""
    gate = _gate()
    sleeps: list[float] = []
    provider = EdgarProvider(
        gate=gate, cik=320193,
        transport=_raising_twice_then_ok(_tickers_body(), code=code),
        sleeper=sleeps.append)
    if True:  # транспорт падает только дважды — третий ответ 200
        outcome = provider.resolve("AAPL", "US", "2026-10-03")
        assert not isinstance(outcome, ProviderError), outcome
        assert gate.calls_made == 3
        assert sleeps == [1.0, 4.0]


def test_always_429_is_retried_to_exhaustion():
    gate = _gate()
    sleeps: list[float] = []

    def transport(url, headers):
        raise urllib.error.HTTPError(url, 429, "later", {},
                                     io.BytesIO(b""))

    provider = EdgarProvider(gate=gate, cik=320193, transport=transport,
                             sleeper=sleeps.append)
    outcome = provider.resolve("AAPL", "US", "2026-10-03")

    assert isinstance(outcome, ProviderError), outcome
    assert outcome.reason == "source_unreachable:http_429"
    assert gate.calls_made == 4, "начальная + три повтора"
    assert sleeps == [1.0, 4.0, 15.0], sleeps


@pytest.mark.parametrize("code", [403, 404])
def test_other_4xx_is_never_retried(code):
    """403/404 — ответ, не обрыв: один запрос, ни одного сна."""
    gate = _gate()
    sleeps: list[float] = []

    def transport(url, headers):
        raise urllib.error.HTTPError(url, code, "refused", {},
                                     io.BytesIO(b""))

    provider = EdgarProvider(gate=gate, cik=320193, transport=transport,
                             sleeper=sleeps.append)
    outcome = provider.resolve("AAPL", "US", "2026-10-03")

    assert isinstance(outcome, ProviderError), outcome
    assert outcome.reason == f"source_unreachable:http_{code}"
    assert gate.calls_made == 1, code
    assert sleeps == [], "403/404 не повторяются"


# ── Yahoo / Twelve Data: транспорт ВОЗВРАЩАЕТ статус, не поднимая ───────

_CHART = {"chart": {"result": [{"meta": {"currency": "USD"}}],
                    "error": None}}


def test_yahoo_transient_statuses_are_retried_then_succeed():
    import json
    gate = _gate()
    sleeps: list[float] = []
    calls = {"n": 0}

    def transport(url, headers):
        calls["n"] += 1
        if calls["n"] <= 2:
            return 429, b"too many", {}
        return 200, json.dumps(_CHART).encode(), {}

    provider = YahooProvider(gate=gate, transport=transport,
                             sleeper=sleeps.append)
    outcome = provider.time_series("AAPL")

    assert isinstance(outcome, dict), outcome
    assert gate.calls_made == 3
    assert sleeps == [1.0, 4.0], sleeps


def test_yahoo_404_is_one_request():
    gate = _gate()
    sleeps: list[float] = []
    provider = YahooProvider(gate=gate, transport=_always(404),
                             sleeper=sleeps.append)
    outcome = provider.time_series("AAPL")

    assert isinstance(outcome, ProviderError), outcome
    assert outcome.reason == "unknown_issuer"
    assert gate.calls_made == 1
    assert sleeps == []


def test_yahoo_always_500_returns_named_value_after_exhaustion():
    gate = _gate()
    sleeps: list[float] = []
    provider = YahooProvider(gate=gate, transport=_always(500),
                             sleeper=sleeps.append)
    outcome = provider.time_series("AAPL")

    assert isinstance(outcome, ProviderError), outcome
    assert outcome.reason == "source_unreachable:http_500"
    assert gate.calls_made == 4
    assert sleeps == [1.0, 4.0, 15.0]


def test_twelvedata_transient_statuses_are_retried_then_succeed():
    gate = _gate()
    sleeps: list[float] = []
    calls = {"n": 0}

    def transport(url, headers):
        calls["n"] += 1
        if calls["n"] <= 2:
            return 503, b"unavailable", {}
        return 200, b"{}", {}

    provider = TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                  transport=transport,
                                  sleeper=sleeps.append)
    outcome = provider.time_series("AAPL")

    assert isinstance(outcome, dict), outcome
    assert gate.calls_made == 3
    assert sleeps == [1.0, 4.0]


# ── сам помощник и константы ────────────────────────────────────────────

def test_retry_constants_are_the_documented_ones():
    assert RETRY_DELAYS == (1.0, 4.0, 15.0)
    assert TRANSIENT_STATUSES == {429, 500, 502, 503, 504}


def test_retry_transport_reraises_the_last_transient_exception():
    attempts = {"n": 0}

    def op():
        attempts["n"] += 1
        raise urllib.error.URLError("down")

    with pytest.raises(urllib.error.URLError):
        retry_transport(op, sleeper=lambda _s: None)
    assert attempts["n"] == 4, "начальная + три повтора"


def test_retry_transport_passes_budget_refusal_through_unretried():
    """Исчерпание бюджета — не сеть: значение возвращается как есть,
    повторов нет (PROTOCOL §6: стоп, а не головоломка)."""
    from rusterm.providers.budget import BudgetExceeded
    refused = BudgetExceeded(used=5000, max_requests=5000)
    attempts = {"n": 0}

    def op():
        attempts["n"] += 1
        return refused

    outcome = retry_transport(op, sleeper=lambda _s: None)
    assert outcome is refused
    assert attempts["n"] == 1
