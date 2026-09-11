# TASK-16 — M5: ни одна массовая операция не идёт без подтверждения

- **Status: ACCEPTED** — coordinator re-ran acceptance and the suite on
  `agent/night-2` on 10.09.2026: 13/13, 361 passed, 2 skipped, 0 xfailed.
  Rulings on every `Disputed` item are in `agent/TASK-19.md` §0.1.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-16.md`
- **Next in queue:** `agent/TASK-17.md` (M7), then `agent/TASK-18.md`
  (Canada and OTC). Both `Status: READY` and dependent on nothing here.
- **Depends on nothing in TASK-14 or TASK-15.** Every item below reads
  and writes code that exists today. If the two nights before this one
  went badly, this task is still runnable as written.
- **Goal of the night, in one sentence:** the half of milestone M5 that
  does not exist yet — a mass operation is proposed, shown, confirmed by
  a human and only then applied, atomically and with an audit row — and
  the model gets no tool that can change anything.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
bash agent/acceptance.sh
```

`Итог: пройдено 13, провалено 0`, or you are starting on a red tree —
that is the previous item's debt, fix it first.

Read, in full and from the repository: `docs/watchlist-and-llm.md` §2
and §3 (this task is that document turned into code),
`docs/processes.md` §«Процесс 3», `rusterm/core/llm.py`,
`rusterm/core/watchlist_io.py`, `rusterm/store/repos.py`
(`WatchlistRepo`, `AuditRepo`), `rusterm/cli/__init__.py`,
`tests/test_llm_guard.py`.

---

## 0.1. Where M5 stands

`docs/quality-and-observability.md` states the milestone in two halves:

> тест подтверждает: каждое числовое утверждение несёт ссылку; ни одна
> массовая операция не исполняется без подтверждения

**The first half is done** — `LlmSummarizer` substitutes numbers from the
snapshot, and a number in the text that is not in `citations` voids the
whole text; `tests/test_llm_guard.py` holds it. Do not touch it. D8 only
re-runs it and quotes the result.

**The second half does not exist.** There is no intent layer, no
read-only tool set, no dry-run, no confirmation, no atomic apply, no
audit row for a bulk change. `grep -rn "intent" rusterm/` returns
nothing outside unrelated words. That is the whole night.

**The real-key path stays out.** Everything below is exercised with a
fake client written in the tests. With `RUSTERM_LLM_API_KEY` unset the
suite must be green, and the report records
`LLM key unset — real path not exercised`. Do not simulate a real call
and do not weaken a test because the key is absent.

---

## 0.2. Rulings, so no fork is open at 03:00

1. **`confidence` is not a branch condition.** The document removed it
   deliberately: it is an uncalibrated number produced by the same model
   whose decision it would gate. Log it if the fake client returns it;
   never `if confidence > …`. A test asserts that a response with
   `confidence: 0.99` and an unresolved ticker still does **not** execute.
2. **The model gets no state-changing tool. Ever.** The four read-only
   tools in §2.4 are the whole surface. D2 makes that mechanical rather
   than a promise.
3. **The limit is 100 instruments, and it applies to composition edits
   only.** A scheduled `refresh --watchlist` pass is not a composition
   edit and needs no confirmation — `docs/watchlist-and-llm.md` §3.4 says
   so in as many words. D6 pins both sides.
4. **New command, not a renamed one.** `rusterm ops` is new surface; no
   existing flag, key or exit code changes. The `--json` key set of the
   new command is pinned by a test the way B16 pinned the other four.
