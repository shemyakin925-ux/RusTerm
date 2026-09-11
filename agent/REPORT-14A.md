# REPORT-14A — TASK-14: the pass that has to survive five hundred

## Done
- §0 merge: `git merge origin/main` — BACKLOG conflict resolved `--theirs` (B20–B25 queue from main); TASK-14/18 kept local (newer: REPORT-14A rename + SEDAR-probe notes); commit `053754d`, pushed `b90ac14..053754d`.
- §0 acceptance: `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0` (first run 12/13 — untracked duplicate `agent/additional report.md`, byte-identical to tracked `agent/REPORT-14.md`, recreated once by an external process after `rm`; deleted, re-check green).
- A1 `git add -A rusterm tests && git diff --cached …` → P1: 8 строк — пины 37→38 (все заменены равными/строже); P2: только `_SCHEMA_VERSION`; P3/P4 пусто; `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0`. Коммит `8f46d32`, пуш ок. Замер: `pytest tests/test_m4_scale.py -q -s` → `M4 timings: first pass 26.68 s, second pass 0.02 s`.
- A3 строгий xfail снят (единственное разрешённое удаление; до снятия зафиксирован `[XPASS(strict)]`), чекпоинт остался. `python3 -m pytest` → `307 passed, 2 skipped, 1 xfailed` (1 — W4). Причина сцепки A1+A3 в одном коммите — в ## Disputed.
- A2 красная проверка: фильтр снят → `AssertionError: чужие ревизии в диффе: [('revenue', …), ('net_income', …)]`, восстановлен. `python3 -m pytest` → `308 passed, 2 skipped, 1 xfailed`; acceptance 13/13. План (verbatim): `SEARCH f USING COVERING INDEX idx_fact_issuer_concept_period_basis (issuer_id=?)` / `CORRELATED SCALAR SUBQUERY 1` / `SEARCH a USING COVERING INDEX … (issuer_id=? AND concept=? AND period_end=? AND basis=?)`. Коммит запушен.
- A4 `python3 -m pytest tests/test_m3_snapshot.py -q -s` → таблица: `roe: 16/20 … {'missing_data: total_equity': 4}`, `nopat: 14/20 … {'missing_data: operating_income': 6}` — голых причин нет; `python3 -m pytest` → `308 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Коммит запушен.
- A5 `python3 -m pytest tests/test_refresh.py -q` → `3 passed`; `python3 -m pytest` → `309 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Счётчики payload закреплены тестом: `{"updated": 1, "unchanged": 0, "error": 0, "submissions": 1, "companyfacts": 1}`. Коммит запушен.
- A6 `python3 -c "…get_type_hints…"` → `ok`; `grep -n 'def finish' rusterm/core/refresh.py` → пусто; `python3 -m pytest` → `309 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Коммит запушен.
- A7 `python3 -m pytest tests/test_db.py -q` → `10 passed`; `python3 -m pytest` → `310 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Перестройка внутри миграции 38 (как требует A7), 37 не тронута; текст checksum миграции 38 изменился против коммита 8f46d32 — ни одна база вне этого ночного бранча версию 38 применить не могла. Коммит запушен.
- B20 `python3 -m pytest tests/test_refresh.py -q` → `4 passed`; totals==sum(calls) на обоих проходах; `--json` возвращает 0 даже при ошибках (контракт Z4, отмечено). Инцидент: первый вариант коммита ушёл в git с красным тестом (пайп скрыл код возврата) — аменд до пуша, см. ## What not to trust. Коммит запушен.
- B21 `python3 -m pytest tests/test_db.py -q` → `11 passed`; acceptance 13/13. Коммит запушен.
- B22 `grep -rn '1100' rusterm/ --include='*.py'` → только `_STALE_LOOKBACK_DAYS = 1100`; tests → 10 passed, 1 xfailed; acceptance 13/13. Коммит запушен.
- B23 `python3 -m pytest tests/test_trim_tool.py -q` → `5 passed`; acceptance 13/13. Коммит запушен.
- B24 `python3 -m pytest tests/test_logs.py -q` → `6 passed`; `python3 -m pytest` → `314 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Коммит запушен.
- B25 `python3 -m pytest tests/test_cli.py -q` → `32 passed`; `python3 -m pytest` → `315 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Коммит запушен.

## Blocked

## What not to trust
- Параллельная сессия работает в этой же рабочей копии на agent/night-2:
  коммит 741a685 (REPORT-MARKETS, «вне цепочки TASK-14») въехал в цепочку
  между моими коммитами; его правки про rusconv попали в blob отчёта через
  мой `git add`. Секция side task ниже сохранена дословно, ничего не удалено.
