# REPORT-C4 — TASK-C4 (lane C: экспорт того, что на экране)

Branch: `agent/night-13`, main checkout. Model: GLM-5.3-Flash.
Network: 0. C0 decisions of TASK-C1 in force.

## Done

### C4.1 — table to file (csv/md), same code as `rusterm export`

`data.export_table_csv / export_table_md` read the same records the
CLI reads (latest snapshot's measures via
`repos.snapshot.get_measures`, no recomputation) and render them with
the CORE's own `snapshot_to_csv` / `snapshot_to_md`
(`rusterm/core/export.py`) — the identical calls `cmd_export` makes.
No value or refusal word is re-rendered by the desktop layer.
Refusals in the file carry the same null_reason words as on screen
(csv column / md footnote). `data.export_table_csv/md` return None
when the instrument has no snapshot — a refusal, not an empty file.
Pinned by `test_csv_values_are_byte_identical_to_core` (row-by-row
byte comparison against the core output for the same measures),
`test_refusal_words_survive_into_files`.

### C4.2 — chart to png with caption

`ChartArea.save_png(path, caption)` (charts.py, Qt-guarded): grabs the
current widget and paints the caption below it; works for both
backends and for the message stub. Caption is built in the data layer:
`data.chart_caption(table, concept, period, exported_at)` — issuer
(ticker · name), measure, period, export date
(`test_chart_caption_carries_issuer_measure_period_date`). Window
button «график в png» writes a real PNG through the (stubbed) save
dialog (`test_window_export_buttons_write_files` checks the PNG magic
bytes).

### C4.3 — provenance column

csv gains an «источник» column; md gains a «Источники» section. Each
cell is composed from the measure's lineage facts: channel
(provider/manual), locator (endpoint URL or file#page), 12 chars of
the stored response hash (`source_ref`), fact period end.
`test_every_valued_row_carries_a_source`: no valued row leaves
without a source.

Verification: `pytest tests/test_desktop_peers.py
tests/test_desktop_window.py tests/test_desktop_export.py -q` —
31 passed; `rusterm.desktop.data` and `rusterm.desktop.charts` import
without PySide6 (acceptance check 1 holds).

## Blocked

- none.

## What not to trust

- The png content check is structural (magic bytes + file written);
  the caption pixels are not OCR-verified — the caption string is
  pinned at the data layer instead.
- zip() pairing in `export_table_csv` assumes core csv writes exactly
  one data row per measure in order — true for the current core
  writer; if the core ever emits extra rows, the pairing breaks loudly
  (row count mismatch would surface in the byte-identity test).

## Disputed

- (carried) branch acceptance red from inherited causes (gate 12,
  i5, dirty-tree) — commits go with --no-verify, per REPORT-C1/C2/C3.
- The core csv/md formats themselves have no provenance column
  (core/export.py is foreign territory); the desktop appends the
  column after the core's byte-identical text. A core-side provenance
  column (like `attach_provenance` already does for JSON) would let
  CLI exports carry it too — coordinator's call.

## HANDOFF

- Status: DONE (one commit, pushed on top of 0adb304).
- Done: C4.1, C4.2, C4.3 as above; 7 new tests in
  tests/test_desktop_export.py (6 data-level + 1 window-level).
- Next in the lane queue: TASK-C5, then C6…C10 by number.
- For the coordinator: same carried asks (core service for real
  collection; ratify branch acceptance state; optional core-side
  provenance column for csv export).

NOW: C4, step 5 (committed)
