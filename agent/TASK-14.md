# TASK-14 — the pass that has to survive five hundred

- **Status: ACCEPTED** — coordinator re-ran acceptance and the suite on
  `agent/night-2` on 10.09.2026: 13/13, 361 passed, 2 skipped, 0 xfailed.
  Rulings on every `Disputed` item are in `agent/TASK-19.md` §0.1.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-14A.md` — **not** `REPORT-14.md`, which is
  already taken by your SEDAR+ access probe (commit `8677934`). Two
  different pieces of work must not share a report file.
- **Supersedes:** TASK-12 (**ACCEPTED**, Y1–Y9) and TASK-13
  (**ACCEPTED**, Z1–Z6; M4 partial by your own honest reading). Both
  verified on a clean detached checkout at `b90ac14`. Do not reopen them.
- **Goal of the night, in one sentence:** the finding you made in Z3 is
  upheld and gets fixed — a snapshot build stops scanning every fact of
  every issuer, five hundred instruments stop being a three-hour
  proposition, and the strict xfail you left as a signal goes green and
  is retired in the same night.

You are an autonomous coding agent with the same tools as the
coordinator: shell, file editing, test runs, network. This file gives
contracts, decisions and acceptance commands, not tutorials. Anything
readable from the repository, read from the repository.

No coordinator is online during the run. Every fork below is closed by a
deterministic rule. Where a rule is wrong, follow it and put the
objection in **`## Disputed`**.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git merge origin/main          # brings TASK-14, TASK-15, BACKLOG, LAUNCH
bash agent/acceptance.sh
```

The last command must print `Итог: пройдено 13, провалено 0`. The
coordinator ran exactly this on a clean detached checkout of
`agent/night-2` at `b90ac14` and got 13/13 with
`303 passed, 2 skipped, 2 xfailed`.

**On the merge, `agent/BACKLOG.md` will conflict.** The coordinator
repaired the file by hand (§0.2 ruling 3) and refilled the queue with
B20–B25. Resolve in favour of `origin/main` — `git checkout --theirs
agent/BACKLOG.md` after the merge, or `git checkout origin/main --
agent/BACKLOG.md` — and do not reconstruct the old queue.

Then read, in full and from the repository, the files you will touch:
`rusterm/store/db.py`, `rusterm/store/repos.py`, `rusterm/core/snapshot.py`,
`rusterm/core/refresh.py`, `tests/test_m4_scale.py`,
`tests/test_m3_snapshot.py`, `rusterm/store/doctor.py`.

---

## 0.1. Where the project stands — measured by the coordinator, not reported

Clean detached checkout at `b90ac14`:

| Check | Result |
|---|---|
| `bash agent/acceptance.sh` | **13/13**, `Принято` |
| `python3 -m pytest -q` | **303 passed, 2 skipped, 2 xfailed** |
| deleted `assert` lines | 12 — eleven are schema pins 36→37, one is the Y4 exemption **replaced by a stronger `assert not missing`**; nothing weakened |
| edits to applied migrations | **0** — 37 is a new migration |
| `agent/acceptance.sh` vs `origin/main` | byte-identical (check 12 green) |
| `docs/` | untouched (check 10 green) |
| `tests/data/golden_m2.json` `expected` | `git diff … \| grep -c '^[-+].*expected'` = **0**; only the trailing newline changed |
| M3 measure table | re-run by the coordinator with `-s`: **identical to your REPORT-12 table, line for line** |
| `period_mismatch` across the twenty | **0** — Y2 did what it was for |
| `net_margin` | **20/20** — your correction of REPORT-11's "19 of 20" was right |

Both nights are accepted in full. The Y2 rule, the two source tags, the
conditional GET, the incremental pass and `refresh --watchlist` are the
project's now — none of it is reopened below.

| Layer | State |
|---|---|
| store, migrations, parsers, provider, pipeline, coverage | done |
| concept map, period eligibility, measure period/unit | done, `us-gaap.v3` |
| the ten-measure formula set | eight measures at or above floor, tail is data, not code |
| `add` / `ingest` / `snapshot` / `export` / `verify` / `tui` / `doctor` / `refresh` | done, subprocess-covered |
| M1, M2, M3 | reached |
| **M4** | incrementality, schedule-as-command and rollback **reached**; five hundred instruments **blocked by Z3 — this night** |
| M5 | not started, needs a key |

---

## 0.2. Rulings. Your two questions, and three defects the review found

### 1. Z3, the quadratic pass. **Upheld, and it is the most valuable
finding of the six nights so far.**

The coordinator reproduced it structurally rather than by timing:

```
EXPLAIN QUERY PLAN of SnapshotRepo.restated_revisions():
  (2, 0, 216, 'SCAN f')
  (7, 0, 0, 'CORRELATED SCALAR SUBQUERY 1')
  (11, 7, 216, 'SCAN a')
