# TASK-123 — quality tab content and migration without the terminal

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-123.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 50 requests, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Q1. Quality tab says something
All governance rows are grey `not_collected`. Fill what free data allows:
auditor and auditor change (10-K), insider net (forms), related-party
mention (10-K text search), going-concern flag, restatements count (our
`restated` facts). Each row: value, colour, one-line why.
**Done when:** test per indicator; look.py — ≤50 % grey rows for US papers on copy.

## Q2. Migration without the terminal
App start with an older schema: backup → migrate → continue, progress in
the window; failure restores the backup.
**Done when:** test — schema 47 base opened by app → 48, backup file
exists; injected failure → base restored byte-identical.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
