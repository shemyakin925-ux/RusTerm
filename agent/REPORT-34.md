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
