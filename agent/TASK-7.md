# TASK-7 — the rest of the project, in priority order

- **Status: ACCEPTED** (08.09.2026, 13/13 on a clean checkout of
  `origin/agent/night-2` @ `81c7068`). Closed — see `agent/TASK-8.md`.
- **Branch:** `agent/night-2`
- **Report:** `agent/REPORT-7.md`
- **Supersedes:** TASK-5, TASK-6 (merged in). Do not open them.
- **Scope change from every previous task:** the network ban and the
  LLM ban are **lifted**. Real sources and a real model are now in
  scope, under the rules in §1.12 and §1.13. Those rules are hard.

You are an autonomous coding agent with the same tools as the
coordinator: shell, file editing, test runs, network. This file is
written on that assumption — it gives contracts, decisions and
acceptance commands, not tutorials. Anything readable from the
repository, read from the repository.

No coordinator is online during the run. Every fork below is closed by a
deterministic rule, so nothing here needs an answer from anyone. Where a
rule is wrong, follow it and put the objection in **Disputed** — that
channel works: two of two disputes were upheld last cycle.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git merge origin/main
# Exactly one conflict, agent/LAUNCH.md — the coordinator's file, never
# yours. Take main's version verbatim:
git checkout --theirs agent/LAUNCH.md && git add agent/ && git commit --no-edit
bash agent/acceptance.sh
```

The last command must print `Итог: пройдено 13, провалено 0`. The
coordinator ran exactly this sequence before handing you the task and
got 13/13. Anything else means your environment differs — record the
full output as the first entry in `agent/REPORT-7.md` and continue. Do
not "fix" acceptance.

Then load the repository in one pass: `docs/`, `rusterm/`, `tests/`.
~3.8k lines of code, ~3k of tests — cheaper to hold in context than to
re-derive. The recurring failure in this repo's history is editing a
file from a remembered shape instead of its current one; with the tree
in context that failure mode is gone.

The specs in `docs/` are authoritative. This task does not restate them —
it names the section and fixes what a spec deliberately leaves open
(exact enums, thresholds, tie-breakers), so two runs of this task
produce the same design.

---

## 0.1. Where the project stands

Accepted, green, **not to be rewritten**:

| Layer | State |
|---|---|
| paths, config, content-addressed raw store, 33 migrations, WAL, writer lock | done |
| repositories — the only SQL layer | done |
| Fact, 6 locator kinds, basis rule, `resolve(locator)` | done |
| synthetic providers (`typing.Protocol`), XBRL + table parsers | done |
| ingestion pipeline: 9 nodes, E1–E5, idempotency, staleness cascade | done |
| formulas: TTM, Valuation, Growth, Quotes, null-reasons | done |
| peer set: versions, origin, verified/unverified, thresholds 5/8, drift | done |
| snapshot (two passes, three diffs), export CSV/JSON without recompute | done |
| CLI: `init ingest snapshot export verify doctor` | done |
| tests | 147 passed, 1 skipped, 0 xfail |

Milestone status against `docs/quality-and-observability.md` §5:

| Milestone | State |
|---|---|
| M1 skeleton — repeat ingest creates no duplicates | **done** |
| M2 US facts — 5 issuers, 5 years, matches golden file, every number resolves to an XBRL fact | **not started — needs the network** |
| M3 snapshot — 20 issuers in one pass, gaps shown with reason | not started |
| M4 watchlist — 500 instruments incremental, rollback by date | not started |
| M5 LLM — every numeric statement carries a citation; no bulk op without confirmation | not started |

Everything built so far has been verified **only on synthetic data**.
That is the single largest open risk in the project, and closing it is
what the ordering below optimises for: defects first (they corrupt real
data silently), then the network path to M2, then everything else.

---

## 1. Working protocol. This outranks the task list

Four autonomous runs on this repo failed on method rather than
difficulty, and the losses were mechanical: work left uncommitted, work
committed but never pushed, a file edited from memory, an assertion
deleted to make a change fit, an already-applied migration edited in
place. The rules below are one counter-measure per failure — the parts
of the loop that no amount of reasoning recovers once skipped.

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
Batching commits to the end is the highest-variance thing you can do
here; one item, one commit, one push bounds any loss to the item in
flight.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong, not that the test is junk. A genuinely
obsolete assertion is **replaced by a stronger one**, and the report
says how the new one is stricter.

**P2. Never edit an existing migration.** `_MIGRATIONS` in
`rusterm/store/db.py` is history already applied to other databases. An
edit after the fact never arrives: `apply_migrations` skips versions
already in `schema_version`. Schema change = **new** migration, new
number, `_SCHEMA_VERSION` bumped.

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`. Except fetched data — see §1.12, which is the opposite
rule and takes precedence for it.

