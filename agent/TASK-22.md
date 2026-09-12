# TASK-22 — Долг после M8: календарь, сохранность данных, и программа, которую можно установить

- **Status: READY** — take it when `agent/TASK-21.md` is finished and
  handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-4` (branch it from the head of `agent/night-3`)
- **Report:** `agent/REPORT-22.md`
- **Sequential, one process.** It touches shared files by design; there
  is nothing here to fan out.
- **Depends on TASK-21 only for J1 and J2.** Everything from J3 down is
  runnable even if the M8 lanes went badly — that is deliberate, so a
  bad night upstream does not waste this one.
- **Goal of the night, in one sentence:** the things that were true
  while there was one market, one currency and one machine stop being
  true — the fiscal calendar stops being December for everyone, the
  user's irreplaceable data becomes restorable, and `rusterm` becomes a
  command you install rather than a module you invoke.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-3 && git pull
git checkout -b agent/night-4
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -m rusterm.cli markets
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
```

`STATUS=0` required. `markets` tells you which of the six markets
actually reached data — **J1 and J2 are scoped by that output, not by
what TASK-20 intended.** Read `_SCHEMA_VERSION` from the file; do not
assume a number.

**First commit:** create `agent/REPORT-22.md` with its five section
headers and repoint `agent/STATE.json` at it in the same commit —
`tests/test_report_sections.py` reads the report `STATE.json` names, so
repointing before the file exists turns the suite red.

Read, in full: `rusterm/core/peers.py`, `rusterm/core/fact.py`,
`rusterm/core/industry/aggregate.py`, `rusterm/store/paths.py`,
`rusterm/store/raw_store.py`, `rusterm/store/doctor.py`,
`rusterm/tui/model.py`, `rusterm/core/tools.py`, `pyproject.toml`,
`docs/adr/0010-rynki-vne-edgar.md`, `agent/TASK.md`.

## 0.1. Why this night exists

Five things were measured by the coordinator on 10.09.2026 and are
facts, not suspicions:

| Measured | Consequence |
|---|---|
| `grep -n "jurisdiction\|currency\|market" rusterm/core/peers.py` → **no matches** | a peer set has never known what country or currency it holds |
| no `backup`/`restore` anywhere in `rusterm/` | the only copy of a manually imported fact is one SQLite file |
| no `.github/workflows` | acceptance runs only when a human runs it — and ten parallel branches just landed |
| `requires-python = ">=3.12"`, installed 3.14.6 | 3.12 support is a claim nobody has ever tested |
| `list_industry_instruments` returns a hardcoded `[]` | M7 built the aggregate; the tool that should expose it was never wired |

The last one is the coordinator's own dangling promise: `TASK-19` §0.1
said it would be wired in TASK-21, and TASK-21 has no such item. It is
J6 here. Recorded so the queue does not quietly lose it.

---

## 1. Working protocol. This outranks the task list

Identical to `agent/TASK-19.md` §1 — the cycle, the five prohibitions,
the selfcheck, the stuck rule, the stop rule, the commit format, the
R1–R4 bookkeeping, push, the 09:30 line, the network rules N2–N7, money
and quota. **Read it there.** Three points that bite tonight:

- **P2 applies twice.** J3 and J4 each want schema. Read
  `_SCHEMA_VERSION` before each, never edit an applied migration.
- **P1 applies to `golden_m2.json` and `golden_m6_ca.json`.** Several
  items below touch code that produces those numbers. **They must not
  move.** A changed golden value is a stop under §1.5, not a finding.
- `docs/` is frozen; **a new ADR is the one permitted change** there.

`agent/STATE.json` is the single state file again (the per-lane files of
TASK-20 were folded in by TASK-21 H9).

---

## 2. The work, in priority order

### J1.0. Precondition, added by the coordinator 12.09.2026 — read before J1

**H3 landed** (TASK-21 accepted, `agent/ACCEPTANCE-21.txt`); the branch
you cut from already has the tripwire. But J1 as written could not have
been satisfied, and the reason was measured, not guessed:

```
grep -n "\"currency\"" rusterm/parsers/__init__.py
  86:  "currency": None,
  155: "currency": None,
  263: "currency": None,
```

