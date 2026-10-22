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

PAIR_TAGS = ("us-gaap:LongTermDebtNoncurrent",
             "us-gaap:LongTermDebtCurrent")

# ТЗ-143 F2: вторая пара правил — XOM подаёт долгосрочный долг тегом
# с финансовым лизингом и текущую часть отдельным тегом
SECOND_PAIR_TAGS = ("us-gaap:LongTermDebtAndCapitalLeaseObligations",
                    "us-gaap:DebtCurrent")


def pair_total_at(rows, end: str) -> Optional[tuple]:
    """ТЗ-141 D2 (вердикт на REPORT-139 Q2): суммарный долг из ПАРЫ
    Noncurrent + Current на дату `end`; ТЗ-143 F2: на дате без первой
    пары — вторая (XOM: LongTermDebtAndCapitalLeaseObligations +
    DebtCurrent). Оба тега пары обязательны — половина пары долгом не
    считается. rows — (value, period_end, currency, fact_id, concept)
    из `SnapshotRepo.debt_pair_facts`, свежие первыми. Возвращает
    (сумма, конец, валюта, fact_id non-current, fact_id current) или
    None."""
    for tags in (PAIR_TAGS, SECOND_PAIR_TAGS):
        nc = cur = None
        for value, row_end, currency, fact_id, concept in rows:
            if row_end != end:
                continue
            if concept == tags[0] and nc is None:
                nc = (float(value), fact_id, currency)
            elif concept == tags[1] and cur is None:
                cur = (float(value), fact_id, currency)
        if nc is not None and cur is not None:
            return (nc[0] + cur[0], end, nc[2] or cur[2], nc[1], cur[1])
    return None


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
