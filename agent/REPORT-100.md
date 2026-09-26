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

### K2 — a red verify keeps its tree

Ruling #3 of the REPORT-98 disputed list: H3 made a red run remove the
tree it had just created, so the one artifact worth looking at after a
failing acceptance — the checked-out tree, with whatever the run left in
it — disappeared, and inspecting it meant re-running. Green keeps H3's
behaviour; red keeps the tree and says so on the last line.

`cmd_verify` (`agent/relay.py:795–812`):

- `red = proc.returncode != 0` is captured right after the acceptance
  subprocess, inside the `try`.
- The `finally` removes the tree only when `ours and not red`.
- After the exit-code line, `ours and red` prints as the last line of
  stdout: `дерево оставлено для разбора: <path> — удалит следующий verify`.
- `red` is initialised to `True`: if the subprocess call itself raises
  (bash gone, SIGINT between the checkout and the run) there is no exit
  code to explain, so no promise line is printed, and the tree is kept
  and stamped — the next run's sweep collects it. Declared choice, not
  an oversight: a crashed run is the case where the tree is most useful.
- Both branches stay inside `ours`. A tree the operator named with
  `--worktree` is neither removed nor promised to anybody.

Removing the kept tree is not new code: the stamp written at
`worktree add`, plus the dead pid of the finished run, make it exactly
the case `sweep_stale_verify_trees` already handles at the start of the
next `verify` (H3).

Teeth, `tests/test_task98_h3_verify_trees.py` (6 → 8):

| Tooth | Pins |
|---|---|
| `test_red_run_keeps_its_tree_and_names_it_last` (replaces `test_red_run_removes_the_tree_too`) | rc 5; directory and worktree registration survive; the promise is literally the last line; no removal message |
| `test_the_next_run_removes_a_tree_left_by_a_red_one` | the first red tree is named, unregistered and gone after the next run, while that run's own red tree survives |
| `test_a_red_run_in_a_foreign_tree_promises_nothing` | `--worktree` tree: red, present, registered, and neither message appears |
| green tooth, +1 assert | a green run does not print the promise |

Measured, this item:

- red-before — the module against `HEAD:agent/relay.py` (K2 source
  restored afterwards, `git diff --stat` back to the two K2 files):
  `.FF.....` — 2 of 8 failed, both of them the new red-run teeth.
- green-after — `tests/test_task98_h3_verify_trees.py` with
  `test_relay_verify_worktree.py`, `test_cli.py`, `test_manual_seats.py`:
  59 passed, 0 failed.
- mutation campaign (`../rt100-scratch/mutate_k2.py`, every mutation
  reverted; relay.py compared byte-identical afterwards → True):

| Mutation | Result |
|---|---|
| M1 red tree removed as before K2 | red — both new red teeth |
| M2 promise without the path | red — last-line tooth |
| M3 promise printed for a green run too | red — green tooth's new negative pin |
| M4 promise printed for a foreign tree | red — foreign-tree tooth |
| M5 stale sweep disabled | red — next-run tooth + H3's own sweep tooth |
| M6 owner stamp not written | red — next-run tooth + the stamp tooth |

### K3 — the owner stamp is a sibling of the tree

Ruling #4 of the REPORT-98 disputed list. H3 proved ownership by writing
`.relay-verify-owner` *inside* the acceptance tree, and the live run at
`2026-09-25T19:18Z` named the cost: check 13 («нет мусора вне git») reads
`git status --porcelain` of that same tree, and the I5 cases' nested
selfcheck reads it too — 3 failures, all on `?? .relay-verify-owner`.
Hiding the file behind a `.gitignore` line made the tree green and the
guard softer at the same time: the line was the only reason the exemption
existed, and `untracked_files()` had to know the file by name.

`agent/relay.py`:

- `VERIFY_OWNER` → `VERIFY_OWNER_SUFFIX = ".owner"`; `verify_owner_path()`
  resolves `<parent>/<tree-name>.owner` (relay.py:714). The stamp is
  written next to the tree at `worktree add`; the tree receives nothing.
- `remove_verify_tree()` unlinks the sibling after the tree is gone
  (`OSError` → ignore: it may already be gone).
- `sweep_stale_verify_trees()` gained a second pass for stamps that
  outlived their tree — killed between `worktree remove` and the unlink.
  Candidate must carry our prefix, a readable dict, an integer pid and a
  dead pid; everything else (a foreign `*.owner`, a stamp of a live run,
  a stamp whose tree still stands) is left alone.
- `untracked_files()` has no exemptions at all (relay.py:660).
- Foreign trees get nothing at all: `stamp_verify_tree` is only reached
  for `ours`, so `--worktree` stays clean inside *and* beside.

Teeth, `tests/test_task98_h3_verify_trees.py` (8 → 10, one rename):

| Tooth | Pins |
|---|---|
| `test_the_stamp_is_a_sibling_and_nothing_lands_in_the_tree` (replaces `test_the_stamp_lies_in_the_tree_and_is_not_trash`) | stub sees `МЕТКА: есть` beside it and `ВНУТРИ: нет`; `git status --porcelain` empty with the **real** `.gitignore` copied into the fixture repo; sandbox `/tmp` holds only the tree and its sibling |
| `test_the_repo_gitignore_no_longer_hides_an_in_tree_stamp` | the line is gone from the repo file — the exemption cannot come back as a hide |
| `test_an_orphan_owner_stamp_is_swept_too` (new) | dead-pid orphan removed; `kakaya-to-sveshaya.owner` and a live-pid orphan both survive |
| green / red / next-run / stale-sweep / no-stamp / live-pid teeth, +1 assert each | the sibling, not the in-tree file, is what appears and disappears |

