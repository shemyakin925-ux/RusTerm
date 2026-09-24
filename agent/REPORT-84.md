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

### K3 — an exception inside the door releases everything

Done when, verbatim: «a raise inside `writer_transaction` → ROLLBACK (row
absent) and a second thread's transaction starts within 1 s». No product change
was needed: this item is the first executable proof of the second half of the
door's own docstring («при исключении — ROLLBACK»), which until now was only
asserted by reading `db.py`.

Two tests, because the door fails in two different ways:

| test | how the failure is produced | what it pins |
|---|---|---|
| `test_raise_inside_transaction_rolls_back_and_frees_lock` | hand-opened `writer_transaction`, one `INSERT`, then `raise _K3Boom` — a type that is **not** `sqlite3.Error`, so the generic `except Exception` branch runs | the same type escapes the door; the row is absent; a fresh writer writes within 1 s; after the release only that writer's row exists |
| `test_repo_integrity_error_releases_everything` | no hand-rolled SQL at all: `repos.instrument.upsert_instrument` under a dangling `issuer_id`, which `PRAGMA foreign_keys=ON` turns into `IntegrityError` inside the repository's own door | `sqlite3.IntegrityError` escapes; no row survives; a fresh writer writes within 1 s |

The design point that decided the test's value: **the failing connection is
held open while the second writer is tried** (`_fail_and_hold`). `close()` in
sqlite3 rolls an unfinished transaction back by itself, so if the first thread
closed before the check, the test would pass with `ROLLBACK` removed — a green
that proves nothing. Measured, in `$TMPDIR/rt84-lab` at `7966097`:

| run | output |
|---|---|
| baseline, K3 only | `2 passed, 2 deselected in 0.07s` |
| mutation C: `conn.execute("ROLLBACK")` → `pass` | `2 failed, 2 deselected in 2.16s` |
| after `git checkout -- rusterm/store/db.py` | `МУТАЦИЯ=0`, `2 passed, 2 deselected in 0.06s` |

The mutation's message is the interesting part:

```
AssertionError: писатель не вошёл за 1.0 с (ошибки: []) — отказавшая
транзакция оставила замок занятым
```

Empty error list, not `database is locked`: the second writer is parked inside
sqlite3's busy-retry (`timeout=30` in `open_connection`), still hoping the
aborted transaction will end. That is what a missing ROLLBACK does to a process
— it does not error, it stalls, and only the 1-second ceiling of the test makes
it visible.

A finding on the way, in the other direction: the first draft of K3 called a
repository method inside an outer `writer_transaction`, and what came out was
K2's new error, not the intended exception:

```
AssertionError: из транзакции должен выйти тот же тип, что брошен, получено
RuntimeError: RuntimeError('writer_transaction уже открыт в этом потоке:
вложенная транзакция невозможна, SQLite не умеет вложенный BEGIN')
```

So K2's guard is confirmed reachable through a product door (`upsert_instrument`
→ `writer_transaction`), not only through the hand-built nesting in K2's own
test. The draft was rewritten to keep transaction bodies free of repository
calls — which is also what the AST scan says about the product.

Cost of the whole file after K3: `4 passed in 0.16s`, slowest call — K1's 400
concurrent transactions at 0.08 s.

### K4 — two processes on one base: the recipe self-serialises, so the race window had to be widened

The item's recipe, run as written (probes `/tmp/rt84-staging/k4_probe.py`,
`k4_probe2.py`; 5 fresh roots, `init` + offline `add` of two instruments, then
two `ingest --source synthetic` subprocesses at once): both exit 0 every time,
`database is locked` never appears, and each root ends with `fact 6, job 2,
raw_object 2, source_cursor 1, coverage 4`. The processes really do run
together — lifetime 0.116-0.121 s each, overlap 0.115-0.120 s, spawn skew
0.7-0.9 ms.

Teeth run on that first draft (lab at `0768c79`, `bash
/tmp/rt84-staging/k4_teeth.sh`) — **all three mutations stayed green**:

| mutation | result | what that says |
|---|---|---|
| A: `open_connection(timeout=30)` → `0.001` | `1 passed, 4 deselected in 3.14s` | no writer ever had to wait for the write lock |
| B: `job.enqueue` re-raises `IntegrityError` instead of returning `False` | `1 passed, 4 deselected in 3.11s` | the second process never attempted a job key |
| C: `_writer_lock` → no-op context manager | `1 passed, 4 deselected in 3.04s` | cross-process writes are serialised by SQLite, not by the in-process lock (same reading as K1, Disputed entry 1) |

