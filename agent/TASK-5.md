# TASK-5 — Stage C: watchlist, coverage, metrics, logs

- **Status: SUPERSEDED by `agent/TASK-7.md`** — its items are merged
  there as T0–T8. Kept for the record; do not work from this file.
- **Branch:** `agent/night-2`
- **Report file:** `agent/REPORT-5.md`
- **Predecessor:** TASK-4 — **ACCEPTED** (see §0)

This task is self-contained. You do not need `SKILL.md` or earlier
TASK files. Section 1 ("How to work") outranks the task list — read it
first, in full.

---

## 0. Where we are

Coordinator ran `bash agent/acceptance.sh` on a clean checkout of
`agent/night-2` at `a11ec89` (no working-tree noise):

```
Итог: пройдено 12, провалено 1
```

The single failure was check 12 (`acceptance.sh` differs from
`origin/main`). **Both "Disputed" items in your report were correct:**

| Your claim | Verdict |
|---|---|
| Check 12 red because `origin/main` lacked check 13, not because of the work | **Upheld.** Coordinator published check 13 to `main`. Now 13/13. |
| Check 13 red because of untracked coordinator files (`CLAUDE.md`, `AGENTS.md`, `agent/BACKLOG.md`) | **Upheld.** Coordinator committed them. Not your fault, correct not to commit them. |

Verified independently of your report, by git:

| Check | Result |
|---|---|
| `assert` deletions in `tests/` across your 17 commits | 3, all strengthenings (`_SCHEMA_VERSION 32→33`, `endswith(".v1")` → parameterised `endswith(version)`). Accepted. |
| Migrations 1–32 edited | No. Migration 33 is a new entry. |
| `agent/acceptance.sh` touched by you | No (only coordinator commit `7dd69c4`). |
| `docs/` adjusted to code | No. One new ADR only. |
| Tests | 147 passed, 1 skipped. 0 xfail remaining. |
| Fixtures naming rule (`synthetic` in name and body) | 5/5 pass. |

**Stage A + increments I1–I13 are accepted.** Do not rewrite any of it.

### Two defects found in review

1. **I16 is missing.** TASK-4 §T3 required
   `test_i16_schema_change_reaches_existing_db` in
   `tests/test_invariants.py`. It does not exist. The substance is in
   `tests/test_db.py:155`, but the named invariant is absent, and
   acceptance check 2 only scans `i01…i15`, so it slipped through.
   → **T0 below.**
2. **Shadowed import.** `rusterm/store/db.py`, `open_connection()`
   re-imports `sqlite3` inside the function body while the module
   already imports it at the top. Dead line. → **T1 below.**

### One thing outside your control

`origin/agent/night-2` is at `7c010ab`. Your 17 commits are **local
only** — never pushed. If your next session clones from GitHub you will
get the old tree and lose everything. **First thing you do: check
`git log origin/agent/night-2..agent/night-2`. If it is non-empty and
you have push rights, push. If you do not have push rights, say so in
the report's first line and produce `git bundle create handoff.bundle --all`.**

---

## 1. HOW TO WORK. Read this whole section; it is the important part

Four agents in a row failed on method, not on difficulty. Every rule
below exists because of a specific loss.

### 1.1. The cycle. One task item = one pass

```
1. READ     the file you are about to change, in full. Not from memory.
2. SHOW     current state with a command, and look at the output.
3. CHANGE   exactly one item. Not two.
4. VERIFY   with the command from that item's "Done when".
5. SELFCHECK  four commands from §1.3. All must be clean.
6. COMMIT   immediately, before moving to the next item.
7. RECORD   one line in agent/REPORT-5.md: command + its output.
```

Step 6 does not get deferred. Two agents left a whole night's work in
the working tree; it survived only because someone dug it out by hand.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong, not that the test is junk. If an assertion
is genuinely obsolete it is **replaced by a stronger one**, and the
report says in what way the new one is stricter.

