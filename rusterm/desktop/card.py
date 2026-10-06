"""Карточка компании как в Yahoo Financials (PRODUCT.md, сценарий С2).

Слой отображения поверх `data.measure_table_rows`, без Qt и без SQL:
- разделы (Отчётность · Рентабельность · Оценка · Долг · Денежный
  поток · Дивиденды) и русские названия с формулой в подсказке;
- годы слева направо от старых к новым, «сейчас» — последней колонкой;
- пусто — «—», причина — в подсказке; строка, где пусто всё, и мера,
  неприменимая к отрасли, не показываются (сколько скрыто — словами);
- бессмысленное значение (ROE при отрицательном капитале, P/E при
  убытке) — «—» с объяснением, исходное число остаётся в подсказке,
  панели источника и экспорте;
- строки отчётности (выручка, чистая прибыль, долг…) берутся из
  годовых фактов как поданы — это не формула, а сам факт.
"""
from __future__ import annotations

import datetime
from typing import Optional

from rusterm.desktop import data
from rusterm.measures_ru import measure_name
from rusterm.reasons_ru import reason_phrase

DASH = "—"

# Сколько лет показывает карточка: 10, как у аналогов
CARD_YEARS = 10

# Колонка текущих значений — последней, как TTM у аналогов
NOW_COLUMN = "сейчас"

# (концепт, подпись, подсказка-формула, источник): "measure" — мера
# снапшота, "flow" — годовой факт-поток, "stock" — факт-остаток на
# конец финансового года
SECTIONS: list[tuple[str, list[tuple[str, str, str, str]]]] = [
    ("Отчётность", [
        ("revenue", "Выручка", "строка отчёта о прибылях, за год", "flow"),
        ("gross_profit", "Валовая прибыль", "выручка − себестоимость",
         "measure"),
        ("operating_income", "Операционная прибыль",
         "строка отчёта о прибылях, за год", "flow"),
        ("ebitda", "EBITDA", "операционная прибыль + амортизация",
         "measure"),
        ("net_income", "Чистая прибыль", "строка отчёта о прибылях, за год",
         "flow"),
        ("eps_diluted", "Прибыль на акцию (разводн.)",
         "строка отчёта о прибылях, за год", "flow"),
    ]),
    ("Рентабельность", [
        ("gross_margin", "Валовая маржа", "валовая прибыль / выручка",
         "measure"),
        ("operating_margin", "Операционная маржа",
         "операционная прибыль / выручка", "measure"),
        ("net_margin", "Чистая маржа", "чистая прибыль / выручка",
         "measure"),
        ("roe", "ROE", "чистая прибыль / средний собственный капитал",
         "measure"),
        ("roe_incl_nci", "ROE с долей меньшинства",
         "чистая прибыль / средний капитал вместе с неконтролирующей долей",
         "measure"),
        ("roic", "ROIC", "NOPAT / средний инвестированный капитал",
         "measure"),
        ("nopat", "NOPAT", "операционная прибыль × (1 − ставка налога)",
         "measure"),
        ("effective_tax", "Эффективная ставка налога",
         "налог / прибыль до налога", "measure"),
        ("asset_turnover", "Оборачиваемость активов",
         "выручка / средние активы", "measure"),
    ]),
    ("Оценка", [
        ("market_cap_total", "Капитализация",
         "цена × число акций, все классы", "measure"),
        ("ev", "EV", "капитализация + чистый долг + доля меньшинства",
         "measure"),
        ("pe", "P/E", "капитализация / чистая прибыль", "measure"),
        ("pb", "P/B", "капитализация / собственный капитал", "measure"),
        ("ps", "P/S", "капитализация / выручка", "measure"),
        ("ev_ebitda", "EV/EBITDA", "EV / EBITDA", "measure"),
        ("fcf_yield", "Доходность FCF", "FCF / капитализация", "measure"),
    ]),
    ("Долг и устойчивость", [
        ("total_assets", "Активы", "баланс на конец года", "stock"),
        ("total_equity", "Собственный капитал", "баланс на конец года",
         "stock"),
        ("total_debt", "Долг", "баланс на конец года", "stock"),
        ("cash", "Денежные средства", "баланс на конец года", "stock"),
        ("net_debt", "Чистый долг", "долг − денежные средства", "measure"),
        ("net_debt_ebitda", "Чистый долг / EBITDA", "чистый долг / EBITDA",
         "measure"),
        ("interest_coverage", "Покрытие процентов",
         "операционная прибыль / процентные расходы", "measure"),
        ("invested_capital", "Инвестированный капитал",
         "собственный капитал + долг − денежные средства", "measure"),
    ]),
    ("Денежный поток", [
        ("ocf", "Операционный денежный поток",
         "строка отчёта о движении денег, за год", "flow"),
        ("capex", "Капитальные затраты",
         "строка отчёта о движении денег, за год", "flow"),
        ("fcf", "Свободный денежный поток (FCF)",
         "операционный поток − капзатраты", "measure"),
    ]),
    ("Дивиденды и доходность", [
        ("dps", "Дивиденд на акцию", "объявлено за год", "flow"),
        ("div_yield", "Дивидендная доходность",
         "дивиденд на акцию за 12 мес. / цена", "measure"),
        ("total_return", "Полная доходность акции",
         "рост цены + дивиденды за период", "measure"),
        ("drawdown", "Просадка от максимума",
         "цена / максимум за период − 1", "measure"),
    ]),
]

