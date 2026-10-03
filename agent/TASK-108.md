# TASK-108 — live-window findings 01.10 (rusterm-check skill)

- **Status: DONE by coordinator — see REPORT-108**
- **Report:** `agent/REPORT-108.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 40 SEC requests (W3 only), LLM 0.
- **Queue:** after TASK-107 and TASK-106.
- Measure on a **copy** of the user's base (P7).
- Live check: `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  → `report.json`; "filled" below = cells in column «сейчас» ≠ «нет данных».

## Where we are

Coordinator branch `claude/table-display-fixes` (merge before this task):
table numbers formatted (%, ×, млрд), percentile rows named,
`st_investments` / NCI discontinued → 0 by the D7 rule with a lineage role.
Prices refreshed 01.10 (all 38 to 2026-09-30); snapshots rebuilt.
Filled «сейчас» on the user's base: 660 → 701 of ~1300.

## W1. total_return / drawdown — price lineage

Formulas exist (`formulas.total_return`, `drawdown`), measures are
`concept_not_mapped`. A coordinator attempt (16ad207, reverted f0c20dc)
failed I4: `measure_lineage` CHECK needs a fact, measure or CA row; a
price series has none. Add a NEW migration with price lineage
(e.g. `measure_lineage_price(measure_id, instrument_id, date_from,
date_to, source)`) counted by I4. Window = 365 days to `as_of`, period in
the measure row; dividends from `corporate_action`; **no split
adjustment** (Twelve Data close is already split-adjusted: AAPL
2020-08-31 has no 4× jump).
**Done when:** test — 365-day window, dividend counted, split not
applied twice, <2 points → `missing_data: price_close`; copy: DELL, BAC
`total_return`, `drawdown` numbers; `rusterm snapshot` passes I4.

## W2. Stale debt tag (SMCI)

`stale_data: total_debt: last 2023-06-30` blocks 5 measures for SMCI.
Find the debt tag SMCI files after 2023 and map it (concept map). Do NOT
zero debt.
**Done when:** copy: SMCI `ev`, `net_debt` numeric; test on the mapped
tag; list of the 38 with any `stale_data: total_debt` before → after.

## W3. CRM net_debt looks 3× high

CRM `net_debt` = 31.0 bn; public filings: debt ~10 bn, cash ~14 bn.
Print the lineage facts of `total_debt` for CRM; fix the mapping that
pulls the wrong line (leases? unearned revenue?).
**Done when:** test on the offending tag; copy: CRM `net_debt` within
±15 % of (debt − cash − ST investments) from the latest 10-Q.

## W4. `refresh` forgets earlier collection

`rusterm refresh --dry-run --watchlist peers` plans «первый сбор» for
all 38: `ingest` never writes `issuer_state`, so the first `refresh`
re-downloads every companyfacts. `ingest` (edgar) records
`issuer_state` like `refresh` does.
**Done when:** test — ingest then `refresh --dry-run` → no «первый сбор»;
copy: count before → after.

## W5. «Отрасль»: every row `period_mismatch`

hardware_electronics: all 5 aggregates refuse `period_mismatch`. Report
per peer the period each measure uses; apply the 2-year window rule of
TASK-97 Q8 to industry aggregates as it is applied to percentiles.
**Done when:** copy: refused aggregates per sector before → after; test.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations.
- Write to `~/EquityLab` (P7).
