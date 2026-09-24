# REPORT-84 — TASK-84: concurrent writers

Round 119, branch `agent/night-11`, executor. Spec: `agent/TASK-84.md`
(items K1–K8). Report language: English (agent-to-agent); code comments and
commit messages are Russian per the project rule.

## Arrival state (measured before the first source edit)

* Base: `3b89b79` «Эстафета: круг 119, ход у executor — agent/TASK-84.md»,
  working tree clean, `agent/STATE.json` re-pointed by this commit.
* Suite as it stands: `1316/1336 tests collected (20 deselected) in 0.60s`
  under the default marker filter (`-m 'not live and not volume and not
  firsthour and not slow'`).
* The spec's central claim is true as measured: `grep -rln "threading\|Thread("
  tests/` → **no matches**. Nothing in `tests/` mentions threads at all, so
  I14 («single writer») has no executing check today and
  `tests/test_concurrency.py` will be the first file to drive two writers.
* Store core, as read (`rusterm/store/db.py`): `_writer_lock =
  threading.Lock()` at line 25 — plain, non-reentrant, no owner tracking;
  `open_connection()` at line 796 — `timeout=30`, `isolation_level=None`,
  `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`; `writer_transaction()`
  at lines 806–823 — `with _writer_lock:` → `BEGIN IMMEDIATE` → yield →
  `COMMIT`, and `except Exception` → `ROLLBACK` + re-raise. Consequences the
  items have to pin: a nested call on one thread blocks the thread forever
  (K2), an exception inside does roll back and release (K3, to be proven, not
  assumed), and the lock is per-process, so two processes rely on
  `BEGIN IMMEDIATE` + the 30 s busy timeout alone (K4).
* Budgets: network 0, LLM 0 — nothing in this round needs either.
* Bookkeeping on arrival was red, in exactly the way REPORT-83 recorded it as
  its entry 1 of `## Disputed` (so the ruling has not landed yet): the hand
  moved `agent/BATON.json` to round 119 while `agent/STATE.json` still named
  the closed round (`task: agent/TASK-83.md`, `report: agent/REPORT-83.md`,
  `status: awaiting_review`). The guards take the round from the baton and the
  report path from STATE, so TASK-83's finished items were screened against
  round 119's commits:

```
$ python3 -m pytest tests/test_report_sections.py -q -o addopts=""
FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
1 failed, 27 passed in 0.84s
AssertionError: пункты ['F1', 'F2', 'F3', 'F4', 'F5'] объявлены сделанными, но
коммита круга с реализацией (не только tests/) не найдено
```

  Nothing about TASK-83 is actually undone — it was accepted (`4e997a1`,
  «ТЗ-83 ПРИНЯТО целиком»). The consequence for this round is a rule of
  order: the repair (re-pointing STATE at TASK-84/REPORT-84) must be the
  round's first commit, because the `pre-commit` hook runs acceptance and a
  red tree cannot pass the turn.
* Not yet run at the moment of writing this section: the acceptance chain
  (it runs in this commit's own `pre-commit` hook, so its verdict is quoted
  from the hook log in a later section, never predicted here).

## Done

(to be filled item by item: K1 … K8)

## Blocked

none

## What not to trust

* Nothing is finished yet — this section fills up as items land.

## Disputed

(none yet)

## Runs

| # | command | output |
|---|---|---|
| 1 | `git log --oneline -1`, `git status --porcelain` | `3b89b79 Эстафета: круг 119, ход у executor — agent/TASK-84.md`, tree clean |
| 2 | `python3 -m pytest --collect-only -q -o addopts="-m 'not live and not volume and not firsthour and not slow'"` | `1316/1336 tests collected (20 deselected) in 0.60s` |
| 3 | `grep -rln "threading\|Thread(" tests/` | no output (exit 1) — zero test files mention threads |
| 4 | `python3 -m pytest tests/test_report_sections.py -q -o addopts=""` (before the STATE repair) | `1 failed, 27 passed in 0.84s` — `пункты ['F1', 'F2', 'F3', 'F4', 'F5'] … коммита круга с реализацией … не найдено` |
| 5 | `python3 agent/relay.py --branch agent/night-11 status` | `круг 119: ход у executor  task=agent/TASK-84.md  report=agent/REPORT-84.md  передал coordinator в 2026-09-24T03:56:06Z` |
| 6 | same guard command again, after STATE points at TASK-84/REPORT-84 | `27 passed, 1 skipped in 1.87s` — the skip is L3 itself: nothing is declared done yet, so there is no item id to look for a commit for |

## HANDOFF

Status: WORKING — круг 119 идёт, только приём круга.

Items done: приём круга (STATE + этот отчёт).
Items not done: K1, K2, K3, K4, K5, K6, K7, K8.

NOW: K1, step 1
