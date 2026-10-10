"""Вкладка «Аналоги» (PRODUCT.md С4, ТЗ-132 G1–G3): компании группы рядом.

Без Qt и без SQL. Строки — участники peer set выбранной компании; числа
— из последнего снапшота каждой теми же правилами прочерков, что
стартовая таблица и колонка «сейчас» карточки (`home._now_cells`).
Последняя строка — медиана показанных значений; колонка, где числа нет
ни у кого (EBITDA у банков), не показывается.
"""
from __future__ import annotations

import statistics

from rusterm.desktop import card, data, home

# (концепт, заголовок) — столбцы сравнения слева направо
PEER_COLUMNS = (
    ("market_cap_total", "Капитализация"), ("pe", "P/E"), ("ps", "P/S"),
    ("ev_ebitda", "EV/EBITDA"), ("gross_margin", "Валовая маржа"),
    ("net_margin", "Чистая маржа"), ("roe", "ROE"),
    ("net_debt_ebitda", "Чистый долг / EBITDA"),
    ("fcf_yield", "Доходность FCF"),
)
MEDIAN_LABEL = "Медиана группы"
MIN_VALUES = 3


def peer_table(repos, instrument_id: str, peer: dict) -> dict | None:
    """{"title", "columns": [(концепт, заголовок)], "rows": [...],
    "median": {концепт: клетка}} или None без peer set.

    Строка: {"instrument_id", "ticker", "name", "is_self", "cells"}."""
    if not peer or not peer.get("has_peer_set"):
        return None
    concepts = tuple(c for c, _t in PEER_COLUMNS)
    rows = []
    for member in peer["members"]:
        iid = member["instrument_id"]
        instrument = repos.instrument.get_instrument(iid)
        issuer = (repos.instrument.get_issuer(instrument.issuer_id)
                  if instrument is not None else None)
        cells = home._now_cells(repos, iid, concepts)
        rows.append({"instrument_id": iid, "ticker": member["ticker"],
                     "name": issuer.name if issuer else "",
                     "is_self": member["is_self"],
                     "cells": {c: cells.get(c, home._text(card.DASH))
                               for c in concepts}})
    # колонка — где чисел хотя бы MIN_VALUES: одно-два числа медианы не
    # дают (у банков «валовая маржа» была бы одним значением Kaspi)
    columns = [(c, title) for c, title in PEER_COLUMNS
               if sum(r["cells"][c]["value"] is not None
                      for r in rows) >= MIN_VALUES]
    median = {}
    for concept, _title in columns:
        values = [r["cells"][concept]["value"] for r in rows
                  if r["cells"][concept]["value"] is not None]
        middle = statistics.median(values)
        unit = "USD" if concept == "market_cap_total" else None
        median[concept] = home._text(
            card.format_number(middle, concept, unit), value=middle,
            tip=f"медиана {len(values)} компаний из {len(rows)}")
    sector = home.sector_name(peer.get("peer_set_id"))
    title = (f"Группа: {sector} · {len(rows)} компаний · "
             f"медиана по последним значениям")
    return {"title": title, "columns": columns, "rows": rows,
            "median": median}


def compare_spec(table: dict | None) -> dict:
    """ТЗ-132 G2: место выбранной компании в группе по каждому
    показателю — какую долю остальных компаний она обходит (0–100,
    медиана группы — 50). Проценты к медиане взрываются, когда медиана
    близка к нулю (DELL: долг/EBITDA 2,05 против медианы 0,14 давал
    «+1 364 %»), место в группе ограничено и читается сразу. Показатель
    без числа у компании или без других чисел в группе не рисуется."""
    if not table:
        return {"kind": "message", "text": "у компании нет группы аналогов"}
    me = next((r for r in table["rows"] if r["is_self"]), None)
    if me is None:
        return {"kind": "message", "text": "компании нет в своей группе"}
    labels, values = [], []
    for concept, title in table["columns"]:
        mine = me["cells"][concept]["value"]
        others = [r["cells"][concept]["value"] for r in table["rows"]
                  if not r["is_self"]
                  and r["cells"][concept]["value"] is not None]
        if mine is None or not others:
            continue
        below = sum(1 for v in others if v < mine)
        equal = sum(1 for v in others if v == mine)
        labels.append(title)
        values.append(100.0 * (below + equal / 2) / len(others))
    if not values:
        return {"kind": "message",
                "text": "у компании нет чисел для сравнения с группой"}
    return {"kind": "hbars", "labels": labels, "values": values,
            "center": 50.0, "range": (0.0, 100.0),
            "axis_label": (f"{me['ticker']}: место в группе, % компаний "
                           f"ниже (50 — медиана)")}
