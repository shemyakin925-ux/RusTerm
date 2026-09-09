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

CONCEPT_MAP_VERSION = "us-gaap.v3"  # v3: + теги-преемники capex/d_and_a (TASK-12 Y1)

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
                "DepreciationAndAmortization",
                # преемник (TASK-12 Y1): TSLA и другие; добавлен в конец —
                # приоритет прежних тегов не тронут
                "Depreciation"),
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
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",
              # преемник (TASK-12 Y1): AMZN; после прежнего тега —
              # эмитент, сдающий оба, продолжает получать прежний
              "PaymentsToAcquireProductiveAssets"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "st_investments": ("ShortTermInvestments",),
    "total_assets": ("Assets",),
    "total_equity": ("StockholdersEquity",),
    # капитал включая неконтролирующую долю (TASK-10 W3): НЕ синоним
    # total_equity и никогда с ним не суммируется; формулы пока нет —
    # факт перестаёт быть невидимым
    "total_equity_incl_nci": (
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",),
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


# ── Второй словарь: IFRS (TASK-18 G3, §0.2) ─────────────────────────────
# Каждое имя взято решением по живым payload'ам Royal Bank, BP,
# AstraZeneca (Bank of Montreal и Canadian Natural несут те же ядерные
# теги). Ни одного тега сверх таблицы; два тега не суммируются; forbidden
# lookalikes (см. тест) намеренно отсутствуют — они дают неверное число
# там, где сейчас честная дыра.

CONCEPT_MAP_VERSION_IFRS = "ifrs-full.v1"

CONCEPT_MAP_IFRS: dict[str, tuple[str, ...]] = {
    "revenue": ("Revenue", "RevenueFromContractsWithCustomers"),
    "net_income": ("ProfitLossAttributableToOwnersOfParent", "ProfitLoss"),
    "operating_income": ("ProfitLossFromOperatingActivities",),
    "gross_profit": ("GrossProfit",),
    "pretax_income": ("ProfitLossBeforeTax",),
    "income_tax": ("IncomeTaxExpenseContinuingOperations",),
    "d_and_a": ("DepreciationAndAmortisationExpense",
                "AdjustmentsForDepreciationAndAmortisationExpense"),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "total_equity": ("EquityAttributableToOwnersOfParent",),
    "total_equity_incl_nci": ("Equity",),
    "cash": ("CashAndCashEquivalents",),
    "ocf": ("CashFlowsFromUsedInOperatingActivities",),
    "capex": ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",),
    "interest_expense": ("FinanceCosts",),
    "shares_diluted": ("AdjustedWeightedAverageShares",),
}

_IFRS_TAG_TO_CONCEPT: dict[str, str] = {
    tag: concept
    for concept, tags in CONCEPT_MAP_IFRS.items()
    for tag in tags
}

_IFRS_PRIORITY: dict[str, dict[str, int]] = {
    concept: {tag: rank for rank, tag in enumerate(tags)}
    for concept, tags in CONCEPT_MAP_IFRS.items()
}


def canonical_for(local_tag: str, taxonomy: str = "us-gaap") -> str | None:
    """Каноническое имя для локального тега данной таксономии; None —
    тег вне карты: такой факт не выбрасывается, а остаётся
    неотображённым. Дефолт us-gaap: все существующие вызовы не меняют
    поведения."""
    if not local_tag:
        return None
    if taxonomy == "ifrs-full":
        return _IFRS_TAG_TO_CONCEPT.get(local_tag)
    return _TAG_TO_CONCEPT.get(local_tag)


def map_version(taxonomy: str = "us-gaap") -> str:
    """Версия карты таксономии — для concept_map_version факта."""
    return CONCEPT_MAP_VERSION_IFRS if taxonomy == "ifrs-full" \
        else CONCEPT_MAP_VERSION


def priority_rank_ifrs(concept: str, local_tag: str) -> int:
    """Ранг IFRS-тега внутри концепта (см. priority_rank)."""
    return _IFRS_PRIORITY.get(concept, {}).get(local_tag, 1 << 30)


def strip_taxonomy(concept: str) -> tuple[str, str]:
    """'us-gaap:Revenues' -> ('us-gaap', 'Revenues'); без префикса —
    ('', concept)."""
    if ":" in concept:
        taxonomy, local = concept.split(":", 1)
        return taxonomy, local
    return "", concept


def priority_rank(concept: str, local_tag: str,
                  taxonomy: str = "us-gaap") -> int:
    """Ранг тега внутри концепта (0 — самый приоритетный). Неизвестный
    тег получает ранг за пределами таблицы. Таксономия выбирает таблицу
    приоритетов (us-gaap / ifrs-full, TASK-18 G3)."""
    if taxonomy == "ifrs-full":
        return _IFRS_PRIORITY.get(concept, {}).get(local_tag, 1 << 30)
    return _PRIORITY.get(concept, {}).get(local_tag, 1 << 30)