sqlite_master indexes (type='index', sql NOT NULL): []
```

**The schema has not one explicit index.** Every lookup in this project
is a full scan; `restated_revisions()` is merely the one that scans twice
and runs on every build.

There is a second defect inside the same query, and it is a correctness
one you did not claim: **the query has no `issuer_id` filter at all.**
`_diff()` puts its result into `SnapshotDiff.revisions` for **one**
instrument, so the diff of AAPL's snapshot currently lists the restated
revisions of every issuer in the database. On a twenty-issuer test base
that reads as a slow diff; on a five-hundred watchlist it is a wrong
answer shown to the user.

**Ruling: fix both halves, in this order — A1 the index, A2 the scope.**
Not either/or. The index makes the pass linear; the scope makes the
answer right and cuts the remaining work to one issuer's rows.

### 2. V and UNH: `roe` on `total_equity_incl_nci`. **Denied.**

You asked whether `roe` may fall back to `total_equity_incl_nci` when an
issuer's only fresh equity tag is the including-NCI one. It may not.
`roe` is compared across a peer set and ranked into percentiles; a
denominator that means "equity including minority interests" for two
issuers and "equity attributable to the parent" for eighteen produces a
number that is wrong in a way no lineage note repairs. An honest gap is
the correct output, and Y2 is what made it honest.

**What is wrong is the reason text, and A4 fixes that**: `roe` reports a
bare `missing_data` where the single-period measures report
`missing_data: operating_income`. The user must be able to see *which*
input is absent without opening a database.

### 3. `agent/BACKLOG.md` was left malformed. **Coordinator repaired it;
the rule that prevents a repeat is in Y7's successor.**

Marking B12–B19 done deleted only the **first line** of each multi-line
item and left its continuation lines orphaned in `## Queue`. The queue
was empty in substance and unreadable in form. When you close a backlog
item, move **the whole block** — every continuation line — into `## Done`
as one line, or delete the block entirely and write the one-line `- [x]`
entry. Never delete a bullet's first line alone.

### 4. `rusterm/core/refresh.py` annotates `provider_factory: Callable`
and never imports `Callable`. `from __future__ import annotations` hides
it at import time; `typing.get_type_hints` on that function raises
`NameError`. A6.

### 5. `issuer_ingest_state` claims "one row per issuer **and source**"
in its own migration comment, but its primary key is `issuer_id` alone
and `IssuerStateRepo.put` writes `ON CONFLICT(issuer_id)`. Two sources
for one issuer cannot coexist. A7 makes the schema say what the code
means.

---

## 1. Working protocol. This outranks the task list

Six autonomous runs on this repo failed on method rather than
difficulty. The rules below are one counter-measure per failure.

### 1.1. The cycle. One item = one pass

```
1. READ     the file you are about to change, in full. Not from memory.
2. SHOW     current state with a command, and look at the output.
3. CHANGE   exactly one item. Not two.
4. VERIFY   with the command from that item's "Done when".
5. SELFCHECK  the four commands in §1.3. All must be clean.
6. COMMIT   immediately, before moving to the next item.
7. PUSH     immediately (§1.8).
8. RECORD   one line in agent/REPORT-14A.md: command + its output (§1.7).
```

Steps 6 and 7 do not get deferred. One item, one commit, one push bounds
any loss to the item in flight.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong. A genuinely obsolete assertion is **replaced
by a stronger one**, and the report says how the new one is stricter.

