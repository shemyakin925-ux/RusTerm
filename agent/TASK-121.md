# TASK-121 — portfolio

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-121.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network 0, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## PF1. Positions
Portfolio = list of (paper, quantity, average price, date). Add/edit in
window; stored in the base (new migration).
**Done when:** test CRUD; versioned like watchlists.

## PF2. Results
Value, P&L absolute/%, weight, dividends received (corporate actions ×
quantity), total return vs S&P 500 / IMOEX.
**Done when:** test on fixture prices — numbers exact.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
