"""Golden-file И9: движок формул на синтетическом двухклассовом эмитенте.

Эталон выписан вручную из арифметики входов (data-dictionary.md §3, v1),
не снят с вывода кода. Числа входов синтетические.

Синтетический эмитент «Golden Corp», классы A и B:
  класс A: price_close 100, shares_outstanding 10   -> cap 1000
  класс B: price_close 40,  shares_outstanding 25   -> cap 1000
  total_debt 900, cash 300, st_investments 100,
  minority_interest 50, preferred_equity 200 (префы НЕ отдельный класс)
  net_income кварталы [110, 90, 100, 100]  -> TTM 400
  revenue кварталы  [500, 500, 500, 500]   -> TTM 2000
  ebitda_ttm = operating_income 700 + d_and_a 100 = 800
"""
from __future__ import annotations

import pytest

from rusterm.formulas import (
    calculate_measure,
    enterprise_value,
    market_cap_per_class,
    market_cap_total,
    ttm,
)

# ── Входы (синтетические, см. модульную шапку) ──────────────────────────
PRICE_A, SHARES_A = 100.0, 10.0
PRICE_B, SHARES_B = 40.0, 25.0
DEBT, CASH, STINV, MINORITY, PREF = 900.0, 300.0, 100.0, 50.0, 200.0
NI_QUARTERS = [110.0, 90.0, 100.0, 100.0]
REV_QUARTERS = [500.0, 500.0, 500.0, 500.0]
OPERATING_INCOME, D_AND_A = 700.0, 100.0

# ── Эталон, выписанный руками ───────────────────────────────────────────
GOLDEN = {
    "cap_a": 1000.0,                      # 100 * 10
    "cap_b": 1000.0,                      # 40 * 25
    "market_cap_total": 2000.0,           # 1000 + 1000
    "ttm_net_income": 400.0,              # 110+90+100+100
    "ttm_revenue": 2000.0,                # 500*4
    "ev": 2750.0,                         # 2000+900-300-100+50+200
    "pe": 5.0,                            # 2000/400
    "ps": 1.0,                            # 2000/2000
    "ev_ebitda": 3.4375,                  # 2750/800
    "net_margin": 0.2,                    # 400/2000
}


def test_golden_ttm():
    assert ttm(NI_QUARTERS) == (GOLDEN["ttm_net_income"], None)
    assert ttm(REV_QUARTERS) == (GOLDEN["ttm_revenue"], None)
    # три квартала — TTM нет, а не частичная сумма
    assert ttm(NI_QUARTERS[:3]) == (None, "missing_data")
    assert ttm([100.0, None, 100.0, 100.0]) == (None, "missing_data")


def test_golden_valuation_chain():
    cap_a, r1 = market_cap_per_class(PRICE_A, SHARES_A)
    cap_b, r2 = market_cap_per_class(PRICE_B, SHARES_B)
    assert (cap_a, r1) == (GOLDEN["cap_a"], None)
    assert (cap_b, r2) == (GOLDEN["cap_b"], None)

    total, r3 = market_cap_total([cap_a, cap_b])
    assert (total, r3) == (GOLDEN["market_cap_total"], None)

    ev, r4 = enterprise_value(total, DEBT, CASH, STINV, MINORITY, PREF,
                              preferred_is_separate_class=False)
    assert (ev, r4) == (GOLDEN["ev"], None)

    ni_ttm, _ = ttm(NI_QUARTERS)
    rev_ttm, _ = ttm(REV_QUARTERS)
    m_pe = calculate_measure("pe", market_cap_total=total, net_income_ttm=ni_ttm)
    m_ps = calculate_measure("ps", market_cap_total=total, revenue_ttm=rev_ttm)
    m_evebitda = calculate_measure("ev_ebitda", ev=ev,
                                   ebitda_ttm=OPERATING_INCOME + D_AND_A)
    m_margin = calculate_measure("net_margin", net_income=ni_ttm,
                                 revenue=rev_ttm)

    assert m_pe.value == pytest.approx(GOLDEN["pe"])
    assert m_ps.value == pytest.approx(GOLDEN["ps"])
    assert m_evebitda.value == pytest.approx(GOLDEN["ev_ebitda"])
    assert m_margin.value == pytest.approx(GOLDEN["net_margin"])

    # уровень расчёта: оценочные — instrument, фундаментальные — issuer
    assert m_pe.scope == "instrument"
    assert m_ps.scope == "instrument"
    assert m_evebitda.scope == "instrument"
    assert m_margin.scope == "issuer"


