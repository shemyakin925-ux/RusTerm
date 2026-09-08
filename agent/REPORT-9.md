# REPORT-9 — TASK-9, session 2026-09-08

## Done
- §0 setup: merged origin/main (TASK-9, BACKLOG, processes.md budget ruling) → 7970011, clean, no conflict.
- §0 baseline: `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0` (coordinator's clean run: 251 passed, 1 skipped).

## Blocked

## What not to trust

## Disputed

NOW: V0, step 1
- V0 done: migration 36 (fact.canonical_concept + concept_map_version, nullable; _SCHEMA_VERSION=36); rusterm/normalize/concepts.py — authoritative table us-gaap.v1 (22 concepts, priority order, canonical names self-mapped for synthetic docs; no SQL/network); pipeline apply_concept_map fills columns at ingest, unmapped counted (PipelineResult.unmapped_concepts, CLI 'неотображённых концептов: N'); as_reported_facts queries canonical_concept and returns unit/periods; _issuer_inputs prefers lower priority_rank on same canonical. insert_fact gained canonical params; test seed helpers updated (raw-SQL helper in test_snapshot_export too); schema pins 35->36 (test_db, test_cli, test_governance); v32 fixtures in test_db/i16 got a minimal fact table (real v32 DBs have one — migration 36 ALTERs it).
  - Tests: tests/test_concept_map.py — 5 (doc guard both ways, unknown tag None + synthetic passthrough, priority ranks + both-tags fixture, AAPL m2 payload ingest yields revenue/net_income/total_assets/total_equity/ocf canonical, no SQL/HTTP in normalize).
  - `pytest -q` → exit 0 (239 tests); acceptance → 13/13
- V1 done: _issuer_inputs chooses the latest period_end where ALL inputs of a measure exist with the same unit (duration inputs also need the same period_start); no common period -> new null-reason period_mismatch; absent concept -> missing_data (reasons never merged); tag priority picks the winner among same-canonical rows; lineage fact_ids provably one period (test asserts lineage periods == FY2023 set). as_reported_facts returns unit/period_start/period_end (no second query, no SQL outside store).
  - Tests: tests/test_measure_periods.py — 4 (common-period FY2023 computation with lineage periods, period_mismatch, missing_data, unit-mismatch).
  - `pytest -q` → exit 0 (243 tests); acceptance → 13/13
- V2 done: measure carries its inputs' period (chosen_period from V1; no-input measures carry as_of and a null-reason — empty period_start never written) and unit from the formula's table (formulas.py MEASURE_UNIT_KINDS + measure_unit: ratio/money/per_share/count; money keeps the inputs' unit, per-share = <unit>/share, counts = 'шт.').
  - Tests: test_v2_measure_carries_input_period_and_ratio_unit; test_v2_unit_table_covers_kinds_and_never_empty_period (money/per_share/count via the table — a money _BASE_MEASURE itself lands with V4).
  - `pytest -q` → exit 0 (245 tests); acceptance → 13/13
- V3 done: new `rusterm add --ticker T --market M [--cik N] [--name] [--instrument-id] [--class]` — issuer(cik-N, one per CIK)+instrument+listing+ticker-history, idempotent ('уже существует', exit 0), online resolves --cik/--name via the EDGAR ticker map (1 cached request), offline requires both and exits 1 naming the missing flag. watchlist add gains --ticker/--market through resolve_ticker_candidates (ambiguity exits 1, no second resolver). Unresolved-ticker message now names 'rusterm add --ticker T --market M'. _ensure_demo_instrument wrote listing+ticker history (demo --ticker works). README quick-start: real-company path added, commands run for real.
  - Tests: 6 new (add+ingest resolves exactly one, idempotent add 1/1, watchlist add by ticker, offline requires --cik/--name, unresolved message names add, two share classes one issuer).
  - Tests hermetic: SEC contact neutralized for add tests (env + env-file via RUSTERM_ENV_FILE).
  - `pytest -q` → exit 0 (251 tests); acceptance → 13/13
- V4 done: _BASE_MEASURES replaced by _MEASURE_FORMULAS (7 single-period: net_margin/operating_margin/effective_tax/gross_margin/ebitda/fcf/interest_coverage) + _TWO_PERIOD_MEASURES (roe, asset_turnover: chosen end + immediately preceding stock period, else missing_prior_period) + _CHAIN_MEASURES (nopat = oi * (1 - effective_tax), rate from the computed measure, lineage links peer measure) + _UNMAPPED_FORMULAS registry (18 §3 names outside the V0 map: invested_capital/roic/net_debt/net_debt_ebitda/fcf_yield/market_cap*/ev/pe/pb/ps/ev_ebitda/div_yield/cagr/total_return/drawdown/price_adj/hhi — visible rows with concept_not_mapped, never omitted). formulas.py gained fcf and interest_coverage branches (verbatim §3) and a complete unit table. Snapshot line keeps U3's value/empty split.
  - Tests: tests/test_v4_formulas.py — 3 over the committed AAPL payload: net_margin non-null with duration period; balance measure (roe/asset_turnover) non-null; every §3 name present with value or fixed-set reason; nopat chain honest either way.
  - Fixes en route: build treated missing inputs as {} and called calculate_measure (erasing period_mismatch); two-period stock selection matched duration keys for instants (start=end) — now selected by period end.
  - `pytest -q` → exit 0 (257 tests); acceptance → 13/13
- V5 PARTIAL — network half STOPPED by the task's own rule; offline half done and strengthened.
  - Re-fetched all 20 companyfacts (20 requests). Re-trim hit the STOP: SEC restated JNJ historical figures between fetches — RFC FY2021 val 93775000000 -> 78740000000 (Kenvue continuing-ops restatement), RFC FY2022 94943000000 -> 79990000000 (newest filed). Per task: expected value changed = red flag, not a fix. Stopped; committed payloads/golden left untouched and consistent (M2 golden 125/125 still resolving).
  - Changed values for the coordinator: JNJ RFC FY2021 93775->78740, RFC FY2022 94943->79990 (continuing ops), SEI unchanged. Decision needed: adopt continuing-ops restatements as new golden values (new accn) or pin golden to first-as-reported via the recorded payloads.
  - Offline half: test_m3_snapshot.py strengthened — apply_concept_map at ingest; >=15 of 20 issuers must have a non-null net_margin with a real period; every remaining null carries a reason from the fixed set. Result: 19/20 issuers non-null net_margin on the COMMITTED payloads (mapping V0 + periods V1 work on real data). 140 blocks missing with reasons (was 160).
  - `pytest tests/test_m2_golden.py tests/test_v4_formulas.py tests/test_m3_snapshot.py -q` → exit 0; `pytest -q` → exit 0 (257 tests); acceptance → 13/13
  - **M3v2: 20 issuers, 20 requests (refetch, not adopted), 19 of 20 issuers with non-null net_margin on committed payloads, nulls by fixed reasons**
- V6 done: tui source_panel adds source_tag (fact.concept) + concept_map_version per input fact; coverage --json and status --json carry concept_map_version (CONCEPT_MAP_VERSION); doctor reports unmapped fact count + top-5 unmapped tags by name and count (SQL in store, names/counts only).
  - Tests: source panel fields asserted (test_tui_model); doctor lists nothing on empty base without crashing (test_concept_map).
  - `pytest -q` → exit 0 (259 tests); acceptance → 13/13
