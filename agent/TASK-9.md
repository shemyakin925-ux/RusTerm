# TASK-9 — the numbers on the screen become real numbers

- **Status: ACCEPTED** — verified by the coordinator on a clean detached
  checkout at `cf1919b`: 13/13, 273 passed, 2 skipped, `net_margin`
  20/20. Defects found in review are items of `agent/TASK-10.md`
  (W0, W3, W4, W8), not a reason to reopen this file.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-9.md`
- **Supersedes:** TASK-8 (**ACCEPTED**, all of U0–U12 done, 13/13 on a
  clean checkout). Do not reopen it.
- **Goal of the night, in one sentence:** twenty real US issuers come out
  of `snapshot` with **values**, not with three nulls each — the
  us-gaap tag on the wire is mapped to the concept the formulas expect,
  the inputs of one measure come from **one** period, and the measure
  carries that period instead of today's date.

You are an autonomous coding agent with the same tools as the
coordinator: shell, file editing, test runs, network. This file gives
contracts, decisions and acceptance commands, not tutorials. Anything
readable from the repository, read from the repository.

No coordinator is online during the run. Every fork below is closed by a
deterministic rule. Where a rule is wrong, follow it and put the
objection in **Disputed** — that channel works: ten of ten disputes have
been upheld or answered so far, three of them last night.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git merge origin/main          # brings TASK-9, LAUNCH, BACKLOG, docs fix
bash agent/acceptance.sh
```

The last command must print `Итог: пройдено 13, провалено 0`. The
coordinator ran exactly this on a clean detached checkout of
`agent/night-2` at `8c2f5b5` and got 13/13 with
`251 passed, 1 skipped`. Anything else means your environment differs —
record the full output as the first entry in `agent/REPORT-9.md` and
continue. Do not "fix" acceptance.

**The merge is not optional and comes first.** `origin/main` carries an
amendment to `docs/processes.md` §«Бюджет запросов» (the ruling in §0.2,
dispute 2). Run acceptance *before* merging and check 10 goes red — it
compares `docs/` against `origin/main` and sees the branch lagging. That
is the expected state of an unmerged branch, not a defect and not
something to work around: merge, then run acceptance, then start V0.

The merge may conflict in `agent/LAUNCH.md` — the coordinator's file,
never yours. Take main's version verbatim:

```bash
git checkout --theirs agent/LAUNCH.md && git add agent/ && git commit --no-edit
```

Then read, in full and from the repository, the files you will touch:
`rusterm/normalize/__init__.py`, `rusterm/parsers/__init__.py`,
`rusterm/core/snapshot.py`, `rusterm/formulas.py`,
`rusterm/store/repos.py`, `rusterm/store/db.py`, `rusterm/pipeline.py`,
`rusterm/tui/model.py`, `docs/data-dictionary.md`.
The recurring failure in this repo is editing a file from a remembered
shape instead of its current one.

---

## 0.1. Where the project stands — verified, not reported

The coordinator re-ran everything on a clean detached checkout at
`8c2f5b5`. These are facts, not claims from a report:

| Check | Result |
|---|---|
| `bash agent/acceptance.sh` | **13/13**, `Принято` |
| `python3 -m pytest` | **251 passed, 1 skipped**, 0 xfail |
| `git diff origin/main HEAD -- rusterm/ tests/ \| grep -c '^-.*assert'` | **0** — no assertion deleted |
| `git diff origin/main HEAD -- rusterm/store/db.py \| grep '^-'` | **empty** — no applied migration edited |
| `grep -rn 'US-CLI-DEMO' rusterm/` | one constant, used only by `cmd_demo` |
| `grep -rnE 'execute\(\|httpx\|requests' rusterm/tui/` | empty |
| `git ls-remote origin refs/heads/agent/night-2` | pushed by the coordinator to `8c2f5b5` |

U0's guard was re-read on the shipped code: `_citations_for` is now
multiset containment over whole numeric tokens, the three probe texts
are rejected, and `tests/test_llm_guard.py` carries `test_u0_*` for each
case. The defect TASK-8 existed to close is closed.

