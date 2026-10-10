# TASK-119 — company profile, calendar, alerts

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-119.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 100 requests, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## A1. Profile
Block on the company card: description, sector/industry, employees, HQ,
website, fiscal year end, next report date — SEC submissions + Yahoo
profile (no key).
**Done when:** test on recorded json; look.py — profile text for DELL.

## A2. Calendar
Tab «Календарь»: report dates and ex-dividend dates for papers in lists,
next 60 days.
**Done when:** test on fixture dates; sorted, grouped by week.

## A3. Alerts
Rules: price crosses X, measure crosses X, new filing (10-K/10-Q/8-K).
Checked in the TASK-110 pass; macOS notification + list in the window.
**Done when:** test — rule fires once per crossing; new-filing rule fires on a new accession only.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
