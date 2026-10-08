# TASK-137 — С2: match Yahoo ≥ 95 % (input choice by tag meaning)

- **Status: ACCEPTED (08.10, done by the coordinator) — Y1 done, Y3 97 %. Y2 (AAPL/MSFT debt) → BACKLOG P5.**
- **Report:** `agent/REPORT-137.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` «Контрольная десятка»: ≥ 95 % of
  numbers within 5 % of Yahoo. Queue rules: `agent/TASK-131.md`.
- **Budgets:** network ≤ 20 requests (Yahoo, via the tool's cache), LLM 0.

## Where we are (coordinator, 07.10, `agent/RECONCILE-2026-10-07.md`)
`python3 tools/yahoo_check.py --root <copy> --cache <dir>` → **90 %**
(166/184). Fixed by the coordinator: the year column is the fiscal year
(`tui/model._history_walk`). Remaining misses are listed by the tool.

## Y1. Tag meaning beats filing basis (first)
FCX FY2024: `NetIncomeLoss` 1.889 B exists only as `restated`;
`ProfitLoss` 4.399 B (incl. NCI) as `as_reported`. The input scan picks
any as_reported tag and looks at restated only when the concept is
absent, so `ProfitLoss` wins → net margin, ROE, P/E wrong (FCX, T, AA).
Rule: within one canonical concept and one period, the best tag rank
wins; as_reported beats restated only between facts of the SAME tag.
Apply in every input path that scans as_reported then restated
(`SnapshotBuilder._issuer_inputs`, the capital scan near
`restated_stock_facts`). Lineage role keeps `basis: restated`.
**Done when:** test — fixture with ProfitLoss as_reported + NetIncomeLoss
restated for one period → NetIncomeLoss chosen; `yahoo_check` shows no
`net_income`/`roe`/`pe` miss for FCX 2023–2024 and T 2024.

## Y2. AAPL and MSFT total debt
Ours is 8–13 % below Yahoo's long-term + current debt (AAPL 2024 96.7 vs
106.6 B; MSFT 2024 44.9 vs 51.6 B). Find the missing part (commercial
paper, current portion) in the facts; add it under the existing
total_debt rule or a new map version.
**Done when:** test per company fixture; `yahoo_check`: no `total_debt`
miss for AAPL/MSFT.

## Y3. Re-measure and report
**Done when:** `yahoo_check` total ≥ 95 % on the copy (paste the output);
every remaining miss in the report has a line: defect or Yahoo method
(with the 10-K line that proves ours).

## Do not
Same list as `agent/TASK-131.md` «Do not». Never tune our numbers toward
Yahoo: the 10-K is the truth, Yahoo is a smoke detector.
