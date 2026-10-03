# TASK-113 — financial statements: income, balance, cash flow — years, quarters, TTM

- **Status: READY**
- **Report:** `agent/REPORT-113.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network 0, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

Facts are in the base (us-gaap/ifrs/cvm), only derived measures are shown.
Every analog (Yahoo Financials, Koyfin, TIKR) has the three statements.

## F1. Statement views
Tab «Отчётность» with sub-tabs Прибыли и убытки · Баланс · Денежный поток.
Rows = a fixed line list per statement (revenue, COGS, gross profit, opex,
operating income, interest, pretax, tax, net income, EPS; assets, cash,
receivables, …, equity; CFO, capex, FCF, dividends, buybacks). Values from
facts through the concept map; currency + «млн/млрд» once in the header.
**Done when:** test on AAPL fixture — every line resolves or says why; look.py — tab with ≥20 rows for DELL.

## F2. Years / quarters / TTM
Toggle «Годы | Кварталы»; first column «TTM» (sum of last 4 quarters for
flows, last instant for stocks). Same column order as Yahoo: TTM, newest → oldest.
**Done when:** test — TTM = sum of 4 quarter facts; quarter view shows
≥8 quarters for AAPL fixture.

## F3. Same rules for measures
Measure table gets the same «Годы | Кварталы» toggle; quarter flows never
land in a year column (rule already in `_history_walk`).
**Done when:** offscreen test — toggle switches columns; values equal core.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
