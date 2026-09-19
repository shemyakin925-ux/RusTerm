# REPORT-47 — TASK-47 (does-not-know I2 + clock discipline)

Shift started 2026-09-17 (round 58, baton from coordinator at 00:04:32Z).
Real clock read, never typed: `TZ=Asia/Bangkok date`.

## Done

- Step 1-2: fetched, fast-forwarded `agent/night-11` to `dac57a9`
  (stale local BATON.json from the finished TASK-46 hand discarded —
  the remote round-58 commit supersedes it), bootstrapped hooks,
  merged `origin/fix/connectivity` as `2c6be05`. Baseline acceptance
  on the merged tree: **«Итог: пройдено 13, провалено 0», exit 0** —
  measured, not claimed.
- O0: new guard `tests/test_state_clock.py` — reds when
  `agent/STATE.json` `updated_at` diverges from the real clock
  (machine form of `date -u`) by more than 15 minutes; names both
  values and the difference in minutes. Comparison is against
  `datetime.now(timezone.utc)`, never the committer date.
- O0 red cases proven by run:
  - on the inherited stale file: `updated_at=2026-09-17T02:25:00Z
    расходится с реальным 2026-09-17T15:45:51Z на +800.9 мин`;
  - planted exactly +3h: `updated_at=2026-09-17T18:46:13Z расходится
    с реальным 2026-09-17T15:46:15Z на -180.0 мин`; byte-exact
    restore after the demo.
- O0 REWORK (same shift, evidence-driven): the wall-clock comparison
  originally lived in `tests/test_state_clock.py` — WRONG placement,
  caught live during TASK-48: the nested selfcheck inside
  `test_i5_staged_and_authorised_widening_is_green` went «пройдено 11,
  провалено 2» because STATE.json had gone stale past 15 minutes by
  the time the nested suite reached the clock test. By construction
  the same red awaits the coordinator's fresh-worktree acceptance run
  hours after the commit. The wall-clock check moved to
  `agent/selfcheck.sh` (the task allowed either place): it runs only
  at commit time, only when STATE.json is staged, and is skipped
  under I5_NESTED=1. Red case re-proven against selfcheck: staged +3h
  → `SELFCHECK FAIL (O0): updated_at=2026-09-17T20:08:51Z расходится
  с реальным 2026-09-17T17:08:52Z на -180.0 мин (допуск 15)`, exit 1;
  fresh staged value → «O0: … на +0.0 мин», green.
  `tests/test_state_clock.py` keeps the parse/must-exist checks and
  now proves the drift MESSAGE on synthetic timestamps — always
  reproducible, never red on a delayed run.
- O0 `updated_at` is obtained by command, not typed. The method, used
  for every refresh this shift:

  ```
  python3 -c "import json; from datetime import datetime,timezone; \
  p='agent/STATE.json'; d=json.load(open(p)); \
  d['updated_at']=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'); \
  open(p,'w').write(json.dumps(d, indent=1) + chr(10))"
  ```

- O1 (I2 does-not-know): the refusal machinery and the three cases
  were already in place from TASK-42 (`tests/test_i2_does_not_know.py`,
  `unknown_reason_from_tools` in `rusterm/core/chat.py`) and passed —
  CONTEXT.md's "open debt" was stale about the machinery, but the
  done-when was NOT proven: cases 2-3 never asserted `answer is None`,
  nothing asserted the fabricated number stays out of the result, and
  no assert tied the refusal reason to the LIVE
  `rusterm/reasons.py` dictionary. Strengthened case by case with a
  shared `_assert_refused` (rejected / answer None / exact reason /
  `is_known_reason` on the token / fabricated number absent from the
  whole returned dict), plus a green control case proving the refusal
  net is caused by the data reason, not by the tool call itself.
- O2: new guard `tests/test_call_arity.py` — static (ast) check that
  every call resolvable to a declaration in `rusterm/` fits its
  signature's positional bounds. Resolution is package-bounded:
  same-file defs, `from rusterm.. import` bindings, `self.method(...)`
  to same-file methods, dotted module receivers through package
  imports. Calls with `*args` unchecked; with `keywords` only the
  excess-positional side; dynamic registry calls (`TOOLS[name](...)`)
  are Subscripts and green by construction. Measurement recorded in
  the header: the naive global-name pass flags 61 of 1590 call sites,
  ALL false positives (Path/set/decimal method names shadow package
  methods); after narrowing 0 findings over 695 resolved calls on the
  current tree. Red case proven by run on a temp copy: the restored
  `_chat_screen(stdscr, repos, make_intent_client(), None)` is named
  with file, line and «ожидалось 3, передано 4». The narrowed guard
  found nothing else on the current tree — the merge's N2 fix is the
  only call of that class, already consistent.
