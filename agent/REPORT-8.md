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

- U4 done: rusterm/env.py — load_env (existing env var wins, else  else ~/.rusterm.env; 'export NAME=value' and NAME=value, quotes stripped, blanks/# ignored, foreign names ignored), report() for doctor (names + origins only: 'окружение'/path/'—', world_readable flag), values never printed/logged/audited. main() bootstraps load_env before anything (RequestGate/NetworkGate see it via os.environ). doctor: env section + problem when env file is group/world-readable.
  - Tests: 5 (pickup from file, env wins, missing file not an error, doctor names/origins never values, world-readable reported with exit 1).
  - ~/.rusterm.env verified reachable: doctor via main() now reports the three names (values withheld).
  - `pytest -q` → exit 0 (219 tests); acceptance → 13/13

- U4 done (corrected): rusterm/env.py load_env/report — existing env var wins, else  / ~/.rusterm.env; parse export/NAME=value, quotes, comments; foreign names ignored; values never printed. doctor: env section (names+origins+world_readable problem). main() bootstraps.
  - METHOD VIOLATIONS this item, both self-reported: (1) committed once with the suite red (second time this task; B5 was the first) — the chain habit 'pytest && acceptance && commit' did not abort on failure; fixed by running the suite as its own gate before any commit from now on. (2) Design flaw found by the doctor test: after bootstrap, report() saw file-applied values as 'окружение' — load_env now records origins and doctor reads the record.
  - Leak found and closed: main() bootstrap sets RUSTERM_SEC_UA (user's real contact) into os.environ for every CLI test; my live-fetch placeholder test would then have executed pytest.fail against a valid contact. Placeholder removed — live segment fetch belongs to U5 with recorded payloads; offline integration test covers the doc's bullet (N7).
  - `pytest -q` → exit 0 (219 tests, 2 skips); acceptance → 13/13

- U9 done: bare `rusterm` prints usage (program purpose, data dir, normal path init/watchlist/ingest/snapshot, status) and exits 0. New `rusterm status` (text or --json): data dir, schema version, instruments/watchlists counts, last snapshot per instrument (new SnapshotRepo.latest_per_instrument), coverage status summary (new CoverageRepo.status_summary), budget state, env origins. --json on status/coverage/metrics/budget prints one JSON object. Error discipline: expected errors exit 1 with a Russian sentence naming the next command; unexpected exceptions log traceback to logs/app.log, print that path, exit 2. status applies migrations idempotently (fresh DB reports zeros honestly); counts never conflate written vs known (U3 pattern).
  - Fixes en route: budget payload precedence garbage; snapshot parser lacked --market/--ticker; coverage gained --instrument flag (consistent selector vocabulary).
  - `pytest tests/test_cli.py -q` → exit 0; `pytest -q` → exit 0 (224 tests); acceptance → 13/13

- U10 done: README 'Быстрый старт' added after Содержание — clone→install→init→demo→ingest→snapshot→status→coverage→export (10 commands), where data lives, ~/.rusterm.env for real data, missing-block explanation. Every command executed for real from a fresh clone (/tmp/qstart, console script 'rusterm' on PATH after pip install -e .); real outputs quoted above and in this report: 'применено миграций: 34; schema_version=35', 'US-CLI-DEMO: заданий закрыто: 2; фактов: 6', 'мер: 3 — со значением 3, пусто 0', coverage/status/export lines as run. rusterm/cli/__main__.py added so python -m rusterm.cli works; subprocess test asserts exit 0 + usage for both -m and installed 'rusterm'. pip install -e . succeeded with empty dependencies (setuptools 68 wheel), no new deps.
  - Disputed: README header still says 'код приложения ещё не пишется' — stale, but README outside the Быстрый старт section is out of my assigned scope; flagged for coordinator.
  - `pytest -q` → exit 0 (225 tests); acceptance → 13/13

- U10 follow-up: pip install -e . generated rusterm.egg-info/ in the worktree; acceptance check 13 correctly flagged it. Added to .gitignore (generated artifact, standard practice — not project work).
  - acceptance → 13/13 after .gitignore

- U5 done: rusterm/providers/edgar.py — ticker map (1 request for ALL tickers, cached), submissions/CIK poll_index (records after cursor, advance = max filingDate, repeat = 0 records + 0 requests), list_documents from cached submissions without bodies, fetch_document idempotent sha256 + NotModified on 304, fetch_companyfacts for U6. Transport injected: offline tests run on recorded real payloads (tests/data/edgar/: tickers trimmed to 8, submissions/companyfacts AAPL trimmed; real data per task, 12K total). REGISTRY ENFORCEMENT (the T3 leftover): get_provider('edgar') without gate returns ConfigError value 'network_provider_requires_gate:edgar'; with gate -> provider. Live integration test: 1 real request via RequestGate, skips cleanly when UA absent.
  - Probed live shapes 2026-09-08 (3 requests, in report above): company_tickers {idx:{cik_str,ticker,title}}; submissions filings.recent parallel arrays (form/accessionNumber/filingDate/reportDate/primaryDocument); companyfacts facts.us-gaap.<concept>.units.<unit>[] with start/end/val/accn/fy/fp/form/filed/frame — matched the task's expected shapes, no deviation.
  - DISPUTED: task ideal 'poll_index: one request per source, not per company' — EDGAR has NO global change feed; submissions is per-CIK. Implemented issuer-scoped poll (1 request per issuer feed) + the 1-request market-wide ticker map. The letter is unreachable, the intent (incrementality) is met per-company.
  - Net requests so far: 3 probe + 1 live test = 4.
  - `pytest tests/test_edgar.py -q` → exit 0 (7); `pytest -q` → exit 0 (226); acceptance → 13/13

- U5 correction commit: the U3-era assertion 'ingest --source edgar exits 1, provider unavailable' became false the moment U5 built the provider. New honest contract: provider exists; demo issuer has no CIK -> pipeline records E1 error coverage, 0 jobs, exit 0 (deterministic offline — poll fails before transport with or without UA). METHOD NOTE (third self-report): two commits earlier the suite ran red into a commit because my shell chain used ';' after pytest — chains now use '&&' and the suite runs standalone before any commit.
  - `pytest tests/test_cli.py -q` → exit 0; `pytest -q` → exit 0 (226 tests); acceptance → 13/13

- U6 done: CompanyFactsParser (companyfacts.v1) registered alongside the synthetic parsers. Parses facts.<taxonomy>.<concept>.units.<unit>[]; concept = 'us-gaap:Revenues'; basis = the same I3 rule fed (latest_end_of_accn, end, filed) — no second rule. Dedup by (concept, unit, start, end) across filings: newest filed is live, loser kept in new ParseResult.superseded with superseded_by_locator -> winner pointer (nothing dropped/averaged). Locator = existing LocatorAPI (request_hash = sha of the stored payload, json_pointer ends at the scalar 'val', value_snapshot) — resolve re-reads the same bytes and compares snapshots; resolve_locator pointer walker extended to list indices (backward compatible). i17 extended with a companyfacts doc (checked >= 3 parsers).
  - Fix en route: pointer initially ended at the entry object; the api resolver correctly returned ApiRevision — pointer now ends at /val.
  - `pytest tests/test_edgar_parser.py tests/test_invariants.py -q` → exit 0; `pytest -q` → exit 0 (230 tests); acceptance → 13/13

NOW: U7, step 1
