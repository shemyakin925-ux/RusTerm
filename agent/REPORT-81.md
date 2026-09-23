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
