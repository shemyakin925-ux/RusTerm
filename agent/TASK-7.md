# TASK-7 — the whole offline core in one night

- **Status: READY** — this is the task. Start here.
- **Branch:** `agent/night-2`
- **Report:** `agent/REPORT-7.md`
- **Supersedes:** TASK-5 and TASK-6 (their content is merged into this
  file; do not open them)
- **No coordinator online during the run.** Every fork below is closed
  by a deterministic rule, so nothing here requires an answer from
  anyone. Where a rule turns out to be wrong, follow it anyway and put
  the objection in **Disputed** — that is the channel, and it works
  (two of two disputes upheld last cycle).

You are an autonomous coding agent with a large context window; this
file is written on that assumption. It gives you decisions, contracts
and acceptance commands — not tutorials. Anything you can read from the
repository, read from the repository. Section 1 is the working protocol
and outranks the task list.

---

## 0. Start here. Four commands, in this order

```bash
git checkout agent/night-2
git merge origin/main
# Expect exactly one conflict: agent/LAUNCH.md. Resolve it by taking
# main's version verbatim — that file is the coordinator's, never yours:
git checkout --theirs agent/LAUNCH.md && git add agent/ && git commit --no-edit
bash agent/acceptance.sh
```

**The last command must print `Итог: пройдено 13, провалено 0`.** The
coordinator ran exactly this sequence before handing you the task and
got 13/13. If you get anything else, something in your environment
differs — record the full output as the first entry in
`agent/REPORT-7.md` and continue anyway; do not try to "fix" acceptance.

Then load the repository into context in one pass: `docs/`, `rusterm/`,
`tests/`. The whole project is ~3.8k lines of code and ~3k of tests — a
small fraction of your window, and cheaper to hold than to re-derive.
This matters because the recurring failure in this repo's history is
editing a file from a remembered shape rather than its current one; with
the tree in context that failure mode disappears.

The specs live in `docs/` and are authoritative. This task does not
restate them — it names the section and fixes the decisions that a spec
deliberately leaves open (exact enums, thresholds, tie-breakers), so
that two runs of this task produce the same design.

---

## 0.1. Where the project stands

Accepted and working — **do not rewrite any of it**:

| Layer | State |
|---|---|
| Storage: paths, config, content-addressed raw store, 33 migrations, WAL, writer lock | done |
| Repositories — the only SQL layer | done |
| Fact, 6 locator kinds, basis rule, `resolve(locator)` | done |
| Providers (synthetic, `typing.Protocol`), parsers (XBRL + table) | done |
| Ingestion pipeline: 9 nodes, E1–E5, idempotency, staleness cascade | done |
| Formulas: TTM, Valuation, Growth, Quotes, null-reasons | done |
| Peer set: versions, origin, verified/unverified, thresholds 5/8, drift | done |
| Snapshot (two passes, three diffs), export CSV/JSON without recompute | done |
| CLI: `init ingest snapshot export verify doctor` | done |
| Tests | 147 passed, 1 skipped, 0 xfail |

Missing, and that is your night: **watchlist read-side, coverage,
metrics, logs, verification/ground-truth, governance, industry metrics,
the deterministic half of LLM-summary** — plus three defects found in
review (T0–T2).

---

## 1. Working protocol. This outranks the task list

Four autonomous runs on this repo failed on method rather than on
difficulty, and the losses were mechanical: work left uncommitted, work
committed but never pushed, a file edited from memory, an assertion
deleted to make a change fit, an already-applied migration edited in
place. The rules below are the counter-measures, one per failure. They
are not a judgement about capability — they are the parts of the loop
that no amount of reasoning recovers once they are skipped.

### 1.1. The cycle. One item = one pass

```
1. READ     the file you are about to change, in full. Not from memory.
2. SHOW     current state with a command, and look at the output.
3. CHANGE   exactly one item. Not two.
4. VERIFY   with the command from that item's "Done when".
5. SELFCHECK  the four commands in §1.3. All must be clean.
6. COMMIT   immediately, before moving to the next item.
7. PUSH     immediately (§1.8).
8. RECORD   one line in agent/REPORT-7.md: command + its output.
```

