# TASK-94 — peers actually compared, one snapshot factory, a window that does real work, an archive that restores

- **Status: READY**
- **Report:** `agent/REPORT-94.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-94.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Budgets:** network 0. LLM 0.
- **How to work:** as TASK-90. A precondition that is missing ⇒
  `SKIPPED — <reason>` for that item, next item.
- **Place in queue:** after TASK-93, numeric order. Items are ordered
  by priority; E6 onwards is reserve.

РАЗРЕШЕНО ПРАВИТЬ: agent/p1_rule.sh
РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh

## E1. One snapshot-builder factory

Five call sites build `SnapshotBuilder` by hand: `cli/__init__.py:839`
(refresh), `:932` (snapshot), `:1080` (verify), `:1620` (census),
`desktop/actions.py:105`. The census one passes **no** price,
corporate-action, industry or governance repos, so
`rusterm census --instrument X --rebuild` writes a **new latest
snapshot** whose valuation measures read `missing_data: price_close`
although prices exist — a diagnostic command degrades the user's data
and then reports the degradation as the census.

**Done when:** `make_snapshot_builder(repos, as_of)` in `rusterm/core/`
is the only constructor outside tests (guard test greps
`SnapshotBuilder(`); census `--rebuild` test on a base with a price ⇒
`market_cap` has a value.

## E2. Percentiles reach a real snapshot (depends on TASK-73 T2)

No production call passes `peer_set_version` / `peer_measures` to
`SnapshotBuilder.build` (refresh, snapshot, verify, census, desktop):
pass 2 — the percentiles of ADR-0002 — runs **only in tests**. User
base: 0 peer sets, 0 percentile rows. TASK-73 T2 builds peer sets from
SIC; this item makes them count. Precondition: T2 landed; else
`SKIPPED — TASK-73 T2 not landed`. TASK-90 A3.1 must be in first (the
shadowed `computed` crashes exactly this path).

Rules: the factory of E1 resolves the instrument's latest peer-set
version (approved, or unverified with `peer_set_status='unverified'`);
members' latest ready snapshots supply `(peer_id, measure_id,
concept, value, fresh)`; `fresh` = the member measure's `period_end`
within `_PERIOD_GAP_DAYS` of the instrument's own; the snapshot row
records the version.

**Done when:** e2e test — six instruments in one peer set, snapshots
built through the CLI ⇒ percentile rows with `peer_set_version`;
`rusterm snapshot` prints `перцентилей: N` with N > 0; the desktop peer
screen shows the instrument's percentile.

## E3. The window's chat does not freeze the window

`desktop/window.py:831` calls `ChatSession.ask` on the UI thread (the
comment there admits it). One live answer may take up to 2 × 60 s per
model call (`READ_TIMEOUT`, `RETRY_ATTEMPTS`) times up to six tool
calls. ADR-0004 §3: the UI thread is not blocked.

**Done when:** `ask` runs in a worker with its own connection (the
`_CollectWorker` pattern); an offscreen test with a fake slow client
shows a `QTimer` firing on the UI thread while the answer is pending;
closing the window mid-question neither hangs nor prints
`QThread: Destroyed while thread is still running`.

## E4. The window collects real sources

`desktop/actions.py:42-57` `CLI_LOCKED_SOURCES` /
`CLI_LOCKED_FUNCTIONS`: the real ingest bodies live in the CLI (they
print and return an int), so the window's «Собрать» works only for the
demo instrument (REPORT-C2 Disputed, never resolved).

Rule: move `_ingest_edgar_companyfacts`, `_ingest_twelvedata_prices`,
`_ingest_twelvedata_actions` into `rusterm/core/ingest.py`, returning
an outcome value (counts, requests, reason); the CLI prints it, the
window's worker calls it. `cvm`, `asx`, `ownership` the same way if
time remains, each named in the report.

**Done when:** `CLI_LOCKED_FUNCTIONS` shrinks by the moved names;
a desktop test with injected transports collects an AAPL-like payload
and builds a snapshot; the CLI output of the moved commands is
byte-identical in the existing tests.

## E5. An archive that restores the whole working state

- `store/backup.py` archives `rusterm.db`, raw manifests and raw
  objects — not `logs/audit.jsonl` (the audit that «переживает потерю
  базы»), not `config.toml` (host-limit overrides), not
  `golden_proposals.jsonl` (written by `verify`).
- `restore --force` writes `rusterm.db` next to a live
  `rusterm.db-wal` / `-shm` of the old base (WAL mode, `db.py:788`);
  SQLite replays that stale WAL onto the restored file at next open.

**Done when:** the three files round-trip (test); restore into a target
holding `rusterm.db-wal` or `rusterm.db-shm` refuses and names them
(a clean close removes them; a present one means a live or crashed
writer).

## E6. P1/P6 on a merge-commit HEAD (reserve)

Measured on `main` = `36d1999` (the lane merge), fresh linked worktree,
23.09: acceptance «пройдено 11, провалено 2», red in both pytest runs:
`test_i5_staged_and_authorised_widening_is_green`,
`test_selfcheck_cannot_exit_zero_with_dirty_tree` (plus
`test_keys_view_names_origin_without_values`, order-dependent through
`env._LAST_ORIGINS`, already fixed on the shift branch by `0472136`).
Cause of the first two: with an empty index `agent/p1_rule.sh` checks
`HEAD~1..HEAD`; on a merge commit that is the whole lane diff with only
the merge message ⇒ «необъявленная замена булавок:
tests/test_task56_z2.py tests/test_task57_br_census.py», although both
replacements were declared in the lane commits (TASK-58 C4).

Rule: when HEAD has two parents, P1 and P6 check each non-merge commit
of `HEAD^1..HEAD` against its own message.

**Done when:** a temp-repo test: lane commit with a declared
replacement + merge commit ⇒ P1 green; the same without the declaration
⇒ red; guard files changed only as permitted above (one path per line).

## E7. The cadence plan is executed, not only printed (reserve)

`core/cadence.py` `plan_pass` (backfill first, poll when due, skip when
complete, within the daily ceiling) is shown by `rusterm cadence`, but
nothing runs it: `ingest --source twelvedata` fetches every listed
instrument in full. **Done when:** `rusterm ingest --source twelvedata
--watchlist W --plan` follows the plan (counting-transport test: a
complete instrument costs 0 requests, a backfill one 1); the pass
stops cleanly at the ceiling and says where.

## E8. Small truths (reserve, one commit each)

- `formulas.py` `MEASURE_UNIT_KINDS` lists `invested_capital`, `roic`,
  `ev` twice — dedupe; a test that the literal has no repeated keys
  (AST).
- `cmd_cadence` and `cmd_census` call themselves read-only (B40) yet run
  `apply_migrations` on an existing base — either say «миграции
  применены: N» or stop migrating there; test.
- `store/backup.py` restore: the «внелистовый член» check compares a
  member against the list it was built from — it can never fire; make
  it compare zip names against the manifest (extra members ⇒ refusal).
- `core/watchlist_io.py` `import_rows`: `new_version`, `copy_members`
  and each `add_member` are separate transactions — a failure midway
  leaves a half-built version as current; `ops.apply` already uses the
  atomic `create_version_with_members`. Use the same door; a test
  injects a failure on the second member ⇒ version count unchanged.
  An unknown watchlist id raises `TypeError` (`current_version` is
  `None`) — refuse by value instead.
