# TASK-143 — cards for filers without an operating-income line (PFE, XOM)

- **Status: ACCEPTED (22.10, coordinator) — F0a b64e462, F0b 8462418, F1 e1335eb, F1b 7d6dc5f, F2 a9caebb; hand acceptance green. PFE 94 %, XOM 92 %, control ten Yahoo 99 %. Q1/Q2 (OI and XOM debt vs Yahoo methodology) accepted as named methodology.**
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

## How to finish (new rule, 22.10)
`relay.py hand` already runs the full acceptance and refuses on red. Do
NOT run `relay.py verify` before it — that was a second ~80-min run per
task. Sequence: last commit (its hook runs acceptance) → `hand` → `wait`.

## F0a. One refusal must not abort «Обновить» (REPORT-142 Q1, first)
`refresh_one`: a `ProviderError` from EDGAR submissions turns into a
`TypeError` and aborts the whole window pass. A per-instrument refusal
is recorded (counted in «отказов: N» of the summary line, reason named)
and the pass goes on with the next instrument.
**Done when:** test: fake provider raises ProviderError for instrument 2
of 3 → pass finishes, instruments 1 and 3 refreshed, summary «отказов: 1».

## F0b. Desktop tests do not start the background pass (REPORT-142 Q2)
Set `RUSTERM_NO_AUTO_REFRESH=1` once for the whole desktop test family
(a fixture in `tests/conftest.py` applied to `test_desktop_*`), except
tests that test the start-up pass itself (they unset it explicitly).
Do not delete the per-test settings already there.
**Done when:** `pytest tests/test_desktop_*` green 3 runs in a row;
grep shows the fixture; the start-up-pass tests still run the pass.

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

## F1b. Not for banks (coordinator, 22.10 — from your F1 test)
Your F1 derives operating income for JPM too. For a bank, interest
income and expense ARE the business: pretax + interest expense −
interest income is meaningless and lands in the snapshot and in the
banks' peer medians. The derivation applies only to non-bank issuers:
same bank test the card already uses to hide bank rows
(`card.BANK_HIDDEN` / the bank model in core — reuse it, do not add a
second definition). Banks keep the honest «—» with
`missing_data: operating_income`.
**Done when:** test: bank fixture with pretax + interest → operating
income stays None; non-bank → derived; `test_m3_snapshot` keeps JPM out
of `derived_named` and in the refusal set.

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
