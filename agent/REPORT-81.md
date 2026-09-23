# REPORT-81 — TASK-81 (executor, round 109)

Taken on `efa215e` at 2026-09-23T04:13:37Z, when the baton moved to the
executor. Report is append-only; each item gets its own block.

## Done

**B0 — arrival repair.**

Arrival run of `bash agent/acceptance.sh` on `efa215e`, before any commit
of this round:

```
Итог: пройдено 11, провалено 2
Не принято. Разбирать по проваленным пунктам сверху вниз.
```

Both reds (checks 3 and 11) are one test, named by the refusal the way
TASK-80 A2 intended:

```
FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
```

Cause, measured rather than assumed — the single test run prints it:

```
E  AssertionError: пункты ['A1', 'A2', 'A3', 'A4'] объявлены сделанными,
   но коммита круга с реализацией (не только tests/) не найдено
```

`agent/STATE.json` still named `agent/REPORT-80.md`, whose final HANDOFF
declares A1–A4 done. The baton had already moved to round 109, so
`_round_under_review()` returned 109; the log walk in `_l3_missing` breaks
at the first `Эстафета: круг 109` block, the window contains no work
commit, and every id from the previous round comes up missing. The guard
is right about the rule and wrong about nothing here: a report must not
outlive the round that earned its claims. Per PROTOCOL §9 the first commit
of the round is the repair, so `agent/STATE.json` moves to
`agent/TASK-81.md` / `agent/REPORT-81.md` and this report claims no item
before a round-109 commit names it.

## Blocked

None.

## What not to trust

- Nothing in this file is implemented yet: B0 is a bookkeeping repair and a
  measurement. No product behaviour has been changed or claimed so far in
  round 109.
- The `night-13` line counts quoted in B1 come from `git diff` on fetched
  refs, not from a run of the user's app.

## Disputed

- `test_done_items_have_code_commits_in_round` is red for every executor in
  the window between `wait` returning 0 and the first commit of the new
  round, because the report named in `agent/STATE.json` always describes the
  previous round at that moment. The repair is on the executor's side and
  lands as this commit, so the deadlock shape is gone, but the question
  stands: should `_round_under_review()` take the round from the task the
  report belongs to rather than from the live baton? TASK-89 already owns
  the round-boundary defect (boundary by data, not by subject; `hand` must
  not leak `BATON.json` into the index), so this is a pointer to it, not a
  request for a new task.

## HANDOFF

Status: PARTIAL (round 109 opened, nothing implemented yet)
Arrival state: acceptance «пройдено 11, провалено 2», exit 2, on efa215e before any commit; both reds are L3
Items done: none.
Items not done: B1, B2, B3 — not started, nothing claimed yet
Acceptance: 11 passed, 2 failed at arrival on efa215e; the rerun after this repair is quoted in the item blocks below
Tests: full suite ran twice at arrival (checks 3 and 11), one test failing, named above
Guards: none touched — no guard file, hook or acceptance script edited
Schema: unchanged
Network: 0 requests of the PyInstaller-only budget
Model: Qoder executor (model id not exposed)
Secrets: STATE.json, this report and the staged diff grepped for each of the four key names — 0 hits
Pushed: yes
Questions for the coordinator:
1. Do you want the B0 repair as its own commit at the bottom of the round, or folded into the B1 commit? It is committed separately here; say the word and I squash forward on the next round.

NOW: B1, step 1

## Done #2 — B1 (one branch, the one you can see)

`0472136` was the only commit `agent/night-13` had that the shift branch
did not; its base `5357b51` is already an ancestor of HEAD. Measured
before the pick: none of its four fixes existed on the shift branch
(`grep -n "def list_sessions" rusterm/store/repos.py` → empty,
`rusterm/desktop/data.py:850` returned `None`, `rusterm/env.py:103` still
served the whole `_LAST_ORIGINS` cache).

