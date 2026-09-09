# REPORT-15 — TASK-15: what the user can check for himself

## Done
- §0 `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0`, дерево чистое (head a524cef).

## Blocked

## What not to trust

## Disputed

- Разовый провал полного сюита при прогоне перед коммитом C4 (1 failed  без захваченного имени; пайп с tail замаскировал код возврата и коммит  ушёл — повтор вчерашнего инцидента B20 с моей стороны). Четыре  последующих полных прогона зелёные (319 passed, 2 skipped), включая  два прогона приёмки. Подозреваемый — тайминг-чувствительный чекпоинт  в test_m4_scale (2.0 s на первый инструмент при нагрузке параллельной  сессией), но это гипотеза: имя теста не зафиксировано.
## HANDOFF
Status:          DONE
Items done:      §0, C1, C2, C3, C4, C5, C6, C7 (queue empty — nothing to
                 pull), C8
Items not done:  none
Acceptance:      пройдено 13, провалено 0   (agent/ACCEPTANCE-13.txt)
Tests:           321 passed, 2 skipped, 0 xfailed
Measure table:   measure -> n/20 + reasons:
                   net_margin: 20/20 (порог 20) причины: —
                   effective_tax: 20/20 (порог 15) причины: —
                   fcf: 19/20 (порог 12) причины: {'missing_data: capex': 1}
                   ebitda: 14/20 (порог 10) причины: {'missing_data: operating_income': 6}
                   interest_coverage: 12/20 (порог 8) причины: {'missing_data: operating_income': 6, 'negative_denominator': 1, 'missing_data: interest_expense': 1}
                   nopat: 14/20 (порог 12) причины: {'missing_data: operating_income': 6}
                   roe: 16/20 (порог 12) причины: {'missing_data: total_equity': 4}
                   asset_turnover: 20/20 (порог 12) причины: —
                   operating_margin: 14/20 (порог 14) причины: {'missing_data: operating_income': 6}
                   gross_margin: 7/20 (порог 7) причины: {'missing_data: gross_profit': 13}
Short measures:  operating_margin null exactly at {BRKB, CVX, JNJ, JPM,
                 PFE, XOM}, all missing_data: operating_income;
                 gross_margin values exactly 7 of 20, nulls all
                 missing_data: gross_profit
Pass shape:      mean 0.0333 s/issuer (budget 0.30, x3 headroom),
                 halves 1.60 s / 1.73 s, second/first ratio 1.08 (cap 1.5)
Milestones:      M4 yes; M5 no (no key)
Strict xfail:    none remain — W4 retired by C1 per §0.1
Network:         RUSTERM_SEC_UA set via ~/.rusterm.env; the item itself
                 spent 6 requests of its 8 cap; every suite run re-executes
                 live tests (~7: probe 1 + C6 6) and acceptance runs the
                 suite twice — night total roughly 60, N3 ceiling 5000
Model:           app LLM calls 0; own model GLM-5.3-Flash
Pushed:          yes (through the final acceptance commit)
Questions for the coordinator:
1. The backlog queue is empty again — refill for the next night?
2. Live tests re-run inside every acceptance (two suite runs). Acceptable
   as the standing cost, or gate them behind an opt-in flag?

NOW: C8, step 8
