# TASK-120 — ownership tables and filings feed

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-120.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 100 requests, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## O1. Insiders
Forms 3/4/5 are collected (only `insider_net` uses them). Table: date,
person, role, buy/sell, shares, price, value; 12-month net.
**Done when:** test on stored forms; look.py — table for NVDA on copy.

## O2. Institutional holders
SEC 13F (free): top holders, change vs previous quarter.
**Done when:** test on recorded 13F; live on copy for AAPL.

## O3. Filings feed
List of latest SEC filings per paper (form, date, link) from submissions;
click opens the document.
**Done when:** test; look.py — feed rows for DELL.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