**No parser writes `fact.currency`. Every fact in the repository is
blank.** So "every exported absolute number carries its currency" has
nothing to carry: the currency string lives in `fact.unit` (the
companyfacts units key), and the H3 firewall, though armed and tested,
has never seen a currency in real data. This is the executor's own
honest finding in `REPORT-21.md` §H9, confirmed by the coordinator.

**Therefore J1 starts here, and this part is done first:**

- The EDGAR parser records the currency it already has: the
  companyfacts `units` key is the currency for money concepts
  (`USD`, `CAD`, …). Write it to `fact.currency`. `unit` keeps its
  present meaning and value — this adds a field, it does not move one.
- A unit that is not a currency (`shares`, `pure`, `USD/shares`) leaves
  `fact.currency` `None` — that is correct, not missing.
- `manual/pipeline.py` writes `currency=None` deliberately (a human
  typed the number, the currency was not parsed). It stays `None` and
  the snapshot marks it unverified, as today.
- **The blank rule from the TASK-21 ruling lands with this change and
  only with it:** once a provider records currency, a blank on a money
  fact from that provider is `missing_data`, and a peer set mixing
  blanks with a stated currency is `currency_mismatch` — not silently
  "that one currency". Before this commit, blanks stay legitimate.
- `golden_m2.json` / `golden_m6_ca.json` **may move in this commit and
  in no other.** Quote the before/after diff in the report and say
  which field changed. If they do not move, say that too.

**Done when:** a test asserts a fact ingested from a recorded EDGAR
payload has `currency == "USD"` (and the CA one `"CAD"`), and that a
`shares` fact has `currency is None`; `SELECT DISTINCT currency FROM
fact` over a fresh ingest no longer returns `[None]` — paste the real
output; the goldens are either unchanged or their diff is in the report.

**If this cannot be done by 03:00, stop it and write J1.0 in `Blocked`
with what you found** — then do J1's display half over `fact.unit` as
today and say plainly in the report that the currency shown is derived
from the unit key, not recorded. A named half-measure beats a silent
one. Everything from J3 down does not depend on this.

### J1. Валюта доезжает до пользователя, а не только до стоп-крана

**Needs:** J1.0 above (this night) and TASK-21 H3 (landed, accepted).

The tripwire refuses. This item makes the refusal legible.

- Every displayed and exported absolute number carries its currency.
  A snapshot states the currency of its issuer; an aggregate states the
  currency it is stated in, or `currency_mismatch` and the list.
- `coverage` counts `currency_mismatch` separately from `missing_data` —
  they are different problems and a user fixes them differently.
- The TUI card shows the currency beside absolute measures.
- **Still no FX provider.** Conversion is not in scope and adding a
  rates source is out of bounds (ADR-0010: a source is a registry row,
  and nobody authorised one).
- **An `fx_rate` table already exists in the schema** and nothing fills
  it. Do not create a second one, and do not start filling this one —
  note in the report whether its shape would serve conversion when a
  rates source is eventually authorised.

**Done when:** `python3 -m rusterm.cli export` output carries a currency
on every absolute measure, asserted by a test; a test asserts
`golden_m2.json` and `golden_m6_ca.json` values are unchanged; the
report shows a `coverage` run distinguishing the two reasons.

### J2. Peer set знает, кого он держит

**Needs:** whichever markets landed. `rusterm/core/peers.py`.

`peers.py` mentions neither jurisdiction, market nor currency. With six
markets that is no longer defensible: peers are chosen by sector and
size and may now silently span three regulators.

- A peer set records the markets and currencies of its members, and
  exposes them. The I6 thresholds are **unchanged** — this is
  information, not a new filter.
- Its `origin` says whether it is single-market or mixed.
- A mixed set is legitimate and stays legitimate: the honest comparison
  of a tanker operator in Oslo and one in Seoul is the point of the
  product. It must simply be **visible** that it is mixed.

**Done when:** a test builds a mixed peer set and asserts the markets
and currencies are reported; a test asserts every existing single-market
peer set keeps its exact membership and version (`golden` unchanged);
`rusterm status` shows the composition.

