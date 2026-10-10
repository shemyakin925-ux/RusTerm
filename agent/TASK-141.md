# TASK-141 — rulings on REPORT-139 questions: split basis, split debt, revenue line, CIK hint

- **Status: READY** (take after TASK-140)
- **Report:** `agent/REPORT-141.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С2 (numbers match Yahoo), С5 (add any ticker).
- **Budgets:** network ≤ 150 (SEC, Yahoo via `--cache`), LLM 0. Copy of
  the user's base (P7) — the B2 copy with NVDA/KO/XOM/PFE/WMT is fine.
- **Relay:** as in `agent/TASK-139.md`, with REPORT-141.

## Where we are (coordinator, 09.10)
TASK-139 ACCEPTED (B1 46ca7a1, B2+B3 406e3f9; verify 13/0). Its six
questions are answered here. Acceptance tools: `tools/card_fill.py`,
`tools/yahoo_check.py` (control ten must stay ≥ 99 % / fill ≥ 90 %).

## Rulings (binding)
- Q1 XOM → D4 (manual CIK hint). B17 «last feed row wins» stays.
- Q2 PFE debt → D2 (sum of the split pair). The ТЗ-31 C2 pin is replaced,
  not deleted: ЗАМЕНА-БУЛАВКИ in the commit (agent/p1_rule.sh).
- Q3 WMT → D1 (my 08.10 code; you fix it — rule below).
- Q4 PFE revenue → D3, gated by the control ten.
- Q5 → done by D5 (one verify at the end).
- Q6 → the coordinator tells the user (reparse); not your item.

## D0. Concept map version (from 406e3f9)
The dps successor changed `CONCEPT_MAP` but the version stayed
`us-gaap.v7`: facts stored as v7 no longer mean one mapping. Bump to
`us-gaap.v8` the way v7 was introduced (version constant, pins in
`tests/test_task130_k2_map.py` and peers, GUIDE.md line). D3 lands in the
same v8 if it passes, otherwise v8 = dps only.
**Done when:** `grep -rn "us-gaap.v7" rusterm/ GUIDE.md` → only history
comments; full suite green.

## D1. Share count basis across a split (WMT 2024 ×3)
A shares fact whose filing date is after a split and whose period end is
before it is already on the post-split basis. In the historical market
cap, divide such a count by `core.prices.split_factor_after` between the
period end and the fact's filing date (filing date from the fact's
document; no date → leave as is and add lineage role saying so).
**Done when:** fixture test (3:1 split between period end and filing) →
cap = actual close × count ÷ 3; `yahoo_check.py US-WMT` market_cap 2024
within 5 %; control ten unchanged (≥ 99 %).

## D2. Debt filed as a non-current + current pair (PFE)
Period without the combined tag (`LongTermDebt` / combined debt tags of
`core/debt.py`) but with `LongTermDebtNoncurrent` and
`LongTermDebtCurrent` for the same date → total_debt = their sum, both
facts in lineage, in the snapshot AND the card (`card.statement_series`
uses the same `core/debt.py` door — no second copy of the rule).
**Done when:** fixture test (pair → sum; combined present → combined
only); `yahoo_check.py US-PFE` total_debt within 5 % for the last 3
years; control ten ≥ 99 %.

## D3. Revenue line (PFE)
When `Revenues` and `RevenueFromContractWithCustomer…` are both filed for
the same period and `Revenues` is larger, the card and snapshot take
`Revenues` (the income statement's top line). Implement as a rank rule in
the concept map (new map version, reparse) only if the control ten stays
≥ 99 % with it; otherwise revert and report the numbers.
**Done when:** `yahoo_check.py US-PFE` revenue within 5 % 2023–2025 and
control ten ≥ 99 % — or the revert with both runs quoted.

## D4. Manual CIK hint (XOM)
`rusterm add --ticker XOM --market US --cik 34088` (and the same field,
optional, in the «+ компания» dialog) resolves to the given registrant
instead of the feed row; the choice is stored with origin `manual`.
**Done when:** test with a fake feed (feed says CIK A, `--cik B` → B,
origin manual); on the copy XOM via `--cik 34088` gets ≥ 8 year columns
and `card_fill.py US-XOM` ≥ 80 %.

**Coordinator, 09.10 — your D4 commit hangs the suite (killed twice
after 1–2 h):** `tests/test_desktop_*s1_watchlist_add_button*` blocks
forever in `QDialog.exec()` (offscreen). The test patches
`QInputDialog.getText`; the new CIK `QDialog` bypasses the patch (known
B49 class). Fix: keep the ticker prompt on `QInputDialog.getText` and ask
the optional CIK with a second `QInputDialog.getText` (empty = feed
row), or route the dialog through one patchable function. Do not change
the s1 test. Before committing: `python3 -m pytest -q -x
tests/test_desktop_*s1*` must finish in seconds.

## D5. One verify at the end
**Done when:** `python3 agent/relay.py verify` → 13/0 on the final head.

## Do not
Same list as `agent/TASK-131.md` «Do not».
