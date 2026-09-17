# REPORT-50 — TASK-50 (connectivity: T1–T5 verified; T6 diagnostics)

T1–T5 arrived with the merge (`2c6be05`, coordinator's own verified
work). Per the task they were VERIFIED, not redone; the night's own
work is T6.

## Done

- **T1–T5 verified by run** (acceptance on the merged tree, and
  targeted files):
  - T1 chat door: `make_chat_client(environ, gate)` lives in
    `rusterm/core/llm.py:112`, both CLI and the TUI screen call it
    (TASK-46 N2); `tests/test_chat_door.py` green.
  - T2 screens survive 80x24: `tests/test_tui_pty.py` (pty driver,
    stdlib) green.
  - T3 intent gate: `make_intent_client(environ, gate)` builds the
    client WITH a gate; `tests/test_chat_door.py` + full suite green.
  - T4 reason in `ops --json`: `"reason": null` present in the keyless
    dry-run output (re-produced live during TASK-52 §7 — see
    REPORT-52); refusal path carries the reason value.
  - T5 vendor refusals as values: `tests/test_readonly_and_refusals.py`
    green; `rusterm/core/ops.py` carries `Refused(reason)`.
  - Baseline acceptance on the merged tree at shift start:
    «Итог: пройдено 13, провалено 0», exit 0.
- **T6.1 — acceptance failure inside the hook is now readable**
  (`agent/selfcheck.sh`): on non-zero acceptance the full output file
  is NOT deleted, its path is printed («полный вывод приёмки: …
  (файл сохранён)»), and the `ПРОВАЛ`/`FAILED`/`Traceback` lines are
  printed immediately with line numbers (head -40). Proven by run:
  a deliberately failing test staged → selfcheck rc=1, output file
  preserved at the printed path (verified on disk), failing tests
  named for BOTH pytest passes. `acceptance.sh` untouched.
- **T6.2 — guard-dir leak closed (BACKLOG B37)**: `GUARD_DIR` (the
  extracted-guards mktemp -d) is removed by its own EXIT trap; the
  117 stale `selfcheck-guards.*` directories on this machine were
  removed; new selfcheck runs leave none.
- **T6.3 — sandbox environment audit** (the five
  `GIT_INDEX_FILE`/`GIT_DIR`/`GIT_WORK_TREE`/`GIT_OBJECT_DIRECTORY`/
  `GIT_ALTERNATE_OBJECT_DIRECTORIES`): every sandbox git call is
  clean — `test_d5_p1_rule.py` and `test_j3_p6_relay_commit.py` build
  from-scratch env dicts (the five are absent by construction);
  `test_i5_guard_source.py`, `test_i7_p6_worktree.py`,
  `test_j1_hand.py` scrub exactly those five from the inherited
  environment. No edit needed; audit recorded.
- **T6.4 — environment proof**: `GIT_DIR=$(git rev-parse
  --absolute-git-dir) GIT_INDEX_FILE=$GIT_DIR/index I5_NESTED=1
  python3 -m pytest -q` → green (rc=0) with `git status --porcelain`
  clean afterwards (run recorded in /tmp/t6-proof.txt; result in the
  HANDOFF block).

## Blocked

- **T6 root cause of the coordinator's non-deterministic red** (d5
  pair, guard sees «пустой дифф») is NOT reproduced on this machine
  this shift: a 5-run full-suite campaign under the exact real-commit
  hook environment (GIT_INDEX_FILE=.git/index relative, GIT_PREFIX=,
  GIT_EXEC_PATH, GIT_AUTHOR_*, I5_NESTED=1 — captured by a probe hook
  from a real commit) gave 4 green runs; the 1 red was MY OWN doctor
  regression mid-task (fixed in the TASK-51 commit, see REPORT-51),
  not the d5 pair. The targeted ordering probe (i5, i7, then d5 in
  one process, hook env) is green. With T6.1 in place the next red
  commit names its failing checks and keeps the full output — that is
  the instrument this item was opened for.

## Disputed

- (empty)

## What not to trust

