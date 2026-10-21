# TASK-143 — cards for filers without an operating-income line (PFE, XOM)

- **Status: READY** (take after TASK-142)
- **Report:** `agent/REPORT-143.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С2 (fill, Yahoo match) for any added company.
- **Budgets:** network ≤ 100 (Yahoo via `--cache`), LLM 0. Copy of the
  user's base (P7) with NVDA/KO/XOM/PFE/WMT.
- **Relay:** as in `agent/TASK-139.md`, with REPORT-143.

## Where we are (coordinator, 21.10)
TASK-141 ACCEPTED (D0–D5, verify 13/0 on 3ccee30). Open from REPORT-141:
XOM card 70 %, PFE 70 %: neither files `OperatingIncomeLoss`, so the whole
chain (operating_income → ebitda, margins, roic, nopat, ev_ebitda,
net_debt_ebitda, interest_coverage) is «—». XOM debt is
`LongTermDebtAndCapitalLeaseObligations` + `DebtCurrent`.

## Rulings
- Q1 XOM debt → F2. Q2 PFE lease residual → accepted as methodology.
- Q3 user's base reparse → the coordinator tells the user.

## F1. Operating income when the line is not filed
Period without any operating-income tag: operating_income =
`IncomeLossFromContinuingOperationsBeforeIncomeTaxes…` + interest
expense (the map's interest_expense tags) − interest income
(`InvestmentIncomeInterest`, if filed; absent = 0). Lineage role names
the derivation; never used when an operating-income tag exists for that
period. Same rule in the snapshot and the card (one function in core).
**Done when:** fixture test (no OI tag → derived; OI tag present → tag
wins); on the copy `card_fill.py US-PFE US-XOM` ≥ 80 % each;
`yahoo_check.py` control ten ≥ 99 % (unchanged) and PFE/XOM listed.

## F2. Debt pair extended (XOM)
Add `LongTermDebtAndCapitalLeaseObligations` (non-current) +
`DebtCurrent` as a second ruled pair in `core/debt.py`, same rule as D2
(both on one date; combined tag wins).
**Done when:** fixture test; `yahoo_check.py US-XOM` total_debt within
5 % for the last 3 years or the residual named (leases).

## F3. Verify
**Done when:** `python3 agent/relay.py verify` → 13/0 on the final head.

## Do not
Same list as `agent/TASK-131.md` «Do not».
