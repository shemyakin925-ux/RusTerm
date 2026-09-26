# REPORT-101 — hand never names an unborn report

## Done
- **L1** — `hand` writes a report skeleton for a `--report` file that is not
  in the tree and puts it into the same baton commit. All of it in
  `agent/relay.py`:
  - New helpers: `report_skeleton()`, `task_title()`, `outside_repo()`,
    `_write_report_skeleton()`, `_report_rollback()`.
  - Skeleton text: `# REPORT-N — <title line of the task>`, then `## Done`,
    `## Blocked`, `## What not to trust`, `## Disputed`, `## Runs`,
    `## HANDOFF`, then `Status: NOT STARTED`. The section list is a superset
    of the guard's `REQUIRED_SECTIONS`; the teeth import the live constant
    instead of restating it. No placeholder text anywhere in it.
  - Tree path (branch checked out): the file is written before `git add`, so
    `git commit --only` carries it. Not written when the file exists — an
    uncommitted draft of the receiving shift survives.
  - Plumbing path (foreign tree): the skeleton goes in as a blob only.
    Nothing is written into the coordinator's tree, and a report the branch
    already has is not overwritten (`cat-file -e base:report`).
  - Both post-creation refusals (commit failed, push rejected) call
    `_report_rollback()`: a refused hand leaves no skeleton in tree or index
    — the same law as the STATE stamp, ТЗ-99 J2.
  - Creation is announced on stdout naming the file, not silent.
  - Added by me (not asked for by the spec): `--report` naming a path outside
    the repository is refused before acceptance runs. `hand` writes files now,
    so the path has to stay inside the tree (P7). Checked early because a red
    acceptance costs ~19 min and must not be paid for a call that cannot work.
- New teeth: `tests/test_task101_l1_hand_creates_report.py`, 13 tests.

## Blocked
(none)

## What not to trust
- **"the whole two guard modules are green right after the hand" is a
  scratch-clone number, not an acceptance number.** Rig:
  `rt101-scratch/repo` — a clone of `agent/night-11` at `0e4c219`, private bare
  origin, `agent/acceptance.sh` stubbed to `exit 0`, no `core.hooksPath`. Those
  two modules read the real branch history, so they cannot be proven green
  inside a synthetic pytest sandbox; the permanent teeth run the six specific
  guard nodes on byte-copied guards instead. Acceptance for this commit ran in
  the pre-commit hook — its number is in `## Runs`.
- After a hand the guard is satisfied partly by absence:
  `test_done_items_have_code_commits_in_round` passes on a skeleton because an
  empty report has no "Items done" line, so it skips. The skeleton makes the
  baton commit self-consistent; it does not make the receiving round's report
  true.
- A `report` inherited from BATON (no `--report` flag in the call) takes the
  same code path, but only the flag case was measured in the rig.
- `outside_repo()` resolves with `os.path.commonpath`, so a symlinked report
  path that lands outside the root is not caught. Untested.

## Disputed
(none. Rulings 1, 2, 3 accepted as written — 2 belongs to TASK-100 K1 and is
unchanged here, 3 needed no work.)

## Runs
Times UTC. Live clone `rt-night11-exec`, HEAD `0e4c219`.

| # | command | result |
|---|---|---|
| 1 | `pytest tests/test_report_sections.py tests/test_state_report_tracked.py` (baseline, before any edit) | `33 passed, 1 skipped` |
| 2 | hand in the scratch rig naming `agent/REPORT-102.md` (no such file), old `relay.py`, then row 1's two modules | baton commit `099003a` = BATON + STATE only; guards `6 failed, 28 passed` — the red-before of this item |
| 3 | `pytest tests/test_task101_l1_hand_creates_report.py` before the fix | `8 failed, 5 passed` |
| 4 | same, after the tree+plumbing edits, before the heading fix | `2 failed, 11 passed` — both reds were `# REPORT-21.md` vs the spec's `# REPORT-21`; implementation fixed, teeth kept |
| 5 | `pytest tests/test_task101_l1_hand_creates_report.py tests/test_j1_hand.py tests/test_task99_j1_hand_stamps_state.py tests/test_task99_j2_refusal_names_staged.py` | `30 passed in 54.51s` |
| 6 | `pytest tests/test_task100_k1_stampable_state.py tests/test_task89_d2_relay_index.py tests/test_task98_h2_hand_clock.py` | `18 passed in 31.22s` |
| 7 | `pytest tests/test_report_sections.py tests/test_state_report_tracked.py` in the live clone after the relay.py edit | `33 passed, 1 skipped in 1.14s` |
| 8 | scratch rig, hand naming the absent `agent/REPORT-102.md` with the fixed `relay.py` | rc 0, stdout names the file and the word "заготовка"; commit `4b141a1` = BATON + STATE + `agent/REPORT-102.md`; heading `# REPORT-102 — hand never names an unborn report (REPORT-99 Disputed)` |
| 9 | row 1's two modules in the rig right after that hand | `33 passed, 1 skipped in 1.57s` (was 6 failed / 28 passed in row 2) — the spec's Done-when |
| 10 | scratch rig, a second hand naming the existing `agent/REPORT-101.md` | commit `4af4a70` = BATON + STATE only; `git hash-object` of the file before and after = `f8a4ea6020378ed2…`, worktree sha256 unchanged, committed bytes equal the worktree bytes |
| 11 | mutation proof, 5 ways to break the implementation, teeth re-run each time | M1 skeleton overwrites an existing report → 2 red (both "existing report" teeth); M2 no rollback → `test_a_refusal_after_the_skeleton_rolls_it_back` red; M3 no path check → `test_a_report_path_outside_the_repository_is_refused` red; M4 plumbing ships nothing → `test_plumbing_adds_the_blob_without_writing_into_a_foreign_tree` red; M5 silent creation → `test_the_skeleton_is_announced_not_silent` red. `relay.py` restored byte-identical after each run |
| 12 | pre-commit acceptance for the L1 commit (`I5_NESTED=1 bash agent/selfcheck.sh`, runs the whole suite) | see the close-out commit |

## HANDOFF
Status: WORKING
Items done: L1 — hand writes the report skeleton into the baton commit
Question for the coordinator: the outside-repo refusal is my own addition to
the item (see Done). Keep it, or move it into the backlog as its own item?
