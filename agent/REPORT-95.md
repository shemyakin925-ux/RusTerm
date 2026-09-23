# REPORT-95 — ТЗ-95, круг 113

Branch `agent/night-11`, head on arrival `242656a`, baton `agent/TASK-95.md`.
English per AGENTS.md; command output quoted as it came out. Budgets: network
0 used (PyInstaller was already installed), LLM calls 0.

## F0 — the coordinator's verdict, read before any code

B0/B1/B2 of ТЗ-81 accepted; **B3 returned**: nobody double-clicked the app.
Taken as the premise of this round, not argued with. The three sub-verdicts
(transcript circle from the live relay, the B1 wording caveat, the single-date
"снапшот от" form) are noted; F3 of this task covers the year-gap line the
verdict asked for. User bases (`~/equitylab`, `~/.rusterm`) were opened
read-only in this round and are not written to — see "Runs".

## Arrival state (measured before the first source edit)

Reproduced the coordinator's finding on my own machine, without touching the
user's catalogs: two sandbox catalogs under `/tmp/f2-probe`, built by
`apply_migrations` (schema 45) and by the same migrations with `_SCHEMA_VERSION`
pinned to 44 (schema 44, no `chat_transcript`, 1 instrument).

`python3 -m PyInstaller EquityLab.spec --noconfirm` → `Build complete!` in
19.6 s, `167M dist/EquityLab.app`.

1. Finder-equivalent launch (`open -n`, process must live), 5 s check:

   ```
   current: alive after 5s = 1 ['25763']
   schema44: alive after 5s = 0 []
   ```

2. Same bundle, direct binary, offscreen + `RUSTERM_APP_SMOKE=1`, sandbox HOME:

   ```
   === current ===
   rc 0
   rusterm-app root=/private/tmp/f2-probe/current (правило: 1)

   === schema44 ===
   rc 1
     File "rusterm/desktop/window.py", line 1002, in _build_window
       repaint_chat_usage()
     File "rusterm/desktop/data.py", line 913, in llm_usage_line
       totals = repos.chat_transcript.calls_totals()
     File "rusterm/store/repos.py", line 2164, in calls_totals
   sqlite3.OperationalError: no such table: chat_transcript
   [PYI-25711:ERROR] Failed to execute script 'app_entry' due to
   unhandled exception: no such table: chat_transcript
   ```

   Nothing is printed by the app itself, so a double-click looks like "nothing
   happens" — exactly what the user reported.

## Done

### F1 — старая схема: слова, а не падение

**Строка словами, а не падение.** `data.header_info` gained one key,
`schema_notice`: on a base whose applied schema is older than the program's, it
returns a single line; on a current base, `None` (the line is about the gap, not
a permanent caption). The window renders it in a `QLabel` under the header
(`objectName="schema_notice"`), shown only when there is something to say.

Measured on a schema-44 copy of `tests/data/upgrade/schema44.sqlite.gz`:

```
база в /private/var/folders/.../stale — схема 44, программе нужна 45;
обновите: rusterm --root /private/var/folders/.../stale init
```

The command is printed with an explicit `--root`, because the window opened the
catalog by one of the four rules of ТЗ-90 A5 — telling the user to run a bare
`rusterm init` would have migrated a *different* base than the one on screen.
The path goes through `shlex.quote`, and the tail is parsed by
`_build_parser()` in a test (`parsed.root`, `parsed.command == "init"`), then
actually executed: the schema reaches 45 and the line disappears.

**Window still does not migrate** (ADR-0023): a test builds the window on the
stale copy and asserts `current_schema_version` is still 44 afterwards.

**Ни одна стартовая дверь не бросает.** Two doors raised on the stale base and
now answer with words — `chat_sessions` → `[]`, `llm_usage_line` → `"вызовы: —"`
— guarded by a new store door `db.has_table(conn, name)` (SQL stays in
`rusterm/store/`, acceptance check 7). The rest never needed a change.

The startup door list is not copied by hand: `data.*` functions are wrapped at
runtime, the window is built, and whatever actually ran is what the test names.
Measured run on the stale fixture (`errors: []`):

```
doors: catalog_view, channel_degrees, chat_sessions, chat_unavailable_reason,
       current_schema_version*, expanded_sectors, has_table*, header_info,
       host_limits_view, keys_view, llm_usage_line, matches_query, sector_tree,
       sidebar_companies, watchlist_choices
```