**P4. No `.bak`, `.orig`, temp databases, junk.**

**P5. Never claim a check you did not run.** "Not run" is acceptable.
"Works" without command output is not. Everything here gets rerun.

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

An honest blocked item beats a closed item that lies.

### 1.5. Stop rule

A passing test starts failing — stop immediately:

```bash
git checkout -- <file>
```

A regression means an assumption upstream of the edit is wrong. Fixing
forward compounds it instead of surfacing it.

### 1.6. Commit format

Russian, imperative, one thought. First line — what was done. Body —
how it was verified, with the command's real output.

### 1.7. Bookkeeping — two files, same commit as the work

- `agent/REPORT-7.md`, written as you go. Sections: **Done** (one line
  per item: command + output), **Blocked**, **What not to trust**,
  **Disputed**. Last line always `NOW: <item>, step <n>`.
- `agent/STATE.json`:
  ```json
  {"task": "agent/TASK-7.md", "report": "agent/REPORT-7.md",
   "item": "T4", "step": "4", "status": "working",
   "last_commit": "<sha>", "requests": 0, "net_requests": 0,
   "llm_calls": 0, "model": "<your model id>",
   "updated_at": "<ISO8601 UTC>"}
  ```

### 1.8. Push, every time

```bash
git push origin agent/night-2
```

Push fails for lack of rights — do not retry in a loop. Write
`PUSH UNAVAILABLE` as the **first line** of `agent/REPORT-7.md`, keep
committing locally, and at the end produce `git bundle create
handoff.bundle --all`. Say so in `## HANDOFF`.

### 1.9. Stop time

**10:00 Danang (UTC+7).** Finish the current item to a commit and a
push, then do §3. Do not start a new item after 09:30.

### 1.10. Precedence when sources disagree

This file → `docs/` → existing code → your judgement. A conflict between
the first two is a coordination bug: implement per this file and record
both quotes in **Disputed**.

Existing green code is authoritative over your preferences. It is
extended, never refactored or "improved". The only exceptions are items
that name a file and say what is wrong with it (T1, T2).

### 1.11. What you may assume

- `python3` is 3.14.6 here; the code must also run on 3.12. `pytest` is
  installed. `zstandard` is **not**, and acceptance check 11 reruns the
  suite with it blocked — the gzip fallback is load-bearing.
- Acceptance is 13/13 at your start and is ground truth about your work.
  Where your report and the script disagree, the script is right.
- You have network. See §1.12 before using it.

### 1.12. Network rules. Read before the first request

The application may now fetch real data. This is the most dangerous
capability in the project, for three reasons: a real number that is
wrong is indistinguishable from a right one; the repository is public;
and an unattended agent can send a great many requests while nobody
watches.

**N1. One source: SEC EDGAR.** Public, documented, free, no auth. No
price vendor, no scraper, no third-party mirror, no aggregator. Prices
stay synthetic tonight — vendor choice is T19, and it is a decision to
propose, not to make.

**N2. Identify yourself or do not go.** SEC's fair-access policy
requires a `User-Agent` carrying a real contact. Read it from the
environment:

```
RUSTERM_SEC_UA="Name Surname email@example.com"
```

Unset or empty → every network operation returns a `ConfigError`
**value** (never an exception, per `docs/module-contracts.md` §7), the
item degrades to the synthetic path, and the report records
`SEC_UA UNSET — network path not exercised`. That is an acceptable
outcome, not a blocker. **Never hardcode a contact, never commit one,
never invent one.** A fabricated contact is worse than no network.

**N3. Rate and ceiling, enforced in code, not by discipline.**

| Limit | Value | Behaviour at the limit |
|---|---|---|
| requests per second | 5 | limiter delays |
| requests per night, total | 5000 | provider **refuses** with a value |
| retries per failed URL | 2, then give up | E1/E2, recorded |

SEC documents 10/s; 5 is deliberate headroom for an unattended run.
Refusing rather than sleeping at the ceiling is deliberate too: a
sleeping agent at 04:00 burns the night silently. Count every request in
`STATE.json` `"net_requests"`.

**N4. 403 or 429 is a stop, not a puzzle.** Back off, record E1/E2, move
on. Do not change the User-Agent, do not switch IP, do not use a proxy,
a mirror or a search-engine cache. This was already the rule
(`agent/TASK.md` §6) and it now has teeth: violating it can get the
user's address blocked from a primary source with no substitute
(`docs/threat-model-sources.md` §2, class A).

