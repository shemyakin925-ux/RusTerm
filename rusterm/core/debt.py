"""Долг = долгосрочный + краткосрочный (BACKLOG P5, 08.10.2026).

Словарь данных определяет `total_debt` как «кратко- и долгосрочный
долг». Тег `LongTermDebt` — долгосрочный долг вместе с текущей частью, но
без коммерческих бумаг и прочих краткосрочных займов: у AAPL за FY2024
96,66 млрд против 106,63 млрд долга в 10-K (+ 9,97 млрд коммерческих
бумаг), у MSFT 44,94 против 51,63. Краткосрочная часть берётся по тегу
(`ShortTermBorrowings` — он включает бумаги; иначе `CommercialPaper`) на
ту же дату баланса и прибавляется только к `LongTermDebt`: объединённый
тег (`DebtLongtermAndShorttermCombinedAmount`) её уже содержит.
"""
from __future__ import annotations

from typing import Optional

LONG_TERM_TAG = "us-gaap:LongTermDebt"
# порядок — приоритет: ShortTermBorrowings включает коммерческие бумаги
SHORT_TERM_TAGS = ("us-gaap:ShortTermBorrowings", "us-gaap:CommercialPaper")


def short_term_at(rows, end: str) -> Optional[tuple]:
    """(значение, fact_id, тег) краткосрочного долга на дату баланса, или
    None. rows — (value, end, currency, fact_id, tag) из
    `SnapshotRepo.short_term_debt_facts`, свежая подача первой."""
    by_tag: dict[str, tuple] = {}
    for value, row_end, _currency, fact_id, tag in rows:
        if row_end != end or tag in by_tag:
            continue
        try:
            by_tag[tag] = (float(value), fact_id, tag)
        except (TypeError, ValueError):
            continue
    for tag in SHORT_TERM_TAGS:
        if tag in by_tag:
            return by_tag[tag]
    return None


def adds_short_term(debt_tag: Optional[str]) -> bool:
    """Краткосрочный долг прибавляется только к LongTermDebt."""
    return debt_tag == LONG_TERM_TAG
