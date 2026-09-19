# REPORT-54 — TASK-54 (X1: operating_income у CNQ — проверено payload-ом)

Round 62. Outcome **(б)**: соответствия нет — отказ остаётся и уже
точен; перечень проверенных тегов ниже, чтобы следующая ночь не искала
заново. Network 0, model 0.

## Done

- **X1, исход (б)**: все 14 тегов IFRS сохранённого companyfacts CNQ
  проверены payload-ом (таблица ниже) — ни один не отображается в
  operating_income; отказ остаётся и точен. Закрепляющий тест
  `test_cnq_operating_income_absence_is_proven` зажжётся, если CNQ
  подаст операционную прибыль под новым тегом. Golden не менялся.

## X1 — проверка payload-ом (исход (б))

Утверждение переписи «concept absent from all filings» проверено по
сохранённому companyfacts (`tests/data/edgar/companyfacts_m6_CNQ.json`),
не по памяти. **Все 14 тегов IFRS, которые подал CNQ**, с числом
фактов и периодами:

| тег (ifrs-full) | canonical | фактов | периоды |
|---|---|---|---|
| AdjustedWeightedAverageShares | shares_diluted | 6 | 2020-12-31..2025-12-31 |
| AdjustmentsForDepreciationAndAmortisationExpense | d_and_a | 6 | 2020-12-31..2025-12-31 |
| Assets | total_assets | 6 | 2020-12-31..2025-12-31 |
| CashAndCashEquivalents | cash | 6 | 2020-12-31..2025-12-31 |
| CashFlowsFromUsedInOperatingActivities | ocf | 6 | 2020-12-31..2025-12-31 |
| DepreciationAndAmortisationExpense | d_and_a | 6 | 2020-12-31..2025-12-31 |
| Equity | total_equity_incl_nci | 6 | 2020-12-31..2025-12-31 |
| FinanceCosts | interest_expense | 6 | 2020-12-31..2025-12-31 |
| IncomeTaxExpenseContinuingOperations | tax_expense | 6 | 2020-12-31..2025-12-31 |
| Liabilities | total_liabilities | 6 | 2020-12-31..2025-12-31 |
| ProfitLoss | net_income | 6 | 2020-12-31..2025-12-31 |
| ProfitLossBeforeTax | pretax_income | 6 | 2020-12-31..2025-12-31 |
| PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities | capex | 4 | 2015-12-31..2018-12-31 |
| Revenue | revenue | 6 | 2020-12-31..2025-12-31 |

 us-gaap-секция в payload пуста; dei — только идентификаторы.

Кандидаты на операционную прибыль проверены и отклонены:
- `ProfitLossFromOperatingActivities` — единственный «прямой» тег
  IFRS — **CNQ никогда не подавал** (подавал NGGTF, там он и работает);
- вывод `revenue − opex` невозможен: операционных расходов
  (`OperatingExpenses`, `CostOfGoodsAndServicesSold`, …) в payload нет;
- вывод `pretax_income + finance_costs` (EBIT) — не тег, а смена
  семантики формулы: у нефтегазовой отчётности pretax_income несёт
  прочие доходы/расходы и обесценения, EBIT получился бы другим
  показателем под именем operating_income. Не делалось — это решение
  продукта, не соответствие тега.

Итог: четыре отказа (operating_margin, ebitda, nopat,
interest_coverage) остаются `missing_data: operating_income` — причина
называет концепт точно. Закреплено тестом
`tests/test_task49_census.py::test_cnq_operating_income_absence_is_proven`:
если CNQ подаст операционную прибыль под новым тегом, canonical_for
начнёт отображение и тест зажжётся — сигнал пересмотреть перепись.
`golden_census_task49.json` не менялся (отказы закреплены как есть),
`tests/test_task49_census.py` зелёный (5 passed).

## X2

Не брался: до стопа меньше часа после закрытия X1, пункт меняет логику
отказов снапшота (новый токен в словаре + различение «никогда не
подавал / подавали давно» в snapshot.py) — не успевает целиком, а по
условию задачи берётся только при закрытом X1 целиком И остатке
времени. Перечень для следующей смены: CNQ `fcf` (capex до
2018-12-31), NGGTF `ebitda` (d_and_a до 2018-09-30).

## Blocked

- Nothing.

## Disputed

- (empty)

## What not to trust

- Проверка — по ЗАПИСАННОМУ payload (круг m6). Свежий EDGAR-срез CNQ
  может содержать другие теги; фикстура — воспроизводимая база
  переписи.

## HANDOFF

Status: DONE
Arrival state: selfcheck SELFCHECK OK on the first run of the round
Items done: X1 исход (б) — payload-проверка всех 14 тегов, перечень в отчёте, закрепляющий тест; X2 не брался (см. выше)
Items not done: X2 — перенесено с перечнем мест
Acceptance: этот коммит прошёл хук «пройдено 13, провалено 0», exit 0
Tests: census suite 5 passed (включая новый X1-тест)
Guards: none touched
Schema: unchanged (45)
Network: 0 requests
Model: 0 llm_calls
Secrets: no key values anywhere
Pushed: yes (with the hand)
Questions for the coordinator:
1. derive operating_income = pretax_income + finance_costs для нефтегазовых IFRS-эмитентов — продуктовое решение; если да, это пункт на отдельную смену с золотыми значениями