**N5. Fetched data never enters git.** The raw store lives in the app
data directory (`AppPaths`), outside the repository; tests use
`tempfile`. Never `git add` a fetched document, an XBRL blob, a
`companyfacts` dump or a database. Acceptance check 13 catches leaks —
if it goes red with fetched files, delete them, do not commit them.

**N6. `fixtures/` stays synthetic-only.** Every file there carries
`synthetic` in its name and body, and that stays true. Real data goes to
the app data directory or to a golden file of *expected values*
(§T6) — never into `fixtures/`. Real and synthetic are never mixed and
never relabelled as each other.

**N7. Nodes 1, 3, 6, 7, 8, 9 of process 1 stay offline** and stay
testable offline on stored raw objects (`docs/processes.md` §46-123).
Network lives only in nodes 2 and 4. A test that needs the network skips
cleanly when `RUSTERM_SEC_UA` is unset; it never fails for that reason.

### 1.13. Money and quota

Three separate budgets. Do not conflate them.

**Your own model.** Free tier only. Paid models spend real money
silently and fast. If the chain switches you to a paid model, record it
in `STATE.json` and as its own line in the report, so the morning shows
where the money went. Count your calls in `"requests"`; at 800, enter
economy mode — finish the current item to a commit and close the night
with §3 rather than starting a new item.

**The application's model calls** (T16) spend the user's money per call.
Key from the environment:

```
RUSTERM_LLM_PROVIDER=<name>   RUSTERM_LLM_API_KEY=<key>
```

Unset → the fake client, and the report records
`LLM key unset — real path not exercised`. With a key: a hard ceiling of
**50 calls for the whole night**, counted in `"llm_calls"`, refusing
past it. No key ever appears in a commit, a log, a report or a test.

**Network requests** — §1.12 N3.

---

## 2. The work, in priority order

Strictly in order. Do not start an item before the previous one is
committed and pushed. The order is the priority: the list is longer than
one night on purpose, and stopping anywhere leaves the most valuable
things done.

Ordering rationale, so you can judge a trade-off the same way: T0–T2 are
defects that would corrupt real data silently, so they precede any
fetch. T3–T6 are the shortest path to **M2**, the first milestone that
proves a real number resolves to its source. T7–T9 reach **M3**. The
rest is breadth.

### T0. Restore invariant I16 — reported done, absent from the tree

TASK-4 required `test_i16_schema_change_reaches_existing_db` in
`tests/test_invariants.py`. The previous run reported it done; it does
not exist. Acceptance check 2 scans only `i01…i15`, so nothing caught it.

Add a function named exactly `test_i16_schema_change_reaches_existing_db`:

1. build a database at the previous schema version, insert a row;
2. apply current migrations;
3. assert `schema_version` grew, the row survived, and the new
   constraint is in force (an insert with `compression='gzip'` succeeds).

`tests/test_db.py:155` has the substance — reuse the approach, keep that
test. Do not touch `test_i01…test_i15`.

**Done when:**
```bash
python3 -m pytest tests/test_invariants.py -q -k i16
grep -c '^def test_i16_schema_change_reaches_existing_db' tests/test_invariants.py
```
→ `1 passed` and `1`.

### T1. Remove the shadowed import

`rusterm/store/db.py`, inside `open_connection()`: an `import sqlite3`
while the module already imports it at the top. Delete the inner line;
change nothing else.

**Done when:**
```bash
awk '/^def open_connection/,/^$/' rusterm/store/db.py | grep -c 'import sqlite3'
python3 -m pytest -q
```
→ `0` and green.

### T2. The table parser bypasses the basis rule (I3) — blocks real data

`rusterm/parsers/__init__.py`, `TableParser.parse`, writes
`"basis": "as_reported"` as a literal on every fact. `determine_basis`
is imported at line 19 and used by `SyntheticXBRLParser` (line 87), never
here. The previous report claims the basis rule is single-sourced from
core: true for one parser, false for the other.

`test_i03_basis_period_rule` tests `determine_basis` in isolation and
cannot see this — the same class of gap as the missing I16: rule tested,
call site not.

This is first among the blockers for real data. In real filings a
comparative column is the normal case, not an edge case, so the wrong
`basis` would be attached to a large share of everything you ingest.

Two faults, the second causing the first:

1. Every cell gets `period_start = period_end = doc["period_end"]` and
   `period_type = "instant"`, discarding the cell's own period before
   basis could be computed. A comparative column becomes
   indistinguishable from the current one.
2. Because of that, `basis` is hardcoded.

Fix both:

- Read the period from the cell, then the column, then the table,
  falling back to the document's `period_end` only when none is present.
- Read `period_type` the same way. Do not hardcode `"instant"` — revenue
  is a duration.
- Call `determine_basis(doc_period_end, fact_period_end, filed_at)`, as
  the XBRL parser does. No literal basis value anywhere.
