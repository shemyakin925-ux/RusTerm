"""Корректировка котировок: наша функция — вендорская сверка (ТЗ-23 K3).

Формула корректировки написана и протестирована в M2 (price_adj,
независимость от порядка сплитов и дивидендов — backlog B5); здесь
только проводка: события из corporate_action (K1) переводятся в
коэффициенты словаря (split_factor, dividend_factor), вендорский
`adjusted` хранится рядом и служит СВЕРКОЙ. Расхождение сверх допуска —
находка с обоими числами; ничто не переписывается и не удаляется.
"""
from __future__ import annotations

from rusterm.formulas import dividend_factor, price_adj, split_factor

# Допуск сверки с вендором: 0.1% относительный, но не меньше копейки
# на абсолютную величину — чтобы целые цены не шумели.
TOLERANCE_ABS = 0.01
TOLERANCE_REL = 0.001


def build_events(price_rows: list[dict],
                 action_rows: list[dict]) -> list[tuple[str, float]]:
    """corporate_action -> коэффициенты для price_adj.

    Сплит 1:k — split_factor(k). Дивиденд D — dividend_factor(D,
    close последнего торгового дня ПЕРЕД ex-date); если цены перед
    ex-date нет, событие не применяется (не хватает данных — это не
    выдуманный коэффициент).
    """
    dates = [r["date"] for r in price_rows if r.get("close") is not None]
    close_by_date = {r["date"]: r["close"] for r in price_rows}
    events: list[tuple[str, float]] = []
    for a in sorted(action_rows, key=lambda x: x["ex_date"]):
        if a["kind"] == "split" and a.get("factor") is not None:
            events.append((a["ex_date"], split_factor(float(a["factor"]))))
        elif a["kind"] == "dividend" and a.get("amount") is not None:
            before = [d for d in dates if d < a["ex_date"]]
            if not before:
                continue
            prev_close = close_by_date[max(before)]
            events.append((a["ex_date"],
                           dividend_factor(float(a["amount"]),
                                           float(prev_close))))
    return events


def our_adjusted_series(
        price_rows: list[dict],
        action_rows: list[dict],
) -> tuple[list[tuple[str, float]], list[tuple[str, float, float]]]:
    """Наша скорректированная серия по price_adj и сверка с вендором.

    price_rows — строки PriceRepo.series() по возрастанию даты;
    action_rows — CorporateActionRepo.all(). Возвращает
    (series, disagreements): series — [(date, our_adjusted)];
    disagreements — [(date, ours, vendor_adjusted)] для дней, где
    вендорский adjusted расходится с нашим сверх допуска. Хранение
    не меняется: оба числа только сообщаются.
    """
    closes = [(r["date"], float(r["close"])) for r in price_rows
              if r.get("close") is not None]
    events = build_events(price_rows, action_rows)
    ours = price_adj(closes, events)
    vendor = {r["date"]: r["adjusted"] for r in price_rows
              if r.get("adjusted") is not None}
    disagreements: list[tuple[str, float, float]] = []
    for date, value in ours:
        other = vendor.get(date)
        if other is None:
            continue
        if abs(other - value) > max(TOLERANCE_ABS,
                                    abs(value) * TOLERANCE_REL):
            disagreements.append((date, value, float(other)))
    return ours, disagreements
