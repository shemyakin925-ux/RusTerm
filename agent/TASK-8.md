# TASK-8 — the program becomes something the user can install, launch and use

- **Status: READY** — this is the task. Start here.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-8.md`
- **Supersedes:** TASK-7 (accepted, 15/20 items). Do not reopen it; the
  five items it could not run are re-issued below as U5–U8.
- **Goal of the night, in one sentence:** after this night the user runs
  `pip install -e .`, then `rusterm`, and works with real companies of
  their own choosing — not with `US-CLI-DEMO`.

You are an autonomous coding agent with the same tools as the
coordinator: shell, file editing, test runs, network. This file gives
contracts, decisions and acceptance commands, not tutorials. Anything
readable from the repository, read from the repository.

No coordinator is online during the run. Every fork below is closed by a
deterministic rule. Where a rule is wrong, follow it and put the
objection in **Disputed** — that channel works: seven of seven disputes
have been upheld or answered so far.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git merge origin/main          # brings TASK-8, LAUNCH, BACKLOG, docs fix
bash agent/acceptance.sh
```

The last command must print `Итог: пройдено 13, провалено 0`. The
coordinator ran exactly this on a clean checkout of
`origin/agent/night-2` at `81c7068` and got 13/13 with
`208 tests: 206 passed, 2 skipped`. Anything else means your environment
differs — record the full output as the first entry in
`agent/REPORT-8.md` and continue. Do not "fix" acceptance.

**The merge is not optional and comes first.** `origin/main` carries an
amendment to `docs/governance-thresholds.md` §3–§4 (the ruling in §0.2).
Run acceptance *before* merging and check 10 goes red — it compares
`docs/` against `origin/main` and sees the branch lagging. That is the
expected state of an unmerged branch, not a defect and not something to
work around: merge, then run acceptance, then start U0.

The merge may conflict in `agent/LAUNCH.md` — the coordinator's file,
never yours. Take main's version verbatim:

```bash
git checkout --theirs agent/LAUNCH.md && git add agent/ && git commit --no-edit
```

Then read, in full and from the repository, the files you will touch:
`rusterm/cli/__init__.py`, `rusterm/core/llm.py`, `rusterm/core/snapshot.py`,
`rusterm/providers/__init__.py`, `rusterm/providers/budget.py`,
`rusterm/pipeline.py`, `docs/ui-architecture.md`, `docs/processes.md`.
The recurring failure in this repo is editing a file from a remembered
shape instead of its current one.

---

## 0.1. Where the project stands — verified, not reported

The coordinator re-ran acceptance on a clean checkout. These are facts,
not claims from a report:

| Layer | State |
|---|---|
| store, 34 migrations (33 + 35; **34 never exists**), WAL, writer lock | done |
| repositories — the only SQL layer | done |
| facts, locators, basis rule, parsers (XBRL + table) | done |
| synthetic providers, ingestion pipeline, idempotency | done |
| formulas, peer set, snapshot, export | done |
| coverage (8 blocks / 5 statuses), verification + ground truth | done |
| watchlist: versions, rollback, import/export | done |
| nine system metrics, three log destinations, audit JSONL | done |
| request budget + rate limiter (`RequestGate`) | done, **not wired** |
| LLM guard rail | done, **porous — U0** |
| governance traffic light `governance.v1`, migration 35 | done |
| Maritime/Tanker: 25 metrics on the shared `Measure` | done |
| CLI `init ingest snapshot export verify doctor watchlist coverage metrics budget` | done, **demo-only — U3** |
| tests | 208: 206 passed, 2 skipped, 0 xfail |

Milestones: M1 done. **M2, M3, M5 not started** — the night of 07/08.09
ran with `RUSTERM_SEC_UA` unset, so T4–T6, T9, T16 were skipped by rule.
That was correct behaviour and not held against the run; U4 below makes
the same loss impossible to repeat.

Everything built so far has been verified **on synthetic data only**.
That is still the largest open risk in the project.

---

## 0.2. Rulings on TASK-7 disputes. All seven answered

