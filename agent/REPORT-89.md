# REPORT-89 — TASK-89: the round boundary comes from the data, not the header

Round 125, branch `agent/night-11`, spec `agent/TASK-89.md`. Budget: network 0
— honoured, nothing in this round touched a data API; the only network use is
`git` (clone + push), which the relay protocol requires.

## Arrival state (measured at round 125, before the first source edit)

* The shift clone under `/tmp` is gone again — `ls /private/tmp/rt-*` → `no
  matches found`, so `/tmp/rt-night11-exec` and every rehearsal tree from round
  123 had been swept between sessions. Nothing committed was lost: the branch
  was re-cloned from `origin` into
  `Documents/Qoder/2026-09-22/c597aa77/rt-night11-exec`, a location outside
  `/tmp`, with `core.hooksPath=agent/githooks`.
* `git log --oneline -1` → `69eb0c0 Эстафета: круг 125, ход у executor —
  agent/TASK-89.md`; `git status --porcelain | wc -l` → `0`; `HEAD ==
  origin/agent/night-11`.
* `agent/BATON.json`: holder=executor, round=125, task=`agent/TASK-89.md`,
  report=`agent/REPORT-89.md`, note — «TASK-88 accepted (fresh clone
  13/0). Disputed 1-5 upheld -> TASK-98 (H1-H4); #5 verdict recorded by
  coordinator in CONTEXT. Queue: 89 -> 98 -> 97 -> 92 -> 93 -> 87 G1 -> 94
  E3-E8 -> 85 -> 86.»
  TASK-88's five asks therefore became a spec, not a rejection, and entry 5 (no
  honest place for the close-out verdict) was ruled «recorded by coordinator».
* `agent/TASK-89.md` at this head is byte-identical to the version read before
  the hand (`git diff ddc0f4b HEAD -- agent/TASK-89.md` → empty).
* Baseline of the file I am about to edit, `python3 -m pytest
  tests/test_report_sections.py -o addopts="" -q` at `69eb0c0`:
  `1 failed, 27 passed in 0.36s`. The failure is bookkeeping, not a defect —
  `agent/STATE.json` still named `agent/REPORT-88.md`, whose items are outside
  round 125's window:

  ```
  E  AssertionError: пункты ['C1', 'C2', 'C3'] объявлены сделанными,
     но коммита круга с реализацией (не только tests/) не найдено
  ```

  Closing it is exactly the rule `tests/test_state_report_tracked.py` states:
  a new report is named by the commit that creates it. STATE is stamped to this
  file in the D1 commit below.
* Marker census on the live branch (`Эстафета: круг N,` in the first line of a
  `%x1e` block, newest-first index positions): 100→127, 101→115, 102→109,
  103→107, 104→101, 105→99, 106→95, **no 107**, 108→83 — D0's story about the
  missing marker 107 confirmed by counting, not by trusting the quote.

## Pre-validation (scratch worktree, no writes to the shift clone)

Every measurement below was taken in a detached worktree of the shift clone
(`rt89-prep` at `69eb0c0`), and the files were copied into the clone only once
green. The clone's own index and `COMMIT_EDITMSG` stay untouched by it.

## Done

### D1 — a coordinator commit is not an implementation

**The hole, measured before touching anything.** Round 107's window on the live
branch, `_log_from_top_marker(log, round_no=107)` then `_l3_missing(probe, …,
[], round_no=107)`, at `69eb0c0` (the coordinator's own D0 table reproduced
exactly):

| probe | before D1 | after D1 |
|---|---|---|
| `A1, A2, A3, A4` | `[]` | `[]` |
| `Y1` | `['Y1']` | `['Y1']` |
| `Q9` | `['Q9']` | `['Q9']` |
| `Z1` | `[]` — wrong | `['Z1']` |

`Z1` was credited by `ca678a1` «Координатор: ТЗ-79 — Z2 принят, Z1 возвращён;
срез истории привязан к кругу; выдано ТЗ-80», which touches
`agent/TASK-80.md` — a non-test file, so the old rule read the acceptance
verdict as the implementation of someone else's item.

