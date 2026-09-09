# REPORT-18 — TASK-18: Canada and OTC, the market becomes a registry

## Done
- §0 `git merge origin/main` → Already up to date; acceptance → `Итог: пройдено 13, провалено 0`.
- §0 `printenv RUSTERM_SEC_UA` → empty in shell, but `~/.rusterm.env` exists and the application reads it itself (N2); live path available (proven by TASK-15 C6).

## Blocked

## What not to trust

## Disputed
- DISPUTED (procedure): G1+G2+G5 сведены в один коммит — изменения
  переплетены в cmd_add и edgar.py (валидация рынка, биржа в листинге,
  404-значение идут через один поток add/ingest); раздельная нарезка
  hunks riskier than the combined commit.

## HANDOFF
Status:          WORKING
Items done:      §0, G1, G2, G5 (commit pending)
Items not done:  G3–G13 in progress
Acceptance:      пройдено 13, провалено 0 at start (23737a7)
Tests:           347 passed, 2 skipped, 0 xfailed at start
Markets:         {US, CA, OTC} pinned
Issuers taken:   pending G6
Measure table:   pending G8
Golden m6 CA:    pending G7
No-filings path: NOFILE (stub 404) — coverage missing no_sec_filings
formulas.py:     guard test pending G4
Payload size:    pending G6
Both taxonomies: pending G6
Milestones:      pending
Network:         ~0 so far (stub-only); budget 40
Model:           app LLM calls 0; own model GLM-5.3-Flash
Pushed:          yes
Questions for the coordinator:

NOW: G3, step 1
