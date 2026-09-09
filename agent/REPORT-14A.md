# REPORT-14A — TASK-14: the pass that has to survive five hundred

## Done
- §0 merge: `git merge origin/main` — BACKLOG conflict resolved `--theirs` (B20–B25 queue from main); TASK-14/18 kept local (newer: REPORT-14A rename + SEDAR-probe notes); commit `053754d`, pushed `b90ac14..053754d`.
- §0 acceptance: `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0` (first run 12/13 — untracked duplicate `agent/additional report.md`, byte-identical to tracked `agent/REPORT-14.md`, recreated once by an external process after `rm`; deleted, re-check green).

## Blocked

## What not to trust

## Disputed

## HANDOFF
Interim — filled at night end per §3.

NOW: §0, step 8
- A1 `git add -A rusterm tests && git diff --cached …` → P1: 8 строк — пины 37→38 (все заменены равными/строже); P2: только `_SCHEMA_VERSION`; P3/P4 пусто; `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0`. Коммит `8f46d32`, пуш ок. Замер: `pytest tests/test_m4_scale.py -q -s` → `M4 timings: first pass 26.68 s, second pass 0.02 s`.
- A3 строгий xfail снят (единственное разрешённое удаление; до снятия зафиксирован `[XPASS(strict)]`), чекпоинт остался. `python3 -m pytest` → `307 passed, 2 skipped, 1 xfailed` (1 — W4). Причина сцепки A1+A3 в одном коммите — в ## Disputed.

## Disputed
- DISPUTED (procedure): A1 и A3 сведены в один коммит `8f46d32`, хотя ТЗ считает их отдельными пунктами. Причина: миграция 38 переводит strict-xfail test_m4_scale в XPASS(strict) — до снятия маркера полный сюит красный (1 failed), а §1.3 запрещает коммит с красной приёмкой; §1.1 требует коммит после каждого пункта. Замкнутый круг разрывается только совместным коммитом. Порядок операций зафиксирован: сначала наблюдался XPASS(strict), затем маркер снят.
- DISPUTED (test repair, not weakening): заглушки «базы v32» в tests/test_db.py (B33-тест) и tests/test_invariants.py (I16) держали fact из двух колонок и без measure/measure_lineage — настоящая база v32 содержала их в полной форме миграций 11/20/21. Миграция 38 требует этих колонок; заглушки расширены до полной схемы, а не урезана миграция.
- DISPUTED (P1 accounting): selfcheck P1 показал 8 снятых assert-строк — все восемь являются обновлениями пинов версии схемы 37→38 (одно усилено: список миграций [33,35,36,37] → [33,35,36,37,38]); ни одна проверка поведения не ослаблена.
- A2 красная проверка: фильтр снят → `AssertionError: чужие ревизии в диффе: [('revenue', …), ('net_income', …)]`, восстановлен. `python3 -m pytest` → `308 passed, 2 skipped, 1 xfailed`; acceptance 13/13. План (verbatim): `SEARCH f USING COVERING INDEX idx_fact_issuer_concept_period_basis (issuer_id=?)` / `CORRELATED SCALAR SUBQUERY 1` / `SEARCH a USING COVERING INDEX … (issuer_id=? AND concept=? AND period_end=? AND basis=?)`. Коммит запушен.
- A4 `python3 -m pytest tests/test_m3_snapshot.py -q -s` → таблица: `roe: 16/20 … {'missing_data: total_equity': 4}`, `nopat: 14/20 … {'missing_data: operating_income': 6}` — голых причин нет; `python3 -m pytest` → `308 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Коммит запушен.
- A5 `python3 -m pytest tests/test_refresh.py -q` → `3 passed`; `python3 -m pytest` → `309 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Счётчики payload закреплены тестом: `{"updated": 1, "unchanged": 0, "error": 0, "submissions": 1, "companyfacts": 1}`. Коммит запушен.
- A6 `python3 -c "…get_type_hints…"` → `ok`; `grep -n 'def finish' rusterm/core/refresh.py` → пусто; `python3 -m pytest` → `309 passed, 2 skipped, 1 xfailed`; acceptance 13/13. Коммит запушен.
