"""Стартовая таблица окна (PRODUCT.md С1): все компании сразу.

Без Qt и без SQL. Числа — из той же карточки (`card.card_view`, колонка
«сейчас»: те же правила прочерков и бессмысленных значений) и из ядра
цен (`core.prices.year_change`). Пусто — «—».
"""
from __future__ import annotations

from rusterm.core.prices import year_change
from rusterm.desktop import card, data

# Коды групп peer set → русские имена (ТЗ-131 H3). Неизвестный код —
# как есть: честнее, чем выдуманное имя
SECTOR_RU = {
    "banks": "Банки",
    "hardware_electronics": "Техника и электроника",
    "mining_metals": "Металлы и добыча",
    "software": "Софт",
    "telecom": "Телеком",
}

# (ключ, заголовок): колонки таблицы слева направо
COLUMNS = (
    ("ticker", "Тикер"), ("name", "Компания"), ("group", "Группа"),
    ("market_cap_total", "Капитализация"), ("pe", "P/E"),
    ("net_margin", "Чистая маржа"), ("roe", "ROE"),
    ("change", "Цена за год"), ("price", "Цена"),
)
CARD_COLUMNS = ("market_cap_total", "pe", "net_margin", "roe")


def sector_name(code) -> str:
    if not code:
        return data.NO_SECTOR
    return SECTOR_RU.get(code, code)


def home_rows(repos, companies: list[dict]) -> list[dict]:
    """Строка на компанию: {"instrument_id", "cells": {ключ: {text,
    value, tooltip}}}. `value` — число для сортировки (None у «—»)."""
    rows = []
    for company in companies:
        instrument_id = company["instrument_id"]
        now = _now_cells(repos, instrument_id)
        cells = {
            "ticker": _text(company["ticker"]),
            "name": _text(company.get("name") or "—"),
            "group": _text(sector_name(company.get("sector"))),
        }
        for concept in CARD_COLUMNS:
            cell = now.get(concept)
            cells[concept] = (dict(cell) if cell is not None
                              else _text(card.DASH, value=None))
        price = year_change(repos.price, instrument_id)
        if price is None:
            cells["change"] = _text(card.DASH, tip="цен нет")
            cells["price"] = _text(card.DASH, tip="цен нет")
        else:
            change = price["change"]
            cells["change"] = (
                _text(card.DASH, tip="нет цены годом раньше")
                if change is None else
                _text(f"{'+' if change > 0 else ''}"
                      f"{data._group(change * 100, 1)} %", value=change,
                      tip=f"к цене годом раньше, на {price['date']}"))
            cells["price"] = _text(
                f"{data._group(price['close'], 2)} {price['currency'] or ''}"
                .strip(), value=price["close"], tip=f"закрытие {price['date']}")
        rows.append({"instrument_id": instrument_id, "company": company,
                     "cells": cells})
    return rows


def _now_cells(repos, instrument_id: str,
               concepts: tuple = CARD_COLUMNS) -> dict:
    """Клетки «сейчас» четырёх мер из последнего снапшота — тем же
    правилом, что колонка «сейчас» карточки (`card.implausible`, срок
    годности по последнему годовому отчёту), но без истории по годам:
    стартовая таблица открывается за секунды, а не за десятки."""
    snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
    instrument = repos.instrument.get_instrument(instrument_id)
    ends = (repos.snapshot.annual_period_ends(instrument.issuer_id)
            if instrument is not None else [])
    last_annual = max(ends, default=None)
    out = {}
    for m in repos.snapshot.get_measures(snapshot_id) if snapshot_id else []:
        concept, value, unit, end, reason = m[3], m[4], m[5], m[7], m[10]
        if concept not in concepts:
            continue
        if value is None:
            out[concept] = _text(card.DASH, tip=card._reason_words(reason))
            continue
        number = float(value)
        text = card.format_number(number, concept, unit)
        why = card.implausible(concept, number)
        if not why and last_annual and end and end < last_annual:
            why = f"значение за период до {end} старше годового отчёта"
        out[concept] = (_text(card.DASH, tip=f"{why} (расчёт: {text})")
                        if why else _text(text, value=number,
                                          tip=f"период до {end}"))
    return out


def _text(text: str, value=None, tip: str = "") -> dict:
    return {"text": text, "value": value, "tooltip": tip}


def matches(row: dict, query: str) -> bool:
    """Поиск по тикеру или названию с первых букв (ТЗ-131 H2)."""
    return data.matches_query(row["company"], query)