Steps 6 and 7 are the ones that do not get deferred. Two runs left a
whole night in the working tree; the third committed but never pushed,
and 17 commits survived only because a human found them on the laptop.
Batching commits to the end of the run is the single highest-variance
thing you can do here — one item, one commit, one push keeps the loss
bounded to the item in flight.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong, not that the test is junk. If an assertion
is genuinely obsolete it is **replaced by a stronger one**, and the
report says in what way the new one is stricter.

**P2. Never edit an existing migration.** `_MIGRATIONS` in
`rusterm/store/db.py` is history already applied to other databases.
An edit after the fact never arrives: `apply_migrations` skips the
version because it is already in `schema_version`. Schema change =
**new** migration with a new number, plus a `_SCHEMA_VERSION` bump.

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`.

**P4. No `.bak`, `.orig`, temp databases or junk.** You are editing a
file — edit the file. Git is the copy.

**P5. Never claim a check you did not run.** "Not run" is an acceptable
answer. "Works" without command output is not. Your report is read by
someone who reruns everything.

### 1.3. Selfcheck. Four commands before every commit

```bash
git diff --cached | grep '^-.*assert'                # P1: must be empty
git diff --cached rusterm/store/db.py | grep '^-'    # P2: empty except _SCHEMA_VERSION
git status --porcelain | grep '^??'                  # P3, P4: must be empty
bash agent/acceptance.sh                             # must stay 13/13
```

Acceptance dropped below 13 — you broke something. Stop, roll back
(§1.5), re-enter. Do not proceed with a red script.

### 1.4. When stuck

The same thing fails after **three different hypotheses** about the
cause — not three retries of the same idea:

1. Stop working on it.
2. If it is a test — mark `@pytest.mark.xfail(strict=True, reason="…")`.
   Do not delete it, do not weaken it.
3. Write in the report: what failed, which three hypotheses you tried.
4. Move to the next item.

This is a normal, accepted outcome. A blocked item with an honest
explanation is worth more than a closed item that lies.

### 1.5. Stop rule

A test that used to pass starts failing — stop immediately. Do not fix
forward:

```bash
git checkout -- <file>
```

then re-enter the item. A regression means an assumption upstream of the
edit is wrong; fixing forward compounds the wrong assumption instead of
surfacing it, and that is how a night gets spent.

### 1.6. Commit format

Russian, imperative, one thought. First line — what was done. Body —
how it was verified, with the command's actual output.

```
T4: coverage пишется по всем восьми блокам, пробел с причиной

python3 -m pytest tests/test_coverage.py -q → 9 passed
Снапшот по инструменту только с ценами: 8 строк coverage,
7 из них missing с непустым reason.
```

### 1.7. Bookkeeping — two files, updated with the same commit

- `agent/REPORT-7.md`, written as you go, never at the end. Sections:
  **Done** (one line per item: command + output), **Blocked**,
  **What not to trust**, **Disputed**. The last line of the file is
  always `NOW: <item>, step <n>`.
- `agent/STATE.json`:
  ```json
  {"task": "agent/TASK-7.md", "report": "agent/REPORT-7.md",
   "item": "T4", "step": "4", "status": "working",
   "last_commit": "<sha>", "updated_at": "<ISO8601 UTC>"}
  ```
  `"status"` is `"working"` until §3, then `"awaiting_review"`.

### 1.8. Push, every time

```bash
git push origin agent/night-2
```

Push fails for lack of rights — do not retry in a loop. Write
`PUSH UNAVAILABLE` as the **first line** of `agent/REPORT-7.md`,
continue working with local commits, and at the end produce:

```bash
git bundle create handoff.bundle --all
```

Then say so in `## HANDOFF`. A bundle that exists beats a push that
does not.

### 1.9. Stop time

**10:00 Danang (UTC+7).** At that moment: finish the current item to a
commit and a push, then do §3. Do not start a new item after 09:30.

### 1.10. Precedence when sources disagree

In descending order: this file → `docs/` → existing code → your own
judgement. A conflict between the first two is a coordination bug, not
something to resolve silently: implement per this file, and record the
conflict in **Disputed** with both quotes.

