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
- **S1.** Every control is pressed by a test (Qt offscreen), each
  with an observable result. Inventory (control → press test →
  observable):

  | Control | Press test | Observable result |
  |---|---|---|
  | search (field) | test_search_filters_live_and_counts | counter text «совпадений: N» |
  | watchlist_box | test_s1_watchlist_box_switch_reloads_members | companies counter + label switch |
  | watchlist_add_button | test_s1_watchlist_add_button_press_adds_paper | companies 4→5, label v2 |
  | watchlist_remove_button | test_s1_watchlist_remove_button_press_removes_selected | companies 4→3 |
  | watchlist_clear_button | test_s1_watchlist_clear_button_press_asks_and_clears | confirm asked, companies 4→0 |
  | tree (selection) | test_expansion_survives_selection_and_search | header/table loaded |
  | table (cell click) | test_cell_click_opens_source_panel_with_reason | panel shows reason |
  | stale_button | test_stale_inputs_collapse_and_expand_on_click | panel expands/collapses |
  | kind_box | test_chart_kind_switches_without_restart | chart message changes |
  | measure_box | test_s1_measure_switch_press_changes_chart | live chart ↔ «нет данных» |
  | industry_measure_box | test_s1_industry_measure_switch_changes_chart | live box-plot ↔ refusal words |
  | export_csv_button | test_s1_export_buttons_write_files | csv file with values |
  | export_md_button | test_s1_export_buttons_write_files | md file with values |
  | save_png_button | test_s1_save_png_button_writes_file | non-empty png |
  | open_raw_button | test_window_open_raw_button_opens_existing_file | raw file opened |
  | collect_button | test_collect_refuses_non_demo_with_cli_words + test_collect_runs_pipeline_and_refreshes_window | status words / pipeline refresh |
  | cancel_button | test_collect_cancel_button_wires_flag | cancel flag set, «отмена…» |
  | question_line | test_chat_without_key_speaks_reason_in_placeholder | reason words in answer |
  | chat_sessions_box | test_s1_chat_sessions_box_honest_empty | honest «ждёт двери list_sessions», no counters change |
  | switch_root_button | test_s1_switch_root_press_cancel_words | «смена каталога отменена — ничего не создано», no dir created |
  | tabs | test_s1_tabs_switch_shows_industry | industry tab shows peer set |

  Findings named (S1 rule) and fixed in this round:
  1. industry box chart crashed on live data (`TypeError: str - str`
     in `_PyqtgraphView`): the core returns quartiles as `repr()`
     strings (ТЗ-22 J7), the desktop spec passed them through raw;
     `industry_chart_spec` now converts to float. Caught exactly
     because the press test drives the live path, not an invented
     dict (the old data-level test fed floats by hand).
  2. `watchlist_add/clear/remove` silently did nothing when no list
     exists — fixed together with S4 (warning with the ready
     `rusterm watchlist create` command).
  3. The add-dialog failure path opens a REAL modal
     `QMessageBox.warning`; in offscreen tests an unresolved ticker
     hung the run for minutes (measured: 25s+ sample showed
     `QDialog::exec`). Not changed — tests patch the dialog; noted
     for any future headless runs.

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

## HANDOFF

Status: PARTIAL (V1, Д2, Д4, S1, S2 done; S4, S5, V3 pending)
Items done: V1, Д2, Д4, S1 (press tests), S2
Items not done: S4, S5, V3 — in progress this shift
Acceptance: selfcheck run before S2 commit
Tests: window file 35 passed (11 S1 presses + S2)
Pushed: yes (through S2 commit)

NOW: S4, step 0

## HANDOFF (FINAL — supersedes the interim values above)

Status: PARTIAL (V1, Д2, Д4, S1, S2 done; S4, S5, V3 continue this shift)
Arrival state: selfcheck exit 0, acceptance 13/0, pytest 972p/3s/4x
Items done: V1, Д2, Д4, S1, S2
Items not done: the remaining V2 work and the V3 guard — in progress
Acceptance: «Итог: пройдено 13, провалено 0» at V1 and Д4 commits;
  two hook rejections during the shift are quoted in Done (Д4) and
  were repaired, not waived
