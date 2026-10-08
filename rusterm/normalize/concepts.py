"""Карта us-gaap-тегов на канонические концепты словаря
(TASK-9 V0, docs/data-dictionary.md §2, CONCEPT_MAP_VERSION = us-gaap.v1).

Таблица — авторитетная: не расширять, не переупорядочивать, не
придумывать теги. Левая колонка — имена словаря, правая — us-gaap
локальные имена в порядке приоритета: первый тег, у которого есть факт
для эмитента/периода/единицы, выигрывает.

Правила: два тега никогда не суммируются; USD-тег не закрывает
концепт в shares; price_close/price_adj намеренно отсутствуют
(инструментные — не эмитентные). Исключение ТЗ-31 C2 (каждый тег — с
payload-доказательством из companyfacts AAPL, 14.09.2026):
shares_outstanding <- us-gaap:CommonStockSharesOutstanding (144
факта, 14 608 963 000 shares на 2026-06-27, 10-Q) — эмитент
раскрывает класс по строке баланса; total_debt <-
us-gaap:LongTermDebt (54 факта, 82 300 000 000 USD на 2026-06-27) —
ОДИН тег «весь сроковой долг» эмитента (коммерческие бумаги не
входят: суммировать два тега запрещено, недоучёт назван здесь);
st_investments <- us-gaap:MarketableSecuritiesCurrent (62 факта,
22 855 000 000 USD на 2026-06-27).

Порядок us-gaap vs dei (ТЗ-78 Y2): если эмитент подаёт ОБА —
us-gaap:CommonStockSharesOutstanding (строка баланса по классу) и
dei:EntityCommonStockSharesOutstanding (обложка 10-K, сущность в
целом) — берётся us-gaap. Правило, не вкус: us-gaap несёт разбивку
по классу и привязан к дате отчётного периода, dei — одна агрегированная
строка с датой обложки, обычно на 30 дней позднее end. Механика
приоритета — в `_PRIORITY` против `CONCEPT_MAP_DEI`: таксономия dei
смещена на _DEI_RANK_OFFSET (=1000), поэтому us-gaap-ранг 0 всегда
меньше любого dei-ранга, и выбор делает `min(rank)`.
"""
from __future__ import annotations

CONCEPT_MAP_VERSION = "us-gaap.v7"  # v7: + interest_expense <- InterestExpenseNonoperating (MSFT, T с 2024); − OtherCostOfOperatingRevenue из cogs (частичная строка AT&T: без себестоимости оборудования валовая прибыль завышена на ~20 млрд; сверка с Yahoo 08.10)
# v6: + cogs <- CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization (AA), OtherCostOfOperatingRevenue (T) — ТЗ-130 K2, payload-доказательства в REPORT-130

# Отозванные теги: были в карте, оказались не тем концептом. reparse
# снимает с их фактов каноническое имя (дописывание имени само этого не
# сделает — оно трогает только неотображённые факты).
# us-gaap.v7: OtherCostOfOperatingRevenue — у AT&T это «прочая»
# себестоимость (27,0 млрд за 2024) без строки оборудования, которую
# AT&T подаёт собственным тегом-расширением; как cogs она давала валовую
# прибыль 95 млрд против ~73 млрд по полной себестоимости.
WITHDRAWN_TAGS: dict[str, str] = {
    "us-gaap:OtherCostOfOperatingRevenue": "cogs",
}