- Extend `fixtures/synthetic_prices_table.json` or add a new synthetic
  fixture with a comparative column for an earlier period (`synthetic`
  in name and body).

Then close the class of gap: add `test_i17_parsers_apply_basis_rule` to
`tests/test_invariants.py`, iterating `registered_parsers()`, feeding
each a document with a comparative figure for an earlier period, and
asserting the fact comes back `basis == "restated"`. A future parser
that hardcodes basis must turn this red.

**Done when:**
```bash
grep -nE '"basis"[[:space:]]*:[[:space:]]*"' rusterm/parsers/__init__.py
python3 -m pytest tests/test_parsers.py tests/test_invariants.py -q
```
→ grep prints nothing; both files green including `test_i17_…`.

### T3. Request budget and rate limiter — the gate on all network work

`docs/processes.md` §"Бюджет запросов", `docs/module-contracts.md` §2
("собственный лимитер запросов"). Nothing of this exists. It is built
**before** the first real request, not after.

`rusterm/providers/budget.py`:

| Piece | Contract |
|---|---|
| `RateLimiter(per_second=5)` | delays to hold the rate; monotonic clock, not wall clock |
| `Budget(max_requests=5000)` | counts; past the ceiling `charge()` returns a `BudgetExceeded` **value**, never sleeps, never raises |
| `NetworkGate` | reads `RUSTERM_SEC_UA`; unset → every call returns `ConfigError`; present → supplies the `User-Agent` header |
| counters | exposed for `metric_sample`: requests made, refused, rate-limited |

Wired into the provider registry so no provider can bypass it. Synthetic
providers report zero cost and never touch the limiter.

**Done when** `tests/test_budget.py` is green and asserts: the 5001st
`charge()` returns `BudgetExceeded` rather than raising or sleeping; the
limiter holds ≤5/s over a burst of 20 with a fake clock (no real
sleeping in tests); with `RUSTERM_SEC_UA` unset, a provider call returns
`ConfigError` and makes no socket call.

### T4. SEC EDGAR provider — probe first, then build

`docs/module-contracts.md` §3. `rusterm/providers/edgar.py`, implementing
`DisclosuresProvider`, going through the gate from T3.

**Step 1, before writing the provider: probe and record.** The
endpoints below are the expected shape, not verified fact. Spend three
requests confirming them and paste the real shapes into
`agent/REPORT-7.md`:

```bash
# with RUSTERM_SEC_UA set
curl -s -H "User-Agent: $RUSTERM_SEC_UA" https://www.sec.gov/files/company_tickers.json | head -c 400
curl -s -H "User-Agent: $RUSTERM_SEC_UA" https://data.sec.gov/submissions/CIK0000320193.json | head -c 800
curl -s -H "User-Agent: $RUSTERM_SEC_UA" https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | head -c 800
```

If a shape differs from what is described below, **the live response
wins** — build against it and note the difference in **Disputed**. If
`RUSTERM_SEC_UA` is unset, skip T4–T6 entirely, record why, and go to T7.

Expected shapes:

- `company_tickers.json` — the whole ticker→CIK map in **one request**.
  This is what makes `resolve` cheap; never resolve a ticker with a
  per-company request.
- `submissions/CIK##########.json` — that issuer's filing index: form
  type, accession number, filing date, primary document.
- `api/xbrl/companyfacts/CIK##########.json` — every XBRL concept for
  the issuer, all periods, **one request per company**. This is the
  ingestion path.

**Step 2, the operations:**

| Operation | Contract |
|---|---|
| `resolve(ticker, market, as_of)` | from the cached ticker map; `ambiguous` with the list, or `not_found`; a date is mandatory (ADR-0005); silently taking the first match is forbidden |
| `poll_index(cursor)` | **one request per source, not per company** — this is what incrementality rests on. Returns new disclosure records plus a new cursor, persisted in `source_cursor` |
| `list_documents(issuer_id, type, period)` | from `submissions`, metadata only, no bodies |
| `fetch_document(url)` | one raw object; idempotent — the same document yields the same `sha256` |

Every operation returns errors as values, never raises
(`docs/module-contracts.md` §7). Cache validators (`ETag`,
`If-Modified-Since`) are used, and `not_modified` is returned when the
source says so — that is what keeps the daily budget in minutes.

**Done when** `tests/test_edgar.py` is green with: the whole suite
passing offline against saved responses (put them in the app data
directory or `tempfile`, **not** `fixtures/`, **not** git); a network
test that skips cleanly when `RUSTERM_SEC_UA` is unset; and `resolve`
proven to consume exactly one request for N tickers, not N.

