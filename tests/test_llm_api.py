"""TASK-19 F6: OpenAI-совместимый клиент по API и переключатель по
ключу (ADR-0011 ②). Ни один тест не требует настоящего ключа: транспорт
инъектируется и возвращает записанные тела; фиктивный ключ — метка для
проверки «ключ нигде не светится», не секрет и не контакт.
"""
from __future__ import annotations

import json
import logging

import pytest

from rusterm.core.intent import RuleClient
from rusterm.core.llm import make_intent_client
from rusterm.providers.budget import (
    BudgetExceeded, ConfigError, HostLimit, NetworkGate, RequestGate)
from rusterm.providers.llm_api import (
    BASE_URL_ENV, KEY_ENV, MODEL_ENV, LlmApiClient, build)

DUMMY_KEY = "DUMMY-KEY-F6-not-a-secret"
BASE = "https://llm.invalid/v1"
MODEL = "fake/fake-1"
UA_ENV = {"RUSTERM_SEC_UA": "Synthetic Test f6.invalid"}


def _gate(nightly_max: int = 5000) -> RequestGate:
    return RequestGate(gate=NetworkGate(environ=dict(UA_ENV)))


def _client(transport, nightly_max: int = 5000) -> LlmApiClient:
    return LlmApiClient(
        base_url=BASE, model=MODEL, api_key=DUMMY_KEY,
        limit=HostLimit(host="openrouter.ai", per_second=1000.0,
                        nightly_max=nightly_max),
        gate=_gate(nightly_max), transport=transport)


def _ok_transport(prompt_text: str = "{\"intent\": null}"):
    def transport(url, headers, payload):
        body = json.dumps(
            {"choices": [{"message": {"content": prompt_text}}]}
        ).encode()
        return 200, body, {}
    return transport


def _env_off() -> dict:
    return {KEY_ENV: "", MODEL_ENV: "", BASE_URL_ENV: ""}


def test_from_env_without_key_is_config_error_value():
    result = LlmApiClient.from_env(environ=_env_off())
    assert isinstance(result, ConfigError)
    assert result.reason == "llm_key_unset"


def test_from_env_key_without_model_is_config_error_value():
    result = LlmApiClient.from_env(
        environ={KEY_ENV: DUMMY_KEY, MODEL_ENV: "", BASE_URL_ENV: ""})
    assert isinstance(result, ConfigError)
    assert result.reason == "llm_model_unset"


def test_selector_uses_rule_client_without_key():
    client = make_intent_client(_env_off())
    assert isinstance(client, RuleClient)


def test_selector_uses_api_client_with_key():
    client = make_intent_client({KEY_ENV: DUMMY_KEY, MODEL_ENV: MODEL,
                                 BASE_URL_ENV: BASE})
    assert isinstance(client, LlmApiClient)


def test_complete_returns_recorded_body_text():
    client = _client(_ok_transport("{\"intent\": null}"))
    assert client.complete("Запрос: проверка") == "{\"intent\": null}"


def test_http_500_is_value_without_body_echo():
    def transport(url, headers, payload):
        return 500, b"internal details", {}
    result = _client(transport).complete("любой")
    assert isinstance(result, ConfigError)
    assert result.reason == "llm_http_500"
    assert "details" not in result.reason


def test_malformed_body_is_value():
    def transport(url, headers, payload):
        return 200, b"not json at all", {}
    assert isinstance(_client(transport).complete("x"), ConfigError)


def test_complete_without_gate_is_config_error():
    client = LlmApiClient(
        base_url=BASE, model=MODEL, api_key=DUMMY_KEY,
        limit=HostLimit("openrouter.ai", 1.0, 5000),
        gate=None, transport=_ok_transport())
    result = client.complete("x")
    assert isinstance(result, ConfigError)
    assert result.reason == "llm_provider_requires_gate"


def test_llm_budget_is_per_host_not_sec_budget():
    """F5+F6: исчерпание хоста openrouter не трогает легаси-пул SEC."""
    client = _client(_ok_transport(), nightly_max=1)
    assert client.complete("раз") == "{\"intent\": null}"
    assert isinstance(client.complete("два"), BudgetExceeded)


def test_key_never_appears_in_logs_or_error_values(caplog):
    """F6 Done-when: фиктивный ключ не светится ни в одной строке лога
    ни при успехе, ни при отказе."""
    with caplog.at_level(logging.DEBUG, logger="rusterm"):
        good = _client(_ok_transport()).complete("успех")
        bad = _client(lambda u, h, p: (503, b"x", {})).complete("отказ")
        no_gate = LlmApiClient(
            base_url=BASE, model=MODEL, api_key=DUMMY_KEY,
            limit=HostLimit("openrouter.ai", 1.0, 5000),
            gate=None).complete("без гейта")
    assert good and isinstance(bad, ConfigError) \
        and isinstance(no_gate, ConfigError)
    assert DUMMY_KEY not in caplog.text
    assert DUMMY_KEY not in bad.reason and DUMMY_KEY not in no_gate.reason


def test_registry_seat_builds_client_from_env(monkeypatch):
    """Место llm-api в реестре теперь отвечает клиентом, а не
    provider_not_implemented: модуль существует (TASK-19 F5+F6).
    Окружение инъецируется точечно, настоящий os.environ не мутируется."""
    from rusterm.providers import get_provider
    for name, value in (UA_ENV
                        | {KEY_ENV: DUMMY_KEY, MODEL_ENV: MODEL,
                           BASE_URL_ENV: BASE}).items():
        monkeypatch.setenv(name, value)
    result = get_provider("llm-api", gate=_gate())
    assert isinstance(result, LlmApiClient)
    assert result.model == MODEL and result.base_url == BASE


def test_build_without_key_is_config_error():
    result = build(_gate())
    assert isinstance(result, ConfigError)
    assert result.reason == "llm_key_unset"
