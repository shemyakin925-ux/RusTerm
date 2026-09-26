# REPORT-100 — relay follow-ups from REPORT-98 Disputed

- **Branch:** `agent/night-11`, round 131, holder executor.
- **Spec:** `agent/TASK-100.md`. File scope: `agent/relay.py` (plus this
  spec's own `tests/` modules).
- **Budgets:** network 0, LLM 0 (git transport only, all sandboxes local).
- **Rulings carried in:** #2 → K1, #3 → K2, #4 → K3 (stamp outside the
  tree). #1 → TASK-101, #5 → no work.

## Arrival state (measured at round 131, before the first source edit)

HEAD `7ec6d80` («Эстафета: круг 131, ход у executor — agent/TASK-100.md»),
tree clean. BATON round 131, holder executor; `agent/STATE.json` —
`status: "handed"`, `updated_at: 2026-09-26T08:01:15Z`, written by the
coordinator's own `hand` (TASK-99 J1 working in production: the baton
commit carries STATE, `last_commit 8527f03` stayed, counters travelled).

`agent/REPORT-100.md` already existed (committed by the coordinator in
`117e6f6`), so TASK-101's skeleton rule was not needed this round.

No unit run was made before the first source edit — the pre-edit state of
the two modules this item rewrites is measured directly in Runs #1 (the
red-before pass against unmodified `relay.py` at `7ec6d80`), which says
more than a green baseline would.

## Done

### K1 — the hand gate believes the stamp, not the clock

Rethink of the TASK-98 H2 gate (`agent/relay.py`):

- `state_clock_refusal()`, `STATE_CLOCK_TOLERANCE_MIN`,
  `FIX_CLOCK_COMMAND` — **deleted**. Nothing else referenced them
  (`tests/test_state_clock.py` carries its own synthetic copy of the
  drift arithmetic; `agent/selfcheck.sh` O0 untouched — forbidden by the
  spec, and it still compares at commit time).
- `_stamp_source(plumbing, remote, branch)` (relay.py:933) — returns the
  *same* base `push_baton` merges the stamp into: the worktree
  `agent/STATE.json` on the tree path, `git show <remote>/<branch>` of it
  on the plumbing path. `None` means "no base".
- `state_stamp_refusal(base, where)` (relay.py:963) — refuses only where
  the stamp has nowhere to land: `base` present but not parseable as
  JSON, or parsed but not an object. Names the source (`where`), says
  what is lost («поля и счётчики прежней смены»), and gives a repair
  (`_stamp_repair`, relay.py:955 — `git checkout HEAD -- agent/STATE.json`
  for the tree, "fix it on origin" for a branch blob).
- `cmd_hand` (relay.py:1003–1012) — the gate sits where H2 sat: before
  `run_acceptance`, refusal through `die_kept` (J2), `--force` still an
  exit but it prints the retired rule's name and the first refusal line.
  A plumbing shift fetches before the gate, so the check reads the blob
  that will actually be committed rather than a stale
  `refs/remotes/origin/…`.
- **Absent STATE is not a refusal.** `hand` already creates it (J1), and
  there is nothing to lose; the retired H2 behaved the same way, and the
  other relay sandboxes (`tests/test_j1_hand.py`,
  `tests/test_task89_d2_relay_index.py`) depend on it.

Deviation from the item's sketch, declared: the body says "stamp first,
then the H2 check sees a fresh clock". Done that way, a refused hand
leaves a stamped `agent/STATE.json` (`status: "handed"`, live clock) for a
transfer that did not happen — J2's `_state_backup/_state_restore` only
covers writes made inside `push_baton` — and on the plumbing path the
tree file is not the commit's base at all, so stamping it would be
side-effect without protection. Same outcomes, no such window: the gate
inspects the source the stamp will be merged into. Ruling 1 of TASK-98
("the Done-when gate governs") is satisfied literally:

> STATE 500 min old, plain `hand` (no `--force`) proceeds and the
> committed STATE carries a fresh `updated_at`; malformed STATE → refused
> with words — `test_a_state_500_minutes_old_hands_without_force`,
> `test_an_unparsable_state_refuses_before_acceptance`.

Teeth (new `tests/test_task100_k1_stampable_state.py`, 6 tests / 42
assert lines; `tests/test_task98_h2_hand_clock.py` re-ruled in place,
7 tests / 29 assert lines against 27 removed):