Existing green code is authoritative over your preferences. It is not
rewritten, refactored or "improved" — only extended. The one exception
is an item below that names the file and says what is wrong with it
(T1, T2).

### 1.11. What you may assume

- `python3` is 3.14.6 here; the code must also run on 3.12. `pytest` is
  installed. `zstandard` is **not** installed, and acceptance check 11
  re-runs the suite with it blocked, so the gzip fallback is load-bearing.
- No network for data. `pip install` may or may not work; if it does not,
  that is a recorded fact, not a blocker.
- Acceptance is 13/13 at your start and is the ground truth about your
  work. Where your report and the script disagree, the script is right.

---

## 2. The night's work, in priority order

Strictly in order. Do not start an item before the previous one is
committed and pushed. The order is the priority: if the night runs out
at T6, the six that mattered most are done.

### T0. Restore invariant I16 — reported done, absent from the tree

TASK-4 required `test_i16_schema_change_reaches_existing_db` in
`tests/test_invariants.py`. The previous agent reported it as done. It
does not exist. Acceptance check 2 only scans `i01…i15`, so nothing
caught it.

Add a function named exactly `test_i16_schema_change_reaches_existing_db`.
It must:

1. build a database at the previous schema version and insert a row;
2. apply current migrations;
3. assert `schema_version` grew, the row survived, and the new
   constraint is in force (an insert with `compression='gzip'`
   succeeds).

`tests/test_db.py:155` already does this substance — reuse the approach,
do not delete that test. Do not touch `test_i01…test_i15`.

**Done when:**
```bash
python3 -m pytest tests/test_invariants.py -q -k i16
grep -c '^def test_i16_schema_change_reaches_existing_db' tests/test_invariants.py
```
→ `1 passed` and `1`.

### T1. Remove the shadowed import

`rusterm/store/db.py`, inside `open_connection()`, there is an
`import sqlite3` while the module already imports it at the top. Delete
the inner line. Nothing else in that function changes.

**Done when:**
```bash
awk '/^def open_connection/,/^$/' rusterm/store/db.py | grep -c 'import sqlite3'
python3 -m pytest -q
```
→ `0` and a green run.

### T2. The table parser bypasses the basis rule (I3)

`rusterm/parsers/__init__.py`, `TableParser.parse`, writes
`"basis": "as_reported"` as a literal on every fact. `determine_basis`
is imported at line 19 and used by `SyntheticXBRLParser` (line 87), but
never called here. The previous agent's report claims the basis rule is
single-sourced from core — true for the XBRL parser, false for this one.

`test_i03_basis_period_rule` tests `determine_basis` in isolation, so it
cannot see this. Same class of gap as the missing I16: the rule is
tested, the call site is not.

Two faults, and the second causes the first:

1. Every cell gets `period_start = period_end = doc["period_end"]` and
   `period_type = "instant"`, so a cell's own period is discarded before
   basis could be computed. A comparative column — the exact case that
   produces `restated` — becomes indistinguishable from the current
   period.
2. Because of that, `basis` is hardcoded.

Fix both:

- Read the period from the cell, then the column, then the table, and
  fall back to the document's `period_end` only when none is present.
- Read `period_type` the same way. Do not hardcode `"instant"` — revenue
  is a duration, not an instant.
- Call `determine_basis(doc_period_end, fact_period_end, filed_at)`,
  exactly as the XBRL parser does. No literal basis value anywhere.
- Extend `fixtures/synthetic_prices_table.json`, or add a new synthetic
  fixture, with a comparative column for an earlier period. The file
  must have `synthetic` in its name and in its body.

Then close the class of gap, not just this instance: add
`test_i17_parsers_apply_basis_rule` to `tests/test_invariants.py`. It
iterates `registered_parsers()`, feeds each a document containing a
comparative figure for an earlier period, and asserts the produced fact
has `basis == "restated"`. A future parser that hardcodes basis must
turn this red.

**Done when:**
```bash
grep -nE '"basis"[[:space:]]*:[[:space:]]*"' rusterm/parsers/__init__.py
python3 -m pytest tests/test_parsers.py tests/test_invariants.py -q
```
→ the grep prints nothing, and both files are green including
`test_i17_parsers_apply_basis_rule`.