### J3. Финансовый год не у всех кончается в декабре

**Needs:** foundation. `rusterm/core/fact.py`, one migration.

Australia's year ends 30 June. Korea and Brazil have their own filing
calendars. `period_end` is a string and the comparison logic was written
when every issuer was a US December filer.

- An issuer records its **fiscal year end**; a period is labelled by the
  fiscal year it belongs to, not by the calendar year its date falls in.
- Two issuers on different calendars compared "as of" a date resolve to
  each one's **latest period ending on or before** that date — which is
  what the existing `as_of` machinery from M7 already does for versions;
  extend it, do not rewrite it.
- Where the gap between their period ends exceeds a threshold, the
  existing `period_mismatch` reason fires. **Do not invent a new reason
  where an accurate one exists.**

**Done when:** a test compares a 30-June filer with a 31-December filer
as of one date and asserts each contributes its own latest closed
period; a test asserts US-only comparisons produce byte-identical
results to before; the migration applied twice creates no duplicates.

### J4. Данные, которых больше нигде нет

**Needs:** foundation; better after manual import landed.
`rusterm/store/`, `rusterm/cli/__init__.py`.

Everything from EDGAR can be downloaded again. **A manually imported
fact cannot** — the user gave a file to a model, paid for the call, and
checked the quote. That is the first genuinely irreplaceable data this
project has ever held, and there is no backup command in the codebase.

- `rusterm backup <path>` — one archive: database, raw store manifest,
  imported documents, watchlists. It carries a manifest with a hash per
  member and the schema version.
- `rusterm restore <path>` — refuses a schema **newer** than the running
  code, refuses a corrupted member by hash, and **never overwrites a
  non-empty data directory without an explicit flag**.
- A round trip is exact: backup, restore into an empty root, and the
  database compares equal member by member.
- `doctor` reports the age of the last backup.

**Done when:** a test round-trips a database containing a manual fact
and asserts the restored fact is identical including locator and
lineage; a test asserts restore refuses a tampered archive by hash and a
future schema by number; a test asserts restore into a non-empty root
fails without the flag.

### J5. Приёмка перестаёт зависеть от того, вспомнил ли кто-то её запустить

**Needs:** nothing. `.github/workflows/` (new).

Ten branches were just merged by hand. This is exactly the moment CI
stops being ceremony.

- One workflow on push and pull request: install, run
  `bash agent/acceptance.sh`, fail the job on a non-zero status.
- **Matrix `3.12` and `3.14`.** `requires-python` claims 3.12 and nobody
  has ever run it there — expect real failures, and fix them as part of
  this item rather than lowering the floor. If 3.12 genuinely cannot be
  supported, that is a `Disputed` line with the errors quoted, and
  `pyproject.toml` changes to tell the truth.
- A job without secrets: every network test must skip cleanly (N7). CI
  proving that is worth as much as CI proving the tests pass.
- **No secret is ever added to the repository's CI configuration.** Not
  the SEC UA, not the LLM key, not the DART key.

**Done when:** the workflow file is committed and its YAML parses
(`python3 -c "import tomllib"` is not enough — parse the YAML); the
report states, per Python version, the suite result you got **locally**
for 3.14 and what you predict for 3.12 with the reason.

### J6. Инструмент отрасли перестаёт врать пустотой

**Needs:** M7 (landed in TASK-17). `rusterm/core/tools.py`.

`list_industry_instruments` returns a hardcoded `[]` with a note saying
there is no industry source. M7 built `industry_aggregate` and a
`rusterm industry` command — the source exists now.

- The tool returns real instruments for a sector, with the peer set
  version and `as_of` it resolved against.
- It stays **read-only**: the four LLM-facing tools do not write, and
  the test asserting the database hash is unchanged after calling all
  four keeps passing.

**Done when:** a test asserts a non-empty list for a sector with
members and the documented empty answer for one without; the read-only
hash test still passes; `NO_INDUSTRY_SOURCE` is gone from the code path
or its comment explains the one case where it survives.

### J7. Третий экран: отрасль

**Needs:** J6. `rusterm/tui/model.py`, `rusterm/tui/app.py`.