**P2. Never edit an existing migration.** `_MIGRATIONS` in
`rusterm/store/db.py` is history already applied to other databases.
An edit made after the fact never arrives: `apply_migrations` skips the
version because it is already in `schema_version`. Schema change =
**new** migration with a new number.

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`.

**P4. No `.bak`, `.orig`, temp databases or junk.** You are editing a
file — edit the file; git is the copy.

**P5. Never claim a check you did not run.** "Not run" is an acceptable
answer. "Works" without command output is not.

### 1.3. Selfcheck. Four commands before every commit

```bash
git diff --cached | grep '^-.*assert'                # P1: must be empty
git diff --cached rusterm/store/db.py | grep '^-'    # P2: empty except _SCHEMA_VERSION
git status --porcelain | grep '^??'                  # P3, P4: must be empty
bash agent/acceptance.sh                             # must not get worse
```

### 1.4. When stuck

Same thing fails after **three different hypotheses** about the cause
(not three retries):

1. Stop working on it.
2. If it is a test — mark `@pytest.mark.xfail(strict=True, reason="…")`.
   Do not delete, do not weaken.
3. Write in the report: what failed, which three hypotheses you tried.
4. Move to the next item.

This is a normal, accepted outcome.

### 1.5. Stop rule

A test that used to pass starts failing — stop immediately. Do not fix
forward, roll back: `git checkout -- <file>`, then re-enter.

### 1.6. Commit format

Russian, imperative, one thought. First line — what was done; body —
how it was verified, with command output.

### 1.7. Bookkeeping

- `agent/REPORT-5.md`, written as you go, not at the end. Sections:
  Done (one line per item, command + output), Blocked, What not to
  trust, Disputed. Last line of the file is always
  `NOW: <item>, step <n>`.
- `agent/STATE.json` after every cycle step:
  `{"task": "agent/TASK-5.md", "report": "agent/REPORT-5.md",
  "item": "<T-id>", "step": "<1-7>", "status": "working"|"awaiting_review",
  "last_commit": "<sha>", "updated_at": "<ISO8601 UTC>"}`.
- At 10:00 Danang (UTC+7): finish the current item to a commit, append
  `## HANDOFF` to the report (DONE/PARTIAL/BLOCKED, what is done, what
  is not, questions for the coordinator), set `"status":
  "awaiting_review"`.

---

## 2. Tasks

Strictly in order. Do not start the next before the previous is
committed. Items are ordered by priority: if the night runs out, the
top ones are the ones that mattered.

### T0. Restore invariant I16

TASK-4 §T3 was reported done but is not in the tree.

Add to `tests/test_invariants.py` a function named exactly
`test_i16_schema_change_reaches_existing_db`. It must:

1. build a database at the previous schema version and insert a row;
2. apply current migrations;
3. assert `schema_version` grew, the row survived, and the new
   constraint is in force (a `compression='gzip'` insert succeeds).

Do not delete `tests/test_db.py:155`; that test stays. Do not touch
`test_i01…test_i15`.

**Done when:**

```bash
python3 -m pytest tests/test_invariants.py -q -k i16
grep -c '^def test_i16_schema_change_reaches_existing_db' tests/test_invariants.py
```
prints 1 passed and `1`.

### T1. Remove the shadowed import

`rusterm/store/db.py`, `open_connection()`: delete the `import sqlite3`
line inside the function body. Module-level import already exists.

**Done when:**

```bash
awk '/^def open_connection/,/^$/' rusterm/store/db.py | grep -c 'import sqlite3'
python3 -m pytest -q
```
prints `0` and a green run.

### T2. The table parser bypasses the basis rule (I3)

`rusterm/parsers/__init__.py`, `TableParser.parse`, writes
`"basis": "as_reported"` as a literal on every fact. `determine_basis`
is imported at line 19 and used by `SyntheticXBRLParser` (line 87) but
never called here. Your own report says "правило basis (I3) одно,
импортируется из core" — that holds for the XBRL parser and does not
hold for this one.

Invariant `test_i03_basis_period_rule` tests `determine_basis` in
isolation, so it cannot see this. Same class of gap as the missing I16:
the rule is tested, the call site is not.

