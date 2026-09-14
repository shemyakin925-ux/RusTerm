# REPORT-31 — TASK-31: vendor cross-check replaced by internal proofs, six measures get values

Arrival state: `bash agent/selfcheck.sh` -> «Итог: пройдено 13, провалено 0», SELFCHECK OK (before any commit).

## Done

### C3 — corporate actions from the real vendor (DONE)

- Free tier serves /splits and /dividends (measured 14.09.2026):
  default answer is ONE latest element; `range=full` returns the whole
  history. AAPL: 5 splits (1987..2020), 83 dividends (1988..2026).
- `TwelveDataProvider`: shared door `_request` (same refusal values as
  time_series), `splits()`, `dividends()`, `cache_url_ca()` — canonical
  key-free URLs, payload cached in raw store (block corporate_actions);
  `parse_splits` (k = from_factor/to_factor — exact integers; the
  vendor's `ratio` is rounded for 7:1: 0.14286), `parse_dividends`.
- Vendor dividend amounts are in TODAY'S share basis (proof from
  payload: 0.000892857143 * 112 = 0.10 — the 1988 dividend; 2.65
  reconstructed for 2013-02-07). `core/prices.declared_dividend`
  converts to the declared amount; that is what enters
  `corporate_action`, so K3's division by the raw close is honest.
- CLI: `_ingest_twelvedata_actions`, wired into
  `ingest --source twelvedata` after the price collector (its own two
  payloads, own cache; a vendor refusal does not sink prices).
- Live run: `rusterm --root ~/.rusterm ingest --instrument US-AAPL
  --source twelvedata` -> `US-AAPL: корп.действия: сплитов 5;
  дивидендов 83; записано новых: 88; запросов: 2; неразобрано: 0`,
  EXIT=0. Spot checks in the DB: declared 0.100000000016 (1988),
  2.650000000004 (2013), 0.27 (2026, no splits after).
- Lineage: both raw payloads stored with provider=twelvedata,
  block=corporate_actions, instrument_id, key-free URL; sha256
  splits 0ea7fdc0…f400f5, dividends 22afc26c…0adb24d. Recorded under
  tests/data/twelvedata/ (817 B and 5,129 B).
- `python3 -m pytest tests/test_c3_actions.py tests/test_market_prices.py
  tests/test_k3_adjusted.py -q` -> `..................` (18 passed,
  0 failed). Order independence (B5) holds on the real rows: the
  reversed-event series equals the original bit for bit.

## Blocked

- (nothing)

## What not to trust

- The declared amounts stored in corporate_action are derived
  (declared_dividend), not the vendor's literal column: float noise at
  the 1e-10 relative level (0.100000000016 for $0.10) — negligible
  against the K3 tolerance, but they are not bit-identical to the
  historical declared dollars.
- The 2 live collection requests and the 7 probe requests were direct
  gate calls in this shift; payload freshness = 14.09.2026.

## Disputed

- DISPUTED: TASK-31 C1 names "the AAPL 4:1 split of 28.08.2020"; the
  vendor payload (and the exchange calendar) date the split ex-date
  2020-08-31 — 28.08.2020 was the last pre-split close. The proof uses
  the vendor ex-date 2020-08-31; both dates are quoted in the report.

## HANDOFF

Status:          PARTIAL — C3 done, C1/C2/C4/C5 ahead
Arrival state:   selfcheck STATUS=OK, «Итог: пройдено 13, провалено 0» before any commit
Items done:      C3
Items not done:  C1, C2, C4, C5 — in progress this shift
Acceptance:      at commit time — see the last selfcheck line in this file
Tests:           C3 scoped run: 18 passed, 0 failed, 0 xfailed (test_c3_actions + test_market_prices + test_k3_adjusted)
Guards:          none touched (no assert changed)
Schema:          unchanged (41)
Network:         9 of 40 Twelve Data requests (1 series + 6 probes + 2 CA collection)
Model:           0 of 0; GLM-5.3-Flash
Secrets:         no key in payload URLs, tests/data or report; grepped artefacts — 0 hits
Pushed:          yes (per commit)
Questions for the coordinator:
1. (none yet)

NOW: C3, step 6
