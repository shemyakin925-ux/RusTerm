"""Тесты метрик Maritime/Tanker (TASK-7 T18, maritime-tanker.md).

Три теста из документа:
1. golden-file на трёх эмитентах (Frontline, Euronav, DHT) — числа
   синтетические, эталон выписан руками;
2. unit на расчёт per-ship, per-class, breakeven — с null-причинами;
3. интеграционный на segment data из годового отчёта — офлайн на
   сохранённом документе через табличный парсер; живой вариант
   помечен integration и чисто пропускается без RUSTERM_SEC_UA.

Все меры — Measure из rusterm/formulas, method_version='maritime.v1'.
"""
from __future__ import annotations

import json
import os

import pytest

from rusterm.core.industry import maritime_tanker as mt
from rusterm.formulas import Measure

# ── Синтетические входы трёх эмитентов (числа выдуманы) ─────────────────
# Общий год: 365 дней.
FLEET = {
    "Frontline": dict(
        ships=80, voyage_revenue=18_250_000.0, voyage_days=365.0,
        opex_per_day=8_000.0, opex_total=8_000.0 * 80 * 365,
        financing=114_400_000.0, ga=90_000_000.0,
        off_hire=36.5, class_revenue=1_460_000_000.0,
        spot_revenue=730_000_000.0, total_revenue=1_460_000_000.0,
        orderbook=8),
    "Euronav": dict(
        ships=40, voyage_revenue=12_410_000.0, voyage_days=340.0,
        opex_per_day=7_500.0, opex_total=7_500.0 * 40 * 365,
        financing=80_000_000.0, ga=45_000_000.0,
        off_hire=18.25, class_revenue=800_000_000.0,
        spot_revenue=560_000_000.0, total_revenue=800_000_000.0,
        orderbook=2),
    "DHT": dict(
        ships=25, voyage_revenue=14_600_000.0, voyage_days=365.0,
        opex_per_day=7_000.0, opex_total=7_000.0 * 25 * 365,
        financing=60_000_000.0, ga=35_000_000.0,
        off_hire=0.0, class_revenue=365_000_000.0,
        spot_revenue=109_500_000.0, total_revenue=365_000_000.0,
        orderbook=0),
}

# ── Эталон, выписанный руками ───────────────────────────────────────────
GOLDEN = {
    "Frontline": {
        "spot_TCE_per_day_by_class": 18_250_000.0 / 365.0,   # 50 000
        "daily_vessel_margin": 50_000.0 - 8_000.0,           # 42 000
        "fleet_utilization_pct": (365.0 - 36.5) / 365.0 * 100.0,  # 90
        "revenue_per_ship_by_class": 1_460_000_000.0 / 80.0,  # 18 250 000
        "vessel_breakeven_TCE": (8_000.0 * 80 * 365 + 114_400_000.0
                                 + 90_000_000.0) / 80.0 / 365.0,  # 15 000
        "orderbook_to_fleet_ratio_pct": 8.0 / 80.0 * 100.0,  # 10
    },
    "Euronav": {
        "spot_TCE_per_day_by_class": 12_410_000.0 / 340.0,   # 36 500
        "daily_vessel_margin": 36_500.0 - 7_500.0,           # 29 000
        "fleet_utilization_pct": (365.0 - 18.25) / 365.0 * 100.0,  # 95
        "revenue_per_ship_by_class": 800_000_000.0 / 40.0,   # 20 000 000
        "vessel_breakeven_TCE": (7_500.0 * 40 * 365 + 80_000_000.0
                                 + 45_000_000.0) / 40.0 / 365.0,  # 12 812.5
        "orderbook_to_fleet_ratio_pct": 2.0 / 40.0 * 100.0,  # 5
    },
    "DHT": {
        "spot_TCE_per_day_by_class": 14_600_000.0 / 365.0,   # 40 000
        "daily_vessel_margin": 40_000.0 - 7_000.0,           # 33 000
        "fleet_utilization_pct": 100.0,                      # ни дня вне найма
        "revenue_per_ship_by_class": 365_000_000.0 / 25.0,   # 14 600 000
        "vessel_breakeven_TCE": (7_000.0 * 25 * 365 + 60_000_000.0
                                 + 35_000_000.0) / 25.0 / 365.0,  # 13 700
        "orderbook_to_fleet_ratio_pct": 0.0,                 # заказов нет
    },
}


