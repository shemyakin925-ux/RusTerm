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

## Done (continued) — the third visit (round 47)

### I7 — P6 also walks through `git rev-parse` (DONE)

- `agent/p6_rule.sh` reads COMMIT_EDITMSG through
  `git rev-parse --git-path COMMIT_EDITMSG` (the fix was lost in the
  round-46 rebase — re-applied and committed at 627a0dc).
- `git grep -n '\.git/' -- agent/ tests/` in code: only comments and
  the I7 test's DOCSTRING mention (prose); no literal paths.
- New test `tests/test_i7_p6_worktree.py`: a throwaway linked
  worktree whose BATON.json points at a DISPOSABLE task file outside
  `agent/` (so the TASK-* pattern does not catch it) carrying
  `РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md`; CONTEXT.md staged; the
  declaration written into the `--git-path` path. Guard invoked
  directly, no nested acceptance.
  - RED on today's code: `I7_BASE=1459cbb pytest
    tests/test_i7_p6_worktree.py -q` -> 1 passed (the test asserts
    P6 red naming agent/CONTEXT.md — the literal path made the
    declaration invisible in a worktree);
  - GREEN on the fix: `pytest tests/test_i7_p6_worktree.py -q` ->
    1 passed (P6 green — the declaration seen through --git-path).
  The worktree base is the INDEX tree wrapped in a temporary
  dangling commit when p6_rule.sh is staged, so the test always
  exercises what is about to be committed.
- Both greens of the previous round hold: linked-worktree acceptance
  at HEAD -> `WT-EXIT=0`, «Итог: пройдено 13, провалено 0»; own
  clone acceptance green (in the hook run of this commit).

### I8 — the lock cannot paint acceptance green by silence (DONE)

- The fixed-path single-flight lock is REMOVED. Recursion stays
  impossible through the explicit `I5_NESTED` marker (the hook and
  the green case set it).
- The I5 module now writes a demonstration marker
  (`i5-demo-ran.json`, own pid); a new sentinel module
  `tests/test_i5z_demonstration_ran.py` (alphabetically after the
  demonstration) fails the acceptance when the demonstration did not
  run in this process and `I5_NESTED` is unset — a silent skip can
  no longer paint acceptance green.
- Stale-lock test: a leftover lock file no longer affects anything —
  both I5 tests still collect (`--collect-only` asserts both names,
  no skips).
- Full suite after this commit: 687 passed, 1 skipped, 6 deselected,
  4 xfailed, 0 failed; linked-worktree acceptance (I7 command above)
  green at the same tree.
