# REPORT-61 — TASK-61, round 76

## Done

- F1. Full pass over `rusterm/desktop/` (2704 lines: data 954, window
  1007, actions 328, charts 353, two entries). Audit table:

| Where | What it does | Verdict |
|---|---|---|
| data.header_info | summed today's provider_requests_used samples with a local-midnight filter | computed — moved to `MetricsRepo.requests_used_today()`; header_info and budget_view read one number from one store door |
| data.measure_coverage | counted green measures and reason tokens — a second copy of the count `rusterm coverage --json` also had inline | computed — one counter moved to `tui_model.measure_reason_counts`; desktop and coverage --json now call it (cli's inline copy switched too) |
| data.format_value | 4-decimal cell display | display — rule pinned by test: third decimal preserved on 0.0012345, full precision only in export |
| data._series_spec / _box_spec / _radar_spec / radar_vs_group_spec / industry_chart_spec | chart shaping from core/model values: None gaps, excluded counters, float() for plots | display |
| data.staleness_mark | staleness mark; threshold imported from core (`_STALE_LOOKBACK_DAYS`), text is display | display |
| data.peer_screen | words assembled from `peers_core.evaluate` and core constants, not copied thresholds | display |
| window._number_item, charts.* | float() for sort roles and plot geometry (radar scale = max of plotted values) | display |
| actions.collect_synthetic | same IngestionPipeline/SnapshotBuilder as cmd_ingest/cmd_snapshot; real sources locked in CLI (accepted Disputed of C2, commands named in CLI_LOCKED_SOURCES) | unchanged |
| data.export_* / actions.export_snapshot_* | core `snapshot_to_csv/md/json` byte-for-byte, source column appended from lineage | display |

- New tests, `tests/test_task61_f1_desktop_rules.py`: (1) the vocabulary
  walk over rusterm/desktop/ with the B1 scanner — every reason-position
  token must be in NULL_REASONS or the allowlist; the red case is
  demonstrated on a made-up desktop reason (mechanics, not a list of
  five); (2) the rounding test — cell == format_value, float(cell) ==
  round(float(v), 4), third decimal preserved, full precision
  byte-for-byte in export.
- Verified: `pytest tests/test_b1_reasons.py tests/test_desktop_market_
  degree.py tests/test_task60_e5_window_vs_cli.py tests/test_task61_f1_
  desktop_rules.py tests/test_desktop_data.py tests/test_desktop_quality.py
  tests/test_j1_display.py tests/test_cli.py -q` → 78 passed.

## Blocked

## What not to trust

- The audit read every desktop file, but "display" verdicts rest on the
  docstrings and the imported-core spot checks named in the table, not on
  a formal proof; the two moved computations are covered by the suites
  listed above.

## Disputed

- `data.set_host_rate_limit` edits config.toml by text surgery because
  the store offers no setter; the write is verified by read-back through
  `load_config` (C9 tests). A store-side `set_provider_rate_limit` would
  be the core's move — coordinator item.
- `data.remove_instruments` (bulk case) rebuilds the version with an
  add_member loop; the repo's `copy_members_except` covers only the
  single-instrument case. Semantics equal, C5 tests pin the audit rows.
  Unifying = coordinator item.
- Two display-string implementations exist inside the desktop layer
  (`_source_cell` and `chart_caption` in data.py and actions.py, different
  shapes for different surfaces). Display duplication, not computation;
  consolidation = coordinator item.

## HANDOFF

Status: PARTIAL (F1 done; F2-F4 ahead)
Arrival state: task taken round 76 on 008aded, selfcheck green
Items done: F1
Items not done: F2 three-face cross-check, F3 window at volume, F4 KR door
Acceptance: hook verdict on this commit (see commit body)
Tests: 78 passed in the eight suites listed above
Guards: none touched; new desktop vocabulary walk added
Schema: unchanged
Network: 0 requests
Model: GLM-5.3, app llm_calls 0
Secrets: nothing to grep this commit
Pushed: this commit pushes immediately
Questions for the coordinator:
1. The three Disputed rows above — confirm "coordinator item" or accept
   as permanent display-layer behavior.

NOW: F1, step 8

- F2. Three faces on one catalog, three markets (US-A7, CA-C7, BR-B7):
  `tests/test_task61_f2_three_faces.py` compares, per measure and period,
  (1) the real `rusterm export --format json` subprocess, (2)
  `tui_model.card_rows`, (3) `desktop_data.measure_table_rows`. Concept
  lists must be identical across the three (no silent omissions — an
  omission reds with all three lists named); model == export
  byte-for-byte; the desktop cell equals the export or exactly its
  format_value (the F1-pinned display rule); refusals are recognised by
  one token (`missing_data`) in all three faces, the model shows «—» and
  the window «нет данных». Verified: `pytest tests/test_task61_f2_three_
  faces.py -q` → 2 passed.
