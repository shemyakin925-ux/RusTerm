# REPORT-12 — TASK-12, session 2026-09-09

## Done
- Y1 done: python3 -m pytest tests/test_concept_map.py -q -> exit 0 (8 passed); new test pins PaymentsToAcquireProductiveAssets->capex, Depreciation->d_and_a, PaymentsToAcquireMarketableSecurities->None, appended last, CONCEPT_MAP_VERSION us-gaap.v3; status --json -> us-gaap.v3; 20 payloads re-fetched (20 requests, <=4/sec, UA from ~/.rusterm.env) and re-trimmed by unchanged tools/trim_companyfacts.py; m3_manifest regenerated; golden 125 expected verified against new payloads by (start,end)+accn — zero pointer moves, git diff golden | grep expected -> empty; JNJ FY2021 93775000000 accn 0000200406-22-000022 in place; AMZN/TSLA new tags reach 2025-12-31; du -sk tests/data/edgar/ = 520; pytest -q exit 0; acceptance 13/13

## Blocked

## What not to trust

## Disputed

NOW: Y1, step 8
- Y2 done: python3 -m pytest tests/test_measure_periods.py -q -> exit 0 (9 tests: +stale_input_is_missing_data_not_period_mismatch 2012-vs-2025 -> 'missing_data: operating_income'; +eligible_inputs_on_different_recent_periods_still_mismatch 2024-vs-2025 -> 'period_mismatch'); rule in _issuer_inputs selection (not in as_reported_facts): anchor = newest period_end over base_concepts facts, input ineligible when older than 1100 days; store keeps all facts. M3 rerun: BRKB/JNJ operating_margin+ebitda+interest_coverage reasons now 'missing_data: operating_income' (were period_mismatch); period_mismatch remaining: 0 (was 13); honest roe drop 18->16 (V, UNH: their only StockholdersEquity ends 2009-2011/2009-2014, roe used to pair a 15-year-old balance sheet with FY2025 income — now missing_data; their current equity tag is the incl_nci one, separate concept by W3 ruling -> question to coordinator); counts with Y1+Y2: net_margin 20, effective_tax 20, asset_turnover 20, fcf 19, roe 16, nopat 14, operating_margin 14, ebitda 14, interest_coverage 12, gross_margin 7; strict xfail (15/10) still xfail; pytest -q exit 0

NOW: Y2, step 8