Measured, this item:

- red-before — module against `HEAD:agent/relay.py`: `.F..FF..FF`,
  5 of 10 failed (both K2 red teeth plus the three new/renamed K3
  claims).
- green-after — `tests/test_task98_h3_verify_trees.py` alone: 10 passed;
  with relay/hand neighbours: 44 passed; with `.gitignore`-reading and
  output guards (`test_task81_b3_build`, `test_no_shared_tmp`,
  `test_report_sections`, `test_docs_truth`, `test_cli`,
  `test_manual_seats`): 89 passed, 1 skipped.
- mutation campaign (`../rt100-scratch/mutate_k3.py`, each mutation
  reverted; relay.py and `.gitignore` compared byte-identical at the end
  → True). Whole module run per mutation, so the red list is measured,
  not predicted:

| Mutation | Result |
|---|---|
| M1 stamp written inside the tree again | red — sibling tooth, red-run tooth, stale-sweep tooth (fixtures stamp the sibling; the mutant looks inside) |
| M2 sibling never unlinked on removal | red — green tooth + sibling tooth (its `/tmp` leftover pin) |
| M3 orphan pass disabled | red — orphan tooth |
| M4 orphan pass ignores the live pid | red — orphan tooth's new live-pid pin |
| M6 tree without a stamp treated as ours | red — next-run tooth + stale-sweep tooth. The no-stamp tooth stayed green: the fabricated `pid: 0` answers `pid_alive` as alive, so this mutant is caught from two sides, not from the «don't touch foreign» side |
| M5 `.relay-verify-owner` line restored in `.gitignore` | red — gitignore tooth |

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
- K2's kept red tree is a directory under `/tmp` that now survives a
  failing run. Nothing in this round measured how long one sits there if
  `verify` is never run again — the sweep only fires at the start of the
  next run. The K1 `hand` gate is unaffected.
- K3's tree-purity proof is a stub's `git status --porcelain` in a
  sandbox. The claim that matters for the round is the real acceptance's
  check 13, and the only evidence for that is this round's live
  acceptance at the K3 commit (the `commit K3` row in Runs). Until that
  line carries its numbers, "13 is green" is a prediction.
- Trees stamped by the *old* scheme (`.relay-verify-owner` inside) are
  recognised by nothing after K3: `sweep_stale_verify_trees` looks for
  the sibling, so such a tree is left in place rather than deleted —
  safe direction, but it needs a manual removal. Measured here: zero
  `rusterm-relay-verify-*` entries under either `/tmp` or the session
  temp dir at close-out, so nothing on this machine is in that state.
- The stamp now lives in the same directory the tree is created in. A
  `--worktree` path the operator owns is still never stamped, but if a
  default-path parent holds a foreign file named exactly
  `rusterm-relay-verify-…owner`, that file is a sweep candidate once its
  pid reads as dead. The fixture pins only the two shapes we tested
  (`kakaya-to-sveshaya.owner`, live pid), not arbitrary names.

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
| 8 | commit K1 — pre-commit runs `selfcheck.sh`, which runs the full acceptance nested | `Итог: пройдено 13, провалено 0`, `Принято.`, `SELFCHECK OK`, rc 0 → `f7d7750`; wall clock 10:09:24→10:23:10Z |
| 9 | `pytest -q tests/test_task98_h3_verify_trees.py` (K2 teeth, unmodified relay.py) | 2 of 8 failed (`.FF.....`) — red-before captured |
| 10 | same module against `HEAD:agent/relay.py`, then relay.py restored | same 2 failures; `grep -c "дерево оставлено" agent/relay.py` → 1 after restore |
| 11 | `python3 -m py_compile agent/relay.py` | ok |
| 12 | `pytest -q` H3 + `test_relay_verify_worktree` + `test_cli` + `test_manual_seats` | 59 passed |
| 13 | `python3 ../rt100-scratch/mutate_k2.py` | 6/6 mutations red, relay.py restored byte-identical |
| 14 | commit K2 — same hook chain | `Итог: пройдено 13, провалено 0`, `Принято.`, `SELFCHECK OK`, rc 0 → `ee34ced`; wall clock 10:33:31→10:47:01Z |
| 15 | `pytest -q tests/test_task98_h3_verify_trees.py` (K3 teeth, source at `HEAD`) | 5 of 10 failed (`.F..FF..FF`) — red-before captured |
| 16 | `python3 -m py_compile agent/relay.py` | ok |
| 17 | `pytest tests/test_task98_h3_verify_trees.py` | 10 passed |
| 18 | `pytest` 10 relay/hand neighbour modules (H3 worktree, J1, J1-STATE, H2, K1, state clock, J3, K1-skip, guard, D2 index) | 44 passed |
| 19 | `pytest` `.gitignore`/tmp/report/docs guards + `test_cli` + `test_manual_seats` | 89 passed, 1 skipped |
| 20 | `python3 ../rt100-scratch/mutate_k3.py` | 6/6 mutations red; relay.py and `.gitignore` restored byte-identical |
| 21 | `ls -d /tmp/rusterm-relay-verify-*` and the same in the session temp dir | 0 entries — no old-scheme trees left to migrate |
| 22 | commit K3 — same hook chain, the first acceptance with no `.gitignore` exemption | see below |

## HANDOFF

Status: NOT STARTED — K1 in progress, K2/K3 to follow.
