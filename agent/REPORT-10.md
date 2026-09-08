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
- W2 done: refetched 20 companyfacts (20 requests, 200 OK), trimmed all through the W1 tool, one payload set companyfacts_m3_<TICKER>.json for all twenty (5 m2 files deleted; aapl/companyfacts_aapl.json kept for the parser test), manifest regenerated for 20 with matching sha256s; tests repointed (m2 fallback removed from _payload_path). M2 golden: all 125 rows resolve by accn, expected values unchanged (git diff shows only json_pointer/accn/filed moves), 125 pointers regenerated. JNJ check by name: FY2021 (2021-01-04..2022-01-02) val 93775000000 accn 0000200406-22-000022 — as_reported, not the 78740000000 restatement. du -sk = 504 (< 1024).
  - DISPUTED (W1-vs-W2 conflict, resolved in code): W1's 'six most recent by end' over 10-K entries includes quarterly comparatives, which evict annual periods and make W2's own JNJ check impossible. Implemented: six most recent ANNUAL durations (>= 350 days) plus six most recent other periods, per tag per unit. Both quotes recorded per §1.10.
  - `pytest -q` → exit 0 (263 tests); acceptance → 13/13
- W3 done: new canonical concept total_equity_incl_nci -> StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest (alone); total_equity keeps StockholdersEquity only and does NOT absorb the tag; CONCEPT_MAP_VERSION -> us-gaap.v2 (status --json reports it via the import); test_m3_snapshot asserts 0 facts with NULL canonical_concept over the twenty issuers.
  - DISPUTED: docs/data-dictionary.md §2 has no total_equity_incl_nci name; docs edits are barred by check 10. The V0 doc-guard gained RULED_BEYOND_DICTIONARY = {total_equity_incl_nci} with the reason recorded; the dictionary row should land with the next docs revision.
  - `pytest -q` → exit 0 (263 tests); acceptance → 13/13