### T3. WatchlistRepo: the read side and immutable versioning

`docs/watchlist-and-llm.md` §1.1. The tables exist (`watchlist`,
`watchlist_version`, `watchlist_member`, `watchlist_group`,
`watchlist_group_member`, `watchlist_filter`). `WatchlistRepo` has three
write methods and no reads.

Add to `rusterm/store/repos.py` — SQL stays in the store layer, check 7
enforces it:

| Method | Contract |
|---|---|
| `current_version(watchlist_id)` | max `version` row, or `None` |
| `members(watchlist_id, version=None)` | members of that version; default = current |
| `groups(watchlist_id, version=None)` | groups with their members |
| `filters(watchlist_id, version=None)` | `criteria_json` parsed |
| `add_group`, `add_group_member`, `set_filter` | writes into a given version |
| `rollback_to(watchlist_id, version)` | **inserts a new version** copying that version's members, groups and filters; never deletes, never rewrites history; `action='rollback:<n>'` |
| `list_watchlists()` | id, name, current version, member count |

A composition change is a new `watchlist_version` row plus a fresh
member set. There is no in-place edit of a version, ever.

**Done when** `tests/test_watchlist.py` exists and asserts, at minimum:
current version after three edits is 3; `rollback_to(1)` produces
version 4 whose members equal version 1's; version 1's rows are
identical before and after the rollback. `python3 -m pytest
tests/test_watchlist.py -q` green.

### T4. Coverage: a gap is shown, never hidden

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
  the repo, not by convention.
- Snapshot assembly (`rusterm/core/snapshot.py`) writes coverage for all
  eight blocks on every run. A block with no data gets `missing` plus a
  reason — it is not skipped.

**Done when** `python3 -m pytest tests/test_coverage.py -q` is green and
one of its tests asserts that assembling a snapshot for an instrument
that has prices only yields exactly 8 coverage rows, 7 of them `missing`
with non-empty reasons.

### T5. Watchlist import and export

`docs/watchlist-and-llm.md` §1.4.

- Export: CSV and JSON, ticker-addressed, columns exactly
  `ticker,market,isin,industry,note,added_at`.
- Import: every row goes through `resolve_ticker(ticker, market,
  as_of)`. A row that does not resolve, or resolves ambiguously, goes
  into the import report and is **not added**. Silent skipping is the
  defect this item exists to prevent.
- Import returns a report: `added`, `already_present`, `not_found`,
  `ambiguous` — each a list of rows with a reason.

**Done when** `tests/test_watchlist_io.py` is green and asserts that
importing a 4-row file (1 good, 1 unknown ticker, 1 ambiguous, 1 already
present) adds exactly one member and reports the other three by
category.

### T6. System metrics

`docs/quality-and-observability.md` §3. Table `metric_sample` exists;
nothing writes it.

Implement all nine in `rusterm/core/metrics.py`, computed from the
database: `provider_success_rate`, `provider_rate_limited`, `data_lag`,
`suspect_share`, `unparsed_share`, `verification_queue`,
`peer_set_coverage`, `peer_set_churn`, `locator_resolve_failures`.

- `MetricsRepo.record(name, value, at, scope)` in the store layer.
- **No metric invents a value.** With no input rows the metric is not
  recorded at all, rather than recorded as 0. A missing sample and a
  zero are different facts, and the second one lies.

**Done when** `tests/test_metrics.py` is green and asserts, for each of
the nine names, both a computed value on seeded data and "not recorded"
on empty data.

### T7. Logs: three destinations, never mixed

`docs/quality-and-observability.md` §4.

- `logs/app.log` — application work, size-rotated (stdlib
  `logging.handlers.RotatingFileHandler`, 5 files × 1 MB).
- `logs/audit.jsonl` — user operations, append-only, one JSON object per
  line, must survive loss of the database. Never rotated, never
  rewritten.
- `raw/manifests/*.jsonl` already exists and does not change.

Paths go through `rusterm/store/paths.py`. `AuditRepo` writes both the
`audit_log` table and the JSONL line, and **the JSONL line is written
even when the database write fails** — that is the whole point of it.

