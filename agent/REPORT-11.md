# REPORT-11 — TASK-11, session 2026-09-09 (X-часть)

## Done
- §0: merged coordination branch earlier; baseline 13/13 at cf1919b→TASK-9 final state.
- X2 done: rusterm/__main__.py (two lines, delegates to rusterm.cli.main); `python3 -m rusterm --help` and `python3 -m rusterm.cli --help` produce identical stdout, exit 0.
- X4 done: export carries concept_map_version — JSON metadata field, CSV first row `concept_map_version,us-gaap.v2` (data rows start at line 2). Existing assertions untouched (strengthened where the header moved).

## Blocked

## What not to trust

## Disputed

NOW: X3, step 1
- X3 done: _issuer_inputs names the absent concepts in the missing_data reason ('missing_data: operating_income, tax_expense'); the fundamentals coverage row carries that reason when measures are null; `coverage --json` adds per-row `missing_concepts` array alongside the reason; reason keeps missing_data as the first token, and the m3 fixed-set assertion matches the token only (as the task directed).
  - Tests: measure_periods X3 test (reason + names + json array via subprocess coverage call); m3 fixed-set assertion now token-based; test_coverage reason updated to the X3 shape (stricter than before: names the concepts).
  - \`pytest -q\` → exit 0 (267 tests); acceptance → 13/13
- X1 done: tests/test_e2e_cli.py drives the four commands as real subprocesses (python -m rusterm.cli) with a hermetic EDGAR: tests/e2e_stub/sitecustomize.py (PYTHONPATH) swaps EdgarProvider's transport to one serving company_tickers.json + companyfacts_m3 payloads. add resolves ticker→CIK+title online-branch; ingest --source edgar resolves ticker (map), fetches companyfacts (1 request/issuer), parses, maps, persists; snapshot yields ≥8 valued measures. Repeat pass: issuer/instrument/fact/raw_object counts unchanged, exit codes 0. cmd_ingest gained the edgar companyfacts branch (per issuer: registry CIK → provider.cik), honest error when the issuer has no CIK; PipelineResult not used on this path (no poll/jobs — companyfacts is one request per issuer).
  - Test count grew: e2e + updated demo-edgar expectation (demo issuer has no CIK → exit 1 'нет CIK', honest).
  - \`pytest -q\` → exit 0 (265 tests); acceptance → 13/13
