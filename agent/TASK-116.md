# TASK-116 — valuation: multiple ranges, simple DCF, dividend history

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-116.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network 0, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## V1. Multiple vs its own history
For P/E, P/S, P/B, EV/EBITDA: current value, 5-year min/median/max from
yearly history, percentile of today.
**Done when:** test on fixture history — range and percentile exact.

## V2. Simple DCF / reverse DCF
Inputs: FCF TTM, growth (default = 5-year FCF CAGR clipped to [0, 15 %]),
discount 9 %, terminal 2.5 %, net debt, shares. Output: value per share vs
price; reverse DCF = growth implied by price. Editable fields in the window.
**Done when:** test against a hand-computed case (±0.1 %).

## V3. Dividends
Table by year: DPS, payout, yield on year-end price, growth; from
corporate actions (Yahoo).
**Done when:** test on fixture actions; look.py — table for a dividend payer.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
