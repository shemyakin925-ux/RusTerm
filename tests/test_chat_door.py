"""Страж связности двери разговора (координатор, 17.09.2026).

Дефект, ради которого файл заведён: экран разговора строил клиента
`make_intent_client`, у которого есть только `complete()`, а
`ChatSession.ask` зовёт `chat(prompt, history)` — первый же вопрос
ронял программу с `AttributeError`, и с ключом, и без. Тесты этого не
видели, потому что подменяли дверь фальшивкой, у которой `chat` есть,
и сверяли **текст исходника** на подстроку «make_intent_client».

Правило: дверь проверяется тем, что зовёт её потребитель, а не тем,
как она называется.
"""
from __future__ import annotations

import json

import pytest

from rusterm.core.chat import ChatSession
from rusterm.core.intent import Clarification, classify
from rusterm.core.llm import make_chat_client, make_intent_client

_KEYED = {"RUSTERM_LLM_API_KEY": "fake-key",
          "RUSTERM_LLM_MODEL": "fake/model",
          "RUSTERM_SEC_UA": "Тест Тестов test@example.com"}


class _StubGate:
    """Гейт-заглушка: сеть не трогается, ответ вендора задан здесь.

    Инъекция именно гейтом, а не подменой приватных полей: дверь
    принимает gate параметром ровно для этого.
    """

    def __init__(self, payload: str = '{"intent": null}'):
        body = json.dumps(
            {"choices": [{"message": {"content": payload}}]}).encode()
        self._reply = (200, body, {})
        self.calls = 0

    def request(self, send, limit=None):
        self.calls += 1
        return self._reply


@pytest.mark.parametrize("environ, case", [({}, "без ключа"),
                                           (_KEYED, "с ключом")])
def test_chat_door_returns_a_client_the_session_can_call(environ, case):
    """То, что отдаёт дверь, обязано уметь ровно то, что зовёт ask."""
    client = make_chat_client(environ=environ, gate=_StubGate("ответ"))
    assert hasattr(client, "chat"), (
        f"{case}: дверь разговора отдала клиента без chat() — "
        f"{type(client).__name__}; именно так падал экран")
    reply = client.chat("вопрос", [])
    assert isinstance(reply, dict) and "tool_calls" in reply, (
        f"{case}: ответ клиента не по протоколу ChatSession: {reply!r}")


def test_chat_without_key_refuses_by_name_instead_of_raising(tmp_path):
    """Ключа нет — разговор говорит причину, а не падает и не молчит."""
    client = make_chat_client(environ={})
    session = ChatSession(_NoRepos(), client)
    result = session.ask("какая выручка?")
    assert result["rejected"] is True
    assert result["reason"] == "llm_error:llm_key_unset", result


def test_intent_door_builds_a_client_with_a_gate():
    """Без гейта complete() у API-клиента отказывает всегда: `ops` с
    заданным ключом не работал вовсе."""
    assert getattr(make_intent_client(_KEYED), "gate", None) is not None, (
        "дверь намерений собрала сетевого клиента без гейта — "
        "complete() вернёт llm_provider_requires_gate на любой запрос")
    client = make_intent_client(_KEYED, gate=_StubGate("привет"))
    outcome = client.complete("что угодно")
    assert getattr(outcome, "reason", None) != "llm_provider_requires_gate", (
        "дверь по-прежнему отдаёт клиента, который до модели не доходит")
    assert outcome == "привет"


def test_classify_names_the_client_error_and_does_not_retry():
    """Ошибка-значение не маскируется под «ответ модели не JSON» и не
    стоит второго вызова модели."""

    class _Failing:
        def __init__(self):
            self.calls = 0

        def complete(self, prompt):
            self.calls += 1
            return _Error("llm_provider_requires_gate")

    client = _Failing()
    decision = classify(client, "добавь AAPL")
    assert isinstance(decision, Clarification)
    assert decision.reason == "llm_error:llm_provider_requires_gate"
    assert client.calls == 1, (
        "на ошибке клиента сделан повтор — потраченный вызов модели "
        f"(сделано {client.calls})")


class _Error:
    """Ошибка-значение проекта: несёт reason и строкой не является."""

    def __init__(self, reason: str):
        self.reason = reason


class _NoRepos:
    """Разговор до инструментов не доходит: клиент отказал сразу."""