**P2. Never edit an existing migration.** Schema change = **new**
migration, new number, `_SCHEMA_VERSION` bumped. Next free number is
**38** (34 does not exist and never will; 37 is `issuer_ingest_state`).

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`. Except fetched data — §1.12 is the opposite rule and
takes precedence for it.

**P4. No `.bak`, `.orig`, temp databases, junk.**

**P5. Never claim a check you did not run.** "Not run" is acceptable.
"Works" without command output is not.

### 1.3. Selfcheck. Four commands before every commit

```bash
git diff --cached | grep '^-.*assert'                # P1: must be empty
git diff --cached rusterm/store/db.py | grep '^-'    # P2: empty except _SCHEMA_VERSION
git status --porcelain | grep '^??'                  # P3, P4: must be empty
bash agent/acceptance.sh                             # must stay 13/13
```

Below 13 means you broke something. Stop, roll back (§1.5), re-enter.
Never proceed with a red script.

**The ordering mistake you made twice in TASK-13**: check 13 fails on
your own new file while it is still untracked. `git add` the file
**before** you run the final acceptance, not after reading the failure.

### 1.4. When stuck

The same thing fails after **three different hypotheses** about the
cause — not three retries of one idea:

1. Stop working on it.
2. If it is a test — `@pytest.mark.xfail(strict=True, reason="…")`.
   Never delete, never weaken.
3. Report: what failed, which three hypotheses you tried.
4. Next item.

### 1.5. Stop rule

A passing test starts failing — stop immediately: `git checkout -- <file>`.
A regression means an assumption upstream of the edit is wrong.

### 1.6. Commit format

Russian, imperative, one thought. First line — what was done. Body — how
it was verified, with the command's real output.

### 1.7. Bookkeeping

`agent/REPORT-14A.md` is **append-only and verified after every write.**

- **R1.** Never open the report with a truncating mode. Append only:
  `printf '%s\n' "…" >> agent/REPORT-14A.md`, or a quoted heredoc with
  `>>`. Never `>`, never `open(p, "w")` on it.
- **R2.** After every append, run
  `wc -c agent/REPORT-14A.md && tail -3 agent/REPORT-14A.md` and look at the
  output. A zero-byte or shrinking report is an incident to fix at once,
  before the next item.
- **R3.** Chain commands with `&&`, never with `;`. A `;` after a red
  `pytest` hides the failure from the next step.
- **R4** (new, from incident R2 of TASK-13). The final HANDOFF is
  **appended at the end of the file**, and the section it replaces is
  edited in place by line, never by rewriting the file from a variable.
  After writing it, `wc -c` must be **larger** than before, never smaller.

Sections, in this order: **Done** (one line per item: command + output),
**Blocked**, **What not to trust**, **Disputed**, and — filled at the
end, never deleted — **HANDOFF** (§3 template). Last line always
`NOW: <item>, step <n>`. `tests/test_report_sections.py` checks the
shape; it reads whatever `agent/STATE.json` names, so it follows you.

`agent/STATE.json`, same commit as the work:

```json
{"task": "agent/TASK-14.md", "report": "agent/REPORT-14A.md",
 "item": "A1", "step": "4", "status": "working",
 "last_commit": "<sha>", "requests": 0, "net_requests": 0,
 "llm_calls": 0, "model": "<your model id>",
 "updated_at": "<ISO8601 UTC>"}
```

### 1.8. Push, every time

```bash
git push origin agent/night-2
```

Push fails for lack of rights or for lack of network — do not retry in a
loop. Write `PUSH UNAVAILABLE` as the **first line** of
`agent/REPORT-14A.md`, keep committing locally, and at the end produce
`git bundle create ../RusTerm-handoff.bundle --all` (outside the repo, so
check 13 stays green). Say so in `## HANDOFF`.

### 1.9. Stop time

**10:00 Danang (UTC+7).** Finish the current item to a commit and a
push, then do §3. Do not start a new item after 09:30. A session started
by the coordinator by hand outside those hours runs until its work is
done.

### 1.10. Precedence when sources disagree

This file → `docs/` → existing code → your judgement. A conflict between
the first two is a coordination bug: implement per this file and record
both quotes in **Disputed**.

Existing green code is authoritative over your preferences. It is
extended, never refactored or "improved". The only exceptions are the
items below that name a file and say what is wrong with it.