Measured cause: `source_cursor` is keyed by `(provider, index_kind)` — one row
per source for the whole base, not per instrument
(`rusterm/store/repos.py:1334, 1340`) — and the job idempotency key is
`f"{provider_name}:{rec.url}"`, with no instrument in it (`rusterm/pipeline.py:164`,
written at `:158`).
So the loser of the cursor race polls an already-advanced index, gets 0 records
and writes only the cursor row back: its line read
`US-K4B: заданий закрыто: 0; фактов: 0`. Two "concurrent" processes were one
writer plus one near-reader, which is why A and B could not be seen.

Widening the window: `tests/k4_stub/sitecustomize.py` (tracked, added to this
commit) patches `SyntheticDisclosuresProvider.poll_index` to sleep **after**
the source returns its index and **before** the pipeline commits the cursor, so
both processes hold the same stale cursor at the same moment. It is inert
unless `RUSTERM_K4_POLL_PAUSE` is set, and no product step is substituted: the
same parse, validation, raw store, canonical mapping and persist run in both
processes. The precedent for a `sitecustomize` in a subprocess test is
`tests/e2e_stub/` (TASK-11 X1).

With the pause, A and B go red — at `0768c79`, same script:

```
A: AssertionError: US-K4B: код 2 вместо 0, stderr: …
   File "rusterm/store/repos.py", line 1341, in set_cursor
     with writer_transaction(self.conn) as c:
   File "rusterm/store/db.py", line 830, in writer_transaction
     conn.execute("BEGIN IMMEDIATE")
   sqlite3.OperationalError: database is locked
   1 failed, 4 deselected in 4.62s
B: AssertionError: US-K4B: код 2 вместо 0, stderr: …
   File "rusterm/store/repos.py", line 1282, in enqueue
   sqlite3.IntegrityError: UNIQUE constraint failed: job.idempotency_key
   1 failed, 4 deselected in 2.72s
C: 1 passed, 4 deselected in 6.38s
baseline: 1 passed, 4 deselected in 6.62s
```

A fails on the *cursor write* — that is the collision the item is about: two
real OS processes inside `writer_transaction` for the same row at the same
time, absorbed by the 30 s busy timeout the product sets. B proves the work
itself is contended: both processes reach `enqueue` for the same idempotency
keys, and the dedup branch is what keeps the loser's exit code 0.

What the shipped test asserts, per repetition (5, order alternated) against a
sequential baseline built the same way in the same test: exit 0 for both, no
`database is locked`, no `Traceback` in either stream, process lifetimes
overlapping, `fact`/`job`/`raw_object` counts equal to the baseline,
`PRAGMA integrity_check` = `ok`; and `baseline["fact"] > 0`, because an empty
baseline would make "equal counts" vacuous.

Distribution over instruments is deliberately **not** asserted — measured, not
assumed. 30 repetitions of the pair without the pause: 29 times the
first-spawned process stored the 6 facts, once the second; every root ended
`fact 6, job 2, raw_object 2`. 30 repetitions with the pause: same totals in
all 30, `coverage 4`, one issuer holding all six facts, integrity `ok` each
time. `coverage` stays out of the comparison because its rows hang off whichever
instrument did the work — if the two documents ever split between the two
processes, `coverage` would double while `fact` stays 6, and that is a legal
outcome the totals comparison must not reject.

Network stayed 0: `add` is given both `--cik` and `--name`, which is the
offline form (`cmd_add` only resolves the ticker through a provider when one of
them is missing, `rusterm/cli/__init__.py:1440`). Roots are `tmp_path`, every
call carries `--root`, `RUSTERM_ENV_FILE` points at a nonexistent file, and
PYTHONPATH points at this clone — P7.

Runs: `python3 -m pytest tests/test_concurrency.py` → `5 passed in 6.64s`; the
K4 test alone five times → `6.40s, 6.51s, 6.68s, 6.68s, 6.60s`, all
`1 passed, 4 deselected`.
### K5 — the reader never sees half a batch, and the control run proves the poll can

Spec: writer inserts batches of 100 in one transaction; a reader on its own
connection polls the count; done when every observation is a multiple of 100.
`tests/test_concurrency.py::test_reader_sees_only_whole_batches`, helper
`_poll_batches(root, prefix, atomic)`.