**Done when** `tests/test_logs.py` is green and asserts: the audit line
survives when the DB connection is closed mid-operation; `app.log`
rotates past the size limit; neither file ever contains the other's
records.

### T8. CLI for the new layers

Extend `rusterm/cli/` — no SQL there, check 7 enforces it:

```
rusterm watchlist create|add|remove|list|show|rollback
rusterm watchlist export --format csv|json
rusterm watchlist import <file>
rusterm coverage <instrument-id | --watchlist ID>
rusterm metrics [--record]
```

Every command works on synthetic data, and every gap prints with its
reason.

**Done when** `tests/test_cli.py` covers each new command end-to-end and
`python3 -m pytest -q` is green.

### T9. Process 5 — verification and ground truth

`docs/processes.md` §263-284. Table `verification` exists; nothing
writes it. Five nodes, all five required:

| Node | Contract |
|---|---|
| `capture` | what was shown, what it should be, link to the document; row in `verification` |
| `store_ground_truth` | new `fact` with `origin='manual'`, priority over the extracted one; **the extracted fact is not deleted** — it gets `superseded_by` pointing at the manual one |
| `recompute` | recompute every `measure` whose lineage touches the superseded fact |
| `propose_golden` | append the (raw, expected) pair to a golden-file proposal set on disk |
| `flag_parser` | counter of mismatches per `(provider, concept)`; over threshold the parser is marked degraded |

- `superseded_by` needs a **new migration (34)** if the column does not
  exist. New migration, never an edit to an old one (P2).
- `flag_parser` threshold: **5 mismatches per (provider, concept) within
  a rolling 30 days.** Deterministic. No judgement call, no tuning.
- A degraded parser surfaces through `coverage.reason`, not only in logs.

**Done when** `tests/test_verification.py` is green and asserts: the
extracted fact still exists after `store_ground_truth` and carries
`superseded_by`; a measure derived from it changed value after
`recompute`; the 5th mismatch flips the parser to degraded and the 4th
does not.

### T10. Governance traffic light, `governance.v1`

`docs/governance-thresholds.md`, all five indicators, thresholds
verbatim from that file. Deterministic computation over facts — no LLM,
no heuristics, no invented cutoffs.

- New module `rusterm/core/governance.py`; new table via **migration
  35**: `governance_assessment(instrument_id, indicator, color,
  method_version, as_of, lineage_ref, reason)`.
- Five indicators: independent-director share; CEO/chair combination;
  related-party transactions to revenue; net insider transactions
  (rolling 12 months); auditor.
- Hard rules from the doc, each its own test:
  - No aggregate score. Five separate colours, never summed or weighted.
  - Missing data is `gray`, never `green`.
  - A colour without `lineage_ref` is never emitted — raise, do not
    return one with an empty lineage.
  - Thresholds apply to the last completed reporting year, except
    indicator 4 (rolling window).
- `method_version = "governance.v1"` on every row. A threshold change
  means a new version; history is never recomputed in place.

**Done when** `tests/test_governance.py` is green with, at minimum: one
test per indicator hitting all four colours on synthetic facts; one test
asserting the result object has no aggregate or score field; one test
asserting that an empty lineage raises.

### T11. Maritime / Tanker industry metrics

`docs/industry-metrics/maritime-tanker.md`. Implement the metrics in
"Специфичные метрики", the tests named in "Тесты", and the default
pure-play peer set from the last section.

- `rusterm/core/industry/maritime_tanker.py`.
- Every metric carries `scope` and null-reasons exactly like the
  existing measures in `rusterm/formulas.py` — **reuse that machinery,
  do not fork it**.
- Maritime/Tanker only. No other industry, not even a stub.

**Done when** `tests/test_industry_maritime.py` is green and every test
named in the doc's "Тесты" section exists by that name.

### T12. LLM-summary guard rail — the deterministic half, no model

`docs/watchlist-and-llm.md` §2.6. **No network, no model call, no API
key.** You build the part that must be correct regardless of which model
is used later:

- A summary renderer where **numbers are substituted by the application
  from the snapshot**, never taken from model text.
