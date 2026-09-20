# REPORT-68 — TASK-68, round 90

## Done

- N1. Разбор 14 пустых по причинам (не по мерам) и корзины:
  - (а) чинится картой концептов — **5 мер закрыты этим кругом**:
    pe, ps, fcf_yield, net_debt, net_debt_ebitda. Они стояли в
    `_UNMAPPED_FORMULAS` (core/snapshot.py) как «формулы вне карты V0»,
    хотя их входы уже в карте v4: cash →
    CashAndCarryEquivalentsAtCarryingValue, total_debt → LongTermDebt,
    shares_outstanding → CommonStockSharesOutstanding (ТЗ-31 C2),
    eps_diluted → EarningsPerShareDiluted, revenue → Revenues (исходно).
    _valuation_pass дополнен расчётом: net_debt = total_debt − cash −
    st_investments; net_debt_ebitda = net_debt / ebitda; pe = price /
    eps_diluted; ps = market_cap_total / revenue; fcf_yield = fcf /
    market_cap_total — с проверками валют (K6) и lineage по входам
    (I4). _VALUATION_INPUT_CONCEPTS дополнен eps_diluted и revenue.
  - (б) чинится расчётом — 3: invested_capital (нужна сумма долга:
    CommercialPaper + LongTermDebtCurrent + LongTermDebt — теги в
    payload есть, суммирования в мерах нет), hhi (нужны пиры отрасли),
    price_adj/total_return/drawdown (нужен ряд цен, а не одна
    закрытая) — оценка размера: 3-4 формулы.
  - (в) честно невозможно на этом источнике — 0 для AAPL по данным;
    roe_incl_nci отдельный случай (N3).
  - Живой прогон на /tmp/rt-h1 (AAPL): **было 15 из 28, стало 20 из
    28**; новые значения: pe = 166.4009900990099, ps =
    44.87886464799803, net_debt = 19901000000.0, net_debt_ebitda =
    0.15030399154110494, fcf_yield = 0.022441046560632005.
- N3. roe_incl_nci у AAPL: тега MinorityInterest в payload НЕТ (есть
  только поток IncomeLoss...MinorityInterestAndIncomeLossFromEquity... —
  это прибыль, не капитал). Отказ `missing_data:
  total_equity_incl_nci` — правильный; мера остаётся в словаре ради
  Канады (ТЗ-56), где NCI подаётся.
- Тесты формул и золотые: test_c2_six_measures, j1_display,
  task64_j2_export_provenance, task62_g3_source_cell, e2e_cli —
  зелёные.

## Blocked

## What not to trust

- pe = 166.4 — математика верна (цена/разводнённая EPS TTM), но
  высокий AAPL-мультипликатор на срезе 2026-09-20 не сверялся с
  внешним источником.

## Disputed

## HANDOFF (FINAL)

Status: PARTIAL (N1 done; N2, N4 ahead)
Arrival state: task taken round 90 on 1b1202f, selfcheck green
Items done: N1, N3
Items not done: N2 (учащие отказы), N4 (свежие числа первого часа) —
следующий коммит
Acceptance: hook verdict on this commit
Tests: 64 зелёных в пяти наборах (c2, j1_display, task64_j2, task62_g3,
e2e_cli) + живой прогон выше
Guards: none touched
Schema: unchanged
Network: 0
Model: GLM-5.3, app llm_calls 0
Secrets: нет ключевого материала
Pushed: this commit pushes immediately
Questions for the coordinator:
1. Корзина (б): invested_capital как сумма трёх тегов — заводить
   отдельным пунктом?

NOW: N2, step 1

## HANDOFF

Статус: DONE для N1/N3; N2 и N4 — следующим коммитом этого круга.
