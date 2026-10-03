# TASK-91 — measures that tell the truth about their inputs: periods, reasons, currencies

- **Status: READY**
- **Report:** `agent/REPORT-91.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-91.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Budgets:** network 0. LLM 0.
- **How to work:** as TASK-90. Goldens may move **only** in the commit
  that changes the rule, with `было → стало` per value in the message.
- **User base:** `/Users/anton/equitylab` is read-only. To measure on
  it: `cp -R /Users/anton/equitylab "$TMPDIR/eqlab-<item>"` and build
  there; never open the original for writing.
- **Place in queue:** after TASK-74 — the tail of the queue:
  TASK-74 → **91** → 92 → 93 → 94 (user's order, 23.09).
- **Relation to TASK-59 D1** (formula census): D1 lists behaviours;
  this task fixes the concrete defects below. If D1 already fixed one,
  write «closed by <sha>» and move on.

## Where we are (user base, AAPL latest snapshot, as_of 2026-09-21, read-only)

| measure | value | period in the row | defect |
|---|---|---|---|
| asset_turnover | 0.2901 | 2026-03-29…2026-06-27 (**one quarter**) | flow ÷ average stock on a quarter; FY ≈ 1.15 |
| roe | — | `missing_prior_period` | prior year-end equity exists in the filings (TASK-92 C1) |
| fcf | 110.2e9 | 2025-09-28…2026-06-27 (**9-month YTD**) | fed to `fcf_yield` as if TTM |
| ebitda | 132.4e9 | 9-month YTD | fed to `net_debt_ebitda` as if TTM |
| fcf_yield | 0.02244 | no period declared in lineage | TASK-69 P1 required a declared annual denominator |
| net_debt_ebitda | 0.1503 | no period declared | same |
| ev_ebitda | 34.06 | annual (`_annual_common_period`) | correct — the model to follow |

## B1. Flow ÷ stock (or ÷ price) uses an annual flow, declared

Pass 1 picks `max(common, key=(end, start))` (`core/snapshot.py:596`,
`:623`) — the newest period, which for a 10-Q filer is the quarter or
the YTD. That is fine for flow ÷ flow of the same period (margins,
effective_tax) and wrong for flow ÷ stock.

| Measure | Rule |
|---|---|
| `asset_turnover`, `roe`, `roe_incl_nci` | flow = newest **annual** (350…380 days) period ≤ as_of; begin stock = stock at that period's start (±10 days), end stock = at its end; none ⇒ `missing_prior_period` / `missing_data: <flow>` as today |
| `fcf_yield`, `net_debt_ebitda` | flow = the same annual window as `ev_ebitda` (`_annual_common_period`), lineage rows carry `period_basis='annual'` and the window |
| margins, `effective_tax`, `interest_coverage`, `nopat`, `ebitda`, `fcf` | unchanged (their own period is already stored in the row) |

**Done when:**
- a fixture shaped like a 10-Q filer (quarter, YTD and FY rows for the
  same concepts) gives FY-based `asset_turnover`, `fcf_yield`,
  `net_debt_ebitda`, and lineage names the window;
- the report prints `было → стало` for these three on a temp copy of
  the user base for all six papers.

## B2. Refusal reasons that do not lie

Measured on `3f7dcc9` (repro: NI = −50, revenue 0, one price, shares):

| Where | Now | Must be (dictionary §1.4) |
|---|---|---|
| `snapshot.py:1071` pe, NI ≤ 0 | `missing_data: net_income` (the fact exists) | `negative_denominator` / `denominator_zero` |
| `:1026` net_debt_ebitda, ebitda ≤ 0 | `missing_data: ebitda` | same |
| `:890` no price ⇒ early return writes the price reason into **all 13** valuation concepts | `net_debt`, `invested_capital` refused for `price_close` | they need no price: compute them |
| `:1002` net_debt | refused `missing_data: market_cap_total` when price is missing | net_debt does not depend on market cap |
| `formulas.py:102` effective_tax, pretax < 0 | `jurisdiction_rate` | `negative_denominator` |
| `formulas.py:680` unknown concept | `missing_data` | `concept_not_mapped` |

**Done when:** one table-driven test covers every row; a guard test
builds the valuation pass with each input present-but-nonpositive and
asserts no `missing_data: <x>` is written for an input `<x>` that has a
value.

## B3. A money measure is labelled with the currency of its inputs

- `net_debt` and `invested_capital` are written with
  `unit=price_currency` (`:1016`, `:1053`) although computed from facts
  in the filing currency: an OTC/ADR paper with a USD price and GBP
  facts gets a GBP number labelled USD.
- `ev` adds market cap (price currency) to debt, cash, minority (fact
  currency) with no currency check; `pb` and `div_yield` do check.

Rule: unit of a money measure = currency of its fact inputs; inputs in
more than one currency (price included where it is an input) ⇒
`currency_mismatch: A, B` (sorted), same as `pb`.

**Done when:** test with price USD + facts GBP: net_debt unit `GBP`,
ev / ev_ebitda / roic → `currency_mismatch: GBP, USD`; AAPL goldens
unchanged.

## B4. Valuation inputs respect `as_of` and staleness

- `_latest_canonical` (`:697`) takes the newest fact per concept with
  **no `as_of` bound** and **no staleness window**;
  `SnapshotRepo.latest_annual_fact` (repos.py:506) the same, and accepts
  any window ≥ 300 days (a two-year cumulative passes as «annual»).
- Consequences: `rusterm snapshot --as-of 2024-06-30` values a 2026
  balance sheet at a 2024 price; a debt tag abandoned years ago still
  enters today's EV.

Rule: facts with `period_end > as_of` are excluded (as pass 1 does,
TASK-22 J3); a stock input older than `_STALE_LOOKBACK_DAYS` from the
issuer's anchor ⇒ `stale_data: <concept>: last <date>` (TASK-55 Y1
form); annual = 350…380 days, the same constant as
`_annual_common_period`.

**Done when:** three tests (future fact, abandoned tag, 730-day window).

## B5. `roic` averages begin and end capital

`:1221` and `:1232` pass the same invested capital as begin **and**
end; the dictionary defines the average of the two. Rule: begin = IC
from stock facts at the start of the NOPAT window (±10 days); absent ⇒
`missing_prior_period`. **Done when:** test with two year-ends; AAPL
golden moves in this commit with `было → стало`.

## B6. CVM tax line: negate, do not take the absolute value

`normalize/concepts.py:243` `normalize_sign_cvm` flips only negative
3.08 values. DFP presents deductions as negative numbers, so a
**positive** 3.08 is a tax benefit; today it becomes a positive
`tax_expense` and yields a fake positive rate for a loss-making
company. Pinned by the first block of
`tests/test_task58_c4.py::test_map_leaves_positive_tax_and_other_lines_untouched`.

Rule: canonical `tax_expense` = −raw for every 3.08 row; `raw_value`
in the locator unchanged.

**Done when:** the pin is replaced by a stronger one with
`ЗАМЕНА-БУЛАВКИ:` / `ПОЧЕМУ СИЛЬНЕЕ:` (positive raw ⇒ negative value;
negative raw ⇒ positive; 3.01/3.04/junk unchanged — those asserts
stay); AMBEV golden unchanged (its 3.08 is negative).
