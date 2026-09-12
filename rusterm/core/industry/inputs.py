"""Физические записи ручного импорта -> входы отраслевого модуля
(ТЗ-24 N3/N5/N6).

Маппинг явный и по секторам — как concepts.py отображает XBRL-теги:
запись, не отобразившаяся ни в один вход, сохраняется и попадает в
счётчик unmapped, но никогда не становится чьим-то входом молча.
verified=no не кормит метрику (ADR-0011 ③) — метрика серая с
manual_unverified. Единицы несут масштаб; неизвестное масштабное слово
— причина, а не молчаливая единица.
"""
from __future__ import annotations

import re


# ── N5: масштабные слова и ожидаемые базовые единицы ──────────────────

SCALE_WORDS: dict[str, float] = {
    "thousand": 1e3, "million": 1e6, "billion": 1e9,
    "тысяча": 1e3, "тыс.": 1e3, "миллион": 1e6, "млн": 1e6,
    "миллиард": 1e9, "млрд": 1e9,
}

# базовые единицы входов maritime_tanker (N5): метрика отказывается
# от входа не в своей базовой единице — без догадок о конверсии
EXPECTED_BASE_UNITS: dict[str, str] = {
    "tankers": {
        "off_hire_days": "days", "vessel_days": "days",
        "voyage_days": "days", "contract_days": "days",
        "ships_in_class": "ships", "fleet_ships": "ships",
        "scrubber_ships": "ships", "idle_ships": "ships",
        "orderbook_ships": "ships", "ready_ships": "ships",
        "ship_count": "ships", "voyage_revenue_usd": "USD",
        "contract_revenue_usd": "USD", "class_revenue_usd": "USD",
        "opex_usd": "USD", "technical_opex_usd": "USD",
        "ga_usd": "USD", "opex_total_usd": "USD",
        "financing_cost_usd": "USD", "spot_revenue_usd": "USD",
        "tce_per_day": "USD/day", "opex_per_day": "USD/day",
        "hsfo_price_usd": "USD", "vlsfo_price_usd": "USD",
    },
    "mining": {
        "production_volume": "tons", "ore_milled": "tons",
        "grade": "g/t", "reserves": "tons",
        "cash_cost_per_unit": "USD/t", "ships": "ships",
        "fleet_ships": "ships",
    },
}


def parse_scaled_unit(unit: str | None) -> tuple[str, float, bool]:
    """unit -> (базовая единица, множитель, распознан).

    'million tons' -> ('tons', 1e6, True); 'USD/day' ->
    ('USD/day', 1.0, True); 'млн тонн' -> ('тонн'? — базовое слово
    берётся как есть после снятия масштабного слова). Нераспознанное
    масштабное слово ('billionn') -> (unit, 1.0, False) — вызывающий
    даёт причину, молчаливой единицы нет.
    """
    if not unit:
        return "", 1.0, True
    text = unit.strip().lower()
    # масштабное слово допустимо только ПРЕФИКСОМ ('million tons');
    # внутри слова ('billionn tons') оно не масштаб, а опечатка —
    # единица не распознана, вызывающий даст причину
    for word, mult in SCALE_WORDS.items():
        if text.startswith(word + " "):
            base = text[len(word) + 1:].strip()
            return (base or text), mult, True
        if text == word:
            return "", mult, False  # масштаб без базовой единицы
    for word in SCALE_WORDS:
        if word in text:
            return text, 1.0, False
    return text, 1.0, True


def _norm_metric(name: str | None) -> str:
    return re.sub(r"[\s\-]+", "_", (name or "").strip().lower())


# ── N3: явный маппинг записей -> входы, по секторам ───────────────────

