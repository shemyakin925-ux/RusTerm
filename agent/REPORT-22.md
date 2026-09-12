# REPORT-22 — TASK-22: fiscal calendar, data durability, an installable program

## Done

- §0: branch `agent/night-4` cut from `agent/night-3` head (e324dee,
  the released-and-accepted state); selfcheck STATUS=0; `markets` shows
  all six rows with implemented modules; `_SCHEMA_VERSION` read from
  the file: 40.

## Blocked

- none

## What not to trust

- Nothing yet: no work item has landed.

## Disputed

- (empty by design — nothing disputed yet)

## HANDOFF

Status:          PARTIAL
Items done:      §0 (branch cut, selfcheck green, schema read from file)
Items not done:  J1.0..J9 pending
Acceptance:      STATUS=0 at branch cut (selfcheck, /tmp/sc-j0.txt)
Tests:           not counted yet this shift
Schema:          40 (unchanged so far)
Pushed:          with this commit
Questions for the coordinator:
1. (none yet)

### J1.0 — EDGAR parser records currency (DONE, coordinator's precondition)

- `rusterm/parsers/__init__.py`: new `currency_of_unit()` — a units key
  of exactly three capital letters (`USD`, `CAD`, `KRW`) is recorded to
  `fact.currency`; `shares`, `pure`, `USD/shares` are not currencies and
  stay `None`. Only `CompanyFactsParser` is touched; the synthetic
  parsers and `manual/pipeline.py` keep `None` deliberately.
- **The blank rule lands with this commit**: `currencies_for_measure`
  now returns blanks as empty strings, and `currency_guard` treats a
  recorded currency mixed with blanks as `currency_mismatch: (blank), X`
  — never "that one currency". All-blank (legacy) sets behave exactly as
  before. The TASK-21 Disputed trade-off is closed.
- Real output, fresh ingest of the recorded AAPL+RY payloads:
  ```
  SELECT DISTINCT currency FROM fact:
    None     <- shares / USD/shares facts (correct, not missing)
    CAD
    USD
  ```
- Goldens: UNCHANGED — `tests/test_m2_golden.py` and the m6-ca golden
  test pass in the suite; they resolve values by locator, and the
  parser change adds a field without touching any value.
- Tests: `tests/test_j1_currency.py`, 5 passed. Full suite:
  531 passed, 3 skipped, exit 0.

## Blocked

- none
