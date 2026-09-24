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

### K1 — two threads, own connections, 400 rows

`tests/test_concurrency.py` is the round's new file and the first test in the
repository that runs two writers at once. K1's shape is the spec's letter: two
threads, each opening its own connection through `db.open_connection(paths)`
(the same door the CLI and the window use), a `threading.Barrier(2)` so they
really start together, and 200 real repository writes each —
`repos.instrument.upsert_instrument` → `writer_transaction` → one row in
`instrument` under an issuer seeded beforehand (FKs are on, so the seed is
part of the setup, not decoration).

What the test asserts, beyond «it did not crash»:

* every exception a worker raises is collected into a list and asserted empty —
  an exception inside a thread is otherwise swallowed and the test stays green;
* the two threads' write intervals **overlap** (`max(start) < min(end)`),
  because without that the same code path can pass by writing one after the
  other and claim to have tested concurrency;
* row count is exact: `len(rows) == 2 * N_WRITES` **and** the id set equals the
  expected set, so a lost write and a stray write are both red;
* `join(JOIN_TIMEOUT)` with `JOIN_TIMEOUT = 25 s`, a hung thread reported by
  name, and total wall time `< 30 s` per the item.

Measured:

```
$ PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_concurrency.py \
      -p no:cacheprovider --durations=3 -o addopts=""
0.05s call     tests/test_concurrency.py::test_two_threads_two_hundred_writer_transactions_each
1 passed in 1.19s
```

Teeth, proven by mutating `writer_transaction` in a temp worktree
(`$TMPDIR/rt84-lab` at `b1d0890`, script `/tmp/rt84-staging/k1_teeth.sh`):

| mutation | result | reading |
|---|---|---|
| none (baseline) | `1 passed in 0.10s` | — |
| A: `with _writer_lock:` → `if True:` (process lock removed) | **`1 passed in 0.09s`** | K1 does *not* pin the lock — see below |
| B: `conn.execute("COMMIT")` → `pass` (commit forgotten) | **`1 failed in 0.07s`** | K1 catches lost writes, which is its stated job |

After both mutations `git checkout -- rusterm/store/db.py`; `grep -c МУТАЦИЯ`
→ `0`, worktree left with only the copied test file.

The honest consequence of mutation A is the most useful number of this item:
with the process-wide lock deleted, 400 concurrent transactions on two
connections still land exactly right, because SQLite's own single-writer rule
plus `timeout=30` serializes them at the file level. So `_writer_lock` is not
what protects a cross-thread write from a lost update in this design — what it
buys is latency (no 30 s busy retries) and, negatively, the hang K2 turns into
an error. The window never shares a connection between threads
(`rusterm/desktop/window.py:65-66` says so out loud: «sqlite-соединение не
переезжает между потоками», and `collect_synthetic` opens its own), which is
why I did not add a shared-connection case to K1: it would test a scenario the
design rules out, and its green would be about my test, not about the product.

Budget: 0 network requests, 0 LLM calls.

## Blocked

none

## What not to trust

