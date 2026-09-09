# TASK-15 — what the user can check for himself

- **Status: READY** — take this only when `agent/TASK-14.md` is finished
  and handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-15.md`
- **Next in queue:** `agent/TASK-16.md` (M5), `agent/TASK-17.md` (M7),
  `agent/TASK-18.md` (Canada and OTC). All `Status: READY` and dependent
  on nothing here — take the next one rather than idling.
- **Depends on:** TASK-14 A1–A4. C2 and C5 assume the pass is linear and
  `restated_revisions` is issuer-scoped. If A1–A3 did not land, do C1,
  C3, C4, C6 and say in `## Blocked` that C2 waits on A1.
- **Goal of the night, in one sentence:** every number the terminal shows
  can be traced by the person looking at it — a stale fact is visible as
  stale rather than silently absent, a shortfall is pinned to the issuers
  that cause it instead of to a wish, and the commands say what happened
  instead of exiting quietly.

Section 1 is the working protocol and outranks the task list. It is the
same protocol as TASK-14 §1, reproduced in full so this file stands alone.

---

## 0. Start here

```bash
git checkout agent/night-2
bash agent/acceptance.sh
```

`Итог: пройдено 13, провалено 0`, or you are starting on a red tree —
fix that first, it is the previous item's debt.

Read, in full and from the repository: `rusterm/core/snapshot.py`,
`rusterm/tui/model.py`, `rusterm/core/verification.py`,
`rusterm/store/doctor.py`, `rusterm/cli/__init__.py`,
`tests/test_m3_snapshot.py`.

---

## 0.1. Ruling carried into this task

**The `operating_margin` 15 / `gross_margin` 10 strict xfail is retired
by C1, and this is the coordinator's decision, not yours to re-derive.**

It was the right instrument when the shortfall might have been a code
defect. TASK-12 settled that it is not: JPM is a bank, PFE/CVX/XOM do not
tag `OperatingIncomeLoss`, and 13 of 20 issuers never tag `GrossProfit`.
A strict xfail that can only go red if a third party changes its filing
habits is a permanent yellow light, and it hides the thing actually worth
guarding — *which* issuers are short and *why*. C1 replaces it with an
assertion that is strictly harder to satisfy.

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
8. RECORD   one line in agent/REPORT-15.md: command + its output (§1.7).
```

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A genuinely obsolete assertion is
**replaced by a stronger one**, and the report says how the new one is
stricter. C1 is the single authorised removal this night, and only
because it replaces a marker with a stronger assertion.

**P2. Never edit an existing migration.** New migration, new number,
`_SCHEMA_VERSION` bumped. Next free number is **39** if TASK-14 used 38,
otherwise **38**. Check `_SCHEMA_VERSION` before you write it.

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`. Except fetched data — §1.12 takes precedence for it.

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

`agent/REPORT-15.md` is **append-only and verified after every write.**

- **R1.** Append only: `printf '%s\n' "…" >> agent/REPORT-15.md` or a
  quoted heredoc with `>>`. Never `>`, never `open(p, "w")`.
- **R2.** After every append: `wc -c agent/REPORT-15.md && tail -3
  agent/REPORT-15.md`, and look at the output.
- **R3.** Chain with `&&`, never `;`.
- **R4.** The final HANDOFF is appended at the end; a section is edited
  in place by line, never by rewriting the file from a variable. After
  writing it, `wc -c` must be larger than before, never smaller.

Sections, in this order: **Done**, **Blocked**, **What not to trust**,
**Disputed**, **HANDOFF**. Last line always `NOW: <item>, step <n>`.

`agent/STATE.json`, same commit as the work:

