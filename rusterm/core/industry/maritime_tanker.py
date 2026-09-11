"""Метрики Maritime/Tanker (TASK-7 T18, docs/industry-metrics/maritime-tanker.md).

Механизм общий с rusterm/formulas.py: те же Measure и null-причины,
никаких исключений — валидное число или None с причиной. Своей
арифметики вне этого файла не появляется.

Рыночные ряды (Clarksons, Baltic Exchange) не фетчатся: они входят
как готовые входы вызывающего — с lineage на источник, иначе метрика
серая с no_data. method_version='maritime.v1'.
"""
from __future__ import annotations

from typing import List, Optional

from rusterm.formulas import Measure

METHOD_VERSION = "maritime.v1"
YEAR_DAYS = 365.0


def _measure(concept: str, value: Optional[float], unit: str,
             null_reason=None, scope: str = "issuer") -> Measure:
    return Measure(concept=concept, value=value, unit=unit,
                   method_version=METHOD_VERSION, null_reason=null_reason,
                   scope=scope)


def _ratio(numerator: Optional[float], denominator: Optional[float],
           scale: float = 1.0) -> tuple:
    """Деление с правилами null: нет входа — missing_data, нулевой
    знаменатель — denominator_zero."""
    if numerator is None or denominator is None:
        return None, "missing_data"
    if denominator == 0:
        return None, "denominator_zero"
    return numerator / denominator * scale, None


def _per_day(total_usd: Optional[float], days: Optional[float],
             concept: str) -> Measure:
    value, reason = _ratio(total_usd, days)
    return _measure(concept, value, "USD/day", reason)


def _per_ship(total_usd: Optional[float], ships: Optional[float],
              concept: str, unit: str = "USD") -> Measure:
    value, reason = _ratio(total_usd, ships)
    return _measure(concept, value, unit, reason)


def _percent(part: Optional[float], whole: Optional[float],
             concept: str) -> Measure:
    value, reason = _ratio(part, whole, scale=100.0)
    return _measure(concept, value, "pct", reason)


# ── Доходность флота ────────────────────────────────────────────────────

def spot_TCE_per_day_by_class(voyage_revenue_usd, voyage_days,
                              ship_class: str = "") -> Measure:
    """TCE спота в день по классу: выручка рейсов / рейсовые дни."""
    return _per_day(voyage_revenue_usd, voyage_days,
                    "spot_TCE_per_day_by_class")


def time_charter_TCE_per_day_by_class(contract_revenue_usd, contract_days,
                                      ship_class: str = "") -> Measure:
    """TCE средне- и долгосрочных контрактов в день по классу."""
    return _per_day(contract_revenue_usd, contract_days,
                    "time_charter_TCE_per_day_by_class")


def fleet_utilization_pct(off_hire_days: Optional[float],
                          year_days: float = YEAR_DAYS) -> Measure:
    """% дней в году, когда судно работало: (год - вне эксплуатации)/год."""
    if off_hire_days is None:
        return _measure("fleet_utilization_pct", None, "pct",
                        "missing_data")
    value, reason = _ratio(year_days - off_hire_days, year_days, scale=100.0)
    if reason == "denominator_zero" or (value is not None and value < 0):
        value, reason = None, "denominator_zero" if year_days == 0 else "negative_denominator"
    return _measure("fleet_utilization_pct", value, "pct", reason)


def off_hire_days(off_hire_days: Optional[float]) -> Measure:
    """Дней вне эксплуатации по судну/флоту — прямое раскрытие."""
    if off_hire_days is None:
        return _measure("off_hire_days", None, "days", "missing_data")
    return _measure("off_hire_days", float(off_hire_days), "days")


def revenue_per_ship_by_class(class_revenue_usd, ships_in_class) -> Measure:
    """Годовая выручка класса / число судов класса."""
    return _per_ship(class_revenue_usd, ships_in_class,
                     "revenue_per_ship_by_class")


# ── Операционные расходы ────────────────────────────────────────────────

def vessel_OPEX_per_day_by_class_and_age(opex_usd, vessel_days) -> Measure:
    return _per_day(opex_usd, vessel_days,
                    "vessel_OPEX_per_day_by_class_and_age")


