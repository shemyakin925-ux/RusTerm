# TASK-21 — Фаза 2: сведение полос, сквозные пути и веха M8

- **Status: READY** — take it when the lanes of `agent/TASK-20.md` are
  pushed, or when 09:30 of that night has passed and some of them are
  not. It is written to work with **whatever subset actually merged**.
- **Branch:** `agent/night-3` (the foundation branch; the coordinator
  merges the lane branches into it — see §0.2 for what to do if that
  has not happened yet)
- **Report:** `agent/REPORT-21.md`
- **Goal of the night, in one sentence:** the pieces ten processes built
  separately become one program — a user picks any of six markets, gets
  data or a named refusal, imports a file when the refusal says to, and
  every number in the snapshot says where it came from.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

### 0.1. Establish what actually merged. Do not assume

```bash
git checkout agent/night-3 && git pull
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
git log --oneline n3-foundation..HEAD | head -40
for l in L1 L2 L3 L4 L5 L6 L7 L8 L9 L10; do
  printf '%s ' "$l"; git rev-parse --verify -q "agent/n3-$l" || echo "absent"
done
python3 -c "import rusterm.providers as p; print(p.available())"
```

**Write the result of that last loop into the report before item H1.**
It is the ground truth about what exists; a lane's HANDOFF saying `DONE`
is a claim until the branch is in the log.

### 0.2. If the lanes are not merged yet

Merging is the coordinator's job (ADR-0012 §4). If you arrive and the
branches are pushed but unmerged, **do not merge them yourself.** Write
`LANES UNMERGED: <list>` in `## Blocked`, and spend the night on the
items below that need only the foundation: H1, H6, H7, H8. They are
placed to be worth a night on their own.

### 0.3. Every item below is conditional, and says on what

An item whose lane never landed is **not** a failure — it is `n/a`, and
the report says which lane it was waiting for. Do not implement a
missing lane's work from scratch tonight: a rushed re-implementation of
somebody else's zone is worse than an honest gap.

Read, in full: the three ADRs 0010/0011/0012, `agent/TASK.md`,
`agent/TASK-20.md` §2 (the zone lists — they tell you who owned what),
and every `agent/REPORT-20-*.md` that exists, **starting with their
`Blocked` and `Disputed` sections**, not their `Done`.

---

## 1. Working protocol

Identical to `agent/TASK-19.md` §1 — the cycle, the five prohibitions,
selfcheck, the stuck rule, the stop rule, commit format, R1–R4
bookkeeping, push, the 09:30 line, network rules N2–N7, money and quota.
Read it there. Two additions:

- **The zone rule is over.** This task is the one that is allowed to
  touch shared files — `rusterm/normalize/concepts.py`,
  `rusterm/core/snapshot.py`, `rusterm/store/doctor.py`. That is why it
  is sequential and single-process.
- **A migration is allowed again**, if and only if H4 needs one. Read
  `_SCHEMA_VERSION` from the file. One number, one bump.

`agent/STATE.json` returns as the single state file; fold the per-lane
`agent/state/*.json` into it at H8 and say in the report what each lane
reported at its end.

---

## 2. The work, in priority order

### H1. Consolidate: one truth about what the program can do

**Needs:** foundation only.

`rusterm/cli/__init__.py` — a `markets` subcommand printing, per
registry row: code, jurisdiction, venue kind, provider, access level,
**whether its provider is actually implemented**, and the issuer count
in the local database.

A user must be able to answer "can this program get Korean data?"
without reading source. `provider_not_implemented` prints as exactly
that, not as a blank.

**Done when:** `python3 -m rusterm.cli markets` prints six rows; a test
asserts a market whose module is absent prints
`provider_not_implemented` and the command still exits 0; piped output
carries no ANSI (the existing rule from backlog B11).

### H2. Close the taxonomy gaps the lanes found

**Needs:** L10's gap list (or L1–L4's reports if L10 did not run).
`rusterm/normalize/concepts.py`.

Each new market's issuers hit tags absent from the `ifrs-full`
dictionary built for Canada. The lanes were forbidden to touch
`concepts.py`; you are not.

- Add tags **only** where a lane recorded a concrete missing tag against
  a concrete recorded payload. **A tag added without a payload that
  needs it is not allowed** — that is guessing, and it silently changes
  measures for markets nobody looked at.
- Every added tag gets a one-line comment: which market, which issuer,
  which payload proved it.

**Done when:** the measure table `measure -> n/N + reasons` is recomputed
for every market that landed and is in the report; `golden_m2.json` and
`golden_m6_ca.json` values are **unchanged** (assert it — the US and CA
numbers must not move because a Korean tag was added); the full suite is
green.

