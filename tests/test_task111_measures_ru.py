"""ТЗ-111 U2: имена мер и разделы — rusterm/measures_ru.py.

Done-when пункта: у каждого концепта словаря формул есть имя и раздел;
колонка 0 таблицы окна без подчёркиваний (проверка узора — на отчёте
look.py, см. отчёт задания).
"""
from __future__ import annotations

from rusterm.formulas import MEASURE_UNIT_KINDS
from rusterm.measures_ru import (MEASURE_RU, MEASURE_SECTIONS,
                                 SECTION_ORDER, measure_formula,
                                 measure_name, measure_section,
                                 measure_tooltip)


def test_every_dictionary_concept_has_name_and_section():
    """Полное покрытие: каждый концепт словаря формул имеет имя и раздел
    из шести названных; лишних имён нет."""
    concepts = set(MEASURE_UNIT_KINDS)
    missing_name = sorted(concepts - set(MEASURE_RU))
    assert not missing_name, f"концепты без имени: {missing_name}"
    missing_section = sorted(concepts - set(MEASURE_SECTIONS))
    assert not missing_section, f"концепты без раздела: {missing_section}"
    extra = sorted(set(MEASURE_RU) - concepts)
    assert not extra, f"имена без концепта: {extra}"
    assert set(MEASURE_SECTIONS.values()) <= set(SECTION_ORDER)


def test_names_have_no_underscores():
    """Колонка 0 — человеческие имена: подчёркиваний в них нет."""
    for concept, name in MEASURE_RU.items():
        assert "_" not in name, (concept, name)


def test_sections_are_the_six_named_ones():
    assert SECTION_ORDER == ("Оценка", "Рентабельность", "Эффективность",
                             "Долг", "Денежный поток", "Доходность")


def test_formula_lookup_reads_the_dictionary_doc():
    """Формула для подсказки разбирается из §3 словаря: у мер с формулой
    в документе — знак равенства и входы, у котировочной цены — пусто
    (она приходит от вендора)."""
    assert "gross_profit / revenue" in measure_formula("gross_margin")
    assert "total_debt" in measure_formula("net_debt")
    assert measure_formula("price_adj") == ""
    tooltip = measure_tooltip("gross_margin", "ratio")
    assert "gross_profit / revenue" in tooltip
    assert "единица: ratio" in tooltip