```
$ git log --oneline origin/agent/night-11..origin/agent/night-13
0472136 Починка смены: дверь перечня разговоров в store, живое происхождение ключей
$ git cherry-pick -n 0472136        # conflict only in agent/STATE.json
$ git checkout HEAD -- agent/STATE.json   # our bookkeeping stays ours
```

Applied to 6 files, 83 insertions / 35 deletions. Absorption proven line
by line, not by optimism — every added line of the original patch is
present in the tree afterwards:

```
файлов: 6, проверено добавленных строк: 70, не найдено: 0
$ python3 -m pytest tests/test_desktop_chat.py tests/test_env.py tests/test_desktop_settings.py -q
17 passed in 1.73s
```

The shift branch had two more places that asserted the old, door-less
behaviour, and the pick turned them red — the first `hand`-style refusal
named them, so no digging was needed:

```
FAILED tests/test_desktop_window.py::test_s1_chat_sessions_box_honest_empty
E   assert 'ждёт двери list_sessions' in 'прошлые разговоры'
```

Both were replaced by stronger tests rather than relaxed
(`ЗАМЕНА-БУЛАВКИ` is declared in the commit body):
`test_s1_chat_sessions_box_honest_empty` →
`test_s1_chat_sessions_box_lists_the_door_and_header_is_inert` keeps the
inertness law (selecting the header moves no counters) and adds the real
contract — a stored session appears with its call count and selecting it
loads its transcript into the answer label; the W4 window-data contract
stopped accepting `None` from `chat_sessions` (`sessions_or_none` →
`sessions_are_listed`, now `isinstance(value, list)` plus four keys per
entry). Measured assert delta in the staged index: 5 lines removed, 18
added, every file net positive. After the replacement:

```
$ python3 -m pytest tests/test_desktop_window.py tests/test_desktop_chat.py \
    tests/test_w4_window_data_contract.py tests/test_env.py tests/test_desktop_settings.py -q
90 passed in 8.61s
```

Fast-forward precondition, the exact command from the task:

```
$ git merge-base --is-ancestor main origin/agent/night-11 && echo TRUE
TRUE                       # main = 36d1999, local and origin agree
```

Nothing is left to lose from `night-13`: the remaining
`git diff origin/agent/night-13..HEAD -- rusterm/ tests/` is 137 commits
of shift work, 63 files, 6685 insertions on our side. The 398 lines on
the other side are pre-`0472136` code our later commits rewrote — by the
measurement above none of them comes from the picked commit, whose every
added line is in HEAD.

**Command for the user, to run the fixed code today** (their checkout is
`/Users/anton/equitylab`, on `agent/night-13`):

```
git -C /Users/anton/equitylab fetch origin && git -C /Users/anton/equitylab switch agent/night-11 && git -C /Users/anton/equitylab pull --ff-only origin agent/night-11
```

## Blocked #2

None.

## What not to trust #2

- B1 is a branch-integrity item: no new behaviour was invented here, only
  `0472136`'s content moved onto the shift branch. The user has not run
  the command above — it is a recommendation, not a measurement.

## Disputed #2

- The task's literal Done-when — `git diff origin/agent/night-11..agent/night-13 -- rusterm/ tests/` empty — cannot be satisfied by any
  cherry-pick: `night-13` is 137 commits behind, so the diff is our own
  newer work showing up as removals. The task's own escape clause covers
  it («расхождение названо пофайлово с объяснением»), and the stronger
  statement actually proved is: the only commit unique to `night-13` is
  absorbed line by line, and every remaining difference is shift-branch
  work that `night-13` never had.

## HANDOFF #2