1. **insider_net gap −0,5%…−0,1%.** You were right, the table had a
   hole. `docs/governance-thresholds.md` §4 is amended by the
   coordinator: yellow is everything that is neither green nor red.
   Your implementation already matches — no code change, but see U12 for
   the reason string.
2. **related_party, `approved=None` does not force red.** Upheld, and
   the document now says so explicitly.
3. **Fixed-interval limiter as "≤5/s".** Accepted; the boundary slack is
   immaterial against SEC's documented 10/s. No change.
4. **ADR numbering: 0006 was taken, you wrote 0008.** You were right,
   the task text was wrong. `0008` stands.
5. **Whole-tree preload deviated to per-file full reads.** Accepted;
   the method rule (read before edit) is what matters.
6. **CLI `verify` interface change.** Sanctioned — it was the task's own
   contract.
7. **Schema pins 33→35 in six test spots.** Accepted: the pins were
   moved, no assertion was weakened, and the table list was extended.

Also recorded, not penalised: commit `f9b5a3a` contained a red test,
fixed in `27dd6fa`, and you reported it yourself. Self-reporting a
method violation is worth more than the violation costs.

---

## 1. Working protocol. This outranks the task list

Five autonomous runs on this repo failed on method rather than
difficulty, and the losses were mechanical: work left uncommitted, work
committed but never pushed, a file edited from memory, an assertion
deleted to make a change fit, an already-applied migration edited in
place. The rules below are one counter-measure per failure.

### 1.1. The cycle. One item = one pass

```
1. READ     the file you are about to change, in full. Not from memory.
2. SHOW     current state with a command, and look at the output.
3. CHANGE   exactly one item. Not two.
4. VERIFY   with the command from that item's "Done when".
5. SELFCHECK  the four commands in §1.3. All must be clean.
6. COMMIT   immediately, before moving to the next item.
7. PUSH     immediately (§1.8).
8. RECORD   one line in agent/REPORT-8.md: command + its output.
```

Steps 6 and 7 do not get deferred. One item, one commit, one push bounds
any loss to the item in flight.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong. A genuinely obsolete assertion is **replaced
by a stronger one**, and the report says how the new one is stricter.

**P2. Never edit an existing migration.** Schema change = **new**
migration, new number, `_SCHEMA_VERSION` bumped. Next free number is
**36** (34 does not exist and never will).

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`. Except fetched data — §1.12 is the opposite rule and
takes precedence for it.

**P4. No `.bak`, `.orig`, temp databases, junk.**

**P5. Never claim a check you did not run.** "Not run" is acceptable.
"Works" without command output is not. Everything here gets rerun on a
clean checkout — last cycle every claimed command was re-executed.

### 1.3. Selfcheck. Four commands before every commit

```bash
git diff --cached | grep '^-.*assert'                # P1: must be empty
git diff --cached rusterm/store/db.py | grep '^-'    # P2: empty except _SCHEMA_VERSION
git status --porcelain | grep '^??'                  # P3, P4: must be empty
bash agent/acceptance.sh                             # must stay 13/13
```

Below 13 means you broke something. Stop, roll back (§1.5), re-enter.
Never proceed with a red script.

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

### 1.7. Bookkeeping — two files, same commit as the work

- `agent/REPORT-8.md`, written as you go. Sections: **Done** (one line
  per item: command + output), **Blocked**, **What not to trust**,
  **Disputed**. Last line always `NOW: <item>, step <n>`.
- `agent/STATE.json`:
  ```json
  {"task": "agent/TASK-8.md", "report": "agent/REPORT-8.md",
   "item": "U3", "step": "4", "status": "working",
   "last_commit": "<sha>", "requests": 0, "net_requests": 0,
   "llm_calls": 0, "model": "<your model id>",
   "updated_at": "<ISO8601 UTC>"}
  ```

### 1.8. Push, every time

```bash
git push origin agent/night-2
```

Push fails for lack of rights — do not retry in a loop. Write
`PUSH UNAVAILABLE` as the **first line** of `agent/REPORT-8.md`, keep
committing locally, and at the end produce
`git bundle create handoff.bundle --all`. Say so in `## HANDOFF`.