Tests: window file 35 passed; desktop files 49 passed at Д4; full
  suite green at V1 (975p/3s/4x)
Guards: none touched (no assert removed; new asserts added only)
Schema: unchanged
Network: 0 requests used of 0 budget
Model: app llm_calls 0 of 0; executor model GLM-5.3-Flash
Secrets: not applicable; `env | grep -c RUSTERM` = 0
Pushed: yes (1154307, 06e390e, 3f4c366, 4621122, d8134eb, and this commit)
Questions for the coordinator:
1. History keyed by snapshot as_of year (kept) vs measure period year —
   see Disputed; say the word and it becomes an item.
2. `_handoff_section` merges every interim HANDOFF into one section
   (setdefault on the same header), so «last supersedes» only works
   via the FINAL suffix — interim blocks naming future work red G4
   once that work lands. This report works around it with a FINAL
   block; a guard fix belongs to the coordinator.

NOW: S4, step 0

- **S5 (частично; Verizon — Blocked, см. ниже).** The thin-source
  case (Kaspi/Vale class) now speaks: `measure_summary` +
  `measure_summary_line` in tui/model.py — one door for both faces
  (pairs of value/null_reason from the card or raw measures). Rule:
  valued measures < a quarter of the card → the summary names the
  count and the dominant FIRST TOKEN of the dictionary refusals (no
  invented reason). The window shows it in the panel above the table;
  `rusterm export` prints it to stderr before the untouched table.
  Rule threshold is my call, reasoned: Kaspi 4/28 and Vale 6/28 are
  under 25%, AAPL 15/27 (56%) is not; VZ 7/28 sits exactly on the
  line and stays a table until the VZ fix lands.
  - Red before the fix:
    `FAILED tests/test_desktop_data.py::test_thin_source_summary_in_table_and_words`
    (KeyError 'summary');
    `FAILED tests/test_cli.py::test_export_of_thin_source_says_words`
    (no words in stderr). After: both green; full suite 998p/2s/4x
    with the one report-guard issue quoted in Disputed (L3).
  - **Verizon cascade — SKIPPED/BLOCKED, not faked** (PROTOCOL §11):
    matching the shares tag requires the VZ companyfacts payload
    ("тег найден в payload"); there is no VZ fixture under
    tests/data/, the round budget is network 0, and the user's
    five-paper base no longer exists (measured:
    `SELECT instrument_id FROM instrument` → only US-AAPL).
    Guessing a look-alike tag is forbidden by the Z1 rule.
  - «Было → стало» for the five papers — measured on today's base:

    | Paper | TASK-72 (round 98) | Today |
    |---|---|---|
    | AAPL | 20 of 28 | 15 of 27 (base rebuilt since; summary off) |
    | ADBE | 20 of 28 | absent from base |
    | VZ | 7 of 28 | absent from base (fix blocked) |
    | VALE | 6 of 28 | absent from base (summary now fires at <25%) |
    | KSPI | 0 of 28 | absent from base (summary now fires at <25%) |

## HANDOFF (FINAL 2 — supersedes every block above)

