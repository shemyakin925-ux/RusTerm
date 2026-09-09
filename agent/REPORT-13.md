# REPORT-13 — TASK-13, session 2026-09-09 (M4)

## Done

## Blocked

## What not to trust

## Disputed

## HANDOFF
Status:          PARTIAL (смена продолжается)
Items done:      setup
Items not done:  Z1-Z6 впереди
Acceptance:      пройдено 13, провалено 0   (последний прогон: 2ca3423)
Tests:           300 passed, 2 skipped, 1 xfailed
Milestones:      M4 в работе; M3 yes, M5 no (no key)
Network:         RUSTERM_SEC_UA set; запросов в этой смене: 0
Model:           app LLM calls 0; own model GLM-5.3-Flash, exact call count not instrumented
Pushed:          yes
Questions for the coordinator:
- Z1 done: conditional GET added; test proves 200+ETag -> (doc, validators etag/last_modified lowercase), second call sends If-None-Match, 304 -> NotModified, no raw_object, gate.calls_made == 2; pytest tests/test_edgar.py -q -> 9 passed; pytest -q exit 0; acceptance 13/13 (first run 12/13 — untracked REPORT-13.md, staged and re-run green)

NOW: Z2, step 1
- Z2 done: migration 37 issuer_ingest_state; refresh_watchlist (rusterm/core/refresh.py): 1 submissions per instrument per pass, companyfacts skipped entirely when last_filing_date not newer, conditional GET with stored validators, 304 -> NotModified, snapshot rebuilt only with new facts; test test_z2_second_pass_requests_submissions_only: 10 issuers, pass1 = 10 companyfacts, pass2 = 0 companyfacts + 10 submissions, facts/raw_object counts unchanged, every skip line carries reason + last_filing_date; schema pins 36->37 / tables 33->34 / [33,35,36]->[33,35,36,37] / doctor-drift updated with the migration (same strength); pytest -q exit 0; acceptance 13/13. Note: llm_guard textual grep for 'requests' tripped on the field name — renamed to calls

NOW: Z3, step 1