```json
{"task": "agent/TASK-15.md", "report": "agent/REPORT-15.md",
 "item": "C1", "step": "4", "status": "working",
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

**N1. One source: SEC EDGAR.** No vendor, scraper, mirror or aggregator.

**N2.** `RUSTERM_SEC_UA` must carry a real contact, read by the
application from `~/.rusterm.env`. Unset → `ConfigError` **value**, the
item degrades to the offline path, the report records
`SEC_UA UNSET — network path not exercised`. Never hardcode, commit or
invent a contact.

**N3.** 5 requests/second, 5000/night ceiling, 2 retries then give up.
Count every request in `STATE.json` `"net_requests"`.

**N4.** 403 or 429 is a stop, not a puzzle. Back off, record, move on.
Never change the User-Agent or route around it.

**N5.** Fetched data never enters git, except a trimmed payload under
`tests/data/edgar/`.

**N6.** `fixtures/` stays synthetic-only.

**N7.** A network test skips cleanly when `RUSTERM_SEC_UA` is unset.

**Only C5 uses the network, and it costs at most 8 requests.**

### 1.13. Money and quota

Free tier only for your own model; record a switch to a paid one in
`STATE.json`. At 800 of your own calls, close the night with §3. The
application's LLM path: no key → the fake client and a report line, never
a simulation; with a key → 50 calls for the night, counted in
`"llm_calls"`. No key in a commit, a log, a report or a test.

---

## 2. The work, in priority order

### C1. The shortfall is pinned to issuers, not to a wish

Per §0.1. In `tests/test_m3_snapshot.py`:

- Delete `test_w4_known_short_floors_operating_margin_and_gross_margin`
  together with its `xfail(strict=True)` marker.
- In its place, in the **passing** test, assert the exact composition of
  the two gaps:
  - the set of issuer tickers whose `operating_margin` is null is exactly
    the six the data produces, and every one of them carries
    `missing_data: operating_income`;
  - the count of issuers with a non-null `gross_margin` is exactly 7, and
    every null carries `missing_data: gross_profit`.
- Take the six tickers from the M3 run, do not guess them; write them in
  the test as a literal set with a comment naming the run.

This is stricter than the retired test in both directions: a new issuer
losing `operating_income` fails, and an issuer *gaining* it fails too,
which is exactly the review signal the xfail was there to raise.

**Done when** `grep -rn "known_short_floors" tests/` is empty,
`python3 -m pytest tests/test_m3_snapshot.py -q -rx` exits 0 with the
composition assertions in the passing test, the printed table is copied
into the report, and `python3 -m pytest -q` exits 0 with **one fewer
xfail** than at the start of the night.

---

### C2. The pass stays linear — a guard, not a one-off measurement

Depends on TASK-14 A1. A fixed index is worth nothing without a test that
notices when someone drops it.

- A test asserts, on a fresh database, that `EXPLAIN QUERY PLAN` for each
  of the three hottest queries — `restated_revisions`,
  `as_reported_facts`, `get_measures` — contains `SEARCH` and **no**
  `SCAN` of `fact` or `measure`.
- A second test builds snapshots for 100 issuers and asserts the mean
  per-issuer time is under a named constant with ×3 headroom, and that
  the **second** hundred costs no more than 1.5× the first — the shape of
  the curve, not the absolute speed of the machine. That ratio is what
  catches a return of quadratic behaviour on any hardware.

**Done when** both tests exist and pass, the measured mean per-issuer
time and the two-half ratio are in the report, and `python3 -m pytest -q`
exits 0.

---

### C3. A command that finds nothing says so

`rusterm refresh --watchlist <unknown-id>` currently prints nothing and
exits 0 — indistinguishable from a watchlist that is up to date.

- Unknown watchlist id → stderr line naming the id, exit code **1**.
- An empty but existing watchlist → a line saying it is empty, exit 0.
- `--json` keeps its key set in both cases; add `"error"` only as a
  member of the existing `results` shape, never as a new top-level key
  (a renamed or added top-level key is a task item, not a fix).

**Done when** a subprocess test pins all three cases — exit codes,
stderr, and `json.loads` on the `--json` variants;
`python3 -m pytest -q` exits 0.

---

### C4. `doctor` sees the two new kinds of drift

- Rows in `issuer_ingest_state` whose `issuer_id` has no `issuer` row —
  orphans, reported with counts, exit 1.
- Every index the schema declares is present in `sqlite_master` —
  a dropped index is drift exactly as a dropped table is, and after
  TASK-14 A1 there is something to check.

**Done when** a test seeds one orphan state row and one dropped index and
asserts `doctor` exits 1 naming both; `python3 -m pytest -q` exits 0.

---

### C5. A stale fact is visible, not vanished

The Y2 eligibility rule (1100 days) keeps a decade-old fact out of the
measures. That is right. But the fact is still in the store, and the user
looking at `missing_data: operating_income` deserves to see *why* — that
Berkshire's last `OperatingIncomeLoss` is from 2012, not that the number
never existed.

- The source panel data (`rusterm/tui/model.py`) and `rusterm verify`
  show excluded facts marked `устаревший (последний 2012-12-31, anchor
  2025-12-31)` — the fact's own period end and the anchor it was measured
  against.
- Nothing changes in the measure itself. This is presentation of state
  that already exists; if it needs a new query, it is a read on
  `as_reported_facts`, not a new column.

**Done when** a test asserts that for an issuer with a 2012
`operating_income` and 2025 revenue the panel data lists the 2012 fact
with the stale marker and both dates, and that the measure's reason is
unchanged; `python3 -m pytest -q` exits 0.

---

### C6. The incremental pass against the live feed

Network, and the only item that uses it. Skips cleanly without
`RUSTERM_SEC_UA` (N2, N7).

- Two real issuers already in `tests/data/edgar/`, a watchlist, two
  consecutive `refresh --watchlist` passes against the live feed.
- Assert: the second pass makes 2 `submissions` requests and **0**
  `companyfacts` requests, and creates no `raw_object`, `fact` or `job`.
- At most **8** requests for the whole item. Record the real count in
  `STATE.json` `"net_requests"` and in the report.

**Done when** the test passes with a contact set, or skips with
`SEC_UA UNSET — network path not exercised` recorded in the report; the
request count is stated; `python3 -m pytest -q` exits 0.

---

### C7. The backlog

`agent/BACKLOG.md`, top down, by ID. Closing an item moves **the whole
block** into `## Done` as one `- [x]` line — never delete a bullet's
first line and leave its continuation behind.

