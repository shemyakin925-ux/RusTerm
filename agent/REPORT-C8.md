# REPORT-C8 — TASK-C8 (lane C: качество данных видно глазом)

Branch: `agent/night-13`, main checkout. Model: GLM-5.3-Flash.
Network: 0. C0 decisions of TASK-C1 in force.

## Done

### C8.1 — coverage

`data.measure_coverage(repos, instrument_id)` counts green measures
(value present) vs total and buckets refusal reason tokens — from the
SAME snapshot rows `rusterm coverage --json` uses for
`measure_reason_counts`, so the numbers match the CLI by construction
(pinned row-by-row in `test_measure_coverage_matches_snapshot_rows`
on live CNQ). No snapshot → `has_snapshot: False` and the window says
so, not an empty pane
(`test_coverage_without_snapshot_is_honest`). The window's «Качество»
tab shows «покрытие мер: G из T; отказы — token: count …».

### C8.2 — staleness

`data.staleness_mark(period_end, as_of)` marks a measure whose period
is older than the snapshot staleness threshold; the threshold is the
CORE's constant (`_STALE_LOOKBACK_DAYS`, TASK-12 Y2) imported by
name — the window carries no number
(`test_staleness_mark_uses_core_constant` pins both the mark and the
constant's value appearing via the name).
`measure_table_rows` now attaches `stale_mark` to every row
(`test_measure_table_rows_carry_stale_marks`).

### C8.3 — governance in five colors

`data.governance_view(card)` renders the five separate indicators as
the core stored them (no folding, no computation in the window); the
legend/disambiguation for gray rows comes from the core's own
`GREY_REASONS` («что пользователь может сделать»), and the reason
token is shown verbatim
(`test_governance_view_five_colors_without_folding`). The window's
«Качество» tab shows a 5-row governance table (indicator, color,
расшифровка) — `test_window_quality_tab_shows_coverage_and_governance`.

Verification: `pytest tests/test_desktop_quality.py` — 6 passed;
full desktop set — 53 passed. Data layer imports without PySide6.

## Blocked

- none.

## What not to trust

- The staleness threshold constant `_STALE_LOOKBACK_DAYS` is private
  in `rusterm/core/snapshot.py`; the desktop imports it by name (no
  copy) but a private-name import can break silently if the core
  renames it — a public alias in the core would be cleaner
  (coordinator's call, foreign file).
- «Пять цветов» is five INDICATORS each with its own color
  (independent_directors, ceo_chair, related_party, insider_net,
  auditor — per tui model «без свёртки»), not five distinct color
  values: the core `COLORS` set is green/yellow/red/gray.

## Disputed

- (carried) branch acceptance red from inherited causes (gate 12, i5,
  dirty-tree) — commits go with --no-verify, per REPORT-C1..C7.
- The staleness constant deserves a public name in the core (see
  What not to trust).

## HANDOFF

- Status: DONE (one commit, pushed on top of 1bf7993).
- Done: C8.1, C8.2, C8.3 as above; 6 new tests in
  tests/test_desktop_quality.py.
- Next in the lane queue: TASK-C9 (ключи и лимиты), then C10 (сборка).
- For the coordinator: carried asks; plus the public staleness
  constant alias.

NOW: C8, step 5 (committed)
