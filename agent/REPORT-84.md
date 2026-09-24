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

### K2 — nested writer fails fast instead of hanging

The spec's claim, measured before the fix. `tests/test_concurrency.py::
test_nested_writer_transaction_fails_fast` run against `a258537` in
`$TMPDIR/rt84-lab` (no `_writer_owner` in that tree's `db.py` — the script
greps for it and says so):

```
E  AssertionError: вложенный вызов висит дольше 5.0 с: ошибку программиста
   лок превращает в зависание процесса
1 failed in 5.11s
```

The hang is real: measured as a thread that never returns within 5 s. By code
reading the park point is `with _writer_lock:` — the thread waits on a lock the
same thread holds, with `BEGIN IMMEDIATE` already open on its connection.
Nothing in the log would have shown it — only the test's 5-second ceiling turns
it into a red.

Fix in `rusterm/store/db.py`: `_writer_owner = threading.local()`, and
`writer_transaction` compares `threading.get_ident()` against the recorded
owner **before** taking the lock, raising the named error:

```
RuntimeError("writer_transaction уже открыт в этом потоке: вложенная
              транзакция невозможна, SQLite не умеет вложенный BEGIN")
```

The owner slot is cleared in `finally`, so the same thread re-enters the door
normally once the outer transaction is over. `RLock` was deliberately not used:
it would admit the nested `BEGIN IMMEDIATE` and SQLite would answer «cannot
start a transaction within a transaction» — the same programmer error, reported
one layer further from its cause and without naming the door.

What the test pins, clause by clause:

| check in the test | «Done when» clause |
|---|---|
| worker thread returns within 5 s | fails fast |
| `isinstance(result, RuntimeError)` + `"writer_transaction" in str(result)` | raises the named `RuntimeError` |
| neither `K2-outer` nor `K2-in` survives in `issuer` | the nested call leaves no half-written transaction |
| a fresh thread writes `K2-after` within 1 s | the lock is free afterwards |

Nesting is produced through the product's own door — `upsert_issuer` called
inside an outer `writer_transaction` — rather than by hand-writing two `BEGIN`s,
because that is how a real caller reaches it. The worker opens its own
connection, measured rather than assumed: a probe that opens the connection in
the main thread and enters `writer_transaction` in a worker gets
`ProgrammingError: SQLite objects created in a thread can only be used in that
same thread` — the lock under test would never have been reached.

Before trusting this change with 51 write doors, checked who nests:
`grep -c 'with writer_transaction(' rusterm/store/repos.py` → **51** (50 on
`self.conn`, one — `persist_ingestion_results` — on a bare `conn`), and the
same grep across `rusterm/` lists no other file: nothing outside the store
opens the door. An AST scan of `rusterm/**/*.py` for calls of any
`self.<repo>.…` inside a `with writer_transaction(...)` body found **0** —
bodies only do `c.execute(...)`. So no product path nests today: the new error
is a guard rail, not a live break. Full suite with the change:
`1309 passed, 5 skipped, 20 deselected, 4 xfailed, 3 warnings in 673.38s
(0:11:13)` — no regression from the `db.py` edit; the file alone:
`2 passed in 1.26s`.

### K2, postscript — the item's first commit was red, and how it was caught

`bf7bf68` carried the test but not the fix. The per-item committer
(`/tmp/rt84-staging/commit_item.sh`) staged `agent/` and `tests/` only — it was
written for K1, which touched no source — so `rusterm/store/db.py` stayed in the
working tree: P3 («leave nothing outside git») breached, and the pushed HEAD was
red for its own new test. Measured in a clean worktree at that commit:

```
git worktree add --detach "$TMPDIR/rt84-head" bf7bf68
cd "$TMPDIR/rt84-head" && python3 -m pytest tests/test_concurrency.py
1 failed, 1 passed in 6.49s
```

The round's own guard could not see this: `agent/acceptance.sh` runs pytest
against the working tree, which still held the unstaged fix, so the hook printed
`Итог: пройдено 13, провалено 0` for a commit whose tree fails. The hole is in
the check and not in this item's code, so entry 2 of the disputed list below
carries the ask; `acceptance.sh` itself is off-limits here.

Repaired by the follow-up commit that lands `db.py` (this one). Published
history was not rewritten: `bf7bf68` stays where the coordinator can read what
went wrong. The committer now stages tracked modifications in `rusterm/` too
(`git add -u agent/ rusterm/ tests/`), so an item that edits source cannot be
committed half-way again.

## Blocked

none

## What not to trust
* The K2 guard is per-thread and per-process. Two connections nested on one
  thread now raise; one transaction nested across *threads* still just queues on
  the lock, which is correct serialisation and not what K2 covers. Nothing
  protects a caller that catches the `RuntimeError` and retries — `grep` says no
  such caller exists, but the guard cannot enforce that.
* K2's rollback proof covers the `issuer` rows the test itself writes. It says
  nothing about WAL side effects after a nested failure — `PRAGMA integrity_check`
  under a real mixed workload is K6/K7's job, and K2 must not be read as
  covering it.

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

2. K2's postscript is the evidence: `agent/acceptance.sh` step 3 (`pytest
   целиком`) and the pre-commit hook both run against the **working tree**, so a
   commit that leaves a fix unstaged still prints `Итог: пройдено 13, провалено
   0` — measured: `bf7bf68` checked out clean is `1 failed, 1 passed`, while at
   that same commit the hook said 13/0. Ask: should the hook verify the *commit*
   instead — run the suite in a throwaway checkout of the staged tree, or refuse
   when `git diff --cached` and `git diff` disagree? Not fixed here:
   `acceptance.sh` is never edited (it is diffed against `origin/main`), and the
   guard scripts around it belong to the coordinator.

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

| 10 | `bash /tmp/rt84-staging/k2_red.sh` — файл K1 + блок K2, worktree `$TMPDIR/rt84-lab` на `a258537`, правки нет | `1 failed in 5.11s` — `вложенный вызов висит дольше 5.0 с: ошибку программиста лок превращает в зависание процесса`; `grep -n "_writer_owner" rusterm/store/db.py` → no match, то есть дерево действительно до починки |
| 11 | проба: то же соединение, открытое в main, входит в `writer_transaction` из рабочего потока | `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` (лог `/tmp/rt84-staging/k2-probe.log`; вторая строка пробы упала — у `sqlite3.Connection` нет атрибута `check_same_thread`, так что значение по умолчанию документировано, а не прочитано) |
| 12 | `python3 /tmp/rt84-staging/apply_k2.py rusterm/store/db.py`, блок добавлен, `ast.parse` обоих файлов | `правка K2 внесена`, `syntax ok`, `git diff --stat` → `2 files changed, 118 insertions(+)` |
| 13 | `python3 -m pytest tests/test_concurrency.py` (клон, после правки) | `2 passed in 1.26s` |
| 14 | `grep -c 'with writer_transaction(' rusterm/store/repos.py`, тот же греп по `rusterm/`, AST-обход тел транзакций | 51 сайт (50 на `self.conn`), других файлов греп не нашёл, `кандидатов на вложенную запись: 0` |
| 15 | `python3 -m pytest -p no:cacheprovider` (полный прогон после правки лока) | `1309 passed, 5 skipped, 20 deselected, 4 xfailed, 3 warnings in 673.38s (0:11:13)` |
| 16 | `bash /tmp/rt84-staging/commit_item.sh K2 …` (первый коммит пункта) | hook `Итог: пройдено 13, провалено 0` → `bf7bf68`; но `git status` после него — `M rusterm/store/db.py`: правка осталась вне коммита |
| 17 | `git show --stat bf7bf68`; `git show HEAD:rusterm/store/db.py`, `grep -c _writer_owner` там и в рабочем дереве | в коммите `agent/REPORT-84.md`, `agent/STATE.json`, `tests/test_concurrency.py` без `db.py`; счётчик: HEAD → `0`, дерево → `4` |
| 18 | `git worktree add --detach "$TMPDIR/rt84-head" bf7bf68` и `python3 -m pytest tests/test_concurrency.py` в нём | `1 failed, 1 passed in 6.49s` — запушенный HEAD красен для собственного теста K2; полный прогон над ним же — `1309 passed`, то есть сломан только новый тест, а не сборка |
| 19 | первая попытка коммита починки (`commit_item.sh K2 …msg-k2fix.txt`) | хук отклонил: `FAILED tests/test_report_sections.py::test_disputed_lines_live_only_in_disputed_section` — постскриптум начинал строку со слова Disputed; `commit exit=1`, `git log` не изменился. Правка текста + повторный прогон `tests/test_report_sections.py`: `28 passed in 1.05s` |

## HANDOFF

Status: WORKING — круг 119 идёт, K1 и K2 закрыты коммитами; K2 — двумя,
первый был красным (см. постскриптум и Disputed 2).

Items done: приём круга (STATE + отчёт), K1, K2.
Items not done: K3, K4, K5, K6, K7, K8 — очередь ТЗ-84, по одному коммиту
на пункт.

Network: 0 requests spent. LLM calls: 0.
First finding for the coordinator: entry 1 of `## Disputed` — with
`_writer_lock` removed, K1 stays green, so I14's wording is about latency and
nesting, not about lost writes.
NOW: K3, step 1