PHYSICAL_INPUT_MAP: dict[str, dict[str, list[str]]] = {
    "tankers": {
        "off_hire_days": ["off_hire_days", "offhire_days",
                          "off_hire", "days_off_hire"],
        "vessel_days": ["vessel_days", "operating_days"],
        "voyage_days": ["voyage_days", "loaded_voyage_days"],
        "contract_days": ["contract_days", "time_charter_days"],
        "ships_in_class": ["ships_in_class", "vessels_in_class",
                           "fleet_count_by_class"],
        "fleet_ships": ["fleet_ships", "fleet_count", "vessels"],
        "ship_count": ["ship_count", "vessels"],
        "voyage_revenue_usd": ["voyage_revenue", "voyage_revenue_usd"],
        "contract_revenue_usd": ["contract_revenue"],
        "class_revenue_usd": ["class_revenue"],
        "opex_usd": ["opex", "vessel_opex"],
        "technical_opex_usd": ["technical_opex"],
        "ga_usd": ["ga", "general_administrative"],
        "opex_total_usd": ["total_opex"],
        "financing_cost_usd": ["financing_cost", "interest_expense_ops"],
        "spot_revenue_usd": ["spot_revenue"],
        "tce_per_day": ["tce", "tce_per_day"],
        "opex_per_day": ["opex_per_day"],
    },
    "mining": {
        "production_volume": ["production_volume", "production"],
        "ore_milled": ["ore_milled"],
        "grade": ["grade"],
        "reserves": ["reserves"],
        "cash_cost_per_unit": ["cash_cost", "cash_cost_per_unit"],
    },
}


class SectorInputs:
    """Результат сбора входов сектора: значения, отчёт о мимо прошедших
    и непроверенных; единицы уже с масштабом."""

    def __init__(self):
        self.inputs: dict[str, dict] = {}
        self.unmapped: list[str] = []
        self.unverified: list[str] = []
        self.unit_refused: dict[str, str] = {}


def collect_physical_inputs(manual_repo, issuer_id: str,
                            sector: str) -> SectorInputs:
    """Собрать входы сектора из verified-физических записей эмитента.

    Отображение — PHYSICAL_INPUT_MAP[sector]; запись мимо карты —
    unmapped (сохранена и посчитана, не выброшена); verified=no —
    имя входа в unverified (метрика серая с manual_unverified);
    единица не той базы — unit_refused[вход] = ожидаемая.
    """
    out = SectorInputs()
    mapping = PHYSICAL_INPUT_MAP.get(sector, {})
    expected_units = EXPECTED_BASE_UNITS.get(sector, {})
    for row in manual_repo.for_issuer(issuer_id, category="physical"):
        (_rowid, _sha, _page, _cat, metric, value, unit, _period,
         _quote, verified, _model, _pv) = row
        norm = _norm_metric(metric)
        input_name = None
        for candidate, aliases in mapping.items():
            if norm in (_norm_metric(a) for a in aliases) \
                    or norm == _norm_metric(candidate):
                input_name = candidate
                break
        if input_name is None:
            out.unmapped.append(metric or "")
            continue
        if not verified:
            if input_name not in out.unverified:
                out.unverified.append(input_name)
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            out.unmapped.append(metric or "")
            continue
        base, mult, recognised = parse_scaled_unit(unit)
        if not recognised:
            out.unmapped.append(f"{metric} (unit: {unit})")
            continue
        expected = expected_units.get(input_name)
        if expected and base != expected.lower():
            out.unit_refused[input_name] = expected
            continue
        if input_name not in out.inputs:  # первая подтверждённая запись
            out.inputs[input_name] = {
                "value": numeric * mult, "unit": unit or base,
                "base": base, "multiplier": mult, "source": "manual"}
    return out


def sector_of(repos, instrument_id: str) -> str | None:
    """Сектор инструмента — id его отраслевого peer set (M7)."""
    peer = repos.peer_set.peer_set_for_instrument(instrument_id)
    return peer["peer_set_id"] if peer else None


