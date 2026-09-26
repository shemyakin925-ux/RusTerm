# REPORT-62 — TASK-62, round 78

## Done

- G1. `store.config.set_provider_rate_limit(path, host, per_second)` — the
  config-format door: it splices the TOML, verifies by read-back through
  `load_config`, and refuses a broken existing file with reason
  `config_broken: <parse error>` WITHOUT touching its bytes (registered in
  the B1 allowlist as a config-layer refusal). `data.set_host_rate_limit`
  delegates; `rusterm/desktop/` no longer contains the filename
  `config.toml` anywhere (a test greps it). C9 tests green unmodified.
- G2. `WatchlistRepo.copy_members_except` now takes a string OR a list —
  one door for single and bulk removal. `data.remove_instruments` calls it
  instead of its add_member loop; the CLI's single-remove path calls the
  same door. Semantics pinned by tests: bulk 3-of-5 → one new version,
  members = 2, exactly one `watchlist_bulk_remove` audit row; the old
  single path (desktop and CLI) unchanged — one version, one
  `watchlist_remove` row.
- G3. `data.source_cell(facts, shape=...)` is the single source-string
  implementation; `actions._source_cell` delegates with shape="export"
  (compact `kind:sha12@period`), the export table column uses
  shape="table" (`kind where #sha12 period`). The chart caption names no
  document/hash — the "no room for it" note is in both captions'
  docstrings, and the test asserts the sha is absent from the caption.
  A test proves table, panel, and compact export name the same document
  (the cell's 12-hex is a prefix of the panel's), the same period, and
  that both shapes come from one function.
- Verified: `pytest tests/test_task62_g1_config_door.py tests/test_task62_
  g2_removal_door.py tests/test_task62_g3_source_cell.py tests/test_b1_
  reasons.py tests/test_desktop_settings.py tests/test_desktop_watchlist.py
  tests/test_desktop_data.py tests/test_desktop_quality.py tests/
  test_j1_display.py tests/test_task60_e5_window_vs_cli.py tests/test_cli.py
  -q` → 92 passed.

## Blocked

## What not to trust

- G1's broken-file refusal is tested at the door level; the window's
  warning-box rendering of the reason is unchanged C9 behavior.

## Disputed

## HANDOFF

Status: PARTIAL (G1-G3 done; G4-G5 ahead)
Arrival state: task taken round 78 on d026daa, selfcheck green
Items done: G1, G2, G3
Items not done: G4 HANDOFF guard strengthening, G5 B38/PROTOCOL line
Acceptance: hook verdict on this commit (see commit body)
Tests: 92 passed in the eleven suites listed above
Guards: none touched yet (G4 strengthens test_report_sections)
Schema: unchanged
Network: 0 requests
Model: GLM-5.3, app llm_calls 0
Secrets: nothing to grep this commit
Pushed: this commit pushes immediately
Questions for the coordinator:
1. None so far.

NOW: G4, step 1

## HANDOFF (FINAL — supersedes the interim above)

Status: DONE
Arrival state: task taken round 78 on d026daa, selfcheck green
Items done: G1-G3 (ed71383), G4-G5 (0d7c6f0)
Items not done: none
Acceptance: «Итог: пройдено 13, провалено 0» on every commit's hook
(ED71383's hook covered G1-G3's 92 targeted tests; 0d7c6f0's the
guard suite)
Tests: 92 passed (G1-G3 suites), 7 passed (report guard), volume and
degree suites green
Guards: test_report_sections strengthened — the last HANDOFF may not
call an item undone while its commit exists in the same round; red
demonstrated on the literal round-76 lie, then REPORT-61 closed with
the final section
Schema: unchanged
Network: 0 requests
Model: GLM-5.3, app llm_calls 0
Secrets: no key material in this report
Pushed: yes through 0d7c6f0; this commit pushes immediately
Questions for the coordinator:
1. B38 закрыта коммитом 0d7c6f0 (строка соглашения в PROTOCOL §5) —
   BACKLOG-правка за вами, как договорились.
2. Что взял бы следующим: общий запрет синтетики на не-демо
   инструмент в cmd_ingest (F4 починил только KR; дефолтная
   синтетика всё ещё молча собирает демо-факты на любом другом
   не-демо инструменте).

NOW: G5, step 2 — task complete, handing the baton back
