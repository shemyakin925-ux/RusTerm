# REPORT-34 — TASK-34: extraction is checked by a model, not by hope

Arrival state: selfcheck OK at 8cce46c (13/13); full suite 668 passed,
1 skipped, 4 xfailed, 0 failed.

## Done

### F6 — a red selfcheck can no longer be committed, whatever the caller types (DONE, taken first)

- `agent/githooks/pre-commit` (tracked): runs
  `bash "$(dirname $0)/../selfcheck.sh"` — no pipe, the hook's exit
  status IS selfcheck's. Activated in this clone:
  `git config core.hooksPath agent/githooks` (printed:
  `agent/githooks`).
- `agent/PROTOCOL.md` §12 gained the one authorized bootstrap line
  (the only PROTOCOL edit; the P6 guard gained the matching declared
  exception `РАЗРЕШЕНИЕ-ПРОТОКОЛА:` — otherwise the guard would block
  the very edit F6 orders; 2 tests added to test_e6_p6_rule.py:
  PROTOCOL without the declaration -> red, with it -> green; 5 passed).
- Demonstration (the blocker is the P1 rule, exercising the full
  chain):
  * setup: one `assert` line deleted from the committed
    `tests/test_smoke.py`, staged; COMMIT_EDITMSG carries only the
    PROTOCOL authorization, no pin-replacement block for that file;
  * command: `git commit -F .git/COMMIT_EDITMSG`;
  * exit status: 1; output tail:
    `P1: необъявленная замена булавок: tests/test_smoke.py (нет
    объявления ЗАМЕНА-БУЛАВКИ/ПОЧЕМУ СИЛЬНЕЕ)` +
    `SELFCHECK FAIL (P1): undeclared pin replacement in staged diff`;
  * `git log -1` before and after: `df7dd7` both — HEAD did not move;
  * the scratch edit was then unstaged and reverted
    (`git restore --staged && git checkout --`);
  * `pytest tests/test_smoke.py -q` -> 3 passed (file intact).
- The first commit of this night made UNDER the hook: the F6 commit
  itself (hook + PROTOCOL line + p6 exception + this report) — it
  passed the hook with selfcheck green on exit 0.

## Blocked

- (nothing)

## What not to trust

- The hook's demo ran the full selfcheck twice (red case ~fast via P1,
  green case full acceptance); the numbers in this file were produced
  under the hook from the first F6 commit onward.

## Disputed

- (none yet)

## HANDOFF

Status:          PARTIAL - F6 done; F1..F5 ahead
Arrival state:   selfcheck OK at 8cce46c (13/13)
Items done:      F6
Items not done:  F1, F2, F3, F4, F5
Acceptance:      «Итог: пройдено 13, провалено 0» at this commit (exit 0 captured before any pipe)
Tests:           full default run 0 failed (see final HANDOFF)
Guards:          pre-commit hook (tracked) + PROTOCOL §12 bootstrap; p6 declared-exception for PROTOCOL with 2 tests
Schema:          unchanged (44)
Network:         0 requests used of 0
Model:           0 of 80 so far; GLM-5.3-Flash
Secrets:         0 hits
Pushed:          yes
Questions for the coordinator:
1. (none yet)

NOW: F6, step 8

### F5 — the extract_text door is wired (DONE)

- `rusterm/manual/__init__.py:extract_text` now delegates to
  `rusterm/manual/extract.py:extract_text` (lazy import — the
  implementation imports Document/Page from this package).
- The old pin (quoted): `test_extract_text_seat_refuses_every_format_as_value`
  asserted `extract_text("обычный текст".txt) -> ProviderError with
  reason startswith "format_unsupported"` — it hid a working
  implementation behind a bypassed door (the TASK-19 F6 defect
  shape).
- The new pin (quoted): `test_extract_text_door_delegates_to_implementation`
  — on the committed fixture table1_clean_two_column.html the door
  returns exactly what the implementation returns (same sha256 ==
  file sha, identical pages, "Off-hire days" present in the page
  text) — strictly stronger: it pins DELEGATION plus real parsing,
  not a refusal. `tests/test_manual_seats.py` 13 passed;
  manual suite (extract/pipeline/seats) green.

### F1 — the four table shapes through the real pipeline (DONE)

Client: the user's configured free model `glm-5.3-flash` (OpenRouter
free tier), through RequestGate with the llm-api declared limit; run
root /tmp/n4root (synthetic issuer n4-fleet — the user's real DB is
not polluted with fixtures).

| table | extracted records | verified | near_miss | failed (dropped) | facts stored |
|---|---|---|---|---|---|
| table1_clean_two_column | 0 | 0 | 0 | 0 | 0 |
| table2_ten_column_fleet_by_class | 36 | 0 | 0 | 0 | 0 |
| table3_with_total_row | 45 (36 + 9 Total) | 0 | 0 | 0 | 0 |
| table4_footnote_in_number | 0 stored (9 dropped: bad shape — "210(3)" values) | 0 | 0 | 9 | 0 |

Findings recorded as measured, nothing tuned:
- The extract stage flattens an HTML table into digit soup
  ("Off-hire daysVoyage days / 12365"; "VLCC1230000004300...").
  On table1 the model returns an empty set — nothing quotable.
- On tables 2-3 the model names EVERY metric and takes EVERY number
  from the right column (all 81 values match the by-eye read), but
  the deterministic control rejects all of them: the quotes are
  verbatim copies of the FLATTENED text and still fail the string
  law on whitespace. The honest measure of the feature is therefore
  0 facts from 4 tables — the bottleneck is stage ①'s table
  flattening, not the model's column discipline.
- table4's footnote markers inside numbers ("210(3)") break the
  model's output shape: all 9 records dropped by the shape counter.

### F2 — verified-but-wrong is measured, not assumed (DONE)

**verified-but-wrong cases: 0**, and the evidence is stronger than
the number: not a single record was verified on any of the four
tables (verified=0 everywhere), so nothing wrong could pass the
control. Additionally every stored record was compared by eye
against the fixture tables — all 81 values on tables 2-3 are the
CORRECT column values (the model's column discipline is fine; the
quotes/whitespace are what fails). A `verified=no` record is stored,
shown, and absent from every formula — asserted by the existing
`tests/test_manual_pipeline.py::test_unverified_record_stored_marked_and_never_a_fact`.

### F3 — the cost is named (DONE)

- Model calls: 8 `complete()` invocations total; 4 of them were
  refused at the gate before any network (client constructed without
  a gate — my first-pass error, recorded here as spent discipline),
  4 real API calls — exactly one per table. STATE.json:
  `llm_calls: 8` of the 80-call budget.
- Free-tier limit (ADR-0018: the budget is calls, not money):
  OpenRouter free model `glm-5.3-flash`; no paid route touched.

### F4 — a recorded model response is committed (DONE)

- `tests/data/manual/response_table2_fleet.json` — the real model's
  answer for the ten-column fleet table (7,430 bytes, synthetic
  content only).
- `tests/test_manual_pipeline.py::test_recorded_model_response_replays_whole_pipeline_offline`:
  a fake client serves the recorded response through the WHOLE
  ①②③ pipeline on the committed table2 fixture -> 36 records,
  0 verified, 36 stored as unverified, 0 facts, exactly 1 call.
  The path is covered on a machine with no key.
- Repair en route (F1 scope): the final ImportOutcome dropped
  `records_near_miss` (the field existed, the live return omitted it
  — near-miss would always print 0); now passed through.