### 1.9. Stop time

**10:00 Danang (UTC+7).** Finish the current item to a commit and a
push, then do §3. Do not start a new item after 09:30.

### 1.10. Precedence when sources disagree

This file → `docs/` → existing code → your judgement. A conflict between
the first two is a coordination bug: implement per this file and record
both quotes in **Disputed**.

Existing green code is authoritative over your preferences. It is
extended, never refactored or "improved". The only exceptions are the
items below that name a file and say what is wrong with it (U0–U3, U12).

### 1.11. What you may assume

- `python3` is 3.14.6 here; the code must also run on 3.12. `pytest` is
  installed. `zstandard` is **not**, and acceptance check 11 reruns the
  suite with it blocked — the gzip fallback is load-bearing.
- Acceptance is 13/13 at your start and is ground truth about your work.
- You have network. See §1.12 before using it.

### 1.12. Network rules. Read before the first request

**N1. One source: SEC EDGAR.** Public, documented, free, no auth. No
price vendor, no scraper, no mirror, no aggregator. Prices stay
synthetic — the vendor decision is `docs/adr/0008-...`, proposed and
awaiting the user.

**N2. Identify yourself or do not go.** `RUSTERM_SEC_UA` must carry a
real contact. Unset or empty → every network operation returns a
`ConfigError` **value** (never an exception), the item degrades to the
synthetic path, and the report records
`SEC_UA UNSET — network path not exercised`. **Never hardcode a contact,
never commit one, never invent one.** U4 makes the variable reachable
without a shell export; run U4 before U5 and re-check with
`rusterm doctor` rather than assuming the shell is empty.

**N3. Rate and ceiling, enforced in code.**

| Limit | Value | Behaviour at the limit |
|---|---|---|
| requests per second | 5 | limiter delays |
| requests per night, total | 5000 | provider **refuses** with a value |
| retries per failed URL | 2, then give up | E1/E2, recorded |

Count every request in `STATE.json` `"net_requests"`.

**N4. 403 or 429 is a stop, not a puzzle.** Back off, record E1/E2, move
on. Do not change the User-Agent, do not switch IP, do not use a proxy,
a mirror or a cache. Violating this can get the user's address blocked
from a primary source with no substitute.

**N5. Fetched data never enters git.** Raw store lives in the app data
directory, outside the repository; tests use `tempfile`.

**N6. `fixtures/` stays synthetic-only.** Real data goes to the app data
directory or to a golden file of *expected values* (U7) — never into
`fixtures/`.

**N7. Nodes 1, 3, 6, 7, 8, 9 of process 1 stay offline** and stay
testable offline on stored raw objects. Network lives only in nodes 2
and 4. A network test skips cleanly when `RUSTERM_SEC_UA` is unset; it
never fails for that reason.

### 1.13. Money and quota

**Your own model.** Free tier only. If the chain switches you to a paid
model, record it in `STATE.json` and as its own report line. Count your
calls in `"requests"`; at 800, finish the current item to a commit and
close the night with §3.

**The application's model calls.** Key from `RUSTERM_LLM_PROVIDER` /
`RUSTERM_LLM_API_KEY`. Unset → the fake client, and the report records
`LLM key unset — real path not exercised`. With a key: a hard ceiling of
**50 calls for the whole night**, counted in `"llm_calls"`. No key ever
appears in a commit, a log, a report or a test. As of this writing the
user's env file defines `RUSTERM_SEC_UA` only, so expect the fake client
and do not treat that as a failure.

**Network requests** — §1.12 N3.

---

## 2. The work, in priority order

Strictly in order. Do not start an item before the previous one is
committed and pushed.

Ordering rationale, so you can judge a trade-off the same way: U0–U2 are
defects that silently corrupt what the user would see, so they come
first. U3–U4 are what makes the program operable at all. U9–U10 are the
smallest work that turns "operable" into "installable and documented" —
they are deliberately placed before the network block, so that a night
that ends early still leaves the user a program they can run. U5–U8 are
real data. U11 is the interface. U12 is cleanup.

---

### U0. The LLM guard rail lets invented numbers through — fix the match

