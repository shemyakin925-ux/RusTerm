# REPORT-15 — TASK-15: what the user can check for himself

## Done
- §0 `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0`, дерево чистое (head a524cef).

## Blocked

## What not to trust

## Disputed

- Разовый провал полного сюита при прогоне перед коммитом C4 (1 failed  без захваченного имени; пайп с tail замаскировал код возврата и коммит  ушёл — повтор вчерашнего инцидента B20 с моей стороны). Четыре  последующих полных прогона зелёные (319 passed, 2 skipped), включая  два прогона приёмки. Подозреваемый — тайминг-чувствительный чекпоинт  в test_m4_scale (2.0 s на первый инструмент при нагрузке параллельной  сессией), но это гипотеза: имя теста не зафиксировано.
## HANDOFF
Status:          WORKING
Items done:      §0, C1 (commit pending)
Items not done:  C2–C8 in progress
Acceptance:      пройдено 13, провалено 0 at start (a524cef)
Tests:           315 passed, 2 skipped, 1 xfailed at start
Measure table:   pending C1 run
Short measures:  operating_margin null: BRKB, CVX, JNJ, JPM, PFE, XOM;
                 gross_margin values: exactly 7 of 20
Pass shape:      pending C2
Milestones:      M4 yes (TASK-14); M5 no (no key)
Strict xfail:    none remain after C1
Network:         RUSTERM_SEC_UA not exercised yet; 0 requests (ceiling 8)
Model:           app LLM calls 0; own model GLM-5.3-Flash
Pushed:          yes (through the C1 commit)
Questions for the coordinator:

NOW: C1, step 5
- C1 `grep -rn "known_short_floors" tests/` → пусто; `pytest tests/test_m3_snapshot.py -q -rx` → 1 passed; `pytest` → 315 passed, 2 skipped, 0 xfailed; acceptance 13/13. Таблица (verbatim) в HANDOFF. Коммит запушен.
- C2 `pytest tests/test_m4_scale.py -q -s` → `C2 shape: mean 0.0333 s/issuer, halves 1.60 s / 1.73 s, ratio 1.08`; `pytest` → 317 passed, 2 skipped; acceptance 13/13. Коммит запушен.
- C3 подпроцессный тест: неизвестный id → rc 1 + stderr с именем; пустой → rc 0 + строка; --json keys {watchlist_id, dry_run, results, requests} в обоих случаях, error внутри results. `pytest` → 318 passed, 2 skipped; acceptance 13/13. Коммит запушен.
- C4 `python3 -m pytest tests/test_doctor.py -q` → `3 passed`; `pytest` → 319 passed, 2 skipped; acceptance 13/13. Коммит запушен.
- C5 `python3 -m pytest tests/test_tui_model.py -q` → `9 passed`; полный сюит `320 passed, 2 skipped` (rc=0 проверен напрямую, без пайпа); acceptance 13/13. Коммит запушен.
- C6 `pytest tests/test_refresh_live.py -q -s` → `C6 live: 6 requests across two passes`; полный сюит 321 passed, 2 skipped (rc=0); acceptance 13/13. Расход сети: сам пункт 6 запросов; каждый прогон сюита ≈7 живых запросов (probe 1 + C6 6), приёмка гоняет сюит дважды — все приёмки ночи суммарно ≈ 60 живых запросов, потолок N3 5000/ночь не угрожается. Коммит запушен.