# Русское имя по концепту — для списка мер графика
LABELS = {concept: label for _title, items in SECTIONS
          for concept, label, _hint, _kind in items}

# Меры вне разделов карточки — в «Прочее» под понятным именем
OTHER_LABELS = {"market_cap": "Капитализация класса акций",
                "cagr": "CAGR"}

# Служебные меры, которых в карточке нет: HHI — вход отрасли, цена с
# поправкой — вход доходности; у аналогов строк таких нет
DROPPED = frozenset({"hhi", "price_adj"})

# У банка нет валовой и операционной прибыли, EBITDA и долга в смысле
# промышленной компании — как у Yahoo, строк нет вовсе. Признак банка —
# любая мера карточки с причиной `not_applicable: banks`
BANK_HIDDEN = frozenset({
    "gross_profit", "gross_margin", "operating_income", "operating_margin",
    "ebitda", "nopat", "total_debt", "cash", "capex"})

# Меры-проценты среди фактов не встречаются; деньги на акцию — отдельно
PER_SHARE = frozenset({"eps_diluted", "dps"})

# Годовой поток: 350..380 дней — тот же коридор, что у ядра (ТЗ-91 B4)
ANNUAL_MIN_DAYS, ANNUAL_MAX_DAYS = 350, 380


def _year(period_end: str) -> str:
    return str(period_end)[:4]


def statement_series(repos, issuer_id: str, concept: str,
                     kind: str) -> dict[str, tuple]:
    """{год: (значение, валюта, fact_id)} годового факта.

    Поток — окно 350..380 дней; остаток — значение на дату конца
    финансового года эмитента (`annual_period_ends`). В пределах года
    побеждает свежий конец периода и свежая подача (порядок двери)."""
    rows = repos.snapshot.statement_facts(issuer_id, concept)
    year_ends = (set(repos.snapshot.annual_period_ends(issuer_id))
                 if kind == "stock" else set())
    series: dict[str, tuple] = {}
    for value, start, end, currency, fact_id in rows:
        if kind == "flow":
            if not start:
                continue
            try:
                days = (datetime.date.fromisoformat(end)
                        - datetime.date.fromisoformat(start)).days
            except (TypeError, ValueError):
                continue
            if not ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
                continue
        elif end not in year_ends:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        series.setdefault(_year(end), (number, currency, fact_id))
    return series


def format_number(value: float, concept: str, unit: Optional[str]) -> str:
    """Число карточки: деньги на акцию — 2 знака с валютой, прочее —
    общим правилом окна."""
    if concept in PER_SHARE:
        suffix = f" {unit}" if unit else ""
        return f"{data._group(value, 2)}{suffix}"
    return data.format_value(value, concept, unit)