### H3. End to end, per market, as a test

**Needs:** whichever of L1–L4 landed.

One e2e test per landed market, all from recorded payloads, no network:
add issuer → ingest → build snapshot → measures present with reasons →
export carries the market code.

**Done when:** `python3 -m pytest -k e2e -q` green; the report lists one
line per market: `<code>: issuers N, measures M/10, export ok`.

### H4. The refusal path is a first-class path

**Needs:** foundation; better with L3/L4/L6.

The user's rule is that a company which cannot be downloaded is offered
manual import (ADR-0010 §3). Prove the whole loop as one test:

`add` a non-auto-ingestible issuer → `manual_import_required` naming the
import command → run that command on a synthetic document → facts land
with `source_kind='manual'` → they appear in the snapshot marked, and
the unverified ones enter no formula.

**Done when:** that single test passes end to end; it asserts **zero**
`issuer` rows at the refusal step and non-zero `fact` rows with
`source_kind='manual'` at the end; the refusal message contains the
exact command string a user can copy.

### H5. `doctor` learns the new shapes

**Needs:** foundation; H4 for the manual half.
`rusterm/store/doctor.py`.

- Documents on disk without a `document` row, and rows without a file —
  reported both directions (the shape of backlog B9).
- Facts with `source_kind='manual'` whose document is missing.
- Registry rows whose provider module is absent.
- Per-market coverage: issuers, facts, last successful collection.

**Done when:** `python3 -m rusterm.cli doctor` reports each of the four
on a deliberately damaged database, and reports clean on a healthy one;
both asserted by tests.

### H6. The guard that makes the recurring defect impossible

**Needs:** foundation (F7 built `selfcheck.sh`).

A red acceptance was pushed on three separate nights because an exit
code went through `| tail`. F7 gave a tool; this makes it structural.

- A test in `tests/` reads `agent/selfcheck.sh` and asserts it captures
  status before piping, and that it cannot exit 0 with a dirty tree.
- The same test asserts `agent/acceptance.sh` is byte-identical to
  `origin/main` — the same thing check 12 does, so a plain `pytest` run
  catches it too, not only the acceptance script.

**Done when:** both assertions pass; deliberately breaking either makes
the test fail with a message naming which.

### H7. Secrets, proven absent rather than assumed absent

**Needs:** foundation.

Four keys now exist: `RUSTERM_SEC_UA`, `RUSTERM_LLM_API_KEY`,
`RUSTERM_DART_KEY`, and whatever a lane added.

- A test asserts no file in `git ls-files` matches the shapes of an
  OpenRouter key (`sk-or-` followed by a long token), a bearer token, or
  a `RUSTERM_*_KEY=` line with a value.
- A test asserts a `ConfigError` for a missing key **never** contains
  the environment variable's value, only its name.
- `rusterm doctor` reports which keys are set — **by name and set/unset
  only, never a prefix, never a suffix, never a length.**

**Done when:** all three pass; the report confirms the scan covered
every tracked file, with the file count.

### H8. Milestone M8, stated with its evidence

**Needs:** everything above that landed.

Append to the report, each claim with the command that proves it:

- which of the six markets reach data, and by which provider;
- the measure table per market;
- the manual-import loop, with counts of records produced, verified and
  rejected;
- which model the LLM path used and what the free models scored (L7);
- what M8 does **not** yet cover, named honestly.

Fold the per-lane `agent/state/*.json` into `agent/STATE.json`, and set
`"status": "awaiting_review"`.

**Done when:** `bash agent/selfcheck.sh` exits 0; every claim above has
its command and its real output beside it in the report.

### H9. Backlog

`agent/BACKLOG.md`, top-down, only if H1–H8 are done before 09:30.

---

## 3. Closing the shift

```
Status:          DONE | PARTIAL | BLOCKED
Lanes merged:    the list from §0.1, and which were absent
Items done:      H1, H2, …
Items n/a:       … and the lane each was waiting for
Acceptance:      the "Итог" line and the captured exit status
Tests:           N passed, N skipped, N xfailed
Schema:          _SCHEMA_VERSION <old> -> <new>, or "unchanged"
Markets reached: per code — provider, issuers, measures M/10
Golden unchanged: golden_m2.json and golden_m6_ca.json — assert output
Manual import:   records produced / verified / rejected
Secrets scan:    files scanned, hits (must be 0)
M8:              reached | partial — and exactly what is missing
Network:         requests used
Model:           app llm_calls N; your own model id
Pushed:          yes/no
Questions for the coordinator:
1. …
```