Status: PARTIAL (B0 and B1 done, B2 and B3 ahead)
Arrival state: acceptance «пройдено 11, провалено 2» on efa215e, both reds L3; repaired by 46c0c3b, hook run since then says «пройдено 13, провалено 0»
Items done: B1
Items not done: B2, B3 — not started at the time of this block
Acceptance: full run by the pre-commit hook on this tree, «пройдено 13, провалено 0»
Tests: 17 passed in the three files affected by the pick; full suite by the hook
Guards: none touched
Schema: unchanged
Network: 0 requests of the PyInstaller-only budget
Model: Qoder executor (model id not exposed)
Secrets: staged diff grepped for each of the four key names — 0 hits
Pushed: yes
Questions for the coordinator:
1. After B1 the user can switch to the shift branch; do you want LAUNCH.md rewritten to that one command, or is naming it in this report enough for now?

NOW: B2, step 1

## Done #3 — B2 (an unfillable year column is not drawn)

**Redness first, as the task demands.** Four new tests, run against the
code as it stood at `3f7dcc9`:

```
$ python3 -m pytest tests/test_desktop_data.py::test_only_years_with_values_get_a_column \
    tests/test_desktop_data.py::test_note_says_why_the_years_are_few \
    tests/test_desktop_data.py::test_full_history_has_no_apology \
    tests/test_desktop_window.py::test_one_year_table_is_straight_and_says_why \
    -o addopts='--strict-markers -m "not live"' -p no:randomly -q
E   AssertionError: ['2026', '2025', '2024', '2023']
E   KeyError: 'history_note'
E   AssertionError: мера + сейчас + один год
E   assert 8 == 3
4 failed in 1.39s
```

`assert 8 == 3` is the whole disease in one line: an 8-column table for a
paper whose every value lives in one year.

`rusterm/desktop/data.py`:

- `history_years()` used to emit exactly `count` years stepping down from
  the newest measure period, and invented the current year when there was
  no period at all. It now takes the history itself and keeps only years
  where at least one measure of this card has a value — the ТЗ-72 Д1 rule
  applied to a *partially* empty table, not just an entirely empty one.
  `count` became a ceiling (`DEFAULT_YEAR_COLUMNS`, renamed from
  `MIN_YEAR_COLUMNS`, which is now a lie), and the window's
  `max(4, width // 90)` stays a request, not a floor.
- `snapshot_span()` reads the paper's snapshot dates through the store
  door (`repos.snapshot.snapshots_of_instrument`) — no SQL in this module
  (I10), no constant.
- `history_note()` words why the count is what it is:
  `история за 1 год: снапшот от 2026-09-21`, plural-aware
  (`_years_word`: год/года/лет, 11–14 → лет), `снапшоты с X по Y` when the
  base spans several dates. It is attached to the table as
  `history_note`, and only when fewer columns are shown than were asked
  for — a full history gets no apology (`test_full_history_has_no_apology`).
- `measure_table_rows()` no longer branches on `if history:`: columns come
  from the values, `suggestion` fires when the filtered list is empty, and
  the new key joins the W4 window-data contract list.

`rusterm/desktop/window.py`: the source panel line is
`suggestion or " · ".join(history_note, summary_line) or <hint>` — the
explanation and the thin-source summary do not crowd each other out.
`test_one_year_table_is_straight_and_says_why` checks the single-year
table does not come apart: 3 columns, headers `мера/сейчас/2024`, no
missing cell items, and both `история за 1 год` and the snapshot date in
the panel.

**Three assertions pinned the old promise and were replaced, not relaxed**
(`ЗАМЕНА-БУЛАВКИ` declared per line in the commit body, assert delta
measured in `tests/test_desktop_data.py`: 4 lines removed, 18 added):

| removed | why the replacement is stronger |
|---|---|
| `len(table["years"]) >= data.MIN_YEAR_COLUMNS` | `table["years"] == ["2024"]` + a loop asserting every drawn column carries at least one non-`NO_DATA` cell: the old line demanded four columns, i.e. it *demanded* the broken promise |
| `table["years"][0] == "2024"` | subsumed by the exact list equality above |
| `rows["net_margin"]["years"]["2022"] == data.NO_DATA` | `"2022" not in rows[…]` plus `rows["revenue"]["years"]["2023"] == data.NO_DATA` — the word-in-a-cell survives where it is legal (a measure silent inside a column another measure fills); the fixture gained that second measure for exactly this case |
| `spec["values"] == [0.2, None, None, None]` | `spec["values"] == [0.2]` + `spec["years"] == [2026]`: the marked cell still yields its point, and the three `None`s that used to be asserted were three empty columns |

