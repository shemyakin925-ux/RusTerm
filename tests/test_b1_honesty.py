"""ТЗ-B1 (полоса B) B1.1: мера не подгоняет значение — перепись
«зелёных, которые не заслужили» и граничные тесты закрытых случаев.

Закрыто пять нечестных случаев (REPORT-B1, таблица переписи):
  1. nopat: tax_rate=None при живом operating_income давал (None, None)
     — ни значения, ни причины (I4); теперь missing_data.
  2. invested_capital в диспетчере: TypeError вместо отказа — и при
     нехватке cash/st_investments, и при любом лишнем kwargе;
     теперь отказ называет отсутствующие концепты (X3).
  3. gross/operating/net_margin: отрицательная выручка молча давала
     отрицательную долю; теперь negative_denominator — то же правило
     §1.4, что у pe/pb/ps (_divide_checked).
  4. drawdown: ряд неположительных цен давал молчаливый 0.0 («просадки
     нет»); теперь missing_data: nonpositive_price.
  5. ebitda: operating_income без d_and_a молча выдавался за ebitda —
     значение, заниженное на d_and_a; теперь отказ с именами нехватки.

Все числа синтетические; сеть не трогается.
"""
from __future__ import annotations

import pytest

from rusterm.formulas import (
    calculate_measure,
    drawdown,
    gross_margin,
    invested_capital,
    net_margin,
    nopat,
    operating_margin,
)


# ── 1. nopat: отказ обязан иметь причину ────────────────────────────────

def test_nopat_missing_tax_rate_has_a_reason():
    m = calculate_measure("nopat", operating_income=10.0, tax_rate=None)
    assert m.value is None
    assert m.null_reason == "missing_data"
    # живой путь не задет: настоящий ноль дохода остаётся числом
    m0 = calculate_measure("nopat", operating_income=0.0, tax_rate=0.2)
    assert m0.value == 0.0 and m0.null_reason is None


# ── 2. invested_capital: отказ вместо TypeError ─────────────────────────

def test_invested_capital_missing_cash_names_concepts():
    m = calculate_measure("invested_capital", total_equity=100.0,
                          minority_interest=5.0, total_debt=50.0)
    assert m.value is None
    assert m.null_reason == "missing_data: cash, st_investments"


def test_invested_capital_extra_kwargs_do_not_crash():
    # лишний kwarg раньше падал TypeError: unexpected keyword argument
    m = calculate_measure("invested_capital", total_equity=100.0,
                          minority_interest=5.0, total_debt=50.0,
                          cash=10.0, st_investments=0.0,
                          period_start="2024-01-01")
    assert m.value == 100.0 + 5.0 + 50.0 - 10.0 - 0.0
    assert m.null_reason is None


def test_invested_capital_all_zero_is_a_real_zero():
    # B1.3-грань: настоящий ноль отличим от отказа
    m = calculate_measure("invested_capital", total_equity=0.0,
                          minority_interest=0.0, total_debt=0.0,
                          cash=0.0, st_investments=0.0)
    assert m.value == 0.0 and m.null_reason is None
    # арифметическое ядро остаётся строгим к None — precondition в докстринге
    with pytest.raises(TypeError):
        invested_capital(100.0, 5.0, 50.0, None, 0.0)


# ── 3. маржи: отрицательный знаменатель — отказ ─────────────────────────

@pytest.mark.parametrize("fn", [gross_margin, operating_margin, net_margin])
def test_margins_negative_revenue_refused(fn):
    assert fn(50.0, -100.0) == (None, "negative_denominator")


@pytest.mark.parametrize("concept, numerator", [
    ("gross_margin", "gross_profit"),
    ("operating_margin", "operating_income"),
    ("net_margin", "net_income"),
])
def test_margins_negative_revenue_refused_in_dispatcher(concept, numerator):
    m = calculate_measure(concept, **{numerator: 50.0, "revenue": -100.0})
    assert m.value is None
    assert m.null_reason == "negative_denominator"


def test_margins_zero_and_missing_denominator_unchanged():
    assert gross_margin(50.0, 0.0) == (None, "denominator_zero")
    assert gross_margin(None, 100.0) == (None, "missing_data")
    assert gross_margin(50.0, None) == (None, "missing_data")
    # живой путь не задет
    assert gross_margin(50.0, 200.0) == (0.25, None)


# ── 4. drawdown: неположительные цены — не молчаливый ноль ──────────────

def test_drawdown_nonpositive_prices_refused():
    assert drawdown([("a", -5.0), ("b", -3.0)]) == \
        (None, "missing_data: nonpositive_price")
    assert drawdown([("a", 10.0), ("b", 0.0)]) == \
        (None, "missing_data: nonpositive_price")
    m = calculate_measure("drawdown",
                          prices_adj=[("a", -5.0), ("b", -3.0)])
    assert m.value is None
    assert m.null_reason == "missing_data: nonpositive_price"


def test_drawdown_real_zero_stays_a_number():
    # растущий ряд — настоящий «просадки нет», отличим от отказа
    assert drawdown([("a", 5.0), ("b", 6.0)]) == (0.0, None)


# ── 5. ebitda: operating_income не выдаёт себя за ebitda ────────────────

def test_ebitda_oi_without_dna_refused_with_names():
    m = calculate_measure("ebitda", operating_income=10.0, d_and_a=None)
    assert m.value is None
    assert m.null_reason == "missing_data: d_and_a"
    # oi=0 без d_and_a — та же подмена, тот же отказ (не «настоящий 0»)
    m0 = calculate_measure("ebitda", operating_income=0.0, d_and_a=None)
    assert m0.value is None
    assert m0.null_reason == "missing_data: d_and_a"


def test_ebitda_full_paths_unchanged():
    m = calculate_measure("ebitda", operating_income=10.0, d_and_a=2.0)
    assert m.value == 12.0 and m.null_reason is None
    m2 = calculate_measure("ebitda", revenue=100.0, cogs=30.0,
                           opex=20.0, d_and_a=5.0)
    assert m2.value == 55.0 and m2.null_reason is None


def test_ebitda_all_missing_names_everything():
    m = calculate_measure("ebitda")
    assert m.value is None
    assert m.null_reason == \
        "missing_data: cogs, d_and_a, operating_income, opex, revenue"