Status: PARTIAL (V1, Д2, Д4, S1, S2, S4, S5-partial done; VZ part of S5 blocked, V3 pending)
Arrival state: selfcheck exit 0, acceptance 13/0, pytest 972p/3s/4x
Items done: V1, Д2, Д4, S1, S2, S4, S5 (thin-source part)
Items not done: the Verizon tag fix (blocked, quoted in Done; belongs to the thin-source item) and the V3 guard — next this shift
Acceptance: «Итог: пройдено 13, провалено 0» at V1/Д4; hook rejections during the shift are quoted in Done and were repaired, not waived
Tests: full suite 998 passed, 2 skipped, 4 xfailed after S5 code (one report-guard red quoted in Disputed — L3 parser, passes at commit time via the staged-report fallback)
Guards: none touched (no assert removed)
Schema: unchanged
Network: 0 requests used of 0 budget
Model: app llm_calls 0 of 0; executor model GLM-5.3-Flash
Secrets: not applicable; `env | grep -c RUSTERM` = 0
Pushed: yes (1154307, 06e390e, 3f4c366, 4621122, d8134eb, ebc7dc1, fcc2662, 0a53190, and this commit)
Questions for the coordinator:
1. History keyed by snapshot as_of year (kept) vs measure period year — see Disputed.
2. `_handoff_section` merges all interim HANDOFFs (setdefault), so only the FINAL suffix decides; interim blocks naming future work red G4 once it lands. This report carries a FINAL block; a guard fix is yours.
3. L3 (`test_done_items_have_code_commits_in_round`) parses
   `git log --format="%h %s" --name-only` assuming a blank line
   between the subject and its file list; git puts the blank AFTER
   the subject, so subject blocks never match files and the guard
   only ever passes via the staged-report fallback (L2) — i.e. it
   verifies nothing in normal runs. Reproduced in REPORT-75; a guard
   fix is yours.

NOW: V3, step 0

## HANDOFF (FINAL 3 — the shift is stopped by the user's order)

Status: PARTIAL — shift stopped on the user's order ("finish the item, report, stop")
Arrival state: selfcheck exit 0, acceptance 13/0, pytest 972p/3s/4x
Items done: V1, Д2, Д4, S1, S2, S4, S5 (thin-source part)
Items not done: the Verizon tag fix (blocked, see Done) and the V3 guard — for the next round
Acceptance: «Итог: пройдено 13, провалено 0» at commits V1/Д4 and before this
  hand; on the CLEAN tree acceptance is now 11/13 — see Disputed (L3 parser):
  the same guard passes at every commit-time hook via the staged-report
  fallback and reds only on a clean tree
Tests: full suite 998 passed, 2 skipped, 4 xfailed (S5 code); every item's
  own run is quoted above
Guards: none touched (no assert removed; guard defects are in Disputed for
  the coordinator, per «спорное — в отчёт, не в код»)
Schema: unchanged
Network: 0 requests used of 0 budget (DART key question untouched: `env |
  grep -c RUSTERM` = 0)
Model: app llm_calls 0 of 0; executor model GLM-5.3-Flash
Secrets: not applicable; no key artifacts touched
Pushed: yes (1154307, 06e390e, 3f4c366, 4621122, d8134eb, ebc7dc1, fcc2662,
  0a53190, b667939, and this commit)
Relay: `hand` REFUSED (exit 5) — «приёмка на дереве красная» — because of
  the L3 clean-tree red quoted above, not because of shift work. A repeat
  is futile until the coordinator fixes or adjusts the L3 parser; the baton
  stays with the executor deliberately, and STATE.json is left at
  "awaiting_review".
Questions for the coordinator:
1. History keyed by snapshot as_of year (kept) vs measure period year — see Disputed.
2. `_handoff_section` merges all interim HANDOFF blocks (setdefault on the
   same header); only a UNIQUE FINAL suffix decides. Interim blocks naming
   future work red G4 once that work lands under a named commit.
3. L3 (`test_done_items_have_code_commits_in_round`) parses
   `git log --format="%h %s" --name-only` assuming a blank line between a
   subject and its file list; git puts the blank AFTER the subject, so
   subject blocks never contain files and nothing ever matches — the guard
   only passes via the staged fallback (L2) or skips on Cyrillic-only ids.
   TASK-75's latin ids (V1, S1...) are the first to trigger it on a clean
   tree. Reproduction: clean clone of agent/night-11 at this commit, run
   `bash agent/acceptance.sh` → 11/13 with only this test red, twice.

NOW: stopped by user order
