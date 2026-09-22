# REPORT-79 — граница круга получает зубы с той стороны, где её нет

No deviation from the brief: branch `agent/night-11`, the same fresh
clone as TASK-76/78 (one clone per session, no linked worktree),
`core.hooksPath agent/githooks` set once, `relay.py wait --for executor`
exit 0 at round 105 before the first line of code.

Arrival state: HEAD `b03bc89` (baton "Эстафета: круг 105, ход у
executor — agent/TASK-79.md"), previous circle closed at `1ed7632`.

## Done

- **Z1 — teeth on the coordinator's side of the round bound.**
  `tests/test_report_sections.py` gains six tests over the fixed
  `_l3_missing` / new `_round_under_review`, none of the TASK-76/78
  teeth rewritten:
  - `FAKE_LOG_ACCEPTANCE_SHAPE` — a literal log whose TOP block is the
    marker of round N+1, with round N's work under it and the marker of
    round N below that. `test_item_is_found_under_the_next_round_marker`
    asserts the item is found there (`_l3_missing(["Y2"], …,
    round_no=104) == []`).
  - `test_old_bound_collapsed_the_window_at_acceptance` pins both
    shapes of the window (marker N on top, and marker N+1 on top) green
    — the old rule served only the first one.
  - `test_leading_marker_of_another_round_is_not_a_lower_bound` — a
    leading marker that is neither `round_no` nor `round_no + 1` still
    stops the scan: the upper bound is one specific round, not "any
    obstacle", so foreign work cannot buy a credit through it.
  - `test_round_under_review_shifts_when_the_holder_is_coordinator` —
    `_round_under_review()` on a substituted `REPO`/`BATON.json`:
    `holder=coordinator, round=105 → 104`, `holder=executor, round=105
    → 105` (and `round=1 → 0`). The live baton is never read or written
    by this test.
  - `test_round_under_review_and_live_baton_agree` — the same rule
    applied to the real `agent/BATON.json`, so the helper cannot drift
    away from the holder it claims to follow.
  - `test_strictness_holds_on_the_real_branch` — the boundary stays
    strict on real history (see the numbers below).

  **Red before the fix, quoted.** With the coordinator's upper-bound
  clause removed (back to "break at the marker of `round_no`"), same
  file, same command:

  ```
  $ python3 -m pytest tests/test_report_sections.py -o addopts='--strict-markers -m "not live"' -p no:randomly -q -k "found_under_the_next or old_bound_collapsed or not_a_lower_bound or round_under_review or strictness_holds"
  FF...F                                                                   [100%]
  __________________ test_item_is_found_under_the_next_round_marker ________________
  >       assert _l3_missing(["Y2"], FAKE_LOG_ACCEPTANCE_SHAPE, [],
                             round_no=104) == []
  E       AssertionError: assert ['Y2'] == []
  ______________ test_old_bound_collapsed_the_window_at_acceptance _______________
  >       assert _l3_missing(["Y2"], FAKE_LOG_ACCEPTANCE_SHAPE, [],
                             round_no=104) == []
  E       AssertionError: assert ['Y2'] == []
  ___________________ test_strictness_holds_on_the_real_branch ___________________
  >       assert _l3_missing(["Y1", "Y2"], log, [], round_no=104) == []
  E       AssertionError: assert ['Y1', 'Y2'] == []
  =========================== short test summary info ============================
  FAILED tests/test_report_sections.py::test_item_is_found_under_the_next_round_marker
  FAILED tests/test_report_sections.py::test_old_bound_collapsed_the_window_at_acceptance
  FAILED tests/test_report_sections.py::test_strictness_holds_on_the_real_branch
  3 failed, 3 passed, 20 deselected in 1.92s
  ```

  Three red on the acceptance shape, and — the part that matters — the
  real-branch probe too: the window collapsed to empty, so the guard
  called live commits `5dbad52`/`9da772f` missing. That is exactly the
  failure that locked the relay at hand time. The clause was then
  restored (`cp /tmp/trs-z1-good.py`) and the selection went green:
  `6 passed, 20 deselected`.

  **My own numbers (Z1, third bullet), real branch, `round_no=104`.**
  The coordinator measured the acceptance moment with the baton commit
  on top; on a working branch commits of the NEXT round sit above it,
  so `_log_from_top_marker()` truncates the live log to the acceptance
  shape before probing. Both shapes agree here because nothing of round
  105 had been committed yet when the measurement ran:

  | items probed | raw live log | acceptance-shape log | coordinator |
  |---|---|---|---|
  | `Y1, Y2` | `missing: []` | `missing: []` | `[]` |
  | `W1, W5` | `missing: ['W1', 'W5']` | `missing: ['W1', 'W5']` | `['W1','W5']` |
  | `W3` | `missing: ['W3']` | `missing: ['W3']` | `['W3']` |
  | `Z9` | `missing: ['Z9']` | `missing: ['Z9']` | `['Z9']` |

  Top block of the raw log at measurement time: `b03bc89 Эстафета: круг
  105, ход у executor — agent/TASK-79.md`; of the truncated log:
  `d7938ca Координатор: ТЗ-78 — … выдано ТЗ-79`.

## Blocked

- Nothing blocked. Z1 is committed; Z2 in progress.

## What not to trust

- `test_strictness_holds_on_the_real_branch` hard-codes `round_no=104`
  because that is the round whose work (Y1/Y2) the coordinator measured.
  It stays valid as long as markers 104/105 exist on the branch — they do
  not move — but it is a statement about history, not a live check of the
  current baton. `_round_under_review()` has its own live-baton test.
- The red-before-fix run was produced by deleting the coordinator's
  three-line clause in the working tree only, from a `/tmp` backup, and
  restoring it before the commit; the committed file is the fixed one.
  Anyone re-checking must restore first (`cp /tmp/trs-z1-good.py`
  equivalent: `git show` the parent version) — the mutation is not in git.
- Full-file run right now: `1 failed, 25 passed` — the failure is
  `test_done_items_have_code_commits_in_round` reading REPORT-78's
  "Items done: Y1, Y2" while the round under review is already 105. It
  resolves when STATE.json points at this report (same commit as Z1), the
  same interim redness as in round 103.

## Disputed

- (none yet this circle)

## HANDOFF

Status: PARTIAL — Z1 done and committed, Z2 ahead.
Arrival state: round 105, HEAD `b03bc89`, TASK-79 read in full.
Items not done: Z2 verification guard on the authorization line form.
NOW: Z2, step 1
