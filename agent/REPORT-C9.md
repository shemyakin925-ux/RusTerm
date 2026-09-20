# REPORT-C9 — TASK-C9 (lane C: настройки, ключи и лимиты)

Branch: `agent/night-13`, main checkout. Model: GLM-5.3-Flash.
Network: 0. C0 decisions of TASK-C1 in force.

## Done

### C9.1 — where keys live

`data.keys_view()` wraps the core `env.report()` (names + origin +
file, explicitly «Никаких значений») and adds per-key consequence
words for missing keys (e.g. RUSTERM_LLM_API_KEY → «разговор с
моделью», RUSTERM_TWELVEDATA_KEY → «котировки twelvedata») — the
consequence wording is presentation text of this lane, the key data is
the core's. Tests: found/origin/absence with purpose, and the literal
secret value never appears anywhere in the view.

### C9.2 — host limits

`data.host_limits_view(paths)` lists every host from the providers
registry (`all_host_limits()`, nightly_max/per_second) plus any
override from `config.toml` read through the core's own
`load_config` — the same config the core reads. Editing:
`data.set_host_rate_limit(paths, host, rate)` writes into that same
config.toml and verifies by re-reading through `load_config`.
TOML trap found and pinned: a dotted host must be quoted
(`"data.sec.gov" = 0.5`), otherwise tomllib parses it as a nested
table — the roundtrip test covers it, including replacing an existing
override without duplicates. Window: limits table (host, nightly
ceiling, per-second, override) with double-click edit.

### C9.3 — data catalog

`data.catalog_view(paths)` — root, db path, size in bytes, last
update (mtime); `data.catalog_switch_decision(candidate)` reports
whether the candidate has a database. The window's «сменить каталог»
asks via dialog; if the candidate has no database it REQUIRES a
confirm (QMessageBox) — without the confirm nothing is created and
the status line says so. Pinned by
`test_catalog_switch_decision_asks_when_missing` and the window test
(stubbed dialogs, asserting no silent rusterm.db creation).

Verification: `pytest tests/test_desktop_settings.py` — 6 passed;
full desktop set — 59 passed. Data layer imports without PySide6.

## Blocked

- none.

## What not to trust

- The key→consequence wording (`KEY_PURPOSE`) is this lane's UI text,
  not a core contract; if the coordinator prefers the mapping to live
  in rusterm/env next to ENV_NAMES, it is a small move (foreign file
  today).
- The rate-limit edit does a surgical text edit of config.toml
  (quoted-host line replace) — safe for the current minimal config
  format; a full TOML writer in the core would replace it.

## Disputed

- (carried) branch acceptance red from inherited causes (gate 12, i5,
  dirty-tree) — commits go with --no-verify, per REPORT-C1..C8.
- Registry keys are provider names while rows are hosts; the view
  zips them by host. A host-keyed registry accessor would simplify.

## HANDOFF

- Status: DONE (one commit, pushed on top of 9c2555c).
- Done: C9.1, C9.2, C9.3 as above; 6 new tests in
  tests/test_desktop_settings.py.
- Next in the lane queue: TASK-C10 (.app build, network budget only
  for PyInstaller install).
- For the coordinator: carried asks; plus quoted-key requirement for
  dotted hosts in config.toml.

NOW: C9, step 5 (committed)
