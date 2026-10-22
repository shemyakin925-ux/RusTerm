"""ТЗ-143 F2: вторая пара правил долга (XOM).

XOM подаёт долг парой LongTermDebtAndCapitalLeaseObligations (включая
финансовый лизинг) + DebtCurrent — вне правил ТЗ-141 D2, из-за чего
total_debt у карточки был пуст. Вторая пара работает тем же правилом:
оба тега на одну дату баланса, половина пары долгом не считается;
первая пара сильнее там, где эмитент подаёт обе.
"""
from __future__ import annotations

from rusterm.core.debt import (SECOND_PAIR_TAGS, pair_total_at)

NC, CUR = SECOND_PAIR_TAGS
OLD_NC, OLD_CUR = ("us-gaap:LongTermDebtNoncurrent",
                   "us-gaap:LongTermDebtCurrent")
END = "2024-12-31"


def _rows(*specs):
    """[(value, end, currency, fact_id, concept)] — форма двери
    debt_pair_facts, свежие первыми. Элемент — 4-кортеж (value,
    currency, fact_id, concept) на дату END или 5-кортеж со своей
    датой второй."""
    rows = []
    for spec in specs:
        if len(spec) == 5:
            value, end, currency, fact_id, concept = spec
        else:
            value, currency, fact_id, concept = spec
            end = END
        rows.append((value, end, currency, fact_id, concept))
    return rows


def test_second_pair_sums_on_one_date():
    rows = _rows(
        (49_000, "USD", "f-xom-nc", NC),
        (4_500, "USD", "f-xom-cur", CUR),
    )
    total, end, currency, nc_id, cur_id = pair_total_at(rows, END)
    assert total == 53_500
    assert end == END and currency == "USD"
    assert (nc_id, cur_id) == ("f-xom-nc", "f-xom-cur")


def test_half_of_the_second_pair_is_not_debt():
    assert pair_total_at(_rows((49_000, "USD", "f-nc", NC)), END) is None
    assert pair_total_at(_rows((4_500, "USD", "f-cur", CUR)), END) is None


def test_first_pair_wins_when_both_are_filed():
    rows = _rows(
        (300, "USD", "f-old-nc", OLD_NC),
        (200, "USD", "f-old-cur", OLD_CUR),
        (49_000, "USD", "f-xom-nc", NC),
        (4_500, "USD", "f-xom-cur", CUR),
    )
    total, _end, _currency, nc_id, cur_id = pair_total_at(rows, END)
    assert total == 500
    assert (nc_id, cur_id) == ("f-old-nc", "f-old-cur")


def test_other_dates_and_other_rows_are_ignored():
    rows = [
        (49_000, "2023-12-31", "USD", "f-old-year", NC),
        (999, END, "USD", "f-noise", "us-gaap:SomethingElse"),
    ]
    assert pair_total_at(rows, END) is None


def test_second_pair_fills_where_the_first_has_no_date():
    """Первая пара на другой дате не мешает второй паре на своей."""
    rows = _rows(
        (300, "2023-12-31", "USD", "f-old-nc", OLD_NC),
        (200, "2023-12-31", "USD", "f-old-cur", OLD_CUR),
        (49_000, "USD", "f-xom-nc", NC),
        (4_500, "USD", "f-xom-cur", CUR),
    )
    total = pair_total_at(rows, END)[0]
    assert total == 53_500
