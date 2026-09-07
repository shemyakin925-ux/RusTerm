"""Тесты формул «Оценка» (data-dictionary.md §3, method_version v1).

Все числа в тестах — синтетические, для арифметики формул.
"""
from __future__ import annotations

import pytest

from rusterm.formulas import (
    Measure,
    calculate_measure,
    dividend_yield,
    enterprise_value,
    market_cap_per_class,
    market_cap_total,
    price_to_book,
    price_to_earnings,
    price_to_sales,
)


# Синтетический двухклассовый эмитент:
# класс A: price 10.0 * shares 100 = cap 1000
# класс B: price 20.0 * shares 50  = cap 1000
# market_cap_total = 2000; net_income_ttm = 200
SYN_CAP_A = 1000.0
SYN_CAP_B = 1000.0
SYN_CAP_TOTAL = 2000.0
SYN_NET_INCOME = 200.0


def test_pe_same_for_both_classes():
    """P/E классов A и B одного эмитента совпадают: знаменатель — величина
    эмитента, числитель — market_cap_total, а не капитализация класса."""
    cap_a, reason_a = market_cap_per_class(10.0, 100.0)
    cap_b, reason_b = market_cap_per_class(20.0, 50.0)
    assert (cap_a, reason_a) == (SYN_CAP_A, None)
    assert (cap_b, reason_b) == (SYN_CAP_B, None)
    total, reason = market_cap_total([cap_a, cap_b])
    assert (total, reason) == (SYN_CAP_TOTAL, None)

    pe_from_total = price_to_earnings(total, SYN_NET_INCOME)
    assert pe_from_total == (10.0, None)

    # Контроль замысла: P/E от капитализации одного класса дал бы 5.0,
    # и классы разошлись бы — поэтому формула принимает только total.
    pe_wrong, _ = price_to_earnings(cap_a, SYN_NET_INCOME)
    assert pe_wrong == 5.0

    m_a = calculate_measure("pe", market_cap_total=total,
                            net_income_ttm=SYN_NET_INCOME)
    m_b = calculate_measure("pe", market_cap_total=total,
                            net_income_ttm=SYN_NET_INCOME)
    assert m_a.value == m_b.value == 10.0
    assert m_a.scope == "instrument"


def test_ev_does_not_double_count_preferred():
    """preferred_equity входит в ev только если префы не учтены
    отдельным классом в market_cap_total; иначе — 0. ev в обоих случаях
    одинаков (2750), двойного счёта нет."""
    # Вариант 1: префы НЕ класс в капитализации — входят в ev деньгами.
    ev_without_class, r1 = enterprise_value(
        market_cap_total=SYN_CAP_TOTAL, total_debt=500.0, cash=100.0,
        st_investments=0.0, minority_interest=50.0, preferred_equity=300.0,
        preferred_is_separate_class=False,
    )
    assert r1 is None
    assert ev_without_class == 2000.0 + 500.0 - 100.0 + 50.0 + 300.0

    # Вариант 2: префы — отдельный класс P (кап 300) уже внутри total 2300.
    # preferred_equity игнорируется, иначе 300 считалось бы дважды.
    ev_with_class, r2 = enterprise_value(
        market_cap_total=2300.0, total_debt=500.0, cash=100.0,
        st_investments=0.0, minority_interest=50.0, preferred_equity=300.0,
        preferred_is_separate_class=True,
    )
    assert r2 is None
    assert ev_with_class == ev_without_class == 2750.0


def test_ev_scope_and_missing_inputs():
    m = calculate_measure(
        "ev", market_cap_total=SYN_CAP_TOTAL, total_debt=500.0, cash=100.0,
        st_investments=0.0, minority_interest=50.0, preferred_equity=300.0,
        preferred_is_separate_class=False,
    )
    assert m.value == 2750.0
    assert m.scope == "issuer"

    m2 = calculate_measure("ev", market_cap_total=SYN_CAP_TOTAL,
                           total_debt=None, cash=100.0, st_investments=0.0,
                           minority_interest=50.0, preferred_equity=0.0,
                           preferred_is_separate_class=False)
    assert m2.value is None
    assert m2.null_reason == "missing_data"


def test_market_cap_missing_inputs():
    assert market_cap_per_class(None, 100.0) == (None, "missing_data")
    assert market_cap_per_class(10.0, None) == (None, "missing_data")
    assert market_cap_total([1000.0, None]) == (None, "missing_data")
    assert market_cap_total([]) == (None, "missing_data")


def test_pe_null_rules():
    assert price_to_earnings(SYN_CAP_TOTAL, 0.0) == (None, "denominator_zero")
    assert price_to_earnings(SYN_CAP_TOTAL, -5.0) == (None, "negative_denominator")
    assert price_to_earnings(SYN_CAP_TOTAL, None) == (None, "missing_data")


def test_pb_and_ps():
    assert price_to_book(SYN_CAP_TOTAL, 800.0) == (2.5, None)
    assert price_to_book(SYN_CAP_TOTAL, 0.0) == (None, "denominator_zero")
    assert price_to_book(SYN_CAP_TOTAL, -1.0) == (None, "negative_denominator")

    assert price_to_sales(SYN_CAP_TOTAL, 4000.0) == (0.5, None)
    assert price_to_sales(SYN_CAP_TOTAL, 0.0) == (None, "denominator_zero")
    assert price_to_sales(SYN_CAP_TOTAL, None) == (None, "missing_data")
    m = calculate_measure("ps", market_cap_total=SYN_CAP_TOTAL,
                          revenue_ttm=4000.0)
    assert m.scope == "instrument"


def test_div_yield_per_class():
    """Дивдоходность считается на классе: dps_ttm(i) / price_close(i)."""
    assert dividend_yield(5.0, 100.0) == (0.05, None)
    assert dividend_yield(5.0, 0.0) == (None, "denominator_zero")
    assert dividend_yield(5.0, -3.0) == (None, "negative_denominator")
    assert dividend_yield(None, 100.0) == (None, "missing_data")
    m = calculate_measure("div_yield", dps_ttm=5.0, price_close=100.0)
    assert m.value == 0.05
    assert m.scope == "instrument"


def test_ev_ebitda_null_at_nonpositive_ebitda():
    from rusterm.formulas import ev_to_ebitda
    ev_value = 2750.0
    assert ev_to_ebitda(ev_value, 550.0) == (5.0, None)
    assert ev_to_ebitda(ev_value, 0.0) == (None, "denominator_zero")
    assert ev_to_ebitda(ev_value, -10.0) == (None, "negative_denominator")


def test_measure_has_scope_field():
    m = Measure(concept="revenue", value=1.0, scope="issuer")
    assert m.scope == "issuer"
    m2 = Measure(concept="price_close", value=1.0, scope="instrument")
    assert m2.scope == "instrument"
