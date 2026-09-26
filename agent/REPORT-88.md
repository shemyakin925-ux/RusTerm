# REPORT-88 — TASK-88: coordinator-side acceptance without other people's junk

Round 123, branch `agent/night-11`, executor. Spec: `agent/TASK-88.md`
(items C1–C3; C0 is the coordinator's verdict on TASK-80, C4 is a
constraint, not work). Report language: English (agent-to-agent); code
comments and commit messages are Russian per the project rule.

## Arrival state (measured before the first source edit)

* Base: the coordinator's hand commit («Эстафета: круг N, ход у executor», N
  recorded below), working
  tree clean (`git status --porcelain` → no output).
* Suite as it stands: see Runs — the baseline number is quoted there.
* C1 census — `rusterm-relay-verify*` under `tempfile.gettempdir()`
  (`/var/folders/hb/_dcdc6j13k17mgfw9lh7814r0000gn/T`): **0**, measured twice —
  23:39Z during pre-validation and 04:00Z at the start of this turn. The
  machine-global path the old default pointed at (`/tmp/rusterm-relay-verify`)
  is absent too, so nothing was inherited; after this item each `verify` run
  creates its own tree (see Disputed). The machine-global default path
  that `cmd_verify` used (`/tmp/rusterm-relay-verify`, still named in
  `.claude/skills/run-agent-relay/SKILL.md:62` as `--worktree
  /tmp/rusterm-relay-verify`) is also **absent** on this machine.
  Honest caveat: my own pre-validation probes created 3 trees under a
  private `TMPDIR` and I removed them, so the count inherited from
  earlier rounds is 0, not "0 ever".

## Pre-validation (done while the coordinator held round 122, no writes to the clone)

All three items were built and measured in a scratch worktree
(`/tmp/rt88-guards`) plus two draft files, then re-applied here item by
item. Numbers below are from that pre-check, the suite run again in the
clone, and acceptance.

## Done

### C1 — `verify` does not inherit junk

* Default worktree path became unique per run:
  `$TMPDIR/rusterm-relay-verify-<short-sha>-<UTC-stamp>-<pid>-<seq>`.
* Explicit `--worktree` path with untracked files → refusal, not silent
  cleaning: the file list is printed and the removal command is named
  (`git -C <path> clean -fd`). A non-git, non-empty directory at that
  path is refused the same way with `rm -rf <path>` — `verify` touches
  neither.
