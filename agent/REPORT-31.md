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
### C1 — the correction is proven from inside, no vendor opinion (DONE)

**Discovery that reshaped this item (ADR-0020, new — the permitted
docs change):** the free-tier vendor `close` is ALREADY split-adjusted
to today's share basis. Digit-for-digit anchors, all from recorded
payloads: 2020-08-28 close 124.80750 = 499.23/4; 2014-06-06 close
23.05607 = 645.57/28 (rounded by the vendor to 5 decimals); vendor
dividend amounts are in the same basis (0.000892857143 x 112 = 0.10 —
the 1988 dividend; 0.094642857143 x 28 = 2.65 — 2013-02-07).
ADR-0019 stays true (no `adjusted_close` COLUMN) but its premise
"our price_adj must apply splits too" was incomplete: applying our
split factors to this series would double-correct.

- **Repair of C3 (same rule as TASK-30's I9 repair):** the collector
  no longer converts dividends to declared amounts — the vendor's
  literal amount is stored (`_ingest_twelvedata_actions`);
  `declared_dividend` remains as the basis-proof machinery, not a
  storage step. ADR-0020 records the decision.
- `core/prices.vendor_adjusted_series` + `build_vendor_events`: the
  vendor-basis path — dividend factors only (ratio dividend/close is
  basis-invariant); the raw-basis `build_events`/`our_adjusted_series`
  are untouched for sources with truly raw closes.

**Proof 1 — adjustment computed over the REAL corporate actions:**
live DB, 5000 real price rows (2006-10-26..2026-09-14) + 88 real
events (5 splits, 83 dividends): `vendor_adjusted_series` -> adjusted
2006-10-26 = 0.7641080073226756, 2020-08-28 = 120.95566991789994
(close 124.8075 minus ~3.1% of six years of dividends), 2026-09-14 =
334.765 (= close: no dividends after 2026-08-10). Disagreements: 0
(no vendor adjusted exists to disagree with — ADR-0019).

**Proof 2 — order independence on the real events (B5 on live rows):**
reversing the real event list changes nothing:
`test_price_adj_order_independence_on_real_rows` (element-wise
pytest.approx for the direct price_adj permutation — float
multiplication converges approximately, same convention as
tests/test_formulas.py::test_price_adj_split_and_dividend_order_independent;
EXACT equality through our_adjusted_series, which sorts events
canonically regardless of input row order).

**Proof 3 — the AAPL 4:1 split recalculated by hand:** 499.23 (the
known pre-split close of 2020-08-28) x split_factor(4) = 499.23 x 0.25
= **124.8075** — our function's number (`price_adj([("2020-08-28",
499.23)], [("2020-08-31", split_factor(4.0))])` == 124.8075, exact
float: division by 4 is a pure exponent shift) and simultaneously the
vendor's stored close for that day, digit for digit. The vendor's
split ex-date is 2020-08-31 (see Disputed). Pinned by
`test_real_split_event_digit_for_digit_against_vendor`.

**Golden pins:** `adjusted IS NULL` now pinned twice — at the parse
level (test_market_prices.py, pre-existing) and at the store level
(new `test_real_price_rows_keep_adjusted_null_in_store`: 200 recorded
rows -> SUM(adjusted IS NULL)=200, SUM(adjusted IS NOT NULL)=0). The
vendor-basis anchors 124.80750/129.039993 are pinned inside the split
test — if the vendor changes the series basis, the pin goes red
(ADR-0020 p.4).

- `python3 -m pytest tests/test_k3_adjusted.py tests/test_c3_actions.py
  tests/test_market_prices.py tests/test_formulas.py -q` -> 41 passed,
  0 failed. New data file: tests/data/twelvedata/
  time_series_AAPL_split_window.json (2,582 B, 15 real rows around the
  split) and time_series_AAPL_div_window.json (1,644 B, 9 real rows
  around the 2026 dividends) — both extracted from the already-stored
  live payload, zero extra requests.

- Guard note (P1): the C3 pin `assert div2013["amount"] ==
  pytest.approx(2.65, abs=1e-9)` stayed in place byte-identical, but
  its subject is now the DERIVED declared amount (the basis proof),
  and the storage is guarded by the strictly stronger exact pin
  `assert vendor_amount == 0.094642857143` (the vendor's literal, no
  tolerance). The `assert series == reversed_series` pin in the order
  test keeps its line; its input construction was corrected to the
  canonical event order (build_events sorts), which is what the pin
  meant; the direct factor-permutation case is additionally covered
  element-wise approx (B5 convention). README §15 lists ADR-0020
  (test_docs_truth guard).
