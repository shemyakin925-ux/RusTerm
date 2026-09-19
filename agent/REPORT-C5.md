# REPORT-C5 — watchlists: switch, edit as new versions, confirm bulk

- **Task:** `agent/TASK-C5.md`
- **Branch note (user's call):** this task was implemented in the
  isolated worktree `.wt-exec2` on branch `agent/night-13-exec2`
  (user chose "option 3": one worktree per executor after the live
  collision on C4 in the shared tree). Merge to `agent/night-13` is
  the coordinator's per lane rule; before pushing I rebase on
  `agent/night-13` and re-run everything.

## Done

- C5.1 lists visible and switchable: left column gained the list
  combo (name + current version), the line «версия N · участников M»
  and switching reloads the company tree for that list
  (`test_watchlist_switch_changes_sidebar`: empty second list empties
  the sidebar and back). Overview comes from the same
  `list_watchlists` door as `rusterm watchlist list`.
- C5.2 edit through the core: «Добавить» resolves the ticker through
  the same resolver as CLI
  (`resolve_ticker_candidates`; ambiguous/unknown → words), then
  follows the exact CLI add sequence (new full-composition version →
  add_member → audit row); «Убрать из списка» follows the CLI remove
  sequence (new version + `copy_members_except` → audit). Every edit
  bumps the version, older versions stay readable; the version combo
  lists known versions with their actions
  (`test_add_creates_new_version_and_audit`,
  `test_remove_creates_version_without_instrument`,
  window `test_remove_then_add_same_ticker_bumps_versions` — the
  add/remove round trip, audit rows counted).
- C5.2 rollback test: remove AAA then roll back to v1 — `rollback_to`
  creates v3 with the old composition, v1/v2 remain, audit row
  `watchlist_rollback` with confirmed=1
  (`test_remove_then_rollback_restores_previous_version`).
- C5.3 bulk confirmation: rollback (affects the whole list) asks for
  confirmation via a modal question; «no» does nothing, «yes» calls
  the same `rollback_to` + audit with confirmed=1
  (`test_rollback_requires_confirmation`). Single-instrument
  add/remove need no confirmation — same as CLI.
- Tests: `tests/test_desktop_watchlist.py` (6, Qt-free; audit rows
  read from `audit_log` directly — tests may use SQL, the acceptance
  restricts `rusterm/` only), 4 window additions.

## Blocked

- none.

## What not to trust

- Fixture venues changed XNAS → NASDAQ in two test files: the ticker
  resolver checks the venue against the market registry
  (`venue_in_market`, TASK-18 G1/G2) and XNAS is not a registered
  prefix — real CLI seeds use NASDAQ/NYSE strings.
- Window writes (add/remove/rollback) run synchronously in the UI
  thread — local sqlite ops, no network; same tradeoff as the chat
  question (noted in REPORT-C1).
- `_confirm_bulk` uses QMessageBox.question; tests monkeypatch it —
  the modal itself is not exercised offscreen.

## Disputed

- DISPUTED: add/remove helpers reuse the CLI private helper
  `_next_version_full_composition` (imported from
  `rusterm/cli/__init__.py`) — no copy, but it imports the CLI module
  into the desktop; if the coordinator wants, moving it to a core
  service would make the dependency cleaner (same ask as REPORT-C2
  about ingest bodies).
- DISPUTED: rollback confirmation is a modal; there is no audit row
  for a REFUSED confirmation (CLI has none either — nothing happened).

## HANDOFF

- Status: DONE (commit on `agent/night-13-exec2`, pushed).
- Next: TASK-C6 (source panel), C7…C10 by number.
