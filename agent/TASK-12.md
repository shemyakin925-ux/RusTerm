# TASK-12 — the dead tags that poison a period

- **Status: READY** — this is the task. Start here.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-12.md`
- **Supersedes:** TASK-10 (**ACCEPTED**, W0–W8) and TASK-11
  (**ACCEPTED**, X1–X4, X5 partial). Both verified on a clean checkout.
  Do not reopen them.
- **Goal of the night, in one sentence:** a measure stops reading
  `period_mismatch` because one of its inputs is a tag the company
  abandoned in 2012 — the map learns the tags companies switched to, and
  a fact too old to belong to the current period is `missing_data`, which
  is the truth, instead of dragging a whole measure down with it.

You are an autonomous coding agent with the same tools as the
coordinator: shell, file editing, test runs, network. This file gives
contracts, decisions and acceptance commands, not tutorials. Anything
readable from the repository, read from the repository.

No coordinator is online during the run. Every fork below is closed by a
deterministic rule. Where a rule is wrong, follow it and put the
objection in **`## Disputed`** — see §0.3, which is about *where* you
put it, because for three tasks running the section has been empty while
the disputes were real.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git merge origin/main          # brings TASK-12, TASK-13, the docs row, LAUNCH
bash agent/acceptance.sh
```

The last command must print `Итог: пройдено 13, провалено 0`. The
coordinator ran exactly this on a clean detached checkout of
`agent/night-2` at `6246fa1` and got 13/13 with
`289 passed, 2 skipped, 1 xfailed`.

**The merge comes first and matters this time.** `origin/main` carries a
new row in `docs/processes.md`'s sibling `docs/data-dictionary.md` §2 —
`total_equity_incl_nci`, the dictionary line you were owed and could not
write yourself. Run acceptance *before* merging and check 10 goes red
against the lagging branch; that is the expected state, not a defect.
After the merge, Y4 removes the escape hatch you had to add.

Then read, in full and from the repository, the files you will touch:
`rusterm/normalize/concepts.py`, `rusterm/core/snapshot.py`,
`tools/trim_companyfacts.py`, `tests/test_m3_snapshot.py`,
`tests/test_concept_map.py`, `rusterm/cli/__init__.py`,
`docs/data-dictionary.md`.

---

## 0.1. Where the project stands — measured, not reported

Re-run by the coordinator on a clean detached checkout at `6246fa1`:

| Check | Result |
|---|---|
| `bash agent/acceptance.sh` | **13/13**, `Принято` |
| `python3 -m pytest` | **289 passed, 2 skipped, 1 xfailed** |
| deleted `assert` | 12 lines — **every one replaced by an equal or stronger assertion**, checked one by one |
| edits to applied migrations | **0** |
| `agent/acceptance.sh` vs `origin/main` | byte-identical |
| `docs/` | untouched |
| `tests/data/golden_m2.json` `expected` values | **not one changed** — only the 125 `json_pointer` lines regenerated |
| JNJ FY2021 in the re-trimmed payload | `93775000000`, `accn 0000200406-22-000022` — as-reported survived |
| `du -sk tests/data/edgar/` | 504, manifest 20 entries, every sha256 matches |

**The night did what it was for.** The coordinator rebuilt all twenty
snapshots and counted every measure again:

| measure | before | after |
|---|---|---|
| `net_margin` | 20/20 | 20/20 |
| `effective_tax` | 0/20 | **20/20** |
| `asset_turnover` | 5/20 | **20/20** |
| `roe` | 4/20 | **18/20** |
| `fcf` | 0/20 | **14/20** |
| `nopat` | 0/20 | **14/20** |
| `operating_margin` | 0/20 | **14/20** |
| `interest_coverage` | 0/20 | **12/20** |
| `ebitda` | 0/20 | **11/20** |
| `gross_margin` | 0/20 | **7/20** |

Eight measures went from nothing to most of the field. That is the
largest single-night gain this project has had.

**What is left is the tail, and it has one cause.** Of the nulls that
remain, `period_mismatch` accounts for 13 across six issuers. The
coordinator dumped the latest as-reported period of each input, per
issuer, and the pattern is not subtle:

| issuer | concept | its latest period | every other input |
|---|---|---|---|
| AMZN | `capex` | **2016** | 2025 |
| NVDA | `capex` | **2011–2012** | 2025–2026 |
| TSLA | `d_and_a` | **2017** | 2025 |
| BRKB | `operating_income` | **2012** | 2025 |
| JNJ | `operating_income` | **2013–2014** | 2025 |

These are not missing numbers. They are **tags the company stopped
using**, still sitting in `companyfacts` from a decade ago, and the V1
rule dutifully reports that no common period exists. The coordinator
checked the live feed for three of them:

- **AMZN** tags capex as `PaymentsToAcquireProductiveAssets` through
  2025. The map only knows `PaymentsToAcquirePropertyPlantAndEquipment`,
  which Amazon last filed in 2016.
- **TSLA** tags `Depreciation` through 2025. All three variants the map
  knows die for Tesla in 2017.
- **BRKB** genuinely has nothing: Berkshire has not tagged
  `OperatingIncomeLoss` since 2012 and there is no successor.
  `NonoperatingIncomeExpense` is a different thing and is **not** the
  answer. Same for JNJ.

So two different fixes, and the night needs both: **Y1** teaches the map
the tags companies switched to, and **Y2** stops a decade-old fact from
being chosen at all — which turns BRKB's and JNJ's `operating_margin`
from a misleading `period_mismatch` into an honest
`missing_data: operating_income`.

A warning that belongs with Y1: searching the feed for `PaymentsToAcquire`
also returns `PaymentsToAcquireMarketableSecurities`, which is not capex
and would be a wrong number rather than a missing one. **The map is
extended by named decision, never by substring match.** That is why Y1
lists the tags explicitly and forbids you to add others.

| Layer | State |
|---|---|
| store, migrations, parsers, provider, pipeline, coverage | done |
| concept map, one-period selection, period and unit on the measure | done, `us-gaap.v2` |
| recorded payloads + `tools/trim_companyfacts.py` | done, reproducible, accn-aware |
| the `docs/data-dictionary.md` §3 formula set | **eight of ten measures carry values — Y1/Y2 for the tail** |
| `rusterm add` / `ingest` / `snapshot` / `export` / `tui` / `doctor` | done, end-to-end covered by subprocess test |
| M1, M2, M3-with-the-formula-set | reached |
| M5 | not started, needs a key |

---

## 0.2. Rulings on your four questions. All four answered

### 1. W1-vs-W2: the annual band. Upheld, and it was my spec that was wrong

You found that "six most recent by `end` over 10-K entries" pulls in
quarterly comparatives, which evict the annual periods and make W2's own
JNJ check impossible — then implemented six most recent **annual**
durations (≥ 350 days) plus six most recent other periods, per tag per
unit, and recorded both quotes.

**Correct on all three counts**: the conflict is real, my W1 text was
underspecified, and your reading is the one that satisfies both
requirements. Confirmed as the contract. Y3 writes it into the tool's
docstring so the next reader does not re-derive it.

### 2. `operating_margin` 14/20 against a floor of 15, `gross_margin` 7/20 against 10

**My floors were guesses and two of them were wrong.** JPMorgan is a
bank and does not report operating income in the industrial sense;
Pfizer, Chevron and Exxon do not tag `OperatingIncomeLoss` consistently.
`GrossProfit` is disclosed by 7 of 20 because a great many issuers never
tag it. 14 and 7 are what the data supports, not a shortfall.

**You handled it exactly right**: floors not lowered, the shortfall moved
to `xfail(strict=True)` naming the four issuers, the defect reported.
Strict xfail is stronger than a lowered floor, because an improvement
turns it red and forces a review instead of passing silently.

**Ruling, implement both halves:**

- The passing test's floors for these two become **14** and **7** — the
  measured truth, so a regression is caught.
- The strict-xfail test **keeps 15 and 10** unchanged, so Y1's new tags
  turning `operating_margin` into 15/20 flips it red and lands on my
  desk. That is the intended outcome, not a failure.

### 3. `total_equity_incl_nci` missing from `docs/data-dictionary.md`

**Upheld, and it was my debt.** You were right to refuse the docs edit —
check 10 exists precisely so code cannot be legalised by rewriting the
specification. The row is on `origin/main` now. Y4 removes the
`RULED_BEYOND_DICTIONARY` hatch you had to add; an escape hatch in a
guard test is the kind of thing that quietly becomes permanent.

### 4. `current_version` → `version` renamed in passing

**The rename stands; the way it happened does not.**

On the substance you are right: once `watchlist show` can print any
version, `version` is the truthful key and `current_version` is a lie.
B16 pinned the new schema the same night, so nothing is left dangling,
and reverting would cost more than it returns.

On method: a user-visible `--json` key is a contract. Renaming one is a
task item with its own line in the report, never a side effect of an
unrelated backlog entry — the word in your own report is «попутно», and
that is the warning sign. **New project rule, in force from now:** a
change to any `--json` key name, any exit code, or any command-line flag
is either named by a task item or does not happen. If you find one that
must change, put it in `## Disputed` and keep the old name that night.

