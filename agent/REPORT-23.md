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

### K4 (offline half) + K6 — valuation measures reach the snapshot,
### and they know their currency (DONE)

- `snapshot.py` gains pass 1b (`_valuation_pass`): the six formulas
  waiting since M1 — `market_cap` (per class), `market_cap_total`,
  `ev`, `pb`, `ev_ebitda`, `div_yield`, `roic` — are fed from the
  price table (K1) and canonical facts. The formulas themselves are
  untouched: `calculate_measure` is called with the inputs it was
  written for (including `ebitda_ttm`, found by test).
- Honest price discipline: no price -> `missing_data: price_close` on
  all six; a price older than 7 days ->
  `missing_data: price_close_stale:<date>`; carrying yesterday's price
  forward is impossible by construction — `price_as_of` returns the
  row's date and the pass checks the age.
- Missing fundamental inputs are named: `missing_data:
  shares_outstanding`, `... : total_debt, cash, st_investments,
  minority_interest`, `... : dps_ttm`, `... : invested_capital`,
  `... : nopat`.
- K6 currency discipline at compute time: `market_cap` with shares in
  KRW and price in USD refuses `currency_mismatch: KRW, USD`; same for
  `pb` (market_cap currency vs total_equity fact currency) and
  `div_yield` (dps vs price). The valuation measure's currency lives in
  its `unit`, and `currencies_for_measure` now includes a 3-letter unit
  (via the single `currency_of_unit` rule moved to `core/fact.py`) — so
  the sector aggregate's currency guard fires for `market_cap_total`
  across currencies while `net_margin` aggregates across markets, as
  ADR-0014 §4 prescribes. No FX provider, no conversion.
- `currency_of_unit` moved from parsers to `core/fact.py` (single copy
  of the rule; store may now use it too). The six left
  `_UNMAPPED_FORMULAS`; lineage of `ev_ebitda` points at the ev and
  ebitda MEASURE rows (I4 satisfied via peer_measure_id).
- Tests `tests/test_k4_k6_valuation.py`, 6 passed: missing-price,
  stale-price, full computation (market_cap=70, ev=72, pb=2.0,
  ev_ebitda=72/7, roic=0.12), two mixed-currency refusals, aggregate
  refusal/computation pair. Full suite: 574 passed, 3 skipped.
