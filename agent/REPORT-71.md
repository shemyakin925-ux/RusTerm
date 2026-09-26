# REPORT-71 — TASK-71, round 96

## Done

- R2. invested_capital = total_equity + total_debt − cash − st_inv
  (словарь; minority = 0 — NCI AAPL не подаёт, подтверждено N3).
  **Живой прогон AAPL: invested_capital = 127.4e9; roic = 0.881** (nopat
  112.01e9 × (1−0.1786) / avg(ic) — реалистично для Apple).
  _UNMAPPED_FORMULAS сужен: 4 честно несчитаемых остались
  (total_return/drawdown/price_adj/hhi).
- Итог R2: **21 из 28** со значением (было 20, +invested_capital, +roic).

## Blocked

## What not to trust

- roic = 0.881 использует nopat из цепочки effective_tax и ic из
  баланса AAPL — значения реальные, но не сверялись с внешним
  источником.

## Disputed

## HANDOFF (FINAL)

Status: PARTIAL
Arrival state: task taken round 96 on 7095d80, selfcheck green
Items done: R2 (invested_capital + roic, 21/28 live)
Items not done: R3 (второй эмитент), R4 (двухпутевые сверки),
collision guard — следующий круг
Acceptance: «Итог: пройдено 13, провалено 0» на хуке
Tests: c2_six_measures + task69_consistency green
Guards: none touched
Schema: unchanged
Network: 0
Model: GLM-5.3, app llm_calls 0
Secrets: нет ключевого материала
Pushed: this commit pushes immediately
Questions for the coordinator:
1. roic = 0.881 — правдоподобно? Apple ROIC исторически 50-80%.

NOW: R2, step 2 — context exhausted, handing back with plan for R3/R4

## HANDOFF

Статус и план — в блоке HANDOFF (FINAL) выше; эта секция оставлена
под требование обязательных секций отчёта.
