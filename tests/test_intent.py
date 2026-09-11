"""TASK-16 D1: намерение из ответа модели — значение, не исключение и
не действие. Ровно один повтор при не-JSON / намерении вне списка;
известное намерение без обязательного параметра — уточняющий вопрос.
Базы данных в модуле нет вообще — тест убеждается, что импорт
rusterm.core.intent не тянет store.
"""
from __future__ import annotations

import json
import sys

from rusterm.core.intent import (
    Clarification,
    INTENTS,
    REQUIRED_PARAMS,
    Intent,
    classify,
)

FAKE_UA = None  # сеть не нужна по определению модуля


class CountingClient:
    """Фальшивый клиент: ответы по очереди, счётчик вызовов."""

    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.calls = 0
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


def test_good_response_yields_intent_with_params():
    client = CountingClient(json.dumps(
        {"intent": "add_instruments",
         "params": {"tickers": ["AAPL", "MSFT"], "market": "US"}}))
    decision = classify(client, "добавь AAPL и MSFT")
    assert isinstance(decision, Intent)
    assert decision.name == "add_instruments"
    assert decision.params["tickers"] == ["AAPL", "MSFT"]
    assert client.calls == 1


def test_non_json_gets_exactly_one_retry_then_clarification():
    client = CountingClient(
        "Кажется, вы хотите что-то добавить!",
        json.dumps({"intent": "add_instruments",
                    "params": {"tickers": ["AAPL"]}}))
    decision = classify(client, "добавь AAPL")
    assert isinstance(decision, Intent)
    assert client.calls == 2, "повтор обязан быть ровно один"
    assert "JSON" in client.prompts[1] or "ОТВЕТ НЕ ПРИНЯТ" \
        in client.prompts[1]

    # повтор не спасает — уточняющий вопрос, не исключение
    stubborn = CountingClient("нет", "всё ещё нет")
    decision = classify(stubborn, "добавь AAPL")
    assert isinstance(decision, Clarification)
    assert stubborn.calls == 2


def test_unknown_intent_is_clarification_after_one_retry():
    client = CountingClient(
        json.dumps({"intent": "delete_everything", "params": {}}),
        json.dumps({"intent": "delete_everything", "params": {}}))
    decision = classify(client, "снеси всё")
    assert isinstance(decision, Clarification)
    assert "delete_everything" in decision.reason
    assert client.calls == 2


def test_known_intent_missing_required_param_is_clarification():
    client = CountingClient(json.dumps(
        {"intent": "ask_company", "params": {"question": "как дела?"}}))
    decision = classify(client, "как дела у AAPL?")
    assert isinstance(decision, Clarification)
    assert "instrument" in decision.reason
    assert client.calls == 1, "параметр форматом не лечится — без повтора"


def test_intents_and_params_are_the_frozen_table():
    assert INTENTS == (
        "add_instruments", "add_industry", "add_index", "add_peers",
        "update_summaries", "compare", "ask_company", "ask_industry")
    assert set(REQUIRED_PARAMS) == set(INTENTS)


def test_module_has_no_store_import():
    """D1: в модуле нет ни одного обращения к хранилищу — менять нечего
    по построению."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "rusterm.store\|sqlite", "rusterm/core/intent.py"],
        capture_output=True, text=True)
    assert result.returncode == 1, result.stdout