### T5. Real XBRL parser over `companyfacts`

`docs/module-contracts.md` §4, `docs/data-model.md` §3. The synthetic
XBRL parser stays; this is a second parser registered alongside it.

Real XBRL is messy in specific ways. These are the rules — do not
improvise them:

- **Units.** `companyfacts` groups values under `units` keyed by unit
  (`USD`, `shares`, `USD/shares`). Pick the unit the concept expects.
  Taking the first key silently is forbidden; no expected unit → the
  fact is `suspect` with a reason, not dropped.
- **Duplicates across filings.** The same `(concept, start, end)` appears
  once per filing that reported it. This is exactly the basis
  distinction, and T2 is what makes it work: the entry whose filing
  period matches the fact period is `as_reported`; a later filing
  restating an earlier period is `restated`. Feed
  `determine_basis(doc_period_end, fact_period_end, filed)` and keep
  **both** facts — never deduplicate by dropping, never average, never
  pick the "more plausible" one.
- **Forms.** Keep `form` (`10-K`, `10-Q`, `8-K`, …) and `accn`. TTM needs
  quarterlies; annual-only ingestion silently breaks it.
- **Amendments.** `10-K/A` supersedes `10-K` for the same period — it
  is a `restated` fact with its own locator, not an overwrite.
- **Dimensions/segments.** Entries carrying a segment axis are not the
  consolidated figure. Tonight: keep only undimensioned entries; count
  the rest into the unparsed counter. Never mix a segment figure into a
  consolidated metric.
- Every fact gets `kind=xbrl` locator, `basis`, `source_ref` = the raw
  object's `sha256`, and must satisfy `resolve(locator)`.

**Done when** `tests/test_edgar_parser.py` is green with: a saved real
`companyfacts` response parsed offline; a case producing both an
`as_reported` and a `restated` fact for the same concept and period; a
multi-unit concept picking the right unit; a segment entry counted as
unparsed rather than ingested; and every produced fact passing
`resolve(locator)`.

### T6. **M2** — five issuers, five years, against a golden file

`docs/quality-and-observability.md` §5. This is the milestone the whole
project exists to reach: *every number resolves to an XBRL fact.*

- Five US issuers, large and boring, so their filings are complete.
  Fixed list, do not improvise: `AAPL`, `MSFT`, `JNJ`, `KO`, `XOM`.
- Five completed fiscal years.
- Key metrics from `docs/data-dictionary.md`: revenue, net income, total
  assets, total equity, operating cash flow, plus the derived
  `roic`, `roe`, margins.
- Golden file `tests/golden/m2_us_issuers.json` holds **expected values
  and their locators, not raw documents**: concept, period, basis,
  expected value, unit, `accn`, source URL, raw `sha256`. It is small,
  reviewable, and committed. The documents themselves stay out of git
  (§1.12 N5).
- Build the golden file from a real fetch, then **verify a sample by
  hand against the filing** and record in the report which values you
  checked and against what. A golden file generated by the same code it
  tests proves nothing; the hand-checked sample is what gives it force.
- The test runs offline against saved raw objects and skips cleanly with
  no `RUSTERM_SEC_UA`.

**Done when** `python3 -m pytest tests/test_m2_golden.py -q` is green,
and for every value in the golden file `resolve(locator)` returns the
document and the value, byte-comparable. Record in the report:
`M2: N of 5 issuers, M of 5 years, K values, all resolving.`

### T7. Coverage — a gap is shown, never hidden

`docs/watchlist-and-llm.md` §1.3. Table `coverage` exists; nothing
writes it.

- `CoverageRepo`: `upsert(instrument_id, block, status, last_update,
  reason)`, `for_instrument`, `for_watchlist`.
- Blocks, exactly these eight: `prices`, `fundamentals`, `ownership`,
  `corporate_actions`, `governance`, `industry_metrics`, `peer_set`,
  `llm_summary`.
- Statuses, exactly these five: `ready`, `stale`, `processing`,
  `missing`, `error`.
- `missing` and `error` **require** a non-empty reason, enforced in the
  repo, not by convention.
- Snapshot assembly writes coverage for all eight blocks on every run. A
  block with no data gets `missing` plus a reason; it is not skipped.
- A source that failed (E1/E2 from T4) produces `error` with the cause,
  per `docs/threat-model-sources.md` §2 class A: collected data is not
  lost, the snapshot still builds on what exists, and `as_of` honestly
  shows the date of the last data.

**Done when** `python3 -m pytest tests/test_coverage.py -q` is green and
one test asserts a prices-only instrument yields exactly 8 coverage
rows, 7 `missing` with non-empty reasons.

### T8. Process 5 — verification and ground truth