* K1's green does **not** mean the writer lock works: measured, deleting
  `with _writer_lock:` leaves K1 green (`1 passed in 0.09s`), because SQLite
  serializes writers at the file level and the connection carries
  `timeout=30`. K1 pins «no lost writes, no leaked OperationalError, exact row
  count»; the lock's own behaviour is what K2 pins, and cross-process behaviour
  is not covered by any lock at all (K4's job).
* 400 transactions in 0.05 s looks too good, and it is worth doubting. What
  makes it plausible is measured, not assumed: the row check runs on a
  *separate connection opened after both workers closed theirs*, and it sees
  all 400 ids — so the bytes really reached the database, and WAL on APFS with
  SQLite's plain `fsync` (not `F_FULLFSYNC`) costs microseconds, not
  milliseconds. What this does *not* prove: durability across a power loss,
  which no test here claims.
* `JOIN_TIMEOUT = 25 s` is a per-test ceiling, not a measured need — the item
  ran in 0.05 s. If a future regression makes writers slow (rather than hung),
  K1 will stay green up to 25 s and then blame a hang. K8's 20-run loop is what
  bounds the timing claim.
* Nothing in `## Blocked`, but only K1 is done: the file's remaining items will
  add the cross-process and reader cases, so treat the current «I14 is proven»
  reading as premature until K8 closes the round.

## Disputed

1. K1's mutation A says the round's premise needs a sharpening, and the place
   to say it is here rather than in code: `agent/CONTEXT.md`'s invariant I14
   («один писатель» через `_writer_lock`) is treated as the thing that protects
   concurrent writes, but measured, it is not — with the lock removed the
   two-thread case still produces exactly the right 400 rows, because SQLite
   allows one writer and `open_connection` carries `timeout=30`. What the lock
   actually owns: (a) latency — without it every loser of the race burns busy
   retries; (b) the nesting hang that K2 turns into a `RuntimeError`; (c)
   nothing at all across processes, which is K4's whole point. Ask: restate
   I14 as «одна транзакция за раз на соединение + сериализация писателей на
   уровне базы», or keep the wording and accept that the lock is a latency
   device? Not fixed here: I14's text is coordinator-owned (`agent/CONTEXT.md`,
   P6), and TASK-84 authorises no doc edits.

## Runs

| # | command | output |
|---|---|---|
| 1 | `git log --oneline -1`, `git status --porcelain` | `3b89b79 Эстафета: круг 119, ход у executor — agent/TASK-84.md`, tree clean |
| 2 | `python3 -m pytest --collect-only -q -o addopts="-m 'not live and not volume and not firsthour and not slow'"` | `1316/1336 tests collected (20 deselected) in 0.60s` |
| 3 | `grep -rln "threading\|Thread(" tests/` | no output (exit 1) — zero test files mention threads |
| 4 | `python3 -m pytest tests/test_report_sections.py -q -o addopts=""` (before the STATE repair) | `1 failed, 27 passed in 0.84s` — `пункты ['F1', 'F2', 'F3', 'F4', 'F5'] … коммита круга с реализацией … не найдено` |
| 5 | `python3 agent/relay.py --branch agent/night-11 status` | `круг 119: ход у executor  task=agent/TASK-84.md  report=agent/REPORT-84.md  передал coordinator в 2026-09-24T03:56:06Z` |
| 6 | same guard command again, after STATE points at TASK-84/REPORT-84 | `27 passed, 1 skipped in 1.87s` — the skip is L3 itself: nothing is declared done yet, so there is no item id to look for a commit for |
| 7 | `git commit -F …` for the arrival (hook = selfcheck → full acceptance) | `Итог: пройдено 13, провалено 0` / `Принято.` / `SELFCHECK OK` → `b1d0890`, pushed (log `/tmp/rt84-commit-arrival.log`) |
| 8 | `python3 -m pytest tests/test_concurrency.py -p no:cacheprovider --durations=3 -o addopts=""` (clone) | `0.05s call … K1`, `1 passed in 1.19s` |
| 9 | `bash /tmp/rt84-staging/k1_teeth.sh` — baseline + mutation A (lock removed) + mutation B (COMMIT forgotten) in `$TMPDIR/rt84-lab` at `b1d0890` | baseline `1 passed in 0.10s`; A `1 passed in 0.09s` (K1 blind to the lock); B `1 failed in 0.07s`; after restore `grep -c МУТАЦИЯ` → `0`, `git status --porcelain` → only `?? tests/test_concurrency.py` |

## HANDOFF

Status: WORKING — круг 119 идёт, K1 закрыт коммитом.

Items done: приём круга (STATE + отчёт), K1.
Items not done: K2, K3, K4, K5, K6, K7, K8 — очередь ТЗ-84, по одному коммиту
на пункт.

Network: 0 requests spent. LLM calls: 0.
First finding for the coordinator: entry 1 of `## Disputed` — with
`_writer_lock` removed, K1 stays green, so I14's wording is about latency and
nesting, not about lost writes.
NOW: K2, step 1
