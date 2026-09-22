# REPORT-75 — TASK-75, round 100

**Divergence from the chat brief, first line as instructed:** the brief
ordered TASK-60 E1 first and quoted a red baseline ("11/2", "4 failed,
910 passed"). That state is ~13 relay rounds stale: TASK-60…TASK-72 are
accepted (CONTEXT.md, updated after round 75), REPORT-60..REPORT-72
exist, and the baton (round 100) names TASK-75 as the executor's task.
Per PROTOCOL §12 ("BATON.json names whose turn it is") and the brief's
own fallback rule, this shift executes **TASK-75**; the divergence is
recorded here instead of re-doing accepted work. Measured on arrival:
`selfcheck` exit 0, acceptance «Итог: пройдено 13, провалено 0»,
pytest 972 passed / 3 skipped / 4 xfailed / 0 failed.

## Done

- **Arrival state (before any change).** `bash agent/selfcheck.sh` →
  exit 0, `Итог: пройдено 13, провалено 0`, `SELFCHECK OK`;
  `python3 -m pytest -q` → 972 passed, 3 skipped, 4 xfailed (exit 0).
- **V1.** History now reaches the screen:
  - `measure_history_by_year` (tui/model.py) walks ALL snapshots of the
    instrument via the new `SnapshotRepo.snapshots_of_instrument`;
    the old code used `latest_per_instrument()` — one snapshot per
    instrument, so more than one year was impossible and the docstring
    ("из ВСЕХ сохранённых снапшотов") lied;
  - `measure_table_rows` (desktop/data.py) reads the year cell as
    `history[year][concept]`; the shape `{год: {концепт: значение}}` is
    now named identically in the docstrings of both sides;
  - dead branch `point["value"]` (written against an imagined
    `{мера: {год: точка}}` shape) replaced by direct `format_value(point)`;
  - empty-column rule (ТЗ-72 Д1): no measure has history → no year
    columns (`years == []`), and `suggestion` carries the one-action
    executable line `rusterm snapshot --instrument <id>`; the window
    shows it in the source panel under the table.
  - **Red before the fix** (required by V1), same three tests:
    `FAILED tests/test_desktop_data.py::test_history_cells_carry_snapshotted_values`
    (KeyError '2024' — cell dict did not hold the year),
    `FAILED tests/test_desktop_data.py::test_no_history_no_year_columns_and_command_offered`,
    `FAILED tests/test_desktop_window.py::test_company_without_snapshot_is_offered_one_action_series`
    (`assert 8 == 2` — six empty year columns drawn).
  - **After the fix:** `python3 -m pytest -q` → 975 passed, 3 skipped,
    4 xfailed (exit 0); `bash agent/selfcheck.sh` → exit 0,
    `Итог: пройдено 13, провалено 0`.
  - **Cells filled on the live base** (`~/.rusterm`, `RUSTERM_DATA`
    unset; read-only probe `data.open_readonly(default_root())`):
    AAPL **15 of 108** year cells filled, 4 year columns;
    ADBE **0 of 0** — instrument absent from the base, window shows the
    suggestion line; MSFT **0 of 0** — same. The five-instrument base
    from the TASK-72 S0 ulika no longer exists: `SELECT instrument_id
    FROM instrument` returns only `US-AAPL` (3 snapshots, as_of
    2026-09-15), so the MSFT/ADBE counts from the baton note are not
    reproducible on this machine today.

- **Д2.** The watchlist label no longer lies: `repaint_watchlists`
  syncs box/state/label — when the requested id is absent from the
  list of choices, the first list is shown and the label describes
  THAT list; «списков нет» appears only when there are truly no
  watchlists. Startup re-reads the sidebar after the sync, so the
  visible list and the left column are about the same list.
  - Red before the fix (quote):
    `FAILED tests/test_desktop_window.py::test_watchlist_label_agrees_on_stale_id`
    — `'списков нет' is contained here: списков нет`;
    `FAILED tests/test_desktop_window.py::test_watchlist_window_start_without_id_is_honest`.
  - After: `tests/test_desktop_window.py` → 22 passed (exit 0);
    commit 06e390e, selfcheck OK.



- **Д4.** The source panel leads with the essentials (concept,
  value, unit, reason, document+hash+period) and collapses the
  stale-input wall into one line «устаревших входов: N, самый свежий
  X»; the full list expands on demand via a dedicated button (and
  stale_detail=True in the data layer).
  - Red before the fix (quote):
    `FAILED tests/test_desktop_data.py::test_source_panel_collapses_stale_inputs`
    — the panel carried 25+ per-entry «устаревший (последний
    2009-12-31, anchor 2024-12-31)» lines and the line-count assert
    read `28 <= 12`.
  - First commit attempt was rejected by the hook:
    test_refusal_panel_names_missing_concept hit KeyError 'current' on
    the partial row built by the test helper; the value read is now
    robust (fallback to format_value of the measure dict), the test's
    asserts themselves unchanged.
  - After: the three desktop test files → 49 passed (exit 0),
    including the button click/expand/collapse round-trip on a
    25-stale-input base.
## Blocked

## What not to trust

- V2 (Д2, Д4, S1, S2, S4, S5) and V3 are not started at this commit.
- The AAPL 15/108 number depends on the live base, which the user
  rebuilds; it is a measurement, not an invariant. The invariant lives
  in `test_history_cells_carry_snapshotted_values` (synthetic base,
  tmp_path).

## Disputed

- Chat brief says `updated_at` берётся из `TZ=Asia/Bangkok date`; the
  machine is +07, and selfcheck O0 compares `updated_at` to real UTC
  (±15 min) — a +07 wall clock stamped "Z" would red O0 by +420 min.
  Using `date -u +%Y-%m-%dT%H:%M:%SZ` (same real clock, correct zone).
- History year = snapshot `as_of[:4]` (kept from the accepted ТЗ-72 Д1
  mechanic). A snapshot rebuilt today carries today's year, so year
  columns anchor on measure periods while history keys on run years;
  on the live AAPL base they align (15/108 filled). If the coordinator
  wants period-keyed history instead, that is a semantics change of the
  shared TUI function — left out of V1 on purpose.

## HANDOFF

Status: PARTIAL (V1 done, V2/V3 pending — shift continues)
Arrival state: selfcheck exit 0, acceptance 13/0, pytest 972p/3s/4x
Items done: V1
Items not done: V2 (Д2, Д4, S1, S2, S4, S5), V3 — in progress this shift
Acceptance: «Итог: пройдено 13, провалено 0», exit 0 (before and after V1)
Tests: 975 passed, 3 skipped, 4 xfailed
Guards: none touched (no assert removed; new asserts added only)
Schema: unchanged
Network: 0 requests used of 0 budget
Model: app llm_calls 0 of 0; executor model GLM-5.3-Flash
Secrets: not applicable (no key artifacts touched); `env | grep -c RUSTERM` = 0
Pushed: yes
Questions for the coordinator:
1. History keyed by snapshot as_of year (kept) vs measure period year —
   see Disputed; say the word and it becomes an item.

NOW: V1, step 8

## HANDOFF

Status: PARTIAL (V1, Д2, Д4 done; S1, S2, S4, S5, V3 pending)
Items done: V1, Д2, Д4
Items not done: S1, S2, S4, S5, V3 — in progress this shift
Acceptance: selfcheck OK (13/0) on the Д4 commit
Tests: three desktop test files 49 passed; suite green at V1 (975p/3s/4x)
Pushed: yes (1154307, 06e390e, 3f4c366, and this commit)

NOW: S1, step 0