| File | Pin | Proves |
|---|---|---|
| h2 | `test_a_state_44_minutes_old_hands_and_gets_a_live_clock` | the round-129 refusal is gone; tree *and* commit carry a live clock |
| h2 | `test_a_clock_44_minutes_ahead_hands_too` | future stamps no longer refuse (H2 used `abs(drift)`) |
| h2 | `test_a_state_500_minutes_old_hands_without_force` | K1 Done-when, verbatim number |
| h2 | `test_an_unparsable_clock_value_is_stamped_over` | `updated_at="вчера после обеда"` is a value, not a gate |
| h2 | `test_a_state_without_a_clock_gets_one` | the old «нет updated_at» refusal is retired |
| h2 | `test_a_fresh_state_reaches_acceptance_and_hands` | kept unchanged — the green path still works |
| h2 | `test_force_is_not_required_for_a_stale_clock_and_stays_silent` | no `force` substring in the output — a routine path must not read as an exception |
| k1 | `test_an_unparsable_state_refuses_before_acceptance` | rc≠0, no `.acceptance-ran` trace, words + repair, BATON unmoved, bad file not touched |
| k1 | `test_a_json_array_instead_of_an_object_refuses` | array → words, and no traceback (old code hit `.get` on a list) |
| k1 | `test_an_absent_state_is_created_by_hand_and_not_refused` | absent STATE → hand writes the four stamp fields itself |
| k1 | `test_a_valid_object_with_absurd_fields_still_hands_and_keeps_them` | the border is mergeability, not content (`item=42`, `requests="тридцать девять"`) |
| k1 | `test_force_over_an_unstampable_state_proceeds_out_loud` | exit exists and is audible |
| k1 | `test_plumbing_hand_gates_on_the_branch_blob_not_this_worktree` | two phases: bad blob + good worktree → refuse naming `agent/night-k1:agent/STATE.json`; fixed blob → same call hands |

Every h2 tooth carries a negative pin (`DRIFT_WORDS`) that reddens if the
drift comparison comes back anywhere in the output.

Measured, this round:

- red-before on unmodified relay.py: `10 failed, 3 passed` over the two
  modules — the six re-ruled clock teeth, `test_a_valid_object_with_absurd_fields…`
  and three of the K1 teeth; the three green ones were already true
  (fresh clock hands; absent STATE hands; `--force` over garbage handed
  via `_state_bytes`' fallback line).
- green-after: `13 passed`; neighbouring relay modules together
  `41 passed` (`test_j1_hand`, `test_task89_d2_relay_index`,
  `test_task99_j1/j2`, `test_no_shared_tmp`, `test_state_clock`);
  all other relay-referencing guards `35 passed`;
  `test_report_sections.py + test_docs_truth.py` `34 passed, 1 skipped`.
- mutation campaign (each mutation reverted after its run; the script is
  outside the clone, `../rt100-scratch/mutate_k1.py`):

| Mutation | Result |
|---|---|
| M1 gate moved after `run_acceptance` | red — 2 K1 order teeth |
| M2 plumbing reads the worktree (`plumbing = False`) | red — plumbing tooth |
| M3 drop `isinstance(parsed, dict)` | red — array tooth |
| M4 unparsable → silent `{}` base | red — 3 teeth |
| M5 re-add a `updated_at`-missing refusal | red — h2 tooth 5, and the `DRIFT_WORDS` pin names the phrase |

## Blocked

(none)

## What not to trust

- **The live `hand` path is not exercised by K1 until the baton moves.**
  Sandboxes prove the gate; a real `hand` on `agent/night-11` runs once
  per round, at close-out. If K1 breaks the production hand (for example
  by fetching before the gate in a tree the coordinator holds), the first
  proof of that is this round's hand commit.
- `agent/CONTEXT.md:32` states, as an accepted TASK-98 fact, that "hand
  checks STATE clock". After K1 that sentence is stale — CONTEXT.md is the
  coordinator's file, I did not touch it.
- K2 and K3 are not started yet in this section of the report.

## Disputed

(none)

## Runs

| # | Command | Result |
|---|---|---|
| 1 | `pytest -q` h2 + k1 on unmodified relay.py | 10 failed, 3 passed (red-before captured) |
| 2 | `python3 -m py_compile agent/relay.py` | ok |
| 3 | `pytest -q` h2 + k1 after the gate | 13 passed |
| 4 | `pytest -q` 8 relay/hand modules | 41 passed |
| 5 | `pytest -q` 8 other relay-referencing guards | 35 passed |
| 6 | `pytest -q test_report_sections.py test_docs_truth.py` | 34 passed, 1 skipped |
| 7 | `python3 ../rt100-scratch/mutate_k1.py` | 5/5 mutations red, relay.py restored byte-identical |
| 8 | commit (nested acceptance) | see below |

## HANDOFF

Status: NOT STARTED — K1 in progress, K2/K3 to follow.