A green "every observation is a multiple of 100" is worth nothing unless the
poll can *see* a non-multiple, so the test runs the same geometry twice: the
writer commits per row (control), then per batch (the property). Measured with
`python3 /tmp/rt84-staging/k5_probe.py`:

| run | wall | observations | distinct counts | non-multiples |
| --- | --- | --- | --- | --- |
| control, one transaction per row | 0.75 s | 51 194 | 501 (every value 0…500) | **495** values, 1…499 |
| batches of 100 | 0.15 s | 7 941 | 6 — 0, 100, 200, 300, 400, 500 | **0** |

Same reader, same database, same rate of asking: when the writer publishes a
row at a time the reader catches 495 of the 499 intermediate states, and when
it publishes a batch at a time not one of 7 941 observations lands inside a
batch. All six plateaus appear in the atomic run, so the reader was watching
while the writer worked rather than after it.

Why raw `INSERT`s instead of a repository door: the assertion is about the
transaction boundary, and a repository method would open its own transactions
inside the batch — the writer would no longer be the one the item describes.
`PLATEAU = 0.02` exists so that the "100 rows visible" state lasts 20 ms
instead of microseconds; `MIN_OBSERVATIONS = 50` and the `reached` event (set
by the reader itself on seeing row 500) refuse a green run in which the reader
simply finished early.

Teeth (`k5_teeth.sh`, `k5_teeth2.sh`, `k5_teeth3.sh`, lab detached at
`c476283`, `rusterm/store/db.py` restored after each step and verified
`МУТАЦИЯ=0`):

| mutation | result | reading |
| --- | --- | --- |
| none | `1 passed, 5 deselected in 0.88s` | — |
| D: `PRAGMA journal_mode=WAL` → `DELETE` (db.py:801) | `1 passed, 5 deselected in 1.54s` | **green.** The property does not come from WAL: in rollback-journal mode uncommitted rows never reach the main DB file either. Only the cost changed — +0.66 s for the same work. |
| E: `BEGIN IMMEDIATE` → `BEGIN` (db.py:830) | `1 passed, 5 deselected in 0.86s` | **green**, and expected: deferred start changes who loses when two writers meet (K1, K4), not when a transaction becomes visible. |
| F: `COMMIT` removed from `writer_transaction` (db.py:832) | `1 failed, 5 deselected in 0.15s` — `писатель не дописал: ['писатель: IntegrityError: FOREIGN KEY constraint failed']` | red as soon as the door stops publishing: the issuer row of the setup never becomes visible, so the first batch fails its FK check. |
| G: `COMMIT` moved before the body of the `with` | `1 failed, 5 deselected in 0.12s` — `sqlite3.OperationalError: cannot commit - no transaction is active` on the trailing `COMMIT` of the door | red, though for a mechanical reason rather than for a visible half batch. |

D and E staying green is the interesting part, and it is a limit of this item,
not of the fixture: the only thing WAL could be blamed for is the reader
*waiting* for the writer, and that is not a wrong count. Measured directly
(`k5_wal_probe.py`: writer opens a transaction, inserts 100 rows, holds it open
0.4 s; reader polls in a tight loop):

| journal mode | reader observations in the held window | observations that saw the 100 uncommitted rows |
| --- | --- | --- |
| WAL (db.py:801) | 193 175 | 0 |
| DELETE (mutation) | 75 989 | 0 |

(one measurement per mode; the spread between the two runs of the same code
in this file is a few percent, not a factor of 2.5)

So WAL buys the reader 2.5× the polling throughput under an open write
transaction; it is not what keeps half a batch out of view. K5 asserts the
latter and cannot assert the former: a throughput assertion would be a
timing assertion, and the file keeps to properties that survive a slow
machine (the 20-run rule in Fixed decisions).

Runs: `python3 -m pytest tests/test_concurrency.py` → `6 passed in 9.44s`; the K5
test alone ten times in a row → `1 passed, 5 deselected` every time, wall
`0.93, 0.93, 0.94, 0.95, 0.94, 0.95, 0.95, 0.97, 0.95, 0.96` s.

### K6 — the desktop collector and the window's writer, at once, in one process