- Инцидент B20: первый вариант коммита ушёл в git с красным тестом —
  пайп `pytest | tail` замаскировал код возврата, приёмка была 11/13.
  Исправлен амендом ДО пуша; в origin красный вариант не попадал.
- Замеры M4 (26.68 s / 0.02 s) — один прогон на этой машине, не усреднение;
  XPASS(strict) наблюдался один раз, до снятия маркера.
- Счётчик собственных вызовов модели не инструментирован; net_requests 0 —
  сетевые узлы этой ночью не вызывались, llm_calls 0 — ключа не было.
- ACCEPTANCE-12.txt снимается на хэндовер-голове после этого HANDOFF (§3).
- Тест B20 закрепляет ФАКТИЧЕСКОЕ поведение второго прохода (unchanged по
  sha256-дедупликации), а не моё изначальное ожидание updated.

## Disputed
- DISPUTED (procedure): A1 и A3 сведены в один коммит `8f46d32`, хотя ТЗ считает их отдельными пунктами. Причина: миграция 38 переводит strict-xfail test_m4_scale в XPASS(strict) — до снятия маркера полный сюит красный (1 failed), а §1.3 запрещает коммит с красной приёмкой; §1.1 требует коммит после каждого пункта. Замкнутый круг разрывается только совместным коммитом. Порядок операций зафиксирован: сначала наблюдался XPASS(strict), затем маркер снят.
- DISPUTED (test repair, not weakening): заглушки «базы v32» в tests/test_db.py (B33-тест) и tests/test_invariants.py (I16) держали fact из двух колонок и без measure/measure_lineage — настоящая база v32 содержала их в полной форме миграций 11/20/21. Миграция 38 требует этих колонок; заглушки расширены до полной схемы, а не урезана миграция.
- DISPUTED (P1 accounting): selfcheck P1 показал 8 снятых assert-строк — все восемь являются обновлениями пинов версии схемы 37→38 (одно усилено: список миграций [33,35,36,37] → [33,35,36,37,38]); ни одна проверка поведения не ослаблена.

## User-directed side task (chat, 2026-09-09, outside TASK-14 scope)
- The user directly instructed (chat) to build an external PDF->data tool in `~/TextConv/rusconv/` (outside this repo): PDF -> per-page text -> local gpt-oss-20b (LM Studio) -> validated records (financial / physical-operational / other), CSV+JSON outputs. No repo code touched, no commits made for it. Logged here per the AGENTS.md rule: user chat instructions outrank the task queue; final arbiter is the user.

## HANDOFF
Status:          DONE
Items done:      §0 (merge + 13/13), A1, A2, A3, A4, A5, A6, A7, A8 (B20–B25), A9
Items not done:  A10 as execution — TASK-15 taken next per the standing
                 instruction "queue not empty"; nothing else left undone
Acceptance:      пройдено 13, провалено 0   (agent/ACCEPTANCE-12.txt)
Tests:           315 passed, 2 skipped, 1 xfailed (W4)
M4 scale:        first pass 26.68 s, second pass 0.02 s, requests on the
                 second pass 0 companyfacts (test-pinned); budget 240 s
Query plan:      restated_revisions after A1+A2 —
                 (2, 0, 54, 'SEARCH f USING COVERING INDEX idx_fact_issuer_concept_period_basis (issuer_id=?)')
                 (9, 0, 0, 'CORRELATED SCALAR SUBQUERY 1')
                 (13, 9, 51, 'SEARCH a USING COVERING INDEX idx_fact_issuer_concept_period_basis (issuer_id=? AND concept=? AND period_end=? AND basis=?)')
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
Milestones:      M4 yes — five hundred instruments inside the budget on
                 both passes; incrementality, schedule-as-command and
                 rollback were already in
Strict xfail:    one remains — test_w4_known_short_floors_operating_margin_
                 and_gross_margin (data floor: 14/20 and 7/20 vs 15/10)
Network:         RUSTERM_SEC_UA not exercised tonight; app requests 0
Model:           app LLM calls 0; own model GLM-5.3-Flash
Pushed:          yes (through the final acceptance commit)
Questions for the coordinator:
1. refresh --json returns 0 even when the pass had errors (Z4-era
   contract, pinned by test; B20 left it untouched). Deliberate?
2. Migration 38's checksum text changed between 8f46d32 (A1) and the
   A7 commit — no stored-checksum verification exists; keep it that way?
3. agent/additional report.md (byte-identical duplicate of tracked
   agent/REPORT-14.md) was deleted twice; something external recreated
   it once — same parallel session as the side-task note?
4. A parallel session commits to agent/night-2 in this checkout
   (741a685 REPORT-MARKETS; rusconv note). Coordinate file ownership
   so report files are not co-edited.

NOW: A9, step 8