def technical_OPEX_per_day(technical_opex_usd, vessel_days) -> Measure:
    """OPEX без G&A и финансирования."""
    return _per_day(technical_opex_usd, vessel_days,
                    "technical_OPEX_per_day")


def GA_per_ship_per_year(ga_usd, ship_count) -> Measure:
    return _per_ship(ga_usd, ship_count, "G&A_per_ship_per_year")


# ── Маржинальность ──────────────────────────────────────────────────────

def daily_vessel_margin(tce_per_day, opex_per_day) -> Measure:
    """TCE в день минус OPEX в день: валовая маржа судна в день."""
    if tce_per_day is None or opex_per_day is None:
        return _measure("daily_vessel_margin", None, "USD/day",
                        "missing_data")
    return _measure("daily_vessel_margin", tce_per_day - opex_per_day,
                    "USD/day")


def vessel_breakeven_TCE(opex_total_usd, financing_cost_usd, ga_usd,
                         ship_count, year_days: float = YEAR_DAYS) -> Measure:
    """TCE нулевой прибыли: (OPEX + финансирование + G&A)/суда/дни."""
    parts = [opex_total_usd, financing_cost_usd, ga_usd]
    if any(p is None for p in parts):
        return _measure("vessel_breakeven_TCE", None, "USD/day",
                        "missing_data")
    if not ship_count or not year_days:
        return _measure("vessel_breakeven_TCE", None, "USD/day",
                        "denominator_zero")
    value = (opex_total_usd + financing_cost_usd + ga_usd) \
        / ship_count / year_days
    return _measure("vessel_breakeven_TCE", value, "USD/day")


# ── Структура флота ─────────────────────────────────────────────────────

def fleet_count_by_class(count) -> Measure:
    if count is None:
        return _measure("fleet_count_by_class", None, "ships",
                        "missing_data")
    return _measure("fleet_count_by_class", float(count), "ships")


