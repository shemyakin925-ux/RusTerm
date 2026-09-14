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
