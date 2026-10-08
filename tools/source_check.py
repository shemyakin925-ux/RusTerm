"""С3: панель источника для каждой клетки карточки — машиной (ТЗ-140 S1).

    python3 tools/source_check.py --root <каталог> [US-JPM US-DELL …]

Только чтение. Для каждой бумаги каждая заполненная клетка `card_view`
(годы и «сейчас») получает тот же текст панели, что окно при клике, —
одну дверь `data.panel_for_cell`, без Qt. Клетка проходит, когда текст
называет документ — источник с периодом, — или формулу с её входами
(источники панели; для меры из одного ценового ряда — ряд с датами).

Печать по бумаге: клеток · пройдено · первые 3 отказа с причиной.
Код выхода 0, когда по базе пройдено ≥ 98 % (ворота S2), иначе 1.
"""
from __future__ import annotations

import argparse
import sys

from rusterm.desktop import card, data
from rusterm.store.repos import RepoRegistry

TARGET = 0.98


def _panel_passes(panel: dict) -> tuple[bool, str]:
    """(пройдена, причина отказа) по виду панели клетки."""
    text = panel["text"]
    if panel.get("cell_kind") == "fact":
        if "значения нет" in text:
            return False, "факта нет"
        if "источник: —" in text:
            return False, "факт без источника (source_ref пуст)"
        if "период … —" in text:
            return False, "у факта нет периода"
        return True, ""
    if panel["panel"]["sources"]:
        return True, ""
    if "ценовой ряд" in text or "дивиденд (событие)" in text:
        return True, ""
    reason = "в родословной нет ни одного документа"
    null_reason = (panel.get("panel").get("null_reason")
                   or (panel.get("measure_row") or {}).get("null_reason"))
    if null_reason:
        reason = f"{reason}; причина меры: {null_reason}"
    return False, reason


def check_instrument(repos, paths, instrument_id: str) -> dict:
    """Все заполненные клетки карточки бумаги: [(колонка, концепт,
    прошла, причина, is_fact)] и цель «открыть документ» — файл
    первой прошедшей фактов-клетки."""
    info = data.measure_table_rows(repos, instrument_id, card.CARD_YEARS)
    view = card.card_view(repos, info)
    years = view["columns"][:-1]
    cells: list[tuple] = []
    open_target = None
    panels: dict = {}
    for row in view["rows"]:
        if row["kind"] == "section":
            continue
        now_year = (max(row["fact_ids"], default="")
                    if row["kind"] == "fact" else None)
        for index, cell in enumerate(row["cells"]):
            if cell["value"] is None:
                continue
            column = years[index] if index < len(years) else "сейчас"
            key = (row["concept"], column)
            if key not in panels:
                panels[key] = data.panel_for_cell(
                    repos, paths, view, row, index,
                    instrument_id=instrument_id)
            panel = panels[key]
            ok, why = _panel_passes(panel)
            is_fact = panel.get("cell_kind") == "fact"
            cells.append((column, row["concept"], ok, why, is_fact))
            if (ok and is_fact and open_target is None
                    and panel.get("open_target")):
                open_target = panel["open_target"]
    return {"instrument_id": instrument_id, "cells": cells,
            "open_target": open_target}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("instruments", nargs="*")
    args = parser.parse_args(argv)
    paths, conn = data.open_readonly(args.root)
    if conn is None:
        print(f"базы нет: {args.root}")
        return 1
    repos = RepoRegistry(conn, paths)
    instrument_ids = args.instruments or list(
        repos.instrument.list_instruments())
    total = passed = 0
    with_target = 0
    companies = 0
    for instrument_id in instrument_ids:
        result = check_instrument(repos, paths, instrument_id)
        cells = result["cells"]
        if not cells:
            continue
        companies += 1
        good = sum(1 for c in cells if c[2])
        total += len(cells)
        passed += good
        if result["open_target"]:
            with_target += 1
        fails = [c for c in cells if not c[2]]
        line = (f"{instrument_id:10} {good}/{len(cells)} = "
                f"{good / len(cells):.0%}")
        if fails:
            line += "   отказы: " + "; ".join(
                f"{concept}:{column} — {why}"
                for column, concept, _ok, why, _f in fails[:3])
        print(line)
    share = passed / total if total else 0.0
    print(f"ИТОГО {passed}/{total} = {share:.0%} клеток с источником "
          f"(ворота S2 {TARGET:.0%}); «открыть документ» есть у "
          f"{with_target}/{companies} бумаг")
    conn.close()
    return 0 if share >= TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