def test_golden_three_tanker_issuers_frontline_euronav_dht():
    """Golden-file на трёх эмитентах: каждая мера сходится с ручным
    эталоном (data-dictionary-арифметика, не вывод кода)."""
    for issuer, inputs in FLEET.items():
        tce = mt.spot_TCE_per_day_by_class(
            inputs["voyage_revenue"], inputs["voyage_days"])
        assert tce.value == pytest.approx(
            GOLDEN[issuer]["spot_TCE_per_day_by_class"]), issuer
        assert tce.method_version == "maritime.v1"
        assert tce.unit == "USD/day"

        margin = mt.daily_vessel_margin(tce.value, inputs["opex_per_day"])
        assert margin.value == pytest.approx(
            GOLDEN[issuer]["daily_vessel_margin"]), issuer

        util = mt.fleet_utilization_pct(inputs["off_hire"])
        assert util.value == pytest.approx(
            GOLDEN[issuer]["fleet_utilization_pct"]), issuer

        rps = mt.revenue_per_ship_by_class(
            inputs["class_revenue"], inputs["ships"])
        assert rps.value == pytest.approx(
            GOLDEN[issuer]["revenue_per_ship_by_class"]), issuer

        breakeven = mt.vessel_breakeven_TCE(
            inputs["opex_total"], inputs["financing"], inputs["ga"],
            inputs["ships"])
        assert breakeven.value == pytest.approx(
            GOLDEN[issuer]["vessel_breakeven_TCE"]), issuer

        orderbook = mt.orderbook_to_fleet_ratio_pct(
            inputs["orderbook"], inputs["ships"])
        assert orderbook.value == pytest.approx(
            GOLDEN[issuer]["orderbook_to_fleet_ratio_pct"]), issuer


def test_unit_per_ship_per_class_and_breakeven_null_rules():
    """Unit: per-ship/per-class/breakeven и их null-правила — нет входа
    или нулевой знаменатель: null с причиной, не исключение и не ноль."""
    # per-class TCE: ноль рейсовых дней — denominator_zero
    m = mt.spot_TCE_per_day_by_class(1_000.0, 0)
    assert (m.value, m.null_reason) == (None, "denominator_zero")
    assert mt.spot_TCE_per_day_by_class(None, 10).null_reason == \
        "missing_data"

    # per-ship: судов нет — делить нельзя
    assert mt.revenue_per_ship_by_class(1_000.0, 0).null_reason == \
        "denominator_zero"
    assert mt.GA_per_ship_per_year(1_000.0, None).null_reason == \
        "missing_data"

    # breakeven: нет финансирования — missing; нет судов — denominator_zero
    assert mt.vessel_breakeven_TCE(1.0, None, 1.0, 10).null_reason == \
        "missing_data"
    assert mt.vessel_breakeven_TCE(1.0, 1.0, 1.0, 0).null_reason == \
        "denominator_zero"

    # утилизация: нет off-hire — missing; больше года в найме — невозможно
    assert mt.fleet_utilization_pct(None).null_reason == "missing_data"
    assert mt.fleet_utilization_pct(400.0).null_reason == \
        "negative_denominator"

    # маржа: нет OPEX — missing_data, а не ноль и не TCE
    assert mt.daily_vessel_margin(1_000.0, None).null_reason == \
        "missing_data"

    # диспетчер: единая точка расчёта по имени концепта
    m = mt.calculate_industry_measure(
        "bunker_spread_HSFO_VLSFO", hsfo_price_usd=550.0,
        vlsfo_price_usd=480.0)
    assert m.value == pytest.approx(70.0)
    with pytest.raises(KeyError):
        mt.calculate_industry_measure("no_such_metric")
    # все имена §«Специфичные метрики» известны диспетчеру
    for name in (
        "spot_TCE_per_day_by_class", "time_charter_TCE_per_day_by_class",
        "fleet_utilization_pct", "off_hire_days", "revenue_per_ship_by_class",
        "vessel_OPEX_per_day_by_class_and_age", "technical_OPEX_per_day",
        "G&A_per_ship_per_year", "daily_vessel_margin",
        "vessel_breakeven_TCE", "fleet_count_by_class", "average_fleet_age",
        "average_residual_years_by_class",
        "spot_vs_time_charter_exposure_pct", "orderbook_to_fleet_ratio_pct",
        "newbuilding_price_index_by_class",
        "secondhand_price_index_by_class", "scrapping_age_profile",
        "bunker_spread_HSFO_VLSFO", "CII_per_ship", "scrubber_fitted_pct",
        "IMO_2020_readiness_pct", "port_congestion_TEU_waiting",
        "idle_capacity_pct", "blank_sailings_pct",
    ):
        assert name in mt.known_measures(), name

    # мера — это Measure общего движка, свой класс не заводился
    assert isinstance(m, Measure)


