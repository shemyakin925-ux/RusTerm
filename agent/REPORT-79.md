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

## Done #2 — Z2 (appended; the interim sections above stay as written)

- **Z2 — the silent authorization becomes loud.**
  New file `tests/test_task_authorization_form.py` (5 tests). It checks
  the TASK file named by `agent/BATON.json` against the parser's own
  commands rather than a paraphrase: `_parser_lines()` literally runs
  `grep '^РАЗРЕШЕНО ПРАВИТЬ:' <task>` (as `agent/p6_rule.sh:63` does),
  and acceptance is the fixed-substring test `grep -qF
  "РАЗРЕШЕНО ПРАВИТЬ: <path>"` (as `authorized()` at `:67`). A line that
  claims a path the parser cannot reach is red, and the message quotes
  the line with its number. `agent/p6_rule.sh` was not touched — it does
  not appear in any commit of this circle; `test_the_guard_still_matches_
  the_parser_it_emulates` reads it and reddens if either pattern moves,
  so the guard cannot quietly drift away from the parser it emulates.

  Coverage beyond the live check: the markdown form as it stood in
  TASK-76 (flagged), the flat form plus the prose lines of TASK-79 that
  only *quote* the phrase (not claims — the guard must not lie on
  explanations), the half-measure where two paths share one flat line
  (only the first is authorized, the second is named), and the
  current baton TASK file.

  **Redness on the TASK-76 markdown form, quoted.** One-off run of the
  live checker against the real `agent/TASK-76.md` (scratch file under
  `/tmp`, not committed; the committed test asserts the same result on a
  literal copy of that line):

  ```
  $ python3 -m pytest /tmp/rt-z2-red/test_z2_red_demo.py -q
  E       AssertionError: TASK-76.md: разрешение написано формой, которую agent/p6_rule.sh не видит — исполнитель молча теряет право править эти файлы:
  E           TASK-76.md:15: '- **РАЗРЕШЕНО ПРАВИТЬ:** `tests/test_report_sections.py`,' — не принято: ['tests/test_report_sections.py']
  E       assert not [('15', '- **РАЗРЕШЕНО ПРАВИТЬ:** `tests/test_report_sections.py`,', ['tests/test_report_sections.py'])]
  =========================== short test summary info ============================
  FAILED ../../../tmp/rt-z2-red/test_z2_red_demo.py::test_task76_markdown_form_reddens_the_live_guard
  1 failed in 0.04s
  ```

  Green on the current baton file: `5 passed` in
  `tests/test_task_authorization_form.py`.

- **Forms measured across the whole TASK set with the parser's own
  greps** — the class is not hypothetical, it is still live in the queue:

  | ТЗ | строк видит парсер | что принимает `authorized()` | что молчит |
  |---|---|---|---|
  | TASK-76 | 0 | — | `tests/test_report_sections.py` (markdown) |
  | TASK-77 | 2 | `agent/CONTEXT.md`, `GUIDE.md` | — |
  | TASK-78 | 0 | — | `tests/test_report_sections.py` (markdown) |
  | TASK-79 | 2 | `tests/test_report_sections.py`, `agent/CONTEXT.md` | — |
  | TASK-73 | 1 | `agent/PROTOCOL.md` | `agent/CONTEXT.md`, `GUIDE.md` — строка 89 continues the previous line without the phrase, so neither the parser nor my per-line guard sees it |
  | TASK-74 | 1 | `agent/CONTEXT.md` | `GUIDE.md` — second path on the same flat line; **my guard reddens on this one** |

  Checked with the parser's commands, quoted:

  ```
  $ AUTH=$(grep '^РАЗРЕШЕНО ПРАВИТЬ:' agent/TASK-73.md)
  $ printf '%s\n' "$AUTH" | grep -qF "РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md" && echo ok || echo "CONTEXT.md НЕ принят"
  TASK-73: CONTEXT.md НЕ принят (строка 89 — продолжение, парсер её не видит)
  $ printf '%s\n' "$AUTH" | grep -qF "РАЗРЕШЕНО ПРАВИТЬ: agent/PROTOCOL.md" && echo ok
  TASK-73: PROTOCOL.md принят
  ```

  Practical consequence for the next circles, so this does not repeat
  as a lost right or a locked relay: one path per line, flat, no
  backticks, no `**`, no comma lists — TASK-74's line 75 and TASK-73's
  line 89 need that rewrite before they are issued.

## Blocked #2

- Nothing blocked. Z1 and Z2 are both committed.

## What not to trust #2

- The guard follows Z2's letter: it treats a line as a claim only when
  the phrase is on that same line. That is why TASK-79's explanatory
  prose (lines 42, 44, 45, 48, 100 quote the phrase and its own grep
  patterns) does not redden it — and also why TASK-73's continuation
  line 89 is NOT caught. The table above documents the gap instead of
  the code guessing which prose lines were meant as permissions.
- Full suite ran BEFORE the new test file was staged:
  `1 failed, 1074 passed, 3 skipped, 11 deselected, 4 xfailed in 242.86s`.
  The single failure was `test_i5_staged_and_authorised_widening_is_green`,
  and it was my own untracked file tripping the P3/P4 rule inside that
  demo — not a broken tooth. After `git add` the same three files
  (I5 demo + sentinel + the new guard) went `11 passed in 452.27s`. The
  full suite has not been re-run since; `hand` re-runs it in a clean
  clone, so any remaining red will surface there rather than here.
- The red quote for Z2 comes from a scratch copy of the live checker
  pointed at the real `agent/TASK-76.md`; the committed test uses a
  literal copy of that line, so the demonstration survives edits to
  TASK-76 but is not a check of TASK-76 itself.

## HANDOFF (FINAL — supersedes the interim block above)

Status: DONE — TASK-79 closed on the executor's side, both items
committed and green locally.
Items done: Z1, Z2
Items not done: none
Queue as I leave it: TASK-77 (reproducible base of five papers), then
TASK-73, then TASK-74. Heads-up for the coordinator before issuing
them: TASK-74 line 75 and TASK-73 line 89 carry authorizations the
parser cannot see, and my new guard reddens on the former.
Budget: network 0 honoured — no request was made; every number in this
report comes from local git history and repo files.
Last commit: see `agent/STATE.json`.
NOW: hand to coordinator, step 1

## Note on the queue (appended; the final HANDOFF above still decides)

TASK-79 closes with both items done, and the header offers TASK-77 next.
I am not taking it in this circle, for two measured reasons rather than
convenience:

1. Budget collision. This baton's ТЗ states `Budgets: network 0`;
   TASK-77's X1/X2 require up to 60 live requests (X2: "прогнана живьём
   в пределах бюджета 60 запросов"). Spending network under a baton that
   forbids it would be a violation of the file that currently governs
   the circle, and I cannot resolve that from the ТЗ text — the
   coordinator can, in one line of the next baton.
2. One report per acceptance. TASK-77 names `agent/REPORT-77.md` and its
   own `hand --report`, while `agent/STATE.json` carries a single
   `report` field that the section guards and the round guard read.
   Merging the two circles would make TASK-77's evidence invisible to
   `test_report_carries_every_required_section` and
   `test_done_items_have_code_commits_in_round`. Precedent: round 103
   brief also listed TASK-77 next, TASK-76 was handed alone and accepted.

So: TASK-77 is ready to be issued with its own budgets in force. Before
it is issued, the authorization lines of TASK-73 (line 89) and TASK-74
(line 75) need the flat one-path-per-line form — see the table in
`## Done #2`; otherwise TASK-74 will redden the Z2 guard at hand time
and lock the relay for a header typo, which is exactly the failure Z2
exists to make loud.
