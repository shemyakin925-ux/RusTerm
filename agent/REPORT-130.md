# REPORT-130 — С2: fill the control ten to ≥ 90 % (concept-map gaps)

## Done
## Blocked
## What not to trust
## Disputed
## Runs
## HANDOFF
Status: NOT STARTED
# REPORT-130 — TASK-130 (C2: card fill ≥ 90 %)

Executor: GLM 5.3, night of 07.10.2026. Branch `agent/night-11`.
Base copy: `/tmp/rt-task130` (sqlite .backup of `~/EquityLab/data/rusterm.db`,
never touched the original), `history --all --rebuild` run on it.

Arrival: selfcheck 13/0 at `dcae6f6` (TASK-111 U3 commit landed before this
task; see REPORT-111). Baseline measured:

```
US-JPM 100%  US-BAC 91%  US-DELL 97%  US-HPQ 94%  US-AAPL 96%
US-MSFT 99%  US-T 78%    US-AA 59%    US-FCX 95%  US-ORCL 63%
ИТОГ 1389/1614 = 86% (цель 90%)
```

## Done

### K1 — the missing tag behind each gap (no code)

Method: for every gap line of `tools/card_fill.py` the raw facts of the
company were queried (`fact.concept` with `canonical_concept IS NULL`,
`superseded_by IS NULL`, `status='ok'`), values matched against the
10-K line they carry. One base for the whole task: 1.11 M facts carry no
`concept_map_version` at all (ingested before v4/v5) — a **reparse** is
required for any map addition to reach them (K2 does it).

| concept | company | tag (us-gaap) | 10-K line it matches | value (proof) |
|---|---|---|---|---|
| cogs | AA | `CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization` | «Cost of goods sold (exclusive of expenses shown separately below)» | FY2021 9 153 M |
| cogs | T | `OtherCostOfOperatingRevenue` | «Operating expenses: Cost of revenues» | FY2024 27 032 M |
| cogs | ORCL | not in the filing | Oracle reports expense components (cloud/license support, hardware, services), no COGS line; mapped `CostOfRevenue` stops 2011 | — |
| dps | AA | `CommonStockDividendsPerShareCashPaid` exists, **do not map**: annual windows carry the quarterly rate (FY2023 = 0.10 while 4×0.10 was paid) — mapping would serve dps 4× understated | «Cash dividends declared per common share» | Q 0.10, FY window also 0.10 (contradiction) |
| dps | BAC | facts exist (`CommonStockDividendsPerShareDeclared`) but with `period_start = period_end` = declaration dates (2023-02-01, 04-26, 07-19, 10-18; 0.22/0.22/0.24/0.24) — the dps TTM window wants periods, so it refuses; fix = K4 | «Dividends declared per common share» | 2023 sum 0.92 |
| dps | ORCL | mapped `CommonStockDividendsPerShareDeclared` stops 2011; no unmapped per-share tag since | not in the filing (in stored facts) | — |
| operating_income | AA | not in the filing | AA income statement has no operating-income subtotal (2021 dump: Sales → COGS → SG&A → R&D → D&A → restructuring → interest → pretax); no `OperatingIncomeLoss` facts at all | — |
| pretax_income | ORCL | not in the filing (stored facts) | only the Domestic/Foreign split is tagged (`IncomeLossFromContinuingOperationsBeforeIncomeTaxes{Domestic,Foreign}`); the combined line is absent | — |
| total_debt | ORCL | `DebtLongtermAndShorttermCombinedAmount` — **already mapped** (us-gaap.v5, ТЗ-108 W2), but 245 facts predate the map → reparse | «Debt» (notes payable, total) | FY2023 90 481 M, FY2024 86 869 M, FY2025 92 568 M |
| total_debt | AAPL 2021 | not in the filing as one tag: term debt 118.1 B is `DebtInstrumentCarryingAmount` (per-instrument tag, lookalike risk), commercial paper 6.0 B separate; `LongTermDebt` resumes only 2022-06-25 | «Total term debt» + «Commercial paper» | 118.1 + 6.0 B |
| total_equity | T | no parent-only tag; T files only `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` (+ `MinorityInterest`); fix = identity incl_nci − NCI in the capital assembly | «Total stockholders' equity» − «Noncontrolling interest» | FY2024 118 245 − 13 873 = 104 372 M |
| total_equity | AA 2025 | same shape as T at 2025-12-31: incl_nci 6 118 M, no plain tag, no NCI at the date | «Total stockholders' equity» | 6 118 M |
| eps_diluted | FCX 2022–25, DELL 2022 | no annual EPS facts in the filing feed (quarterly + YTD only); FY EPS from quarters would be a per-share sum — refused | — | — |
| invested_capital inputs | AA 2024–26 | **guard defect, not a tag**: `unmapped_current_investments` (repos.py) middle arm `LIKE '%MarketableSecurities%Current%'` has no `Noncurrent` exclusion and SQLite LIKE is case-insensitive — `MarketableSecuritiesNoncurrent` (AA files it 2024+) blocks the legitimate st_investments = 0 | balance has no current investments line | — |
| st_investments | T, AA, ORCL | legitimately zero (`st_investments_never_reported: us-gaap balance`, coordinator's 06.10 rule) | — | 0 |
| effective_tax | AA | honest «—»: computed rate −5.17 % is outside the plausibility band (`jurisdiction_rate`) — Alcoa's one-off-heavy years; Yahoo shows the same wild rates | — | — |
| effective_tax | ORCL | blocked by pretax_income (above) → «—» | — | — |
| invested_capital/roic | HPQ 2021–23 | 2021: year snapshot assembles through `_issuer_inputs`, where the 1100-day staleness door eats `minority_interest` (last 2016) and `st_investments` (last 2009) before the zero-rules can answer; 2022+ take another path and compute | — | — |

Expected honest gain: T 78→~93 %, AA 59→~69 % (capped: operating income,
dps, effective tax are structurally absent or unusable), ORCL 63→~69 %
(capped: pretax, cogs, dps absent), BAC 91→97 % (K4). Total ≥ 90 % is
reachable; **every company ≥ 80 % is NOT reachable honestly for AA and
ORCL** — evidence above, coordinator's call in Disputed.

NOW: K1 done, step 5