Two things are wrong, and the second causes the first:

1. Every cell gets `period_start = period_end = doc["period_end"]` and
   `period_type = "instant"`, so a cell's own period is discarded before
   basis could be computed. A comparative column — the exact case that
   produces `restated` — is indistinguishable from the current period.
2. Because of that, `basis` is hardcoded.

Fix both:

- Read the period from the cell, then the column, then the table, and
  fall back to the document's `period_end` only when none is present.
- Read `period_type` the same way; do not hardcode `"instant"` (revenue
  is a duration, not an instant).
- Call `determine_basis(doc_period_end, fact_period_end, filed_at)`,
  same as the XBRL parser. No literal `basis` value anywhere.
- Extend `fixtures/synthetic_prices_table.json`, or add a new synthetic
  fixture, with a comparative column for an earlier period.

Then close the class of gap, not just this instance: add
`test_i17_parsers_apply_basis_rule` to `tests/test_invariants.py` — it
iterates `registered_parsers()`, feeds each a document containing a
comparative figure for an earlier period, and asserts the produced fact
has `basis == "restated"`. A new parser that hardcodes basis must turn
this red.

**Done when:**

```bash
grep -nE '"basis"\s*:\s*"' rusterm/parsers/__init__.py
python3 -m pytest tests/test_parsers.py tests/test_invariants.py -q
```
the grep prints nothing (no literal basis anywhere in the parsers) and
both test files are green, including `test_i17_parsers_apply_basis_rule`.

### T3. WatchlistRepo: the read side and immutable versioning

`docs/watchlist-and-llm.md` §1.1. Schema tables already exist
(`watchlist`, `watchlist_version`, `watchlist_member`, `watchlist_group`,
`watchlist_group_member`, `watchlist_filter`). `WatchlistRepo` currently
has three write methods and no reads.

Add to `rusterm/store/repos.py` (SQL stays in the store layer — check 7):

| Method | Contract |
|---|---|
| `current_version(watchlist_id)` | max `version` row, or `None` |
| `members(watchlist_id, version=None)` | members of that version; default = current |
| `groups(watchlist_id, version=None)` | groups + their members |
| `filters(watchlist_id, version=None)` | `criteria_json` parsed |
| `add_group` / `add_group_member` / `set_filter` | writes into a given version |
| `rollback_to(watchlist_id, version)` | **inserts a new version** copying that version's members, groups and filters; never deletes or rewrites history; `action='rollback:<n>'` |
| `list_watchlists()` | id, name, current version, member count |

Composition change = new `watchlist_version` row + a fresh member set.
There is no in-place edit.

**Done when** `tests/test_watchlist.py` exists and covers, at minimum:
current version after three edits is 3; `rollback_to(1)` produces
version 4 whose members equal version 1's; version 1's rows are
byte-identical before and after the rollback. `python3 -m pytest
tests/test_watchlist.py -q` green.

### T4. Coverage: gaps are shown, never hidden

`docs/watchlist-and-llm.md` §1.3. Table `coverage` exists; nothing
writes it.

- `CoverageRepo` in `rusterm/store/repos.py`: `upsert(instrument_id,
  block, status, last_update, reason)`, `for_instrument(instrument_id)`,
  `for_watchlist(watchlist_id)`.
- Blocks, exactly these eight: `prices`, `fundamentals`, `ownership`,
  `corporate_actions`, `governance`, `industry_metrics`, `peer_set`,
  `llm_summary`.
- Statuses, exactly these five: `ready`, `stale`, `processing`,
  `missing`, `error`.
- `missing` and `error` **require** a non-empty `reason`. Enforce it in
  the repo, not only by convention.
- Snapshot assembly (`rusterm/core/snapshot.py`) writes coverage for
  every one of the eight blocks on every run — a block with no data
  gets `missing` + reason, it is not skipped.

**Done when:**

```bash
python3 -m pytest tests/test_coverage.py -q
```
green, and one of its tests asserts that assembling a snapshot for an
instrument with prices only yields exactly 8 coverage rows, 7 of them
`missing` with non-empty reasons.

