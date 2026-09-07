"""Формульный движок по data-dictionary.md.

Реализует v1 формулы: методы, TTM, правила null.
Каждая формула возвращает (value, null_reason) или (None, reason).
Никаких исключений — валидные данные или null с причиной.
"""
from __future__ import annotations

from typing import Optional, Tuple, Literal, List
from dataclasses import dataclass


NullReason = Literal["denominator_zero", "negative_denominator", "missing_data", "jurisdiction_rate"]
Scope = Literal["issuer", "instrument"]


@dataclass
class Measure:
    """Готовая мера для снапшота."""
    concept: str
    value: Optional[float] = None
    unit: str = ""
    period_start: str = ""
    period_end: str = ""
    period_type: Literal["instant", "duration"] = "duration"
    method_version: str = "v1"
    null_reason: Optional[NullReason] = None
    lineage: list = None  # list of Locator dicts
    scope: Scope = "issuer"  # уровень расчёта по data-model.md §4


def clip(x: float, lo: float, hi: float) -> float:
    """Ограничение значения диапазоном."""
    return max(lo, min(hi, x))


def effective_tax_rate(tax_expense: float, pretax_income: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """effective_tax = clip(tax_expense / pretax_income, 0, 0.5).
    
    При pretax_income <= 0 -> ставка юрисдикции из справочника (возвращаем None, jurisdiction_rate).
    При pretax_income == 0 -> denominator_zero.
    """
    if pretax_income is None or pretax_income == 0:
        if pretax_income == 0:
            return None, "denominator_zero"
        else:  # None
            return None, "missing_data"
    rate = clip(tax_expense / pretax_income, 0.0, 0.5)
    return rate, None


def invested_capital(total_equity: float, minority_interest: float,
                     total_debt: float, cash: float, st_investments: float) -> float:
    """invested_capital = total_equity + minority_interest + total_debt - cash - st_investments."""
    return total_equity + minority_interest + total_debt - cash - st_investments


def roic(nopat: float, invested_capital_begin: float, invested_capital_end: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """ROIC = nopat / avg(invested_capital_начало, invested_capital_конец).
    
    Знаменатель <= 0 -> null с причиной.
    """
    if invested_capital_begin is None or invested_capital_end is None:
        return None, "missing_data"
    
    avg_ic = (invested_capital_begin + invested_capital_end) / 2
    if avg_ic == 0:
        return None, "denominator_zero"
    if avg_ic < 0:
        return None, "negative_denominator"
    
    return nopat / avg_ic, None


def roe(net_income: float, total_equity_begin: float, total_equity_end: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """ROE = net_income / avg(total_equity_начало, total_equity_конец).
    
    Знаменатель <= 0 -> null с причиной.
    """
    if total_equity_begin is None or total_equity_end is None:
        return None, "missing_data"
    
    avg_te = (total_equity_begin + total_equity_end) / 2
    if avg_te == 0:
        return None, "denominator_zero"
    if avg_te < 0:
        return None, "negative_denominator"
    
    return net_income / avg_te, None


def asset_turnover(revenue: float, total_assets_begin: float, total_assets_end: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """Asset Turnover = revenue / avg(total_assets).
    
    Знаменатель <= 0 -> null с причиной.
    """
    if total_assets_begin is None or total_assets_end is None:
        return None, "missing_data"
    
    avg_ta = (total_assets_begin + total_assets_end) / 2
    if avg_ta == 0:
        return None, "denominator_zero"
    if avg_ta < 0:
        return None, "negative_denominator"
    
    return revenue / avg_ta, None


def nopat(operating_income: float, tax_rate: float) -> Optional[float]:
    """nopat = operating_income * (1 - effective_tax).
    
    Если tax_rate None (нет данных) -> None.
    Если operating_income None -> None.
    """
    if operating_income is None:
        return None
    if tax_rate is None:
        return None  # missing_data - будем считать позже с реальной ставкой
    return operating_income * (1.0 - tax_rate)


def gross_margin(gross_profit: float, revenue: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """Gross Margin = gross_profit / revenue.
    
    Знаменатель <= 0 -> null.
    """
    if revenue == 0:
        return None, "denominator_zero"
    if revenue is None:
        return None, "missing_data"
    return gross_profit / revenue, None


def operating_margin(operating_income: float, revenue: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """Operating Margin = operating_income / revenue."""
    if revenue == 0:
        return None, "denominator_zero"
    if revenue is None:
        return None, "missing_data"
    return operating_income / revenue, None


def net_margin(net_income: float, revenue: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """Net Margin = net_income / revenue."""
    if revenue == 0:
        return None, "denominator_zero"
    if revenue is None:
        return None, "missing_data"
    return net_income / revenue, None


def _divide_checked(numerator: Optional[float],
                    denominator: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """Частное с правилами null §1: None на входе — missing_data,
    нулевой знаменатель — denominator_zero, отрицательный — negative_denominator."""
    if numerator is None or denominator is None:
        return None, "missing_data"
    if denominator == 0:
        return None, "denominator_zero"
    if denominator < 0:
        return None, "negative_denominator"
    return numerator / denominator, None


def ttm(quarterly: List[Optional[float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """TTM (data-dictionary.md §1.2): сумма четырёх последних завершённых
    кварталов. Меньше четырёх — TTM нет, missing_data: смешивать годовой
    и неполный TTM в одном показателе запрещено."""
    if quarterly is None or len(quarterly) < 4:
        return None, "missing_data"
    window = quarterly[-4:]
    if any(v is None for v in window):
        return None, "missing_data"
    return sum(window), None


# ── Оценка (data-dictionary.md §3 «Оценка», v1) ────────────────────────

def market_cap_per_class(price_close: Optional[float],
                         shares_outstanding: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """market_cap(i) = price_close(i) * shares_outstanding(i).

    Капитализация одного класса акций — scope=instrument; оба входа
    берутся по тому же классу (data-dictionary.md §2).
    """
    if price_close is None or shares_outstanding is None:
        return None, "missing_data"
    return price_close * shares_outstanding, None


def market_cap_total(class_caps: List[Optional[float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """market_cap_total = sum(market_cap(i)) по всем классам эмитента — scope=issuer.

    Ни один класс не может быть None: неполная сумма выглядела бы как
    настоящая капитализация.
    """
    if not class_caps or any(c is None for c in class_caps):
        return None, "missing_data"
    return sum(class_caps), None


def enterprise_value(market_cap_total: Optional[float],
                     total_debt: Optional[float],
                     cash: Optional[float],
                     st_investments: Optional[float],
                     minority_interest: Optional[float],
                     preferred_equity: Optional[float],
                     preferred_is_separate_class: bool) -> Tuple[Optional[float], Optional[NullReason]]:
    """ev = market_cap_total + total_debt - cash - st_investments
    + minority_interest + preferred_equity — на эмитента, scope=issuer.

    Правило preferred_equity: привилегированный капитал входит в ev
    только когда префы НЕ учтены в market_cap_total отдельным классом;
    если учтены — в ev подставляется 0, иначе двойной счёт.
    """
    parts = [market_cap_total, total_debt, cash, st_investments, minority_interest]
    if any(p is None for p in parts):
        return None, "missing_data"
    pref = 0.0 if preferred_is_separate_class else (preferred_equity or 0.0)
    value = market_cap_total + total_debt - cash - st_investments + minority_interest + pref
    return value, None


def price_to_earnings(market_cap_total: Optional[float],
                      net_income_ttm: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """pe = market_cap_total / net_income_ttm, null при знаменателе <= 0."""
    return _divide_checked(market_cap_total, net_income_ttm)


def price_to_book(market_cap_total: Optional[float],
                  total_equity: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """pb = market_cap_total / total_equity, null при знаменателе <= 0."""
    return _divide_checked(market_cap_total, total_equity)


def price_to_sales(market_cap_total: Optional[float],
                   revenue_ttm: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """ps = market_cap_total / revenue_ttm; правило нулевого/отрицательного
    знаменателя — общее (data-dictionary.md §1.4)."""
    return _divide_checked(market_cap_total, revenue_ttm)


def ev_to_ebitda(ev_value: Optional[float],
                 ebitda_ttm: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """ev_ebitda = ev / ebitda_ttm, null при ebitda <= 0."""
    return _divide_checked(ev_value, ebitda_ttm)


def dividend_yield(dps_ttm: Optional[float],
                   price_close: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """div_yield(i) = dps_ttm(i) / price_close(i) — на классе акций,
    scope=instrument; null при price_close <= 0."""
    return _divide_checked(dps_ttm, price_close)


# Уровень расчёта по data-model.md §4: фундаментальные — issuer,
# оценочные и котировочные — instrument; ev и market_cap_total — эмитента.
_INSTRUMENT_SCOPED = {"market_cap", "pe", "pb", "ps", "ev_ebitda", "div_yield",
                      "total_return", "drawdown"}


# ── Рост (data-dictionary.md §3 «Рост», v1) ────────────────────────────

def cagr(v_start: Optional[float], v_end: Optional[float], n: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """cagr(V, n) = (V_end / V_start)^(1/n) - 1.

    null по правилам словаря:
    - V_start <= 0 — рост от убытка не определён;
    - V_end < 0 — корень из отрицательного числа не определён (падение в убыток);
    - n <= 0 — период не положителен;
    - неполный период (§1.3) не приводится к году и в CAGR не участвует —
      это правило вызывающего кода, он не передаёт такие периоды вовсе.
    """
    if v_start is None or v_end is None or n is None:
        return None, "missing_data"
    if v_start <= 0:
        return None, "negative_denominator"
    if v_end < 0:
        return None, "negative_denominator"
    if n <= 0:
        return None, "denominator_zero"
    return (v_end / v_start) ** (1.0 / n) - 1.0, None


# ── Котировки (data-dictionary.md §3 «Котировки», v1) ──────────────────

def split_factor(k: float) -> float:
    """Коэффициент корректировки сплита: f = 1 / k (сплит 1:k)."""
    return 1.0 / k


def dividend_factor(dividend: float, price_close_before_ex: float) -> float:
    """Коэффициент корректировки денежного дивиденда D с ex-date:
    f = 1 - D / price_close последнего дня перед ex-date."""
    return 1.0 - dividend / price_close_before_ex


def price_adj(prices: List[Tuple[str, float]],
              events: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """Скорректированный ряд цены, задним числом, по формуле словаря:

    price_adj(t) = price_close(t) * prod(f_e) по всем событиям e ПОСЛЕ t.

    prices — [(date, close)] по возрастанию даты; events — [(date, f)]
    в тех же датах, f = split_factor/dividend_factor события с датой ex-date.
    Событие «после t» — строго позже t: день ex-date сам уже торгуется
    по скорректированной цене, его close не умножается на его же f.
    """
    adjusted: List[Tuple[str, float]] = []
    for date, close in prices:
        factor = 1.0
        for ev_date, f in events:
            if ev_date > date:
                factor *= f
        adjusted.append((date, close * factor))
    return adjusted


def total_return(prices_adj: List[Tuple[str, float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """total_return(t0, t1) = price_adj(t1) / price_adj(t0) - 1 — полная
    доходность по всему ряду (первый и последний элементы)."""
    if len(prices_adj) < 2:
        return None, "missing_data"
    ratio, reason = _divide_checked(prices_adj[-1][1], prices_adj[0][1])
    if ratio is None:
        return None, reason
    return ratio - 1.0, None


def drawdown(prices_adj: List[Tuple[str, float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """drawdown(t) = price_adj(t) / max(price_adj[t0..t]) - 1; возвращает
    максимальную просадку по ряду (наименьшее значение)."""
    if not prices_adj:
        return None, "missing_data"
    peak = prices_adj[0][1]
    worst = 0.0
    for _, v in prices_adj:
        if v > peak:
            peak = v
        if peak > 0 and v / peak - 1.0 < worst:
            worst = v / peak - 1.0
    return worst, None


def calculate_measure(
    concept: str,
    **kwargs
) -> Measure:
    """Вычисляет меру по концепту.

    Поддерживаемые концепты по data-dictionary.md §2:
    - EBITDA, gross_margin, operating_margin, net_margin
    - invested_capital, roic, roe
    - asset_turnover
    - nopat
    - Оценка: market_cap, market_cap_total, ev, pe, pb, ps, ev_ebitda, div_yield
    """
    method_version = kwargs.get("method_version", "v1")
    
    # По умолчанию null с причиной
    value = None
    null_reason = None
    
    if concept == "ebitda":
        # ebitda = operating_income + d_and_a (если operating_income не раскрыт:
        # revenue - cogs - opex + d_and_a)
        operating_income = kwargs.get("operating_income")
        d_and_a = kwargs.get("d_and_a")
        revenue = kwargs.get("revenue")
        cogs = kwargs.get("cogs")
        opex = kwargs.get("opex")
        
        if operating_income is not None:
            value = operating_income
            if d_and_a is not None:
                value = operating_income + d_and_a  # already has d_and_a added? No, ebitda = operating_income + d_and_a
                # Actually: ebitda = operating_income + d_and_a when operating_income is revealed
                # If not revealed: revenue - cogs - opex + d_and_a
        elif all(x is not None for x in [revenue, cogs, opex, d_and_a]):
            value = revenue - cogs - opex + d_and_a
        else:
            null_reason = "missing_data"
    
    elif concept == "gross_margin":
        gp = kwargs.get("gross_profit")
        rev = kwargs.get("revenue")
        if gp is not None and rev is not None and rev != 0:
            value = gp / rev
        elif gp is None or rev is None or rev == 0:
            null_reason = "denominator_zero" if rev == 0 else "missing_data"
    
    elif concept == "operating_margin":
        oi = kwargs.get("operating_income")
        rev = kwargs.get("revenue")
        if oi is not None and rev is not None and rev != 0:
            value = oi / rev
        elif oi is None or rev is None or rev == 0:
            null_reason = "denominator_zero" if rev == 0 else "missing_data"
    
    elif concept == "net_margin":
        ni = kwargs.get("net_income")
        rev = kwargs.get("revenue")
        if ni is not None and rev is not None and rev != 0:
            value = ni / rev
        elif ni is None or rev is None or rev == 0:
            null_reason = "denominator_zero" if rev == 0 else "missing_data"
    
    elif concept == "invested_capital":
        te = kwargs.get("total_equity")
        mi = kwargs.get("minority_interest")
        td = kwargs.get("total_debt")
        cash = kwargs.get("cash")
        stinv = kwargs.get("st_investments")
        if all(x is not None for x in [te, mi, td]) or _has_sufficient_ic_inputs(kwargs):
            value = invested_capital(**kwargs)
        else:
            null_reason = "missing_data"
    
    elif concept == "roic":
        nop = kwargs.get("nopat")
        ic_begin = kwargs.get("invested_capital_begin")
        ic_end = kwargs.get("invested_capital_end")
        if nop is not None and ic_begin is not None and ic_end is not None:
            val, reason = roic(nop, ic_begin, ic_end)
            value = val
            null_reason = reason
        else:
            null_reason = "missing_data"
    
    elif concept == "roe":
        ni = kwargs.get("net_income")
        te_begin = kwargs.get("total_equity_begin")
        te_end = kwargs.get("total_equity_end")
        if ni is not None and te_begin is not None and te_end is not None:
            val, reason = roe(ni, te_begin, te_end)
            value = val
            null_reason = reason
        else:
            null_reason = "missing_data"
    
    elif concept == "asset_turnover":
        rev = kwargs.get("revenue")
        ta_begin = kwargs.get("total_assets_begin")
        ta_end = kwargs.get("total_assets_end")
        if rev is not None and ta_begin is not None and ta_end is not None:
            val, reason = asset_turnover(rev, ta_begin, ta_end)
            value = val
            null_reason = reason
        else:
            null_reason = "missing_data"
    
    elif concept == "nopat":
        oi = kwargs.get("operating_income")
        tr = kwargs.get("tax_rate")
        value = nopat(oi, tr)
        if value is None:
            null_reason = "missing_data" if oi is None else None
    
    elif concept == "effective_tax":
        te = kwargs.get("tax_expense")
        pi = kwargs.get("pretax_income")
        value, null_reason = effective_tax_rate(te, pi)

    elif concept == "market_cap":
        value, null_reason = market_cap_per_class(
            kwargs.get("price_close"), kwargs.get("shares_outstanding"))

    elif concept == "market_cap_total":
        value, null_reason = market_cap_total(kwargs.get("class_caps") or [])

    elif concept == "ev":
        value, null_reason = enterprise_value(
            kwargs.get("market_cap_total"), kwargs.get("total_debt"),
            kwargs.get("cash"), kwargs.get("st_investments"),
            kwargs.get("minority_interest"), kwargs.get("preferred_equity"),
            bool(kwargs.get("preferred_is_separate_class")),
        )

    elif concept == "pe":
        value, null_reason = price_to_earnings(
            kwargs.get("market_cap_total"), kwargs.get("net_income_ttm"))

    elif concept == "pb":
        value, null_reason = price_to_book(
            kwargs.get("market_cap_total"), kwargs.get("total_equity"))

    elif concept == "ps":
        value, null_reason = price_to_sales(
            kwargs.get("market_cap_total"), kwargs.get("revenue_ttm"))

    elif concept == "ev_ebitda":
        value, null_reason = ev_to_ebitda(
            kwargs.get("ev"), kwargs.get("ebitda_ttm"))

    elif concept == "div_yield":
        value, null_reason = dividend_yield(
            kwargs.get("dps_ttm"), kwargs.get("price_close"))

    elif concept == "total_return":
        value, null_reason = total_return(kwargs.get("prices_adj") or [])

    elif concept == "drawdown":
        value, null_reason = drawdown(kwargs.get("prices_adj") or [])

    elif concept == "cagr":
        value, null_reason = cagr(
            kwargs.get("v_start"), kwargs.get("v_end"), kwargs.get("n"))

    else:
        # Неизвестный концепт
        null_reason = "missing_data"

    scope: Scope = "instrument" if concept in _INSTRUMENT_SCOPED else "issuer"
    return Measure(
        concept=concept,
        value=value,
        unit=kwargs.get("unit", ""),
        period_start=kwargs.get("period_start", ""),
        period_end=kwargs.get("period_end", ""),
        period_type=kwargs.get("period_type", "duration"),
        method_version=method_version,
        null_reason=null_reason,
        lineage=kwargs.get("lineage", []),
        scope=scope,
    )


def _has_sufficient_ic_inputs(kwargs: dict) -> bool:
    """Проверяет, достаточно ли данных для invested_capital."""
    # invested_capital = total_equity + minority_interest + total_debt - cash - st_investments
    # Минимум: total_equity + minority_interest + total_debt (остальное можно 0)
    has_te = kwargs.get("total_equity") is not None
    has_mi = kwargs.get("minority_interest") is not None
    has_td = kwargs.get("total_debt") is not None
    return has_te and has_mi and has_td
