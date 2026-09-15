# REPORT-37 — TASK-37: I5 executed-from-commit guards; Q3/Q7/Q10 opened

Arrival state: selfcheck OK at acd09f4 (13/13); full suite 674 passed,
1 skipped, 6 deselected, 4 xfailed, 0 failed.

## Done

### I5 — the guard that runs is the committed one (DONE, taken first; the night ended here by PROTOCOL §10)

- `agent/selfcheck.sh` now extracts `agent/p1_rule.sh` and
  `agent/p6_rule.sh` from the INDEX when they are staged, else from
  HEAD, into a temp dir, and executes those copies; the output names
  the source per file (`I5: p6_rule.sh исполняется из index|HEAD`).
- A guard script modified in the working tree but NOT staged is a red
  selfcheck by itself, naming the file:
  `I5: страж изменён в рабочем дереве и не застейджен: agent/p6_rule.sh`.
- `agent/githooks/pre-commit` sets `I5_NESTED=1` for its selfcheck so
  the nested acceptance run skips the two I5 tests themselves (they
  mutate the index and would recurse under the commit).
- End-to-end tests (`tests/test_i5_guard_source.py`) reproduce the
  95b669a manoeuvre against the real selfcheck:
  * RED: agent/CONTEXT.md staged + agent/p6_rule.sh widened in the
    working tree only -> selfcheck red, output names the unstaged
    guard ("страж изменён в рабочем дереве и не застейджен");
  * GREEN: the same widening STAGED (the task file authorises it via
    `РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh`, line 88) -> selfcheck
    green, and the output proves the index copy executed
    ("p6_rule.sh исполняется из index" + the index-copy marker line).
    The staged widening is behaviour-preserving on purpose: a
    waive-everything staged guard would break the p6 red-case tests
    in the nested suite — which is itself the desired outcome, and
    the source-selection mechanism (what I5 exists for) is what the
    marker line proves.
- `bash agent/selfcheck.sh` green on this item's own commit (the
  first commit fully under I5).

## Blocked

- (nothing)

## What not to trust

- The full-suite runtime grew to ~6 minutes (the green I5 case runs a
  nested full acceptance).
- I1-I4 not started this night: stop time (PROTOCOL §10) fell during
  I5. The scope text of TASK-26 Q3/Q7/Q10 is untouched and next.

## Disputed

- (none yet)

## HANDOFF

Status:          PARTIAL — I5 done; I1..I4 for the next night
Arrival state:   selfcheck OK at acd09f4 (13/13)
Items done:      I5
Items not done:  I1 (question vs order), I2 (does-not-know), I3 (TUI screen), I4 (no new door)
Acceptance:      «Итог: пройдено 13, провалено 0», SELFCHECK OK at this commit (exit captured before any pipe)
Tests:           685 passed, 1 skipped, 6 deselected, 4 xfailed, 0 failed (the two I5 tests included; they run the real selfcheck twice)
Guards:          selfcheck executes guard scripts from the commit (index when staged, else HEAD, named in output); unstaged guard edit = red with the file named; hook skips nested I5 recursion
Schema:          unchanged (45)
Network:         0 of 0
Model:           0 of 0
Secrets:         0 hits
Pushed:          yes
Questions for the coordinator:
1. The green I5 case extends the runtime by a nested full acceptance
   (~2 min). A faster demonstration (extraction script driven
   directly) is possible if the runtime matters.

NOW: HANDOFF, step 8

## Done (continued) — the second visit (round 45)

### I6 — `.git` is not always a directory (DONE)

- The COMMIT_EDITMSG path in `agent/p1_rule.sh`, `agent/p6_rule.sh`
  and `tests/test_i5_guard_source.py` now comes from
  `git rev-parse --git-path COMMIT_EDITMSG` — in a linked worktree
  `.git` is a file, and the old literal path made the pending commit
  message invisible to both guards and broke the I5 tests with
  NotADirectoryError (the coordinator's reproduction).
- `grep -rn "\.git/" agent/ tests/` in code shows no literal paths
  (only comments; agent/relay.py's help strings are user text about
  its own state file, untouched — relay.py is the coordinator's).
- Done-when shown with the exact commands and output:

      git worktree add --detach /tmp/i6check HEAD
      cd /tmp/i6check && bash agent/acceptance.sh

  -> `WT-ACC-EXIT=0`, «Итог: пройдено 13, провалено 0», Принято
  (worktree at detached HEAD 33b7f17). Own clone: selfcheck 13/13
  (extraction lines: `p1_rule.sh исполняется из index` — the staged
  I6 copy), full suite 685 passed, 0 failed.
- Guard suites: tests/test_i5_guard_source.py +
  tests/test_e6_p6_rule.py + tests/test_d5_p1_rule.py -> 15 passed.
- The worktree was removed after the run (`git worktree remove
  /tmp/i6check`).

Also recorded (round 44→45 hand): the relay's `hand` committed my
staged I5 work inside its own baton commit fa6fb08 after my own
`git commit` aborted — the relay.py fix (committing only its own
files) landed on the coordinator side; fa6fb08's message therefore
does not describe I5, REPORT-37 does.
