# REPORT-13 — TASK-13, session 2026-09-09 (M4)

## Done

## Blocked

## What not to trust

## Disputed

## HANDOFF
Status:          DONE
Items done:      Z1 (4ebf691), Z2 (bf0740c), Z3 (96b6227), Z4 (7577066), Z5+Z6 (этот коммит); setup: отчёт/состояние переключены на TASK-13
Items not done:  нет по пунктам Z1-Z6; веха M4 закрыта частично — см. Milestones и Disputed (структурная находка производительности)
Acceptance:      пройдено 13, провалено 0   (agent/ACCEPTANCE-11.txt)
Tests:           303 passed, 2 skipped, 2 xfailed
Real numbers:    инкрементальность на 10 эмитентах: проход 1 — 10 companyfacts, проход 2 — 0 companyfacts + 10 submissions; на CLI (AAPL) повторный refresh делает 0 запросов companyfacts и печатает 'не изменилось'
Milestones:      M4 частично (инкрементальность+расписание+откат — да; 500 бумаг — блокировано находкой Z3, xfail(strict) с бюджетом 240 s); M3 yes, M5 no (no key)
Period mismatch: 0 (после TASK-12 Y2)
Concept map:     version = us-gaap.v3; payload'ы не перезагружались в этой части смены (сеть для Z1-Z6 не требовалась)
Strict xfail:    один xfail прежний (operating_margin 15 / gross_margin 10) + новый test_m4_scale (500 бумаг, находка Z3); оба ждут устранения причин, красные станут намеренно
Network:         RUSTERM_SEC_UA set — 0 requests в этой части смены (масштаб офлайн по заданию)
Model:           app LLM calls 0; own model GLM-5.3-Flash, exact call count not instrumented
Pushed:          yes
Questions for the coordinator:
  - Z3 (важнейшее): restated_revisions() с полным SCAN fact на каждой сборке снапшота — проход O(N^2); замеры в ## Disputed (416.6 s на 100, ~2.9 ч экстраполяция на 500). Жду решения: индекс миграцией 38 либо отложенный/поэмитентный diff. Строгий xfail в tests/test_m4_scale.py покраснеет после починки — это сигнал к ревизии.
  - Доктрина бюджетов времени: 240 s на проход 500 — константа здоровой машины x3; при другом железе поправить одну константу в tests/test_m4_scale.py.
- Финал: ACCEPTANCE-11.txt — 13/13, HEAD 3c587bd (коммит перед финальным agent/-коммитом); STATE.json awaiting_review; BACKLOG.md — очередь пуста (B12-B19 перенесены в Done с пометками TASK-12 Y7); HANDOFF заменён на финальный

NOW: final, step 8