---

### C8. The bookkeeping

`agent/STATE.json` naming this task and this report, real
`net_requests`, ending at `"status": "awaiting_review"`; `## HANDOFF`
filled with real values; `agent/ACCEPTANCE-13.txt` taken at the head you
hand over, `git add`ed before the run.

**Done when** `tests/test_report_sections.py` passes,
`agent/ACCEPTANCE-13.txt` is non-empty and its `HEAD:` line is the commit
before the final `agent/` commit, and
`python3 -c "import json;d=json.load(open('agent/STATE.json'));assert d['task']=='agent/TASK-15.md' and d['status']=='awaiting_review'"`
succeeds.

---

## 3. Night end

```bash
git add agent/ACCEPTANCE-13.txt agent/REPORT-15.md agent/STATE.json
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-13.txt
git add agent/ACCEPTANCE-13.txt
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      C1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-13.txt)
Tests:           N passed, M skipped, K xfailed
Measure table:   the printed M3 table, verbatim
Short measures:  the six tickers C1 pinned, and the gross_margin seven
Pass shape:      mean per-issuer time, second-half / first-half ratio
Milestones:      M4 yes/no; M5 no (no key)
Strict xfail:    which remain and why
Network:         RUSTERM_SEC_UA set? — N requests (ceiling 8 tonight)
Model:           app LLM calls N; your own model id and call count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

Out of scope tonight, no exceptions for spare time:

- Qt or any GUI; price vendors; IFRS/UK/CA (M6); Industry View (M7)
- a second taxonomy; any new source tag; new composite concepts
- a daemon, a service, a background thread
- renaming or adding a top-level `--json` key, an exit code or a flag
  beyond what C3 names
- refactoring green code that no item names
- changing the 1100-day rule, the concept map, or any floor

## 5. Stack

Python 3.12+, must also run on 3.14. Standard library; `pytest`;
`sqlite3` and `curses` from stdlib; `zstandard` optional with `gzip`
fallback; `httpx`/`requests` only inside `rusterm/providers/`.
Forbidden: ORM, `alembic`, `pandas`, `numpy`, async frameworks, `rich`,
`textual`. `from __future__ import annotations` at the top of every
module; builtin generics.

## 6. Acceptance script

`bash agent/acceptance.sh` — thirteen machine checks, 13/13 when you
start, never below it. **Editing that file is forbidden** — check 12
compares it byte for byte against `origin/main`. Think a check is wrong —
write it in `## Disputed`.
