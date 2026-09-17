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

## HANDOFF

Status: PARTIAL (T6 diagnostics done; root cause not reproduced)
Items done: T1-T5 verified by run; T6.1 failure diagnostics (file kept, failures named — proven); T6.2 guard-dir leak closed (B37); T6.3 env audit; T6.4 environment proof
Items not done: T6 root cause of the non-deterministic d5 red — next red commit now leaves full evidence by construction
Acceptance: this commit's selfcheck prints «Итог: пройдено 13, провалено 0», exit 0
Tests: full suite green in this commit's selfcheck; guide suite, upgrade suite, census suite, arity, clock, tautology, tmp guards all green this shift
Guards: agent/selfcheck.sh — failure path now preserves and names evidence; guard-dir trap; no accepted check weakened
Schema: unchanged (45)
Network: 0 requests of any budget
Model: 0 llm_calls
Secrets: no key values anywhere
Pushed: yes (with the hand)
Questions for the coordinator:
1. the linked-worktree probe (commit in a fresh worktree with the new selfcheck) — result recorded in the final HANDOFF below; if it is green, the trap evidence must come from your worktree — the next red will now name itself.
