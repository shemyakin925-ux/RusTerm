# TASK-122 — look and feel: dark theme, hotkeys, tabs, global search

- **Status: READY**
- **Report:** `agent/REPORT-122.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network 0, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## L1. Dark theme
Follows macOS appearance; charts and tables readable in both.
**Done when:** offscreen test both palettes; look.py shots in both.

## L2. Global search and hotkeys
Cmd+K: search any ticker/name in the base (not only the list), Enter
opens; Cmd+1..6 tabs; Cmd+R refresh; Esc closes dialogs.
**Done when:** offscreen key-event tests.

## L3. Several papers in tabs
Opened papers as closable tabs; state restored at next start.
**Done when:** offscreen test — 3 tabs, restart → same 3.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
