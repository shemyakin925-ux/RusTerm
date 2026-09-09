"""Тесты SEC EDGAR-провайдера (TASK-8 U5).

Весь набор офлайн: транспорт подставной, ответы — настоящие, снятые с
живых запросов 2026-09-08 и обрезанные до малого размера
(tests/data/edgar/; это записанные ответы, не синтетика). Живой тест —
отдельно, помечен integration и без RUSTERM_SEC_UA пропускается чисто.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.providers import get_provider
from rusterm.providers.base import ProviderError
from rusterm.providers.budget import (
    Budget,
    ConfigError,
    NetworkGate,
    RateLimiter,
    RequestGate,
)
from rusterm.providers.edgar import EdgarProvider

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"

# Подставной контакт только для тестов; настоящие запросы без него не идут.
FAKE_UA = "Synthetic Test synthetic.invalid"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now += s


def _gate():
    fc = FakeClock()
    return RequestGate(
        budget=Budget(max_requests=100),
        limiter=RateLimiter(per_second=5, clock=fc, sleeper=fc.sleep),
        gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))


def _saved_transport(requests_log: list):
    """Транспорт на записанных ответах; считает запросы по URL."""
    payloads = {
        "https://www.sec.gov/files/company_tickers.json":
            DATA / "company_tickers.json",
        "https://data.sec.gov/submissions/CIK0000320193.json":
            DATA / "submissions_aapl.json",
    }

    def transport(url, headers):
        assert headers.get("User-Agent") == FAKE_UA
        path = payloads.get(url)
        if path is None:
            return 404, b'{"error": "not found"}', {}
        requests_log.append(url)
        return 200, path.read_bytes(), {}

    return transport


def test_registry_refuses_network_provider_without_gate():
    outcome = get_provider("edgar")
    assert isinstance(outcome, ConfigError)
    assert outcome.reason == "network_provider_requires_gate:edgar"
    # с гейтом — полноценный провайдер
    provider = get_provider("edgar", gate=_gate())
    assert isinstance(provider, EdgarProvider)
    assert provider.needs_network is True


def test_resolve_n_tickers_costs_exactly_one_request():
    log: list = []
    provider = EdgarProvider(gate=_gate(),
                             transport=_saved_transport(log))
    for ticker in ("AAPL", "NVDA", "MSFT", "GOOGL"):
        outcome = provider.resolve(ticker, "US", "2026-09-08")
        assert isinstance(outcome, dict), outcome
        assert outcome["cik"] > 0
    assert len(log) == 1, "карта тикеров должна кэшироваться: 1 запрос"

    missing = provider.resolve("NOSUCH", "US", "2026-09-08")
    assert isinstance(missing, ProviderError)
    assert missing.reason == "not_found:NOSUCH"
    assert len(log) == 1  # не найденный тикер не ходит в сеть повторно


def test_poll_index_returns_only_filings_after_cursor():
    log: list = []
    provider = EdgarProvider(gate=_gate(), cik=320193,
                             transport=_saved_transport(log))
    poll = provider.poll_index("2025-06-30")
    assert not isinstance(poll, ProviderError)
    assert len(log) == 1  # один запрос на источник-эмитента
    assert poll.records, "после 2025-06-30 в записанных данных есть ф��линги"
    for record in poll.records:
        assert record.published_at > "2025-06-30"
        assert record.url.startswith(
            "https://www.sec.gov/Archives/edgar/data/320193/")
    assert poll.cursor == max(r.cursor for r in poll.records)

    # тот же курсор повторно — новых записей нет, нового запроса тоже
    again = provider.poll_index(poll.cursor)
    assert again.records == ()
    assert len(log) == 1


def test_list_documents_filters_without_bodies():
    log: list = []
    provider = EdgarProvider(gate=_gate(), cik=320193,
                             transport=_saved_transport(log))
    listing = provider.list_documents("ins-aapl", doc_type="10-K")
    assert not isinstance(listing, ProviderError)
    assert all(d.doc_type == "10-K" for d in listing.documents)
    assert all(d.url.startswith("https://") for d in listing.documents)
    assert len(log) == 1  # тела не скачивались


def test_fetch_document_is_idempotent_and_304_is_not_new_data():
    import hashlib
    log: list = []
    body = b"<html>synthetic probe document for offline test</html>"

    def transport(url, headers):
        log.append(url)
        return 200, body, {}

    provider = EdgarProvider(gate=_gate(), cik=320193, transport=transport)
    doc = provider.fetch_document("https://example.sec/doc.htm")
    assert doc.sha256 == hashlib.sha256(body).hexdigest()
    again = provider.fetch_document("https://example.sec/doc.htm")
    assert again.sha256 == doc.sha256

    def transport_304(url, headers):
        return 304, b"", {}

    etagged = EdgarProvider(gate=_gate(), cik=320193,
                            transport=transport_304)
    from rusterm.providers.edgar import NotModified
    assert isinstance(etagged.fetch_document("https://x/1.htm"),
                      NotModified)


def test_gate_still_enforced_inside_provider():
    """Без RUSTERM_SEC_UA провайдер возвращает ConfigError и не делает
    ни одного запроса — гейт работает и внутри провайдера."""
    calls: list = []

    def transport(url, headers):
        calls.append(url)
        return 200, b"{}", {}

    provider = EdgarProvider(
        gate=RequestGate(budget=Budget(max_requests=10),
                         limiter=RateLimiter(per_second=5),
                         gate=NetworkGate(environ={})),
        cik=320193, transport=transport)
    outcome = provider.resolve("AAPL", "US", "2026-09-08")
    assert isinstance(outcome, ConfigError)
    assert outcome.reason == "sec_ua_unset"
    assert calls == []


@pytest.mark.integration
def test_live_edgar_probe_skips_without_contact():
    """Живой запрос к SEC: ровно один, через RequestGate, с контактом
    из окружения. Без RUSTERM_SEC_UA — чистый пропуск (N2/N7)."""
    if not _live_ua():
        pytest.skip("RUSTERM_SEC_UA unset — network path not exercised")
    provider = EdgarProvider(gate=_live_gate())
    outcome = provider.resolve("AAPL", "US", "2026-09-08")
    assert isinstance(outcome, dict) and outcome["cik"] == 320193
    assert provider.gate.calls_made == 1


def _live_ua():
    import os
    from rusterm import env as env_module
    env_module.load_env()
    return os.environ.get("RUSTERM_SEC_UA")


def _live_gate():
    return RequestGate()  # NetworkGate читает настоящий os.environ


def test_b17_duplicate_ticker_last_feed_row_wins():
    """B17: тикер с двумя строками в карте (смена класса, релейстинг):
    зафиксировано «побеждает последняя строка фида», ошибки
    неоднозначности нет. Рукотворная двухстрочная карта; нижний регистр
    в фиде нормализуется, как в живом company_tickers.json."""
    feed = {
        "0": {"cik_str": 111, "ticker": "DUP", "title": "First Corp"},
        "1": {"cik_str": 222, "ticker": "dup", "title": "Second Corp"},
    }

    def transport(url, headers):
        assert "company_tickers" in url
        return 200, json.dumps(feed).encode(), {}

    provider = EdgarProvider(gate=_gate(), transport=transport)
    outcome = provider.resolve("DUP", "US", "2026-09-08")
    assert outcome == {"ticker": "DUP", "cik": 222,
                       "title": "Second Corp"}, outcome
