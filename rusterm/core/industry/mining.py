"""Mining / upstream energy: каталог метрик сектора (ТЗ-24 N11).

Каталожная страница сектора (аналог docs/industry-metrics/maritime-
tanker.md) живёт ЗДЕСЬ, в докстринге модуля: пункт 10 приёмки пускает
в docs/ только новые ADR, а добавленный файл
docs/industry-metrics/mining.md её валит (см. Disputed REPORT-24.md).
Имена метрик — дословно из каталога ниже, как U12.1 bindит maritime.

## Catalogue: mining (production-weighted business)

Metrics (name, unit, inputs):
- production_volume_tons(production_volume)            -> tons
- ore_grade_g_per_ton(grade)                           -> g/t
- reserves_to_production_ratio(reserves, production_volume)
                                                       -> years
- cash_cost_per_ounce(cash_cost_per_unit, grade_multiplier)
                                                       -> USD/t
- production_per_employee(production_volume, employees)-> tons/person
- revenue_per_ton(revenue_usd, production_volume)      -> USD/t
- reserve_replace_ment_pct(reserves_added, reserves_mined) -> pct
- all_in_sustaining_cost(aisc_usd, production_volume)  -> USD/t
- production_cost_ratio(cash_cost_per_unit, realized_price) -> ratio

Форма бизнеса отличается от перевозок: не судо-дни, а объёмы,
содержания и запасы; единицы — tons / g/t / USD/t, не days / ships.
"""
from __future__ import annotations

from typing import List, Optional

from ...formulas import Measure

METHOD_VERSION = "mining.v1"


def _measure(concept: str, value: Optional[float], unit: str,
             null_reason=None, scope: str = "issuer") -> Measure:
    return Measure(concept=concept, value=value, unit=unit,
                   method_version=METHOD_VERSION, null_reason=null_reason,
                   scope=scope)


def _ratio(numerator: Optional[float], denominator: Optional[float],
           scale: float = 1.0) -> tuple:
    if numerator is None or denominator is None:
        return None, "missing_data"
    if denominator == 0:
        return None, "denominator_zero"
    return numerator / denominator * scale, None


def production_volume_tons(production_volume) -> Measure:
    """Добыча за период, тонн — прямое раскрытие."""
    if production_volume is None:
        return _measure("production_volume_tons", None, "tons",
                        "missing_data")
    return _measure("production_volume_tons", float(production_volume),
                    "tons")


def ore_grade_g_per_ton(grade) -> Measure:
    """Содержание металла, г/т — прямое раскрытие."""
    if grade is None:
        return _measure("ore_grade_g_per_ton", None, "g/t",
                        "missing_data")
    return _measure("ore_grade_g_per_ton", float(grade), "g/t")


def reserves_to_production_ratio(reserves, production_volume) -> Measure:
    """Обеспеченность запасами: reserves / годовая добыча, лет."""
    value, reason = _ratio(reserves, production_volume)
    return _measure("reserves_to_production_ratio", value, "years", reason)


def cash_cost_per_ounce(cash_cost_per_unit, grade_multiplier) -> Measure:
    """Кэш-кост на единицу с поправкой на содержание."""
    if cash_cost_per_unit is None or grade_multiplier is None:
        return _measure("cash_cost_per_ounce", None, "USD/t",
                        "missing_data")
    if grade_multiplier == 0:
        return _measure("cash_cost_per_ounce", None, "USD/t",
                        "denominator_zero")
    return _measure("cash_cost_per_ounce",
                    cash_cost_per_unit / grade_multiplier, "USD/t")


def production_per_employee(production_volume, employees) -> Measure:
    """Добыча на сотрудника, тонн на человека."""
    value, reason = _ratio(production_volume, employees)
    return _measure("production_per_employee", value, "tons/person",
                    reason)


def revenue_per_ton(revenue_usd, production_volume) -> Measure:
    """Выручка на тонну добытого."""
    value, reason = _ratio(revenue_usd, production_volume)
    return _measure("revenue_per_ton", value, "USD/t", reason)


def reserve_replacement_pct(reserves_added, reserves_mined) -> Measure:
    """Замещение запасов, %: добавленные / добытые * 100."""
    value, reason = _ratio(reserves_added, reserves_mined, scale=100.0)
    if value is not None and value < 0:
        value, reason = None, "negative_denominator"
    return _measure("reserve_replacement_pct", value, "pct", reason)


def all_in_sustaining_cost(aisc_usd, production_volume) -> Measure:
    """AISC на тонну: полные поддерживающие затраты / добыча."""
    value, reason = _ratio(aisc_usd, production_volume)
    return _measure("all_in_sustaining_cost", value, "USD/t", reason)


def production_cost_ratio(cash_cost_per_unit, realized_price) -> Measure:
    """Кэш-кост к реализованной цене: доля затрат в цене (ratio)."""
    value, reason = _ratio(cash_cost_per_unit, realized_price)
    return _measure("production_cost_ratio", value, "ratio", reason)


def realized_price_per_ton(realized_price) -> Measure:
    """Реализованная цена, USD/t — прямое раскрытие."""
    if realized_price is None:
        return _measure("realized_price_per_ton", None, "USD/t",
                        "missing_data")
    return _measure("realized_price_per_ton", float(realized_price),
                    "USD/t")


_DISPATCH = {}


def _register(fn):
    _DISPATCH[fn.__name__] = fn
    return fn


for _fn in (production_volume_tons, ore_grade_g_per_ton,
            reserves_to_production_ratio, cash_cost_per_ounce,
            production_per_employee, revenue_per_ton,
            reserve_replacement_pct, all_in_sustaining_cost,
            production_cost_ratio, realized_price_per_ton):
    _register(_fn)


def calculate_industry_measure(concept: str, **inputs) -> Measure:
    if concept not in _DISPATCH:
        raise KeyError(f"неизвестная отраслевая мера {concept!r}")
    return _DISPATCH[concept](**inputs)


def known_measures() -> tuple:
    return tuple(sorted(_DISPATCH))