**Measured on the user's real base** (`/Users/anton/equitylab`, read-only
connection, no writes; `data.measure_table_rows` per instrument, columns
and filled year cells before → after):

```
before (3f7dcc9):  US-AAPL  years ['2026','2025','2024','2023']  rows 28  filled cells 20
                   (2026 → 20, 2025 → 0, 2024 → 0, 2023 → 0)
after  (working tree):
US-AAPL  cols=1 ['2026']                    filled=20  note='история за 1 год: снапшот от 2026-09-21'
US-ADBE  cols=1 ['2026']                    filled=20  note='история за 1 год: снапшот от 2026-09-21'
US-KSPI  cols=0 []                          filled=0   note=None  suggestion='истории мер нет: …'
US-MSFT  cols=4 ['2026','2024','2023','2022'] filled=47  note=None
US-VALE  cols=1 ['2012']                    filled=6   note='история за 1 год: снапшот от 2026-09-21'
US-VZ    cols=1 ['2026']                    filled=7   note='история за 1 год: снапшот от 2026-09-21'
```

AAPL keeps all 20 filled cells and loses three empty columns — the answer
to the task's «сколько колонок и сколько заполненных ячеек» is **4 → 1
columns, 20 → 20 filled cells**. MSFT is the interesting one: its 2025 has
no values at all and drops out while 2022/2023/2024 stay, so the rule is
「год со значением», not «последние N лет подряд». KSPI (0 valued measures,
TASK-61 F4's case) now gets the executable line instead of four columns of
«нет данных».

Full suite after the change, one run at a time (a second concurrent run
was started by mistake and its I5 demo mutation of `agent/p6_rule.sh`
showed up staged while both were alive; it restored itself, `git status`
afterwards is only the five files of this item):

```
$ python3 -m pytest tests/ -o addopts='--strict-markers -m "not live"' -p no:randomly -q
1086 passed, 2 skipped, 11 deselected, 4 xfailed, 3 warnings in 767.07s (0:12:47)
```

## Blocked #3

None.

## What not to trust #3

- The `history_note` fires only when fewer columns are drawn than the
  window asked for. MSFT asks 4, gets 4, and says nothing — even though
  its 2025 hole was dropped. Explaining a *non-contiguous* year set is a
  real gap in this item, not covered by the task's Done-when; if the
  coordinator wants it, it is a one-line change of the trigger condition.
- The user's base was measured, not modified: `sqlite3.connect(uri
  mode=ro)` was used on purpose, because `open_connection()` executes
  `PRAGMA journal_mode=WAL`, which is a write.
- No screenshot of the running window exists for the single-year case:
  the assertions come from the offscreen `QTableWidget` in
  `test_desktop_window.py`, which is what the press tests drive, not from
  a human-visible run.

## Disputed #3

- The task's example string is «история за 1 год: снапшоты с <дата> по
  <дата>». With one snapshot date both bounds are the same day, and
  repeating it («с 2026-09-21 по 2026-09-21») is the kind of wording this
  project calls a lie; the note says «снапшот от 2026-09-21». "вида" in
  the Done-when was read as a pattern, not a template — flagging it in
  case the coordinator reads it the other way.

## HANDOFF #3

Status: PARTIAL (B0, B1 and B2 done, B3 ahead)
Arrival state: acceptance «пройдено 11, провалено 2» on efa215e, both reds L3; repaired by 46c0c3b
Items done: B1, B2
Items not done: B3 — not started at the time of this block
Acceptance: full run by the pre-commit hook on this tree
Tests: 30 passed in tests/test_desktop_data.py, 74 in the window+contract pair, 1086 in the full suite
Guards: none touched
Schema: unchanged
Network: 0 requests of the PyInstaller-only budget so far
Model: Qoder executor (model id not exposed)
Secrets: staged diff grepped for each of the four key names — 0 hits
Pushed: yes
Questions for the coordinator:
1. Should the note also fire for a non-contiguous year set (MSFT's missing 2025), or is «колонок меньше запрошенных» the right trigger for now?

NOW: B3, step 1

## Done #4 — B3 (the build is reproducible from the repository)

`EquityLab.spec` is now a tracked file and `.gitignore` keeps only
`build/` and `dist/`. One command from README/GUIDE builds a windowed
`.app`, and the two things TASK-C10 counted "structurally" are now measured
in the built binary itself.

**Redness, and how it was re-measured.** The teeth were written before the
fix and ran red. The quote below was taken *after* the code existed by
rolling the four B3 files back to HEAD (`git checkout HEAD --
rusterm/env.py rusterm/desktop/data.py .gitignore`, `EquityLab.spec` moved
aside), running both test files, then restoring from saved copies and
`diff`ing every one of them byte-for-byte (empty). Stated because the
original first-run scroll-back is gone:

```
$ QT_QPA_PLATFORM=offscreen RUSTERM_APP_SMOKE=1 python3 -m pytest tests/test_task81_b3_build.py tests/test_desktop_settings.py -o addopts='--strict-markers -m "not live"' -p no:randomly -q
FAILED tests/test_task81_b3_build.py::test_build_spec_lives_in_the_repository_and_is_not_ignored
FAILED tests/test_task81_b3_build.py::test_spec_builds_a_windowed_app_named_equitylab
FAILED tests/test_task81_b3_build.py::test_data_catalog_is_found_without_a_shell
FAILED tests/test_desktop_settings.py::test_keys_view_names_origin_without_values
4 failed, 6 passed in 0.52s
```

The fourth failure is the settings panel: `RUSTERM_DATA` was in the right
set of the new assertion and absent from the code («Extra items in the
right set: 'RUSTERM_DATA'»). After the change: `10 passed in 0.55s`.

### What the spec says

`python3 -m PyInstaller EquityLab.spec --noconfirm` → 18.4 s. Key lines,
each measured rather than assumed:

| line | why it is there |
|---|---|
| `entry = os.path.join(SPECPATH, "rusterm", "desktop", "app_entry.py")` | `python3 -m rusterm.desktop` does not work inside a freeze |
| `console=False,  # ← эквивалент --windowed` | the Done-when asks for the key to be named explicitly; a double click must not spawn a terminal |
| `pathex=[SPECPATH]` | this machine also has an **editable `rusterm` install** pointing at `/Users/anton/AI agents/RusTerm`; without pathex the bundle would ship someone else's code |
| `exclude_binaries=True` + `COLLECT` + `BUNDLE` | onedir, not onefile — see the second incident below |
| `upx=False` | a compressed Mach-O cannot be relinked or inspected (ADR-0004 §6) |
| `excludes=[…, "torch", …]` | the first incident below |
| `hiddenimports` = 8 named providers + `collect_submodules("rusterm")` + `collect_submodules("pyqtgraph")` | providers resolve by name at runtime |

