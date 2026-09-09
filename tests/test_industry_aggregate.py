"""TASK-17 E1: агрегат сектора — чистая функция с названным методом.

Квартили считаются statistics.quantiles(method="inclusive") — линейная
интерполяция между порядковыми статистиками; ожидания в тесте —
литералы, вычисленные вручную, а не вызовом той же функции:
- девять значений 1..9: p25=3.0, median=5.0, p75=7.0 (позиции 2, 4, 6);
- восемь значений 1..8: p25=1.75 (1 + 0.75), median=4.5, p75=6.25
  (интерполяция между порядковыми статистиками).
Null исключается и считается; 7 вкладчиков — peer_set_too_small (I6);
неподтверждённый набор — peer_set_not_confirmed.
"""
from __future__ import annotations

from rusterm.core.industry.aggregate import (
    METHOD_VERSION,
    sector_aggregate,
)


def test_nine_values_quartiles_are_hand_computed_literals():
    values = [(f"in-{i}", float(i)) for i in range(1, 10)]  # 1..9
    agg = sector_aggregate("net_margin", values, verified=True)
    assert agg.p25 == repr(3.0)
    assert agg.median == repr(5.0)
    assert agg.p75 == repr(7.0)
    assert agg.n == 9
    assert agg.null_reason is None
    assert agg.method_version == METHOD_VERSION == "industry.v1"


def test_eight_values_exercise_the_interpolation():
    values = [(f"in-{i}", float(i)) for i in range(1, 9)]  # 1..8
    agg = sector_aggregate("net_margin", values, verified=True)
    assert agg.p25 == repr(1.75), agg.p25
    assert agg.median == repr(4.5)
    assert agg.p75 == repr(6.25)
    assert agg.n == 8


def test_nulls_are_excluded_and_counted_not_zero():
    values = [(f"in-{i}", float(i)) for i in range(11)]  # 11 вкладчиков
    values += [(f"in-empty-{i}", None) for i in range(3)]
    agg = sector_aggregate("operating_margin", values, verified=True)
    assert agg.n == 11, "null приравнялся к вкладчику"
    assert agg.median == repr(5.0)  # медиана одиннадцати значений 0..10
    assert agg.reason_counts == {"no_value": 3}


def test_seven_contributors_yield_peer_set_too_small():
    values = [(f"in-{i}", float(i)) for i in range(7)]
    agg = sector_aggregate("net_margin", values, verified=True)
    assert agg.p25 is None and agg.median is None and agg.p75 is None
    assert agg.n == 0
    assert agg.null_reason == "peer_set_too_small"


def test_unverified_set_yields_peer_set_not_confirmed():
    values = [(f"in-{i}", float(i)) for i in range(12)]
    agg = sector_aggregate("net_margin", values, verified=False)
    assert agg.median is None
    assert agg.n == 0
    assert agg.null_reason == "peer_set_not_confirmed"
    # участники с пустыми значениями остались в счётчике причин
    values_with_null = values + [("in-x", None)]
    agg = sector_aggregate("net_margin", values_with_null, verified=False)
    assert agg.reason_counts == {"no_value": 1}


def test_reason_is_in_the_b15_vocabulary():
    from rusterm.reasons import is_known_reason
    assert is_known_reason("peer_set_too_small")
