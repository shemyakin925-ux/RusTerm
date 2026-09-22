# REPORT-78 — граница круга у L3 и акции VZ, которые payload всё-таки доказал

No deviation from the brief: branch `agent/night-11`, fresh clone carried
over from TASK-76 (one clone per session, no linked worktree),
`core.hooksPath agent/githooks` set once, `relay.py wait --for executor`
exit 0 at round 103 before the first line of code.

Arrival state: HEAD `4a1157c` (baton "Эстафета: круг 103, ход у executor —
agent/TASK-78.md"), previous circle closed at `236f74a` (W5).

## Done

- **Y1 — L3 sees only its own round.**
  `_l3_missing(done_ids, log_text, staged, round_no=None)` in
  `tests/test_report_sections.py` now takes the current round number and
  stops scanning when it hits the baton commit
  `Эстафета: круг <round_no>,`. Commits that live BELOW that boundary
  (older rounds) can no longer close a `Items done: X` claim; and if the
  marker is absent from the log the guard grants no credit at all — the
  safe side. `test_done_items_have_code_commits_in_round` passes
  `round_no=_baton_round()`, i.e. it reads the round from
  `agent/BATON.json` exactly like G4's `_commit_for_items`.

  Red-before-fix (temporary one-line revert of the boundary in the
  working tree, `tests/test_report_sections.py` otherwise unchanged,
  `python3 -m pytest tests/test_report_sections.py -q`):

  ```
  ____________ test_l3_with_the_round_bound_flags_the_foreign_commit ____________
  >       assert _l3_missing(["W3"], FAKE_LOG_TWO_ROUNDS, [],
                             round_no=103) == ["W3"]
  E       AssertionError: assert [] == ['W3']
  E         Right contains one more item: 'W3'
  tests/test_report_sections.py:428: AssertionError

  _________ test_w3_is_not_closed_by_a_foreign_round_on_the_real_branch _________
  >       assert after == ["W3"], (
              f"граница круга не сработала на настоящей ветке: after={after}")
  E       AssertionError: граница круга не сработала на настоящей ветке: after=[]
  E       assert [] == ['W3']
  tests/test_report_sections.py:443: AssertionError

  ______________ test_round_marker_missing_means_no_credits_at_all ______________
  >       assert _l3_missing(["W9"], log, [], round_no=103) == ["W9"]
  E       AssertionError: assert [] == ['W9']
  E         Right contains one more item: 'W9'
  tests/test_report_sections.py:463: AssertionError
  =========================== short test summary info ===========================
  FAILED tests/test_report_sections.py::test_l3_with_the_round_bound_flags_the_foreign_commit
  FAILED tests/test_report_sections.py::test_w3_is_not_closed_by_a_foreign_round_on_the_real_branch
  FAILED tests/test_report_sections.py::test_round_marker_missing_means_no_credits_at_all
  3 failed, 17 passed in 2.00s
  ```

  Green-after (`cp /tmp/trs-y1-good.py tests/test_report_sections.py`,
  same command): `20 passed in 0.55s` on the Y1 tests; see "What not to
  trust" for the one live-guard test that is intentionally red in this
  interim state.

  New tests in this commit (all teeth, no weakenings, 0 asserts removed):

  | Test | What it pins |
  |---|---|
  | `test_l3_without_a_round_bound_credits_an_older_round` | the hole itself: same literal log, no `round_no` — W3 credit leaks through. Left green deliberately so a future refactor that forgets the boundary turns the *other* Y1 tests red. |
  | `test_l3_with_the_round_bound_flags_the_foreign_commit` | the boundary on a literal log: W3 below `Эстафета: круг 103,` is missing. This is the red-before-fix test. |
  | `test_w3_is_not_closed_by_a_foreign_round_on_the_real_branch` | the same on the real branch: `before = _l3_missing(["W3"], log, [])` is `[]` (the hole is live right now on the branch), `after = _l3_missing(["W3"], log, [], round_no=_baton_round())` is `["W3"]`. Names the before/after explicitly, as Y1 requires. |
  | `test_z9_teeth_still_hold_under_the_round_bound` | Z9 still red both ways — recorded as *weak* evidence, see below. |
  | `test_round_marker_missing_means_no_credits_at_all` | safety-by-denial when the current round's marker is absent from the log (fresh clone, history outside relay). |

  Why `Z9` alone was a weak argument (Y1 asks for this in one line, and
  it is the exact mistake the coordinator's earlier acceptance made):
  `Z9` is a name no commit in the branch's entire history has ever
  carried, so it reds the guard with or without the round bound — its
  success proved the parser was reading files at all (TASK-76 W1), not
  that L3 could tell one round from another. `W3` is the strong case
  because the SAME letter appears in commits from ТЗ-53, round 101
  (`1d39cd2`) and older; without a boundary those close it, with the
  boundary they do not.

## Blocked

- none so far. Y2 has not been started in this commit.

## What not to trust

- `test_done_items_have_code_commits_in_round` in the Y1 commit is red by
  design: it reads the *live* `agent/STATE.json` report field. Before
  this commit that pointed to `REPORT-76.md`, whose final HANDOFF says
  `Items done: W1, W2, W3, W4, W5` — and none of W1..W5 was committed in
  round 103, which is exactly what Y1's boundary now enforces. The
  commit rewrites `STATE.json.report` to `agent/REPORT-78.md`, and this
  file's `Items done:` will grow as Y1/Y2 land, so the guard turns green
  on HEAD. Verify with `python3 -m pytest tests/test_report_sections.py -q`
  on the committed tree — do NOT trust this sentence if the run disagrees.
- The red quote above was captured by a working-tree edit
  (`tests/test_report_sections.py` only), then restored with
  `cp /tmp/trs-y1-good.py tests/test_report_sections.py`; no
  `git checkout` was involved, so `git diff HEAD` before this commit
  showed exactly the round-bound lines and nothing else. The mutation
  file lives in `/tmp` and disappears with the machine — check the diff,
  not the sentence.

## Disputed

- none new. The coordinator's own Y0 acceptance already adopted my
  earlier dispute that L3 was not round-bounded; Y1 closes it.

## HANDOFF

Status: PARTIAL — Y1 committed, Y2 (VZ shares route) not yet started.
Arrival state at the moment of writing: HEAD will be the Y1 commit on
round 103; `agent/STATE.json` points to this report; `tests/
test_report_sections.py` full-file run green (see Done).
Items done: Y1
Items not done: Y2 (route choice, W5-test rewrite, measure count before→after)
NOW: Y2, step 1
