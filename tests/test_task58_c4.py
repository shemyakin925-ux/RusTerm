"""ТЗ-58 C4: знак 3.08 нормализует карта (cvm-dfp.v2), clip() снят.

Дефект (вердикт Q2 по REPORT-57): DRE подаёт налог вычетом со знаком
минус, effective_tax = clip(tax/pretax, 0, 0.5) зажимал -0.2381 в
«зелёный» 0.0 — мера выдумывала значение. Теперь: карта приводит знак
(cvm-dfp.v2, исходное значение — в locator.raw_value), а ставка вне
полосы [0, 0.5] — отказ jurisdiction_rate с числом, не 0.0 и не 0.5.
"""
from __future__ import annotations

import pytest

from rusterm.formulas import effective_tax_rate
from rusterm.pipeline import apply_concept_map
from rusterm.reasons import is_known_reason

from tests.test_task57_br_census import _census_rows, br_app


def test_map_normalizes_tax_sign_and_records_version():
    """Карта cvm-dfp.v2 приводит знак вычета 3.08: value — модуль,
    чем нормализовано — версия карты на факте; исходное знаковое
    значение остаётся на месте (в локаторе его несёт raw_value)."""
    fact = {"concept": "cvm-dfp:3.08", "value": "-4640375000.0"}
    assert apply_concept_map(fact) == 0
    assert fact["canonical_concept"] == "tax_expense"
    assert fact["value"] == "4640375000.0"
    assert fact["concept_map_version"] == "cvm-dfp.v2"


def test_map_leaves_positive_tax_and_other_lines_untouched():
    """Положительный налог не трогается; другие строки карты (и вне
    карты) знак не меняют: нормализация — только 3.08 с минусом."""
    pos = {"concept": "cvm-dfp:3.08", "value": "4640375000.0"}
    apply_concept_map(pos)
    assert pos["value"] == "4640375000.0"
    rev = {"concept": "cvm-dfp:3.01", "value": "-5.0"}
    assert apply_concept_map(rev) == 0
    assert rev["value"] == "-5.0"
    outside = {"concept": "cvm-dfp:3.04", "value": "-1.0"}
    assert apply_concept_map(outside) == 1
    assert outside["value"] == "-1.0"
    junk = {"concept": "cvm-dfp:3.08", "value": "abc"}
    apply_concept_map(junk)
    assert junk["value"] == "abc"


def test_tax_rate_outside_band_refuses_instead_of_clipping():
    """clip() снят: отрицательная ставка и ставка выше 0.5 — отказ
    jurisdiction_rate с числом в продолжении, не выдуманные 0.0/0.5."""
    value, reason = effective_tax_rate(-4640375000.0, 19487327000.0)
    assert value is None
    assert reason == "jurisdiction_rate: rate=-0.2381"
    assert is_known_reason(reason)
    value, reason = effective_tax_rate(3000.0, 4000.0)
    assert value is None
    assert reason == "jurisdiction_rate: rate=0.7500"
    assert is_known_reason(reason)
    value, reason = effective_tax_rate(1000.0, 4000.0)
    assert value == 0.25 and reason is None
    value, reason = effective_tax_rate(1000.0, 0)
    assert value is None and reason == "denominator_zero"
    value, reason = effective_tax_rate(1000.0, -4000.0)
    assert value is None and reason == "jurisdiction_rate"
    value, reason = effective_tax_rate(None, 4000.0)
    assert value is None and reason == "missing_data"


def test_ambev_true_rate_replaces_invented_zero(br_app):
    """Сквозной случай на записанном наборе: effective_tax AMBEV —
    настоящая ставка 0.23812270405274155 (≈23.81%), а не 0.0; налоговый
    факт в базе несёт нормализованный модуль и версию карты v2."""
    import sqlite3

    root, paths = br_app
    rows = _census_rows(root)
    assert rows["effective_tax"] == {
        "value": "0.23812270405274155", "reason": None}
    conn = sqlite3.connect(str(paths.db_path))
    conn.row_factory = sqlite3.Row
    try:
        fact = conn.execute(
            """SELECT value, concept_map_version FROM fact
               WHERE canonical_concept='tax_expense'
                 AND period_end='2024-12-31'""").fetchone()
        assert fact is not None
        assert fact["value"] == "4640375000.0"
        assert fact["concept_map_version"] == "cvm-dfp.v2"
    finally:
        conn.close()