* `tests/test_relay_verify_worktree.py` (new, 3 tests, `tmp_path`):
  dirty tree → refusal naming `leftover.py` + `clean -fd`, the stub
  acceptance never runs, and the file is still on disk afterwards
  (C4: no deletion of other people's files); clean tree → the run
  proceeds; two consecutive default-path runs → two different
  directories.
* Commit `af23188` «ТЗ-88 C1: verify берёт уникальное дерево на прогон
и не чистит чужое», hook run `Итог: пройдено 13, провалено 0` / `Принято.`

### C2 — teeth that do not depend on a live `Z9`

Two tests that called `_git_log_name_only()` and stayed green only
because no commit named `Z9` exists on the branch. Replaced with a
literal log (`Z9_LOG`, `%x1e`-separated, three blocks) and an explicit
round number (`round_no=121`); `Z9` sits *below* the round marker with
code attached, so it is missing because of the boundary, not because of
history.

Fragility measured, not asserted — the HEAD version of the file, copied
to a non-git directory (`/tmp/rt88-notgit/tests/`):

```
E   subprocess.CalledProcessError: Command '['git', 'log', '--format=%x1e%h %s', '--name-only']' returned non-zero exit status 128.
FAILED tests/test_report_sections.py::test_l3_flags_an_item_that_no_commit_carries
FAILED tests/test_report_sections.py::test_l2_staged_fallback_only_opens_for_a_non_test_file
2 failed, 26 deselected in 0.30s
```

The same command on the new file in the same non-git directory:
`2 passed, 26 deselected in 0.17s`. History is no longer an input.

Strength measured by mutation, each mutation reverted immediately
(`_l3_missing` only; line numbers are the new file's):

| mutation | `…l3_flags_an_item…` | `…l2_staged_fallback…` |
|---|---|---|
| M1 boundary not enforced (`break` → `continue`) | rc=1, `:422 AssertionError` | rc=1, `:428 AssertionError` |
| M2 fallback opens for any staged file (`if missing:`) | rc=1, `:422 AssertionError` | rc=1, `:428 AssertionError` |
| M3 fallback never opens (`if missing and False:`) | rc=0 (correct: no fallback in that call) | rc=1, `:430 AssertionError` |

Baseline (unmutated) both green in the repo and outside it. Assert count:
3 removed, 3 added — no `assert` lost, so P1 has nothing to declare.

Commit `e689574` «ТЗ-88 C2: зубы L3/L2 на литеральном логе, граница круга
названа явно», hook run `Итог: пройдено 13, провалено 0` / `Принято.`
The `ЗАМЕНА-БУЛАВКИ:` block was pre-written into `COMMIT_EDITMSG` before
`git commit -F`, as the pin rule reads the pending message; `bash
agent/p1_rule.sh` said `P1: OK (staged)` with 3 removed / 3 added assert lines.

### C3 — no night shift left in the tests

The docstring of `tests/test_state_clock.py` justified the guard with
«Стоп смены — 10:00 по Данангу (PROTOCOL §10), поэтому ложные «+4 часа»
заканчивают ночь на треть раньше». That reasoning is void since the user
cancelled the night shift on 23.09. Replaced with what is actually true:
the coordinator reads `updated_at` to decide whether the executor is
alive or stuck, so a wrong clock misreports liveness — no expiry event,
just a wrong statement about the world. Text only: no function, no
threshold, no comparison touched.

`git grep -nE '10:00|Дананг|Danang' -- tests/ rusterm/` in the clone
after the change, in the clone itself: `tests/test_market_br.py:66` and nothing else — measured in the pre-validation worktree it
returns exactly one line, a time label inside fixture data:

```
tests/test_market_br.py:66:            200, b"ZIPBODY", {"Last-Modified": "Mon, 07 Sep 2026 10:00:00 GMT",
```

(`__pycache__/*.pyc` also matches by content; it is ignored by
`git grep`, which is why it does not appear.) `agent/acceptance.sh`
untouched, as C4 requires.

Commit `a2a84e6` «ТЗ-88 C3: страж часов больше не обоснован несуществующей
ночной сменой», hook run `Итог: пройдено 13, провалено 0` / `Принято.`
Diff is docstring only: 0 removed assert lines.

## Blocked

None.

## What not to trust

* C1's uniqueness is per *process*, not per *machine*: two `verify` runs
  in the same second, same head, same pid namespace … the `seq` counter
  only separates runs inside one process. Two separate processes started
  in the same second collide only if they also share a pid, which does
  not happen on this machine — but the guard is the stamp, not the
  counter.
* The refusal looks at `git ls-files --others --exclude-standard`. Files
  ignored by `.gitignore` are invisible to it and still sit in the tree.
  That is deliberate (they are the project's own junk, and `test_i5`
  only trips on untracked-and-not-ignored), but it means "clean tree" in
  this message ≠ "empty directory".
* The `relay.py` change is exercised only by the three new tests, which stub
  `agent/acceptance.sh` with an `echo`. The real `verify` path — a per-run
  tree, refusal on a dirty explicit tree, on a live branch — has not been run
  end-to-end by me, because running it means a ~12-minute acceptance in a
  tree I just created, and TASK-88's budget is 0 network requests. What was
  measured: the default path is unique (two runs, two directories), a leaked
  file in an explicit path produces a refusal naming it, and the leaked file
  survives the refusal untouched.
* `test_report_sections.py`'s new literals were validated against
  `_l3_missing` in a scratch worktree and then committed unchanged; the line
  numbers in the mutation table (:422, :428, :430) belong to the file as
  committed in `e689574`.
* C2 replaced the *inputs* of two tests, not the guard. `_l3_missing`
  itself is unchanged in this report — if it is broken, these two teeth
  can still be green while `test_done_items_have_code_commits_in_round`
  is wrong; the mutations below are the evidence that they bite on the
  boundary and on the fallback, nothing more.

## Disputed

* **The old shared verify path is still documented as the recommendation.**
  `.claude/skills/run-agent-relay/SKILL.md:62` tells whoever reads it to run
  `python3 agent/relay.py --branch agent/night-10 verify --worktree
  /tmp/rusterm-relay-verify` — the exact machine-global path C1 stops using by
  default. C1's authorisation covers `agent/relay.py` and two test files only,
  so the skill text was left alone; one line there should name the default
  instead. The coordinator's call.

* **The O0 clock guard cannot fire on any commit path.** `agent/selfcheck.sh:84`
  gates the real-UTC comparison behind `if [ -z "${I5_NESTED:-}" ] && …`,
  and `agent/githooks/pre-commit` always exports `I5_NESTED=1`. Measured:
  round 121 shipped a 44-minute-old `updated_at` in `63db7b8` and
  acceptance was 13/0. TASK-88 C3 asks me to re-justify the guard in
  `tests/test_state_clock.py` without weakening it — I did exactly that
  (text only), but the coordinator should know the stronger claim in the
  old docstring ("настоящие часы сравниваются в agent/selfcheck.sh в
  момент коммита") is true only for a manual `selfcheck.sh` run, not for
  a commit.
* **Unique default paths mean one tree per run, forever.** `cmd_verify`
  already runs `git worktree prune`, which forgets pruned trees but does
  not delete directories I no longer point at. Nothing in TASK-88
  authorises deleting a verify tree, so I did not delete any. Measured
  cost per tree on this machine: ~8.5 MB of tracked content
  (`git ls-files | du -ch` on a scratch worktree) and 16 MB once the
  caches from one acceptance run are in it (`du -sh` of the same
  worktree: `.pytest_cache` 20 K, `.hypothesis` 316 K, 194 `__pycache__`
  entries). So each round's `verify` will now leave ~16 MB behind;
  cleaning them is a decision for the coordinator (and belongs to C4's
  "не удалять чужие файлы" as much as to disk hygiene).

* **A tracked guard file carries demonstration residue, and this round is
  forbidden to clean it.** `agent/p6_rule.sh` ends with a line
  `# i5 green case: staged widening` that the I5 demonstration appends when
  `agent/selfcheck.sh` runs standalone; `git log -S` traces the shipped copy
  to `5171e68` «ТЗ-53 W1: масштаб меряется операциями, а не секундами». Every
  standalone selfcheck since then appends a *second* copy, which is what the
  coordinator's run in this clone did at 03:50Z (`git status --porcelain` →
  `M  agent/p6_rule.sh`) before my first edit. I restored HEAD bytes rather
  than committing them, because TASK-88 C4 forbids touching that file — but
  the ask is for the coordinator: either strip the shipped residue in the
  guard's own commit, or have the demonstration write to a temp copy. Left as
  it is, the guard file is a ratchet that only grows.

* **The close-out verdict has nowhere honest to be written.** A round's last
  act is `relay.py hand`, and that commit carries the report — so the report
  would have to quote the verdict of the very run that publishes it. Either
  the row is a placeholder (this one was, until a minute before the hand) or
  it claims a check that had not happened yet. Ask: have `cmd_hand` print a
  paste-ready line for the *next* round's first commit to land into the
  previous report, or let the coordinator record it in the review. The
  executor cannot fix it inside its own turn without writing to the branch
  after having handed it over.

## Runs

| run | what it certified | verdict |
|---|---|---|
| hook of `af23188` (C1) | relay.py + `tests/test_relay_verify_worktree.py` + report + STATE | Итог: пройдено 13, провалено 0 → Принято. |
| hook of `e689574` (C2) | literal-log teeth, 3 removed / 3 added asserts, declared | Итог: пройдено 13, провалено 0 → Принято. |
| hook of `a2a84e6` (C3) | docstring-only clock guard re-justification | Итог: пройдено 13, провалено 0 → Принято. |
| `relay.py hand` (close-out) | this report + STATE + BATON to coordinator | printed by that commit's own hook, and no earlier — the last Disputed entry names why this row cannot quote it |

Separate measurements, each on a quiet machine (no second pytest pass
overlapping): `python3 -m pytest tests/test_relay_verify_worktree.py
tests/test_no_shared_tmp.py tests/test_no_tautology_asserts.py` → 9 passed
in 2.32 s (the new file plus both tree-scanning guards);
`python3 -m pytest tests/test_state_clock.py` → 3 passed in 1.36 s.
Arrival collection: `1375/1395 tests collected (20 deselected)`.

**One correction to "quiet machine", made before the hand.** Preparing this
submission I found an orphaned test subprocess on the machine — pid 2274,
parent `launchd`, `python -m rusterm.cli --root <pytest tmp dir> tui`,
8 h 13 m elapsed, 99 % CPU, `cwd` in `/private/tmp/rt88-baseline`: a leftover
of my own scratch rehearsal, whose clone directory had already been swept. I
terminated it. Wall-clock numbers in this report that overlap another
acceptance run are therefore inflated by contention and not by the code
under review; the two short measurements above were re-read against that
possibility and not changed.

`git grep -nE '10:00|Дананг|Danang' -- tests/ rusterm/` in the clone after
C3, verbatim:

```
tests/test_market_br.py:66:            200, b"ZIPBODY", {"Last-Modified": "Mon, 07 Sep 2026 10:00:00 GMT",
```

That single hit is a `Last-Modified` header value inside fixture data — the
kind of time label C3 allows. Nothing in `rusterm/` names the shift, the
hour or the city; `agent/acceptance.sh` still calls itself «приёмкой ночной
работы» in its first line and was not touched (C4, and acceptance check 12
compares it with `main`).

**Rehearsal first, in a scratch clone** (`/tmp/rt88-sim`, cloned from the
shift clone, `origin/main` mirrored so acceptance's own comparison works,
`core.hooksPath=agent/githooks`, never pushed, network untouched — TASK-88
budget is 0 requests). Same files, same messages, same order as the real
turn. A simulated hand commit (hooks off, it is the coordinator's action)
put the baton at holder=executor so the round window matched.

| commit | started | hooks ran | verdict |
|---|---|---|---|
| C1 (relay.py + new test file + report + STATE) | 01:24Z | yes | Итог: пройдено 13, провалено 0 → 7162887 |
| C2 (test_report_sections.py, ЗАМЕНА-БУЛАВКИ in COMMIT_EDITMSG) | 01:35Z | yes | Итог: пройдено 13, провалено 0 → 684644f |
| C3 (test_state_clock.py docstring) | 01:48Z | yes | Итог: пройдено 13, провалено 0 → 0040ed4 |
| close-out (report + STATE + BATON → coordinator) | 02:00Z | yes | Итог: пройдено 13, провалено 0 → b3fcf36 |

~11–13 min per commit. Two defects were found by this rehearsal and fixed
before the real turn, both bookkeeping rather than code:

* with `agent/REPORT-88.md` present but **untracked**, selfcheck reds at
  P3/P4 in ~40 s (`SELFCHECK FAIL (P3/P4): untracked files present`), so
  the report ships staged inside the C1 commit;
* with `agent/STATE.json` pointing `report` at that draft while the draft
  still carried template values, `test_handoff_carries_real_values_not_
  placeholders` reddened **two** acceptance checks (11/2). From the first
  stamped commit the HANDOFF block therefore carries real values
  (`Status: PARTIAL (C1 landed; C2, C3 ahead)`), and no `<` anywhere in it.

## HANDOFF

Status: DONE. All three items are committed, one commit per item. The hand
commit carries this report and the closing STATE stamp.
Items done: C1, C2, C3
Items not done: none
