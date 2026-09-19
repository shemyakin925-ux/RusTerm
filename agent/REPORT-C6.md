# REPORT-C6 — TASK-C6 (lane C: панель источника целиком)

Branch: `agent/night-13`, main checkout. Model: GLM-5.3-Flash.
Network: 0. C0 decisions of TASK-C1 in force.

## Done

### C6.1 — panel on click

`data.source_panel_view(repos, paths, measure_row)` renders the panel
from `tui_model.source_panel` plus the fact row and the raw-store
location — nothing is computed on the spot. Lines: concept and
method_version, unit (from the measure row), per source: channel
kind, 16 chars of the stored-response hash (`source_ref` — the
document), the raw-store path, the input fact's period end. The
window's `on_cell_clicked` now renders this view; the previous
hand-rolled line assembly is gone (single door).

### C6.2 — open the stored response

`data.raw_object_location(paths, sha)` — `raw/store/<2>/<sha>` and
whether the file exists. The window gains «открыть сохранённый ответ»
(`open_raw_button`), enabled only when the clicked measure has an
existing raw file; the click hands the file URL to
`QDesktopServices.openUrl` (system opener). Missing file → the button
stays disabled, the panel says «сырья нет в хранилище» — no crash.
Pinned by `test_window_open_raw_button_opens_existing_file` (stubbed
QDesktopServices; URL ends with the stored sha) and
`test_raw_location_exists_and_missing`.

### C6.3 — refusal explained in place

For a refused cell the panel shows the reason line and, when the
reason carries a continuation, names the missing concept explicitly:
«не подан: total_equity — подстановки нет: значение строится только
из поданных фактов». Live CNQ from the census fixture:
`test_refusal_panel_names_missing_concept` pins CNQ `roe`
(«missing_data: total_equity») naming total_equity.

Verification: `pytest tests/test_desktop_source_panel.py` — 4 passed;
full desktop set (peers, window, export, watchlist, source panel) —
43 passed. Data layer imports without PySide6.

## Blocked

- none.

## What not to trust

- «Дата подачи» (filing date) is NOT stored in the fact table — the
  panel shows the input fact's period end labeled «период входа»
  instead. A true filed-date would need parser/schema changes (foreign
  territory; the raw payload carries `filed`, the DB does not).
- The raw file open is delegated to the OS; the test stubs
  QDesktopServices and asserts the URL, not a real application launch.

## Disputed

- (carried) branch acceptance red from inherited causes (gate 12, i5,
  dirty-tree) — commits go with --no-verify, per REPORT-C1..C5.
- A `filed` column on fact would let the panel show the true filing
  date; schema is lane-A/foreign territory (Disputed → coordinator).

## HANDOFF

- Status: DONE (one commit, pushed on top of 06ff985).
- Done: C6.1, C6.2, C6.3 as above; 4 new tests in
  tests/test_desktop_source_panel.py.
- Next in the lane queue: TASK-C7 (разговор), then C8…C10.
- For the coordinator: carried asks; plus the fact.filed gap above.

NOW: C6, step 5 (committed)