def implausible(concept: str, value: float,
                equity: Optional[float] = None,
                ebitda: Optional[float] = None) -> Optional[str]:
    """Почему число нельзя показывать как число, или None.

    Деление на отрицательный или почти нулевой знаменатель даёт
    формально верное, но бессмысленное значение (ROE DELL 1 401 % при
    отрицательном капитале). Аналоги показывают здесь прочерк."""
    if concept in ("roe", "roe_incl_nci", "pb"):
        if equity is not None and equity <= 0:
            return "собственный капитал отрицательный — показатель не имеет смысла"
        if concept != "pb" and abs(value) > 5:
            return "больше 500 % — капитал близок к нулю, показатель не имеет смысла"
    if concept == "pe" and value <= 0:
        return "убыток — P/E не имеет смысла"
    if concept == "pb" and value <= 0:
        return "собственный капитал отрицательный — P/B не имеет смысла"
    if concept == "ev_ebitda" and value <= 0:
        return "EBITDA отрицательная — EV/EBITDA не имеет смысла"
    if concept == "net_debt_ebitda" and ebitda is not None and ebitda <= 0:
        return "EBITDA отрицательная — показатель не имеет смысла"
    return None


def _number(value) -> Optional[float]:
    """Значение меры числом; текст, который не число, — нет значения."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _cell(text: str, tooltip: str = "", value=None) -> dict:
    return {"text": text, "tooltip": tooltip, "value": value}


def _reason_words(reason: Optional[str]) -> str:
    """ТЗ-111 U1: фраза словами, сырой токен — в скобках."""
    if not reason:
        return "нет значения"
    phrase = reason_phrase(reason)
    return phrase if phrase == reason else f"{phrase} ({reason})"


def _empty_tooltip(measure_row: Optional[dict]) -> str:
    reason = (measure_row or {}).get("null_reason")
    if str(reason or "").startswith("negative_denominator"):
        return ("знаменатель отрицательный — показатель не имеет смысла "
                f"({reason})")
    return _reason_words(reason)


def card_view(repos, info: dict, year_count: int = CARD_YEARS,
              show_empty: bool = False) -> dict:
    """Карточка по разделам из результата `data.measure_table_rows`.

    Форма: ``{"columns": [годы по возрастанию…, "сейчас"],
    "rows": [...], "hidden_note": str|None}``. Строка — либо
    ``{"kind": "section", "title"}``, либо ``{"kind": "measure"|"fact",
    "concept", "label", "hint", "cells": [{text, tooltip, value}],
    "measure_row": строка data (для панели источника) или None,
    "fact_ids": {год: fact_id}}``."""
    measures = {m["concept"]: m for m in info["measures"]
                if not m["measure"].get("percentile_of")}
    instrument = repos.instrument.get_instrument(info["instrument_id"])
    issuer_id = instrument.issuer_id if instrument is not None else None

    facts: dict[str, dict] = {}
    if issuer_id:
        for _title, items in SECTIONS:
            for concept, _label, _hint, kind in items:
                if kind != "measure":
                    facts[concept] = statement_series(
                        repos, issuer_id, concept, kind)

    years = set(info["years"])
    for series in facts.values():
        years.update(series)
    columns = sorted(years)[-year_count:]

    def year_value(concept: str, year: str) -> Optional[float]:
        if concept in facts:
            point = facts[concept].get(year)
            return point[0] if point else None
        row = measures.get(concept)
        return _number(row["year_values"].get(year)) if row else None

    def now_value(concept: str) -> Optional[float]:
        row = measures.get(concept)
        return _number(row["value"]) if row else None

    # мера, которой нет в разделах (новая в словаре), не теряется молча:
    # она уходит в «Прочее» под своим кодом
    listed = {concept for _t, items in SECTIONS for concept, *_ in items}
    extra = [(concept, OTHER_LABELS.get(concept, measure_name(concept)), "",
              "measure")
             for concept in measures
             if concept not in listed and concept not in DROPPED]
    is_bank = any(str(m.get("null_reason") or "").startswith(
        "not_applicable: banks") for m in measures.values())

    rows: list[dict] = []
    hidden_na: list[str] = []
    hidden_empty: list[tuple[str, str]] = []
    for title, items in [*SECTIONS, ("Прочее", extra)]:
        section_rows = []
        for concept, label, hint, kind in items:
            measure_row = measures.get(concept)
            if (measure_row is not None and data.not_applicable_text(
                    measure_row.get("null_reason"))) or (
                        is_bank and concept in BANK_HIDDEN):
                hidden_na.append(label)
                continue
            # капитализация класса — только если классов несколько и она
            # отличается от общей; иначе это вторая строка капитализации
            if concept == "market_cap" and all(
                    year_value("market_cap", y) is None
                    or year_value("market_cap_total", y) is None
                    or abs(year_value("market_cap", y)
                           - year_value("market_cap_total", y))
                    <= 0.001 * abs(year_value("market_cap_total", y))
                    for y in columns):
                continue
            # ROE с долей меньшинства — только если доля есть и меняет
            # число: иначе это вторая строка ROE (у аналогов её нет)
            if concept == "roe_incl_nci" and not any(
                    year_value("roe_incl_nci", y) is not None
                    and year_value("roe", y) is not None
                    and abs(year_value("roe_incl_nci", y)
                            - year_value("roe", y)) > 0.005
                    for y in columns):
                continue
            cells = []
            fact_ids = {}
            for year in columns:
                value = year_value(concept, year)
                if value is None:
                    cells.append(_cell(DASH, _empty_tooltip(measure_row)))
                    continue
                if concept in facts:
                    _v, currency, fact_id = facts[concept][year]
                    fact_ids[year] = fact_id
                    unit = currency
                else:
                    unit = measure_row.get("unit")
                why = implausible(concept, value,
                                  equity=year_value("total_equity", year),
                                  ebitda=year_value("ebitda", year))
                text = format_number(value, concept, unit)
                if why:
                    cells.append(_cell(DASH, f"{why} (расчёт: {text})"))
                    continue
                tip = hint
                if (measure_row is not None and str(
                        measure_row["years"].get(year, "")).endswith(
                            data.RUN_YEAR_MARK)):
                    text += "*"
                    tip += "; * год отнесён по дате расчёта, у меры нет периода"
                cells.append(_cell(text, tip, value))
            current = now_value(concept)
            if current is None:
                cells.append(_cell(DASH, (_empty_tooltip(measure_row)
                                          if measure_row is not None else
                                          "текущего значения нет: "
                                          "строка отчёта — по годам")))
            else:
                text = format_number(current, concept,
                                     measure_row.get("unit"))
                why = implausible(
                    concept, current,
                    equity=year_value("total_equity", columns[-1])
                    if columns else None,
                    ebitda=now_value("ebitda"))
                period = (measure_row["measure"].get("period")
                          or "период не указан")
                cells.append(_cell(DASH, f"{why} (расчёт: {text})")
                             if why else _cell(text, f"{hint}; период {period}",
                                               current))
            if not show_empty and all(c["value"] is None for c in cells):
                reason = (measure_row or {}).get("null_reason")
                hidden_empty.append((label, _reason_words(reason)))
                continue
            section_rows.append({
                "kind": "fact" if concept in facts else "measure",
                "concept": concept, "label": label, "hint": hint,
                "cells": cells, "measure_row": measure_row,
                "fact_ids": fact_ids})
        if section_rows:
            rows.append({"kind": "section", "title": title})
            rows.extend(section_rows)

    notes = []
    if is_bank and not hidden_na:
        hidden_na.append("банк")
    # ТЗ-81 B2: лет меньше потолка — словами почему (границы снапшотов)
    if columns and len(columns) < year_count:
        span = data.history_note(repos, info["instrument_id"], len(columns))
        if span:
            notes.append(span)
    if hidden_na:
        sector = ("не применимо к банкам" if is_bank else
                  data.not_applicable_text(next(
                      m["null_reason"] for m in measures.values()
                      if data.not_applicable_text(m.get("null_reason")))))
        notes.append(f"скрыто {len(hidden_na)} показателей — {sector}")
    if hidden_empty:
        notes.append(f"скрыто {len(hidden_empty)} показателей без данных")
    # ТЗ-95 F3: дыра между видимыми годами названа словами
    gap = data.year_gap_note(columns)
    if gap:
        notes.append(gap)
    return {"columns": [*columns, NOW_COLUMN], "rows": rows,
            "hidden_note": "; ".join(notes) or None,
            # что скрыто и почему — подсказкой к строке под таблицей
            "hidden": hidden_empty}


def hidden_tooltip(view: dict) -> str:
    """Скрытые пустые показатели с причиной, по строке на каждый."""
    return "\n".join(f"{label}: {reason}"
                     for label, reason in view.get("hidden", []))


def axis_label(table: dict, concept: Optional[str]) -> Optional[str]:
    """Подпись оси графика для строки карточки (см. `chart_table`)."""
    row = next((m for m in table["measures"]
                if m["concept"] == concept), None)
    return row.get("axis") if row else None


def fact_source_text(repos, row: dict, year: str) -> str:
    """Панель источника для строки отчётности: документ и место факта."""
    fact_id = row.get("fact_ids", {}).get(year)
    if not fact_id:
        return f"{row['label']}, {year}: значения нет"
    fact = repos.fact.get_fact(fact_id) or {}
    parts = [f"{row['label']}, {year}: факт отчётности",
             f"период {fact.get('period_start') or '…'} — "
             f"{fact.get('period_end')}",
             f"источник: {fact.get('source_ref') or '—'}"]
    if fact.get("locator"):
        parts.append(f"место: {fact['locator']}")
    return " · ".join(parts)


def _axis_scale(entry: dict, values: dict) -> tuple[float, str]:
    """Делитель и подпись оси: «Выручка, млрд USD», «Чистая маржа, %»,
    а не 1.1e+11 и 0.052."""
    concept, label = entry["concept"], entry["label"]
    if concept in data.PERCENT_CONCEPTS:
        return 0.01, f"{label}, %"
    if concept in data.MULTIPLE_CONCEPTS or concept in PER_SHARE:
        return 1.0, label
    unit = next((c["text"].rsplit(" ", 1)[-1] for c in entry["cells"]
                 if c["value"] is not None and " " in c["text"]), "")
    top = max((abs(v) for v in values.values()), default=0.0)
    for limit, word in ((1e12, "трлн"), (1e9, "млрд"), (1e6, "млн")):
        if top >= limit:
            return limit, f"{label}, {word} {unit}".strip()
    return 1.0, label


def chart_table(view: dict, info: dict) -> dict:
    """Строки карточки в форме таблицы `data.measure_table_rows` для
    линии и столбиков: годы по возрастанию, сырые значения по годам.
    Прочерк из-за бессмысленного значения на график тоже не идёт."""
    years = view["columns"][:-1]
    measures = []
    for entry in view["rows"]:
        if entry["kind"] == "section":
            continue
        values = {year: cell["value"] for year, cell
                  in zip(years, entry["cells"]) if cell["value"] is not None}
        scale, axis = _axis_scale(entry, values)
        measures.append({"concept": entry["concept"], "years": {},
                         "year_values": {y: v / scale
                                         for y, v in values.items()},
                         "axis": axis})
    return {**info, "years": years, "measures": measures}


# Пороги PRODUCT.md: заполненность ≥ 90 % за пять закрытых лет
FILL_YEARS = 5


def fill_rate(view: dict) -> tuple[int, int, list[tuple[str, str]]]:
    """(заполнено, применимо, [(концепт, год) пустых]) клеток карточки за последние FILL_YEARS
    закрытых лет — метрика PRODUCT.md С2.

    Закрытый год — тот, где есть выручка (отчёт за год подан); идущий
    год с одной капитализацией не считается. Не применимо и потому не
    в знаменателе: прочерк по бессмысленному значению (отрицательный
    капитал) и строки, которые карточка скрыла как неприменимые."""
    years = view["columns"][:-1]
    revenue = next((r for r in view["rows"]
                    if r.get("concept") == "revenue"), None)
    closed = [y for i, y in enumerate(years)
              if revenue is None or revenue["cells"][i]["value"] is not None]
    window = closed[-FILL_YEARS:]
    index = [years.index(y) for y in window]
    filled = applicable = 0
    gaps: list[tuple[str, str]] = []
    for row in view["rows"]:
        if row["kind"] == "section":
            continue
        for i in index:
            cell = row["cells"][i]
            if cell["value"] is None and "не имеет смысла" in cell["tooltip"]:
                continue
            applicable += 1
            if cell["value"] is None:
                gaps.append((row["concept"], years[i]))
            else:
                filled += 1
    return filled, applicable, gaps