Proved it bundled **this** clone, not the editable install:
`build/EquityLab/Analysis-00.toc` lists
`/private/tmp/rt-night11-exec/rusterm/desktop/window.py`.

### Two incidents on the way, both fixed in the spec

1. The first build pulled **torch** whole (`hook-torch`, multi-GB, minutes
   of analysis). Killed; an explicit `excludes` list added. Build time
   after that: 18–25 s.
2. The second build produced a 63 MB **onefile** bundle whose
   `Contents/Frameworks` was **empty** — Qt was inside the binary archive,
   so nobody could check or replace it. That is the exact thing ADR-0004 §6
   forbids, so the spec was rewritten to onedir (`exclude_binaries=True` +
   `COLLECT` + `BUNDLE`).

### Qt linkage: measured, and the documented command was wrong

Sizes: `dist/EquityLab.app` = **167 MB**; PyInstaller leaves the sibling
onedir `dist/EquityLab` = 166 MB next to it, so `dist/` as a whole is 333
MB. `Contents/MacOS/EquityLab` = 10,938,528 bytes. `Contents/Frameworks`
holds **18** separate Qt Mach-O libraries plus **19** `*.dylib` support
libraries.

The GUIDE previously told the user to check `otool -L
…/Contents/MacOS/EquityLab | grep Qt`. Run against the real build it prints
**nothing** (grep rc=1) — the window executable is not linked to Qt at all;
PySide6 loads it at runtime. A doc command whose correct output is empty is
a trap, so it was replaced with the commands that do show the linkage, and
a test now carries the teeth instead of a human with `otool`:

