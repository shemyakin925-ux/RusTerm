# TASK-17 — M7: агрегат по сектору, который воспроизводится на дату

- **Status: ACCEPTED** — coordinator re-ran acceptance and the suite on
  `agent/night-2` on 10.09.2026: 13/13, 361 passed, 2 skipped, 0 xfailed.
  Rulings on every `Disputed` item are in `agent/TASK-19.md` §0.1.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-17.md`
- **Next in queue:** `agent/TASK-18.md` (Canada and the OTC venue,
  plus the market registry), `Status: READY`, dependent on nothing
  here — take it rather than idling.
- **Depends on nothing in TASK-14, 15 or 16.** Every table this task
  needs exists today: `peer_set_version` carries `valid_from`/`valid_to`,
  `snapshot` carries `as_of` and `version`. If earlier nights went badly,
  this task is still runnable as written.
- **Goal of the night, in one sentence:** milestone M7 — a sector
  aggregate recomputed for a past date returns the same composition and
  the same numbers it returned then, because it reads the peer set
  version and the snapshot versions that were in force on that date, not
  today's.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
bash agent/acceptance.sh
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
```

The first must print `Итог: пройдено 13, провалено 0`. The second tells
you the next free migration number — **read it, do not assume 38**.

Read, in full and from the repository: `rusterm/core/peers.py` (the I6
thresholds are law here), `rusterm/store/db.py` (the DDL quoted above),
`rusterm/store/repos.py` (`SnapshotRepo`, `PeerSetRepo`),
`rusterm/core/snapshot.py` (how percentiles already use a peer set),
`docs/quality-and-observability.md` §5, `docs/data-model.md` §5.

---

## 0.1. What M7 asks, and what already exists

> **M7 Industry View** — агрегаты по сектору воспроизводятся на
> исторической дате с тем же составом peer set

Three things exist and are not rebuilt tonight:

- `rusterm/core/peers.py` — `PERCENTILE_MIN_PEERS = 5`,
  `AGGREGATE_MIN_PEERS = 8`, verified origins, churn. **These are the
  invariant I6 and this task obeys them; it does not restate or relax
  them.**
- `peer_set` already distinguishes `scope_kind = 'industry'` from
  `'company'` — a sector is a peer set, not a new entity.
- `peer_set_version.valid_from` / `valid_to` and `snapshot.as_of` /
  `version` are what make "on a historical date" answerable at all.

What does not exist: any aggregate over a sector, any table to keep one,
any command to ask for one. That is the night.

---

## 0.2. Rulings, so no fork is open at 03:00

1. **An aggregate is a median and two quartiles, nothing else.**
   Per measure of the ten in `docs/data-dictionary.md` §3: `p25`,
   `median`, `p75`, and `n` — the count of members that actually
   contributed. No mean, no weighting, no composite score. A mean over a
   sector invites one outlier to speak for everyone; the document's own
   governance section refuses composite scores for the same reason.
2. **Nulls are excluded and counted, never treated as zero.** If 11 of 14
   members have `operating_margin`, the aggregate is over 11 and `n = 11`
   is part of the answer. A member with a null contributes to nothing but
   the reason table.