`docs/processes.md` §263-284. Table `verification` exists; nothing writes
it. This is what turns a wrong real number into a signal instead of
endless manual work, so it lands right after real data starts flowing.

| Node | Contract |
|---|---|
| `capture` | what was shown, what it should be, link to the document; row in `verification` |
| `store_ground_truth` | new fact, `origin='manual'`, priority over the extracted one; **the extracted fact is not deleted** — it gets `superseded_by` pointing at the manual one |
| `recompute` | recompute every measure whose lineage touches the superseded fact |
| `propose_golden` | append the (raw, expected) pair to the golden-file proposal set |
| `flag_parser` | mismatch counter per `(provider, concept)`; over threshold the parser is marked degraded |

- `superseded_by` needs **migration 34** if the column does not exist.
  New migration, never an edit (P2).
- Threshold: **5 mismatches per (provider, concept) in a rolling 30
  days.** Deterministic; no tuning.
- A degraded parser surfaces through `coverage.reason`, not only in logs.

**Done when** `tests/test_verification.py` is green and asserts: the
extracted fact still exists and carries `superseded_by`; a derived
measure changed after `recompute`; the 5th mismatch flips the parser to
degraded and the 4th does not.

### T9. **M3** — twenty issuers, one pass, gaps with reasons

Extend T6's five to twenty US issuers. One `ingest` pass, then one
`snapshot` pass per issuer.

- Missing blocks are shown with a reason, never silently absent (T7).
- Repeat the pass: no new raw objects, no new facts, no new jobs
  (M1 idempotency, now on real data).
- Record the request count for the whole pass and compare it with the
  estimate in `docs/processes.md` — that estimate is explicitly marked
  unmeasured, so your number is the first measurement. Put it in the
  report as its own line; if it differs by more than 2×, say so in
  **Disputed** so the doc gets corrected.

**Done when** `python3 -m pytest tests/test_m3_snapshot.py -q` is green
and the report carries: `M3: 20 issuers, one pass, N requests, M blocks
missing with reasons, repeat pass created 0 new objects/facts/jobs.`

### T10. WatchlistRepo — read side and immutable versioning

`docs/watchlist-and-llm.md` §1.1. Tables exist; the repo has three write
methods and no reads.

| Method | Contract |
|---|---|
| `current_version(watchlist_id)` | max version row, or `None` |
| `members(watchlist_id, version=None)` | default = current |
| `groups`, `filters` | same versioning; `criteria_json` parsed |
| `add_group`, `add_group_member`, `set_filter` | write into a given version |
| `rollback_to(watchlist_id, version)` | **inserts a new version** copying that version's members, groups and filters; never deletes, never rewrites; `action='rollback:<n>'` |
| `list_watchlists()` | id, name, current version, member count |

A composition change is a new version plus a fresh member set. No
in-place edit of a version, ever.

**Done when** `tests/test_watchlist.py` asserts: version 3 after three
edits; `rollback_to(1)` makes version 4 whose members equal version 1's;
version 1's rows unchanged before and after.

### T11. Watchlist import and export

`docs/watchlist-and-llm.md` §1.4.

- Export CSV and JSON, ticker-addressed, columns exactly
  `ticker,market,isin,industry,note,added_at`.
- Import runs every row through `resolve_ticker(ticker, market, as_of)`.
  Unresolved or ambiguous → the import report, **not added**. Silent
  skipping is the defect this item exists to prevent.
- The report returns `added`, `already_present`, `not_found`,
  `ambiguous`, each with reasons.

**Done when** `tests/test_watchlist_io.py` asserts a 4-row import (1
good, 1 unknown, 1 ambiguous, 1 present) adds exactly one member and
reports the other three by category.

### T12. System metrics

`docs/quality-and-observability.md` §3. Table `metric_sample` exists;
nothing writes it. All nine, computed from the database, in
`rusterm/core/metrics.py`: `provider_success_rate`,
`provider_rate_limited`, `data_lag`, `suspect_share`, `unparsed_share`,
`verification_queue`, `peer_set_coverage`, `peer_set_churn`,
`locator_resolve_failures`.

`provider_success_rate` and `provider_rate_limited` now have real inputs
from T3's counters — wire them, do not stub.

**No metric invents a value.** With no input rows the metric is not
recorded, rather than recorded as 0: a missing sample and a zero are
different facts, and the second one lies.

**Done when** `tests/test_metrics.py` asserts, for each of the nine, a
computed value on seeded data and "not recorded" on empty data.

### T13. Logs — three destinations, never mixed

`docs/quality-and-observability.md` §4.

