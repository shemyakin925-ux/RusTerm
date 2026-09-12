# REPORT-23 — TASK-23: M9 quotes and valuation (offline path)

## Done

- §0: branch `agent/night-5` cut from `agent/night-4` head (0e4841e);
  selfcheck STATUS=0; `_SCHEMA_VERSION` read from the file: 40.
- **`RUSTERM_TWELVEDATA_KEY` UNSET** (printenv exit 1, absent from the
  environment and from ~/.rusterm.env) → the offline item set of §0:
  K1, K3, K5, K6, K8, plus the offline half of K4 (pure wiring, prices
  inserted by test fixtures — no vendor payload is simulated).

### K1 — prices and corporate actions get a place in the schema (DONE)

- Migration 41 (`_CUSTOM_MIGRATIONS[41]`): table `price`
  (instrument_id, date, source, close, adjusted, currency, volume,
  retrieved_at; PK on the triple; CHECK: close or adjusted present) and
  table `corporate_action` (instrument_id, ex_date, kind
  split|dividend, factor, amount, currency, source; PK on
  (instrument, ex_date, kind); CHECK ties split to factor and dividend
  to amount). `_SCHEMA_VERSION` 40 -> 41, read from the file before.
- `PriceRepo` (put_rows OR IGNORE = re-collecting a day is a no-op,
  I7; series; price_as_of with age_days; latest_date; count) and
  `CorporateActionRepo` (put, all, raw_events — the dividend FACTOR is
  deliberately NOT computed in the repo: it needs the close on the
  ex-date, which belongs to the K3 caller holding the price series).
- Both applied twice create no duplicates (asserted); a populated
  database re-applies cleanly; `tests/test_db.py tests/test_repos.py`
  green.
- **P1 accounting — schema-history pins strengthened** (the guard
  flags any removed assert line mechanically; each replacement below is
  a strengthening: the migration history grew by one entry). Removed
  line -> replacement:
  1. `assert _SCHEMA_VERSION == 40` -> `== 41` (docstring extended
     with 40 and 41);
  2. `'''assert row[0] == 40'''` -> `'''assert row[0] == 41'''`
     (test_apply_migrations_creates_all_tables);
  3. `assert count1 == count2 == 37` -> `== 39` (+ price,
     corporate_action);
  4. `assert newly == [33, 35, 36, 37, 38, 39, 40]` ->
     `[33, 35, 36, 37, 38, 39, 40, 41]`;
  5. `assert newly == [40]` -> `[40, 41]` (v39 migration test);
  6. `tests/test_cli.py`: `"schema_version=40"` -> `41` (init output),
     `report["schema_version"] == 40` -> `41` (doctor),
     `payload["schema_version"] == 40` -> `41` (status), and the four
     drift tests delete the new top version and expect the message to
     name 41;
  7. `tests/test_governance.py`: `assert _SCHEMA_VERSION == 40` -> 41;
  8. `tests/test_j4_backup.py`: `summary.schema_version == 40` -> 41.

## Blocked

- TWELVEDATA_KEY UNSET: K2 (the provider and its recorded payload) and
  K7 (vendor-degradation test) wait for the key; K4's vendor-facing
  half (real collected price rows) waits too.

## What not to trust

- Nothing collected from the vendor this night; every price row in
  tests is a fixture inserted directly.

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL
Items done:      §0
Items not done:  K1..K8 pending
Acceptance:      STATUS=0 at branch cut
Tests:           not counted yet this shift
Schema:          40 (unchanged so far)
Pushed:          with this commit
Questions for the coordinator:
1. (none yet)

NOW: K1, step 1
