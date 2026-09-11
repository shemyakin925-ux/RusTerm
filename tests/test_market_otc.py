"""ТЗ-20 L4: провайдер OTC Markets. Тесты офлайн на ЗАПИСАННЫХ телах
tests/data/otcmarkets/ (живая выкачка 11.09: financial-report OTCM
200/1281 B, active page 200/1538 B, /content -> HTTP 406 — блок).
Сети нет.
"""
from __future__ import annotations

import json
from pathlib import Path

from rusterm.providers.base import ProviderError
from rusterm.providers.budget import NetworkGate, RequestGate
from rusterm.providers.otcmarkets import OtcMarketsProvider

DATA = Path(__file__).resolve().parent / "data" / "otcmarkets"
UA_ENV = {"RUSTERM_SEC_UA": "Synthetic Test l4.invalid"}


def _gate() -> RequestGate:
    return RequestGate(gate=NetworkGate(environ=dict(UA_ENV)))


def _recorded(name: str) -> bytes:
    return (DATA / name).read_bytes()


def _provider(responses: dict[str, object]):
    def transport(url: str, headers: dict):
        for part, body in responses.items():
            if part in url:
                raw = body if isinstance(body, bytes) else json.dumps(
                    body).encode()
                return 200, raw, {}
        return 404, b"not found", {}
    return OtcMarketsProvider(gate=_gate(), transport=transport)


def test_financial_report_recorded_body_parses():
    """Золотая привязка: настоящие байты OTCM (выкачка 11.09)."""
    body = json.loads(_recorded("financial_report_OTCM.json"))
    assert str(body["symbol"]).upper() == "OTCM"
    provider = _provider({
        "financial-report": _recorded("financial_report_OTCM.json")})
    docs = provider.list_documents("OTCM")
    assert docs.documents
    assert docs.documents[0].url.startswith("otcdoc:")
    assert docs.documents[0].issuer_id == "OTCM"


def test_can_auto_ingest_true_when_metadata_reachable():
    provider = _provider({
        "financial-report": _recorded("financial_report_OTCM.json")})
    assert provider.can_auto_ingest("OTCM") is True


def test_unknown_symbol_is_unknown_issuer():
    provider = _provider({})
    answer = provider.can_auto_ingest("NOSUCH")
    assert isinstance(answer, ProviderError)
    assert answer.reason == "unknown_issuer"


def test_content_block_is_manual_import_required_never_retry():
    """Тело документа недостижимо: ответ manual_import_required с
    именем подачи; НОЛЬ запросов через гейт — ретрая нет (N4)."""
    provider = _provider({})
    answer = provider.fetch_document("otcdoc:144874")
    assert isinstance(answer, ProviderError)
    assert answer.reason == "manual_import_required:otcdoc:144874"
    assert provider.gate.calls_made == 0


def test_poll_index_page_maps_symbols_and_advances():
    provider = _provider({
        "market-data/active": _recorded("active_page1.json")})
    poll = provider.poll_index("")
    assert poll.cursor == "2"
    assert poll.records
    assert all(r.url.startswith("otcsym:") for r in poll.records)


def test_blocked_shape_406_is_source_unreachable_value():
    """Дрейф блокировки: /content в замере 09.09 отвечал 200 с HTML-
    заглушкой, 11.09 — 406. Обе формы — source_unreachable значением,
    стоп (N4)."""
    def transport(url: str, headers: dict):
        return 406, b"not acceptable", {}
    provider = OtcMarketsProvider(gate=_gate(), transport=transport)
    answer = provider.can_auto_ingest("OTCM")
    assert isinstance(answer, ProviderError)
    assert answer.reason == "source_unreachable:http_406"