Spec: `desktop_actions.collect_synthetic` in a thread; the main thread adds and
removes watchlist entries meanwhile; a second run cancelled mid-way via
`CancelFlag`. Done when: both complete; `PRAGMA integrity_check` = `ok`; after
the cancelled run the snapshot count is old or old+1, never a half row set.
`tests/test_concurrency.py::test_desktop_collect_finishes_under_ui_writes` and
`::test_cancelled_desktop_collect_leaves_no_half_snapshot`; helpers `_k6_seed`,
`_k6_paced_providers`, `_k6_ui_churn`, `_k6_progress`, `_k6_snapshots`.

The churn uses three different watchlist doors per round — `new_version` +
`copy_members_except` (the only removal door, ТЗ-62 G2), `add_member`, and
`rollback_to` every fourth round — 12 rounds minimum, extended while the
collector thread is alive (cap `K6_CHURN_MAX_ROUNDS = 120`). This is the pair
I14 names: a collect from the window and the window's own writes, in one
process, through `writer_transaction`.

**Interval overlap was not a check.** The draft asserted only that the two
wall-clock intervals touch, and it gated the churn on `on_stage` — an event the
collector sets *before* its last commit, so `ui_began < collect_end` held by
construction and could not fail. Measured instead, three levers:

| lever | what it forces |
| --- | --- |
| `gate=0` | the UI does not write until the collector's rows are visible to a second connection |
| `running=thread.is_alive` | the UI keeps writing while the collector works, and stops only after it is gone |
| `witnesses` | per UI round: collector progress before the write and after it |

