# REPORT-10 — TASK-10, session 2026-09-09

## Done
- §0 setup: merged coordination branch (TASK-10, TASK-11, BACKLOG, LAUNCH) → ce202da, clean.
- §0 baseline: `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0` (coordinator's clean run: 273 passed, 2 skipped).

## Blocked

## What not to trust

## Disputed

NOW: W0, step 1
- W0 done: cmd_add imports get_provider (module level); checks the registry ConfigError value before .resolve() and prints the reason with exit 1; EdgarProvider._ticker_map keeps {ticker: (cik, title)} and resolve returns title — issuer named 'Apple Inc.', not 'AAPL'. Online branch covered hermetically: fake registry provider + saved company_tickers.json transport, no network.
  - Tests: test_w0_add_online_resolves_cik_and_title; test_w0_gateless_provider_exits_1_with_reason_no_traceback (reason in stderr, no traceback in logs/app.log).
  - `pytest -q` → exit 0 (261 tests); acceptance → 13/13
- W1 done: tools/trim_companyfacts.py (outside rusterm/ by design) — deterministic trim: 10-K entries only, (start,end) collapsed to earliest-filed (as_reported), six most recent periods per tag per unit, label/description/foreign tags/unused units dropped, top level cik/entityName/facts.us-gaap; golden tags from json_pointer preserved; sort_keys output byte-stable. tests/test_trim_tool.py: earliest-filed survives restatement, restatement dropped, determinism, top-level shape. tests/test_m2_golden.py switched to accn+(start,end) lookup (json_pointer stays as documentation, regenerated on re-trim).
  - Fix en route: my first test expectation was wrong (Q4 comparative period is a distinct (start,end) per contract) — fixed the test, tool untouched.
  - `pytest -q` → exit 0 (263 tests); acceptance → 13/13