`rusterm/core/llm.py`, `_citations_for`. A number counts as cited if it
is a **substring** of any measure value *or of a period string*. With
one measure `revenue=1000`, period `2024-01-01…2024-12-31`, the
coordinator ran the shipped code and got:

| model text | current verdict |
|---|---|
| `маржа выросла на 31%` | **accepted** (`31` inside `12-31`) |
| `заработала 12 млрд` | **accepted** (`12` inside `12-31`) |
| `рост в 2 раза` | **accepted** (`2` inside `2024`) |

This is the exact failure the item exists to prevent, and it is worse
than no guard rail because the block reports `ready`.

Replace substring matching with **multiset containment over whole
numeric tokens**:

1. `_render` returns, alongside the text, `substituted: list[str]` — the
   exact strings the renderer inserted (measure values, and periods only
   where a period placeholder was substituted).
2. `allowed` = the multiset of numeric tokens (`_NUMBER_RE`) found in the
   concatenation of `substituted`.
3. `found` = the multiset of numeric tokens in the final text
   (summary + highlights + risks together).
4. Accept **iff** `found` is contained in `allowed` counting
   multiplicity. Otherwise reject the whole text, exactly as now.

Normalisation, fixed here so two runs agree: strip thousands separators
(space, ` `, `,` between digit groups of three), treat `,` and `.`
as the same decimal separator, compare as strings after normalisation.
No rounding, no numeric tolerance.

**Done when** `tests/test_llm_guard.py` has a test that, with the single
measure above, asserts each of the three texts in the table is rejected
in full (`stored is False`, `llm_summary` empty, coverage `missing` with
the guard reason); asserts a text repeating a substituted token once
more than it was substituted is rejected (multiset, not set); asserts
the fully-cited text is still stored; and `python3 -m pytest -q` exits 0.

---

### U1. Coverage is optional by convention — make it structural

`SnapshotBuilder.__init__(..., coverage_repo=None)`. A call site that
forgets the argument silently writes no coverage, while
`docs/watchlist-and-llm.md` §1.3 and TASK-7 T7 require all eight blocks
on **every** build. `VerificationService.recompute` builds through such
a call site today.

Make `coverage_repo` a required argument, update every call site
(`rusterm/cli/__init__.py`, tests), and let the omission fail loudly.

**Done when** a test asserts `SnapshotBuilder(snapshot_repo, peer_repo)`
raises `TypeError`; `grep -rn 'SnapshotBuilder(' rusterm/ tests/` shows
no call site without a coverage repo; `python3 -m pytest -q` exits 0 and
acceptance stays 13/13.

---

### U2. `rusterm verify` stores ground truth but never recomputes

`cmd_verify` calls `store_ground_truth` and stops. The corrected fact
never reaches derived measures, so the user fixes a number and the
screen keeps showing the old one.

Call `recompute` after a successful correction, print which instruments
and snapshot versions were rebuilt, and audit-log the rebuild.

**Done when** a test in `tests/test_cli.py` runs
`init → ingest → snapshot → verify` on a fact that feeds a derived
measure and asserts the measure's value in the **new** snapshot version
differs from the old one, and that the command printed the rebuilt
version; `python3 -m pytest -q` exits 0.

---

### U3. Kill `US-CLI-DEMO` — the program must work on the user's companies

`rusterm/cli/__init__.py` hard-wires `DEMO_ISSUER` / `DEMO_INSTRUMENT`
into `ingest`, `snapshot` and `export`. Whatever the user adds to a
watchlist, the pipeline still processes one synthetic company. This is
the single largest reason the program cannot be used.

| Command | New contract |
|---|---|
| `rusterm ingest [--instrument ID \| --ticker T --market M \| --watchlist ID] [--source synthetic\|edgar]` | one of the three selectors; `--watchlist` iterates current members |
| `rusterm snapshot [--instrument ID \| --watchlist ID] [--as-of DATE]` | same selectors; per-instrument result line |
| `rusterm export --instrument ID [--format csv\|json] [--out PATH]` | instrument is required, no default |
| `rusterm demo` | **new**: creates the synthetic issuer + instrument that `init` used to create implicitly, and says so |

