"""TASK-18 G3+G4: второй словарь ifrs-full.v1 и таксономия из payload.

- каждый тег §0.2 отображается под ifrs-full; шесть forbidden lookalikes
  отображаются в None (они дают неверное число там, где сейчас честная
  дыра); st_investments не имеет IFRS-тега вовсе;
- us-gaap-карта байт-в-байт та же, что на origin/main (ruling 1);
- payload с двумя таксономиями парсится под us-gaap (ruling 2);
- rusterm/formulas.py байт-в-байт равен origin/main (механический страж).
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import subprocess

from rusterm.normalize.concepts import (
    CONCEPT_MAP,
    CONCEPT_MAP_IFRS,
    CONCEPT_MAP_VERSION,
    CONCEPT_MAP_VERSION_IFRS,
    canonical_for,
)

_FORBIDDEN_LOOKALIKES = (
    "RevenueFromInterest",
    "InsuranceRevenue",
    "OtherRevenue",
    "AccountingProfit",
    "CurrentTaxExpenseIncome",
    "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss",
    "WeightedAverageShares",
    "PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets",
)


def test_every_named_ifrs_tag_maps_to_its_concept():
    expected = {
        "Revenue": "revenue",
        "RevenueFromContractsWithCustomers": "revenue",
        "ProfitLossAttributableToOwnersOfParent": "net_income",
        "ProfitLoss": "net_income",
        "ProfitLossFromOperatingActivities": "operating_income",
        "GrossProfit": "gross_profit",
        "ProfitLossBeforeTax": "pretax_income",
        "IncomeTaxExpenseContinuingOperations": "income_tax",
        "DepreciationAndAmortisationExpense": "d_and_a",
        "AdjustmentsForDepreciationAndAmortisationExpense": "d_and_a",
        "Assets": "total_assets",
        "Liabilities": "total_liabilities",
        "EquityAttributableToOwnersOfParent": "total_equity",
        "Equity": "total_equity_incl_nci",
        "CashAndCashEquivalents": "cash",
        "CashFlowsFromUsedInOperatingActivities": "ocf",
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities":
            "capex",
        "FinanceCosts": "interest_expense",
        "AdjustedWeightedAverageShares": "shares_diluted",
    }
    for tag, concept in expected.items():
        assert canonical_for(tag, "ifrs-full") == concept, tag
    assert set(expected) == {t for tags in CONCEPT_MAP_IFRS.values()
                             for t in tags}, "карта != таблица §0.2"
    assert CONCEPT_MAP_VERSION_IFRS == "ifrs-full.v1"


def test_forbidden_lookalikes_map_to_none():
    for tag in _FORBIDDEN_LOOKALIKES:
        assert canonical_for(tag, "ifrs-full") is None, tag


def test_st_investments_has_no_ifrs_tag():
    assert "st_investments" not in CONCEPT_MAP_IFRS


def test_canonical_for_default_keeps_us_gaap_behaviour():
    assert canonical_for("Revenue") is None          # us-gaap: тега нет
    assert canonical_for("Revenue", "ifrs-full") == "revenue"
    assert canonical_for(
        "RevenueFromContractWithCustomerExcludingAssessedTax") == "revenue"
    assert CONCEPT_MAP_VERSION == "us-gaap.v3"


def test_us_gaap_map_is_byte_identical_to_task_start():
    """ruling 1: карта us-gaap не меняется. Эталон — голова старта
    TASK-18 (origin/main не содержит этот файл вовсе: дерево main
    устарело, см. Disputed REPORT-18)."""
    old_src = subprocess.run(
        ["git", "show", "23737a7:rusterm/normalize/concepts.py"],
        capture_output=True, text=True, check=True).stdout
    namespace: dict = {}
    exec(compile(old_src, "task_start_concepts.py", "exec"), namespace)
    assert namespace["CONCEPT_MAP"] == CONCEPT_MAP
    assert namespace["CONCEPT_MAP_VERSION"] == CONCEPT_MAP_VERSION


def test_formulas_py_matches_era_baseline():
    """G4 (обновлён ТЗ-24 N1): формулы заморожены от эры к эре.
    Эталон прежней эры (23737a7) умер вместе с границей TASK-18: N1
    прямо требует реализовать hhi в formulas.py. Базовая линия —
    sha256 файла в tests/data/formulas_baseline.sha256; обновляется
    ТОЛЬКО коммитом своей задачи с учётом в отчёте."""
    baseline = (ROOT / "tests" / "data"
                / "formulas_baseline.sha256").read_text().strip()
    current = hashlib.sha256(
        open("rusterm/formulas.py", "rb").read()).hexdigest()
    assert current == baseline, (
        "formulas.py изменился вне задачи своей эры — обновите "
        "baseline тем же коммитом и учтите замену в отчёте")


def test_g4_payload_taxonomy_us_gaap_wins_and_ifrs_parses():
    """G4: парсер разбирает ту таксономию, которую несёт payload; обе —
    побеждает us-gaap; ifrs-full-only payload даёт канонические
    концепты с версией ifrs-full.v1."""
    from rusterm.parsers import CompanyFactsParser

    both = {
        "cik": 1000275,
        "facts": {
            "us-gaap": {"Revenues": {"units": {"USD": [
                {"end": "2025-12-31", "start": "2025-01-01", "val": 100,
                 "accn": "a1", "form": "10-K", "filed": "2026-02-01"}]}}},
            "ifrs-full": {"Revenue": {"units": {"USD": [
                {"end": "2025-12-31", "start": "2025-01-01", "val": 999,
                 "accn": "a2", "form": "40-F", "filed": "2026-03-01"}]}}},
        },
    }
    from rusterm.pipeline import apply_concept_map
    parser = CompanyFactsParser()
    parsed = parser.parse(json.dumps(both).encode(), {"source_ref": "sha-x"})
    assert [f["concept"] for f in parsed.facts] == ["us-gaap:Revenues"], \
        "us-gaap не победил"
    fact = parsed.facts[0]
    apply_concept_map(fact)
    assert fact["canonical_concept"] == "revenue"
    assert fact["concept_map_version"] == "us-gaap.v3"
    assert "/facts/us-gaap/" in fact["locator"]["json_pointer"]

    ifrs_only = {
        "cik": 1000275,
        "facts": {"ifrs-full": {"Revenue": {"units": {"USD": [
            {"end": "2025-12-31", "start": "2025-01-01", "val": 100,
             "accn": "a1", "form": "40-F", "filed": "2026-02-01"}]}}},
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {
                "shares": [{"end": "2025-12-31", "val": 5,
                            "accn": "a1", "filed": "2026-02-01"}]}}}},
    }
    parsed = parser.parse(json.dumps(ifrs_only).encode(),
                          {"source_ref": "sha-y"})
    concepts = {}
    for f in parsed.facts:
        apply_concept_map(f)
        concepts[f["concept"]] = f
    assert "ifrs-full:Revenue" in concepts
    assert concepts["ifrs-full:Revenue"]["canonical_concept"] == "revenue"
    assert concepts["ifrs-full:Revenue"]["concept_map_version"] == \
        "ifrs-full.v1"
    # "/facts/ifrs-full/" в указателе — таксономия видна без миграции
    assert "/facts/ifrs-full/" in \
        concepts["ifrs-full:Revenue"]["locator"]["json_pointer"]
