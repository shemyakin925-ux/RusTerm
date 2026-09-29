# REPORT-104 — TASK-104 (P1–P7) + TASK-105 (R1–R6), round 141

Status: IN PROGRESS

## Done

### P1 — `pe`, `ps`, `fcf_yield` refuse across currencies (TASK-104)

Before: `_valuation_pass` compared currencies only where a side was a
*fact row it already labelled* (`pb`, `ev`, `div_yield`, `roic`,
`market_cap`). `pe`, `ps`, `fcf_yield` divided blindly — USD market cap
over MXN/CAD/GBP earnings produced a ratio with no currency and no
refusal.

Now (all in `rusterm/core/snapshot.py`):

* `sides_clash(*currencies)` next to `mismatch()` — same K6 format, and
  the B3 legacy rule kept: a side with no recorded currency does not
  start a dispute.
* `pe`/`ps`: window path compares `price_currency` with the currency of
  that TTM window; the annual backup path compares it with the currency
  of the annual fact itself (`_latest_annual_input` index 2).
* `fcf_yield`: numerator side is the unit already written on the `fcf`
  measure (`IssuerInputs.units`), denominator side is the price.
* Window currencies had to reach the pass: `IssuerInputs.window_units`
  (new field, filled from the `window_units` dict that `_issuer_inputs`
  already computes to drop mixed-currency windows) and `IssuerInputs.units`
  are now passed to `_valuation_pass`.
* Order of refusals follows B3/B2: no numerator → `missing_data`;
  currency dispute → `currency_mismatch` before the sign of the
  denominator (with two currencies the quotient does not exist at any
  sign); otherwise the old denominator refusal / the quotient.

Tests: `tests/test_task104_p1_price_side_vs_filing_currency.py` — 6
teeth, offline, USD price + GBP filings:

| tooth | red before | now |
|---|---|---|
| all three refuse | `pe=7.0`, `ps=0.7`, `fcf_yield=0.17142857142857143` (probe on a HEAD worktree) | `currency_mismatch: GBP, USD` ×3 |
| ratio label survives | — | `unit="ratio"` on the refused rows |
| one currency on both sides | green (control) | `7.0 / 0.7 / 0.1714` |
| currency-less denominator | green (control) | values, no refusal |
| missing market cap outweighs the dispute | green (control) | `missing_data: market_cap_total` / `market_cap` |
| annual backup path refuses too | `ps=0.7` | `ps` and `pe` → `currency_mismatch: GBP, USD` |

Two pins in `tests/test_task97_q4_ifrs_ingest.py` moved, and both move
because TASK-97 Q4 left the hole there on purpose («тест держит строку,
чтобы починивший её увидел изменение»):

* `test_pe_and_ps_on_kspi_straddle_currencies` →
  `test_pe_and_ps_on_kspi_refuse_the_off_rate_quotient` — the successor
  keeps the shape assertion (facts exactly `{KZT}`, price exactly `{USD}`)
  and adds, for both measures, `value is None` plus the exact
  `currency_mismatch: KZT, USD`. Declared in the commit message with
  `ЗАМЕНА-БУЛАВКИ` + `ПОЧЕМУ СИЛЬНЕЕ`.
* `KSPI_VALUED` — 10 measures → 8 (`pe`, `ps` left the set). The pin line
  `assert valued == KSPI_VALUED` is untouched; the expected set shrank by
  exactly the two measures the item rules on, so the count check still
  names every empty cell's reason.

Copy measurement (P7; the user's base untouched — `/tmp` copies only,
network 0). Both copies rebuilt with an explicit `--as-of 2026-09-29`:
`/tmp/rt-104-before` by a detached worktree of `ab2bb63`, `/tmp/rt-104-after`
by this working tree — all 44 instruments, one CLI run per instrument
(44 + 44 builds, 0 failures, ~14 s each pass). The diff compares the latest
snapshot per instrument, so clock drift cannot enter it:

| instrument | pe | ps | fcf_yield |
|---|---|---|---|
| US-AMX | `58.100937362525805` → `currency_mismatch: MXN, USD` | `31.027121205055263` unchanged — no revenue window assembles, the annual fallback is the FY2024 **USD** filing, both sides USD | `0.004681244312464769` unchanged — `fcf` is USD (FY2024 annual ocf/capex) over a USD cap |
| US-TECK | `missing_data: market_cap_total` unchanged | `missing_data: market_cap_total` unchanged | `missing_data: market_cap` unchanged |
| US-KSPI | `missing_data: price_close_stale:2026-09-18` unchanged | unchanged | unchanged |
| US-BHP | `missing_data: net_income_ttm` unchanged | `missing_data: revenue_ttm` unchanged | `missing_data: fcf` unchanged |
| US-VOD | `missing_data: net_income_ttm` unchanged | `missing_data: market_cap_total` unchanged | `missing_data: market_cap` unchanged |

1320 measure rows were compared across the 44 instruments and **exactly one
moved: `US-AMX pe`**. TECK/VOD have no numerator at all (no
`shares_outstanding` → no market cap), BHP has no flow inputs, and KSPI on
today's date is refused earlier by the price-staleness door (last close
2026-09-18 is past `_PRICE_STALE_DAYS = 7`) and its only facts in the copy
are 4 unmapped `us-gaap:OtherAssets`/`OtherLiabilities` rows in KZT — so the
only copy instrument whose currency seam actually reaches these three
divisions is AMX, and KSPI is covered by the offline teeth instead.

Rows the user's own older snapshot carries (v6/v7) differ from a fresh
same-day rebuild for reasons that are not this commit — stale prices and the
M1 shares door — listed here so nobody reads them as part of P1.

## Blocked

## What not to trust

## Disputed

## Runs

| what | command | result |
|---|---|---|
| P1 teeth red before | same file on a detached worktree of `ab2bb63` | 2 red: `pe=7.0`, `ps=0.7`, `fcf_yield=0.17142857142857143` |
| P1 teeth after | `pytest tests/test_task104_p1_price_side_vs_filing_currency.py` | 6 passed in 0.57 s |
| KSPI pins + i5 guard + P1 | `pytest tests/test_task97_q4_ifrs_ingest.py tests/test_i5_guard_source.py tests/test_task104_p1_….py` | **22 passed in 1317.40 s** (2026-09-29T03:38Z) |
| guard file after that run | `git diff HEAD -- agent/p6_rule.sh` | empty — the i5 fixture restored its own staged widening |
| full suite before the commit | `I5_NESTED=1 QT_QPA_PLATFORM=offscreen PYTHONHASHSEED=0 python3 -m pytest -q` | exit 0; 1676 passed, 26 skipped (the i5 cases skip under `I5_NESTED`, exactly as inside the hook), 6 xfailed; 03:49→04:17 UTC |
| copy rebuild, both trees | `python3 -m rusterm --root <copy> snapshot --instrument <id> --as-of 2026-09-29` for all 44 ids, HEAD worktree then working tree | `HEAD_REBUILD_FAILED=0`, `CHANGE_REBUILD_FAILED=0`; 1320 measure rows compared, 1 moved |

Why some numbers here look huge: a bare `pytest -q` without `I5_NESTED=1`
lets an i5 case spawn `selfcheck.sh` → `acceptance.sh` → another whole suite
(measured: 3 test files took 1317 s that way). The hook always sets
`I5_NESTED=1`; the 28-minute wall above is a plain suite run on this machine
(today it also carried `PYTHONHASHSEED=0`).

## HANDOFF
Status: NOT STARTED
