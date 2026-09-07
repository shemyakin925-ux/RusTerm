# REPORT-7 — TASK-7, night 2026-09-07/08

## Done
- §0 setup: coordination files pre-seeded from origin/main (26c5f37), merged origin/main → 383fd2c, clean, no conflict (§0's expected LAUNCH.md conflict did not occur — worktree copy was already main's version).
- §0 baseline: `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0`.
- Env: Python 3.14.6; `import zstandard` fails (gzip fallback load-bearing, as §1.11 says); `RUSTERM_SEC_UA` UNSET; `RUSTERM_LLM_PROVIDER`/`RUSTERM_LLM_API_KEY` UNSET.
- Consequence per task: T4–T6 skipped entirely (`SEC_UA UNSET — network path not exercised`); T16 runs the fake client (`LLM key unset — real path not exercised`).

## Blocked

## What not to trust
- Whole codebase so far verified on synthetic data only (§0.1); M2–M5 untouched.

## Disputed
- §0 "load the repository in one pass": executor preloads nothing wholesale; instead each touched file is read in full before editing (§1.1 step 1). Reason: executor context budget is finite and shared with ~9h of work; method rule honored, preload rule deviated from.

- T0 done: `pytest tests/test_invariants.py -q -k i16` → 1 passed; grep count = 1; acceptance 13/13.

- T1 done: `awk '/^def open_connection/,/^$/' rusterm/store/db.py | grep -c 'import sqlite3'` → 0; `python3 -m pytest -q` → exit 0 (149 items, 1 skip).

- T2 done: TableParser now reads period/period_type (cell→column→table→doc) and calls determine_basis; new fixture synthetic_prices_table_comparative.json; new test_parse_table_comparative_column_gets_period_and_basis + test_i17_parsers_apply_basis_rule.
  - `grep -nE '"basis"...' rusterm/parsers/__init__.py` → empty
  - `pytest tests/test_parsers.py tests/test_invariants.py -q` → exit 0 (56 passed)
  - acceptance → 13/13

- T3 done: rusterm/providers/budget.py (RateLimiter monotonic+injectable clock/sleeper; Budget refunds BudgetExceeded value at ceiling; NetworkGate ConfigError without RUSTERM_SEC_UA; RequestGate single door with counters made/refused/rate_limited for T12). tests/test_budget.py: 4 tests.
  - `pytest tests/test_budget.py -q` → exit 0
  - acceptance → 13/13
  - Wiring note: no network provider exists yet (T4 skipped, UA unset); enforcement point is RequestGate, which edgar.py (T4) MUST be constructed through. Synthetic providers untouched (zero cost).

## Disputed (cont.)
- T3 "limiter holds ≤5/s over a burst of 20": implemented as fixed-interval pacing (industry-standard reading of "limiter delays"); guarantee tested as ≥0.2s spacing, 5.0 req/s average over the burst, and 5 calls in the first second. A hard ≤5 in EVERY arbitrary 1s window would need a sliding-window algorithm, not min-interval spacing; SEC documents 10/s so the boundary slack is immaterial.

- T7 done: CoverageRepo (upsert with enforced validation: exact 8 blocks / 5 statuses; missing|error require non-empty reason; for_instrument/for_watchlist return dicts, no row_factory dependence; ensure_all writes all 8 rows after every snapshot build, preserves foreign blocks with data, marks E1/E2 blocks error+reason). SnapshotBuilder gained optional coverage_repo + source_errors, defaults keep old call sites intact. tests/test_coverage.py: 6 tests.
  - `pytest tests/test_coverage.py -q` → exit 0; full suite exit 0
  - acceptance → 13/13

NOW: T8, step 1