### T5. Watchlist import/export

`docs/watchlist-and-llm.md` §1.4.

- Export: CSV and JSON, ticker-addressed, columns exactly
  `ticker,market,isin,industry,note,added_at`.
- Import: every row goes through `resolve_ticker(ticker, market, as_of)`.
  A row that does not resolve, or resolves ambiguously, goes into the
  import report and is **not added**. Silent skipping is a defect.
- Import returns a report object: `added`, `already_present`,
  `not_found`, `ambiguous` — each a list of rows with a reason.

**Done when** `tests/test_watchlist_io.py` is green and asserts that
importing a 4-row file (1 good, 1 unknown ticker, 1 ambiguous, 1 already
present) adds exactly one member and reports the other three by category.

### T6. System metrics

`docs/quality-and-observability.md` §3. Table `metric_sample` exists;
nothing writes it.

Implement all nine, computed from the database, in
`rusterm/core/metrics.py`: `provider_success_rate`,
`provider_rate_limited`, `data_lag`, `suspect_share`, `unparsed_share`,
`verification_queue`, `peer_set_coverage`, `peer_set_churn`,
`locator_resolve_failures`.

- `MetricsRepo.record(name, value, at, scope)` in the store layer.
- No metric invents a value: with no input rows the metric is not
  recorded, rather than recorded as 0. A missing sample and a zero are
  different facts.

**Done when** `tests/test_metrics.py` is green and asserts, for each of
the nine names, both a computed value on seeded data and "not recorded"
on empty data.

### T7. Logs: three destinations, not mixed

`docs/quality-and-observability.md` §4.

- `logs/app.log` — application work, size-rotated (stdlib
  `logging.handlers.RotatingFileHandler`, 5 files × 1 MB).
- `logs/audit.jsonl` — user operations, append-only, one JSON object per
  line, must survive loss of the database. Never rotated, never
  rewritten.
- `raw/manifests/*.jsonl` already exists and is unchanged.

Path construction goes through `rusterm/store/paths.py`. `AuditRepo`
writes both the `audit_log` table and the JSONL line; the JSONL line is
written even if the database write fails.

**Done when** `tests/test_logs.py` is green and asserts: audit line
survives when the DB connection is closed mid-operation; `app.log`
rotates after exceeding the size limit; the two files never contain each
other's records.

### T8. CLI for stage C

Extend `rusterm/cli/` (no SQL there — check 7):

```
rusterm watchlist create|add|remove|list|show|rollback
rusterm watchlist export --format csv|json
rusterm watchlist import <file>
rusterm coverage <instrument-id|--watchlist ID>
rusterm metrics [--record]
```

Every command works on synthetic data and prints gaps with reasons.

**Done when** `tests/test_cli.py` covers each new command end-to-end and
`python3 -m pytest -q` is green.

---

## 3. Out of scope

Not under any circumstances, even with time left: Qt UI, LLM layer and
chat, Industry View, UK/CA providers, industry metrics beyond
Maritime/Tanker, real network sources. All work offline, on synthetic
data.

Time left over — go back to tests, or take the top item from
`agent/BACKLOG.md`. Do not invent work.

## 4. Stack

Python 3.12+, must also work on 3.14. Standard library; `pytest` for
tests; `sqlite3` from stdlib; `zstandard` optional, `gzip` is the
fallback; `httpx`/`requests` only inside `rusterm/providers/`.
Forbidden: ORM, `alembic`, `pandas`, `numpy`, async frameworks.

`list`, `dict`, `tuple`, `set` are builtins — write `list[str]`, with
`from __future__ import annotations` at the top of the module.

## 5. Acceptance

`bash agent/acceptance.sh` — thirteen machine checks, currently 13/13
on `agent/night-2`. Run it after every commit; it must never get worse.

**Editing that file is forbidden** — check 12 compares it against
`origin/main` and an edit voids the whole night. Think a check is
wrong — write it in the report's "Disputed" section; it gets read, and
last time both of your disputed items were upheld.
