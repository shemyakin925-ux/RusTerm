# REPORT-8 — TASK-8, day session 2026-09-08

## Done
- §0 setup: merged origin/main (TASK-8, LAUNCH, BACKLOG, governance doc ruling) -> 0d99c8f, clean, no conflict.
- §0 baseline: `bash agent/acceptance.sh` → `Итог: пройдено 13, провалено 0` (matches coordinator's clean-checkout run: 208 tests, 206 passed, 2 skipped).
- Env: Python 3.14.6; zstandard absent; `~/.rusterm.env` EXISTS (mode 600, defines 3 RUSTERM_* names — values not read into this report).

## Blocked

## What not to trust

## Disputed
- §1.9 stop time (no new item after 09:30 Danang): this is a USER-INITIATED day session (the coordinator delivered TASK-8 at 09:39 and the user pointed me at it), not the scheduled 00:00–10:00 night run; interpreted §1.9 as bounding scheduled night shifts. Working the queue now; same discipline (cycle, selfcheck, commit+push per item).

- U0 done: llm.py guard rebuilt on multiset containment of numeric tokens (Counter(found) - Counter(allowed) must be empty). _render now returns (text, substituted list of exact inserted strings); periods are no longer an allowed source (doc periods in model text are rejected unless substituted as a placeholder value); _normalize_number strips thousands separators (space/NBSP/comma-between-triads), treats ','=='.'; string compare, no tolerance. dispatcher of run() rewritten so any rejected block rejects the whole text.
  - Coordinator's three probe texts (31%/12 млрд/рост в 2 раза) each rejected in full with single measure revenue=1000; token repeated beyond substitution count rejected; same token twice via two placeholders stored; '1,000' measure string normalizes and stores.
  - `pytest tests/test_llm_guard.py -q` → exit 0 (7 passed); `pytest -q` → exit 0; acceptance → 13/13

- U1 done: SnapshotBuilder.__init__ coverage_repo is now a required positional arg (no default); coverage ensure_all runs unconditionally on every build. Call sites updated: cli (already had it), tests/test_snapshot_export.py x4 (CoverageRepo(conn) added), tests/test_verification.py (recompute path now writes coverage — the porous site the item named). New test: omitting coverage_repo raises TypeError.
  - `grep -rn 'SnapshotBuilder(' rusterm/ tests/` → all call sites carry a coverage repo.
  - `pytest -q` → exit 0 (209 tests); acceptance → 13/13

- U2 done: cmd_verify now calls VerificationService.recompute after store_ground_truth (SnapshotBuilder with coverage repo), prints 'пересчитано: <snapshot_id> v<version>' per rebuilt instrument (or 'нет мер с lineage на этот факт'), audit-log carries rebuilt list. Test test_cli_verify_triggers_recompute_of_derived_measure: init->seed->snapshot->verify via CLI; new snapshot version, net_margin 100/1000 -> 100/2000, version printed.
  - `pytest tests/test_cli.py -q -k recompute` → exit 0; `pytest -q` → exit 0; acceptance → 13/13

- U3 done: US-CLI-DEMO killed as implicit default. New: _select_instruments (--instrument | --ticker+--market | --watchlist; exactly one; unresolved/ambiguous ticker exits 1 via resolve_ticker_candidates listing candidates, never silent first pick); ingest/snapshot loop over selected instruments with per-instrument lines; export --instrument required; cmd_demo creates the synthetic issuer+instrument explicitly ('данные синтетические, выдуманные'); init no longer creates demo data. Demo data: new synthetic fixtures synthetic_demo_index.json + synthetic_demo_report.json (concepts revenue/net_income/operating_income/tax_expense/pretax_income -> all three base measures compute non-null); snapshot line separates 'со значением N, пусто M'. grep 'US-CLI-DEMO' rusterm/ -> only the demo constant.
  - Tests: 5 new (demo flow non-null + split counters, no-selector exit 1 x2 commands, unresolved ticker, two instruments two snapshots two exports, watchlist selector); existing CLI tests updated to demo+selectors, strength kept.
  - Fix en route: snapshot --as-of default None violated NOT NULL -> default today via args_as_of_default().
  - `pytest -q` → exit 0 (214 tests); acceptance → 13/13

NOW: U4, step 1