- `logs/app.log` — rotated by size (`RotatingFileHandler`, 5 × 1 MB).
- `logs/audit.jsonl` — user operations, append-only, one JSON object per
  line, must survive loss of the database; never rotated.
- `raw/manifests/*.jsonl` — unchanged.

Paths via `rusterm/store/paths.py`. `AuditRepo` writes both the
`audit_log` table and the JSONL line, and **the JSONL line is written
even when the database write fails** — that is its whole point. No URL
with a key or token is ever logged.

**Done when** `tests/test_logs.py` asserts: the audit line survives a DB
connection closed mid-operation; `app.log` rotates past the limit;
neither file contains the other's records.

### T14. CLI for everything new

Extend `rusterm/cli/` — no SQL there (check 7):

```
rusterm watchlist create|add|remove|list|show|rollback
rusterm watchlist export --format csv|json
rusterm watchlist import <file>
rusterm coverage <instrument-id | --watchlist ID>
rusterm metrics [--record]
rusterm verify --fact <id> --expected <value> --document <url>
rusterm budget                      # requests used, remaining, refused
```

`rusterm ingest` gains `--source edgar|synthetic`, defaulting to
`synthetic`. Real fetching is never the default.

**Done when** `tests/test_cli.py` covers each new command end-to-end and
`python3 -m pytest -q` is green.

### T15. LLM guard rail — deterministic, and it comes before any model

`docs/watchlist-and-llm.md` §2.6. Build this **before** T16; a real
model behind a missing guard rail is how invented numbers reach a
screen.

- The renderer substitutes numbers **from the snapshot**, never from
  model text.
- The validator: any statement containing a number with no matching
  entry in `citations` discards the **whole text** — the block stays
  `missing`, reason "модель не смогла удержаться в данных". Partially
  cleaned text is never stored. An empty block is honest; a plausible
  one is not.
- Storage in `llm_summary`: `instrument_id`, `created_at`, `model`,
  `prompt_hash`, `snapshot_version`, text, `citations`.
- The client is a `typing.Protocol`; the fake implementation lives in
  tests.

**Done when** `tests/test_llm_guard.py` asserts: a fake response with an
invented number is rejected in full (nothing in `llm_summary`, coverage
`missing` with that reason); a fully-cited response is stored; and
`grep -rnE 'httpx|requests' rusterm/core/ rusterm/normalize/` prints
nothing.

### T16. Real model behind the guard rail — **M5**

Only after T15 is green.

- Provider and key from `RUSTERM_LLM_PROVIDER` / `RUSTERM_LLM_API_KEY`.
  Unset → the fake client, recorded, item done as far as it can go.
- HTTP lives in `rusterm/providers/` and nowhere else (check 8).
- Hard ceiling **50 calls for the night**, counted in
  `STATE.json` `"llm_calls"`, refusing past it.
- The key never appears in a commit, a log, a report, a test or a
  `prompt_hash` input.
- The model gets **read-only tools only** (`docs/watchlist-and-llm.md`
  §2.4): `resolve_ticker`, `list_industry_instruments`, `get_peer_set`,
  `get_snapshot_block`. Not one state-changing tool. Changes are made by
  the application after confirmation.
- **No bulk operation executes tonight.** Nobody is awake to confirm, and
  §2.3 requires confirmation of the shown list as a condition of
  execution. Dry-run only: produce the list with each row marked (will be
  added / excluded by filter / already present / unresolved) and stop.
  `docs/watchlist-and-llm.md` §2.5 also forbids showing a time estimate —
  there is no measurement behind one.
- Model self-assessed `confidence` is logged and **never** branched on
  (§2.3).

**Done when** `tests/test_llm_real.py` is green: it skips cleanly with no
key; with a key it makes at most 2 calls and asserts every numeric
statement carries a citation, and that a dry-run mass operation executes
nothing.

### T17. Governance traffic light, `governance.v1`

`docs/governance-thresholds.md`, all five indicators, thresholds
verbatim. Deterministic over facts — no model, no heuristics, no
invented cutoffs.

- `rusterm/core/governance.py`; **migration 35** for
  `governance_assessment(instrument_id, indicator, color, method_version,
  as_of, lineage_ref, reason)`.
- Independent-director share; CEO/chair combination; related-party
  transactions to revenue; net insider transactions (rolling 12 months);
  auditor.
- Hard rules, each its own test: no aggregate score, five separate
  colours, never summed or weighted; missing data is `gray`, never
  `green`; a colour without `lineage_ref` is never emitted — raise;
  thresholds apply to the last completed reporting year except
  indicator 4.
- `method_version = "governance.v1"` on every row; a threshold change is
  a new version, history never recomputed in place.

