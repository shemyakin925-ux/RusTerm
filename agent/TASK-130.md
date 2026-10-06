# TASK-130 — С2: fill the control ten to ≥ 90 % (concept-map gaps)

- **Status: READY**
- **Report:** `agent/REPORT-130.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С2 (fill ≥ 90 %). Queue rules:
  `agent/TASK-131.md` «Rules of the new queue» (bind this task too).
  **Read PRODUCT.md first.**
- **Budgets:** network 0 (facts are already in the base), LLM 0.
- **Executor model:** GLM 5.3 (not Flash) from 06.10.

## Where we are (coordinator, 06.10, measured on a copy of the user base)

- Metric: `python3 tools/card_fill.py --root <copy>` — fill of the card
  over the last 5 **closed** years, control ten; exit 0 when ≥ 90 %.
- Before 06.10: 62 %. After the coordinator's fixes: **85 %**.
  - `rusterm history --rebuild` (new flag) rebuilds year-end snapshots
    with current rules; old snapshots kept holes.
  - `st_investments` never reported in a us-gaap balance → 0 with reason
    `st_investments_never_reported: us-gaap balance`
    (`SnapshotBuilder._stinv_never_in_full_balance`). IFRS stays None.
- Per company: JPM 100 · BAC 92 · DELL 97 · HPQ 94 · AAPL 96 · MSFT 99 ·
  **T 78 · AA 61 · FCX 79 · ORCL 64**.

## Step 0. Your staged TASK-111 U3 (before anything else)
Your main checkout holds TASK-111 U3 staged (upgrade button), message in
`/tmp/commit-msg-u3.txt` (STATE.json says so). The coordinator merged
your U0–U2 (`f511665`, `9e16aea`, `290460e`) and put the card on top
(`origin/agent/night-11`). Do: `git stash push -m u3-<date>` is NOT
allowed (shared stash) — instead commit U3 as is, then
`git pull --rebase origin agent/night-11`, resolve conflicts in
`rusterm/desktop/window.py` keeping the card (`_repaint_table(table,
view)`, `desktop_card`) and your upgrade button. TASK-111 U3 remainder,
U4, U5 are SUPERSEDED (→ TASK-133 R4, TASK-134 W3).
**Done when:** your U3 commit is on `agent/night-11`, desktop tests green
(`python3 -m pytest -q tests/test_desktop*.py tests/test_task111*.py
tests/test_product_card.py`).

## Setup (once)
Copy the base (P7): `sqlite3 ~/EquityLab/data/rusterm.db ".backup <copy>/rusterm.db"`,
then `python3 -m rusterm --root <copy> history --all --rebuild`.

## K1. Name the missing tag for each gap (first)
For each gap `tools/card_fill.py` prints (concept, company, year), find the
raw us-gaap tag in that company's facts for that period that carries the
value (`fact.concept` with `canonical_concept IS NULL`). Known from the
06.10 run: T `total_equity`; AA `operating_income`, `cogs`; ORCL
`total_debt` (since 2022), `pretax_income` (since 2018), `cogs` (since
2011); FCX `eps_diluted`; HPQ `invested_capital` 2021.
Write the table in REPORT-130: concept · company · tag · 10-K line it
matches · value. No code yet.
**Done when:** the table has a row for every concept of the top 15 gap
lines, or the row says «not in the filing» with the 10-K page checked.

## K2. Map the tags
Add the tags from K1 to the concept map (`rusterm/normalize/concepts.py`)
under the existing priority rules — a new map version, never editing a
released one. Reparse, rebuild history on the copy.
**Done when:** test per added tag (fixture fact → canonical concept);
`tools/card_fill.py --root <copy>` ≥ 90 % total and every company ≥ 80 %;
paste the output into the report.

## K3. Interest coverage `period_mismatch`
AAPL 2024–25, MSFT 2025–26, DELL 2025–26, T 2024–25 refuse with
`period_mismatch`: operating income and interest expense come from
different periods. Use the same annual period for both (the rule of
`_annual_common_period`); if a company stopped reporting interest
expense, the reason says so in words.
**Done when:** test on a fixture with misaligned quarterly interest →
annual pair chosen; card_fill gap list has no `interest_coverage` for
AAPL/MSFT.

## K4. Dividends per share for BAC
BAC `dps` / `div_yield` empty 2021–2025 while JPM is full. Find why
(tag or period) and fix.
**Done when:** card_fill: no `dps` gap for BAC.

## K5. DELL market cap before 2022 — one class only?
Card: DELL капитализация 2017–2021 = 14–28 млрд USD, FCF yield 33–38 %.
Dell then had classes A, B, C (public C) and V; the total looks like
class C alone. Check `market_cap_total` inputs (shares per class from
the 10-K cover / dei) against the 10-K; fix the class sum or, if class
shares are not in the facts, make the year «—» with reason
`share_classes_incomplete` instead of an undercount.
**Done when:** test on a two-class fixture; DELL 2020 капитализация is
within 10 % of the 10-K cover value or «—» with the reason.

## Do not
Same list as `agent/TASK-131.md` «Do not». Do not invent values: a cell
is a mapped fact or «—» with a reason (CONTEXT §3 rule 2).