- O3: new guard `tests/test_state_report_tracked.py` — reds when
  `agent/STATE.json` names a `report` absent from `git ls-files` of
  this commit, with a message that says exactly that (the rule plus
  the fix: name the new report in the same commit that switches
  STATE.json to it) instead of the old bare FileNotFoundError from
  test_report_sections.py. Red case proven by run: report pointed at
  `agent/REPORT-99.md` → «agent/STATE.json называет отчёт
  'agent/REPORT-99.md', которого нет в git ls-files этого коммита
  …»; byte-exact restore, green after.

## Blocked

- Nothing yet.

## Disputed

- Found by the new green control case: an answer that names the
  reporting YEAR is bricked by the number guard. Reproduction: measure
  value `0.194`, model answers «net_margin Tanker Corp за 2024 год —
  0.194.» → `guard_rejected_uncited_number`, because
  `get_snapshot_block` returns measures WITHOUT period dates
  (`rusterm/core/tools.py:82-84`), so «2024» is an uncited number by
  construction. The guard's law (ADR-0016) is right; the tool outcome
  is too thin for honest phrasing. Cheapest fix: carry
  period_start/period_end in the measures of `get_snapshot_block`.
  NOT fixed this shift — tool output shape is a product decision
  (TUI/CLI chat and reverify consume it); left to the coordinator.

## What not to trust

- O2's blind spot, by design and measured: calls on object-typed
  receivers (`repos.snapshot.insert_measure(...)`, builders) are NOT
  resolved by the arity guard — a plain ast guard has no type
  inference; they are counted as unresolved, not green-checked. The
  covered classes are same-file functions, package imports and
  `self.*` methods.
- The hook trap (two `test_d5_p1_rule` tests red inside the full suite
  under the hook, TASK-50 T6) has NOT fired for the D5 pair this
  shift. What DID fire, live: an «11, провалено 2» inside the I5
  nested selfcheck — the failing pair was MY clock test against a
  stale STATE.json, not the D5 pair (see the O0 REWORK bullet). The
  capture technique (watcher on selfcheck-acc.* in TMPDIR) works and
  is the tool for the next live red. A real commit exports
  `GIT_INDEX_FILE=.git/index` (relative) to the hook — still the
  suspect for the D5 pair.
- One flake seen once, not reproduced: `test_m4_scale.py::
  test_c2_hundred_issuer_build_shape_stays_linear` failed inside one
  selfcheck run (half-ratio over 1.5 under load), green twice alone
  and green in the next selfcheck. Load-sensitive ratio, not touched.
- The venv is broken on this machine: `.venv/bin/python` symlinks to a
  nonexistent `/usr/bin/python`, so acceptance silently falls back to
  framework `python3` (3.14). Same tree, but the interpreter differs
  from what `.venv` was built for.

## HANDOFF

Status: PARTIAL (shift in progress, interim block)
Items done: baseline merge 13/13; O0 (19bf38c) reworked to selfcheck placement after live evidence; O1 (e26d8ab); O2 (0267926); O3 (2d03609); TASK-48 Q1+Q1b+Q2 in the next commit
Items not done: TASK-49..52 per queue
Acceptance: baseline run on 2c6be05 printed «Итог: пройдено 13, провалено 0», exit 0; per-commit runs via selfcheck, see git notes
Tests: clock/tautology/tmp guards and I5 modules green before this commit; full suite green in this commit's selfcheck
Guards: selfcheck.sh gained the commit-time clock check (O0); test_state_clock.py now synthetic-time only — no accepted check weakens, the wall-clock law moved to the commit gate where it is enforceable
Schema: unchanged (44)
Network: 0 requests of any budget
Model: 0 llm_calls; fake clients only
Secrets: nothing new introduced; no key values in this report
Pushed: no (will push after hand)
Questions for the coordinator:
1. year-in-answer vs number guard: is carrying period dates in get_snapshot_block the wanted fix? (see Disputed)