`*` — store names re-exported in the `data` namespace, wrapped along with the
doors. Of these, the two that used to die are `chat_sessions` and
`llm_usage_line`. Not reached on this fixture (a base with no watchlists or no
instruments at all instead): `all_instruments`, `empty_base_message`,
`empty_base_instruments_message`.

**Test** `tests/test_desktop_f1_stale_schema.py` — 9 cases: the exact line, a
current base silent (label empty and hidden), window builds on the stale base
with the line visible and the sidebar showing the instrument, no migration by
the window, the instrumented no-raise sweep, the named command parses and
updates, and both transcript doors still read real rows *after* the update (so
the guard did not become a permanent dash).

Red on the pre-fix tree, quoted as the task asked (the run was `-q` on top of
`addopts -q`, so pytest printed the nine `FAILED …` lines and no totals line):

```
E       sqlite3.OperationalError: no such table: chat_transcript
...
FAILED tests/test_desktop_f1_stale_schema.py::test_the_notice_names_the_catalog_both_versions_and_the_command
FAILED tests/test_desktop_f1_stale_schema.py::test_a_current_base_has_nothing_to_say
FAILED tests/test_desktop_f1_stale_schema.py::test_the_window_builds_on_the_stale_base_and_shows_the_notice
FAILED tests/test_desktop_f1_stale_schema.py::test_the_window_does_not_migrate_the_base
FAILED tests/test_desktop_f1_stale_schema.py::test_every_door_the_window_calls_at_startup_answers_without_raising
FAILED tests/test_desktop_f1_stale_schema.py::test_the_command_the_window_names_is_parseable_and_updates_the_base
FAILED tests/test_desktop_f1_stale_schema.py::test_after_the_update_the_same_doors_read_transcripts
FAILED tests/test_desktop_f1_stale_schema.py::test_the_transcript_doors_say_words_and_the_rest_still_reads
FAILED tests/test_desktop_f1_stale_schema.py::test_the_chat_box_offers_nothing_to_open_on_a_stale_base
```

After the fix: `.........                                                        [100%]`.

### F2 — двойной щелчок проверяет машина

`tests/test_desktop_f2_double_click.py`, marker `firsthour` (registered, and
deselected by `addopts` — `integration` would NOT have worked, it runs in the
normal set). Explicit call:
`python3 -m pytest -m firsthour tests/test_desktop_f2_double_click.py`.

What the test does, in this order:

1. builds the bundle with the same command the GUIDE names
   (`python3 -m PyInstaller EquityLab.spec --noconfirm`), sending `--distpath`
   and `--workpath` into the test's own tmp dir, so no 167 МБ trace stays in
   the clone;
2. launches it the way Finder does — `open -n -W --stdout … --stderr … <app>
   --args --root <каталог>`. `open` is the point: the child gets no terminal
   environment, which is exactly the ТЗ-81 B3 condition;