**Rule.** `_l3_missing` strips the `%h` token from a block's first line and
skips the block entirely when the subject starts with `Координатор:` or
`Эстафета:`. The relay-marker branch still runs first, so `Эстафета: круг N,`
keeps its reset/break behaviour; what is newly excluded is a relay header that
is *not* a round marker (`Эстафета: пауза`) and every coordinator verdict.

**Teeth, shown red before the fix.** `test_a_coordinator_commit_is_not_an_
implementation` (literal log: a coordinator block naming `Z1` with
`agent/TASK-80.md` in its files, an ordinary work block naming `Y2` with
`rusterm/normalize/concepts.py`, bounded by markers 108 and 107) and
`test_a_relay_header_that_is_not_a_round_marker_is_not_an_implementation`:

```
E  AssertionError: assert [] == ['Z1']
E  AssertionError: assert [] == ['Q1']
2 failed, 28 deselected in 0.03s
```

After the fix both are green, and the same literal also pins the direction that
must not break — the work block in it still gets its credit (`Y2 → []`).

**Third tooth, on the real branch**: `test_a_coordinator_verdict_credits_
nothing_on_the_real_branch` asserts round 107's `A1…A4 → []`, `Y1, Q9 →
['Y1','Q9']` and `Z1 → ['Z1']`.

**What D1 necessarily invalidated: the pinned table `WINDOW_OF_ROUND_104`.**
The rule change reddened two existing tests, so the claim they pinned was
measured rather than defended. Round 104's window contains exactly three blocks:
`b03bc89` (marker 105, the reset), `d7938ca` «Координатор: ТЗ-78 — Y2 принят,
Y1 возвращён; …» and `1ed7632` (marker 104, the lower bound). The executor's
own `5dbad52 Y1 (re-land)` and `9da772f Y2` lie *below* marker 104 — between
markers 103 and 104, i.e. in round 103. So «Y1/Y2 are found in the window of
round 104» was true only through a coordinator verdict: the pin itself was an
artifact of the defect D1 removes. Measured after the fix:

| window | `Y1, Y2` | `W1, W5` | `W3` | `Z9` |
|---|---|---|---|---|
| round 103 | `[]` | `['W1','W5']` | `['W3']` | `['Z9']` |
| round 104 | `['Y1','Y2']` | `['W1','W5']` | `['W3']` | `['Z9']` |

`test_strictness_holds_on_the_real_branch`, `_window_of_round_104` and
`WINDOW_OF_ROUND_104` are re-pinned to round 103 — same table, measured round
number — and round 104's corrected answer is additionally pinned by the new
live-branch test above, so the boundary is asserted from both sides. Nothing
was deleted and no assertion was loosened: 6 assert lines removed, 12 added.

**Not touched, by design.** `agent/CONTEXT.md` is authorized by the spec but no
item's «Done when» asks for a documentation edit, and TASK-98 was the
coordinator's own vehicle for the protocol-level decision, so the file stays
unmodified in this round.

### D2 — a refused `hand` leaves no round change in the index

**How it reproduced before the fix** — the same sandbox that now holds the test:
a bare `origin` in `tmp_path`, the shift branch checked out, a real
`.git/hooks/pre-commit`; no `agent/acceptance.sh` in it, which ТЗ-66 L1 makes
optional-by-presence, so each run costs seconds rather than a full suite. The
fourth row was measured, not assumed: `relay.py` was restored to the pre-fix
head (`grep -c _baton_back_to_head agent/relay.py` → `0`) and the final
five-test file was run against it.

| refusal path | pre-fix state of `agent/BATON.json` |
|---|---|
| hook rejects the commit (round 106's failure) | red — staged: `git diff --cached --name-only -- agent/BATON.json` → `agent/BATON.json`, and the worktree file carried `round: 10, holder: coordinator` |
| foreign path in the index (ТЗ-42 J1 die) | red — worktree modified against `HEAD`: `git diff HEAD --name-only -- agent/BATON.json` → `agent/BATON.json` |
| push rejected, branch advanced (round 108's race) | red — the rollback checked `origin/<branch>` out over `BATON.json`, which stages the *foreign* baton against the new `HEAD` |
| plumbing branch (`--add` names a missing file) | green already — the commit is built in a temp `GIT_INDEX_FILE`, so this path cannot leave the round change; the test locks that |

```
FFF..                                                                    [100%]
E  AssertionError: отказ hand оставил смену круга в индексе: 'agent/BATON.json\n'
E  AssertionError: BATON.json остался изменённым после отказа про чужой индекс: 'agent/BATON.json\n'
E  AssertionError: после отбитого пуша в индексе лежит BATON: 'agent/BATON.json\n'
3 failed, 2 passed in 12.55s
```

**Rule.** New `_baton_back_to_head()` in `agent/relay.py` runs `git checkout
HEAD -- agent/BATON.json` (one step, index *and* worktree) and is called on all
three worktree refusal paths before `die`. The push-rejected path lost its
`checkout origin/<branch> -- BATON`: origin's state is `relay.py status`'s job,
and reading it into the index is precisely what D2 forbids. All three die
messages now say `BATON.json откатан к HEAD`. The invariant is the one the item
states: the round change either left as an `Эстафета:` marker commit or it is
gone.

**Teeth**: `tests/test_task89_d2_relay_index.py` — the four refusals above plus
`test_a_successful_hand_still_moves_the_baton` (the rollback must not lock the
relay: after a green `hand`, origin holds `round 10 / coordinator`, and index
and worktree match `HEAD`). 5 passed after the fix; the 20 tests of the existing
relay suites (`test_j1_hand`, `test_relay_verify_worktree`,
`test_task65_k1_relay_guard`, `test_j3_p6_relay_commit`, `test_k1_p6_relay_skip`,
`test_state_clock`) are unchanged and green.

**Why a new test file.** ТЗ-89's allow-list names three files, none of them a
place for a `tmp_path` harness that drives `relay.py` as a subprocess; the
precedent for an item-shaped test file is `test_task65_k1_relay_guard.py`. No
allow-listed file was modified outside its scope, and `agent/CONTEXT.md` still
needed no change (D1's note applies verbatim).

## Blocked

None.

## What not to trust

* The subject-prefix rule reads the header text. A coordinator commit titled
  without the `Координатор:` prefix — and the branch has such shapes — would
  still be able to credit an item. The census in D1 only proves the two named
  prefixes were the ones that mattered in rounds 104 and 107.
* `WINDOW_OF_ROUND_103` is now a claim about a round that ended long ago; it is
  pinned by `_log_from_top_marker`, which cuts by marker number, so it survives
  rounds piling on top (that is what the A1 test checks) — but if someone ever
  rewrites the branch around markers 103/104, this table has to be re-measured,
  not repaired by editing the expected value.
* Re-pinning was decided by me, the executor, on measurements quoted above. The
  coordinator may prefer a different resolution for those two tests (for
  example keeping 104 and asserting the new answer there); the numbers are in
  this report precisely so that choice can be made from data.
* D2's sandbox rejects the commit with a **stub** `pre-commit` hook, not with
  the real `selfcheck.sh → acceptance.sh` chain that reddened round 106 — the
  sandbox deliberately has no `agent/acceptance.sh` (ТЗ-66 L1 treats it as
  optional by presence), otherwise every one of these five tests would cost a
  full suite. So the tests prove the rollback on "a hook refused", not on "this
  hook refused for this reason"; round 106's actual failure was in the same
  `except SystemExit` branch, which is what the literal reproduces.

## Disputed

* **`test_done_items_have_code_commits_in_round` is red between the hand commit
  and the next round's first commit, and there is no way to make it green in
  between.** At arrival STATE names the previous report, whose items belong to
  the previous window. The only fix available to the executor is to stamp STATE
  and create the new report *inside* its first item commit — which is what
  happened here — so every round begins with a known-red test. Ask: have
  `relay.py hand` stamp `agent/STATE.json` itself (TASK-98 H2 already opens
  `relay.py` for the clock check), so the arriving side starts green.
* **D2 stops at `agent/BATON.json`; the listed `--add` files stay staged after
  a refused hand.** Measured after the fix with a throwaway sandbox probe
  (`rt89-msg/probe_d2_extras.py`, not committed — kept out of the repo so no
  one mistakes it for a test): rejecting `pre-commit` hook, `hand --add
  agent/REPORT-89.md --add agent/STATE.json` →
  `git diff --cached --name-only` lists both files, `git diff HEAD --name-only
  -- agent/BATON.json` is empty, exit code 5. That is deliberate and matches
  the item's letter (only the baton may not survive a refusal; the work must
  not be swallowed by a rollback the user did not ask for), and a retry works
  because the J1 filter excludes this attempt's own `extra`. Ask: should the
  same rollback cover `--add`, i.e. is a half-restored index a worse state than
  a dirty one?

## Runs

| run | what it certified | verdict |
|---|---|---|
| `python3 -m pytest tests/test_report_sections.py -o addopts="" -q` at `69eb0c0` | arrival baseline of the file being edited | 1 failed (bookkeeping, quoted above), 27 passed in 0.36s |
| same, `-k "coordinator_commit or relay_header"`, tests added, fix not yet applied | the two D1 teeth are red on the current code | 2 failed, 28 deselected in 0.03s |
| same, whole file, after the D1 fix | D1 green, re-pinned tables green | 1 failed (the arrival bookkeeping above), 30 passed in 0.36s |
| same file, in this clone with the real `agent/REPORT-89.md` present | the copy is the validated set, and the report-content guards now have something to read | first run 2 failed: the bookkeeping red had become `пункты ['D1']` (STATE names this report), and `test_disputed_lines_live_only_in_disputed_section` caught the baton-note quote — its second wrapped line started with `Disputed`; rewrapped the same quote without changing a character, re-ran: 1 failed, 30 passed in 1.04s |
| same, whole file, with `tests/test_report_sections.py`, this report and `agent/STATE.json` staged | the D1 commit closes the bookkeeping red it inherits (the staged fallback is what the guard accepts on purpose) | 31 passed in 1.16s |
| `_l3_missing` probes on the live branch, round 107 | D0's table reproduced, then Z1 flagged | `A1..A4 → []`, `Y1 → ['Y1']`, `Q9 → ['Q9']`, `Z1 → []` → `['Z1']` |
| `_l3_missing` probes on the live branch, rounds 103 and 104 | the re-pin numbers | table in D1 above |
| `python3 -m pytest tests/test_task89_d2_relay_index.py -v` in `rt89-prep` with `agent/relay.py` restored to the pre-fix head (`grep -c _baton_back_to_head` → `0`) | the three worktree refusal paths really were red before D2, and the plumbing path was not | `FFF..` → 3 failed, 2 passed in 12.55s (assert messages quoted in D2) |
| same file, in this clone, with the fixed `agent/relay.py` | D2 green where it will be committed | 5 passed in 13.06s |
| `python3 -m pytest tests/test_j1_hand.py tests/test_relay_verify_worktree.py tests/test_task65_k1_relay_guard.py tests/test_j3_p6_relay_commit.py tests/test_k1_p6_relay_skip.py tests/test_state_clock.py -q` | the six existing relay suites still agree with the changed `push_baton` | 20 passed in 11.40s |
| `python3 rt89-msg/probe_d2_extras.py …/agent/relay.py` | what a refused hand leaves behind after D2 (`--add` files staged, BATON clean) | exit 5; `git diff --cached --name-only` → `agent/REPORT-89.md`, `agent/STATE.json`; `git diff HEAD -- … BATON.json` → empty |
| `relay.py hand` (close-out) | this report + STATE + BATON to coordinator | hand verdict: recorded by coordinator |

## HANDOFF

Status: PARTIAL (D1 and D2 landed; D3 ahead).
Items done: D1, D2
Items not done: D3 (teeth on the new boundary rules)
Questions for the coordinator: one, in Disputed — whether the arriving red of `test_done_items_have_code_commits_in_round` should be closed by having `cmd_hand` stamp STATE.
