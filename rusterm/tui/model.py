"""Чистая модель экранов TUI (TASK-8 U11).

Здесь всё содержимое экранов: списки строк и словари, собранные из
данных через репозитории. Никакого SQL, никакой сети, никаких формул,
никакого curses — рисование в rusterm/tui/app.py только красит то,
что собрали эти функции. Тесты гоняют модель без терминала.

Пустой блок показывается с причиной, мера без значения — «—» с
null_reason, governance — пять отдельных цветов без свёртки.
"""
from __future__ import annotations

import datetime
import json
from typing import Optional

NULL_MARK = "—"


def _today() -> str:
    return datetime.date.today().isoformat()


def list_rows(repos, watchlist_id: Optional[str]) -> list[dict]:
    """Экран «Список»: по строке на текущего участника watchlist.
    Пустой watchlist_id или без участников — пустой список строк."""
    if not watchlist_id:
        watchlists = repos.watchlist.list_watchlists()
        watchlist_id = watchlists[0]["watchlist_id"] if watchlists else None
    if not watchlist_id:
        return []
    rows = []
    for member in repos.watchlist.members(watchlist_id):
        instrument_id = member["instrument_id"]
        instrument = repos.instrument.get_instrument(instrument_id)
        ref = repos.instrument.ticker_for_instrument(
            instrument_id, _today())
        snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
        snapshot = (repos.snapshot.get_snapshot(snapshot_id)
                    if snapshot_id else None)
        coverage = {r["block"]: r["status"]
                    for r in repos.coverage.for_instrument(instrument_id)}
        cells = [coverage.get(block, "-") for block in (
            "prices", "fundamentals", "ownership", "corporate_actions",
            "governance", "industry_metrics", "peer_set", "llm_summary")]
        rows.append({
            "instrument_id": instrument_id,
            "ticker": ref["ticker"] if ref else instrument_id,
            "as_of": snapshot["as_of"] if snapshot else NULL_MARK,
            "snapshot_id": snapshot_id,
            "coverage_cells": cells,
            "peer_status": repos.peer_set.peer_status_for_instrument(
                instrument_id),
        })
    return rows


def card_rows(repos, instrument_id: str) -> dict:
    """Экран «Карточка»: меры, покрытие с причинами, governance."""
    snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
    measures = []
    for m in (repos.snapshot.get_measures(snapshot_id)
              if snapshot_id else []):
        measure_id, _scope, _ref, concept, value, unit, start, end, \
            formula_id, method_version, null_reason, _psv = m
        measures.append({
            "measure_id": measure_id,
            "concept": concept,
            "value": value if value is not None else NULL_MARK,
            "null_reason": null_reason if value is None else None,
            "unit": unit,
            "period": end,
            "method_version": method_version,
        })
    coverage = [
        {"block": r["block"], "status": r["status"], "reason": r["reason"]}
        for r in repos.coverage.for_instrument(instrument_id)
    ]
    governance = []
    for indicator in ("independent_directors", "ceo_chair", "related_party",
                      "insider_net", "auditor"):
        latest = repos.governance.latest(instrument_id, indicator)
        if latest is not None:
            governance.append({"indicator": indicator,
                               "color": latest["color"],
                               "method_version": latest["method_version"]})
        else:
            governance.append({"indicator": indicator, "color": "gray",
                               "method_version": None})
    return {
        "instrument_id": instrument_id,
        "snapshot_id": snapshot_id,
        "measures": measures,
        "coverage": coverage,
        "governance": governance,
        "peer_status": repos.peer_set.peer_status_for_instrument(
            instrument_id),
    }


def source_panel(repos, measure: dict) -> dict:
    """Панель источника выделенной меры: документ, локатор входного
    факта, method_version. Всё через репозитории, вычислений нет."""
    lineage = repos.snapshot.lineage_fact_ids(measure["measure_id"])
    sources = []
    for fact_id in lineage:
        fact = repos.fact.get_fact(fact_id)
        if fact is None:
            continue
        locator = fact["locator"]
        if isinstance(locator, str):
            locator = json.loads(locator)
        sources.append({
            "document": fact["source_ref"],
            "locator": locator,
            "fact_id": fact_id,
        })
    return {
        "measure_id": measure["measure_id"],
        "concept": measure["concept"],
        "method_version": measure.get("method_version"),
        "sources": sources,
    }


def render_list(rows: list[dict]) -> list[str]:
    """Строки для отрисовки экрана «Список» (чистая функция)."""
    lines = []
    for row in rows:
        mark = {"verified": " [peer verified]",
                "unverified": " [peer не подтверждён]"}.get(
            row["peer_status"], "")
        cells = "|".join(row["coverage_cells"])
        lines.append(f"{row['ticker']:<10} {row['instrument_id']:<14} "
                     f"{row['as_of']:<12} [{cells}]{mark}")
    return lines


def render_card(card: dict) -> list[str]:
    """Строки для отрисовки «Карточки» (чистая функция)."""
    lines = [f"Инструмент: {card['instrument_id']}"
             + (f"  (peer {card['peer_status']})"
                if card["peer_status"] else ""),
             "Меры:"]
    for m in card["measures"]:
        line = f"  {m['concept']}: {m['value']} {m['unit']}"
        if m["null_reason"]:
            line += f" ({m['null_reason']})"
        lines.append(line)
    lines.append("Покрытие:")
    for block in card["coverage"]:
        reason = f" — {block['reason']}" if block["reason"] else ""
        lines.append(f"  {block['block']}: {block['status']}{reason}")
    lines.append("Governance (пять цветов, не сворачиваются):")
    for g in card["governance"]:
        lines.append(f"  {g['indicator']}: {g['color']}")
    return lines