3. waits 5 s and requires the process to be alive, counted by `pgrep -f` on the
   absolute path of the binary inside THIS sandbox bundle (a stray
   `EquityLab.app` of the user's own checkout is not matched);
4. closes it: SIGTERM to the new pids, then SIGKILL to stragglers, and asserts
   none are left;
5. reads the captured stderr, so "жив" and "не упал" are two separate claims.

Case 1: a catalog built by the current migrations. Case 2: the real
schema-44 base from `tests/data/upgrade`. Both must be alive, case 2 also
requires `no such table` absent from stderr.

Measured, post-fix (the whole run, build included):

```
tests/test_desktop_f2_double_click.py::test_double_click_on_a_current_catalog_keeps_the_process_alive [f2] launch root=current alive_after_5.0s=1 stderr_bytes=0
PASSED
tests/test_desktop_f2_double_click.py::test_double_click_on_a_stale_schema_keeps_the_process_alive [f2] launch root=stale44 alive_after_5.0s=1 stderr_bytes=0
PASSED
============================== 2 passed in 50.69s ==============================
```

Measured, on the bundle built from `242656a` (before F1, kept aside at
`/tmp/pre-f1-EquityLab.app`) through the very same helpers of this test file —
case 2 red, with the reason the task asked to quote:

```
[f2] launch root=current alive_after_5.0s=1 stderr_bytes=0
current: alive=True
   stderr tail:
[f2] launch root=stale44 alive_after_5.0s=0 stderr_bytes=1032
stale44: alive=False
   stderr tail:   File "rusterm/desktop/data.py", line 913, in llm_usage_line
 |   File "rusterm/store/repos.py", line 2164, in calls_totals
 | sqlite3.OperationalError: no such table: chat_transcript
```


## Blocked

None.

## What not to trust

- F1's evidence is one base behind (`44 → 45`). A base two or more migrations
  behind may lack tables other doors read (the round's fixture set has
  `schema41`, not tested through the window here). The notice line is correct
  for any older schema; the "readable is readable" claim is only measured for
  one step back.
- A file that is not a RusTerm base at all (`schema_version` table missing →
  `current_schema_version` returns `None`) is *not* covered: `schema_notice`
  stays `None` and the doors of the sidebar would still raise. Out of F1's
  letter ("схема старше ожидаемой"); filed under Disputed.
- F2 builds its bundle inside the test's `tmp_path` (`--distpath`/`--workpath`),
  so the app it measured is gone with the temp dir; `dist/EquityLab.app` in the
  clone is still the arrival-state build from `242656a`, i.e. before F1. The
  artifact the user double-clicks is rebuilt by whoever ships it — this round
  proves the *source* passes the double-click test, not that a stored `.app`
  somewhere on disk carries the fix.

## Disputed

1. F1 says "окно ... показывает одну строку вида «база в <каталог> — схема 44,
   программе нужна 45; обновите: <исполнимая команда>»". It does not say which
   command. I chose `rusterm --root <каталог> init` — `cmd_init` is the only
   writing door that applies migrations without also reaching for the network —
   and the same line is what `rusterm status` would tell me anyway. If the
   coordinator prefers a dedicated `rusterm migrate`, that is a CLI item, not a
   desktop one.
2. Non-base files: opening a sqlite file with no `schema_version` table leaves
   the window raising in `sidebar_companies`. Strictly outside F1 ("чья схема
   старше ожидаемой"), so not widened here; a one-line guard in
   `open_readonly` (treat "no schema table" as "no base to read") would close
   it in the next round.
3. `## Disputed` numbering: TASK-95 F0 answers the previous round's disputes in
   a table keyed `1, 2, 3, В1, В2, В3`; my report keys them `1, 2, 3`. No rule
   says otherwise, noted only so the two files are not read as one numbering.

## Runs

| # | Команда | Итог |
|---|---|---|
| 1 | `python3 -m PyInstaller EquityLab.spec --noconfirm` | `Build complete!`, 19.6 s, 167 МБ |
| 2 | `open -n dist/EquityLab.app --args --root <каталог>` + проверка живости через 5 с | current: жив (1 процесс); schema44: 0 процессов |
| 3 | `dist/EquityLab.app/Contents/MacOS/EquityLab --root <каталог>` (offscreen, `RUSTERM_APP_SMOKE=1`) | current rc=0 + строка smoke; schema44 rc=1, traceback `no such table: chat_transcript` |
| 4 | `python3 -m pytest tests/test_desktop_f1_stale_schema.py -q` (до правки) | 9 failed, цитата выше |
| 5 | то же после правки | 9 passed `[100%]` |
| 6 | прогон окна с обёрнутыми дверями (скрипт, не тест) | `errors: []`, список дверей в `## Done` |
| 7 | `python3 -m pytest -m firsthour tests/test_desktop_f2_double_click.py -o addopts="" -v -s` | `2 passed in 50.69s`, сборка + оба запуска живы |
| 8 | те же хелперы поверх `/tmp/pre-f1-EquityLab.app` (сборка из `242656a`) | current жив; stale44 `alive=False`, stderr `no such table: chat_transcript` |

Nothing here touched `~/equitylab` or `~/.rusterm` for writing: both were
replaced by sandbox `HOME` in tests and probes; the bundle runs above were given
an explicit `--root` under `/tmp`.

## HANDOFF

Status: IN PROGRESS — F1 and F2 committed, F3 next in this round.
Items done: приём круга (STATE + отчёт), F1, F2
Questions: see Disputed 1 (which command the line should name).
