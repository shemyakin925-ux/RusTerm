"""Формульный движок по data-dictionary.md.

Реализует v1 формулы: методы, TTM, правила null.
Каждая формула возвращает (value, null_reason) или (None, reason).
Никаких исключений — валидные данные или null с причиной.

Правило «никаких исключений и никаких NaN» (ТЗ-82 E2, ADR-0024) держит
декоратор refuses_non_finite: вход NaN/±inf, арифметика, сошедшая в
±inf, и степень, упёршаяся в OverflowError, — всё это отказ
non_finite, а не число-призрак в базе.
"""
from __future__ import annotations

import functools
import math
from typing import Optional, Tuple, Literal, List
from dataclasses import dataclass


NullReason = Literal["denominator_zero", "negative_denominator", "missing_data", "jurisdiction_rate", "non_finite"]
Scope = Literal["issuer", "instrument"]


def _has_non_finite(value) -> bool:
    """NaN или ±inf где-то во входе, в том числе вложенном списком."""
    if isinstance(value, float) and not math.isfinite(value):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_non_finite(v) for v in value)
    return False


def _has_missing(value) -> bool:
    """None где-то во входе, в том числе вложенном списком или парой."""
    if value is None:
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_missing(v) for v in value)
    return False


def refuses_non_finite(fn):
    """ТЗ-82 E2: формула обязана вернуть отказ, если вход или частное
    нечисловые.

    Молчание стоило трёх кругов: clip() в effective_tax выдумал 0.0 из
    ≈23,8 % AMBEV (ТЗ-58 C4), и тот же класс — «мера подставляет
    значение вместо отказа» — переживает переписывание: на dd11fbd
    gross_margin(nan, 100.0) давал (nan, None), а gross_margin(1e308,
    1e-308) — (inf, None). Причина называется отдельно от missing_data
    нарочно: «данных нет» и «данные есть, но они не числа» — разные
    разговора с пользователем, и первый из них чинит пайплайн, а
    второй — источник.

    Арифметика floats в Python переводит переполнение в inf молча,
    кроме возведения в степень, которое бросает OverflowError; ловится
    и то, и другое — формула не имеет права ронять снапшот.

    Проверяет декоратор и второе молчание того же рода: формулы,
    объявленные как float, вызываются из calculate_measure с фактами,
    которых может не быть, и арифметика с None бросает TypeError. Формула
    обязана ответить missing_data; сама по себе проверка на None в
    числителе есть не везде (roic смотрит только знаменатель), а
    обещание «никаких исключений» — про все входы.
    """
    @functools.wraps(fn)
    def guarded(*args, **kwargs):
        if _has_non_finite(args) or _has_non_finite(list(kwargs.values())):
            return None, "non_finite"
        try:
            value, reason = fn(*args, **kwargs)
        except (OverflowError, ZeroDivisionError):
            return None, "non_finite"
        except TypeError:
            if _has_missing(args) or _has_missing(list(kwargs.values())):
                return None, "missing_data"
            # Без None во входах TypeError — настоящая ошибка в коде
            # формулы; глотать её значит прятать поломку под отказ.
            raise
        if value is not None and not math.isfinite(value):
            return None, "non_finite"
        return value, reason
    return guarded


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


# Единица меры — свойство формулы, а не места вызова (TASK-9 V2):
# ratio — доля; money — валюта входов; per_share — <валюта>/акция;
# count — штуки. Валюта подставляется из единицы входных фактов.
MEASURE_UNIT_KINDS: dict[str, str] = {
    "ebitda": "money",
    "gross_margin": "ratio",
    "operating_margin": "ratio",
    "net_margin": "ratio",
    "effective_tax": "ratio",
    "invested_capital": "money",
    "roic": "ratio",
    "roe": "ratio",
    "roe_incl_nci": "ratio",
    "asset_turnover": "ratio",
    "nopat": "money",
    "eps_diluted": "per_share",
    "dps": "per_share",
    "shares_diluted": "count",
    "fcf": "money",
    "interest_coverage": "ratio",
    "net_debt": "money",
    "net_debt_ebitda": "ratio",
    "invested_capital": "money",
    "roic": "ratio",
    "fcf_yield": "ratio",
    "market_cap": "money",
    "market_cap_total": "money",
    "ev": "money",
    "cagr": "ratio",
    "total_return": "ratio",
    "drawdown": "ratio",
    "price_adj": "money",
    "hhi": "index",
    "ev": "money",
    "pe": "ratio",
    "pb": "ratio",
    "ps": "ratio",
    "ev_ebitda": "ratio",
    "div_yield": "ratio",
}


