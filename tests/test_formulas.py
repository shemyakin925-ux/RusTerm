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


# ── Рост и котировки (data-dictionary.md §3, v1). Числа синтетические ──

from rusterm.formulas import (  # noqa: E402
    cagr,
    dividend_factor,
    drawdown,
    price_adj,
    split_factor,
    total_return,
)


def test_cagr_positive_case():
    assert cagr(100.0, 121.0, 2.0) == (pytest.approx(0.10), None)


def test_cagr_all_null_cases():
    """Четыре случая null из словаря §3 «Рост»."""
    assert cagr(0.0, 10.0, 2.0) == (None, "negative_denominator")   # V_start <= 0
    assert cagr(-5.0, 10.0, 2.0) == (None, "negative_denominator")  # V_start <= 0
    assert cagr(10.0, -1.0, 2.0) == (None, "negative_denominator")  # V_end < 0
    assert cagr(10.0, 20.0, 0.0) == (None, "denominator_zero")      # n <= 0
    assert cagr(None, 20.0, 2.0) == (None, "missing_data")


def test_price_adj_dividend_series():
    """Ключевой тест ТЗ (P5): дивидендная бумага. total_return по
    price_adj больше, чем по price_close, ровно на дивидендную
    составляющую. Синтетика: close 100 → 99, дивиденд D=1 с ex-date
    во второй день, цена перед ex-date 100 → f = 1 - 1/100 = 0.99."""
    prices = [("2024-05-20", 100.0), ("2024-05-21", 99.0)]
    events = [("2024-05-21", dividend_factor(1.0, 100.0))]
    assert events[0][1] == pytest.approx(0.99)

    adj = price_adj(prices, events)
    # День ex-date уже торгуется по скорректированной цене — его close
    # не умножается на его же коэффициент.
    assert adj[1] == ("2024-05-21", pytest.approx(99.0))
    assert adj[0][1] == pytest.approx(99.0)  # 100 * 0.99

    tr_close, _ = total_return(prices)
    tr_adj, _ = total_return(adj)
    # По close: -1%; по adj: 0%; разница ровно дивидендная составляющая
    assert tr_close == pytest.approx(-0.01)
    assert tr_adj == pytest.approx(0.0)
    assert tr_adj - tr_close == pytest.approx(0.01)


def test_price_adj_split_series():
    """Сплит 1:k, k=2: f = 1/2. По close бумага «упала» вдвое,
    по price_adj доходность нулевая."""
    prices = [("2024-06-03", 100.0), ("2024-06-04", 50.0)]
    events = [("2024-06-04", split_factor(2.0))]
    adj = price_adj(prices, events)
    assert adj[0][1] == pytest.approx(50.0)
    tr_close, _ = total_return(prices)
    tr_adj, _ = total_return(adj)
    assert tr_close == pytest.approx(-0.5)
    assert tr_adj == pytest.approx(0.0)


def test_price_adj_multiple_events_multiply():
    prices = [("2024-01-10", 100.0), ("2024-01-11", 45.0)]
    events = [
        ("2024-01-11", dividend_factor(1.0, 100.0)),  # 0.99
        ("2024-01-11", split_factor(2.0)),            # 0.5
    ]
    adj = price_adj(prices, events)
    assert adj[0][1] == pytest.approx(100.0 * 0.99 * 0.5)


def test_total_return_and_drawdown_edges():
    assert total_return([("d", 100.0)]) == (None, "missing_data")
    assert total_return([]) == (None, "missing_data")
    assert drawdown([]) == (None, "missing_data")

    series = [("t0", 100.0), ("t1", 120.0), ("t2", 90.0), ("t3", 110.0)]
    worst, reason = drawdown(series)
    assert reason is None
    assert worst == pytest.approx(90.0 / 120.0 - 1.0)  # -0.25
    m = calculate_measure("drawdown", prices_adj=series)
    assert m.scope == "instrument"
    assert m.value == pytest.approx(-0.25)


# ── BACKLOG B5: порядок корректировок не влияет на скорректированный ряд ─
def test_price_adj_split_and_dividend_order_independent():
    """Сплит и дивиденд на разных датах, события в любом порядке,
    дают один и тот же ряд price_adj (умножение коммутативно; float
    сравниваем приближённо)."""
    from rusterm.formulas import (
        dividend_factor,
        price_adj,
        split_factor,
    )
    prices = [("2024-01-05", 100.0), ("2024-02-05", 101.0),
              ("2024-03-05", 50.0), ("2024-04-05", 49.0)]
    split = ("2024-03-01", split_factor(2.0))            # сплит 1:2 → f=0.5
    dividend = ("2024-04-01", dividend_factor(1.0, 49.5))  # f = 1 - 1/49.5

    one_order = price_adj(prices, [split, dividend])
    other_order = price_adj(prices, [dividend, split])
    reverse = price_adj(prices, [split, dividend][::-1])

    for (d1, v1), (d2, v2) in zip(one_order, other_order):
        assert d1 == d2
        assert v1 == pytest.approx(v2)
    # до событий множители равны 1; после последнего события — оба
    assert one_order[0][1] == pytest.approx(100.0)
    assert one_order[-1][1] == pytest.approx(
        49.0 * split_factor(2.0) * dividend_factor(1.0, 49.5))