M2's golden file is real: `AAPL FY2021 revenue = 365 817 000 000` from
`accn 0000320193-21-000105` matches the filing. 125 rows, each with
`accn`, `filed`, `source_url` and a `json_pointer`.

| Layer | State |
|---|---|
| store, migrations, WAL, writer lock, repositories | done |
| facts, locators, basis rule, XBRL + table + **companyfacts** parsers | done |
| EDGAR provider through an **enforced** `RequestGate` | done |
| pipeline, idempotency, coverage (8 blocks), verification + recompute | done |
| formulas (the whole `docs/data-dictionary.md` §3 set) | **written, mostly never called — V4** |
| snapshot | done, **three measures only, all null on real data — V0/V1/V2** |
| watchlist, export, governance, Maritime metrics, system metrics | done |
| LLM guard rail | done and tight |
| CLI: install, `status`, `demo`, selectors, `--json`, exit codes | done, **no way to create a real instrument — V3** |
| TUI on `curses`, read-only, model split out and tested | done |
| M1, **M2 (5×5 golden)**, **M3 (20 issuers, one pass)** | reached |
| M5 | **not started — needs a key, V7** |

**Two things are still not true.** First: M3 is twenty issuers whose
snapshots are twenty rows of `null`. `tests/test_m3_snapshot.py` asserts
snapshots exist, coverage rows exist and reasons are non-empty — it
never asserts a single measure carries a value, so an all-null result
passes as green. Second: no command creates an instrument for a real
company, so only a test can reach any of this; a person at a terminal
cannot. Those two are what this night is for.

---

## 0.2. Rulings on TASK-8 disputes. All five answered

1. **§1.9 stop time, day session started 09:39.** Accepted. §1.9 bounds
   the scheduled night run; a session the coordinator starts by hand
   runs until its work is done. No change.
2. **U8: 1 request per issuer measured against ~6 estimated in
   `docs/processes.md`.** Upheld — and it is more than 2×, so it was
   right to dispute. The coordinator has amended the budget table on
   `origin/main`: the `companyfacts` path is now named with its measured
   cost. You could not have fixed it yourself (check 10 forbids editing
   `docs/`); reporting it was the correct move.
3. **us-gaap concepts are not mapped to the dictionary's names, so base
   measures stay null on real data.** Upheld, and it is the largest
   finding of the night — found by you, not by the acceptance script.
   It becomes V0 below, the top of this task. Three further defects sit
   behind it that the report did not name — V1, V2 and V3, the last of
   them found while the coordinator was checking the user-facing path.
4. **CLI `verify` flags removed.** Sanctioned by TASK-8's own contract.
   No dispute.
5. **The empty-report incident, self-reported with a root cause and
   three new personal rules.** Accepted, and the rules are folded into
   §1.7 below as project rules. Self-reporting a silent data loss that
   the acceptance script cannot see is worth more than the loss cost.
   Nothing is held against the run for it.

**One §3 item was missed and is not disputed, just absent:**
`agent/REPORT-8.md` has no `## HANDOFF` section, and
`agent/ACCEPTANCE-6.txt` was recorded at `320f81b`, two commits before
the branch head. Neither changed a verdict — the coordinator re-ran
acceptance at the head — but §3 of this file is now checked as an item,
not as a convention. See V8.

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
8. RECORD   one line in agent/REPORT-9.md: command + its output (§1.7).
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

### 1.7. Bookkeeping — and the rule that comes out of last night

`agent/REPORT-9.md` is **append-only and verified after every write.**
The empty-report incident cost a whole night's history. Three rules,
now project rules and not personal ones:

- **R1.** Never open the report with a truncating mode. Append only:
  `printf '%s\n' "…" >> agent/REPORT-9.md`, or a quoted heredoc with
  `>>`. Never `>`, never `open(p, "w")` on it.
