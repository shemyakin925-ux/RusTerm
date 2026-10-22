# TASK-144 — «Добавить аналоги» for a company from a new industry (С4)

- **Status: TAKEN BY THE COORDINATOR (user, 22.10: «тз 144 и финал сделай ты»). Executor: do NOT take it; after TASK-143 hand, then `wait`.**
- **Report:** `agent/REPORT-144.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С4 + С5: a newly added company gets
  a peer table, not a refusal.
- **Budgets:** network ≤ 200 (SEC only, free; follow of the chosen
  peers counts), LLM 0. Copy of the user's base (P7).
- **Relay:** as in `agent/TASK-139.md`, with REPORT-144.

## Where we are (coordinator, 21.10)
REPORT-142 E3: NVDA (3674), KO (2080), XOM (2911), PFE (2834), WMT (5331)
share no SIC with anyone in the base → «Аналоги» shows a refusal. The
base has only 5 groups (banks, hardware_electronics, mining_metals,
software, telecom). Correct by the rule, wrong for the product.

## G1. Candidates from SEC, ranked by revenue (core, no Qt)
`core.peers_suggest(sic, exclude)`: list of companies with that 4-digit
SIC from EDGAR (company browse by SIC, or the submissions bulk index —
measure which is cheaper; record it), ranked by the latest annual
revenue from ONE `frames` request
(`/api/xbrl/frames/us-gaap/Revenues/USD/CY{year}.json`, fall back to
`RevenueFromContractWithCustomerExcludingAssessedTax`), top 5 with a
ticker on a US venue. Deterministic: same inputs → same list.
**Done when:** fixture test (fake SIC list + fake frames → expected top 5,
order by revenue, companies without a ticker skipped); live on the copy
for NVDA: list quoted in REPORT (expect names like AVGO, AMD, INTC, QCOM).

## G2. Window: one button
On «Аналоги» with no group, besides the refusal text: button «Добавить
аналоги…» → dialog lists the 5 candidates (checkboxes, all on) → OK adds
the checked ones through the same door as «+ компания»
(`desktop_actions.follow_instrument`) and creates the group (id = SIC
name in latin, origin `sic`, approved), then repaints. Dialogs via
`QInputDialog`/a patchable seat only (TASK-141 D4 hang).
**Done when:** offscreen test with a fake suggest + fake follow: button
visible on a company without a group, OK → group with self + checked;
q1 tab-hint guard green; `pytest -x tests/test_desktop_*` finishes.

## G3. Measure
On the copy: run G2's door for NVDA, KO, XOM, PFE, WMT.
**Done when:** REPORT table ticker · group · members · seconds; each
has ≥ 4 members and «Аналоги» shows the table with a median row
(`desktop_peers.peer_table`, ≥ 3 numbers per column).

## G4. Verify
**Done when:** `python3 agent/relay.py verify` → 13/0 on the final head.

## Do not
Same list as `agent/TASK-131.md` «Do not».
