# REPORT-16 — TASK-16: M5, mass operations under confirmation

## Done
- §0 `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0` (head 9ff4587).
- D1 `python3 -m pytest tests/test_intent.py -q` → `6 passed`; полный сюит 321 passed, 2 skipped; acceptance 13/13. Коммит запушен.
- D1 (первый коммит c9fc709 ушёл красным: пайп замаскировал rc, а секции отчёта не существовали — фикс-forward, см. ## What not to trust) `python3 -m pytest tests/test_intent.py -q` → 6 passed после починки ретрая (форматный clarification повторяется, параметровый — нет).

## Blocked

## What not to trust
- Коммит c9fc709 запушен КРАСНЫМ: chain-команда со связкой `&&` после
  `; echo rc` не остановила коммит при rc=1, и 2 провала
  test_report_sections (отчёт без секций) + 1 тест D1 поехали в origin.
  Исправляется следующим коммитом; история не переписывается.

## Disputed

## HANDOFF
Status:          DONE
Items done:      §0, D1, D2, D3, D4, D5, D6, D7, D8, D9 (queue empty), D10
Items not done:  none
Acceptance:      пройдено 13, провалено 0   (agent/ACCEPTANCE-14.txt)
Tests:           336 passed, 2 skipped, 0 xfailed
M5 half one:     python3 -m pytest tests/test_llm_guard.py -q → 7 passed
                 (числа из снапшота подстановкой; число без citations
                 бракует текст целиком; файл не тронут)
M5 half two:     python3 -m rusterm.cli --root … ops --watchlist w1
                 --request "добавь MSFT" --confirm → «применено: версия 2»,
                 audit ops/applied/confirmed=1; тот же вызов без --confirm
                 → dry-run, ноль записей (sha256 базы неизменен, тест D4);
                 101 тикер с --confirm без второго подтверждения размера
                 → refused, exit 1 (тест D6/D8)
Read-only tools: ровно {resolve_ticker, list_industry_instruments,
                 get_peer_set, get_snapshot_block} — закреплено тестом;
                 sha256 базы после вызова всех четырёх не меняется
Milestones:      M5 yes — обе половины: числа со ссылками (llm_guard)
                 и ни одной массовой операции без подтверждения (ops:
                 dry-run по умолчанию, confirm применяет, лимит 100,
                 аудит каждого исхода)
Strict xfail:    none
Network:         0 requests tonight (item fully offline); app LLM calls 0
                 (fake RuleClient; real-key path not exercised — no key)
Model:           own model GLM-5.3-Flash
Pushed:          yes (through the final acceptance commit)
Questions for the coordinator:
1. RuleClient is tonight's deterministic stand-in for the model provider
   (tickers parsed from the request text). When a real provider lands,
   should ops switch on RUSTERM_LLM_API_KEY automatically?
2. list_industry_instruments honestly returns an empty list (no industry
   source in the schema, U12.4). Keep until M7, or drop the tool?

NOW: D10, step 8

## Addendum (found during TASK-17, 10.09)
- HANDOVER DEFECT: c5f20a4 (the handover head) did NOT contain the
  empty-apply guard in ops.apply — it existed only in the working tree,
  so a clean checkout of the handover head fails test_d3_confidence.
  Fixed at start of TASK-17 by commit 2d30407; acceptance 13/13 again.
  Root cause unproven: either a staging miss or the parallel session
  touching the file between edit and commit.