def measure_unit(concept: str, input_unit: str = "") -> str:
    kind = MEASURE_UNIT_KINDS.get(concept, "ratio")
    if kind == "ratio":
        return "ratio"
    if kind == "money":
        return input_unit or ""
    if kind == "per_share":
        return f"{input_unit}/share" if input_unit else "share"
    if kind == "count":
        return "шт."
    return kind


@refuses_non_finite
def effective_tax_rate(tax_expense: float, pretax_income: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """effective_tax = tax_expense / pretax_income, БЕЗ clip (ТЗ-58 C4):
    ставка вне полосы [0, 0.5] — это не 0.0 и не 0.5, а отказ
    jurisdiction_rate с числом в продолжении; clip выдумывал значение.

    При pretax_income <= 0 -> None, jurisdiction_rate.
    При pretax_income == 0 -> denominator_zero.
    При tax_expense is None -> missing_data.
    """
    if tax_expense is None:
        return None, "missing_data"
    if pretax_income is None:
        return None, "missing_data"
    if pretax_income == 0:
        return None, "denominator_zero"
    if pretax_income < 0:
        return None, "jurisdiction_rate"
    rate = tax_expense / pretax_income
    if not math.isfinite(rate):
        # Делимое и делитель конечные, частное уехало в inf — это не
        # полоса юрисдикции, а выход за домен (ТЗ-82 E2): в продолжении
        # строки reasons всё равно не было бы числа.
        return None, "non_finite"
    if rate < 0.0 or rate > 0.5:
        return None, f"jurisdiction_rate: rate={rate:.4f}"
    return rate, None


def invested_capital(total_equity: float, minority_interest: float,
                     total_debt: float, cash: float, st_investments: float) -> float:
    """invested_capital = total_equity + minority_interest + total_debt - cash - st_investments.

    Арифметическое ядро: входы обязаны быть числами, None запрещён —
    отказ с причиной из словаря даёт calculate_measure (B1.1: раньше
    None здесь падал TypeError вместо отказа).
    """
    return total_equity + minority_interest + total_debt - cash - st_investments


@refuses_non_finite
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


@refuses_non_finite
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


@refuses_non_finite
def roe_incl_nci(net_income: float,
                 total_equity_incl_nci_begin: float,
                 total_equity_incl_nci_end: float
                 ) -> Tuple[Optional[float], Optional[NullReason]]:
    """Рентабельность капитала, ВКЛЮЧАЮЩЕГО неконтролирующие доли:
    net_income / avg(total_equity_incl_nci_начало, ..._конец).

    Не синоним roe и не подстановка: roe требует total_equity — долю
    владельцев (ТЗ-56 Z1); здесь знаменатель — весь капитал с долями
    миноритариев (total_equity_incl_nci). Правила null те же.
    """
    if total_equity_incl_nci_begin is None or \
            total_equity_incl_nci_end is None:
        return None, "missing_data"

    avg_eq = (total_equity_incl_nci_begin + total_equity_incl_nci_end) / 2
    if avg_eq == 0:
        return None, "denominator_zero"
    if avg_eq < 0:
        return None, "negative_denominator"

    return net_income / avg_eq, None


@refuses_non_finite
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
    Причина отказа назначается в calculate_measure (B1.1: раньше случай
    «ставки нет, доход есть» возвращал (None, None) — без причины)."""
    if operating_income is None:
        return None
    if tax_rate is None:
        return None  # missing_data - будем считать позже с реальной ставкой
    return operating_income * (1.0 - tax_rate)


@refuses_non_finite
def gross_margin(gross_profit: float, revenue: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """Gross Margin = gross_profit / revenue.

    Знаменатель <= 0 -> null: нулевой — denominator_zero, отрицательный
    — negative_denominator, то же правило §1.4, что у pe/pb/ps (B1.1:
    раньше отрицательная выручка молча давала знак-наоборот).
    """
    if gross_profit is None or revenue is None:
        return None, "missing_data"
    if revenue == 0:
        return None, "denominator_zero"
    if revenue < 0:
        return None, "negative_denominator"
    return gross_profit / revenue, None


@refuses_non_finite
def operating_margin(operating_income: float, revenue: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """Operating Margin = operating_income / revenue; правила знаменателя
    те же, что у gross_margin."""
    if operating_income is None or revenue is None:
        return None, "missing_data"
    if revenue == 0:
        return None, "denominator_zero"
    if revenue < 0:
        return None, "negative_denominator"
    return operating_income / revenue, None


@refuses_non_finite
def net_margin(net_income: float, revenue: float) -> Tuple[Optional[float], Optional[NullReason]]:
    """Net Margin = net_income / revenue; правила знаменателя те же,
    что у gross_margin."""
    if net_income is None or revenue is None:
        return None, "missing_data"
    if revenue == 0:
        return None, "denominator_zero"
    if revenue < 0:
        return None, "negative_denominator"
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


@refuses_non_finite
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

@refuses_non_finite
def market_cap_per_class(price_close: Optional[float],
                         shares_outstanding: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """market_cap(i) = price_close(i) * shares_outstanding(i).

    Капитализация одного класса акций — scope=instrument; оба входа
    берутся по тому же классу (data-dictionary.md §2).
    """
    if price_close is None or shares_outstanding is None:
        return None, "missing_data"
    return price_close * shares_outstanding, None


@refuses_non_finite
def market_cap_total(class_caps: List[Optional[float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """market_cap_total = sum(market_cap(i)) по всем классам эмитента — scope=issuer.

    Ни один класс не может быть None: неполная сумма выглядела бы как
    настоящая капитализация.
    """
    if not class_caps or any(c is None for c in class_caps):
        return None, "missing_data"
    return sum(class_caps), None


@refuses_non_finite
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


@refuses_non_finite
def price_to_earnings(market_cap_total: Optional[float],
                      net_income_ttm: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """pe = market_cap_total / net_income_ttm, null при знаменателе <= 0."""
    return _divide_checked(market_cap_total, net_income_ttm)


@refuses_non_finite
def price_to_book(market_cap_total: Optional[float],
                  total_equity: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """pb = market_cap_total / total_equity, null при знаменателе <= 0."""
    return _divide_checked(market_cap_total, total_equity)


@refuses_non_finite
def price_to_sales(market_cap_total: Optional[float],
                   revenue_ttm: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """ps = market_cap_total / revenue_ttm; правило нулевого/отрицательного
    знаменателя — общее (data-dictionary.md §1.4)."""
    return _divide_checked(market_cap_total, revenue_ttm)


@refuses_non_finite
def ev_to_ebitda(ev_value: Optional[float],
                 ebitda_ttm: Optional[float]) -> Tuple[Optional[float], Optional[NullReason]]:
    """ev_ebitda = ev / ebitda_ttm, null при ebitda <= 0."""
    return _divide_checked(ev_value, ebitda_ttm)


@refuses_non_finite
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

@refuses_non_finite
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

@refuses_non_finite
def hhi(shares: List[Optional[float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """Индекс Герфиндаля–Хиршмана по ДОЛЯМ целого (конвенция дробей).

    hhi = sum(share_i ** 2); единица — "index", диапазон 0..1
    (1 = монополия). Процентная конвенция 0..10000 сознательно не
    используется — чтобы не плодить вторую единицу измерения.

    Доли обязаны суммироваться в целое (1.0 с допуском 1e-6):
    суммы, не сходящиеся в целое, дают причину missing_data:
    shares_sum:<фактическая сумма>, а не молчаливую перенормировку —
    перенормировка спрятала бы дубли или пропуск участника.
    Пустой набор — missing_data: shares_empty; один участник с долей 1
    — валидный монопольный случай, hhi = 1.0.
    """
    values = [s for s in shares if s is not None]
    if not values:
        return None, "missing_data: shares_empty"
    total = sum(float(v) for v in values)
    if abs(total - 1.0) > 1e-6:
        return None, f"missing_data: shares_sum:{round(total, 9)}"
    return sum(float(v) ** 2 for v in values), None


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


@refuses_non_finite
def total_return(prices_adj: List[Tuple[str, float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """total_return(t0, t1) = price_adj(t1) / price_adj(t0) - 1 — полная
    доходность по всему ряду (первый и последний элементы)."""
    if len(prices_adj) < 2:
        return None, "missing_data"
    ratio, reason = _divide_checked(prices_adj[-1][1], prices_adj[0][1])
    if ratio is None:
        return None, reason
    return ratio - 1.0, None


@refuses_non_finite
def drawdown(prices_adj: List[Tuple[str, float]]) -> Tuple[Optional[float], Optional[NullReason]]:
    """drawdown(t) = price_adj(t) / max(price_adj[t0..t]) - 1; возвращает
    максимальную просадку по ряду (наименьшее значение).

    Цена вне домена (<= 0) — отказ missing_data: nonpositive_price
    (B1.1: ряд из неположительных цен раньше давал молчаливый 0.0 —
    «просадки нет» — вместо отказа; настоящий ноль растущего ряда это
    не подделывает, ряды различимы). Пропуск в середине ряда —
    missing_data: null_price (ТЗ-82 E2: раньше None в колонке цены
    ронял сравнение v <= 0 исключением, а формула не имеет права
    бросать)."""
    if not prices_adj:
        return None, "missing_data"
    if any(v is None for _, v in prices_adj):
        return None, "missing_data: null_price"
    if any(v <= 0 for _, v in prices_adj):
        return None, "missing_data: nonpositive_price"
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
        # ebitda = operating_income + d_and_a; если operating_income не
        # раскрыт: revenue - cogs - opex + d_and_a. B1.1: неполный путь
        # раньше подменял ebitda голым operating_income — значение,
        # заниженное на d_and_a, выглядело честным числом. Теперь отказ
        # называет, каких концептов не хватает (X3).
        operating_income = kwargs.get("operating_income")
        d_and_a = kwargs.get("d_and_a")
        revenue = kwargs.get("revenue")
        cogs = kwargs.get("cogs")
        opex = kwargs.get("opex")

        if operating_income is not None and d_and_a is not None:
            value = operating_income + d_and_a
        elif all(x is not None for x in [revenue, cogs, opex, d_and_a]):
            value = revenue - cogs - opex + d_and_a
        else:
            if operating_income is not None:
                # ближний путь: не хватает только d_and_a — не шумим
                # отсутствием концептов второго пути
                missing = ["d_and_a"]
            else:
                missing = sorted(name for name, v in (
                    ("cogs", cogs), ("d_and_a", d_and_a),
                    ("operating_income", operating_income),
                    ("opex", opex), ("revenue", revenue)) if v is None)
            null_reason = "missing_data: " + ", ".join(missing)

    elif concept == "gross_margin":
        value, null_reason = gross_margin(
            kwargs.get("gross_profit"), kwargs.get("revenue"))

    elif concept == "operating_margin":
        value, null_reason = operating_margin(
            kwargs.get("operating_income"), kwargs.get("revenue"))

    elif concept == "net_margin":
        value, null_reason = net_margin(
            kwargs.get("net_income"), kwargs.get("revenue"))

    elif concept == "invested_capital":
        # B1.1: раньше `invested_capital(**kwargs)` падал TypeError
        # дважды — на нехватке cash/st_investments и на любом лишнем
        # kwargе (period_start, lineage); теперь входы передаются
        # явно, а нехватка названа по именам, а не крэшем. Настоящий
        # ноль (все входы 0) остаётся 0.0 и отличим от отказа.
        ic_inputs = {name: kwargs.get(name) for name in (
            "total_equity", "minority_interest", "total_debt",
            "cash", "st_investments")}
        missing = sorted(name for name, v in ic_inputs.items()
                         if v is None)
        if missing:
            null_reason = "missing_data: " + ", ".join(missing)
        else:
            value = invested_capital(**ic_inputs)
    
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

    elif concept == "roe_incl_nci":
        # ТЗ-56 Z1: своя мера для капитала с неконтролирующими долями;
        # roe при том же payload по-прежнему отказывает
        # missing_data: total_equity — подстановки нет
        ni = kwargs.get("net_income")
        tei_begin = kwargs.get("total_equity_incl_nci_begin")
        tei_end = kwargs.get("total_equity_incl_nci_end")
        if ni is not None and tei_begin is not None \
                and tei_end is not None:
            val, reason = roe_incl_nci(ni, tei_begin, tei_end)
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
        # B1.1: при живом operating_income и tax_rate=None мера
        # возвращала (None, None) — ни значения, ни причины (I4).
        # Теперь отказ missing_data в обоих случаях нехватки.
        oi = kwargs.get("operating_income")
        tr = kwargs.get("tax_rate")
        value = nopat(oi, tr)
        if value is None:
            null_reason = "missing_data"
    
    elif concept == "effective_tax":
        te = kwargs.get("tax_expense")
        pi = kwargs.get("pretax_income")
        value, null_reason = effective_tax_rate(te, pi)

    elif concept == "fcf":
        # fcf = ocf - capex (data-dictionary §3 «Денежный поток»)
        ocf = kwargs.get("ocf")
        capex = kwargs.get("capex")
        if ocf is None or capex is None:
            null_reason = "missing_data"
        else:
            value = ocf - capex

    elif concept == "interest_coverage":
        # interest_coverage = operating_income / interest_expense
        oi = kwargs.get("operating_income")
        ie = kwargs.get("interest_expense")
        if oi is None or ie is None:
            null_reason = "missing_data"
        else:
            value, null_reason = _divide_checked(oi, ie)

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

    elif concept == "hhi":
        value, null_reason = hhi(kwargs.get("shares") or [])
        kwargs["unit"] = measure_unit("hhi")  # "index" — дроби (N1)

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

    if value is not None and not math.isfinite(value):
        # ТЗ-82 E2: закрытость распространяется и на концепты, которые
        # считают прямо здесь (ebitda, fcf, invested_capital, nopat,
        # interest_coverage идут мимо формул-обёрток). Значение меры не
        # уезжает в базу ни NaN, ни inf.
        value, null_reason = None, "non_finite"

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