def fleet_age_histogram(ages: Optional[List[float]],
                        bin_years: int = 5) -> dict:
    """Гистограмма возраста флота (не скалярная мера, потому не Measure):
    {«0-4»: n, «5-9»: n, ...}. Старение флота = рост OPEX и списание."""
    histogram: dict = {}
    if not ages:
        return histogram
    for age in ages:
        if age is None:
            continue
        low = int(age // bin_years) * bin_years
        key = f"{low}-{low + bin_years - 1}"
        histogram[key] = histogram.get(key, 0) + 1
    return histogram


def average_fleet_age(ages: Optional[List[float]]) -> Measure:
    if not ages or any(a is None for a in ages):
        return _measure("average_fleet_age", None, "years", "missing_data")
    return _measure("average_fleet_age", sum(ages) / len(ages), "years")


def average_residual_years_by_class(residual_years: Optional[List[float]],
                                    ship_class: str = "") -> Measure:
    """Лет до следующего обязательного dry-dock / скрапа."""
    if not residual_years or any(r is None for r in residual_years):
        return _measure("average_residual_years_by_class", None, "years",
                        "missing_data")
    return _measure("average_residual_years_by_class",
                    sum(residual_years) / len(residual_years), "years")


def spot_vs_time_charter_exposure_pct(spot_revenue_usd,
                                      total_revenue_usd) -> Measure:
    """Доля доходов от краткосрочных контрактов."""
    return _percent(spot_revenue_usd, total_revenue_usd,
                    "spot_vs_time_charter_exposure_pct")


def orderbook_to_fleet_ratio_pct(orderbook_ships, fleet_ships) -> Measure:
    """Заказанные новые суда к текущему флоту: давление на ставки."""
    return _percent(orderbook_ships, fleet_ships,
                    "orderbook_to_fleet_ratio_pct")


# ── Рыночные индикаторы (входы — готовые ряды, не фетчатся) ────────────

def newbuilding_price_index_by_class(price_usd) -> Measure:
    if price_usd is None:
        return _measure("newbuilding_price_index_by_class", None, "USD",
                        "missing_data")
    return _measure("newbuilding_price_index_by_class", float(price_usd),
                    "USD")


def secondhand_price_index_by_class(price_usd) -> Measure:
    if price_usd is None:
        return _measure("secondhand_price_index_by_class", None, "USD",
                        "missing_data")
    return _measure("secondhand_price_index_by_class", float(price_usd),
                    "USD")


def scrapping_age_profile(ages_of_scrapped: Optional[List[float]]) -> Measure:
    """Средний возраст списанных судов — когда флот «созреет»."""
    if not ages_of_scrapped or any(a is None for a in ages_of_scrapped):
        return _measure("scrapping_age_profile", None, "years",
                        "missing_data")
    return _measure("scrapping_age_profile",
                    sum(ages_of_scrapped) / len(ages_of_scrapped), "years")


def bunker_spread_HSFO_VLSFO(hsfo_price_usd, vlsfo_price_usd) -> Measure:
    """Разница цен мазута и низкосернистого топлива: стоимость
    compliance после IMO 2020."""
    if hsfo_price_usd is None or vlsfo_price_usd is None:
        return _measure("bunker_spread_HSFO_VLSFO", None, "USD/tonne",
                        "missing_data")
    return _measure("bunker_spread_HSFO_VLSFO",
                    hsfo_price_usd - vlsfo_price_usd, "USD/tonne")


# ── Экология ────────────────────────────────────────────────────────────

def CII_per_ship(cii_grams_per_tonmile: Optional[float]) -> Measure:
    unit = "g CO2/tonne-mile"
    if cii_grams_per_tonmile is None:
        return _measure("CII_per_ship", None, unit, "missing_data")
    return _measure("CII_per_ship", float(cii_grams_per_tonmile), unit)


def scrubber_fitted_pct(scrubber_ships, fleet_ships) -> Measure:
    return _percent(scrubber_ships, fleet_ships, "scrubber_fitted_pct")


def IMO_2020_readiness_pct(ready_ships, fleet_ships) -> Measure:
    return _percent(ready_ships, fleet_ships, "IMO_2020_readiness_pct")


# ── Контейнеровозы (специфика из того же документа) ────────────────────

def port_congestion_TEU_waiting(teu: Optional[float]) -> Measure:
    if teu is None:
        return _measure("port_congestion_TEU_waiting", None, "TEU",
                        "missing_data")
    return _measure("port_congestion_TEU_waiting", float(teu), "TEU")


def idle_capacity_pct(idle_ships, fleet_ships) -> Measure:
    return _percent(idle_ships, fleet_ships, "idle_capacity_pct")


def blank_sailings_pct(blank_sailings, scheduled_sailings) -> Measure:
    return _percent(blank_sailings, scheduled_sailings,
                    "blank_sailings_pct")


# ── Диспетчер — единая точка расчёта по имени концепта ─────────────────

_DISPATCH = {
    "spot_TCE_per_day_by_class": lambda **kw: spot_TCE_per_day_by_class(
        kw.get("voyage_revenue_usd"), kw.get("voyage_days")),
    "time_charter_TCE_per_day_by_class":
        lambda **kw: time_charter_TCE_per_day_by_class(
            kw.get("contract_revenue_usd"), kw.get("contract_days")),
    "fleet_utilization_pct": lambda **kw: fleet_utilization_pct(
        kw.get("off_hire_days"), kw.get("year_days", YEAR_DAYS)),
    "off_hire_days": lambda **kw: off_hire_days(kw.get("off_hire_days")),
    "revenue_per_ship_by_class": lambda **kw: revenue_per_ship_by_class(
        kw.get("class_revenue_usd"), kw.get("ships_in_class")),
    "vessel_OPEX_per_day_by_class_and_age":
        lambda **kw: vessel_OPEX_per_day_by_class_and_age(
            kw.get("opex_usd"), kw.get("vessel_days")),
    "technical_OPEX_per_day": lambda **kw: technical_OPEX_per_day(
        kw.get("technical_opex_usd"), kw.get("vessel_days")),
    "G&A_per_ship_per_year": lambda **kw: GA_per_ship_per_year(
        kw.get("ga_usd"), kw.get("ship_count")),
    "daily_vessel_margin": lambda **kw: daily_vessel_margin(
        kw.get("tce_per_day"), kw.get("opex_per_day")),
    "vessel_breakeven_TCE": lambda **kw: vessel_breakeven_TCE(
        kw.get("opex_total_usd"), kw.get("financing_cost_usd"),
        kw.get("ga_usd"), kw.get("ship_count")),
    "fleet_count_by_class": lambda **kw: fleet_count_by_class(
        kw.get("count")),
    "average_fleet_age": lambda **kw: average_fleet_age(
        kw.get("ages")),
    "fleet_age_histogram": lambda **kw: fleet_age_histogram(
        kw.get("ages")),
    "average_residual_years_by_class":
        lambda **kw: average_residual_years_by_class(
            kw.get("residual_years")),
    "spot_vs_time_charter_exposure_pct":
        lambda **kw: spot_vs_time_charter_exposure_pct(
            kw.get("spot_revenue_usd"), kw.get("total_revenue_usd")),
    "orderbook_to_fleet_ratio_pct": lambda **kw: orderbook_to_fleet_ratio_pct(
        kw.get("orderbook_ships"), kw.get("fleet_ships")),
    "newbuilding_price_index_by_class":
        lambda **kw: newbuilding_price_index_by_class(kw.get("price_usd")),
    "secondhand_price_index_by_class":
        lambda **kw: secondhand_price_index_by_class(kw.get("price_usd")),
    "scrapping_age_profile": lambda **kw: scrapping_age_profile(
        kw.get("ages_of_scrapped")),
    "bunker_spread_HSFO_VLSFO": lambda **kw: bunker_spread_HSFO_VLSFO(
        kw.get("hsfo_price_usd"), kw.get("vlsfo_price_usd")),
    "CII_per_ship": lambda **kw: CII_per_ship(
        kw.get("cii_grams_per_tonmile")),
    "scrubber_fitted_pct": lambda **kw: scrubber_fitted_pct(
        kw.get("scrubber_ships"), kw.get("fleet_ships")),
    "IMO_2020_readiness_pct": lambda **kw: IMO_2020_readiness_pct(
        kw.get("ready_ships"), kw.get("fleet_ships")),
    "port_congestion_TEU_waiting": lambda **kw: port_congestion_TEU_waiting(
        kw.get("teu")),
    "idle_capacity_pct": lambda **kw: idle_capacity_pct(
        kw.get("idle_ships"), kw.get("fleet_ships")),
    "blank_sailings_pct": lambda **kw: blank_sailings_pct(
        kw.get("blank_sailings"), kw.get("scheduled_sailings")),
}


def calculate_industry_measure(concept: str, **inputs) -> Measure:
    """Единая точка расчёта отраслевой меры по имени — как
    calculate_measure у общих формул. Неизвестное имя — исключение:
    программная ошибка, а не внешняя."""
    if concept not in _DISPATCH:
        raise KeyError(f"неизвестная отраслевая мера {concept!r}")
    return _DISPATCH[concept](**inputs)


# Имена из документа дословно (TASK-8 U12.1): в maritime-tanker.md
# семь метрик пишутся с «%», а fleet_age_profile — гистограмма.
# Функции Python сохраняют *_pct, реестр знает оба имени.
_ALIASES: dict[str, str] = {
    "fleet_utilization_%": "fleet_utilization_pct",
    "spot_vs_time_charter_exposure_%": "spot_vs_time_charter_exposure_pct",
    "orderbook_to_fleet_ratio_%": "orderbook_to_fleet_ratio_pct",
    "scrubber_fitted_%": "scrubber_fitted_pct",
    "IMO_2020_readiness_%": "IMO_2020_readiness_pct",
    "idle_capacity_%": "idle_capacity_pct",
    "blank_sailings_%": "blank_sailings_pct",
    "fleet_age_profile": "fleet_age_histogram",
}

for _doc_name, _code_name in _ALIASES.items():
    _DISPATCH[_doc_name] = _DISPATCH[_code_name]


def known_measures() -> tuple:
    return tuple(sorted(_DISPATCH))