3. **Below `AGGREGATE_MIN_PEERS` there is no aggregate.** Fewer than 8
   contributing members → the value is null with reason
   `peer_set_too_small`, exactly as a measure is null with a reason
   elsewhere. Add that string to `rusterm/reasons.py` (B15's vocabulary)
   in the same commit — it is a new legitimate reason, not an exception.
4. **An unverified peer set produces no aggregate.** `origin=classifier`
   without user approval is `unverified` per ADR-0002; the aggregate is
   null with reason `peer_set_not_confirmed`, which is already in the
   vocabulary.
5. **`as_of` selects versions, it does not filter rows after the fact.**
   The peer set version is the one whose `[valid_from, valid_to)` covers
   `as_of`; each member's snapshot is the newest one with
   `as_of <= <requested date>`. Selecting today's rows and then dropping
   the late ones is the same answer only by accident, and stops being
   the same answer the moment a member is re-classified.
6. **Percentile of one company against its sector is already built and
   is not touched.** `_snapshots`/`peers.percentile_share` stay as they
   are. This task adds the sector's own row, not a rewrite of the
   company's.

---

## 1. Working protocol. This outranks the task list

### 1.1. The cycle. One item = one pass

```
1. READ     the file you are about to change, in full. Not from memory.
2. SHOW     current state with a command, and look at the output.
3. CHANGE   exactly one item. Not two.
4. VERIFY   with the command from that item's "Done when".
5. SELFCHECK  the four commands in §1.3. All must be clean.
6. COMMIT   immediately, before moving to the next item.
7. PUSH     immediately (§1.8).
8. RECORD   one line in agent/REPORT-17.md: command + its output (§1.7).
```

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A genuinely obsolete assertion is
**replaced by a stronger one**, and the report says how the new one is
stricter.

**P2. Never edit an existing migration.** New migration, new number,
`_SCHEMA_VERSION` bumped. **Read `_SCHEMA_VERSION` from the file before
you write a number** (§0).

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`.

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

`git add` a new file **before** the acceptance run, not after check 13
fails on it.

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

### 1.6. Commit format

Russian, imperative, one thought. First line — what was done. Body — how
it was verified, with the command's real output.

### 1.7. Bookkeeping

`agent/REPORT-17.md` is **append-only and verified after every write.**

- **R1.** Append only: `printf '%s\n' "…" >> agent/REPORT-17.md` or a
  quoted heredoc with `>>`. Never `>`, never `open(p, "w")`.
- **R2.** After every append: `wc -c agent/REPORT-17.md && tail -3
  agent/REPORT-17.md`, and look at the output.
- **R3.** Chain with `&&`, never `;`.
- **R4.** The final HANDOFF is appended at the end; a section is edited
  in place by line, never by rewriting the file from a variable. After
  writing it, `wc -c` must be larger than before, never smaller.

Sections, in this order: **Done**, **Blocked**, **What not to trust**,
**Disputed**, **HANDOFF**. Last line always `NOW: <item>, step <n>`.

`agent/STATE.json`, same commit as the work:

```json
{"task": "agent/TASK-17.md", "report": "agent/REPORT-17.md",
 "item": "E1", "step": "4", "status": "working",
 "last_commit": "<sha>", "requests": 0, "net_requests": 0,
 "llm_calls": 0, "model": "<your model id>",
 "updated_at": "<ISO8601 UTC>"}
```

### 1.8. Push, every time

```bash
git push origin agent/night-2
```

Push fails — do not retry in a loop. `PUSH UNAVAILABLE` as the first line
of the report, keep committing locally, and at the end
`git bundle create ../RusTerm-handoff.bundle --all` outside the repo.

### 1.9. Stop time

**10:00 Danang (UTC+7).** No new item after 09:30. Finish the current
item to a commit and a push, then §3.

### 1.10. Precedence when sources disagree

This file → `docs/` → existing code → your judgement. A conflict between
the first two is a coordination bug: implement per this file and record
both quotes in **Disputed**. Green code is extended, never refactored,
except where an item names the file and the defect.

### 1.11. What you may assume

- `python3` is 3.14.6 here; the code must also run on 3.12. `pytest` is
  installed, `zstandard` is not, and check 11 reruns the suite without it.
- Acceptance is 13/13 at your start and is ground truth about your work.

### 1.12. Network rules

**This night needs no network at all.** The rules still bind if you go:
SEC EDGAR only; `RUSTERM_SEC_UA` or a `ConfigError` **value** and the
offline path; 5 requests/second, 5000/night; 403/429 is a stop, not a
puzzle; fetched data never enters git except a trimmed payload under
`tests/data/edgar/`; `fixtures/` stays synthetic.

### 1.13. Money and quota

Free tier only for your own model; record a switch to a paid one in
`STATE.json`. At 800 of your own calls, close the night with §3. The
application's LLM path is not used tonight: `llm_calls` is 0. No key in
a commit, a log, a report or a test.

---

## 2. The work, in priority order

### E1. The aggregate itself, as a pure function

New module `rusterm/core/industry/aggregate.py`. No SQL — it receives
values and returns `Measure`-shaped results, exactly as
`rusterm/formulas.py` and `maritime_tanker.py` do. `method_version =
"industry.v1"`.

- Input: measure name, and a list of `(instrument_id, value | None)`.
- Output: `p25`, `median`, `p75`, `n`, or a null with a reason per
  §0.2 rulings 2–4.
- Quartiles: **linear interpolation between order statistics**, the
  method `statistics.quantiles(method="inclusive")` implements. Name the
  method in the docstring; a percentile without a stated method is not
  reproducible between two readers, let alone two versions.

**Done when** a test pins the numbers for a hand-computed set of nine
values (write the expected quartiles in the test as literals, computed by
hand, not by calling the same function); asserts that 7 contributing
members yield `peer_set_too_small`; asserts that nulls are excluded and
`n` reflects it; `python3 -m pytest -q` exits 0.

---

### E2. `as_of` chooses the versions

New method on the repository layer: for a sector peer set and a date,
return the peer set version in force and, per member, the snapshot in
force. Per §0.2 ruling 5, both are chosen **by date**, not filtered
afterwards.

- Peer set version: the one whose `valid_from <= as_of` and
  (`valid_to IS NULL` or `as_of < valid_to`). More than one match is a
  data defect — raise a `ValueError` naming both; do not pick one.
- Member snapshot: the newest `snapshot` with `as_of <= <date>` for that
  instrument. No snapshot by that date → the member contributes nothing
  and is counted in the reason table as `no_snapshot_at_date`.

**Done when** a test builds a sector of 10 members, computes an aggregate
at `2025-06-30`, then **changes the composition** (a new peer set version
from `2025-09-01`) and adds newer snapshots, then recomputes at
`2025-06-30` and asserts **the composition and every number are
identical** to the first run; and a second assertion shows the aggregate
at `2025-12-31` differs; `python3 -m pytest -q` exits 0.

---

### E3. The table, by the next free migration number

Per §0 and P2. One table, append-only, one row per (sector, date,
measure, method_version):

```
industry_aggregate(
  industry_aggregate_id TEXT PRIMARY KEY,
  peer_set_version_id TEXT NOT NULL REFERENCES peer_set_version(...),
  as_of TEXT NOT NULL,
  concept TEXT NOT NULL,
  p25 TEXT, median TEXT, p75 TEXT,
  n INTEGER NOT NULL,
  method_version TEXT NOT NULL,
  null_reason TEXT,
  built_at REAL NOT NULL,
  UNIQUE (peer_set_version_id, as_of, concept, method_version))
```

Values are TEXT for the same reason `measure.value` is: no float drift
between write and read. The `null_reason` rule from I4 holds — a null
triple requires a reason, and the reason comes from
`rusterm/reasons.py`.

The doctor's schema-drift check must know the new migration exactly as it
knows the previous one — same strength, no exemption.

**Done when** the migration applies on a fresh and on an existing
database, `_SCHEMA_VERSION` is bumped by exactly one, the migration list
test and the doctor test both cover it, a repeat build of the same
(sector, date) writes no duplicate row, and `python3 -m pytest -q`
exits 0; acceptance 13/13.

---

### E4. Reproducibility as an assertion, not a hope

The milestone says *воспроизводятся*. Make that a test that would fail
if any of the three levers moved.

Build the aggregate for a date, store it, then rebuild it after:

1. a new peer set version starting **after** that date;
2. a new snapshot for a member with a later `as_of`;
3. a re-ingest that adds facts with a later `period_end`.

After each, the stored row and the rebuilt values must be **identical**,
and the test asserts equality of the full tuple, not of the median alone.

**Done when** the three-lever test passes and the report quotes the
aggregate values before and after each lever; `python3 -m pytest -q`
exits 0.

---

### E5. The command

`rusterm industry --sector <peer_set_id> [--as-of <date>] [--json]`:

- prints one line per measure: `p25 / median / p75 (n=…)`, or the reason;
- `--as-of` defaults to today, as the other commands do;
- `--json` key set pinned by a test, the way B16 pinned the other
  commands;
- exit 0 when the sector resolved, 1 when it did not exist or the peer
  set was unverified — the second case must say which of the two it was.

**Done when** a subprocess test covers a resolved sector, an unknown
sector and an unverified one, pins the `--json` keys, and asserts the
exit codes; `python3 -m pytest -q` exits 0; acceptance 13/13.

---

### E6. What the aggregate is allowed to hide

A sector row that says `median = 0.11` over 8 of 14 members, with six
nulls, is a different statement from one over 14 of 14. The command and
the `--json` output must carry `n` and the reason counts beside every
number — not in a footnote, in the row.

**Done when** a test asserts the reason counts appear for a sector where
six members lack the measure, and that no aggregate value is ever printed
without its `n`; `python3 -m pytest -q` exits 0.

---

### E7. Milestone M7, written down

In the report's `Milestones` section: M7 with the commands that prove it —
the E2 same-date test and the E4 three-lever test — and, if you consider
it partial, exactly what is missing. "Достигнута" without a command is
not accepted.

---

### E8. The backlog

`agent/BACKLOG.md`, top down, by ID. Closing an item moves **the whole
block** into `## Done` as one `- [x]` line.

---

### E9. The bookkeeping

`agent/STATE.json` naming this task and this report, ending at
`"status": "awaiting_review"`; `## HANDOFF` filled with real values;
`agent/ACCEPTANCE-15.txt` taken at the head you hand over, `git add`ed
before the run.

**Done when** `tests/test_report_sections.py` passes,
`agent/ACCEPTANCE-15.txt` is non-empty and its `HEAD:` line is the commit
before the final `agent/` commit, and
`python3 -c "import json;d=json.load(open('agent/STATE.json'));assert d['task']=='agent/TASK-17.md' and d['status']=='awaiting_review'"`
succeeds.

---

## 3. Night end

```bash
git add agent/ACCEPTANCE-15.txt agent/REPORT-17.md agent/STATE.json
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-15.txt
git add agent/ACCEPTANCE-15.txt
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      E1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-15.txt)
Tests:           N passed, M skipped, K xfailed
Aggregate:       the p25/median/p75/n of one sector, verbatim
Reproducibility: the three levers of E4 — values before and after each
Migration:       number used, _SCHEMA_VERSION before and after
Milestones:      M7 yes/no — and if no, exactly what is missing
Strict xfail:    which remain and why
Network:         0 requests expected — state the real number
Model:           app LLM calls 0; your own model id and count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

Out of scope tonight, no exceptions for spare time:

- a mean, a weighted average or any composite sector score
- changing `PERCENTILE_MIN_PEERS`, `AGGREGATE_MIN_PEERS` or the churn
  threshold — they are invariant I6
- rewriting the company-versus-sector percentile that already exists
- Qt or any GUI; price vendors; IFRS/UK/CA (M6)
- industry metrics beyond Maritime/Tanker, which stays as it is
- a classifier that assigns companies to sectors — membership comes from
  a peer set that a human approved
- changing an existing flag, `--json` key or exit code
- refactoring green code that no item names

## 5. Stack

Python 3.12+, must also run on 3.14. Standard library; `pytest`;
`sqlite3` and `curses` from stdlib; `zstandard` optional with `gzip`
fallback; `httpx`/`requests` only inside `rusterm/providers/`.
Forbidden: ORM, `alembic`, `pandas`, `numpy`, async frameworks, `rich`,
`textual`. `statistics` from the standard library is allowed and is the
intended tool for E1. `from __future__ import annotations` at the top of
every module; builtin generics.

## 6. Acceptance script

`bash agent/acceptance.sh` — thirteen machine checks, 13/13 when you
start, never below it. **Editing that file is forbidden** — check 12
compares it byte for byte against `origin/main`. Think a check is wrong —
write it in `## Disputed`.