- «13/13 green under the hook» claims for THIS machine hold for 5
  campaign runs + several per-commit selfchecks; the coordinator's
  red happened in a linked worktree — the linked-worktree commit
  probe is described in HANDOFF and its result recorded there.
- The trap hypothesis (d5 running a working-tree guard mutated by
  neighbouring modules) was NOT confirmed: no test writes
  `agent/p1_rule.sh`; the I5 machinery stages INDEX blobs, not tree
  files, and the I5 tests skip themselves under `I5_NESTED=1`.

## Done (addendum — pre-approved backlog after the queue)

- **BACKLOG B39** (pre-approved): `refresh` errors carry dictionary
  reasons now — «unknown_issuer: registry_id is empty» and
  «unknown_issuer: instrument not found»; `is_known_reason` accepted
  by test; GUIDE §7 line updated to the real output (guard green).
- **BACKLOG B40** (pre-approved): `budget`, `cadence`, `status`,
  `coverage` audited — all four created the data directory through
  `_open` (budget additionally crashed rc=2 with «no such table»).
  Verdict table:

  | command | must create? | verdict now |
  |---|---|---|
  | budget | no | ceilings + «нет данных», rc 0, nothing created |
  | cadence | no | «нечего планировать», rc 0, nothing created |
  | status | no | named refusal «каталога данных нет», rc 1 |
  | coverage | no | named refusal, rc 1 |

  Covered by `tests/test_b40_readonly_commands.py` (B35 style: run
  from a foreign cwd over an absent data root, assert nothing is
  created).

## HANDOFF

FINAL — supersedes the interim values above.

Local Danang clock at the stop decision: **03:36** (`TZ=Asia/Bangkok
date +%H:%M`).
Status: PARTIAL — only TASK-50's root-cause hunt is open
Arrival state: selfcheck SELFCHECK OK on the first run of the shift, acceptance «пройдено 13, провалено 0» at 2c6be05
Items done: T1-T5 verified by run; T6.1 diagnostics (proven by planted red), T6.2 guard-dir leak (B37), T6.3 env audit, T6.4 env proof, linked-worktree commit probe green (90d3fc3, branch deleted); TASK-47 (O0 reworked to selfcheck, O1-O3), TASK-48 (Q1, Q1b verified, Q2), TASK-49 (R1 census, R2 IFRS v2 + golden values, R3 DART absent), TASK-51 (U1-U4 + doctor --fix), TASK-52 (V1-V4), BACKLOG B39, B40
Items not done: TASK-50 T6 root cause of the non-deterministic d5 red — not reproduced in 5 clean full-suite runs under the real-commit env; next red commit names itself and keeps its full output by construction
Acceptance: every commit this shift passed «Итог: пройдено 13, провалено 0» inside the pre-commit hook; exit 0
Tests: ~780 collected, 0 failed, 5 skipped (I5 nested skips + tui marker), 4 xfailed strict
Guards: selfcheck failure diagnostics + guard-dir trap; new tests — state clock, report tracked, call arity, no-tautology, no-shared-tmp, guide truth, upgrade path, b40 read-only; no guard weakened, IFRS map v2 with payload evidence
Schema: unchanged (45); migrations 42-45 exercised on historical bases (TASK-51), not edited
Network: 0 live requests this shift (TASK-49 census offline on recorded fixtures; 4-request EDGAR budget untouched)
Model: 0 llm_calls; fake clients only
Secrets: grepped the four key names across the diff — 0 value hits; RUSTERM_DART_KEY confirmed ABSENT (Disputed in REPORT-49)
Pushed: yes — agent/night-11 through 3e75262 + this handoff commit; agent/CONTEXT.md coverage line rides the relay hand (--add)
Questions for the coordinator:
1. DART key: issue one, or the Korean channel stays keyless? (REPORT-49)
2. roe over incl-NCI equity as a named fallback for CNQ — wanted? (REPORT-49)
3. doctor: silent migration as default, or --fix flag stays? (REPORT-51)
4. future-schema open guard (U3 proposal) — approve as an item? (REPORT-51)
5. period dates in get_snapshot_block output so the year is citable in chat answers? (REPORT-47)