### 1.11. What you may assume

- `python3` is 3.14.6 here; the code must also run on 3.12. `pytest` is
  installed. `zstandard` is **not**, and acceptance check 11 reruns the
  suite with it blocked — the gzip fallback is load-bearing.
- Acceptance is 13/13 at your start and is ground truth about your work.
- You have network. See §1.12 before using it.

### 1.12. Network rules. Read before the first request

**N1. One source: SEC EDGAR.** Public, documented, free, no auth. No
price vendor, no scraper, no mirror, no aggregator. Prices stay
synthetic.

**N2. Identify yourself or do not go.** `RUSTERM_SEC_UA` must carry a
real contact. Unset or empty → every network operation returns a
`ConfigError` **value** (never an exception), the item degrades to the
offline path, and the report records
`SEC_UA UNSET — network path not exercised`. **Never hardcode a contact,
never commit one, never invent one.** The application reads
`~/.rusterm.env` itself — check with `rusterm doctor`.

**N3. Rate and ceiling, enforced in code.**

| Limit | Value | Behaviour at the limit |
|---|---|---|
| requests per second | 5 | limiter delays |
| requests per night, total | 5000 | provider **refuses** with a value |
| retries per failed URL | 2, then give up | E1/E2, recorded |

Count every request in `STATE.json` `"net_requests"`.

**N4. 403 or 429 is a stop, not a puzzle.** Back off, record E1/E2, move
on. Do not change the User-Agent, do not switch IP, do not use a proxy,
a mirror or a cache.

**N5. Fetched data never enters git** — except a trimmed recorded payload
under `tests/data/edgar/`.

**N6. `fixtures/` stays synthetic-only.**

**N7. Network lives only in nodes 2 and 4 of process 1.** A network test
skips cleanly when `RUSTERM_SEC_UA` is unset; it never fails for that.

**This night needs no network at all.** Every item below is offline. If
you spend a request, say why in the report.

### 1.13. Money and quota

**Your own model.** Free tier only. If the chain switches you to a paid
model, record it in `STATE.json` and as its own report line. Count your
calls in `"requests"`; at 800, finish the current item to a commit and
close the night with §3.

**The application's model calls.** Key from `RUSTERM_LLM_PROVIDER` /
`RUSTERM_LLM_API_KEY`. Unset → the fake client, and the report records
`LLM key unset — real path not exercised`. With a key: a hard ceiling of
**50 calls for the whole night**, counted in `"llm_calls"`. No key ever
appears in a commit, a log, a report or a test.

---

## 2. The work, in priority order

### A1. Migration 38: the schema gets its first indexes

Per §0.2 ruling 1. New migration, number **38**, `_SCHEMA_VERSION` 38.

Indexes to create, and nothing else:

| index | columns | serves |
|---|---|---|
| `idx_fact_issuer_concept_period_basis` | `fact(issuer_id, concept, period_end, basis)` | `restated_revisions`, `as_reported_facts` |
| `idx_fact_source_ref` | `fact(source_ref)` | doctor's raw-store cross-check |
| `idx_measure_snapshot` | `measure(snapshot_id)` | `get_measures`, every diff |
| `idx_measure_lineage_measure` | `measure_lineage(measure_id)` | source panel, `instruments_for_fact` |

Four indexes. Do not add a fifth on a guess; an index you cannot name a
query for is cost without benefit.

The doctor's schema-drift check must know about migration 38 exactly as
it knows about 37 — same strength, no exemption.

**Done when** a test asserts, on a fresh database, that
`EXPLAIN QUERY PLAN` for `restated_revisions()`'s SQL contains **no**
`SCAN fact` and does contain `SEARCH`; `_SCHEMA_VERSION == 38`; the
migration list pins `[33, 35, 36, 37, 38]`; the doctor test covers 38;
`python3 -m pytest -q` exits 0; acceptance 13/13.

---

### A2. `restated_revisions()` answers about one issuer

Per §0.2 ruling 1, second half. This is a correctness fix.

- `SnapshotRepo.restated_revisions(issuer_id)` takes the issuer and
  filters on it. No call site may pass `None` to mean "everyone" — there
  is no such caller and there must not be one.