def test_golden_all_values_present_and_reasons_none():
    """Полная цепочка без пропусков: ни одна мера не должна оказаться null."""
    for m in (
        calculate_measure("pe", market_cap_total=GOLDEN["market_cap_total"],
                          net_income_ttm=GOLDEN["ttm_net_income"]),
        calculate_measure("pb", market_cap_total=GOLDEN["market_cap_total"],
                          total_equity=1250.0),  # эталон: 2000/1250 = 1.6
        calculate_measure("ps", market_cap_total=GOLDEN["market_cap_total"],
                          revenue_ttm=GOLDEN["ttm_revenue"]),
    ):
        assert m.value is not None
        assert m.null_reason is None
        assert m.method_version == "v1"


# ── BACKLOG B4: второй golden-эмитент — префы отдельным классом ─────────
# Синтетический эмитент «Preferred Corp», классы A, B и префы P:
#   класс A: price 50, shares 8   -> cap 400
#   класс B: price 20, shares 30  -> cap 600
#   класс P (префы): price 100, shares 2 -> cap 200 — ВХОДИТ в total
#   total_debt 500, cash 200, st_investments 50, minority_interest 30,
#   preferred_equity (по балансу) 250
# EV = 1200 + 500 - 200 - 50 + 30 + 0 = 1480:
# префы уже в market_cap_total отдельным классом — повторно НЕ добавляются.
# Промах правила (двойной счёт) дал бы 1730.
PRICE_A2, SHARES_A2 = 50.0, 8.0
PRICE_B2, SHARES_B2 = 20.0, 30.0
PRICE_P2, SHARES_P2 = 100.0, 2.0
DEBT2, CASH2, STINV2, MINORITY2, PREF2 = 500.0, 200.0, 50.0, 30.0, 250.0

GOLDEN2 = {
    "cap_a": 400.0,    # 50 * 8
    "cap_b": 600.0,    # 20 * 30
    "cap_p": 200.0,    # 100 * 2
    "market_cap_total": 1200.0,  # 400 + 600 + 200
    "ev": 1480.0,      # 1200 + 500 - 200 - 50 + 30 + 0 (префы уже в cap)
}


def test_golden2_multiclass_cap_with_preferred_class():
    cap_a, r1 = market_cap_per_class(PRICE_A2, SHARES_A2)
    cap_b, r2 = market_cap_per_class(PRICE_B2, SHARES_B2)
    cap_p, r3 = market_cap_per_class(PRICE_P2, SHARES_P2)
    assert (cap_a, r1) == (GOLDEN2["cap_a"], None)
    assert (cap_b, r2) == (GOLDEN2["cap_b"], None)
    assert (cap_p, r3) == (GOLDEN2["cap_p"], None)

    total, r4 = market_cap_total([cap_a, cap_b, cap_p])
    assert (total, r4) == (GOLDEN2["market_cap_total"], None)

    # неполный многоклассовый список — не сумма, а missing_data
    assert market_cap_total([cap_a, None, cap_p]) == (None, "missing_data")


def test_golden2_ev_preferred_not_double_counted():
    total = GOLDEN2["market_cap_total"]
    ev, reason = enterprise_value(total, DEBT2, CASH2, STINV2, MINORITY2,
                                  PREF2, preferred_is_separate_class=True)
    assert (ev, reason) == (GOLDEN2["ev"], None)
    assert ev != 1730.0, "префы посчитаны дважды"

    # контраст: те же входы, но префы НЕ отдельный класс — 250 входят в ev
    ev_alt, _ = enterprise_value(total, DEBT2, CASH2, STINV2, MINORITY2,
                                 PREF2, preferred_is_separate_class=False)
    assert ev_alt == pytest.approx(1730.0)  # 1480 + 250