# Требуемые входы каждой метрики — объявлены явно (диспетчер модуля
# принимает **kw и имён не отдаёт); имя входа = имя параметра функции
# модуля, что проверяется тестом N6.
METRIC_INPUTS: dict[str, dict[str, list[str]]] = {
    "tankers": {
        "fleet_utilization_pct": ["off_hire_days"],
        "off_hire_days": ["off_hire_days"],
        "spot_TCE_per_day_by_class": ["voyage_revenue_usd",
                                      "voyage_days"],
        "time_charter_TCE_per_day_by_class": ["contract_revenue_usd",
                                              "contract_days"],
        "revenue_per_ship_by_class": ["class_revenue_usd",
                                      "ships_in_class"],
        "vessel_OPEX_per_day_by_class_and_age": ["opex_usd",
                                                 "vessel_days"],
        "technical_OPEX_per_day": ["technical_opex_usd", "vessel_days"],
        "G&A_per_ship_per_year": ["ga_usd", "ship_count"],
        "daily_vessel_margin": ["tce_per_day", "opex_per_day"],
        "vessel_breakeven_TCE": ["opex_total_usd", "financing_cost_usd",
                                 "ga_usd", "ship_count"],
        "orderbook_to_fleet_ratio_pct": ["orderbook_ships",
                                         "fleet_ships"],
        "scrubber_fitted_pct": ["scrubber_ships", "fleet_ships"],
        "idle_capacity_pct": ["idle_ships", "fleet_ships"],
        "bunker_spread_HSFO_VLSFO": ["hsfo_price_usd",
                                     "vlsfo_price_usd"],
    },
    "mining": {
        "production_volume_tons": ["production_volume"],
        "ore_grade_g_per_ton": ["grade"],
        "reserves_to_production_ratio": ["reserves",
                                         "production_volume"],
        "cash_cost_per_ounce": ["cash_cost_per_unit"],
        "production_per_employee": ["production_volume"],
        "revenue_per_ton": ["revenue_usd", "production_volume"],
        "reserve_replacement_pct": ["reserves_added", "reserves_mined"],
        "all_in_sustaining_cost": ["aisc_usd", "production_volume"],
        "production_cost_ratio": ["cash_cost_per_unit",
                                  "realized_price"],
        "realized_price_per_ton": ["realized_price"],
    },
}


def compute_sector_metrics(module, sector: str, si: SectorInputs) -> list[dict]:
    """Посчитать объявленные метрики модуля из собранных входов.

    Серая метрика называет недостающий вход ИМЕНЕМ ВХОДА из
    METRIC_INPUTS (= имя параметра функции модуля, N6); вход из
    непроверенной записи — manual_unverified; вход с чужой единицей —
    missing_data: unit_mismatch:<ожидаемая>. У каждой метрики стоит
    method_version модуля и источник.
    """
    declared = METRIC_INPUTS.get(sector, {})
    out: list[dict] = []
    for concept in sorted(declared):
        needed = declared[concept]
        # порядок причин: непроверенная запись важнее отсутствующей
        # (страница есть, доверия нет), чужая единица — прежде missing
        unverified = [p for p in needed if p in si.unverified]
        if unverified:
            out.append({"concept": concept, "value": None, "unit": "",
                        "reason": "manual_unverified",
                        "method_version": module.METHOD_VERSION,
                        "source": "manual"})
            continue
        refused = [p for p in needed if p in si.unit_refused]
        if refused:
            out.append({"concept": concept, "value": None, "unit": "",
                        "reason": "missing_data: unit_mismatch:"
                                  + si.unit_refused[refused[0]],
                        "method_version": module.METHOD_VERSION,
                        "source": "manual"})
            continue
        missing = [p for p in needed if p not in si.inputs]
        if missing:
            out.append({"concept": concept, "value": None, "unit": "",
                        "reason": "no " + ", ".join(sorted(missing)),
                        "method_version": module.METHOD_VERSION,
                        "source": None})
            continue
        try:
            m = module.calculate_industry_measure(
                concept, **{p: si.inputs[p]["value"] for p in needed})
        except (TypeError, KeyError):
            out.append({"concept": concept, "value": None, "unit": "",
                        "reason": "missing_data", "unit2": None,
                        "method_version": module.METHOD_VERSION,
                        "source": "manual"})
            continue
        source = "manual" if any(si.inputs[p].get("source") == "manual"
                                 for p in needed) else None
        out.append({"concept": m.concept, "value": m.value,
                    "unit": m.unit, "reason": m.null_reason,
                    "method_version": m.method_version,
                    "source": source})
    return out


def industry_metrics_for(repos, instrument_id: str,
                         as_of: str | None = None) -> dict:
    """Метрики отрасли инструмента на-месте (N8/N9): сектор из peer
    set, модуль из реестра, входы из verified-записей. Read-only."""
    from . import module_for_sector
    sector = sector_of(repos, instrument_id)
    if sector is None:
        return {"sector": None, "reason": "industry_no_sector",
                "metrics": [], "unmapped": []}
    module = module_for_sector(sector)
    if module is None:
        return {"sector": sector,
                "reason": f"industry_no_module:{sector}",
                "metrics": [], "unmapped": []}
    instrument = repos.instrument.get_instrument(instrument_id)
    si = collect_physical_inputs(repos.manual_extraction,
                                 instrument.issuer_id if instrument
                                 else "", sector)
    metrics = compute_sector_metrics(module, sector, si)
    return {"sector": sector, "reason": None, "metrics": metrics,
            "unmapped": si.unmapped}
