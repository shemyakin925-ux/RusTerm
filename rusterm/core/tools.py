"""Четыре read-only инструмента модели (TASK-16 D2, docs
watchlist-and-llm.md §2.4): resolve_ticker, list_industry_instruments,
get_peer_set, get_snapshot_block. Никакой записи — каждое тело зовёт
только чтения репозиториев; страж теста держит набор имён РОВНО этим
четырём: пятый инструмент или инструмент с записью не пройдёт suite.
"""
from __future__ import annotations

from typing import Callable

# Источника отрасли в схеме нет (TASK-8 U12.4, см. watchlist_io):
# инструмент честно отвечает пустым списком с причиной, не выдумывает
# отрасль из других полей.
NO_INDUSTRY_SOURCE = "industry_source_absent_in_schema"


def resolve_ticker(repos, ticker: str, market: str,
                   as_of: str) -> dict:
    """Тикер -> instrument_id | ambiguous | not_found (§2.4)."""
    candidates = repos.instrument.resolve_ticker_candidates(
        ticker, market, as_of)
    if not candidates:
        return {"outcome": "not_found", "ticker": ticker,
                "market": market, "as_of": as_of}
    if len(candidates) > 1:
        return {"outcome": "ambiguous", "ticker": ticker,
                "candidates": sorted(candidates)}
    return {"outcome": "resolved", "ticker": ticker,
            "instrument_id": candidates[0]}


def list_industry_instruments(repos, industry: str,
                              filters: dict | None = None) -> dict:
    """Список инструментов отрасли. Источника отрасли в схеме нет —
    ответ пустой с причиной (I-coverage стиль: пробел показывается)."""
    return {"outcome": "resolved", "industry": industry,
            "instrument_ids": [], "note": NO_INDUSTRY_SOURCE}


def get_peer_set(repos, instrument_id: str) -> dict:
    """Peer set инструмента с версией и origin (§2.4). ТЗ-22 J2:
    ответ несёт состав набора — рынки, валюты, single-market/mixed."""
    peer_set = repos.peer_set.peer_set_for_instrument(instrument_id)
    if peer_set is None:
        return {"outcome": "not_found", "instrument_id": instrument_id}
    return {"outcome": "resolved", "instrument_id": instrument_id,
            "peer_set": peer_set,
            "composition": repos.peer_set.composition(
                peer_set["peer_set_version_id"]),
            "status": repos.peer_set.peer_status_for_instrument(
                instrument_id)}


def get_snapshot_block(repos, instrument_id: str, block: str) -> dict:
    """Блок снапшота: статус покрытия и меры последней версии (§2.4)."""
    snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
    coverage = {r["block"]: r
                for r in repos.coverage.for_instrument(instrument_id)}
    status = coverage.get(block, {}).get("status", "missing")
    reason = coverage.get(block, {}).get("reason")
    measures = []
    if snapshot_id:
        for m in repos.snapshot.get_measures(snapshot_id):
            measures.append({"measure_id": m[0], "concept": m[3],
                             "value": m[4], "unit": m[5],
                             "null_reason": m[10]})
    return {"outcome": "resolved", "instrument_id": instrument_id,
            "block": block, "status": status, "reason": reason,
            "measures": measures}


# Реестр — явное отображение имя -> вызываемое. Набор имён закреплён
# тестом РОВНО: пятый инструмент не пройдёт suite (TASK-16 D2).
TOOLS: dict[str, Callable] = {
    "resolve_ticker": resolve_ticker,
    "list_industry_instruments": list_industry_instruments,
    "get_peer_set": get_peer_set,
    "get_snapshot_block": get_snapshot_block,
}
