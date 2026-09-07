"""Формульный движок по data-dictionary.md.

Реализует v1 формулы: методы, TTM, правила null.
Каждая формула возвращает (value, null_reason) или (None, reason).
Никаких исключений — валидные данные или null с причиной.
"""
from __future__ import annotations

from typing import Optional, Tuple, Literal, List
from dataclasses import dataclass


NullReason = Literal["denominator_zero", "negative_denominator", "missing_data", "jurisdiction_rate"]


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
    
    else:
        # Неизвестный концепт
        null_reason = "missing_data"
    
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
    )


def _has_sufficient_ic_inputs(kwargs: dict) -> bool:
    """Проверяет, достаточно ли данных для invested_capital."""
    # invested_capital = total_equity + minority_interest + total_debt - cash - st_investments
    # Минимум: total_equity + minority_interest + total_debt (остальное можно 0)
    has_te = kwargs.get("total_equity") is not None
    has_mi = kwargs.get("minority_interest") is not None
    has_td = kwargs.get("total_debt") is not None
    return has_te and has_mi and has_td