- `SnapshotBuilder._diff()` passes the issuer whose snapshot it is
  building. `_diff`'s signature grows the argument; `build()` has it.

**Done when** a test seeds two issuers, each with an `as_reported` and a
`restated` fact for a different concept, builds a snapshot for the first
and asserts `diff.revisions` names **only** the first issuer's concept —
and that the test fails if the filter is removed (check it by removing
it, watching it go red, and restoring it); `python3 -m pytest -q` exits 0.

---

### A3. Five hundred instruments, for real

With A1 and A2 in, `tests/test_m4_scale.py` is expected to pass.

- Remove the `xfail(strict=True)` marker. This is the one deletion this
  night authorises, and only because its `reason` names a cause that A1
  and A2 removed. If the test still does not pass inside
  `M4_FIRST_PASS_BUDGET_S`, **do not raise the budget** — keep the
  xfail, report the new measured time and the new hot spot in
  `## Disputed`, and go to A4.
- Report the **actual measured time of both passes**, first and second,
  as numbers.
- The per-instrument checkpoint you built stays: a future regression must
  fail in seconds, not in hours.

**Done when** `python3 -m pytest tests/test_m4_scale.py -q -s` exits 0
with the marker gone, both pass times are in the report, and
`python3 -m pytest -q` exits 0 with **1 xfailed** remaining (the W4 one).

---

### A4. A gap says which input is missing

Per §0.2 ruling 2. In `rusterm/core/snapshot.py::_issuer_inputs`, the
two-period measures (`roe`, `asset_turnover`) and the `nopat` chain
write a bare `missing_data`; the single-period ones write
`missing_data: <concept>` and have since X3.

- Two-period: name the absent side —
  `missing_data: total_equity` / `missing_data: net_income`, both when
  both are absent, comma-separated in sorted order, exactly as the
  single-period branch formats it.
- `nopat`: `missing_data: operating_income` when the operating income
  rows are absent; when `effective_tax` itself has no period, the reason
  is `missing_data: effective_tax`.
- The vocabulary guard (`rusterm/reasons.py`, B15) matches on the first
  token, so no vocabulary change is needed. Verify that, do not assume it.

**Done when** the M3 table shows named reasons for `roe` and `nopat`
(no bare `missing_data` anywhere in the printed table), the floors in
`tests/test_m3_snapshot.py` are **unchanged**, a test asserts V's or
UNH's `roe` reason is `missing_data: total_equity`, and
`python3 -m pytest -q` exits 0.

---

### A5. `refresh` gets the audit row it should always have written

`refresh --watchlist` mutates the store — facts, coverage, snapshots —
and writes nothing to `audit_log`. Every other mutating command does.

- One row per pass: action `refresh`, target the watchlist id, payload
  the counts (`updated`, `unchanged`, `error`, `submissions`,
  `companyfacts`), `confirmed` false, `result` `ok` or `errors`.
- `--dry-run` writes **no** row: it changed nothing.
- B12's return value is used here: if `AuditRepo.log()` returns a reason,
  the command prints it to stderr and still exits on its own merits. That
  closes the tail you flagged in REPORT-12.

**Done when** a test asserts one `audit_log` row after a normal pass,
zero after `--dry-run`, and that a read-only log directory yields a
stderr line plus the database row; `python3 -m pytest -q` exits 0.

---

### A6. `Callable` is imported

Per §0.2 ruling 4. One line in `rusterm/core/refresh.py`. While you are
in the file, delete the unused `finish()` closure defined inside
`refresh_watchlist` — dead code, nothing calls it.

**Done when**
`python3 -c "import typing, rusterm.core.refresh as m; typing.get_type_hints(m.refresh_watchlist); print('ok')"`
prints `ok`; `grep -n 'def finish' rusterm/core/refresh.py` is empty;
`python3 -m pytest -q` exits 0.

---

### A7. `issuer_ingest_state` says what it means

Per §0.2 ruling 5. Inside migration 38 (one migration, both changes):

- new table with `PRIMARY KEY (issuer_id, source)`, rows copied from the
  old one, old one dropped — the standard SQLite table rebuild, written
  as a *new* migration, never as an edit to 37 (P2);
