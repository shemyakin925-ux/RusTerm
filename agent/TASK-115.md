# TASK-115 — screener and side-by-side comparison

- **Status: READY**
- **Report:** `agent/REPORT-115.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network 0, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

Only one paper or one peer set at a time. Finviz/Koyfin: filter the whole
base, compare several papers in one table.

## S1. Screener
Tab «Скринер»: filters on any measure (>, <, between), market, sector;
result table sortable, click opens the paper; saved screens (name → filter
JSON in config).
**Done when:** test — filter «pe < 15 and roe > 0.15» on a fixture returns
exactly the expected ids; offscreen — sort by column works.

## S2. Compare
Select 2–8 papers (from list or screener) → table measures × papers,
best value highlighted per row, export csv.
**Done when:** offscreen test — 3 papers → 3 value columns, highlight on
max/min by measure direction.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