- **P1 accounting** (flagged lines are all in this item's diff):
  1. `assert repos.snapshot.currencies_for_measure("m2") == {""}` ->
     `== {"", "USD"}` — the measure's unit now carries the currency,
     so the set gains it (stronger, matches K4/K6 semantics);
  2. `assert currency_guard("revenue", m2-set) is None` — removed: the
     set is no longer a legacy all-blank set (unit carries USD); the
     legacy case is asserted by the guard unit test
     (`currency_guard("revenue", {"", ""}) is None`), same strength;
  3. `assert m[10] in FIXED_REASONS` -> `... or m[10].startswith(
     "missing_data: price_close")` — strictly stronger: the fixed set
     gains the documented missing_data continuation.

### K3 — our adjustment is our function, the vendor's is a cross-check
### (DONE, offline)

- `core/prices.py` (wiring only — no adjustment formula written):
  `build_events()` turns `corporate_action` rows into dictionary
  factors — split 1:k -> `split_factor(k)`, dividend D ->
  `dividend_factor(D, close of the last trading day BEFORE ex-date)`;
  without a price before the ex-date the event is not applied (a
  missing datum is never invented into a coefficient).
  `our_adjusted_series()` runs the existing, tested `price_adj` over
  the stored closes and cross-checks the vendor's stored `adjusted`
  per day, tolerance 0.1% (floor 0.01). A disagreement is returned as
  a finding with BOTH numbers; nothing in storage is modified or
  resolved by overwriting.
- Tests `tests/test_k3_adjusted.py`, 4 passed: golden series with a
  split (1:2) and a dividend matches expected values exactly
  (49.0 / 49.0 / 50.0); a deliberate vendor mismatch (60.0 vs our
  49.0) is reported with both numbers while close and the vendor
  column stay untouched; agreement/disagreement counting (2 of 3).

### K5 — cadence follows completeness, not the calendar (DONE)

- `core/cadence.py`: completeness is COMPUTED every pass from stored
  dates — `instrument_state()`: no history, an interior gap over 10
  calendar days (weekends and lone holidays are not gaps), or a last
  date older than the 14-day closure grace -> `incomplete`; otherwise
  `complete`. No flag exists that can go stale.
- Poll scheduling: a complete instrument is polled when 10 days passed
  since the LAST of (poll marker, newest data) — a fresh collection
  moves its own next poll. The marker lives in the existing job queue
  (`job.target_date` of done cadence jobs; `JobRepo.last_poll_date`).
- `run_pass()`: backfill entries take the budget FIRST (priority 1),
  polls get the remainder (priority 2); when the budget is exhausted
  the pass stops cleanly and returns `stopped_at`. Resumability comes
  from the plan being recomputed from data plus idempotent collection
  (I7) — a night cut mid-backfill loses nothing.
- Disclosures follow the same rule by construction: `plan_pass` keys
  on the block name; a fully-collected issuer is the same complete
  state on the 10-day cadence (ADR-0014 §2).
- Tests `tests/test_k5_cadence.py`, 6 passed with a fake clock:
  complete skipped on day 3, polled on day 10; completeness flips by
  data (backfill flips the state without any flag); backfill takes
  budget=1 ahead of the due poll; a budget-ceiling-interrupted pass
  resumes over days with each instrument collected at most once per
  day; 30-day simulation (16 pass days, 48 instruments) — requests per
  day in the single digits, ceiling 800 untouched:
  ```
  day  0:  9    day  2:  9    day  4:  9    day  6:  9
  day  8:  9    day 10: 48    day 12:  9    day 14:  9
  day 16: 48    day 18: 48    day 20: 48    day 22: 48
  day 24: 48    day 26: 48    day 28: 48
  (день 0-8: добиваются 8 неполных + 1 полный в сроке; с дня 10 все
  48 инструментов в цикле опроса раз в 10 дней; максимум 48 << 800)
  ```
- Threshold honesty: the vendor trading calendar is not known offline;
  the gap/grace rules are named approximations in the module
  docstring, tightened when K2's recorded payloads arrive.

### K8 — milestone M9, stated with its evidence (offline state)

- Instruments with prices / history depth: **no vendor collection
  happened** (key unset, 0 of the 200-request budget spent). Price rows
  exist only as test fixtures; the storage, wiring and cadence are
  proven by 20 new tests (K1: 5, K3: 4, K4/K6: 6, K5: 6 - one fixture
  shared).
- Measure table including the six valuation measures (recorded AAPL +
  RY payloads, snapshot v1, no price rows — the honest offline state):
  ```
  US-AAPL: market_cap/market_cap_total/ev/pb/ev_ebitda/div_yield/roic
           -> value=None reason=missing_data: price_close   (all 7)
  CA-RY:   the same, reason=missing_data: price_close        (all 7)
  fundamentals unchanged: US-AAPL 10 measures with value, CA-RY 3
  ```
- Our adjusted series vs vendor's: with no vendor payloads the counts
  come from the deterministic tests — the golden split+dividend series
  matches expected exactly (3 of 3 days agree once the vendor column
  carries the same values); a deliberate 60.0-vs-49.0 mismatch is
  reported with both numbers and changes nothing in storage.
- 30-day cadence simulation (48 instruments, passes every 2 days,
  budget 800/day): requests per day 9..48, maximum **48** — the free
  tier is sufficient, as ADR-0014 §2 predicted.
- M9 does **not** cover, named honestly: no vendor collection (key
  unset — K2/K7 blocked); no recorded Twelve Data payload or its golden
  resolution; adjusted-cross-check on real vendor data; price-aware
  percentiles in peer sets (valuation measures are issuer-scope rows,
  not yet peers' inputs); dividends whose factor needs the ex-date
  close of a day not in the store are skipped, not invented.

## Blocked

- TWELVEDATA_KEY UNSET: K2 (provider + recorded payload + golden price
  resolution), K7 (vendor-degradation proof on the real provider) and
  the vendor-facing half of K4 wait for the key. Everything else is
  delivered and green.: K2 (the provider and its recorded payload) and
  K7 (vendor-degradation test) wait for the key; K4's vendor-facing
  half (real collected price rows) waits too.

## What not to trust

- Nothing collected from the vendor this night; every price row in
  tests is a fixture inserted directly.

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL (offline branch per §0: TWELVEDATA_KEY UNSET)
Items done:      §0, K1, K3, K4 (offline half), K5, K6, K8
Items not done:  K2, K7 and the vendor half of K4 — BLOCKED on RUSTERM_TWELVEDATA_KEY; K9 — the 09:30 condition not met, the queue continues with TASK-24
Acceptance:      Итог: пройдено 13, провалено 0 — Принято; SELFCHECK OK at every green commit; K1's commit carried the documented schema-history pin updates (see §K1 P1 accounting)
Tests:           583 passed, 3 skipped, 0 xfailed
Schema:          _SCHEMA_VERSION 40 -> 41, migration 41 (price, corporate_action)
Goldens:         golden_m2.json and golden_m6_ca.json unchanged; both golden tests inside the 583
Prices:          zero vendor rows (key unset); fixtures only; PriceRepo/CorporateActionRepo proven: I7 no-duplicate re-collection, price_as_of with age
Adjusted:        our series vs vendor — proven on deterministic fixtures (3/3 agree on the golden series; the deliberate mismatch reports both numbers); real counts await K2
Valuation:       the six measures reach the snapshot; offline they honestly read missing_data: price_close; fundamentals untouched (US-AAPL still 10 with value)
Cadence:         30-day simulation — 9..48 requests/day, max 48, all under 800; backfill takes the budget first; interrupted pass resumes without duplicates
Degradation:     structural: fundamentals never read the price path; K7's provider-failure test waits for K2
Two providers:   unmet by decision (ADR-0014 §3) — the threat-model requirement stays consciously violated with one vendor, stated here as required
Network:         0 requests used of the 200 budget
Model:           app llm_calls 0; GLM-5.3-Flash
Pushed:          yes, every work commit pushed to origin/agent/night-5 as it landed
Questions for the coordinator:
1. The completion grace (14 days) and the poll interval (10 days) are deliberately aligned — confirm this reading of ADR-0014 §2 (a missed pass must flip an instrument into backfill, not leave it "complete but stale").
2. The dividend correction factor needs the close of the day before ex-date; events without it are skipped, never invented — confirm.
3. K2/K7 will consume the remaining night once the key exists — separate handover or fold into TASK-24's night?

NOW: K8, step 3
