# REPORT-28 — TASK-28: freeness becomes a machine-checked rule

## Done

### Arrival state (per PROTOCOL §10, before any commit)

- Branch `agent/night-10` (this shift's branch; TASK-28 §0 line 2 done
  once per shift), selfcheck STATUS=0 before this task started
  (TASK-29 closed first, per LAUNCH order: 29, then 28).
- Schema `_SCHEMA_VERSION` = 41 (§0 line 4).
- `sorted(available())` (§0 line 5): ['asx', 'cvm', 'dart', 'edgar',
  'llm-api', 'otcmarkets', 'synthetic-disclosures', 'synthetic-market'].
- Seats still carrying the placeholder ceiling (§0 line 6):
  `grep -rn "nightly_max=5000" rusterm/providers/__init__.py | wc -l`
  -> 6.

### R1 — every external channel declares its cost (DONE)

- `rusterm/providers/__init__.py`: `_TIERS` closed set
  (`open`, `free_key`, `paid`); `_CHANNEL_TIERS` declares a tier for
  every network name; `get_provider` refuses by value a name without a
  tier (`provider_declares_no_tier:<name>`) and a name whose tier is
  `paid` (`paid_channel_refused`) — both before any factory runs, so
  `calls_made` stays 0. Public `channel_tier(name)` added for doctor
  and guards.
- Tiers declared tonight (verbatim, name -> tier):
  asx -> open; cvm -> open; dart -> free_key; edgar -> free_key;
  llm-api -> free_key; otcmarkets -> open.
- `tests/test_free_only.py` (new) asserts all three required things:
  every registered network name carries a tier from the closed set;
  no registered name declares `paid`; a synthetic `paid` seat injected
  into the registry inside the test is refused by value with
  `reason == "paid_channel_refused"`, the factory not called, and
  `gate.calls_made == 0`. Plus: a name with a factory but no tier is
  refused by value.
- Verification: `python3 -m pytest tests/test_free_only.py -q` ->
  4 passed; `tests/test_budget.py tests/test_providers.py` -> 20 passed
  (budget behaviour untouched, no assertion edited).

## Blocked

- (nothing yet)

## What not to trust

- (updated as items land)

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL — shift in progress
Arrival state:   selfcheck STATUS=0 (TASK-29 landed first on this branch)
Items done:      R1
Items not done:  R2, R3, R4, R5, R6 — in numeric order
Acceptance:      last run «Итог: пройдено 13, провалено 0», ACC_EXIT=0
Tests:           test_free_only 4 passed; budget/providers 20 passed
Guards:          tests/test_free_only.py new (R1 part); no existing assertion touched
Schema:          unchanged (41)
Network:         0 requests of 10 budget
Model:           0 calls of 0; GLM-5.3-Flash
Secrets:         no key values anywhere; repr masks from TASK-29 A4 in place
Pushed:          per-commit
Questions for the coordinator:
1. (none yet)