---

## 0.3. The section that keeps coming back empty

`## Disputed` in `agent/REPORT-10.md` and `agent/REPORT-11.md` is empty.
Both nights had real disputes — the W1/W2 conflict, the missing
dictionary row, two floors — and every one of them was written somewhere
else: inline in a `Done` bullet prefixed `DISPUTED:`, or under
`Questions for the coordinator`.

Nothing was lost this time because the review reads the whole file. But
the coordinator's protocol reads `Disputed` **first**, before `Done`, and
a night that buries its objections in the middle of a success log is one
bad morning away from having them missed.

This is the third task in a row that has asked in prose. So it stops
being prose: **Y6 makes it a machine check.** Meanwhile the rule, stated
once more and plainly:

- **`## Disputed`** — anything where you think this file, `docs/` or the
  acceptance script is wrong. One entry per disagreement, with both
  quotes.
- **`Questions for the coordinator`** — things you need a decision on but
  do not disagree with.
- An entry may appear in both. An entry in neither, mentioned only in a
  `Done` bullet, does not count as raised.

Your record in that channel is excellent — sixteen of seventeen disputes
upheld — which is exactly why it should be easy to find.

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
8. RECORD   one line in agent/REPORT-12.md: command + its output (§1.7).
```

Steps 6 and 7 do not get deferred. One item, one commit, one push bounds
any loss to the item in flight.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong. A genuinely obsolete assertion is **replaced
by a stronger one**, and the report says how the new one is stricter.

**P2. Never edit an existing migration.** Schema change = **new**
migration, new number, `_SCHEMA_VERSION` bumped. Next free number is
**37** (34 does not exist and never will; 36 is `canonical_concept`, and nothing has needed 37 yet).

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

### 1.7. Bookkeeping — and the rule that came out of the empty report

`agent/REPORT-12.md` is **append-only and verified after every write.**
The empty-report incident cost a whole night's history. Three rules,
now project rules and not personal ones:

- **R1.** Never open the report with a truncating mode. Append only:
  `printf '%s\n' "…" >> agent/REPORT-12.md`, or a quoted heredoc with
  `>>`. Never `>`, never `open(p, "w")` on it.
- **R2.** After every append, run
  `wc -c agent/REPORT-12.md && tail -3 agent/REPORT-12.md` and look at the
  output. A zero-byte or shrinking report is an incident to fix at once,
  before the next item.
- **R3.** Chain commands with `&&`, never with `;`. A `;` after a red
  `pytest` hides the failure from the next step.

Sections, in this order: **Done** (one line per item: command + output),
**Blocked**, **What not to trust**, **Disputed**, and — filled at the
end, never deleted — **HANDOFF** (§3 template). Last line always
`NOW: <item>, step <n>`.

`agent/STATE.json`, same commit as the work:

```json
{"task": "agent/TASK-12.md", "report": "agent/REPORT-12.md",
 "item": "Y1", "step": "4", "status": "working",
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
`agent/REPORT-12.md`, keep committing locally, and at the end produce
`git bundle create ../RusTerm-handoff.bundle --all` (outside the repo, so
check 13 stays green). Say so in `## HANDOFF`. Last night's push failed
only at the very end; the coordinator pushed the tail by hand.

### 1.9. Stop time

**10:00 Danang (UTC+7).** Finish the current item to a commit and a
push, then do §3. Do not start a new item after 09:30. A session started
by the coordinator by hand outside those hours runs until its work is
done — that reading was disputed and upheld.

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
synthetic — the vendor decision is `docs/adr/0008-…`, awaiting the user.

**N2. Identify yourself or do not go.** `RUSTERM_SEC_UA` must carry a
real contact. Unset or empty → every network operation returns a
`ConfigError` **value** (never an exception), the item degrades to the
offline path, and the report records
`SEC_UA UNSET — network path not exercised`. **Never hardcode a contact,
never commit one, never invent one.** The application reads
`~/.rusterm.env` itself since U4 — check with `rusterm doctor` rather
than assuming the shell is empty.

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

**N5. Fetched data never enters git** — except a trimmed recorded
payload under `tests/data/edgar/`, which is a test fixture of *real*
shape and is small. That exception is what Y1 uses.

**N6. `fixtures/` stays synthetic-only.**

**N7. Network lives only in nodes 2 and 4 of process 1.** A network test
skips cleanly when `RUSTERM_SEC_UA` is unset; it never fails for that.

### 1.13. Money and quota

**Your own model.** Free tier only. If the chain switches you to a paid
model, record it in `STATE.json` and as its own report line. Count your
calls in `"requests"`; at 800, finish the current item to a commit and
close the night with §3.

**The application's model calls.** Key from `RUSTERM_LLM_PROVIDER` /
`RUSTERM_LLM_API_KEY`. Unset → the fake client, and the report records
`LLM key unset — real path not exercised`, and V7 is skipped, not
simulated. With a key: a hard ceiling of **50 calls for the whole
night**, counted in `"llm_calls"`. No key ever appears in a commit, a
log, a report or a test.

---

## 2. The work, in priority order

Y1 and Y2 are the night. They are independent of each other: Y1 without
Y2 still adds numbers, Y2 without Y1 still stops lying about why a
number is missing.

---

### Y1. The map learns the tags companies switched to

`rusterm/normalize/concepts.py` `CONCEPT_MAP` is authoritative and is
extended **only** by the named additions below. Do not add a tag that is
not on this list, do not reorder existing tags, do not search the feed
for likely-looking names — the coordinator checked what a substring
search returns and it includes `PaymentsToAcquireMarketableSecurities`,
which is not capex and would produce a **wrong number** where there is
now an honest gap.

Additions, appended at the end of each concept's tuple so existing
priority is untouched:

| concept | append | why |
|---|---|---|
| `capex` | `PaymentsToAcquireProductiveAssets` | AMZN tags this through 2025; the current tag dies for it in 2016 |
| `d_and_a` | `Depreciation` | TSLA tags this through 2025; all three current variants die for it in 2017 |

That is the whole list. Two tags.

- `CONCEPT_MAP_VERSION` becomes **`us-gaap.v3`**. The table changed;
  the version says so.
- `docs/data-dictionary.md` needs no change — both are existing
  concepts gaining a source tag, not new concepts.
- Priority matters: `PaymentsToAcquireProductiveAssets` goes **after**
  `PaymentsToAcquirePropertyPlantAndEquipment`, so an issuer that files
  both keeps the one it has always used.

`tests/data/edgar/` payloads must be re-trimmed for the new tags to be
present at all. Skip the re-fetch **entirely** if `RUSTERM_SEC_UA` is
unset — record `SEC_UA UNSET — payload refresh not exercised`, do the
map change and its unit test, and say in `## Blocked` that Y1's effect on
the twenty cannot be measured. Do not simulate it.

With a contact: re-fetch the twenty, re-trim through
`tools/trim_companyfacts.py` unchanged, regenerate the manifest. Same
rules as before, and the same red line: **no `expected` value in
`tests/data/golden_m2.json` changes.** A changed expected value is a
stop, not a fix.

**Done when** a test asserts both new tags map to their concepts and
that `PaymentsToAcquireMarketableSecurities` maps to **nothing**;
`rusterm status --json` reports `us-gaap.v3`;
`git diff tests/data/golden_m2.json | grep '^[-+].*expected'` is empty;
`du -sk tests/data/edgar/` stays under 1024; `python3 -m pytest -q`
exits 0.

---

### Y2. A decade-old fact is `missing_data`, not `period_mismatch`

Berkshire has not tagged operating income since 2012 and there is no
successor tag. Today that turns into `period_mismatch` on four measures,
which blames period alignment for what is actually an absent disclosure.
`period_mismatch` should mean *these inputs exist and disagree*;
`missing_data` should mean *this input is not there*.

The rule, deterministic:

- For an issuer, let **`anchor`** be the newest `period_end` among that
  issuer's `as_reported` facts of any canonical concept the measure set
  uses.
- An input fact whose `period_end` is more than **1100 days** before
  `anchor` (three years plus slack for fiscal-year drift) is **not
  eligible** as an input to any measure.
- A concept with no eligible fact is `missing_data`, named as X3 already
  names them (`missing_data: operating_income`).
- `period_mismatch` is then reserved for what it says: eligible inputs
  that share no common period.

Implement it in the selection function `_issuer_inputs` uses, not by
filtering in `as_reported_facts` — the store keeps every fact, and a
stale fact is still a fact that `verify` and the source panel must be
able to show. Nothing is deleted and nothing stops being stored.

1100 days is a rule, not a preference. If you think it is wrong, follow
it and write why in `## Disputed`.

**Done when** a test seeds one issuer with `revenue` and `net_income` at
2025 and `operating_income` at 2012 and asserts `operating_margin` is
`missing_data: operating_income`, **not** `period_mismatch`; a second
test seeds two eligible inputs on different 2024/2025 periods and
asserts `period_mismatch` still happens; the M3 table shows BRKB's and
JNJ's `operating_margin` reason changed accordingly;
`python3 -m pytest -q` exits 0.

---

### Y3. The floors, and the docstring the trim is owed

Per §0.2 rulings 1 and 2. Three small edits, no design in them:

- `tests/test_m3_snapshot.py`: the passing test's floors for
  `operating_margin` and `gross_margin` become **14** and **7**.
- The strict-xfail test keeps **15** and **10** unchanged. After Y1 and
  Y2 it may go red — **that is the intended outcome.** If it does, do not
  touch either number: report it in `## Disputed` with the new table and
  let the coordinator move the floors.
- `tools/trim_companyfacts.py` gets its contract in the module docstring:
  10-K entries only; `(start, end)` collapsed to the **earliest-filed**
  entry, which is the as-reported figure; six most recent **annual**
  durations (≥ 350 days) **plus** six most recent other periods, per tag
  per unit; output `sort_keys` and byte-stable. Say that the two-band
  rule exists because a single "six most recent" band lets quarterly
  comparatives evict the annual periods.

**Done when** `python3 -m pytest tests/test_m3_snapshot.py -q -rx` exits
0 and the printed table is copied into the report; the docstring names
all four rules; `python3 -m pytest -q` exits 0.

---

### Y4. Remove the escape hatch

`origin/main` now carries the `total_equity_incl_nci` row in
`docs/data-dictionary.md` §2. The `RULED_BEYOND_DICTIONARY` exception in
the V0 doc-guard has done its job and must go — a guard with a
permanent exemption list guards nothing.

- Delete `RULED_BEYOND_DICTIONARY` and restore the assertion to
  `assert not missing`.
- Keep the extra assertions you added around it if they are still true;
  the guard should come out of this **stronger** than it went in, per P1.

**Done when** `grep -rn RULED_BEYOND_DICTIONARY tests/ rusterm/` is
empty and `python3 -m pytest tests/test_concept_map.py -q` exits 0.

---

### Y5. `ingest --source edgar` makes one request it throws away

In `_ingest_edgar_companyfacts` (`rusterm/cli/__init__.py`):

```python
provider.resolve(ref.get("ticker", ""), "US", as_of)  # греет карту
```

The CIK is already known — it came from `issuer.registry_id` four lines
above, and `provider.cik` is set from it. This call fetches the whole
ticker map, discards the result, and costs one request per run for
nothing. §1.12 counts every request; the budget table in
`docs/processes.md` is built on measured costs.

Delete the line. If something downstream depends on the map being warm,
the test will say so — and then the fix is to say *that* in a comment,
not to keep an unexplained fetch.

**Done when** a test asserts that `ingest --source edgar` for an issuer
with a known CIK makes **exactly one** request (`gate.calls_made == 1`);
`python3 -m pytest -q` exits 0.

---

### Y6. `## Disputed` becomes a machine check

Three tasks have asked in prose (§0.3). Make it checkable instead.

Add `tests/test_report_sections.py`, which reads the report file named by
`agent/STATE.json` `"report"` and asserts:

- every one of `## Done`, `## Blocked`, `## What not to trust`,
  `## Disputed`, `## HANDOFF` is present;
- **no line outside the `## Disputed` section starts with `DISPUTED`**
  (case-insensitive, after stripping list markers) — if you want to flag
  a dispute inline, the entry goes in the section and the bullet points
  at it;
- the `## HANDOFF` block contains no line still carrying the template
  placeholders `N passed`, `M skipped` or `<`.

The test must pass on an empty `## Disputed` — a night with no
disagreements is legitimate. It is the *misplaced* dispute it catches.

**Done when** the test exists, passes at the end of the night, and fails
if you paste a `DISPUTED:` line into a `Done` bullet (check that by
pasting one, watching it go red, and removing it);
`python3 -m pytest -q` exits 0.

---

### Y7. The tail of the backlog

`agent/BACKLOG.md`, top down, reporting each pulled item by its ID.
B12, B13, B15, B17, B18, B19 are pre-approved and still open. B9, B10,
B11, B16 were closed by TASK-11 X5 — mark them done in the file if the
merge has not already.

---

### Y8. The bookkeeping

`agent/STATE.json` naming this task and this report, real
`net_requests`, ending at `"status": "awaiting_review"`; `## HANDOFF`
filled with real values — **including `Real numbers`, which
`agent/REPORT-11.md` handed over as "19 of 20" when the measured answer
under the new payloads was 20 of 20**; `agent/ACCEPTANCE-10.txt` taken
at the head you hand over.

You got the state file and the acceptance log right last night, after
three tasks of getting them wrong. Keep it.

**Done when** Y6's test passes, `agent/ACCEPTANCE-10.txt` is non-empty
and its `HEAD:` line is the commit before the final `agent/` commit, and
`python3 -c "import json;d=json.load(open('agent/STATE.json'));assert d['task']=='agent/TASK-12.md' and d['status']=='awaiting_review'"` succeeds.

---

### Y9. Queue empty

All of Y1–Y8 done before 09:30 — take `agent/TASK-13.md`, which is
`Status: READY` and waits for no review of this one. Do not invent work
beyond it and the backlog.

---

## 3. Night end — you run the final acceptance yourself

```bash
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-10.txt
git add agent/ACCEPTANCE-10.txt agent/REPORT-12.md agent/STATE.json
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      Y1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-10.txt)
Tests:           N passed, M skipped, K xfailed
Measure table:   the printed table from Y3, verbatim
Period mismatch: N remaining, and which issuer/measure pairs
Concept map:     version = …; payloads re-trimmed yes/no
Strict xfail:    still xfail / went red with these numbers
Milestones:      M3-with-the-formula-set yes/no, M5 yes/no
Network:         RUSTERM_SEC_UA set? — N requests, M refused, K rate-limited
Model:           app LLM calls N; your own model id and call count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

In scope now, new since TASK-10: two named source tags, an eligibility
rule for stale facts, and the paperwork the last two nights owed.

Out of scope tonight, no exceptions for spare time:

- Qt or any GUI — acceptance check 6 forbids it, the TUI is the answer
- price vendors, and therefore every measure in `_UNMAPPED_FORMULAS`
  that needs a price
- IFRS, UK and CA providers (M6), Industry View (M7)
- industry metrics beyond Maritime/Tanker
- a second taxonomy beside `us-gaap`
- `total_debt`, `invested_capital` and any other composite concept
- any source tag not named in Y1's two-row table
- renaming a `--json` key, an exit code or a flag (§0.2 ruling 4)
- refactoring green code that no item names

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
Sixteen of seventeen disputes raised so far were upheld against the
coordinator.