CONCEPT_MAP: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "cogs": ("CostOfGoodsAndServicesSold", "CostOfRevenue",
             "CostOfGoodsSold",
             # ТЗ-130 K2: строка Alcoa «Cost of goods sold (exclusive of
             # expenses shown separately below)» — FY2021 9 153 000 000 USD,
             # 10-K; после прежних тегов — приоритет полных строк не тронут
             "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"),
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
    "interest_expense": ("InterestExpense", "InterestExpenseDebt",
                         # us-gaap.v7: преемник с таксономии 2024 — MSFT и
                         # AT&T подают процентные расходы им с FY2024/2024
                         "InterestExpenseNonoperating"),
    "eps_diluted": ("EarningsPerShareDiluted",),
    "shares_diluted": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "ocf": ("NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",
              # преемник (TASK-12 Y1): AMZN; после прежнего тега —
              # эмитент, сдающий оба, продолжает получать прежний
              "PaymentsToAcquireProductiveAssets"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "st_investments": ("ShortTermInvestments",
                       # ТЗ-31 C2: строка баланса «рыночные ценные
                       # бумаги (текущие)» — преемник ShortTermInvestments
                       "MarketableSecuritiesCurrent",
                       # ТЗ-108 W3: строка баланса CRM «рыночные ценные
                       # бумаги» (3 093 000 000 USD на 2026-07-31, 10-Q);
                       # без неё правило нулевых вложений занижало деньги
                       "AvailableForSaleSecuritiesDebtSecuritiesCurrent"),
    "total_assets": ("Assets",),
    "total_equity": ("StockholdersEquity",),
    # ТЗ-31 C2: весь сроковой долг ОДНИМ тегом эмитента (не сумма
    # двух тегов); коммерческие бумаги не входят — недоучёт назван
    "total_debt": ("LongTermDebt",
                   # ТЗ-108 W2: преемник у SMCI — весь долг одним тегом
                   # (4 056 148 000 USD на 2026-06-30, 10-K; LongTermDebt
                   # последний раз 2023-06-30). Ранг ниже LongTermDebt:
                   # эмитент, подающий оба, получает прежний
                   "DebtLongtermAndShorttermCombinedAmount"),
    # ТЗ-31 C2: акции в обращении по строке баланса эмитента
    "shares_outstanding": ("CommonStockSharesOutstanding",),
    # капитал включая неконтролирующую долю (TASK-10 W3): НЕ синоним
    # total_equity и никогда с ним не суммируется; формулы пока нет —
    # факт перестаёт быть невидимым
    "total_equity_incl_nci": (
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",),
    "minority_interest": ("MinorityInterest",),
    "preferred_equity": ("PreferredStockValue",),
    "dps": ("CommonStockDividendsPerShareDeclared",
            # ТЗ-139 B2: преемник у KO — эмитент с 2018 подаёт в XBRL
            # только выплаченное на акцию: Declared обрывается 2018-09-28,
            # CashPaid живёт до сегодняшнего (KO: 2025 год = 2,04 USD,
            # замер на копии базы; строка dps карточки пуста весь период).
            # Ранг ниже Declared: подающий оба (BAC и прочие) получает
            # прежнее объявленное значение
            "CommonStockDividendsPerShareCashPaid"),
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

# ТЗ-49 R2: income_tax переименован в tax_expense (ifrs-full.v2).
# Формулы мер читают tax_expense (us-gaap-словарь), а карта IFRS
# называла тот же экономический концепт income_tax — effective_tax
# отказывал «missing_data: tax_expense» при живом факте налоговых
# расходов (перепись отказов ТЗ-49: RY/BMO/CNQ/NGGTF, все четыре).
# Payload-доказательство тега (правило 9): IncomeTaxExpenseContinuingOperations —
# RY 12 фактов до 2026-01-31, CNQ 6 до 2025-12-31, NGGTF 6 до
# 2025-09-30 (companyfacts, tests/data/edgar/companyfacts_m6_*.json).
CONCEPT_MAP_VERSION_IFRS = "ifrs-full.v3"  # v3: + cogs <- CostOfSales по payload-доказательствам KSPI/VALE (ТЗ-97 Q4)

CONCEPT_MAP_IFRS: dict[str, tuple[str, ...]] = {
    "revenue": ("Revenue", "RevenueFromContractsWithCustomers"),
    "net_income": ("ProfitLossAttributableToOwnersOfParent", "ProfitLoss"),
    "operating_income": ("ProfitLossFromOperatingActivities",),
    "gross_profit": ("GrossProfit",),
    # ТЗ-97 Q4 (правило 9): cogs <- CostOfSales — payload-доказательства
    # companyfacts: KSPI 9 строк KZT (20-F, до 2025-12-31) и VALE 50
    # строк USD (20-F/6-K). Без него gross_profit и gross_margin
    # отказывали missing_data: cogs там, где себестоимость подана.
    # Dropped-входы названы в отчёте: capex у KSPI подан только тегом из
    # _FORBIDDEN_LOOKALIKES (TASK-18 G3: он складывает PP&E, нематериальные,
    # инвестиционное имущество и прочие внеоборотные — неверное число там,
    # где честная дыра), operating_income у KSPI не раскрывается вовсе.
    "cogs": ("CostOfSales",),
    "pretax_income": ("ProfitLossBeforeTax",),
    "tax_expense": ("IncomeTaxExpenseContinuingOperations",),
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

# ТЗ-97 Q4 (ТЗ-87 G3): смещение рангов IFRS — то же механическое правило,
# что у dei (_DEI_RANK_OFFSET), только со своим номером. Payload с обеими
# таксономиями теперь разбирается целиком (rusterm/parsers), и на один
# канонический концепт могут прийти два факта; смещение даёт us-gaap
# безусловный приоритет, а ifrs-full — приоритет над обложкой dei.
_IFRS_RANK_OFFSET = 100

_IFRS_PRIORITY: dict[str, dict[str, int]] = {
    concept: {tag: _IFRS_RANK_OFFSET + rank for rank, tag in enumerate(tags)}
    for concept, tags in CONCEPT_MAP_IFRS.items()
}


# ── Третий словарь: строки CVM DFP (ТЗ-56 Z2) ───────────────────────────
# Бразильский регулятор публикует годовые наборы DFP не XBRL-тегами, а
# строками CD_CONTA внутри CSV (dados.cvm.gov.br). Каждое имя взято по
# живой нарезке tests/data/cvm/dfp_2024_{dre,bpp}_slice.csv (выкачка
# 11.09: Petrobras 9512, Vale 4170, Ambev 23264; FY2024 + FY2023).
# Отсутствия НАМЕРЕННЫ, те же правила, что у IFRS выше:
#  - 3.05 «Resultado Antes do Resultado Financeiro» — EBIT-подобная
#    величина: под имя operating_income не ставится (вердикт ТЗ-55) —
#    operating_margin/ebitda/nopat/interest_coverage по BR отказывают
#    missing_data: operating_income;
#  - net_income только 3.11 «Lucro/Prejuízo Consolidado do Período» —
#    прибыль периода ВКЛЮЧАЯ доли НКД (аналог ProfitLoss); 3.09
#    (продолжающаяся деятельность) — не net_income;
#  - 2.03 «Patrimônio Líquido Consolidado» — капитал ВКЛЮЧАЯ
#    неконтролирующие доли: это total_equity_incl_nci, НЕ total_equity
#    (правило ТЗ-56 Z1): roe по BR отказывает missing_data:
#    total_equity, roe_incl_nci считает.
CONCEPT_MAP_VERSION_CVM = "cvm-dfp.v2"

CONCEPT_MAP_CVM: dict[str, tuple[str, ...]] = {
    "revenue": ("3.01",),
    "gross_profit": ("3.03",),
    "pretax_income": ("3.07",),
    "tax_expense": ("3.08",),
    "net_income": ("3.11",),
    "total_equity_incl_nci": ("2.03",),
}

_CVM_TAG_TO_CONCEPT: dict[str, str] = {
    tag: concept
    for concept, tags in CONCEPT_MAP_CVM.items()
    for tag in tags
}

_CVM_PRIORITY: dict[str, dict[str, int]] = {
    concept: {tag: rank for rank, tag in enumerate(tags)}
    for concept, tags in CONCEPT_MAP_CVM.items()
}

# cvm-dfp.v2 (ТЗ-58 C4, вердикт Q2; правило знака дописано ТЗ-91 B6):
# DRE подаёт налог (3.08) ВЫЧТОМ — со знаком минус, а словарь мер держит
# tax_expense как расход, поэтому canonical = −поданное для ВСЕЯКОЙ
# строки 3.08: положительно поданный вычет — это налоговый выигрыш, и
# расход от него отрицательный. Первая реализация флипала только
# отрицательные значения, и выигрыш оставался расходом. Карта приводит
# знак при отображении — той же породой, что масштаб ESCALA_MOEDA:
# провенанс — на самом факте, concept_map_version='cvm-dfp.v2' (чем
# нормализовано), исходное ЗНАКОВОЕ значение — в locator.raw_value
# (как подано).
_CVM_SIGN_NORMALIZED: frozenset[str] = frozenset({"tax_expense"})


# ── Четвёртый словарь: DEI (ТЗ-78 Y2) ───────────────────────────────────
# SEC's Data Types reference (dei = "Data Exchange and Interoperability"):
# cover-page facts the filer enters once per filing. Not an accounting
# taxonomy; a distinct concept route. Payload-доказательство тега
# (правило 9): dei:EntityCommonStockSharesOutstanding на VZ — 6 фактов
# (10-K, FY2020..FY2025), свежайший val=4 217 684 168 shares на
# end=2026-01-30 (filed 2026-02-17). Фикстура
# `tests/data/edgar/companyfacts_vz_shares.json` — тот же payload,
# собранный живым запросом 22.09.2026 (TASK-76 W5). VZ не подаёт
# us-gaap:CommonStockSharesOutstanding ни в одном 10-K, поэтому без
# этого тега shares_outstanding для VZ остаётся честным отсутствием.
CONCEPT_MAP_VERSION_DEI = "dei.v1"

CONCEPT_MAP_DEI: dict[str, tuple[str, ...]] = {
    "shares_outstanding": ("EntityCommonStockSharesOutstanding",),
}

_DEI_TAG_TO_CONCEPT: dict[str, str] = {
    tag: concept
    for concept, tags in CONCEPT_MAP_DEI.items()
    for tag in tags
}

# Смещение всех dei-рангов: us-gaap-ранг 0 (CommonStockSharesOutstanding)
# всегда меньше 1000+любой dei-ранг, поэтому если эмитент подаёт ОБА
# тега для одной меры — us-gaap выигрывает по `min(rank)` в snapshot.
_DEI_RANK_OFFSET = 1000

_DEI_PRIORITY: dict[str, dict[str, int]] = {
    concept: {tag: _DEI_RANK_OFFSET + rank for rank, tag in enumerate(tags)}
    for concept, tags in CONCEPT_MAP_DEI.items()
}

# ── Ручная карта метрик (ТЗ-92 C4) ─────────────────────────────────────────
# До C4 ручной импорт писал факты с canonical_concept = NULL (метрика —
# свободный текст модели), а читалка мер фильтрует по canonical_concept,
# поэтому ни одна ручная запись в формулу не попадала.
#
# Таблица авторитетна и выведена не из догадок о словаре модели: ключи —
# ровно имена словаря §2 с единицей «валюта», алиас — то же имя строчными
# буквами и с пробелами вместо подчёркиваний (нормализация ниже делает
# «Net_Income.» и «NET INCOME» одним алиасом). Синонимов («net profit»,
# «turnover», «cash flow») здесь нет намеренно: ни один записанный ответ
# их не доказывает (правило 9), а выдуманный синоним опаснее отсутствия —
# он превращает чужую строку в число словаря. Такая запись остаётся
# неотображённой фактом с NULL и видна счётчиком.
#
# Исключены поимённо (молча не опущено ничего):
#   price_close, price_adj — цена класса акций, её берёт ценовой канал;
#   shares_outstanding, shares_diluted — единица «шт.», не деньги;
#   eps_diluted, dps — «валюта/акцию», ставка на акцию за период; тот же
#   закон, по которому карта отвергает единицу-ставку «USD/day».
MANUAL_MAP_VERSION = "manual.v1"
MANUAL_MAP_EXCLUDED = ("price_close", "price_adj", "shares_outstanding",
                       "shares_diluted", "eps_diluted", "dps")

MANUAL_METRIC_MAP: dict[str, tuple[str, ...]] = {
    "revenue": ("revenue",),
    "cogs": ("cogs",),
    "gross_profit": ("gross profit",),
    "opex": ("opex",),
    "operating_income": ("operating income",),
    "d_and_a": ("d and a",),
    "net_income": ("net income",),
    "pretax_income": ("pretax income",),
    "tax_expense": ("tax expense",),
    "interest_expense": ("interest expense",),
    "ocf": ("ocf",),
    "capex": ("capex",),
    "cash": ("cash",),
    "st_investments": ("st investments",),
    "total_debt": ("total debt",),
    "total_assets": ("total assets",),
    "total_equity": ("total equity",),
    "total_equity_incl_nci": ("total equity incl nci",),
    "minority_interest": ("minority interest",),
    "preferred_equity": ("preferred equity",),
    "buyback_amount": ("buyback amount",),
}

_MANUAL_ALIAS_TO_CONCEPT: dict[str, str] = {
    alias: concept
    for concept, aliases in MANUAL_METRIC_MAP.items()
    for alias in aliases
}


def normalize_metric(metric: str) -> str:
    """Вид метрики для сравнения с картой: строчными, подчёркивания —
    пробелами, лишние пробелы и точка в конце убраны. Больше ничего:
    падежи, опечатки и чужие слова нормализация не выдумывает."""
    text = (metric or "").strip().lower().replace("_", " ")
    return " ".join(text.replace(".", " ").split())


def canonical_for_manual(metric: str) -> str | None:
    """Канонический концепт ручной записи; None — строка вне карты
    (факт остаётся, каноническое имя NULL: считается, не выбрасывается)."""
    return _MANUAL_ALIAS_TO_CONCEPT.get(normalize_metric(metric))


def normalize_sign_cvm(fact: dict) -> bool:
    """Привести знак величины к конвенции словаря мер (cvm-dfp.v2).
    True — правило применилось (строка 3.08 с разобранным числом): value
    заменено на −поданное, и знак меняется как в вычет, так и в
    выигрыш. Исходное знаковое значение остаётся в локаторе
    (raw_value). Других преобразований карта не делает."""
    if strip_taxonomy(fact.get("concept", "")) != ("cvm-dfp", "3.08"):
        return False
    try:
        value = float(fact.get("value"))
    except (TypeError, ValueError):
        return False
    # У нуля знак отбрасывается: -0.0 как строка — знак у величины,
    # знака которой нет.
    negated = -value
    fact["value"] = repr(0.0 if negated == 0 else negated)
    return True


def canonical_for(local_tag: str, taxonomy: str = "us-gaap") -> str | None:
    """Каноническое имя для локального тега данной таксономии; None —
    тег вне карты: такой факт не выбрасывается, а остаётся
    неотображённым. Дефолт us-gaap: все существующие вызовы не меняют
    поведения."""
    if not local_tag:
        return None
    if taxonomy == "ifrs-full":
        return _IFRS_TAG_TO_CONCEPT.get(local_tag)
    if taxonomy == "cvm-dfp":
        return _CVM_TAG_TO_CONCEPT.get(local_tag)
    if taxonomy == "dei":
        return _DEI_TAG_TO_CONCEPT.get(local_tag)
    return _TAG_TO_CONCEPT.get(local_tag)


def map_version(taxonomy: str = "us-gaap") -> str:
    """Версия карты таксономии — для concept_map_version факта."""
    if taxonomy == "ifrs-full":
        return CONCEPT_MAP_VERSION_IFRS
    if taxonomy == "cvm-dfp":
        return CONCEPT_MAP_VERSION_CVM
    if taxonomy == "dei":
        return CONCEPT_MAP_VERSION_DEI
    if taxonomy == "manual":
        return MANUAL_MAP_VERSION
    return CONCEPT_MAP_VERSION


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
    приоритетов (us-gaap / ifrs-full / cvm-dfp / dei, TASK-18 G3,
    ТЗ-56 Z2, ТЗ-78 Y2). Смещения `_IFRS_RANK_OFFSET` (=100) и
    `_DEI_RANK_OFFSET` (=1000) дают us-gaap безусловный приоритет, когда
    один концепт закрыт тегами разных таксономий (ТЗ-97 Q4)."""
    if taxonomy == "ifrs-full":
        return _IFRS_PRIORITY.get(concept, {}).get(local_tag, 1 << 30)
    if taxonomy == "cvm-dfp":
        return _CVM_PRIORITY.get(concept, {}).get(local_tag, 1 << 30)
    if taxonomy == "dei":
        return _DEI_PRIORITY.get(concept, {}).get(local_tag, 1 << 30)
    return _PRIORITY.get(concept, {}).get(local_tag, 1 << 30)
