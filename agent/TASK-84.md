# TASK-84 — concurrent writers: the lock is claimed, now prove it

- **Status: READY**
- **Report:** `agent/REPORT-84.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-84.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Stop:** day round — by the list; night round — PROTOCOL §10.
- **Budgets:** network 0. LLM 0.
- **How to work:** as TASK-82. Red-before-fix rule of TASK-82 applies.

## Where we are

- `rusterm/store/db.py`: `_writer_lock = threading.Lock()` (per
  process), `writer_transaction` = lock + `BEGIN IMMEDIATE`; WAL;
  `timeout=30`. All 51 writes in `repos.py` go through it.
- Real concurrency exists: desktop `_CollectWorker(QThread)` writes
  while the UI thread may write; CLI and desktop can run on one root at
  once; `create_backup` does `VACUUM INTO` and walks `raw/` while ingest
  may be writing.
- **No test drives two writers at once.** Invariant I14 is asserted by
  reading code, not by running it.
- `threading.Lock` is not re-entrant: a nested `writer_transaction` on
  one thread **hangs forever** instead of failing.

## Fixed decisions

| Question | Rule |
|---|---|
| Hang vs error | every test runs its workers in daemon threads / subprocesses with a hard timeout (thread `join(timeout)`, `subprocess.run(timeout=)`); a timeout is a red, never a wait. |
| Nested writer | must fail fast: `RuntimeError` naming `writer_transaction` (owner tracked via `threading.local` or `threading.get_ident`). Not `RLock` — SQLite cannot nest `BEGIN`. |
| Where | new `tests/test_concurrency.py`; `tmp_path` roots only (`test_no_shared_tmp` holds). No Qt: drive `desktop_actions` directly. |
| Flakiness | each test must pass 20 runs in a row: `for i in $(seq 20); do python3 -m pytest tests/test_concurrency.py -q || break; done` — the count in the report. |

## K1. Two threads, one base

Two threads, own connections, 200 `writer_transaction`s each through a
real repo write.

**Done when:** exact row count; no `OperationalError`; < 30 s; green.

## K2. Nested writer fails fast

**Done when:** nested call raises the named `RuntimeError` within 5 s;
the lock is free afterwards (another thread writes within 1 s); green.

## K3. Exception inside releases everything

**Done when:** a raise inside `writer_transaction` → ROLLBACK (row
absent) and a second thread's transaction starts within 1 s; green.

## K4. Two processes

`init` + `add` two instruments, then two `rusterm ingest --source
synthetic` subprocesses on the same root at once, 5 repetitions.

**Done when:** both exit 0 every time; stderr never contains
`database is locked`; fact counts equal the sequential run's; green.

## K5. Reader never sees half a transaction

Writer inserts batches of 100 in one transaction; reader (WAL, own
connection) polls the count.

**Done when:** every observed count is a multiple of 100; green.

## K6. Desktop collect under a UI write

`desktop_actions.collect_synthetic` in a thread; main thread adds and
removes watchlist entries meanwhile; a second run cancelled mid-way via
`CancelFlag`.

**Done when:** both complete; `PRAGMA integrity_check` = `ok`; after
the cancelled run snapshot count is old or old+1, never a half row set;
green.

## K7. Backup during ingest

**Done when:** `create_backup` while an ingest thread writes → archive
restores via `restore_backup` into a fresh root, `PRAGMA
integrity_check` = `ok`, schema version = `_SCHEMA_VERSION`, every
manifest member present; green. If a half-written raw file can enter
the archive — fix, and say how.

## K8. Close

**Done when:** 20/20 loop shown; `bash agent/acceptance.sh` green;
`git diff <base>..HEAD -- tests/ | grep -c '^-.*assert'` → 0.
