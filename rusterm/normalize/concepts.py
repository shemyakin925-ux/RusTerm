"""Карта us-gaap-тегов на канонические концепты словаря
(TASK-9 V0, docs/data-dictionary.md §2, CONCEPT_MAP_VERSION = us-gaap.v1).

Таблица — авторитетная: не расширять, не переупорядочивать, не
придумывать теги. Левая колонка — имена словаря, правая — us-gaap
локальные имена в порядке приоритета: первый тег, у которого есть факт
для эмитента/периода/единицы, выигрывает.

Правила: два тега никогда не суммируются; USD-тег не закрывает
концепт в shares; total_debt/shares_outstanding/price_close/price_adj
намеренно отсутствуют (составное и инструментные — не эмитентные).
"""
from __future__ import annotations

CONCEPT_MAP_VERSION = "us-gaap.v1"

CONCEPT_MAP: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "cogs": ("CostOfGoodsAndServicesSold", "CostOfRevenue",
             "CostOfGoodsSold"),
    "gross_profit": ("GrossProfit",),
    "opex": ("OperatingExpenses",),
    "operating_income": ("OperatingIncomeLoss",),
    "d_and_a": ("DepreciationDepletionAndAmortization",
                "DepreciationAmortizationAndAccretionNet",
                "DepreciationAndAmortization"),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "pretax_income": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ),
    "tax_expense": ("IncomeTaxExpenseBenefit",),
    "interest_expense": ("InterestExpense", "InterestExpenseDebt"),
    "eps_diluted": ("EarningsPerShareDiluted",),
    "shares_diluted": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "ocf": ("NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "st_investments": ("ShortTermInvestments",),
    "total_assets": ("Assets",),
    "total_equity": ("StockholdersEquity",),
    "minority_interest": ("MinorityInterest",),
    "preferred_equity": ("PreferredStockValue",),
    "dps": ("CommonStockDividendsPerShareDeclared",),
    "buyback_amount": ("PaymentsForRepurchaseOfCommonStock",),
}

# тег -> канонический концепт
_TAG_TO_CONCEPT: dict[str, str] = {
    tag: concept
    for concept, tags in CONCEPT_MAP.items()
    for tag in tags
}

# приоритет внутри концепта: меньше rank — выше приоритет
_PRIORITY: dict[str, dict[str, int]] = {
    concept: {tag: rank for rank, tag in enumerate(tags)}
    for concept, tags in CONCEPT_MAP.items()
}

# канонические имена сами на себя: синтетические документы уже
# говорят на языке словаря, их факты каноничны по построению
for _concept in CONCEPT_MAP:
    _TAG_TO_CONCEPT.setdefault(_concept, _concept)
    _PRIORITY[_concept].setdefault(_concept, len(_PRIORITY[_concept]))


def canonical_for(local_tag: str) -> str | None:
    """Каноническое имя для us-gaap локального тега; None — тег вне
    карты: такой факт не выбрасывается, а остаётся неотображённым."""
    if not local_tag:
        return None
    return _TAG_TO_CONCEPT.get(local_tag)


def priority_rank(concept: str, local_tag: str) -> int:
    """Ранг тега внутри концепта (0 — самый приоритетный). Неизвестный
    тег получает ранг за пределами таблицы."""
    return _PRIORITY.get(concept, {}).get(local_tag, 1 << 30)


def strip_taxonomy(concept: str) -> tuple[str, str]:
    """'us-gaap:Revenues' -> ('us-gaap', 'Revenues'); без префикса —
    ('', concept)."""
    if ":" in concept:
        taxonomy, local = concept.split(":", 1)
        return taxonomy, local
    return "", concept
