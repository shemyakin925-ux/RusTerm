"""Массовая операция над watchlist: предложение -> показ -> подтверждение
-> атомарное применение (TASK-16 D3–D6, docs/watchlist-and-llm.md §2.3–2.5
и §3, processes.md «Процесс 3»).

Пять условий §2.3 проверяются детерминированно; не выполнено любое —
уточняющий вопрос или отказ ЗНАЧЕНИЕМ, никогда действие наугад.
confidence принимается полем и не ветвит нигде. Dry-run не пишет ничего:
ни версии, ни участника, ни покрытия, ни аудита. Применение — одна новая
версия списка и все участники в одной транзакции SQLite: сбой посередине
не оставляет полусписка.
"""
from __future__ import annotations

import sqlite3
import uuid

from rusterm.core.intent import Clarification, Intent, missing_params

# Четыре статуса dry-run по §2.5 — текст закреплён документом
STATUS_ADD = "будет добавлена"
STATUS_FILTERED = "исключена фильтром"
STATUS_PRESENT = "уже в списке"
STATUS_UNRESOLVED = "не разрешилась"

# Лимит §3.4: по умолчанию 100 инструментов; больше — отдельное
# подтверждение размера. Лимит относится к правке состава списка.
OPERATION_LIMIT = 100

# Правки состава: только эти намерения создают версию списка.
COMPOSITION_INTENTS: tuple[str, ...] = (
    "add_instruments", "add_industry", "add_index", "add_peers")


class Refused:
    """Отказ как значение: операция не выполнялась, причина названа."""

    def __init__(self, reason: str):
        self.reason = reason

    def __eq__(self, other) -> bool:
        return isinstance(other, Refused) and self.reason == other.reason

    def __repr__(self) -> str:
        return f"Refused({self.reason!r})"


class Proposal:
    """Полный список позиций с пометкой по каждой (§2.5)."""

    def __init__(self, intent: str, rows: list[dict]):
        self.intent = intent
        self.rows = rows

    @property
    def addable(self) -> list[tuple[str, str]]:
        return [(r["instrument_id"], r["ticker"]) for r in self.rows
                if r["status"] == STATUS_ADD]

    def counts(self) -> dict:
        out: dict[str, int] = {}
        for r in self.rows:
            out[r["status"]] = out.get(r["status"], 0) + 1
        return out


def _resolve(repos, ticker: str, market: str, as_of: str) -> tuple:
    """(status, instrument_id) по одному тикеру."""
    candidates = repos.instrument.resolve_ticker_candidates(
        ticker, market, as_of)
    if not candidates:
        return STATUS_UNRESOLVED, None
    if len(candidates) > 1:
        return STATUS_UNRESOLVED, None
    return STATUS_ADD, candidates[0]


def prepare(repos, watchlist_id: str, intent: Intent, as_of: str,
            filters: dict | None = None,
            size_confirmed: bool = False) -> Proposal | Refused | \
    Clarification:
    """Условия 1–4 §2.3. Условие 5 (подтверждение) — на применении.

    Неразрешённый тикер не отменяет операцию: разрешённые показываются
    к добавлению, неразрешённые — отдельными строками с пометкой.
    """
    if not isinstance(intent, Intent):
        return intent if isinstance(intent, Clarification) else \
            Clarification("намерение не распознано")
    if intent.name not in COMPOSITION_INTENTS:
        return Clarification(
            f"намерение {intent.name!r} — не правка состава списка")
    absent = missing_params(intent.name, intent.params)
    if absent:
        return Clarification(
            "не заполнены обязательные параметры: " + ", ".join(absent))

    from rusterm.markets import DEFAULT_MARKET
    market = intent.params.get("market", DEFAULT_MARKET)
    tickers = intent.params.get("tickers") or []
    if intent.name == "add_instruments" and not tickers:
        return Clarification("список тикеров пуст")
    current = {m["instrument_id"]
               for m in repos.watchlist.members(watchlist_id)}
    rows: list[dict] = []
    for ticker in tickers:
        status, instrument_id = _resolve(repos, ticker, market, as_of)
        if status == STATUS_ADD and filters:
            reason = _filtered(filters, repos, instrument_id)
            if reason:
                status, instrument_id = STATUS_FILTERED, None
                rows.append({"ticker": ticker, "status": status,
                             "instrument_id": None, "reason": reason})
                continue
        if status == STATUS_ADD and instrument_id in current:
            status = STATUS_PRESENT
        rows.append({"ticker": ticker, "status": status,
                     "instrument_id": instrument_id,
                     "reason": None if status == STATUS_ADD else
                     (None if status == STATUS_PRESENT else None)})
    proposal = Proposal(intent.name, rows)
    # Условие 4: лимит размера (§3.4). Больше 100 — отдельное явное
    # подтверждение, называющее размер; без него — отказ значением.
    if len(proposal.addable) > (filters or {}).get("limit", 100) \
            and not size_confirmed:
        return Refused(
            f"операция превышает лимит {OPERATION_LIMIT} инструментов: "
            f"к добавлению {len(proposal.addable)}; требуется отдельное "
            "подтверждение размера")
    return proposal


def _filtered(filters: dict, repos, instrument_id) -> str | None:
    """Детерминированные фильтры §Процесс 3 шаг 4. Tonight: исключение
    делистингованных бумаг. Возвращает причину или None."""
    if filters.get("exclude_delisted"):
        instrument = repos.instrument.get_instrument(instrument_id)
        if instrument is not None and instrument.status == "delisted":
            return "инструмент делистингован"
    return None


def apply(watchlist_repo, watchlist_id: str,
          addable: list[tuple[str, str]],
          action: str = "ops") -> dict:
    """Условие 5 пройдено: одна новая версия и все участники в ОДНОЙ
    транзакции. Сбой посередине откатывает целиком — ноль новых версий,
    ноль новых участников; ошибка возвращается значением."""
    if not addable:
        return {"applied": False,
                "reason": "нет позиций к добавлению"}
    current = watchlist_repo.current_version(watchlist_id)
    if current is None:
        return {"applied": False,
                "reason": f"список {watchlist_id!r} не найден"}
    try:
        created = watchlist_repo.create_version_with_members(
            watchlist_id, action,
            f"ops: добавлено {len(addable)}", addable)
    except (sqlite3.IntegrityError, ValueError) as e:
        return {"applied": False, "reason": f"транзакция отменена: {e}"}
    return {"applied": True, "version": created["version"],
            "watchlist_version_id": created["watchlist_version_id"]}