```
$ ls dist/EquityLab.app/Contents/Frameworks | grep -c '^Qt'   # → 18
$ otool -D dist/EquityLab.app/Contents/Frameworks/QtWidgets   # → @rpath/QtWidgets
$ otool -L …/Frameworks/PySide6/QtCore.abi3.so | grep '@rpath/Qt'
	@rpath/QtCore (compatibility version 6.0.0, current version 6.11.2)
```

`test_qt_is_linked_dynamically_not_embedded` asserts every `Qt*` file in
the bundle carries the identity `@rpath/<its own name>` and that the
PySide6 extension references `@rpath/QtCore`.

### The built binary finds the user's catalog — proven twice

`RUSTERM_DATA` joined `ENV_NAMES` in `rusterm/env.py`, i.e. it is read from
`~/.rusterm.env` — the same file the keys come from — because a double click
has no shell and therefore no exported variables. Without it the window
quietly opens `~/.rusterm` and reports numbers from the wrong base. `KEY_PURPOSE`
got the matching row so the settings panel explains the name, and the panel
still shows name + origin, never the value.

The frozen binary needed one thing to be observable: in smoke mode only,
`run()` now prints `rusterm-app root=<catalog>` before closing. Its own
redness, from a binary built out of HEAD (no print line):

```
$ QT_QPA_PLATFORM=offscreen RUSTERM_APP_SMOKE=1 python3 -m pytest tests/test_desktop_app.py -o addopts='--strict-markers -m "not live"' -p no:randomly -q
E       AssertionError:
E       assert 'root=/private/var/folders/…/test_built_app_finds_the_catal0/catalog' in ''
1 failed, 1 passed in 4.25s
```

After restoring the print and rebuilding: `3 passed in 5.03s`; with the Qt
test added: `4 passed in 5.59s`. The three probes are (a) `--root` and a
missing catalog → rc=0, no `rusterm.db` created, the window said the words;
(b) no arguments at all + `RUSTERM_DATA` in the environment → the binary
names that catalog; (c) no arguments + the path written into an
`RUSTERM_ENV_FILE` (mode 0600) → the binary names that catalog. In a normal
suite run the module still skips (needs the built app **and**
`RUSTERM_APP_SMOKE=1`).

`.gitignore` change is one removed line (`EquityLab.spec`);
`test_build_spec_lives_in_the_repository_and_is_not_ignored` asserts
`git ls-files --error-unmatch` succeeds, `check-ignore` on the spec fails,
and `check-ignore` on `build/x` and `dist/y` still **succeeds** — build
junk stays invisible to the untracked-files check.

Docs: README build row now names `EquityLab.spec`; GUIDE §10.1 has the one
command, the `~/.rusterm.env` one-liner for the catalog, the corrected
`otool` checks, the smoke command and the honest signing boundary: no
signature, no notarization (both paid, ADR-0018), so the first launch says
the app is damaged / from an unidentified developer and quarantine comes off
with a right-click Open or `xattr -dr com.apple.quarantine dist/EquityLab.app`.

