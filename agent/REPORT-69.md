# REPORT-69 — TASK-69, round 92

## Done

- P1. Пять мер переведены из _UNMAPPED_FORMULAS в расчёт по словарю
  (docs/data-dictionary.md):
  - net_debt = total_debt − cash − st_investments;
  - net_debt_ebitda = net_debt / ebitda_ttm (null при ≤ 0);
  - pe = market_cap_total / net_income_ttm (null при ≤ 0);
  - ps = market_cap_total / revenue_ttm;
  - fcf_yield = fcf_ttm / market_cap.
  Знаменатели потоков — годовой вход (окно ≥ 300 дней) через
  store.latest_annual_fact (запрос по canonical_concept — в фактах
  сырой тег, а canonical живёт в отдельной колонке). Роль входа в
  lineage называет годовое окно (ADR-0021). Квартального потока в
  знаменателе годовой меры больше нет.
- P2. Страж: lineage-входы меры pe сверяются со словарём
  (docs/data-dictionary.md). Красный показан на старом pe (lineage
  нёс eps_diluted — не словарный вход) до починки.
- P3. Согласованность двух путей pe в тесте (tests/test_task69_
  consistency.py): mcap_total/net_income против price/eps_diluted,
  допуск 5% (TTM-окна способов сдвигаются на квартал). Красный
  показан на расхождении 166.4 против ~39.8.
- P4. Живой прогон AAPL: **20 из 28** (было 15). Новые значения:
  pe = 43.84; ps = 11.80; net_debt = 19.9e9; net_debt_ebitda = 0.15;
  fcf_yield = 0.0224. CONTEXT §4 обновлён.
- Тесты: tests/test_task69_consistency.py — 3 passed
  (согласованность, расхождение старого pe, lineage-входы).

## Blocked

## What not to trust

- Числа pe/ps — точка 2026-09; курс и отчётные периоды изменятся.
- 8 мер остаются честно пустыми (drawdown/hhi/price_adj/total_return —
  нужен ряд цен; hhi/invested_capital — нужен расчёт суммы долга и
  пиров; roe/roe_incl_nci — нужен prior period или NCI; interest_
  coverage — period_mismatch).

## Disputed

## HANDOFF

Status: DONE
Arrival state: task taken round 92 on 993b11e, selfcheck green
Items done: P1 (пять мер по словарю), P2 (страж lineage-входов),
P3 (согласованность двух путей pe), P4 (firsthour + live + CONTEXT)
Items not done: none
Acceptance: «Итог: пройдено 13, провалено 0» на хуке каждого коммита
круга; полный вывод приёмки — в commit body
Tests: 20/28 со значением живьём; 19 после P1 без цен (265B
годовой revenue FY2018 — единственный годовой Revenues в payload)
Guards: agent/p7_relay_rule.sh (раунд-скоп коммитов круга в selfcheck);
new: store.latest_annual_fact + SnapshotBuilder._latest_annual_input
Schema: unchanged
Network: 0 в этом круге (live AAPL — ТЗ-63 каталог)
Model: GLM-5.3, app llm_calls 0
Secrets: нет ключевого материала
Pushed: this commit pushes immediately
Questions for the coordinator:
1. Пустые после N1 меры (drawdown, hhi, price_adj, total_return) —
   нужен ряд цен и пиров: заводить пунктами или в BACKLOG?

NOW: P4, step 2 — task complete, handing the baton back
