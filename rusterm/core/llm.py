"""LLM-summary с детерминированным предохранителем (TASK-7 T15,
docs/watchlist-and-llm.md §2.6).

Числа попадают в текст подстановкой из снапшота — модель их не сочиняет.
Валидатор: любое число в тексте, которого нет в citations, бракует текст
ЦЕЛИКОМ — блок остаётся missing с причиной; частично вычищенный текст
не хранится никогда. Пустой блок честнее правдоподобного.

Здесь нет и не будет HTTP: модель живёт в rusterm/providers/ (T16),
клиент — typing.Protocol, фальшивка живёт в тестах.
"""
from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from typing import Protocol

logger = logging.getLogger("rusterm.llm")

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_0-9]+)\s*\}\}")
_THOUSANDS_RE = re.compile(r"(\d)[,\u00a0 ](\d{3})(?=\D|$)")


def _normalize_number(token: str) -> str:
    """Канонический вид числа-токена (TASK-8 U0): разделители тысяч
    (пробел, неразрывный пробел, запятая между триадами) убираются,
    запятая и точка считаются одним десятичным разделителем. Сравнение
    строковое: без округлений и допусков."""
    t = token.replace("\u00a0", " ")
    while True:
        stripped = _THOUSANDS_RE.sub(r"\1\2", t)
        if stripped == t:
            break
        t = stripped
    return t.replace(",", ".")


class LlmClient(Protocol):
    """Клиент модели. Возвращает структуру ответа, не сырой текст."""

    def summarize(self, prompt: str) -> dict:
        """{summary: str, highlights: [str], risks: [str], ...}"""
        ...



def make_intent_client(environ=None, gate=None):
    """Выбор клиента классификации по ключу модели (TASK-19 F6; ответ
    на вопрос 1 REPORT-16, ruling §0.1): RUSTERM_LLM_API_KEY задан —
    API-клиент (ADR-0011 ②), не задан или пуст — детерминированный
    RuleClient. Оба отвечают по контракту complete(prompt); ошибки API
    приходят значениями. HTTP при этом остаётся в rusterm/providers/
    (проверка 8) — здесь только выбор, без импорта транспорта.

    environ и gate — точки инъекции тестов; реальный вызов читает
    os.environ и строит гейт сам.

    Гейт обязателен (находка координатора 17.09.2026): без него
    complete() у API-клиента сразу отдаёт
    ConfigError("llm_provider_requires_gate"), и `ops` с заданным ключом
    не работал вовсе — то есть у всякого настоящего пользователя.
    """
    import os
    env = os.environ if environ is None else environ
    if env.get("RUSTERM_LLM_API_KEY"):
        from rusterm.providers import host_limit
        from rusterm.providers.budget import NetworkGate, RequestGate
        from rusterm.providers.llm_api import LlmApiClient
        client = LlmApiClient.from_env(
            environ=env,
            gate=RequestGate(gate=NetworkGate(env)) if gate is None else gate,
            limit=host_limit("llm-api"))
        # ошибка сборки API-клиента (нет контакта SEC_UA и пр.) —
        # не ошибка команды: дверь падает на правило, работая офлайн.
        # ConfigError — значение-датаclass, не исключение.
        if hasattr(client, "complete"):
            return client
    from rusterm.core.intent import RuleClient
    return RuleClient()


class _ChatAdapter:
    """LlmApiClient -> протокол chat(prompt, history), который зовёт
    ChatSession.ask. Ошибка клиента приходит значением в поле error:
    разговор обязан сказать, почему молчит, а не упасть."""

    def __init__(self, client):
        self._client = client

    def chat(self, prompt, history):
        raw = self._client.complete(prompt)
        reason = getattr(raw, "reason", None)
        if reason is not None and not isinstance(raw, str):
            return {"text": None, "tool_calls": [], "error": reason}
        return {"text": str(raw), "tool_calls": []}


class _RefusingChatClient:
    """Клиента модели нет — разговор отвечает названной причиной.
    Молчание и падение одинаково запрещены."""

    def __init__(self, reason: str):
        self._reason = reason

    def chat(self, prompt, history):
        return {"text": None, "tool_calls": [], "error": self._reason}


def make_chat_client(environ=None, gate=None):
    """Дверь разговора: клиент, умеющий ровно то, что зовёт
    ChatSession.ask — chat(prompt, history) -> {text, tool_calls, error}.

    Дефект, ради которого дверь заведена (находка координатора
    17.09.2026): экран разговора строил клиента make_intent_client, у
    которого есть только complete(), и первый же вопрос падал
    AttributeError — и с ключом, и без. Единственная реализация
    протокола жила локальным классом внутри cmd_chat и экрану была
    недоступна. Теперь клиента строят одинаково CLI и экран.

    Ключа нет, тариф платный, гейт отказал — возвращается клиент,
    отвечающий названной причиной значением (ConfigError.reason).
    """
    import os

    from rusterm.providers import channel_tier, host_limit
    from rusterm.providers.budget import NetworkGate, RequestGate
    from rusterm.providers.llm_api import LlmApiClient

    env = os.environ if environ is None else environ
    # Те же два условия реестра, что у get_provider (инвариант 12):
    # канал без объявленного тарифа и платный канал не выдаются.
    tier = channel_tier("llm-api")
    if tier is None:
        return _RefusingChatClient("provider_declares_no_tier:llm-api")
    if tier == "paid":
        return _RefusingChatClient("paid_channel_refused")
    if gate is None:
        gate = RequestGate(gate=NetworkGate(env))
    client = LlmApiClient.from_env(environ=env, gate=gate,
                                   limit=host_limit("llm-api"))
    if not hasattr(client, "complete"):
        reason = getattr(client, "reason", "llm_provider_unavailable")
        return _RefusingChatClient(str(reason))
    return _ChatAdapter(client)