def test_integration_segment_data_from_annual_report():
    """Интеграционный: segment disclosure годового отчёта (синтетический
    документ в raw store) -> табличный парсер -> per-class метрики.
    Живое получение по сети помечено отдельным integration-тестом
    и без RUSTERM_SEC_UA чисто пропускается."""
    from rusterm.parsers import parse_auto
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import RawRepo
    from rusterm.store.db import apply_migrations
    import shutil
    import sqlite3
    import tempfile

    doc = {
        "source": "synthetic",
        "note": "Синтетический сегментный отчёт танкерного флота.",
        "doc_kind": "table",
        "period_end": "2024-12-31",
        "tables": [{
            "table_name": "segment_revenue",
            "unit": "USD",
            "rows": [
                {"cells": [
                    {"concept": "vlcc_revenue", "value": "730000000"},
                    {"concept": "aframax_revenue", "value": "146000000"},
                ]},
            ],
        }],
    }
    raw = json.dumps(doc).encode()
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        raw_repo = RawRepo(paths, conn)
        obj = raw_repo.put(raw, provider="synthetic",
                           block="fundamentals")
        result = parse_auto(raw, {"doc_kind": "table"},
                            {"issuer_id": "i1",
                             "source_ref": obj.sha256})
        conn.close()
        by_concept = {f["concept"]: f["value"] for f in result.facts}

        vlcc = mt.revenue_per_ship_by_class(
            float(by_concept["vlcc_revenue"]), 80)
        assert vlcc.value == pytest.approx(9_125_000.0)
        aframax = mt.revenue_per_ship_by_class(
            float(by_concept["aframax_revenue"]), 20)
        assert aframax.value == pytest.approx(7_300_000.0)
    finally:
        shutil.rmtree(tmpdir)

# Живой вариант сегментного фетча появится вместе с EDGAR-провайдером
# (U5, recorded payloads): пока клиентского кода сети нет, тест-заглушка
# запрещена — она либо лжёт, либо делает настоящий запрос контактом
# пользователя. Офлайн-интеграционный тест выше закрывает пункт «Тесты»
# документа: segment data из годового отчёта читается из сохранённого
# сырья (N7: узлы 1,3,6,7,8,9 офлайн).


def test_u12_registry_uses_document_names_verbatim():
    """TASK-8 U12.1: имена из «Специфичные метрики» зарегистрированы
    дословно; реестр отличается от документа только на average_fleet_age
    (разрешённое дополнение)."""
    import re
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[1] / "docs"
           / "industry-metrics" / "maritime-tanker.md").read_text(
        encoding="utf-8")
    section = doc.split("## Специфичные метрики")[1].split("## Источники")[0]
    doc_names = set(re.findall(r"\*\*(.+?)\*\*", section))
    known = set(mt.known_measures())
    assert doc_names <= known, f"не зарегистрированы: {doc_names - known}"
    # вне документа остаются только имена функций Python и дополнение:
    # семь *_pct, fleet_age_histogram и average_fleet_age
    assert known - doc_names == {
        "fleet_utilization_pct", "spot_vs_time_charter_exposure_pct",
        "orderbook_to_fleet_ratio_pct", "scrubber_fitted_pct",
        "IMO_2020_readiness_pct", "idle_capacity_pct", "blank_sailings_pct",
        "fleet_age_histogram", "average_fleet_age",
    }
    # алиас считает то же, что и имя функции
    a = mt.calculate_industry_measure("fleet_utilization_%",
                                      off_hire_days=36.5)
    b = mt.calculate_industry_measure("fleet_utilization_pct",
                                      off_hire_days=36.5)
    assert a.value == b.value == pytest.approx(90.0)
