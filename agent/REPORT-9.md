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