- `IssuerStateRepo.put` conflicts on `(issuer_id, source)`;
- `get`/`put` keep their current signatures and default `source='edgar'`.

**Done when** a test writes two rows for one issuer under sources
`edgar` and `synthetic`, reads both back independently, and asserts a
repeat `put` for the same pair updates rather than duplicates; the
migration test pins the table count and `[33, 35, 36, 37, 38]`;
`python3 -m pytest -q` exits 0; acceptance 13/13.

---

### A8. The backlog

`agent/BACKLOG.md`, top down, reporting each pulled item by its ID. It
was refilled by the coordinator (B20–B25). Read §0.2 ruling 3 before you
mark anything done.

---

### A9. The bookkeeping

`agent/STATE.json` naming this task and this report, real
`net_requests`, ending at `"status": "awaiting_review"`; `## HANDOFF`
filled with real values; `agent/ACCEPTANCE-12.txt` taken at the head you
hand over — `git add` it **before** the run (§1.3).

**Done when** `tests/test_report_sections.py` passes,
`agent/ACCEPTANCE-12.txt` is non-empty and its `HEAD:` line is the commit
before the final `agent/` commit, and
`python3 -c "import json;d=json.load(open('agent/STATE.json'));assert d['task']=='agent/TASK-14.md' and d['status']=='awaiting_review'"`
succeeds.

---

### A10. Queue not empty

`agent/TASK-15.md`, `TASK-16.md`, `TASK-17.md` and `TASK-18.md` are all
`Status: READY` and waiting, in that order. If this night ends early,
take the next one — do not idle and do not invent work. Each has its own
report file; never write into a previous task's report.

---

## 3. Night end — you run the final acceptance yourself

```bash
git add agent/ACCEPTANCE-12.txt agent/REPORT-14A.md agent/STATE.json
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-12.txt
git add agent/ACCEPTANCE-12.txt
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      A1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-12.txt)
Tests:           N passed, M skipped, K xfailed
M4 scale:        first pass … s, second pass … s, requests on the second pass …
Query plan:      restated_revisions after A1 — the EXPLAIN QUERY PLAN lines, verbatim
Measure table:   the printed M3 table, verbatim, with A4's named reasons
Milestones:      M4 yes/no — and if no, exactly what is missing
Strict xfail:    which remain and why
Network:         RUSTERM_SEC_UA set? — N requests (expected 0 tonight)
Model:           app LLM calls N; your own model id and call count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

In scope now: four named indexes, one issuer-scoped query, the scale
test's marker, reason texts, one audit row, two small defects.

Out of scope tonight, no exceptions for spare time:

- Qt or any GUI; price vendors; IFRS/UK/CA (M6); Industry View (M7)
- a second taxonomy beside `us-gaap`; any new source tag
- new composite concepts (`total_debt`, `invested_capital`)
- a daemon, a service, a background thread — the schedule is `cron`
- renaming a `--json` key, an exit code or a flag
- refactoring green code that no item names
- **raising `M4_FIRST_PASS_BUDGET_S`** — see A3

Widening the scope is a failure of this task, not a bonus.

## 5. Stack

Python 3.12+, must also run on 3.14. Standard library; `pytest`;
`sqlite3` and `curses` from stdlib; `zstandard` optional with `gzip`
fallback; `httpx`/`requests` only inside `rusterm/providers/`, and
`urllib.request` from stdlib is preferred. `tools/` is a dev-tool
directory outside the application and outside checks 1, 5, 7 and 8.
Forbidden: ORM, `alembic`, `pandas`, `numpy`, async frameworks, `rich`,
`textual`.

`list`, `dict`, `tuple`, `set` are builtins — write `list[str]`, with
`from __future__ import annotations` at the top of the module.

## 6. Acceptance script

`bash agent/acceptance.sh` — thirteen machine checks, **13/13 when you
start**. Run after every commit; never let it drop below 13.

**Editing that file is forbidden.** Check 12 compares it byte for byte
against `origin/main`, and an edit voids the whole night regardless of
what else you did. Think a check is wrong — write it in `## Disputed`.
Nineteen of twenty disputes raised so far were upheld against the
coordinator; Z3 is the twentieth.
