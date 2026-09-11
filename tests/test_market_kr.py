"""ТЗ-20 L1: провайдер Open DART (Корея).

Настоящий записанный ответ — tests/data/dart/engapi_list_unkeyed.json
(живой запрос 11.09.2026: 200, 60 байт): разбор статуса '100'
тестируется на настоящих байтах. Синтетические тела ответов для
парсера строятся в тесте инлайном JSON — это тестовые подставы, а не
«записанный payload»: золотого payload трёх эмитентов без ключа нет
(BLOCKED в отчёте полосы), и фальшивить его тесты не имеют права.

Сети без ключа нет (N2): каждый сетевой тест скипается, если ключ не
задан (N7).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rusterm.providers.base import ProviderError
from rusterm.providers.budget import (
    Budget, BudgetExceeded, ConfigError, HostLimit, NetworkGate,
    RateLimiter, RequestGate)
from rusterm.providers.disclosures import (
    DocumentList, FetchedDocument, IndexPoll)
from rusterm.providers.dart import KEY_ENV, DartProvider, build

_UA_ENV = {"RUSTERM_SEC_UA": "Synthetic Test l1.invalid"}
_UNKEYED = Path(__file__).resolve().parent / "data" / "dart" / \
    "engapi_list_unkeyed.json"


def _gate() -> RequestGate:
    return RequestGate(gate=NetworkGate(environ=dict(_UA_ENV)))


def _provider(transport) -> DartProvider:
    return DartProvider(gate=_gate(), api_key="SYNTHETIC-DART-KEY",
                        transport=transport)


def _json_transport(responses: dict[str, object]):
    """Подставной транспорт: путь -> тело (dict или bytes)."""
    def transport(url: str, headers: dict):
        for path, body in responses.items():
            if path in url:
                raw = body if isinstance(body, bytes) else json.dumps(
                    body).encode()
                return 200, raw, {}
        return 404, b"not found", {}
    return transport


# ── настоящий записанный ответ ─────────────────────────────────────────

def test_recorded_unkeyed_answer_maps_to_source_refusal():
    """Статус '100' из НАСТОЯЩИХ байтов (живой замер) — отказ источника
    значением, не исключение и не молчание."""
    body = _UNKEYED.read_bytes()
    assert json.loads(body)["status"] == "100"
    provider = _provider(lambda url, headers: (200, body, {}))
    answer = provider.poll_index("20260911")
    assert isinstance(answer, ProviderError)
    assert answer.reason == "source_unreachable:dart_100"


# ── ключ и допуск ──────────────────────────────────────────────────────

def test_build_without_key_is_config_error_value():
    result = build(_gate()) if False else DartProvider.from_env(
        _gate(), environ={KEY_ENV: ""})
    assert isinstance(result, ConfigError)
    assert result.reason == "dart_key_unset"


def test_get_provider_seat_builds_provider_when_key_set(monkeypatch):
    from rusterm.providers import get_provider
    for name, value in (_UA_ENV
                        | {KEY_ENV: "SYNTHETIC-DART-KEY"}).items():
        monkeypatch.setenv(name, value)
    result = get_provider("dart", gate=_gate())
    assert isinstance(result, DartProvider)


def test_without_gate_no_provider_u5_door_still_closed():
    from rusterm.providers import get_provider
    result = get_provider("dart", gate=None)
    assert isinstance(result, ConfigError)
    assert result.reason == "network_provider_requires_gate:dart"


# ── can_auto_ingest: три исхода ADR-0010 §3 ────────────────────────────

def test_can_auto_ingest_true_for_known_corp_code():
    provider = _provider(_json_transport({
        "company.json": {"status": "000", "corp_name": "삼성전자"},
    }))
    assert provider.can_auto_ingest("00126380") is True


def test_can_auto_ingest_unknown_corp_code_is_unknown_issuer():
    provider = _provider(_json_transport({
        "company.json": {"status": "013", "message": "데이터 존재하지 않습니다."},
    }))
    answer = provider.can_auto_ingest("99999999")
    assert isinstance(answer, ProviderError)
    assert answer.reason.split(":", 1)[0] == "unknown_issuer"


def test_can_auto_ingest_empty_identifier_is_unknown_issuer():
    answer = _provider(_json_transport({})).can_auto_ingest("")
    assert isinstance(answer, ProviderError)
    assert answer.reason == "unknown_issuer"


# ── poll_index и list_documents на синтетических телах ────────────────

def _list_body(rows: list[dict]) -> dict:
    return {"status": "000", "list": rows}


def test_poll_index_maps_rows_and_advances_cursor():
    provider = _provider(_json_transport({
        "list.json": _list_body([
            {"corp_code": "00126380", "corp_name": "삼성전자",
             "report_tp": "sb", "business_year": "2025",
             "rcept_no": "202603110001", "rcept_dt": "20260311"},
            {"corp_code": "00126380", "corp_name": "삼성전자",
             "report_tp": "sa", "business_year": "2025",
             "rcept_no": "202605150002", "rcept_dt": "20260515"},
        ]),
    }))
    poll = provider.poll_index("20260301")
    assert isinstance(poll, IndexPoll)
    assert len(poll.records) == 2
    assert poll.records[0].issuer_id == "00126380"
    assert poll.records[0].url == "document:202603110001"
    assert poll.cursor == "20260515"


def test_poll_index_empty_window_keeps_cursor():
    provider = _provider(_json_transport({
        "list.json": _list_body([]),
    }))
    poll = provider.poll_index("20260901")
    assert poll.records == () and poll.cursor == "20260901"


def test_list_documents_filters_by_issuer_and_type():
    provider = _provider(_json_transport({
        "list.json": _list_body([
            {"corp_code": "00126380", "report_tp": "sb",
             "business_year": "2025", "rcept_no": "1",
             "rcept_dt": "20260311"},
            {"corp_code": "00401731", "report_tp": "sb",
             "business_year": "2025", "rcept_no": "2",
             "rcept_dt": "20260312"},
        ]),
    }))
    docs = provider.list_documents("00126380", doc_type="sb")
    assert isinstance(docs, DocumentList)
    assert len(docs.documents) == 1
    assert docs.documents[0].url == "document:1"


def test_fetch_document_returns_bytes_with_sha256():
    payload = b"PK\x03\x04 synthetic dart zip bytes"

    def transport(url: str, headers: dict):
        assert "documentDownload.nav" in url
        assert "rcept_no=202603110001" in url
        return 200, payload, {}

    provider = _provider(transport)
    doc = provider.fetch_document("document:202603110001")
    assert isinstance(doc, FetchedDocument)
    assert doc.content == payload
    assert len(doc.sha256) == 64


def test_fetch_document_bad_url_is_value():
    answer = _provider(_json_transport({})).fetch_document("http://x")
    assert isinstance(answer, ProviderError)
    assert answer.reason.startswith("dart_bad_url")


# ── дверь и бюджет ─────────────────────────────────────────────────────

def test_every_call_goes_through_the_gate():
    """Счётчик гейта растёт ровно на число вызовов: мимо двери запрос
    не проходит (U5), темп — по хосту engopendart (F5)."""
    provider = _provider(_json_transport({
        "company.json": {"status": "000", "corp_name": "n"},
    }))
    gate = provider.gate
    provider.can_auto_ingest("00126380")
    provider.can_auto_ingest("00126380")
    assert gate.calls_made == 2


def test_gate_budget_exhaustion_is_value():
    provider = DartProvider(
        gate=RequestGate(
            budget=None,
            gate=NetworkGate(environ=dict(_UA_ENV))),
        api_key="K", transport=_json_transport({}))
    # потолок хоста из объявления провайдера: 5000 — не трогаем;
    # проверяем отказ гейта без UA отдельно
    provider.gate.gate = NetworkGate(environ={})
    answer = provider.can_auto_ingest("00126380")
    assert isinstance(answer, ConfigError)
    assert answer.reason == "sec_ua_unset"


def test_budget_exceeded_value_on_exhausted_host():
    """Исчерпанный ночной потолок хоста — BudgetExceeded значением
    (N3): провайдер не ждёт и не ретраит."""
    gate = RequestGate(gate=NetworkGate(environ=dict(_UA_ENV)))
    gate._host_pools["engopendart.fss.or.kr"] = (
        Budget(max_requests=0),
        RateLimiter(per_second=1000.0),
        HostLimit("engopendart.fss.or.kr", 2.0, 0))
    provider = DartProvider(
        gate=gate, api_key="K",
        transport=_json_transport({
            "company.json": {"status": "000", "corp_name": "n"}}))
    answer = provider.can_auto_ingest("00126380")
    assert isinstance(answer, BudgetExceeded)


# ── живые тесты: скип без ключа (N7) ───────────────────────────────────

_HAS_KEY = bool(os.environ.get(KEY_ENV, "").strip())


@pytest.mark.skipif(not _HAS_KEY, reason="RUSTERM_DART_KEY unset (N7)")
def test_live_company_json_answers():
    live = DartProvider.from_env(_gate())
    assert isinstance(live, DartProvider)