- A validator: any statement containing a number with no corresponding
  entry in `citations` causes the **whole text** to be discarded — the
  block stays `missing` with reason "модель не смогла удержаться в
  данных". A partially-cleaned text is never stored. An empty block is
  honest; a plausible one is not.
- Storage in the existing `llm_summary` table: `instrument_id`,
  `created_at`, `model`, `prompt_hash`, `snapshot_version`, text,
  `citations`.
- The model client is a `typing.Protocol` with one synthetic fake
  implementation living in tests. No HTTP anywhere.

**Done when** `tests/test_llm_guard.py` is green and asserts: a fake
response containing an invented number is rejected in full (nothing
written to `llm_summary`, coverage block `missing` with that reason
string); a response whose every number is cited is stored; and
```bash
grep -rnE 'httpx|requests' rusterm/core/ rusterm/normalize/
```
prints nothing.

### T13. Queue empty

Items T0–T12 all done before 09:30 — take `agent/BACKLOG.md` top down.
Do not invent work of your own.

---

## 3. Final acceptance — you run it, nobody runs it for you

At 10:00 Danang, or when T13 is reached, whichever comes first. The
point is that the next reader starts from machine evidence in the
repository rather than from your prose. Six steps, in order:

```bash
# 1. everything is committed and pushed
git status --porcelain          # must be empty
git log --oneline origin/agent/night-2..agent/night-2   # must be empty

# 2. full test run
python3 -m pytest -q

# 3. the acceptance script, saved as evidence
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-5.txt

# 4. commit the evidence
git add agent/ACCEPTANCE-5.txt agent/REPORT-7.md agent/STATE.json
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

5. Append `## HANDOFF` to `agent/REPORT-7.md`:

```
## HANDOFF
Status: DONE | PARTIAL | BLOCKED
Items done:      T0 … Tn
Items not done:  Tn+1 … T13, and why
Acceptance:      пройдено N, провалено M   (from agent/ACCEPTANCE-5.txt)
Tests:           N passed, M skipped, K xfailed
Pushed:          yes | no — bundle at handoff.bundle
Questions for the coordinator:
  - …
```

6. Set `agent/STATE.json` to `"status": "awaiting_review"`, commit,
   push.

`PARTIAL` is the expected outcome — the list is deliberately longer than
one night, ordered so that stopping anywhere leaves the most important
things done. The only bad outcome is a `DONE` that a rerun contradicts:
everything here gets rerun, so a claim that fails on rerun costs more
than the item was worth.

---

## 4. What "finished" does not mean

Completing T0–T13 closes the **offline core** — everything in the specs
that can be built without a network source or a model. It does not close
the project, and attempting the rest is a failure of this task, not a
bonus. Out of scope tonight, with no exception for spare time:

- Qt interface, or any GUI
- LLM chat, intent classification, any real model call
- Industry View
- UK and CA providers
- industry metrics beyond Maritime/Tanker
- **any real network source** — no SEC EDGAR, no price vendor, no HTTP
  request to anything

All work is offline, on synthetic data. Every fixture carries
`synthetic` in its filename and in its body. This is not hygiene: the
repository is public, and an invented number that gets pushed becomes an
issuer's published financials to whoever reads it next.

Each of those needs something you do not have tonight: a network egress,
a vendor decision, an API key, or a human. Time left over → T13.

## 5. Stack

Python 3.12+, must also work on 3.14. Standard library; `pytest` for
tests; `sqlite3` from stdlib; `zstandard` optional with `gzip` as the
fallback; `httpx`/`requests` only inside `rusterm/providers/`.

Forbidden: ORM, `alembic`, `pandas`, `numpy`, async frameworks.

`list`, `dict`, `tuple`, `set` are builtins — write `list[str]`, with
`from __future__ import annotations` at the top of the module.

## 6. Acceptance script

`bash agent/acceptance.sh` — thirteen machine checks, **13/13 at the
moment you start** (after §0). Run it after every commit. It must never
go below 13.

**Editing that file is forbidden.** Check 12 compares it byte for byte
against `origin/main`, and an edit voids the entire night's work
regardless of what else you did. Think a check is wrong — write it in
the **Disputed** section of your report. That section gets read: last
night's agent raised two disputes and the coordinator upheld both.