`rusterm demo` must also produce a **useful** demo. The coordinator ran
the shipped path on a clean install:

```
$ rusterm ingest    → заданий закрыто: 2; фактов: 4
$ rusterm snapshot  → снапшот v1; мер: 3
$ rusterm coverage US-CLI-DEMO → fundamentals missing причина: no_as_reported_facts
```

Three measures were written and every one of them is null, so the first
thing a new user sees is a snapshot that reports "мер: 3" next to a
coverage row saying there are no fundamentals. Both statements are
technically true and together they read as broken. Fix both halves: the
demo issuer gets facts from which at least one base measure computes to
a real value, and the snapshot line reports value-carrying and null
measures separately (`мер: 3 — со значением 2, пусто 1`).

Rules: no selector and no default instrument → exit 1 with a message
naming the three ways to choose one; a ticker that does not resolve →
exit 1 quoting `resolve_ticker_candidates` (never a silent pick of the
first candidate); `init` no longer creates demo data — `demo` does.
Ticker resolution reuses `InstrumentRepo.resolve_ticker_candidates` from
TASK-7 T11; no second resolver.

**Done when** a test asserts `demo → ingest → snapshot` yields at least
one measure with a non-null value and that the printed line separates
value-carrying from null measures; a test drives **two different
instruments** through one database in one test — ingest, snapshot, export each, by
`--instrument` — and asserts two distinct snapshot ids and two distinct
export files; a test asserts `ingest` with no selector exits 1 with the
message; a test asserts `--watchlist` ingests every current member;
`grep -rn 'US-CLI-DEMO' rusterm/` returns only `cmd_demo`;
`python3 -m pytest -q` exits 0.

---

### U4. The program reads its own env file — the night's biggest loss, prevented

Last night `RUSTERM_SEC_UA` was unset in the agent's shell although
`~/.rusterm.env` existed and defined it. Five items and three milestones
were lost to a missing `source`. The application must not depend on how
its shell was started.

`rusterm/store/config.py` (or a new `rusterm/env.py`, your call, one
module):

- On startup, for each of `RUSTERM_SEC_UA`, `RUSTERM_LLM_PROVIDER`,
  `RUSTERM_LLM_API_KEY`: if the variable is **already** set in the
  environment, it wins and the file is not consulted for it.
- Otherwise read `$RUSTERM_ENV_FILE` if set, else `~/.rusterm.env`, if it
  exists and is a regular file. Parse `export NAME=value` and
  `NAME=value`, strip matching single or double quotes, ignore blank
  lines and `#` comments, ignore any name outside the three above.
- A file whose mode is group- or world-readable is used, but `doctor`
  reports it as a problem (it holds a contact and may hold a key).
- Nothing is ever printed, logged or audited from a value.

`rusterm doctor` gains a section listing, for each of the three
variables: `задана` / `не задана`, and **where** it came from
(`окружение` / `~/.rusterm.env` / `—`). **Names and origins only, never
values, never a prefix of a value.**

**Done when** a test with `RUSTERM_ENV_FILE` pointing at a temp file
asserts the value is picked up with the variable absent from
`os.environ`; a test asserts an already-set environment variable wins
over the file; a test asserts `doctor`'s output contains the variable
name and the origin and **does not contain** the value; a test asserts a
missing file is not an error; `python3 -m pytest -q` exits 0.

---

### U9. One coherent command-line program, not a set of scripts

The user's first five minutes decide whether this is usable.

- `rusterm` with no arguments prints the short usage: what the program
  is, the four commands of the normal path (`init`, `watchlist add`,
  `ingest`, `snapshot`), and where its data lives. Exit 0.
- `rusterm status` — **new**: data directory, schema version, number of
  watchlists and instruments, last snapshot per instrument (id, version,
  `as_of`), coverage summary (`N ready / M missing / K error`), network
  budget state, and the U4 environment section. This is the "what do I
  have" screen.