Progress is counted over `job`, `fact`, `raw_object`, `coverage` — tables only
the collector fills (the churn touches `watchlist_*`), so a change in the count
is one of the collector's commits. Measured with `python3
/tmp/rt84-staging/k6_witness.py` (three trials):

| trial | collector commits (wall) | progress steps the UI saw | first round pre/post | final |
| --- | --- | --- | --- | --- |
| 1 | 0.201 s | 2, 9, 14, 18 | 2 / 2 | 18 |
| 2 | 0.309 s | 2, 9, 14, 18 | 2 / 2 | 18 |
| 3 | 0.184 s | 2, 9, 18 | 2 / 2 | 18 |

So the UI's first write landed after the collector's first commit and before
its last (`final 18 > post 2`), and the UI's rounds straddle three or four of
its commits. Every round has `pre == post`: the two writers are never inside
the door at the same instant — commits interleave rather than overlap, which is
what serialising them means (K1, K2). What K6 adds is that both writers'
committed state survives the interleaving: version count equals what the UI
wrote and read back, its last composition equals its own, the snapshot has
measures, `integrity_check` is `ok`.

Teeth (lab detached at `ed8a8bc`; `rusterm/store/db.py` and
`rusterm/desktop/actions.py` restored after every step, marker counted before
the restore; the test file re-copied before every step — the first version of
this script ran `git checkout -- tests/test_concurrency.py`, which silently
deleted the K6 tests from the lab, so steps C and J of that run measured
nothing; see Runs):

| mutation | result | reading |
| --- | --- | --- |
| none | `2 passed, 6 deselected in 1.29s` | — |
| 10 repeats of the pair | `2 passed, 6 deselected` every time, walls 1.17…1.49 s | — |
| H: `BEGIN IMMEDIATE` → `BEGIN` inside `writer_transaction` | `2 failed, 6 deselected in 1.25s` | **red.** First mutation in this file where a deferred begin matters: K5's E ran the same swap against one writer and stayed green. Here the two doors really meet. |
| I: `_writer_lock` → no-op | `2 passed, 6 deselected in 1.53s` | **green** — the third independent measurement that the in-process lock is not what protects the data (K1 finding, K5 E). |
| J: the cancel check after the pipeline removed from `collect_synthetic` | `1 failed, 7 deselected in 0.91s` — `assert result.cancelled` (test_concurrency.py:1059) | **red** — without the check the cancelled run builds a snapshot, the exact half-state Done when forbids. |
| K: `gate` removed from the test | `1 failed, 7 deselected in 0.73s` — `assert all(pre > 0 …)` (test_concurrency.py:960); 10/10 runs red | **red** — without the gate the UI's writes precede the collector's first commit: two sequential writers, which is what the clock assertion used to accept. |
| L: sequential variant — `thread.join()` before the churn | `1 failed, 7 deselected in 0.90s` (test_concurrency.py:951) | **red** — the collector must *end* inside the UI's interval; that half of the clock assertion does carry a constraint. |
| pacing off: `K6_PAUSE = 0`, `K6_CHURN_PAUSE = 0`, gate kept | 10/10 `1 passed, 7 deselected`, 0.35…0.82 s | green: on this machine the pauses buy margin, not correctness — gate, `running` and the witnesses do the work. |

The cancelled half is honest about its own limit. After the first collect the
store holds `job 2 / fact 6 / raw_object 2 / coverage 8`; the second, cancelled
collect leaves Δ = 0 on all four and 0.058 s of wall (`k6_probe2.py`) — the jobs
dedupe and the cancel lands before the snapshot. So that test's concurrency
witness is structural (the churn runs while the worker lives and ends after it)
rather than two interleaved commit sequences, and what it proves is the
Done-when itself: `result.cancelled`, `snapshot_id is None`, snapshot count
unchanged, versions a gapless set, every snapshot with measures, `integrity_check`
`ok`.

Runs: `python3 -m pytest tests/test_concurrency.py` in the clone → `8 passed in 8.36s`.
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
* K3 measures the same-process door only. Its «second writer gets in» is about
  `_writer_lock` and SQLite's write lock inside one process; across processes
  there is no `_writer_lock` at all, and that is K4's question, not K3's answer.
* The `ошибки: []` in K3's mutation run is read as «the second writer is busy
  waiting», which is the only reading consistent with `timeout=30` and a 1 s
  ceiling — but it was not traced with a debugger, so the mechanism sentence in
  the K3 section is inference from the timing, and the timing is the measurement.

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

* K4's green is a green *with* a widened race window. The item's recipe as
  written cannot contend: `source_cursor` is one row per source for the whole
  base and the job key is `provider:url`, so the second process usually polls an
  already-advanced index and writes nothing but the cursor (measured: mutations
  A and B green, `1 passed` each). The shipped test therefore pauses the demo
  index in a `sitecustomize` stub. That is an artificial widening: what K4
  proves is «two processes whose writes collide by construction behave
  correctly», not «collisions are this frequent in the field».
* Mutation C in K4 (per-process `_writer_lock` replaced by a no-op) stayed green
  a second time, in a second scenario. Read narrowly: K4 does not test the
  in-process lock, only SQLite's cross-process serialisation plus the 30 s busy
  timeout. Read broadly: this is the second independent measurement that says
  the lock is not what prevents lost writes — see Disputed entry 1, which is
  now backed by two items, not one.

- K5 does not show that WAL is what hides a half batch: with mutation D
  (`journal_mode=DELETE`) the test is green, and in the same measurement the
  reader sees no uncommitted rows in either mode. What WAL demonstrably buys
  is that the reader need not wait for the writer (193 175 polls against
  75 989 during one held transaction) — that is a rate, so the file does not
  assert it.

* K6's watchlist checks compare the UI with itself. The collector writes only
  `job`/`fact`/`raw_object`/`coverage`/`snapshot`/`measure`, never `watchlist_*`,
  so «version count equals what the UI wrote» and «last composition equals the
  UI's own read-back» prove that the churn survived the interleaving, not that
  the two writers agree on a shared table. What they genuinely share is the
  door and the file — and the collector's commits are witnessed mid-churn
  (progress 2 → 9 → 14 → 18 while the UI writes), so the concurrency is real;
  the row-level cross-check between the two is not there to be had.
* The cancelled second collect commits nothing new: measured Δ = 0 on all four
  progress tables in 0.058 s (`k6_probe2.py`), because the jobs dedupe and the
  cancel lands before the snapshot. Its overlap claim is therefore structural
  (the churn runs while the worker lives, and ends after it) rather than two
  interleaved commit sequences — read that test as the Done-when check
  (`cancelled`, `snapshot_id is None`, count unchanged, gapless versions,
  `integrity_check ok`), which is what it asserts.
* `pre == post` in every UI round is read as «commits interleave, never overlap
  inside the door». That is inference from a progress counter over four tables,
  not a trace of the lock — K1's and K2's direct measurements of the door are
  the evidence, and K6 only shows the pairing does not lose either writer's
  work.
* The pauses are margin, not correctness, on this machine: with `K6_PAUSE = 0`
  and `K6_CHURN_PAUSE = 0` and the gate kept, the gated test passed 10/10
  (0.35…0.82 s). The reverse risk is a false red: if a slower machine let the
  collect finish inside one UI round, `final > witnesses[0][1]` (test_concurrency.py:964)
  would fail on timing, not on a lost write. K8's 20-run loop is the bound
  being put on that claim.

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

3. K4's «Done when» is satisfiable by a run in which only one process ever
   writes, and the two checks that would catch a broken writer (busy timeout,
   job dedup) stay green on the recipe as specified. The item reaches its
   intent only after the race window is widened from outside the product (the
   `tests/k4_stub` pause), and even then the *work* never splits: 30/30
   repetitions left all six facts with one issuer. Ask: for K6/K7 and future
   rounds, prefer a source whose cursor and idempotency key carry the instrument
   (or a stub feed with two distinct URLs), so two `ingest` processes contend
   for different rows and the totals comparison is forced rather than lucky.
   Not changed here: `source_cursor`'s key and the job key are product design
   (and TASK-84 authorises no `agent/CONTEXT.md` or provider edits), so the
   finding is filed instead of fixed.

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
| 20 | чистый worktree на `7966097`: `git worktree add --detach "$TMPDIR/rt84-head" …` + `python3 -m pytest tests/test_concurrency.py` | `правка в дереве коммита: 4`, `2 passed in 0.11s` — HEAD после починки зелёный сам в себе |
| 21 | первая версия K3: репозиторий внутри внешней транзакции | `1 failed, 2 passed in 1.57s` → `получено RuntimeError: 'writer_transaction уже открыт в этом потоке…'`: защиту K2 поймал живой вложенный вызов; тест переписан |
| 22 | проба ошибки продукта: `upsert_instrument` под несуществующий эмитент | чужое соединение → `ProgrammingError: SQLite objects created in a thread…`; своё соединение → `IntegrityError: FOREIGN KEY constraint failed`, `строк instrument: 0` — тип из пробы, а не из догадки |
| 23 | `python3 -m pytest tests/test_concurrency.py --durations=3` (после v2) | `4 passed in 0.16s`; call: K1 `0.08s`, K2 `0.01s`, K3-репозиторий `0.01s` |
| 24 | `bash /tmp/rt84-staging/k3_teeth.sh` (лаборатория на `7966097`; первая попытка молча осталась на `b1d0890`, потому что `checkout` без `--force` прервался на изменённом файле) | baseline `2 passed, 2 deselected in 0.07s`; мутация C `2 failed, 2 deselected in 2.16s` с `писатель не вошёл за 1.0 с (ошибки: [])`; после восстановления `МУТАЦИЯ=0`, `2 passed, 2 deselected in 0.06s` |
| 25 | `python3 /tmp/rt84-staging/k4_probe.py` — рецепт K4 как написан: init + два `add` + две пары ingest, затем ещё три повтора | коды `0/0` во всех прогонах, `locked в stderr: False`, `фактов всего: 6`; строка второго процесса — `US-K4B: заданий закрыто: 0; фактов: 0` |
| 26 | `python3 /tmp/rt84-staging/k4_probe2.py` — те же пары, но свежая база на повтор, с замером времени жизни процессов | overlap `0.115-0.121` с из жизни `0.116-0.121` с, разброс запуска `0.0007-0.0009` с, строки `{'fact': 6, 'job': 2, 'raw_object': 2, 'source_cursor': 1, 'coverage': 4}` пять раз подряд, `2.5 с` на пять повторов |
| 27 | `bash /tmp/rt84-staging/k4_teeth.sh` на первом варианте теста (без паузы), лаборатория на `0768c79` | baseline `1 passed in 3.22s`; мутация A `1 passed in 3.14s`; мутация B `1 passed in 3.11s`; мутация C `1 passed in 3.04s`; после каждой — `МУТАЦИЯ=…:0` |
| 28 | причина blindness: `grep -n 'key = f' rusterm/pipeline.py`, `grep -n "def get_cursor" rusterm/store/repos.py` и та же пара для `set_cursor` | `164: key = f"{provider_name}:{rec.url}"`; `source_cursor` выбирается парой `(provider, index_kind)` — repos.py:1334, 1340, инструмента в ключе нет |
| 29 | `python3 /tmp/rt84-staging/k4_probe3.py` — 30 пар без паузы, очерёдность чередуется | исходы: `(первым запущенный, 6, 0)` 14 + 15 раз, `(первым запущенный, 0, 6)` 1 раз; `assert fact==6 and job==2` выдержал все 30; `14.6 с` |
| 30 | `tests/k4_stub/sitecustomize.py` + пауза 0.4 с: `python3 -m pytest tests/test_concurrency.py -k two_ingest`, затем тот же `k4_teeth.sh` | тест зелёный (`1 passed, 4 deselected in 6.57s`); мутация A краснеет на `set_cursor` → `sqlite3.OperationalError: database is locked` (`1 failed in 4.62s`), мутация B — на `enqueue` → `IntegrityError: UNIQUE constraint failed: job.idempotency_key` (`1 failed in 2.72s`), мутация C зелёная (`1 passed in 6.38s`) |
| 31 | `python3 /tmp/rt84-staging/k4_probe5.py` — 30 пар с паузой | `30x ((0, 6), 6, 2, 2, 4, 1, 'ok')`: шесть фактов у одного процесса, `fact 6 / job 2 / raw_object 2 / coverage 4`, один эмитент, `integrity ok`, `29.1 с` |
| 32 | `python3 -m pytest tests/test_concurrency.py` и пять прогонов одного теста K4; `python3 -m pytest tests/test_report_sections.py -k "report or guard"` | `5 passed in 6.64s`; K4 отдельно — `1 passed` за прогоны `6.40 / 6.51 / 6.68 / 6.68 / 6.60` с; защита отчёта на изменённом дереве — `28 passed in 0.92s` |
| 33 | `python3 -m pytest tests/test_concurrency.py -k reader` (первый прогон нового теста) | `1 passed, 5 deselected in 0.88s` |
| 34 | `bash /tmp/rt84-staging/k5_teeth.sh` (лаборатория на `c476283`) | baseline `1 passed in 0.88s`; мутация D (WAL → DELETE) `1 passed in 1.54s`; мутация E (`BEGIN IMMEDIATE` → `BEGIN`) `1 passed in 0.86s`; после каждого шага `МУТАЦИЯ=0`; остальные пять тестов `5 passed in 6.55s` |
| 35 | `bash /tmp/rt84-staging/k5_teeth2.sh` — попытка убрать `COMMIT` заменой строки по всему `db.py` | мутация F не применилась (`AssertionError: строка COMMIT встречается 2 раз`), поэтому строка «мутация F» в том логе — на самом деле второй baseline (`1 passed in 0.96s`); вторая попытка, G, зелёной не вышла: `1 failed in 0.12s` (`cannot commit - no transaction is active`) |
| 36 | `bash /tmp/rt84-staging/k5_teeth3.sh` — F только внутри двери (замена в хвосте `def writer_transaction`) | `1 failed, 5 deselected in 0.15s` с `писатель не дописал: ['писатель: IntegrityError: FOREIGN KEY constraint failed']`; после восстановления `1 passed, 5 deselected in 0.94s` |
| 37 | `python3 /tmp/rt84-staging/k5_probe.py` (что именно видел читатель) и `k5_wal_probe.py` — в клоне и в лаборатории с мутацией D | контроль: 51 194 наблюдения, 501 различный счётчик, 495 не-кратных (1…499); пачками: 7 941 наблюдение, 6 значений (0…500 шагом 100), 0 не-кратных; держимая транзакция 0.4 с — 193 175 запросов под WAL и 75 989 под DELETE, незакоммиченной пачки не видно ни там ни там |
| 38 | `python3 -m pytest tests/test_concurrency.py` и десять прогонов одного теста K5 | `6 passed in 9.44s`; K5 — `1 passed, 5 deselected` десять раз подряд, wall `0.93 / 0.93 / 0.94 / 0.95 / 0.94 / 0.95 / 0.95 / 0.97 / 0.95 / 0.96` с |
| 39 | `python3 -m pytest tests/test_report_sections.py` — до `git add` и после него | без индекса `1 failed, 27 passed in 1.92s` (`пункты ['K5'] … коммита круга с реализацией … не найдено`), после `git add` — `28 passed in 1.76s`: L3 прощает объявление «сделано», только если в индексе есть файл не из `tests/` |
| 40 | правка собственного промаха круга: `git diff --cached -- agent/REPORT-84.md \| grep -n "K4's «Done when»"` | запись 3 из «## Disputed» коммитом `c476283` уехала в конец файла (паттерн вставил её после `## HANDOFF`) и рядом осталась строка-дубль `NOW: K4, step 1`; перенесена в раздел, дубль удалён; ссылка `cli/__init__.py:1436` в разделе K4 исправлена на `:1440` (проверено `sed -n '1440p'`) |
| 41 | `bash /tmp/rt84-staging/k6_teeth.sh` — первая версия скрипта о зубах | часть прогона ничего не измерила: скрипт в конце каждого шага делал `git checkout -- tests/test_concurrency.py`, а файл K6 в лаборатории был только скопирован (не в коммите), поэтому мутации C и J прогнались по файлу без тестов K6 (`6 deselected in 0.04s`), и печать `МУТАЦИЯ=…:0` стояла уже после откатa. Выводы этого лога в отчёт не взяты |
| 42 | `bash /tmp/rt84-staging/k6_teeth2.sh` (лаборатория на `ed8a8bc`; тест копируется заново перед каждым шагом, маркер печатается до откатa) | baseline `2 passed, 6 deselected in 1.29s`; десять прогонов пары — `2 passed, 6 deselected` все десять, wall 1.17…1.49 с; весь файл `8 passed in 30.39s`; мутация «B» скрипта (`BEGIN IMMEDIATE` → `BEGIN`, в отчёте — H) `2 failed, 6 deselected in 1.25s`; «C» (`_writer_lock` → no-op, в отчёте — I) `2 passed, 6 deselected in 1.53s`; `gate=None` `1 failed, 7 deselected in 0.73s`; без пауз (`K6_PAUSE = 0`, `K6_CHURN_PAUSE = 0`) — `1 passed, 7 deselected` десять раз, 0.35…0.82 с; выключенные свидетели (`assert True or all(pre > 0 …)`) — `1 passed` пять раз; после всех шагов `8 passed in 31.81s` и `git status --porcelain` пусто. Первая строка лога — артефакт скрипта: `$(git -C \"$LAB\" …)` с лишними кавычками дала `fatal: cannot change to` и пустое `лаборатория на:`; `cd "$LAB"` ниже сработал, и в этом же логе есть `HEAD is now at ed8a8bc` — все шаги прошли в лаборатории |
| 43 | `bash /tmp/rt84-staging/k6_teeth3.sh` — дочитать обрезанные `head -6` отказы | J → `tests/test_concurrency.py:1059: AssertionError`, `1 failed, 7 deselected in 0.91s`; снятый gate → `:960`, `1 failed, 7 deselected in 0.73s`, десять прогонов подряд красные (0.57…0.63 с); «последовательно» (churn после `join`) → `:951`, `1 failed, 7 deselected in 0.90s`; весь файл трижды — `8 passed` за 11.82 / 14.28 / 15.19 с; те же шесть тестов без K6 — `6 passed, 2 deselected in 13.30s` |
| 44 | `python3 /tmp/rt84-staging/k6_witness.py`, `k6_probe.py`, `k6_probe2.py` | свидетели: сбор 0.201 / 0.309 / 0.184 с, шаги прогресса 2→9→14→18 (в одной пробе 2→9→18), `pre == post` в каждом раунде, финал 18; отменённый второй сбор — Δ = 0 по `job`/`fact`/`raw_object`/`coverage` за 0.058 с |
| 45 | `python3 -m pytest tests/test_concurrency.py` и `python3 -m pytest tests/test_report_sections.py tests/test_state_report_tracked.py` (клон, K6 установлен) | `8 passed in 8.36s`; защита отчёта и STATE — `29 passed in 1.06s` |

## HANDOFF

Status: WORKING — круг 119 идёт, K1, K2, K3, K4, K5 и K6 закрыты
коммитами; K2 — двумя, первый был красным (см. постскриптум и
запись 2 ниже).

Items done: приём круга (STATE + отчёт), K1, K2, K3, K4, K5, K6.
Items not done: K7, K8 — очередь ТЗ-84, по одному коммиту на пункт.

Open questions for the coordinator: 3 entries below — I14's wording, the hook
validating the working tree instead of the commit, and K4's recipe, which
cannot make two ingest processes contend without a widened race window.
K5 added none: its finding (WAL is not what hides a half batch) is a limit
of the item's own metric, and it is in «What not to trust».

Network: 0 requests spent. LLM calls: 0.
NOW: K7, шаг 1 (бэкап во время инжеста).

First finding for the coordinator: entry 1 of `## Disputed` — with
`_writer_lock` removed, K1 stays green, so I14's wording is about latency and
nesting, not about lost writes. K4's mutation C repeats that measurement in a
two-process setting.