**Done when** `tests/test_governance.py` is green: one test per
indicator hitting all four colours; one asserting no aggregate/score
field exists; one asserting an empty lineage raises.

### T18. Maritime / Tanker industry metrics

`docs/industry-metrics/maritime-tanker.md`: the metrics in "Специфичные
метрики", the tests named in "Тесты", the default pure-play peer set.

- `rusterm/core/industry/maritime_tanker.py`.
- Every metric carries `scope` and null-reasons exactly like the
  measures in `rusterm/formulas.py` — **reuse that machinery, do not
  fork it**.
- Maritime/Tanker only; no other industry, not even a stub.

**Done when** `tests/test_industry_maritime.py` is green and every test
named in the doc exists by that name.

### T19. ADR-0006 — propose a price vendor, do not choose one

`docs/processes.md` says the price-vendor limits are unknown until a
vendor is picked, and `docs/adr/` has no 0006 for it. That decision has
money and terms-of-service attached, so it is the user's, not yours.

Write `docs/adr/0006-postavshchik-kotirovok.md` (this is a **new ADR**,
which acceptance check 10 permits): candidates with their documented
limits, cost, whether `close` **and** `adjusted` are both available
(`docs/module-contracts.md` §2 requires both), and terms of use for a
desktop application. `docs/threat-model-sources.md` §2 class B requires
**two** configured providers, so propose at least two plus a fallback
order. End with a recommendation and an explicit
`Статус: предложено, требует решения пользователя`.

Implement nothing against a vendor. Prices stay synthetic.

**Done when** the file exists, names ≥2 candidates with limits and
costs, and `python3 -m pytest -q` is still green. No provider code.

### T20. Queue empty

All of T0–T19 done before 09:30 — take `agent/BACKLOG.md` top down. Do
not invent work beyond it.

---

## 3. Night end — you run the final acceptance yourself

At 10:00 Danang, or when T20 is reached. The point is that the next
reader starts from machine evidence in the repository, not from prose.

```bash
git status --porcelain                                   # must be empty
git log --oneline origin/agent/night-2..agent/night-2    # must be empty
python3 -m pytest -q
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-5.txt
git add agent/ACCEPTANCE-5.txt agent/REPORT-7.md agent/STATE.json
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

Then append to `agent/REPORT-7.md`:

```
## HANDOFF
Status:          DONE | PARTIAL | BLOCKED
Items done:      T0 … Tn
Items not done:  Tn+1 … T20, and why
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-5.txt)
Tests:           N passed, M skipped, K xfailed
Milestones:      M2 yes/no, M3 yes/no, M5 yes/no
Network:         RUSTERM_SEC_UA set? — N requests, M refused, K rate-limited
Model:           key set? — N calls; my own model: <id>, R requests
Pushed:          yes | no — bundle at handoff.bundle
Questions for the coordinator:
  - …
```

and set `agent/STATE.json` to `"status": "awaiting_review"`, commit,
push.

`PARTIAL` is the expected outcome — the list is longer than one night on
purpose, ordered so that stopping anywhere leaves the most important
things done. The only bad outcome is a `DONE` that a rerun contradicts:
everything here gets rerun.

## 4. Scope boundary

In scope now, and new since the last task: real SEC EDGAR data, a real
model behind the guard rail.

Out of scope tonight, no exceptions for spare time:

- Qt or any GUI — `docs/ui-architecture.md` exists, and it is a separate
  body of work that would swallow the night
- UK and CA providers (M6), Industry View (M7)
- industry metrics beyond Maritime/Tanker
- any price vendor (T19 proposes, does not implement)
- executing any bulk operation on the user's behalf (§T16)

Widening the scope is a failure of this task, not a bonus.

## 5. Stack

Python 3.12+, must also run on 3.14. Standard library; `pytest`;
`sqlite3` from stdlib; `zstandard` optional with `gzip` fallback;
`httpx`/`requests` only inside `rusterm/providers/`. Forbidden: ORM,
`alembic`, `pandas`, `numpy`, async frameworks.

`list`, `dict`, `tuple`, `set` are builtins — write `list[str]`, with
`from __future__ import annotations` at the top of the module.

New dependency needed for HTTP — prefer `urllib.request` from stdlib. If
you install `httpx`, record it in the report with the reason; it must
stay inside `rusterm/providers/`.

## 6. Acceptance script

`bash agent/acceptance.sh` — thirteen machine checks, **13/13 when you
start**. Run after every commit; never let it drop below 13.

**Editing that file is forbidden.** Check 12 compares it byte for byte
against `origin/main`, and an edit voids the whole night regardless of
what else you did. Think a check is wrong — write it in **Disputed**.
That section gets read: last night's agent raised two disputes and the
coordinator upheld both.