- Every error the user can cause exits 1 with a Russian sentence naming
  the cause and the next command to run. No traceback reaches the
  terminal for an expected error; an unexpected exception prints the
  path of `logs/app.log` and exits 2.
- Exit codes, fixed: 0 success; 1 the user's situation (missing
  selector, unresolved ticker, nothing to export, network refused);
  2 internal error.
- `--json` on `status`, `coverage`, `metrics`, `budget` prints a single
  JSON object and nothing else, so the output is scriptable.
- No user-facing count may conflate "written" with "known". Wherever a
  count of measures, facts or blocks is printed, a null value is
  reported separately from a value — the demo run above is the pattern
  to avoid.

**Done when** `tests/test_cli.py` asserts: bare `rusterm` exits 0 and
names the data directory; `status` on a fresh database exits 0 and
reports zero instruments without inventing numbers; `status` after
`demo → ingest → snapshot` reports one instrument, a snapshot version
and a coverage summary; an unresolved ticker exits 1 with a message and
no traceback; `--json` output parses with `json.loads` for all four
commands; `python3 -m pytest -q` exits 0.

---

### U10. Installable in one command, and the README says how

`pyproject.toml` already declares `rusterm = "rusterm.cli:main"`. Prove
it works and document the path from clone to first snapshot.

- Rewrite the **Быстрый старт** section of `README.md` (root, not
  `docs/` — acceptance check 10 does not cover it): install, first run,
  where data lives, the four-command normal path, what needs
  `~/.rusterm.env` and what works without it, how to get real data, how
  to read a `missing` block. Russian, ten commands at most, every one
  copy-pasteable and actually run by you before it goes in.
- A test that runs the console entry point **as a subprocess**
  (`sys.executable -m rusterm.cli` and, if the wheel is installed,
  `rusterm`) and asserts exit 0 and the usage text.
- `python3 -m pip install -e .` must succeed on 3.12 and 3.14 with an
  empty `dependencies` list; if you add a dependency, say why in the
  report — it must stay inside `rusterm/providers/`.

**Done when** the README section exists, every command in it was run by
you and its real output is quoted in the report, the subprocess test is
green, and `python3 -m pytest -q` exits 0.

---

### U5. SEC EDGAR provider — probe first, then build (re-issued T4)

Skip **entirely** if `RUSTERM_SEC_UA` is unset after U4 — record
`SEC_UA UNSET — network path not exercised` and go to U9's successor,
U11. Do not simulate it.

Probe before writing code:

```bash
curl -s -H "User-Agent: $RUSTERM_SEC_UA" https://www.sec.gov/files/company_tickers.json | head -c 400
curl -s -H "User-Agent: $RUSTERM_SEC_UA" https://data.sec.gov/submissions/CIK0000320193.json | head -c 800
curl -s -H "User-Agent: $RUSTERM_SEC_UA" https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | head -c 800
```

`rusterm/providers/edgar.py`: ticker→CIK index, `submissions`,
`companyfacts`. Every request through `RequestGate` — and this time
**the registry enforces it**: `get_provider(name)` for a provider
declaring `needs_network = True` returns a `ConfigError` value unless it
is constructed with a gate. The convention "edgar.py must be built
through RequestGate" is not enforcement; TASK-7 T3 asked for the
registry to make bypass impossible and that part is not done.

Raw responses go to the content-addressed raw store (N5), never to git.
`If-Modified-Since` / ETag where the endpoint offers it; a 304 is not a
new raw object.

**Done when** `tests/test_edgar.py` is green with the whole suite
offline (fixtures are recorded responses **stored under the app data
dir or as saved test payloads that carry `synthetic` only if they are
synthetic** — a recorded real response goes to `tests/data/edgar/`, is
listed in git, and is small: one issuer, trimmed); a test asserts a
network provider obtained from the registry without a gate returns
`ConfigError`; a live test skips cleanly with no `RUSTERM_SEC_UA`;
`net_requests` in `STATE.json` reflects the real count.

---

### U6. Real XBRL parser over `companyfacts` (re-issued T5)

The existing XBRL parser was written against synthetic shapes. Extend it
to the real `companyfacts` structure: `facts.us-gaap.<concept>.units.<unit>[]`
with `start`, `end`, `fy`, `fp`, `form`, `filed`, `accn`, `frame`.

