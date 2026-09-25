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

## Disputed

* **`test_done_items_have_code_commits_in_round` is red between the hand commit
  and the next round's first commit, and there is no way to make it green in
  between.** At arrival STATE names the previous report, whose items belong to
  the previous window. The only fix available to the executor is to stamp STATE
  and create the new report *inside* its first item commit — which is what
  happened here — so every round begins with a known-red test. Ask: have
  `relay.py hand` stamp `agent/STATE.json` itself (TASK-98 H2 already opens
  `relay.py` for the clock check), so the arriving side starts green.

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
| `relay.py hand` (close-out) | this report + STATE + BATON to coordinator | hand verdict: recorded by coordinator |

## HANDOFF

Status: PARTIAL (D1 landed; D2, D3 ahead).
Items done: D1
Items not done: D2 (hand must not leave the round change in the index), D3 (teeth on the new boundary rules)
Questions for the coordinator: one, in Disputed — whether the arriving red of `test_done_items_have_code_commits_in_round` should be closed by having `cmd_hand` stamp STATE.
