# REPORT-49 — TASK-49 (CA/OTC refusal census; two cheapest measures fixed)

First product task after six rounds of discipline work. Network used:
**4 EDGAR requests of the 40 budget** — zero live; the census runs on
saved responses (`tests/data/edgar/companyfacts_m6_*.json`, recorded in
earlier rounds). All numbers below are from runs, not estimates.

## Done

- **R1 census command**: new `rusterm census --instrument ID
  [--rebuild] [--json]` (`cmd_census`) — prints the ten-row
  measure × value × refusal table from the latest snapshot.
- **R1 offline replay**: `tests/test_task49_census.py` rebuilds both
  issuers from saved EDGAR responses and pins every row against
  `tests/data/golden_census_task49.json` (value = exact DB string,
  refusal = exact reason). Four tests, fully offline.
- **R1 table** (as_of 2026-09-09; CNQ = Canadian Natural, CA;
  NGGTF = utility ADR, OTC; measured AFTER the R2 fix — the refusal
  rows are the honest remainder, the two lifted measures are marked):

  | issuer | measure | value | refusal reason (missing:) |
  |---|---|---|---|
  | CNQ | net_margin | 0.2791393632939477 | — |
  | CNQ | asset_turnover | 0.4375215165726992 | — |
  | CNQ | **effective_tax (R2)** | **0.18284117513782946** | — |
  | CNQ | roe | — | missing_data: total_equity (EquityAttributableToOwnersOfParent never filed; only incl-NCI Equity is filed) |
  | CNQ | operating_margin | — | missing_data: operating_income (concept absent from all filings) |
  | CNQ | ebitda | — | missing_data: operating_income |
  | CNQ | nopat | — | missing_data: operating_income (tax_expense resolved by R2) |
  | CNQ | interest_coverage | — | missing_data: operating_income (interest_expense resolves via FinanceCosts) |
  | CNQ | fcf | — | missing_data: capex (capex facts exist only to 2018-12-31 — a fact-with-wrong-period case) |
  | CNQ | gross_margin | — | missing_data: gross_profit (concept absent) |
  | NGGTF | net_margin | 0.08733191790516631 | — |
  | NGGTF | asset_turnover | 0.0687216699414431 | — |
  | NGGTF | **effective_tax (R2)** | **0.25181598062953997** | — |
  | NGGTF | **nopat (R2)** | **1141728813.559322** | — |
  | NGGTF | operating_margin | 0.21599433828733192 | — |
  | NGGTF | interest_coverage | 1.611404435058078 | — |
  | NGGTF | roe | 0.01689693417863647 | — |
  | NGGTF | ebitda | — | missing_data: d_and_a (only 2018-09-30 facts — stale period) |
  | NGGTF | fcf | — | missing_data: ocf (concept absent) |
  | NGGTF | gross_margin | — | missing_data: gross_profit (concept absent) |

  Other issuers measured on the same run (CONTEXT §4 updated): RY
  4/10 (effective_tax 0.2189820440124207), BMO 5/10 (effective_tax
  0.25142857142857145), CPTP 3/10 (unchanged — us-gaap filer).
- **R2, two cheapest measures**: the census showed the single
  cheapest defect in the whole table — the IFRS concept map named
  tax expense `income_tax` while the measure formulas read
  `tax_expense`, so `effective_tax` refused «missing_data:
  tax_expense» with the tax fact alive in the store for every IFRS
  issuer. Fix: `CONCEPT_MAP_IFRS` key renamed, version bumped to
  `ifrs-full.v2` with the payload evidence in the comment (rule 9:
  IncomeTaxExpenseContinuingOperations — RY 12 facts to 2026-01-31,
  CNQ 6 to 2025-12-31, NGGTF 6 to 2025-09-30). That lifted
  **effective_tax on CNQ** (the Canadian issuer required by the
  done-when) and, as the second measure, **nopat on NGGTF** — its
  both inputs (effective_tax + operating_income) are now in place.
  Golden tests pin the three values above; lineage of each golden
  measure resolves to the stored EDGAR response (source_ref =
  saved sha256) with `period_basis` visible (NULL = direct
  single-period input, the documented default).
- **R2 honesty check**: every remaining refusal is pinned by the
  golden file with value None and an exact reason; `nopat`'s refusal
  continuation narrowed honestly (tax_expense resolved, only
  operating_income still missing). `tests/test_m6_ca.py` stays green;
  `golden_m6_ca.json` updated mechanically (9 entries
  `income_tax` → `tax_expense`; values, accn, pointers untouched).
- **R3, the key question**: REPORT-45 is right, CONTEXT §5 was wrong.
  Environment (this shell): none of the four variables exported. Env
  file `~/.rusterm.env` (RUSTERM_ENV_FILE unset → the loader reads
  it): `RUSTERM_SEC_UA` present (len 38), `RUSTERM_LLM_API_KEY`
  present (len 73), `RUSTERM_TWELVEDATA_KEY` present (len 32),
  **`RUSTERM_DART_KEY` ABSENT**. No values printed anywhere. No
  values leaked into the report.

## Blocked

- Nothing.

## Disputed

- **`RUSTERM_DART_KEY` does not exist** — neither in the environment
  nor in `~/.rusterm.env` (16 lines, four RUSTERM_* keys, DART is not
  one of them). CONTEXT §5's blanket «keys are in the executor's
  environment from 13.09.2026» is wrong for DART. Per the task this
  is the coordinator's call; the Korean channel stays untouched.
- The R2 done-when reads «две меры считаются для канадского
  эмитента»; from saved facts exactly ONE measure is computable for
  CNQ (effective_tax). The second-cheapest measure of the census
  (nopat) exists only on the OTC issuer — every other CNQ refusal
  lacks a concept CNQ never filed (operating_income, owners' equity,
  gross_profit) or a current-period capex. Making a second CNQ
  measure compute would require either inventing inputs or changing
  formula semantics (e.g. roe over incl-NCI equity) — left to the
  coordinator.

## What not to trust

- The census reflects the SAVED companyfacts snapshots (recorded in
  the m6 round). If an issuer filed new facts since, a fresh EDGAR
  pull may show different refusals; the fixtures, not the live site,
  are the reproducible ground truth.
- `cmd_census` builds a snapshot only when none exists or
  `--rebuild`; it never collects from the network itself.
- The CONTEXT §4 coverage line now carries measured per-issuer
  numbers for five issuers; US «10 of 10» is not re-measured this
  shift.

## HANDOFF

Status: PARTIAL (shift in progress, interim block)
Items done: R1 census command + offline golden replay; R2 IFRS alignment (ifrs-full.v2) lifting effective_tax and nopat with golden values and lineage proof; R3 key census (DART absent)
Items not done: TASK-50 T6 (hook trap), TASK-51, TASK-52 — next in queue
Acceptance: this commit's selfcheck prints «Итог: пройдено 13, провалено 0», exit 0
Tests: census suite 4 cases green; full suite green in this commit's selfcheck
Guards: none touched; CONCEPT_MAP_IFRS version bumped with payload evidence, pins updated with declared replacement
Schema: unchanged (44)
Network: 4 EDGAR requests of 40 (all during earlier rounds' recorded fixtures era — this shift itself made 0 live requests)
Model: 0 llm_calls; fake clients only
Secrets: grepped the four key names across the diff — 0 value hits; presence/lengths only, see R3
Pushed: yes (pushed with the hand at end of shift)
Questions for the coordinator:
1. DART key: issue one, or accept the Korean channel as keyless? (Disputed)
2. roe over incl-NCI equity as a named fallback for CNQ — wanted? (Disputed)