- The basis rule (I3) decides `as_reported` vs `restated` from `end` and
  `filed` — the rule already exists, do not write a second one.
- One fact per `(concept, unit, start, end, accn)`; duplicates across
  frames collapse deterministically, newest `filed` wins, and the loser
  is kept with `superseded_by`.
- Locator points at the `accn` and the concept path, so `resolve` can
  bring the number back.

**Done when** `tests/test_edgar_parser.py` is green over a saved real
`companyfacts` payload for one issuer: every produced fact resolves via
`resolve(locator)`, the basis distribution is asserted, and a duplicate
across two frames yields one live fact plus one superseded;
`python3 -m pytest -q` exits 0.

---

### U7. **M2** — five issuers, five years, against a golden file (re-issued T6)

Five US issuers, five completed fiscal years, from `companyfacts`, with
a golden file of **expected values** written by you from the filings and
committed (`tests/data/golden_m2.json`, real values, not fixtures).

**Done when** `python3 -m pytest tests/test_m2_golden.py -q` is green,
every number in it resolves to an XBRL fact through `resolve(locator)`,
and the report carries the line
`M2: 5 issuers × 5 years, N facts, K требуют проверки, R requests`.
With no `RUSTERM_SEC_UA`: skip, record, move on.

---

### U8. **M3** — twenty issuers, one pass, gaps with reasons (re-issued T9)

Extend U7's five to twenty. One `ingest` pass, then one `snapshot` pass
per issuer. Missing blocks show with a reason (U1 guarantees they
exist). Repeat the pass: no new raw objects, no new facts, no new jobs.

**Done when** `python3 -m pytest tests/test_m3_snapshot.py -q` is green
and the report carries `M3: 20 issuers, one pass, N requests, M blocks
missing with reasons, repeat pass created 0 new objects/facts/jobs`.
Also record the measured request count against the estimate in
`docs/processes.md`; a difference over 2× goes to **Disputed**.

---

### U11. The terminal interface — the program you can sit in front of

`docs/ui-architecture.md` describes a PySide6 desktop, and ADR-0004
chose it, but acceptance check 6 forbids Qt anywhere in the tree and
that check is not negotiable. The resolution is decided here, not by
you: **build the terminal interface now, keep the desktop as the stated
goal.** Record the decision as `docs/adr/0009-terminalnyy-interfeys.md`
(a new ADR, which check 10 permits): why a TUI first, what it does not
do, and that ADR-0004 stays the target for the desktop build.

`rusterm/tui/` on `curses` (stdlib; no `textual`, no `rich`, no
dependency). Two screens from `docs/ui-architecture.md` §2, under §1
rules 1, 3, 4, 5:

| Screen | Content |
|---|---|
| Список | watchlist rows: ticker, instrument, last snapshot `as_of`, coverage as `8` cells (ready/stale/processing/missing/error), peer-set mark when unconfirmed. Keys: ↑↓ move, `Enter` open, `r` refresh from the database, `q` quit |
| Карточка | one instrument: measures with units and periods, `—` plus the null-reason where a value is null, coverage block list with reasons, governance five colours (never summed), `s` source panel for the highlighted number (lineage: document, locator, `method_version`), `Esc` back |

Hard rules: the TUI **computes nothing** — it reads snapshots, measures
and coverage through the repositories; no formula, no SQL, no network in
`rusterm/tui/`. A `missing` block is displayed with its reason, never
hidden. Long operations are not started from the TUI in this item — it
is read-only; `r` re-reads the database.

Testability, which is the reason for the split: all screen content is
produced by pure functions in `rusterm/tui/model.py` returning lists of
rows/strings from repository data; `curses` only paints them. Tests
exercise `model.py` headless and never open a terminal.