5. **No network and no model call.** The night is offline. If you spend
   a request, say why in the report.

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
8. RECORD   one line in agent/REPORT-16.md: command + its output (§1.7).
```

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A genuinely obsolete assertion is
**replaced by a stronger one**, and the report says how the new one is
stricter.

**P2. Never edit an existing migration.** New migration, new number,
`_SCHEMA_VERSION` bumped. **Read `_SCHEMA_VERSION` from the file before
you write a number** — earlier tasks may have used 38 and 39.

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

`agent/REPORT-16.md` is **append-only and verified after every write.**

- **R1.** Append only: `printf '%s\n' "…" >> agent/REPORT-16.md` or a
  quoted heredoc with `>>`. Never `>`, never `open(p, "w")`.
- **R2.** After every append: `wc -c agent/REPORT-16.md && tail -3
  agent/REPORT-16.md`, and look at the output.
- **R3.** Chain with `&&`, never `;`.
- **R4.** The final HANDOFF is appended at the end; a section is edited
  in place by line, never by rewriting the file from a variable. After
  writing it, `wc -c` must be larger than before, never smaller.

Sections, in this order: **Done**, **Blocked**, **What not to trust**,
**Disputed**, **HANDOFF**. Last line always `NOW: <item>, step <n>`.

`agent/STATE.json`, same commit as the work:

```json
{"task": "agent/TASK-16.md", "report": "agent/REPORT-16.md",
 "item": "D1", "step": "4", "status": "working",
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
puzzle — no User-Agent change, no proxy, no mirror; fetched data never
enters git except a trimmed payload under `tests/data/edgar/`;
`fixtures/` stays synthetic.

### 1.13. Money and quota

Free tier only for your own model; record a switch to a paid one in
`STATE.json`. At 800 of your own calls, close the night with §3. The
application's LLM path: **no key tonight** — the fake client and a report
line, never a simulation. No key in a commit, a log, a report or a test.

---

## 2. The work, in priority order

### D1. Intent, and what happens when the model does not produce one

New module `rusterm/core/intent.py`. No HTTP, no client construction —
it receives a response **value** and returns a decision value.

- The eight intents of `docs/watchlist-and-llm.md` §2.2 are a frozen
  tuple. An intent outside it is not an intent.
- Required parameters per intent are a table in the module, not a
  guess at call time.
- Response that is not JSON, or an intent outside the list: **one**
  retry with a hard format reminder, then a `Clarification` value naming
  what was not understood. Never an exception, never an action
  (`docs/processes.md`, the error table).
- Nothing in this module touches the database.

**Done when** tests cover four cases — a good response, a non-JSON
response (one retry, then clarification), an unknown intent, and a known
intent missing a required parameter — and assert that the fake client was
called exactly twice in the retry case and that no database exists to be
changed; `python3 -m pytest -q` exits 0.

---

### D2. Four read-only tools, and a guard that they stay read-only

`docs/watchlist-and-llm.md` §2.4, exactly four:
`resolve_ticker`, `list_industry_instruments`, `get_peer_set`,
`get_snapshot_block`. Wire them to the repositories that already answer
those questions; do not invent a fifth.

The guard is the point of the item, not the tools:

- the registry is an explicit mapping name → callable, and the test
  asserts its key set **exactly** — a tool added without a task item
  fails the suite;
- after calling every tool in turn against a seeded database, the test
  asserts the database file's sha256 is unchanged.

**Done when** both assertions exist and pass, and adding a sixth entry to
the registry makes the suite red (check it by adding one, watching it go
red, and removing it); `python3 -m pytest -q` exits 0.

---

### D3. The five conditions, and `confidence` is not one of them

`docs/watchlist-and-llm.md` §2.3. A proposed operation is executable only
if **all** hold: intent recognised; required parameters present; every
instrument resolved to exactly one `instrument_id`; result size within
the limit; the user confirmed the shown list. Anything else is a
clarifying question, never an action taken on a guess.

Per §0.2 ruling 1: `confidence` may be recorded, never branched on.

**Done when** a test walks all five conditions — one failing at a time,
four passing — and asserts each yields a clarification and no state
change; a sixth case with `confidence: 0.99` and an ambiguous ticker
asserts the operation still does not execute;
`grep -rn "confidence" rusterm/ | grep -v "#"` shows no comparison
operator; `python3 -m pytest -q` exits 0.

---

### D4. Dry-run shows the whole list, per position

Four statuses per instrument, per §2.5: **будет добавлена**,
**исключена фильтром**, **уже в списке**, **не разрешилась**. No time
estimate — the document forbids it, and the two estimates its earlier
revision carried disagreed by an order of magnitude.

Dry-run makes no write of any kind: no version, no member, no coverage
row, no audit row.

**Done when** a test seeds a watchlist that already holds one of the
proposed instruments, one that will not resolve and one excluded by a
filter, asserts all four statuses appear, and asserts the database
sha256 is unchanged after the dry-run; `python3 -m pytest -q` exits 0.

---

### D5. Confirmation, and an apply that is all or nothing

- Applying creates **one** new watchlist version and adds the members in
  **one** SQLite transaction. A failure in the middle leaves no version
  and no member — not a partial list.
- The previous version stays reachable, so §3.3's rollback keeps working
  (it is already covered by `tests/test_watchlist.py`; do not modify it).

**Done when** a test forces a failure part-way through a 10-instrument
apply (a member whose insert raises) and asserts: zero new
`watchlist_version` rows, zero new `watchlist_member` rows, the current
version still the pre-operation one, and the error returned as a value;
`python3 -m pytest -q` exits 0.

---

### D6. The limit of 100, and what it does not cover

Per §0.2 ruling 3.

- A composition edit above 100 instruments requires a second, explicit
  confirmation naming the size. Without it: refused as a value, nothing
  written.
- `refresh --watchlist` is **not** a composition edit: it creates no
  version and changes no member. It must keep working with no
  confirmation at all.

**Done when** a test proposes 101 instruments and asserts refusal
without the second confirmation and success with it; a second test runs
`refresh --watchlist` on a 101-member list and asserts it needs no
confirmation and creates no watchlist version;
`python3 -m pytest -q` exits 0.

---

### D7. Every mass operation leaves a row

`audit_log` gets one row per operation — including the refused and the
clarified ones, because "we did not do it" is the part worth being able
to prove. Action `ops`, target the watchlist id, payload the intent, the
counts and the decision, `confirmed` true only when the user confirmed,
`result` one of `applied` / `refused` / `clarification`.

`AuditRepo.log()` returns a failure reason as a value (B12); the command
prints it to stderr and still exits on its own merits.

**Done when** a test asserts one row for each of the three outcomes with
the right `confirmed` and `result`, and that a read-only log directory
still leaves the database row and prints to stderr;
`python3 -m pytest -q` exits 0.

---

### D8. The command, and the milestone line

`rusterm ops --watchlist <id> --request "<text>" [--confirm] [--json]`:

- without `--confirm` — dry-run, per D4;
- with `--confirm` — apply, per D5;
- `--json` — the same machine-readable, key set pinned by a test the way
  B16 pinned the other four commands;
- exit 0 applied or dry-run, 1 refused or clarification needed.

Then, in the report's `Milestones` section, the M5 line: **both** halves,
each with the command that proves it. The first half is
`python3 -m pytest tests/test_llm_guard.py -q` — run it, quote the
result, do not edit the file.

**Done when** a subprocess test covers dry-run, confirm and refusal with
their exit codes and pinned `--json` keys; the `Milestones` section
carries the M5 line with both commands; `python3 -m pytest -q` exits 0;
acceptance 13/13.

---

### D9. The backlog

`agent/BACKLOG.md`, top down, by ID. Closing an item moves **the whole
block** into `## Done` as one `- [x]` line — never delete a bullet's
first line and leave its continuation behind.

---

### D10. The bookkeeping

`agent/STATE.json` naming this task and this report, ending at
`"status": "awaiting_review"`; `## HANDOFF` filled with real values;
`agent/ACCEPTANCE-14.txt` taken at the head you hand over, `git add`ed
before the run.

**Done when** `tests/test_report_sections.py` passes,
`agent/ACCEPTANCE-14.txt` is non-empty and its `HEAD:` line is the commit
before the final `agent/` commit, and
`python3 -c "import json;d=json.load(open('agent/STATE.json'));assert d['task']=='agent/TASK-16.md' and d['status']=='awaiting_review'"`
succeeds.

---

## 3. Night end

```bash
git add agent/ACCEPTANCE-14.txt agent/REPORT-16.md agent/STATE.json
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-14.txt
git add agent/ACCEPTANCE-14.txt
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      D1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-14.txt)
Tests:           N passed, M skipped, K xfailed
M5 half one:     pytest tests/test_llm_guard.py -q → …
M5 half two:     the command that proves confirmation gates the apply → …
Read-only tools: the exact key set the guard pins
Milestones:      M5 yes/no — and if no, exactly what is missing
Strict xfail:    which remain and why
Network:         0 requests expected — state the real number
Model:           app LLM calls 0 (fake client); your own model id and count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

Out of scope tonight, no exceptions for spare time:

- a real model call, a provider for one, or any HTTP in `core`
- Qt or any GUI; price vendors; IFRS/UK/CA (M6); Industry View (M7)
- a fifth read-only tool; any tool that writes
- branching on `confidence`
- changing an existing flag, `--json` key or exit code
- the concept map, the 1100-day rule, any floor
- refactoring green code that no item names

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