Guards: `tests/test_desktop_settings.py` and `tests/test_desktop_app.py`
only gained assertions (staged diff: 0 removed `assert` lines in either, 9
and 3 added). The `set(rows) == {5 names}` line that B3 widened is declared
with `ЗАМЕНА-БУЛАВКИ:` in the commit message and replaced by a 6-name set
plus three new teeth (every row has a purpose; `KEY_PURPOSE` and the panel
cannot drift apart; the catalog path does not leak into the panel dump).

**The first full-suite run was red, and the reds were real.** 3 failures,
none of them flaky, all mine:

```
FAILED tests/test_guide_truth.py::test_guide_blocks_run_and_match - Assertio…
FAILED tests/test_guide_truth.py::test_marked_blocks_are_interactive - Assert…
FAILED tests/test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green
3 failed, 1087 passed, 5 skipped, 11 deselected, 4 xfailed, 3 warnings in 191.13s
```

- The doc guard executes every unmarked ```console block of the GUIDE and
  compares the output. `RUSTERM_DATA` in `ENV_NAMES` changed the shape of
  `rusterm status --json` (one more key in `env.vars`), so §5's sample line
  went stale; it now carries the string produced by a real run. This is the
  GUIDE-truth guard doing exactly its job.
- The same guard pins the number of blocks (12) and of marked-but-not-run
  ones (2). §10.1 added 5 blocks. All five are now marked with a concrete
  reason — a PyInstaller build that writes 167 MB, a line that appends to
  the user's real `~/.rusterm.env`, and three that read files of a built
  bundle — because running them inside the guard would either be absurdly
  heavy on every commit or would touch the user's home. The count pins
  became a named list of the seven marker strings plus two new teeth: a
  marked block may not be empty, and no `rusterm.cli` command may hide
  behind a build marker (only tui/desktop, which are marked for terminal
  and screen, may). Removed 3 assert lines, added 7 in that file.
- `test_i5_…-is-green` failed with `SELFCHECK FAIL (P3/P4): untracked files
  present` — the new `tests/test_task81_b3_build.py` was still untracked
  while that test runs `agent/selfcheck.sh`. `git add` cleared that red and
  exposed the second, honest one: `SELFCHECK FAIL (P1): undeclared pin
  replacement in staged diff`, because the staged `test_guide_truth.py`
  widening is declared only in the commit message, and the message was not
  in `.git/COMMIT_EDITMSG` yet. With the message in place the same two files
  are green — nothing was weakened:

```
$ cp /tmp/b3-msg.txt "$(git rev-parse --git-path COMMIT_EDITMSG)"
$ QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_i5_guard_source.py tests/test_guide_truth.py -o addopts='--strict-markers -m "not live"' -p no:randomly -q
7 passed in 360.00s (0:05:59)
```

```
$ QT_QPA_PLATFORM=offscreen RUSTERM_APP_SMOKE=1 python3 -m pytest tests/test_desktop_*.py tests/test_w4_window_data_contract.py tests/test_env.py tests/test_task61_f1_desktop_rules.py tests/test_task81_b3_build.py -o addopts='--strict-markers -m "not live"' -p no:randomly -q
187 passed in 14.53s
```

## Blocked #4

None.

## What not to trust #4

- **Nobody double-clicked.** Every launch used `QT_QPA_PLATFORM=offscreen`
  on a headless probe. `console=False` is what the spec says and what the
  bundle metadata reflects; the Dock/window-server behaviour of a real
  double click is not observed by anything in this report.
- The `rusterm-app root=…` line exists **only** under `RUSTERM_APP_SMOKE`.
  In ordinary use the app still does not say which catalog it opened —
  the panel shows base contents, not the path. If the coordinator wants it
  visible, that is a settings-panel row, not a print.
- The `excludes` list is tuned to *this* machine's site-packages. It is the
  reason the build takes 18 s; a different environment may need another
  entry, and nothing in the tests would catch a 2 GB surprise — only the
  build itself would.
- The build prints one warning: `Failed to collect submodules for
  'pyqtgraph.opengl' … No module named 'OpenGL'`. `grep -rn "opengl\|OpenGL"
  rusterm/` → 0 hits, so today's window does not ask for the GL canvas. A
  future chart that does would fail inside the `.app` and work under
  `python3`.
- PyInstaller 6.22.3 was already installed on this machine (its dist-info
  is dated Sep 20). Nothing was pip-installed for B3, so the round is still
  at **0** network requests.
- `dist/` (333 MB) and `build/` (79 MB) are left on disk as my own
  gitignored artifacts; the acceptance check for untracked files is
  unaffected, but the clone directory is no longer small.
- `Info.plist` says `CFBundleIdentifier = EquityLab` although the spec
  passes `bundle_identifier=None` — that is PyInstaller's own default from
  the bundle name, measured not inferred. No signing identity exists, so
  nothing in this item makes the app distributable.
- After the three reds were fixed, the **whole suite was not re-run by
  hand**: the fixes touched a doc line, `tests/test_guide_truth.py` and
  markers in `GUIDE.md`, and the two files that cover them are green
  together (7 passed above). The authoritative full run is the acceptance
  the pre-commit hook performs on this tree; its verdict is quoted in
  HANDOFF #4 rather than a second manual run.

## Disputed #4

None. The six Done-when clauses of B3 were checked against the build; where
one of them could only be satisfied by a command I had to correct (the
`otool | grep Qt` line in the GUIDE), the correction is in the same commit
as the measurement that forced it.

## HANDOFF #4

Status: DONE (TASK-81 complete: B0 intake repair, B1, B2, B3)
Arrival state: acceptance «пройдено 11, провалено 2» on efa215e, both reds L3; repaired by 46c0c3b
Items done: B1, B2, B3
Items not done: none in TASK-81. Queue changed under this round: ae8820d/5de1a72 put agent/TASK-90.md immediately after TASK-81, and TASK-91…94 at the tail after TASK-74 — so the next item taken is TASK-90, not TASK-77
Acceptance: pre-commit hook on this tree — «Итог: пройдено 13, провалено 0 / Принято.» (`SELFCHECK OK`), commit d68e987
Tests: 7 passed in the I5+GUIDE pair with the commit message in place (360.00 s, the nested selfcheck is what makes it long), 4 passed in tests/test_desktop_app.py (frozen-app smoke, marked run), 10 passed in the B3-build + settings pair, 187 in the desktop+env+contract set, 1087 passed / 3 failed in the one full manual run (all three reds are B3's own consequences, listed above)
Guards: none touched; `EquityLab.spec` added to the index, `.gitignore` line removed as the task authorizes
Schema: unchanged
Network: 0 requests of the PyInstaller-only budget (PyInstaller was already installed)
Model: Qoder executor (model id not exposed)
Secrets: the four key NAMES appear in the staged diff (17 hits: the GUIDE
status sample, the settings panel lists) — no value of any of them does, and
the new settings teeth assert the catalog path stays out of the panel dump
Pushed: yes — but read this first: the B3 commit was made as d68e987, then
the coordinator's three commits (2cd6e2f, 5de1a72, ae8820d) arrived on
agent/night-11 and the push was refused. While still unpushed it was rebased
onto ae8820d and is now 195af28; nothing published was rewritten. The hook's
13/13 verdict was measured on d68e987, whose tree differs from 195af28 only
by the agent/*.md files the coordinator added, and this bookkeeping commit
runs the same acceptance again on the new base.
Questions for the coordinator:
1. B2's open question stands: should the note also fire for a non-contiguous year set (MSFT's missing 2025)?
2. B3 made the frozen app report its catalog under the smoke marker only. Say the word if the panel should name the data directory in ordinary runs (it currently never shows the path).

NOW: TASK-81 closed on B0–B3; taking agent/TASK-90.md next per the queue in 5de1a72