**Done when** `tests/test_tui_model.py` asserts: the list screen shows
one row per current watchlist member with eight coverage cells; a
`missing` block renders with its reason; a null measure renders as `—`
plus its null-reason; the source panel for a measure returns the
document, the locator and `method_version`; an unconfirmed peer set is
marked. `rusterm tui` starts and quits on `q` (manual, quoted in the
report); `grep -rnE 'execute\(|httpx|requests' rusterm/tui/` is empty;
`python3 -m pytest -q` exits 0 and acceptance stays 13/13.

---

### U12. Findings from the TASK-7 review, batched

Small, independent, each its own commit:

1. **Maritime names drift from the document.** Eight metrics registered
   as `..._pct` where `docs/industry-metrics/maritime-tanker.md` writes
   `..._%`, and `fleet_age_profile` (a histogram in the doc) is
   registered as `average_fleet_age` while the implemented
   `fleet_age_histogram` is in no registry. Dispatcher keys are strings:
   register the **document's names verbatim** (Python function names may
   keep `_pct`), register `fleet_age_profile` → `fleet_age_histogram`,
   keep `average_fleet_age` as an extra. Then add the B7-style guard: a
   test parsing the metric names out of the doc's "Специфичные метрики"
   section and asserting the set equals `known_measures()` both ways.
2. **`insider_net` reason lies in the yellow band.** It reports
   `within_pm_0.1pct` for −0,3%. Emit the actual band; the amended §4 of
   the document is the source of wording.
3. **`flag_parser` does not exist** under that name (`degraded_parsers`
   does), and nothing tests the rolling window. Add a test asserting a
   mismatch older than 30 days does not count toward the threshold of 5.
4. **`industry` in the watchlist export is always empty.** Either fill
   it from a real source or make the emptiness explicit in the export
   report; do not leave a column that silently means nothing.

**Done when** each has its own commit, `python3 -m pytest -q` exits 0
after each, and acceptance stays 13/13.

---

### U13. Queue empty

All of U0–U12 done before 09:30 — take `agent/BACKLOG.md` top down. Do
not invent work beyond it.

---

## 3. Night end — you run the final acceptance yourself

```bash
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-6.txt
git add agent/ACCEPTANCE-6.txt agent/REPORT-8.md agent/STATE.json
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

Then set `"status": "awaiting_review"` in `STATE.json` and write the
`## HANDOFF` section below. A night whose acceptance log is missing is
reviewed as if it printed zero.

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      U0, U1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-6.txt)
Tests:           N passed, M skipped, K xfailed
Milestones:      M2 yes/no, M3 yes/no, M5 yes/no
Network:         RUSTERM_SEC_UA set? — N requests, M refused, K rate-limited
Model:           app LLM calls N; your own model id and call count
Installable:     output of `python3 -m pip install -e .` and of `rusterm`
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

In scope now, new since TASK-7: the terminal interface, installability,
and a program that works on instruments the user chooses.

Out of scope tonight, no exceptions for spare time:

- Qt or any GUI — acceptance check 6 forbids it and U11 replaces it
- price vendors (ADR-0008 proposes; the user decides)
- UK and CA providers (M6), Industry View (M7)
- industry metrics beyond Maritime/Tanker
- writes from the TUI, bulk operations without confirmation
- refactoring green code that no item names

Widening the scope is a failure of this task, not a bonus.

## 5. Stack

Python 3.12+, must also run on 3.14. Standard library; `pytest`;
`sqlite3` and `curses` from stdlib; `zstandard` optional with `gzip`
fallback; `httpx`/`requests` only inside `rusterm/providers/`, and
`urllib.request` from stdlib is preferred. Forbidden: ORM, `alembic`,
`pandas`, `numpy`, async frameworks, `rich`, `textual`.

`list`, `dict`, `tuple`, `set` are builtins — write `list[str]`, with
`from __future__ import annotations` at the top of the module.

## 6. Acceptance script

`bash agent/acceptance.sh` — thirteen machine checks, **13/13 when you
start**. Run after every commit; never let it drop below 13.

**Editing that file is forbidden.** Check 12 compares it byte for byte
against `origin/main`, and an edit voids the whole night regardless of
what else you did. Think a check is wrong — write it in **Disputed**.
That channel has a perfect record: every dispute raised so far was
answered, and five of seven were upheld against the coordinator.