M7 produced sector medians and quartiles reachable only through
`export` and a CLI command. The product is a terminal.

- A third screen: sector, n, p25/median/p75 per measure, the currency
  it is stated in (J1), and which members contributed.
- Built by pure functions in `model.py` and tested headless; `curses`
  only paints. The TUI computes nothing, writes nothing, and never
  reaches a network (ADR-0009).

**Done when:** `python3 -m pytest tests/test_tui_model.py -q` green; a
test builds the screen's rows without importing `curses`; a mixed-
currency sector renders the mismatch rather than a number.

### J8. `rusterm` — команда, а не модуль

**Needs:** nothing. `pyproject.toml`, `README.md`.

`[project.scripts] rusterm` has existed since M1 and every documented
invocation is `python3 -m rusterm.cli`. Nobody has verified the entry
point works.

- `pip install -e .` then `rusterm --help` works, and so does
  `rusterm markets`.
- Optional document-format libraries (PDF, DOCX, XLSX) become a named
  extra, e.g. `pip install -e ".[documents]"`, and their absence still
  yields `format_unsupported` as a value (ADR-0011 ①).
- README's install section is the commands you actually ran.

**Done when:** the report carries the real terminal output of
`pip install -e .` followed by `rusterm markets`; a test asserts the
console-script entry point resolves to a callable.

### J9. Что на `main` — **переписан 11.09.2026, прежняя предпосылка мертва**

**Needs:** nothing. Report only — **do not merge and do not push to
`main`.**

This item used to say «`origin/main` contains no `rusterm/` at all» and
asked you to gather evidence for a release decision. **That release
happened on 11.09.2026**: the user merged the agent branches into
`main`, which now carries the whole application — `rusterm/`, `tests/`,
`docs/`, `agent/`. Gathering evidence for a decision already taken would
waste the night, so the item is now about the consequence instead.

Releasing into `main` remains the coordinator's decision and the user's
call, not yours. **ADR-0017 devolved the merging of lane branches to the
executor — it did not devolve the release into `main`.**

Two acceptance checks read `origin/main` and their baseline just moved:

- **check 12** compares `agent/acceptance.sh` to `origin/main` byte for
  byte — it was equal at the moment of the merge, and this item confirms
  it still is;
- **check 10** allows `docs/` to differ from `origin/main` only by
  **added** ADRs — before the merge every ADR read as new, now none do.

Report, with command output:

- `git diff --stat origin/main...HEAD` — what your branch adds on top of
  the released `main`;
- `git diff origin/main -- agent/acceptance.sh` — must be empty; if it
  is not, **stop and write it in `Blocked`**: check 12 is the mechanism
  that keeps the executor from editing its own acceptance;
- `git diff --name-status origin/main HEAD -- docs/` — every line must
  be `A docs/adr/…`; anything else is the same kind of finding;
- what a user who clones `main` today actually gets: `pip install -e .`
  from a fresh clone of `main`, then `rusterm markets` — the real
  terminal output, since J8 made this an installable program.

**Done when:** all four are in the report with their output, the two
diffs are as described or named in `Blocked`, and **no merge or push to
`main` was attempted.**

### J10. Backlog

`agent/BACKLOG.md`, top-down, only if J1–J9 are done before 09:30.

---

## 3. Closing the shift

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      J1, J2, …
Items not done:  … and why
Acceptance:      the "Итог" line and the captured exit status
Tests:           N passed, N skipped, N xfailed
Schema:          _SCHEMA_VERSION <old> -> <new>, migrations <numbers>
Golden:          golden_m2.json and golden_m6_ca.json — unchanged? assert output
Currency:        which markets, which currencies, mismatches counted
Fiscal:          which fiscal year ends are represented
Backup:          round-trip result, archive size, refusal cases proven
CI:              workflow committed? 3.12 result or prediction with reason
Install:         pip install -e . output, rusterm markets output
main:            diff size, files overwritten, acceptance.sh match
Network:         requests used
Model:           app llm_calls N; your own model id
Pushed:          yes/no
Questions for the coordinator:
1. …
```

Then set `agent/STATE.json` to `"status": "awaiting_review"` and push.