class LlmSummarizer:
    """Сборка LLM-summary: подстановка из снапшота + браковка целиком."""

    GUARD_REASON = "модель не смогла удержаться в данных"

    def __init__(self, client, snapshot_repo, llm_repo, coverage_repo):
        self._client = client
        self._snapshots = snapshot_repo
        self._llm = llm_repo
        self._coverage = coverage_repo

    def _measures(self, snapshot_id: str) -> dict:
        """Доступные для подстановки меры: концепт -> поля; value NULL
        цитировать нельзя — в подстановку не попадает."""
        out = {}
        for m in self._snapshots.get_measures(snapshot_id):
            concept, value, period_start, period_end = \
                m[3], m[4], m[6], m[7]
            if value is None:
                continue
            out[concept] = {"value": str(value), "unit": m[5],
                            "period_start": period_start,
                            "period_end": period_end}
        return out

    def _prompt(self, measures: dict) -> str:
        placeholders = ", ".join(f"{{{{{c}}}}}" for c in sorted(measures))
        return ("Составь summary по компании. Числа бери ТОЛЬКО "
                f"подстановкой плейсхолдеров: {placeholders}.\n"
                "Любое число не из списка — браковка всего текста.")

    def _render(self, text: str, measures: dict):
        """Подставить числа из снапшота. Возвращает (текст, substituted):
        substituted — точные строки, которые рендер вставил (значения мер).
        Незнакомый плейсхолдер — претензия на отсутствующие данные:
        текст бракуется."""
        substituted: list[str] = []

        def sub(match):
            concept = match.group(1)
            if concept not in measures:
                raise KeyError(concept)
            value = measures[concept]["value"]
            substituted.append(value)
            return value

        try:
            rendered = _PLACEHOLDER_RE.sub(sub, text)
        except KeyError:
            return None, []
        if "{{" in rendered:
            return None, []
        return rendered, substituted

    def _citations_for(self, text: str, substituted: list[str],
                       measures: dict):
        """Мультимножество числовых токенов текста обязано покрываться
        мультимножеством токенов подставленных значений (TASK-8 U0:
        подстроки вида «31» внутри «12-31» больше не цитата).

        None — брак всего текста; [] — чисел нет, цитаты не нужны;
        иначе список цитат по реально встретившимся мерам."""
        allowed: Counter = Counter()
        for value in substituted:
            for token in _NUMBER_RE.findall(value):
                allowed[_normalize_number(token)] += 1
        found: Counter = Counter(
            _normalize_number(token)
            for token in _NUMBER_RE.findall(text))

        if not found:
            return []
        if found - allowed:  # отрицательная разность = непокрытые числа
            return None

        citations = []
        used: set = set()
        remaining = Counter(found)
        for concept in sorted(measures):
            for token in _NUMBER_RE.findall(measures[concept]["value"]):
                token = _normalize_number(token)
                if remaining[token] > 0:
                    used.add(concept)
                    remaining[token] -= 1
        for concept in sorted(used):
            m = measures[concept]
            citations.append({"concept": concept,
                              "period_end": m["period_end"],
                              "value": m["value"]})
        return citations

    def run(self, instrument_id: str, snapshot_id: str,
            model: str = "unspecified") -> dict:
        measures = self._measures(snapshot_id)
        prompt = self._prompt(measures)
        response = self._client.summarize(prompt)

        # confidence логируется, но из ветвления убран (§2.3)
        confidence = response.get("confidence")
        if confidence is not None:
            logger.info("llm confidence=%s (не используется в решениях)",
                        confidence)

        summary, substituted = self._render(response.get("summary", ""),
                                             measures)
        highlights: list | None = []
        risks: list | None = []
        if summary is not None:
            for part_name, target in (("highlights", 0), ("risks", 1)):
                rendered_parts = []
                for item in response.get(part_name, []):
                    rendered, more = self._render(item, measures)
                    if rendered is None:
                        summary = None  # брак любого блока бракует всё
                        break
                    rendered_parts.append(rendered)
                    substituted.extend(more)
                if summary is None:
                    highlights = risks = None
                    break
                if part_name == "highlights":
                    highlights = rendered_parts
                else:
                    risks = rendered_parts
        if summary is None or highlights is None or risks is None:
            return self._reject(instrument_id)

        combined = " ".join([summary, *highlights, *risks])
        citations = self._citations_for(combined, substituted, measures)
        if citations is None:
            return self._reject(instrument_id)

        snapshot = self._snapshots.get_snapshot(snapshot_id)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self._llm.insert(
            instrument_id=instrument_id, model=model,
            prompt_hash=prompt_hash,
            snapshot_version=snapshot["version"],
            summary=summary, highlights=highlights, risks=risks,
            citations=citations)
        self._coverage.upsert(instrument_id, "llm_summary", "ready")
        return {"stored": True, "citations": citations,
                "prompt_hash": prompt_hash}

    def _reject(self, instrument_id: str) -> dict:
        """Браковка целиком: ничего в llm_summary, блок missing с причиной."""
        self._coverage.upsert(instrument_id, "llm_summary", "missing",
                              reason=self.GUARD_REASON)
        return {"stored": False, "reason": self.GUARD_REASON}
