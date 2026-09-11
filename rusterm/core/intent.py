"""Намерения модели и детерминированная классификация (TASK-16 D1,
docs/watchlist-and-llm.md §2.2, processes.md «Процесс 3»).

Модуль получает ТЕКСТ ответа модели значением и возвращает решение
значением: Intent или Clarification. Никогда не исключение, никогда
действие. Базы данных здесь нет и не будет: модуль ничего не знает о
хранилище. HTTP тоже: клиент — вызываемый объект, который отдаёт
строку; настоящий провайдер появится в rusterm/providers/ отдельно.

Ошибке по таблице процессов: не-JSON или намерение вне списка — один
повтор с жёстким напоминанием формата, затем уточняющий вопрос.
Известное намерение без обязательного параметра — уточняющий вопрос
сразу: повтор форматом не лечит.
"""
from __future__ import annotations

import json

# Восемь намерений §2.2 — замороженный кортеж. Намерение вне его —
# не намерение.
INTENTS: tuple[str, ...] = (
    "add_instruments",
    "add_industry",
    "add_index",
    "add_peers",
    "update_summaries",
    "compare",
    "ask_company",
    "ask_industry",
)

# Обязательные параметры по намерению — таблица в модуле, не догадка
# на месте вызова. Необязательные параметры допускаются, отсутствие
# обязательного — уточняющий вопрос (§2.3, условие 2).
REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    "add_instruments": ("tickers",),
    "add_industry": ("industry",),
    "add_index": ("index",),
    "add_peers": ("instrument",),
    "update_summaries": (),
    "compare": ("instruments",),
    "ask_company": ("instrument", "question"),
    "ask_industry": ("industry", "question"),
}

_PROMPT = (
    "Классифицируй запрос пользователя. Ответь ОДНИМ JSON-объектом "
    'вида {"intent": "<имя>", "params": {...}}. '
    f"Допустимые намерения: {', '.join(INTENTS)}."
)
_FORMAT_REMINDER = (
    "ОТВЕТ НЕ ПРИНЯТ. Ответь ровно одним JSON-объектом "
    '{"intent": "<имя из списка>", "params": {...}} и ничего больше.')


class Intent:
    """Распознанное намерение с параметрами. confidence принимается
    значением и нигде не ветвит: логировать можно, решать по нему нет."""

    def __init__(self, name: str, params: dict,
                 confidence: float | None = None):
        self.name = name
        self.params = params
        self.confidence = confidence

    def __eq__(self, other) -> bool:
        return (isinstance(other, Intent) and self.name == other.name
                and self.params == other.params)

    def __repr__(self) -> str:
        return f"Intent({self.name!r}, {self.params!r})"


class Clarification:
    """Уточняющий вопрос как значение: что не понято и почему."""

    def __init__(self, reason: str):
        self.reason = reason

    def __eq__(self, other) -> bool:
        return isinstance(other, Clarification) and \
            self.reason == other.reason

    def __repr__(self) -> str:
        return f"Clarification({self.reason!r})"


def missing_params(name: str, params: dict) -> tuple[str, ...]:
    """Обязательные параметры намерения, которых нет в ответе."""
    needed = REQUIRED_PARAMS.get(name, ())
    return tuple(p for p in needed
                 if params.get(p) in (None, "", [], {}))


def classify(client, message: str) -> Intent | Clarification:
    """Ответ модели значением -> Intent | Clarification.

    Не-JSON или намерение вне списка: ровно один повтор с жёстким
    напоминанием формата (итого два вызова клиента), затем
    Clarification. Известное намерение без обязательного параметра —
    Clarification сразу: повтор форматом не лечит. Ни исключений,
    ни действий.
    """
    prompt = f"{_PROMPT}\nЗапрос: {message}"
    raw = str(client.complete(prompt))
    intent, clarification, retryable = _try_parse(raw)
    if intent is None and retryable:
        retry = str(client.complete(
            f"{_FORMAT_REMINDER}\nЗапрос: {message}\n"
            f"Твой предыдущий ответ: {raw[:500]}"))
        intent, clarification, retryable = _try_parse(retry)
    return intent if intent is not None else clarification


def _try_parse(raw: str) -> tuple[Intent | None, Clarification | None,
                                  bool]:
    """(Intent, None, False) — распознано; иначе (None, Clarification,
    повторять_ли_формат)."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None, Clarification("ответ модели не JSON"), True
    if not isinstance(data, dict):
        return None, Clarification("ответ модели не JSON-объект"), True
    name = data.get("intent")
    if name not in INTENTS:
        return None, Clarification(f"намерение {name!r} вне списка"), True
    params = data.get("params") or {}
    if not isinstance(params, dict):
        return None, Clarification("params не объект"), True
    absent = missing_params(name, params)
    if absent:
        return None, Clarification(
            "не заполнены обязательные параметры: " + ", ".join(absent)
        ), False
    return Intent(name, params, data.get("confidence")), None, False


class RuleClient:
    """Детерминированный офлайн-классификатор tonight'а: ключа модели
    нет, а команде нужен ответ в том же контракте. Отдаёт ТЕКСТ JSON —
    дальше тот же путь classify(), никакого отдельного тракта. Правила
    нарочито узкие: это заглушка провайдера, не вторая логика."""

    def __init__(self, market: str | None = None):
        from rusterm.markets import DEFAULT_MARKET
        self.market = market or DEFAULT_MARKET

    def complete(self, prompt: str) -> str:
        message = prompt.rsplit("Запрос:", 1)[-1].strip()
        if message.lower().startswith(("добав", "add")):
            tickers = _ticker_like(message)
            if tickers:
                return json.dumps(
                    {"intent": "add_instruments",
                     "params": {"tickers": tickers,
                                "market": self.market}},
                    ensure_ascii=False)
        return json.dumps({"intent": None, "params": {}})


def _ticker_like(text: str) -> list[str]:
    import re
    found = re.findall(r"\b[A-Z][A-Z0-9]{1,5}(?:\.[A-Z]{1,3})?\b", text)
    return list(dict.fromkeys(found))
