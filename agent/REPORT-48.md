# REPORT-48 — TASK-48 (empty asserts; shared /tmp paths)

Taken after TASK-47 (all four items done, see REPORT-47). Note: the
O0-rework commit `c3d18bd` already carried the two new TASK-48 guard
files (staged early to keep the I5 widening selfcheck's P3/P4 green);
this commit carries the i5 fix, this report and STATE.json.

## Done

- Q1: new guard `tests/test_no_tautology_asserts.py` — ast scan of
  `tests/` for asserts true under any input: `x or True` (truthy
  constant as a disjunct), bare truthy literal (`assert True`),
  self-comparison (`x == x`, `x is x`). Exemptions are an explicit
  list in the guard with exactly one entry:
  `test_smoke.py::test_pytest_runs` (the smoke test honestly asserts
  pytest works). Measurement recorded in the header: on today's tree
  the naive pass finds exactly 1 tautology — that declared exception;
  no `or True` and no self-comparisons exist (Q1b was repaired before
  the guard landed). String-literal `assert True` inside guard
  fixtures (test_d5_p1_rule.py:107, test_j3_p6_relay_commit.py:87)
  is data to ast, never confused — as the task hoped, so the
  exemption list stayed minimal.
- Q1 j5 check: `assert True in parsed or "on" in parsed`
  (test_j5_ci.py:24) stays green — both disjuncts are comparisons;
  an explicit test pins this (`test_assert_in_membership_is_not_a_
  tautology`), plus the whole-tree green test.
- Q1b: already repaired by the coordinator inside the merge
  (`2c6be05`, «ЗАМЕНА БУЛАВКИ (координатор, 17.09.2026)» in the
  docstring of `tests/test_repos.py::test_no_sql_outside_store`) —
  violations collected, red with file:line, print removed. Verified
  by run: planted `conn.execute("SELECT 1")` into
  `rusterm/core/fact.py` → red names `fact.py:407:
  conn.execute("SELECT 1")`; byte-exact restore, green after.
  Acceptance check 7 untouched.
- Q2: new guard `tests/test_no_shared_tmp.py` — reds on writes
  (write_text/write_bytes/mkdir/open-for-write/makedirs/copy/copytree/
  move) into paths built from `tempfile.gettempdir()`, `/tmp`
  literals or TMPDIR, unless the path comes from pytest's
  `tmp_path`/`tmp_path_factory` or a `git rev-parse --git-path` call.
  Declared narrowing: `tempfile.mkdtemp()/mkstemp()/TemporaryDirectory()`
  without `dir=` stay legal (shared root, machine-unique name — not
  the fixed-name collision class; ~35 such sites in tests/).
  Measurement: exactly one red on today's tree —
  `test_i5_guard_source.py:258`, the stale single-flight lock with a
  fixed name in shared /tmp, a relic of round 56 that the machinery
  no longer reads (marker lives in the git directory since 5e050a4).
  Moved to `tmp_path` in the same change; I5 and I5z modules stay
  green. Red case proven by run on a temp file (write via gettempdir
  named by file:line); `tmp_path`/git-path writes proven green.
- Remaining `gettempdir()` uses in tests/, justified: none write to
  shared paths anymore; the two `/tmp` literals left
  (`test_raw_store.py:132`, `test_paths.py:39`) are pure path
  computations with no write shape — the guard does not flag them,
  and they cannot collide (nothing is written).

## Blocked

- Nothing.

## Disputed

- (empty)

## What not to trust

- Q2 guard tracks one-step variable aliases only
  (`p = <expr>`); a path laundered through three variables or a
  container would not be attributed. It is a tripwire for the round-56
  class, not a full data-flow analyser.
- Q1's measurement is over `tests/` only; `rusterm/` asserts are not
  scanned (the defect class lives in tests).
- The flake and venv notes from REPORT-47 carry over (m4 scale ratio
  seen once; broken `.venv` symlink, acceptance uses framework
  python3).

## HANDOFF

Status: PARTIAL (shift in progress, interim block)
Items done: TASK-48 complete — Q1 guard, Q1b verified by planted violation, Q2 guard + i5 lock moved to tmp_path
Items not done: TASK-49 (CA/OTC census) next, then TASK-50 T6 / 51 / 52 as the night allows
Acceptance: this commit's selfcheck prints «Итог: пройдено 13, провалено 0», exit 0
Tests: new guards 3+3 cases green; full suite green in this commit's selfcheck
Guards: tests/test_no_tautology_asserts.py, tests/test_no_shared_tmp.py (both in c3d18bd), tests/test_i5_guard_source.py path fix — no guard weakened
Schema: unchanged (44)
Network: 0 requests of any budget
Model: 0 llm_calls; fake clients only
Secrets: nothing new introduced; no key values in this report
Pushed: yes (pushed with the hand at end of shift; intermediate pushes along the way)
Questions for the coordinator:
1. none yet