- **R2.** After every append, run
  `wc -c agent/REPORT-9.md && tail -3 agent/REPORT-9.md` and look at the
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
{"task": "agent/TASK-9.md", "report": "agent/REPORT-9.md",
 "item": "V1", "step": "4", "status": "working",
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
`agent/REPORT-9.md`, keep committing locally, and at the end produce
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
shape and is small. That exception is what V5 uses.

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

Strictly in order. Do not start an item before the previous one is
committed and pushed.

Ordering rationale, so you can judge a trade-off the same way: V0–V2 are
what turn twenty null snapshots into twenty snapshots with numbers, and
every one of them works **offline on the payloads already in git** — a
night that ends after V2 has already delivered the point of the task.
V3 is what lets a person, not a test, put a real company in; it is small
and it is also offline. V4 widens the measure set over the same inputs.
V5 needs network and extends the mapping's reach; V6 makes the mapping
visible to the user; V7 needs a key and may not run at all; V8 is the
bookkeeping the last night missed.

---

### V0. The us-gaap mapping layer — a tag on the wire becomes a concept

**The defect, in one run.** `CompanyFactsParser` writes facts whose
`concept` is the source tag verbatim: `us-gaap:Revenues`,
`us-gaap:NetIncomeLoss`. `SnapshotBuilder._issuer_inputs` asks
`SnapshotRepo.as_reported_facts` for `("net_income", "revenue",
"operating_income", "tax_expense", "pretax_income")`. The two
vocabularies never meet, so every base measure on real data is `null`
with `missing_data` while the fact table is full. You found this and
reported it; here is how it gets closed.

**Design, decided here.**

1. **The fact keeps its source tag.** `fact.concept` is never rewritten —
   the locator must resolve back to the document, and a rewritten tag
   makes lineage a lie.
2. **Migration 36** adds to `fact`: `canonical_concept TEXT NULL` and
   `concept_map_version TEXT NULL`. Nullable, so existing rows stay
   valid; `_SCHEMA_VERSION` → 36.
3. **One module, `rusterm/normalize/concepts.py`** (the package exists
   and is empty). It holds the table below and nothing else — no SQL, no
   network, no formulas. `CONCEPT_MAP_VERSION = "us-gaap.v1"`.
4. **The pipeline fills the two columns at ingest**, from the module.
   A tag not in the table maps to `NULL` and is **counted**, not
   dropped: the ingest result reports `неотображённых концептов: N`.
5. **`as_reported_facts` queries `canonical_concept`**, not `concept`.
   Its docstring says so.

**The table. Authoritative — do not extend it, do not reorder it, do not
invent a tag.** Left column is `docs/data-dictionary.md` §2 verbatim.
Right column is us-gaap local names in **priority order**: the first tag
that has a fact for that issuer/period/unit wins.

| concept | us-gaap tags, first wins |
|---|---|
| `revenue` | `RevenueFromContractWithCustomerExcludingAssessedTax`, `RevenueFromContractWithCustomerIncludingAssessedTax`, `Revenues`, `SalesRevenueNet` |
| `cogs` | `CostOfGoodsAndServicesSold`, `CostOfRevenue`, `CostOfGoodsSold` |
| `gross_profit` | `GrossProfit` |
| `opex` | `OperatingExpenses` |
| `operating_income` | `OperatingIncomeLoss` |
| `d_and_a` | `DepreciationDepletionAndAmortization`, `DepreciationAmortizationAndAccretionNet`, `DepreciationAndAmortization` |
| `net_income` | `NetIncomeLoss`, `ProfitLoss` |
| `pretax_income` | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest`, `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments` |
| `tax_expense` | `IncomeTaxExpenseBenefit` |
| `interest_expense` | `InterestExpense`, `InterestExpenseDebt` |
| `eps_diluted` | `EarningsPerShareDiluted` |
| `shares_diluted` | `WeightedAverageNumberOfDilutedSharesOutstanding` |
| `ocf` | `NetCashProvidedByUsedInOperatingActivities`, `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` |
| `capex` | `PaymentsToAcquirePropertyPlantAndEquipment` |
| `cash` | `CashAndCashEquivalentsAtCarryingValue` |
| `st_investments` | `ShortTermInvestments` |
| `total_assets` | `Assets` |
| `total_equity` | `StockholdersEquity` |
| `minority_interest` | `MinorityInterest` |
| `preferred_equity` | `PreferredStockValue` |
| `dps` | `CommonStockDividendsPerShareDeclared` |
| `buyback_amount` | `PaymentsForRepurchaseOfCommonStock` |

**Four hard rules on the mapping.**

- **Never sum two tags** into one concept. First present wins, full stop.
- **Never cross units.** A USD tag never satisfies a `shares` concept.
- `total_debt`, `shares_outstanding`, `price_close`, `price_adj` are
  **deliberately absent**: the first is a composite the dictionary
  defines from several tags, the rest are `scope=instrument`, not
  issuer. Leaving them unmapped is the correct answer tonight, not an
  omission. Do not improvise them.
- The tag that actually won is not thrown away: it stays in
  `fact.concept`, which V6 puts on the screen.

**Done when** `tests/test_concept_map.py` asserts: every left-column name
in the table above exists in `docs/data-dictionary.md` §2 and the guard
fails if a name drifts (parse the doc, compare both ways, B7 style); a
tag outside the table maps to `None`; priority is respected when two
tags of one concept are both present (a fixture with `Revenues` and
`RevenueFromContractWithCustomerExcludingAssessedTax` yields the latter);
`grep -rnE 'execute\(|httpx|requests' rusterm/normalize/` is empty;
and a test over the committed `tests/data/edgar/companyfacts_m2_AAPL.json`
asserts at least `revenue`, `net_income`, `total_assets`, `total_equity`
and `ocf` come out of ingest with a non-null `canonical_concept`.
`python3 -m pytest -q` exits 0 and acceptance stays 13/13.

---

### V1. One measure, one period — stop dividing 2025 by 2021

`SnapshotBuilder._issuer_inputs` takes, per concept, the **first** row of
`as_reported_facts`, which is ordered `period_end DESC, ingested_at DESC`
across all periods. On the synthetic single-period demo that is
harmless. On five years of real `companyfacts` it silently divides one
year's `net_income` by another year's `revenue` whenever the two
concepts have different latest periods — which happens routinely,
because different tags stop and start in different filings.

The fix, decided here:

- For each measure in `_BASE_MEASURES`, choose the **latest `period_end`
  for which every input of that measure exists** with the same `unit`
  and `basis='as_reported'`. Duration and instant inputs match on
  `period_end`; a `duration` input additionally requires the same
  `period_start`.
- No such period → the measure is `null` with the new null-reason
  **`period_mismatch`**, distinct from `missing_data` (which stays for
  "the concept is absent entirely"). Both reasons are shown, never
  merged.
- `as_reported_facts` returns `unit`, `period_start` and `period_end`
  alongside what it returns today, so the selection can be made without
  a second query and without SQL leaving `rusterm/store/`.
- Lineage still names the `fact_id` of each input — now provably of one
  period.

**Done when** a test seeds one issuer with `revenue` for FY2023 and
FY2024 and `net_income` for FY2023 only, and asserts `net_margin` is
computed **on FY2023** (not 2024/2023) and carries FY2023's period; a
test with no overlapping period at all asserts `null_reason ==
"period_mismatch"`; a test asserts a concept absent entirely still gives
`missing_data`; `python3 -m pytest -q` exits 0.

---

### V2. A measure carries its own period and its own unit

`insert_measure_with_lineage` is called with `period_start=""`,
`period_end=as_of`, `unit="ratio"` — hardcoded. So a margin computed
from FY2023 is stamped with today's date, and the `unit` is `ratio` even
for measures that are money. `docs/data-dictionary.md` §1.2 requires the
period used to be stated next to the number; the TUI and the export
print what the measure carries.

- The measure's `period_start` / `period_end` are those of the inputs
  chosen in V1. A measure with no inputs keeps `as_of` and says so via
  its null-reason — an empty period string is never written again.
- `unit` comes from the formula, not from the call site: ratios are
  `ratio`, money keeps the inputs' currency, per-share keeps
  `<currency>/share`, counts are `шт.`. One table, in `rusterm/formulas.py`
  next to the formulas, since that is where the definition lives.

**Done when** a test asserts a computed `net_margin` carries the input
facts' `period_start`/`period_end` and `unit == "ratio"`; a test asserts
a money-valued measure carries the currency, not `ratio`; a test asserts
no measure row is ever written with an empty `period_start`;
`python3 -m pytest -q` exits 0.

---

### V3. A user cannot put a real company into the database at all

Run by the coordinator on a fresh database, on the shipped code:

```
$ rusterm ingest --ticker AAPL --market US --source edgar
тикер 'AAPL' на 'US' не разрешён ни в один инструмент;
проверьте тикер или добавьте инструмент
$ rusterm watchlist add my --ticker AAPL --market US
error: the following arguments are required: --instrument
```

The message names an action the program does not offer. `demo` is the
only command in the whole CLI that ever creates an instrument, and it
creates the synthetic one. TASK-8 U3 correctly removed the hard-wired
demo from `ingest`/`snapshot`/`export`, but nothing took its place, so
the user may now *select* an instrument they have no way to *create*.
The M2 and M3 tests create theirs in Python; a person at a terminal
cannot. This is the last thing between the program and being usable.

Everything needed already exists in `InstrumentRepo`: `upsert_issuer`,
`upsert_instrument`, `upsert_listing`, `add_ticker_history`. This item
composes them behind one command; it writes no new SQL.

| Command | Contract |
|---|---|
| `rusterm add --ticker T --market M [--cik N] [--name NAME] [--instrument-id ID] [--class CLASS]` | **new**: creates issuer + instrument + listing + ticker history so that `--ticker T --market M` resolves afterwards |

Rules, all decided here:

- With `RUSTERM_SEC_UA` available, `--cik` and `--name` are resolved
  through the EDGAR ticker map already implemented in
  `rusterm/providers/edgar.py` — one cached request for all tickers, not
  one per company. Without it, `--cik` and `--name` are **required** and
  the command works fully offline; a missing one exits 1 naming it.
- `--instrument-id` defaults to `<MARKET>-<TICKER>`; `--class` defaults
  to `common`. One issuer may carry several instruments, one per share
  class — that is `docs/data-model.md` §4 and it is not negotiable.
- **Idempotent.** `add` twice for the same ticker creates one issuer and
  one instrument, exits 0, and says the instrument already exists. It
  never creates a second issuer for the same CIK.
- `watchlist add` gains `--ticker T --market M` beside `--instrument`,
  resolving through `InstrumentRepo.resolve_ticker_candidates`. **No
  second resolver**; ambiguity exits 1 listing the candidates, exactly
  as `ingest` does.
- The unresolved-ticker message stops naming a nonexistent action: it
  names `rusterm add --ticker T --market M`.
- `_ensure_demo_instrument` gains the listing and ticker-history rows it
  never wrote, so `--ticker` works for the demo issuer too.
- README «Быстрый старт» gains the real-company path, and every command
  in it is run by you before it goes in (U10's rule, unchanged).

**Done when** a test on a fresh database asserts
`add --ticker AAPL --market US --cik 320193 --name "Apple Inc."` exits 0
and that `ingest --ticker AAPL --market US` then resolves to exactly one
instrument; a test asserts running `add` twice leaves one issuer and one
instrument and exits 0; a test asserts `watchlist add my --ticker AAPL
--market US` adds the member; a test asserts `add` with no contact and
no `--cik` exits 1 with a message naming `--cik`; a test asserts the
unresolved-ticker message contains `rusterm add`; a test asserts two
share classes of one issuer land as two instruments;
`python3 -m pytest -q` exits 0 and acceptance stays 13/13.

---

### V4. Compute the formulas that are already written

`rusterm/formulas.py` implements the whole `docs/data-dictionary.md` §3
set. `_BASE_MEASURES` calls three of them. Everything else — `ebitda`,
`gross_margin`, `roe`, `asset_turnover`, `nopat` — is dead code that the
acceptance script cannot see, because nothing ever asks for it.

Extend `_BASE_MEASURES` to every §3 formula whose inputs are `issuer`
scope and whose concepts are in the V0 table. Rules:

- **The dictionary is the source; do not invent a formula and do not
  change one.** A formula whose inputs are not in the V0 table is
  registered with a permanent null-reason `concept_not_mapped`, not
  omitted — the user must see that the row exists and why it is empty.
- Two-period formulas (`roe`, `asset_turnover` need beginning and ending
  balance) take the chosen period's end and the immediately preceding
  period's end for the same concept; no preceding period → `null` with
  `missing_prior_period`.
- `effective_tax`'s `clip(…, 0, 0.5)` and the `pretax_income <= 0`
  branch stay exactly as `docs/data-dictionary.md` §3 states. If the
  jurisdiction rate table does not exist, the value is `null` with
  `no_jurisdiction_rate` — do not invent a rate.
- No user-facing count conflates written with known: the `snapshot` line
  keeps TASK-8's `мер: N — со значением K, пусто M` shape.

**Done when** a test over the committed AAPL payload asserts at least
`net_margin` and one balance-sheet-derived measure compute to non-null
values with the right period; a test asserts every §3 formula name
appears in the snapshot's measure rows for an issuer, each either with a
value or with a null-reason from the fixed set; a test asserts no
measure is silently absent; `python3 -m pytest -q` exits 0.

---

### V5. **M3 for real** — twenty issuers with numbers, and the payloads to prove it

Skip the network half **entirely** if `RUSTERM_SEC_UA` is unset — record
`SEC_UA UNSET — payload refresh not exercised` and do the offline half
only. Do not simulate it.

The 21 committed payloads under `tests/data/edgar/` were trimmed to the
five M2 concepts. The coordinator checked what is in them:

```
20  us-gaap:NetIncomeLoss          5  us-gaap:Assets
17  us-gaap:Revenues               5  us-gaap:NetCashProvidedByUsedInOperatingActivities
14  us-gaap:RevenueFromContract…   4  us-gaap:StockholdersEquity
 6  us-gaap:SalesRevenueNet        1  us-gaap:StockholdersEquityIncluding…
```

`OperatingIncomeLoss`, `IncomeTaxExpenseBenefit` and the pretax tags are
in **none** of them, so V4's measure set cannot be exercised on real
data until the payloads carry them.

- Re-fetch `companyfacts` for the twenty M3 issuers (**one request per
  issuer**, the measured cost — §0.2 dispute 2) and re-trim keeping
  **every tag named in the V0 table** plus what M2's golden file already
  points at. Keep the files small: drop units you do not use, and keep
  at most the six most recent annual entries per tag.
- M2's golden file must keep resolving: every `json_pointer` in
  `tests/data/golden_m2.json` still lands on its value after the
  re-trim. If a pointer moves because entries were dropped, **the
  pointer is updated and the expected value is not touched.** An expected
  value that changes is a red flag, not a fix — stop and report it.
- Then strengthen `tests/test_m3_snapshot.py`: it must assert that
  **at least 15 of the 20 issuers** have a non-null `net_margin` with a
  real period, and that every remaining null carries a reason from the
  fixed set. The current test passes on twenty empty snapshots; that is
  the hole this closes.
- The report carries
  `M3v2: 20 issuers, N requests, K issuers with non-null net_margin, M nulls by reason`.

**Done when** `python3 -m pytest tests/test_m2_golden.py
tests/test_m3_snapshot.py -q` exits 0 with the strengthened assertions,
`du -sh tests/data/edgar/` stays under 1 MB, `net_requests` in
`STATE.json` reflects the real count, and `python3 -m pytest -q` exits 0.

---

### V6. The user can see which tag became which number

A mapping the user cannot inspect is a mapping they cannot trust. Every
place a number is shown with its lineage already exists — extend it, do
not build a second one.

- `rusterm/tui/model.py` `source_panel` adds two lines for each input
  fact: the source tag (`fact.concept`, e.g. `us-gaap:Revenues`) and
  `concept_map_version`. Alongside the document and the locator it
  already shows.
- `rusterm coverage --json` and `rusterm status --json` gain a
  `concept_map_version` field so a scripted consumer can tell two
  mappings apart.
- `rusterm doctor` reports the count of facts with a `NULL`
  `canonical_concept` and the five most frequent unmapped tags, by name
  and count. This is how the next mapping gap gets found without reading
  code.

**Done when** `tests/test_tui_model.py` asserts the source panel names
the source tag and the map version for a measure built from a mapped
fact; a test asserts `doctor` lists an unmapped tag with its count and
does not crash when there are none; `--json` output still parses with
`json.loads`; `python3 -m pytest -q` exits 0.

---

### V7. **M5** — the real model behind the guard rail

Skip **entirely** if `RUSTERM_LLM_API_KEY` is unset after the U4 env
load — record `LLM key unset — M5 not exercised` and go to V8. Check
with `rusterm doctor`, which reports origin without printing values. Do
not simulate a model, do not stub a key, do not "demonstrate" the path
with the fake client and call the milestone reached.

The contract is TASK-7 T16 and it has not changed:

- Provider and key from `RUSTERM_LLM_PROVIDER` / `RUSTERM_LLM_API_KEY`.
- HTTP lives in `rusterm/providers/` and nowhere else (acceptance 8).
- Hard ceiling **50 calls for the night**, counted in `"llm_calls"`,
  refusing past it. This item needs **at most 2**.
- The key never appears in a commit, a log, a report, a test, or in a
  `prompt_hash` input.
- The model gets **read-only tools only** (`docs/watchlist-and-llm.md`
  §2.4): `resolve_ticker`, `list_industry_instruments`, `get_peer_set`,
  `get_snapshot_block`. Not one state-changing tool.
- **No bulk operation executes.** Nobody is awake to confirm, and §2.3
  requires confirmation of the shown list. Dry-run only: produce the
  list with each row marked (will be added / excluded by filter /
  already present / unresolved) and stop. §2.5 forbids showing a time
  estimate.
- Model self-assessed `confidence` is logged and **never** branched on.
- The guard rail of U0 applies unchanged to real output. A real model
  that invents a number gets its whole text rejected, and that rejection
  is a **success** of this item, not a failure — report it as one.

**Done when** `tests/test_llm_real.py` skips cleanly with no key and,
with a key, makes at most 2 calls and asserts every numeric statement
carries a citation and that a dry-run mass operation executes nothing;
`python3 -m pytest -q` exits 0.

---

### V8. The bookkeeping §3 asked for and did not get

Not a code item. Do it, and do it in the order written:

- `agent/REPORT-9.md` carries a filled `## HANDOFF` section, from the §3
  template, with no heading deleted.
- `agent/ACCEPTANCE-7.txt` is produced from the **branch head you are
  about to hand over**, not from an earlier commit. Concretely: make the
  final acceptance run the last thing before the final commit, and let
  that commit contain only `agent/`.
- `agent/STATE.json` ends at `"status": "awaiting_review"`.

**Done when** `test -s agent/REPORT-9.md && grep -q '^## HANDOFF'
agent/REPORT-9.md` succeeds, `agent/ACCEPTANCE-7.txt` is non-empty and
its `HEAD:` line matches the commit that precedes the final `agent/`
commit, and `python3 -c "import json;json.load(open('agent/STATE.json'))"`
succeeds.

---

### V9. Queue empty

All of V0–V8 done before 09:30 — take `agent/BACKLOG.md` top down. Do
not invent work beyond it.

---

## 3. Night end — you run the final acceptance yourself

```bash
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-7.txt
git add agent/ACCEPTANCE-7.txt agent/REPORT-9.md agent/STATE.json
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

A night whose acceptance log is missing is reviewed as if it printed
zero. A night whose log was taken from an earlier commit is reviewed at
the head anyway — see V8.

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      V0, V1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-7.txt)
Tests:           N passed, M skipped, K xfailed
Real numbers:    issuers with a non-null net_margin: N of 20
Unmapped tags:   top 5 by count, from `rusterm doctor`
Milestones:      M3-with-values yes/no, M5 yes/no
Network:         RUSTERM_SEC_UA set? — N requests, M refused, K rate-limited
Model:           app LLM calls N; your own model id and call count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

In scope now, new since TASK-8: the mapping from source tags to the
project's own vocabulary, correct periods on measures, the formula set
the dictionary already defines, and M3 proved with values instead of
with row counts.

Out of scope tonight, no exceptions for spare time:

- Qt or any GUI — acceptance check 6 forbids it, the TUI is the answer
- price vendors (ADR-0008 proposes; the user decides)
- IFRS, UK and CA providers (M6), Industry View (M7)
- industry metrics beyond Maritime/Tanker
- a second taxonomy beside `us-gaap` — `ifrs-full` waits for M6
- `total_debt` and any other composite concept not in the V0 table
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
answered, and eight of ten were upheld against the coordinator.
