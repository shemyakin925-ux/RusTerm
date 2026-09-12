"""ТЗ-23 K3: корректировка — наша функция (price_adj), вендорский
adjusted — сверка.

- золотой ряд со сплитом и дивидендом: наша серия совпадает с
  ожидаемой ТОЧНО;
- намеренное расхождение с вендором — оба числа в находке, при этом
  ни наш ряд, ни вендорская колонка в хранилище не меняются.
"""
from __future__ import annotations

import pytest

from rusterm.core.prices import our_adjusted_series, build_events
from rusterm.formulas import dividend_factor, split_factor


def _rows():
    return [
        {"date": "2024-06-03", "close": 100.0, "adjusted": None,
         "currency": "USD"},
        {"date": "2024-06-04", "close": 50.0, "adjusted": None,
         "currency": "USD"},
        {"date": "2024-06-05", "close": 50.0, "adjusted": None,
         "currency": "USD"},
    ]


def _actions():
    return [
        {"ex_date": "2024-06-04", "kind": "split", "factor": 2.0,
         "amount": None, "currency": None, "source": "twelvedata"},
        {"ex_date": "2024-06-05", "kind": "dividend", "factor": None,
         "amount": 1.0, "currency": "USD", "source": "twelvedata"},
    ]


def test_golden_series_with_split_and_dividend_exact():
    """Сплит 1:2 на 06-04 (f=0.5) и дивиденд 1 на 06-05
    (f = 1 - 1/50 = 0.98): наша серия точна до последнего знака."""
    ours, disagreements = our_adjusted_series(_rows(), _actions())
    f_div = dividend_factor(1.0, 50.0)
    expected = [
        ("2024-06-03", 100.0 * split_factor(2.0) * f_div),
        ("2024-06-04", 50.0 * f_div),
        ("2024-06-05", 50.0),
    ]
    assert ours == pytest.approx(expected)
    # вендорский adjusted в этом ряду не записан — расхождений нет
    assert disagreements == []


def test_events_use_close_before_ex_date():
    """Дивидендный коэффициент считается по close последнего дня
    ПЕРЕД ex-date; без цены перед ex-date событие не применяется."""
    events = build_events(_rows(), _actions())
    assert ("2024-06-04", split_factor(2.0)) in events
    assert events[-1] == ("2024-06-05", pytest.approx(0.98))
    lone = [{"date": "2024-06-05", "close": 50.0, "adjusted": None}]
    assert build_events(lone, [_actions()[1]]) == []


def test_deliberate_vendor_mismatch_is_reported_not_resolved(env_stub=None):
    rows = _rows()
    # вендор утверждает adjusted=60 на 06-04 — наша формула даёт 49
    rows[1]["adjusted"] = 60.0
    ours, disagreements = our_adjusted_series(rows, _actions())
    assert len(disagreements) == 1
    date, ours_value, vendor_value = disagreements[0]
    assert date == "2024-06-04"
    assert ours_value == pytest.approx(49.0)
    assert vendor_value == 60.0
    # ничто не переписано: наши close и вендорский adjusted на месте
    assert rows[1]["close"] == 50.0
    assert rows[1]["adjusted"] == 60.0
    assert ours[1] == ("2024-06-04", pytest.approx(49.0))


def test_agreements_and_disagreements_counted(env=None):
    rows = _rows()
    rows[0]["adjusted"] = 49.0   # совпадает с нашей
    rows[1]["adjusted"] = 60.0   # расходится
    ours, disagreements = our_adjusted_series(rows, _actions())
    total_days = len(ours)
    assert total_days == 3
    assert len(disagreements) == 1
    agreed = total_days - len(disagreements)
    assert agreed == 2
