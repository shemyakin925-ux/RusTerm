# TASK-18 — Канада и OTC: рынок становится величиной, а не строкой

- **Status: READY** — take it when `agent/TASK-17.md` is finished and
  handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-18.md`
- **Depends on nothing in TASK-14…17.**
- **Goal of the night, in one sentence:** a market stops being a string
  passed to `--market` and becomes a table the program reads — Canada and
  the US OTC venue are its first two new rows, three Canadian issuers get
  the full measure set through a second tag dictionary, and adding the
  next market after the MVP costs one registry entry, not a rewrite.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git merge origin/main
bash agent/acceptance.sh
printenv RUSTERM_SEC_UA | cut -c1-12
```

Acceptance must print `Итог: пройдено 13, провалено 0`.

**This night needs the network** — it is the only task in the queue that
does. Without `RUSTERM_SEC_UA`: do G1, G3, G4 and G5 (all offline), write
`SEC_UA UNSET — payloads not recorded` in `## Blocked`, and skip the
items that record payloads. Do not simulate a payload and do not
hand-write one.

Read, in full and from the repository: `rusterm/normalize/concepts.py`,
`rusterm/parsers/__init__.py`, `rusterm/pipeline.py`,
`rusterm/providers/edgar.py`, `rusterm/cli/__init__.py`,
`tools/trim_companyfacts.py`, `tests/data/golden_m2.json`,
`rusterm/reasons.py`.

---

## 0.1. The decisions behind this task, and what was measured

The user decided four things, and they are not open for re-litigation:

1. **The UK is not needed.** It is dropped from the milestone; no UK
   issuer, no Companies House, no NSM.
2. **Canada is wanted**, and a **second taxonomy** (`ifrs-full`) is
   authorised beside `us-gaap`.
3. **The OTC venue is wanted.**
4. **The architecture must let a new market be added after the MVP** —
   that is G1 and it is the item with the longest life.

The source stays **SEC EDGAR only**. The coordinator checked the live
feed before writing this; every line below is measured, not assumed:

| what | result |
|---|---|
| `company_tickers_exchange.json` | 10 407 tickers with an `exchange` field: Nasdaq 4363, NYSE 3298, **OTC 2500**, CBOE 36, none 210 |
| Royal Bank of Canada, CIK 1000275 | `ifrs-full`, 298 tags, to **2026-01-31** |
| Bank of Montreal, CIK 927971 | `ifrs-full`, 278 tags, to **2026-01-31** |
| Canadian Natural, CIK 1017413 | `ifrs-full`, 179 tags, to **2026-03-04** |
| TC Energy, Barrick, CN Railway | **`us-gaap`** — Canadian issuers reporting under US GAAP; they need no new dictionary at all |
| `NGGTF` (OTC) | `ifrs-full`, 420 tags, to 2026-03-31 — an OTC-traded issuer with full XBRL |
| `CPTP`, `HWKE` (OTC) | `us-gaap`, current — ordinary US OTC filers |
| `TRUFF` (OTC, Canadian) | **HTTP 404 — no `companyfacts` at all** |

Two facts follow, and they shape the night:

- **OTC is not one thing.** 2500 SEC-reporting tickers trade there and
  have full XBRL. Others — typically foreign issuers exempt under Rule
  12g3-2(b) — file nothing with the SEC and return 404. The program must
  serve the first group and say the honest thing about the second. That
  is G5, and it is more important than any measure count.
- **Canada is not one thing either.** Half the MJDS filers report under
  IFRS and half under US GAAP. The taxonomy is a property of the payload,
  never of the market string.

**ADRs and per-share measures stay out.** The ratio between a depositary
receipt and an ordinary share is modelled nowhere in this project, and
`docs/` does not contain the word. No per-share measure, EPS or market
capitalisation is computed or asserted for a non-US issuer tonight.
Changing that is a coordination decision, not a task item.

---

## 0.2. The IFRS map. Named by the coordinator from the live feed

The rule from TASK-12 holds and is why this table exists: **the map is
extended by named decision, never by substring search.** Every tag was
checked against Royal Bank, BP and AstraZeneca's payloads; Bank of
Montreal and Canadian Natural carry the same core tags.

`CONCEPT_MAP_IFRS`, priority left to right:

| concept | tags, in priority order |
|---|---|
| `revenue` | `Revenue`, `RevenueFromContractsWithCustomers` |
| `net_income` | `ProfitLossAttributableToOwnersOfParent`, `ProfitLoss` |
| `operating_income` | `ProfitLossFromOperatingActivities` |
| `gross_profit` | `GrossProfit` |
| `pretax_income` | `ProfitLossBeforeTax` |
| `income_tax` | `IncomeTaxExpenseContinuingOperations` |
| `d_and_a` | `DepreciationAndAmortisationExpense`, `AdjustmentsForDepreciationAndAmortisationExpense` |
| `total_assets` | `Assets` |
| `total_liabilities` | `Liabilities` |
| `total_equity` | `EquityAttributableToOwnersOfParent` |
| `total_equity_incl_nci` | `Equity` |
| `cash` | `CashAndCashEquivalents` |
| `ocf` | `CashFlowsFromUsedInOperatingActivities` |
| `capex` | `PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` |
| `interest_expense` | `FinanceCosts` |
| `shares_diluted` | `AdjustedWeightedAverageShares` |

`st_investments` gets **no** IFRS tag: what issuers file under that idea
(`OtherCurrentFinancialAssets`, `CurrentInvestments`) does not mean the
same thing across them.

**Forbidden lookalikes.** Each exists in the feed, looks right by
substring, and would produce a **wrong number** where there is now an
honest gap. A test asserts every one maps to `None`:

| tag | why not |
|---|---|
| `RevenueFromInterest`, `InsuranceRevenue`, `OtherRevenue` | components of revenue, not revenue |
| `AccountingProfit` | the base of the tax reconciliation, not pre-tax profit |
| `CurrentTaxExpenseIncome` | current tax only; the total is current + deferred |
| `DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss` | includes impairment — a different quantity |
| `WeightedAverageShares` | the **basic** count; `shares_diluted` is the adjusted one |
| `PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets` | mixes PP&E with intangibles and investment property |

Expect gaps and do **not** close them by adding a tag: a bank files no
`operating_income` and no `FinanceCosts` (the same shape JPM has under
us-gaap), and an issuer that files depreciation and amortisation
separately has no `d_and_a`. **Summing two tags into one concept is
forbidden** — this project has no composite concepts, and inventing one
would be a wrong number, not a fuller table.

---

## 0.3. Rulings, so no fork is open at 03:00

1. **Two maps, two versions.** `CONCEPT_MAP` and `CONCEPT_MAP_VERSION`
   (`us-gaap.v3`) keep their names and values, byte for byte. The new
   ones are `CONCEPT_MAP_IFRS` and
   `CONCEPT_MAP_VERSION_IFRS = "ifrs-full.v1"`. They are never merged:
   which taxonomy fed a fact must stay visible.
2. **The taxonomy comes from the payload, never from the market.**
   Both present → `us-gaap` wins, and the report names that issuer.
   `if market == …` is forbidden anywhere in `rusterm/core/`.
3. **The venue comes from SEC's own file**, not from a guess:
   `company_tickers_exchange.json` carries `exchange` per ticker. `OTC`
   there is the venue; the issuer's jurisdiction is a separate thing and
   comes from the issuer record.
4. **No `companyfacts` is a coverage answer, not a crash.** HTTP 404
   means the issuer does not file XBRL with the SEC — for a foreign
   issuer, typically the Rule 12g3-2(b) exemption. The instrument is
   stored, `coverage` says `missing` with the reason `no_sec_filings`,
   and the command exits 0. Chasing that issuer to another source is out
   of scope and out of rule N1.
5. **`docs/` needs no change and must not be touched.** The dictionary
   lists canonical concept names and says nothing about taxonomies or
   venues. Check 10 stays green.
6. **The golden file is new, not edited.** `tests/data/golden_m2.json`
   does not change by one byte.
7. **No floors tonight.** You measure and report; the coordinator sets
   floors in the next task, the way it went for M3.

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
8. RECORD   one line in agent/REPORT-18.md: command + its output (§1.7).
```

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A genuinely obsolete assertion is
**replaced by a stronger one**, and the report says how the new one is
stricter.

**P2. Never edit an existing migration.** New migration, new number,
`_SCHEMA_VERSION` bumped. **Read `_SCHEMA_VERSION` from the file before
you write a number.**

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`. Except fetched data — §1.12 N5 is the opposite rule and
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

`agent/REPORT-18.md` is **append-only and verified after every write.**

- **R1.** Append only: `printf '%s\n' "…" >> agent/REPORT-18.md` or a
  quoted heredoc with `>>`. Never `>`, never `open(p, "w")`.
- **R2.** After every append: `wc -c agent/REPORT-18.md && tail -3
  agent/REPORT-18.md`, and look at the output.
- **R3.** Chain with `&&`, never `;`.
- **R4.** The final HANDOFF is appended at the end; a section is edited
  in place by line, never by rewriting the file from a variable. After
  writing it, `wc -c` must be larger than before, never smaller.

Sections, in this order: **Done**, **Blocked**, **What not to trust**,
**Disputed**, **HANDOFF**. Last line always `NOW: <item>, step <n>`.

`agent/STATE.json`, same commit as the work:

```json
{"task": "agent/TASK-18.md", "report": "agent/REPORT-18.md",
 "item": "G1", "step": "4", "status": "working",
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

### 1.12. Network rules. Read before the first request

**N1. One source: SEC EDGAR.** Canadian and OTC data come from the same
`companyfacts` and the same ticker files. No Companies House, no SEDAR+,
no OTC Markets, no vendor, no mirror, no scraper — the decision that
authorised Canada and OTC did **not** authorise a second source.

**N2. Identify yourself or do not go.** `RUSTERM_SEC_UA` must carry a
real contact. Unset or empty → `ConfigError` **value**, the offline path,
and `SEC_UA UNSET — payloads not recorded` in the report. Never
hardcode, commit or invent a contact.

**N3.** 5 requests/second, 5000/night ceiling, 2 retries then give up.
**This task's budget is 40 requests.** Count every one in `STATE.json`
`"net_requests"`.

**N4.** 403 or 429 is a stop, not a puzzle. Back off, record, move on.
Never change the User-Agent, never use a proxy or a mirror. **404 is not
an error at all here** — it is the answer G5 is built on.

**N5.** Fetched data never enters git **except** the trimmed payloads
under `tests/data/edgar/`.

**N6.** `fixtures/` stays synthetic-only.

**N7.** A network test skips cleanly when `RUSTERM_SEC_UA` is unset.

### 1.13. Money and quota

Free tier only for your own model; record a switch to a paid one in
`STATE.json`. At 800 of your own calls, close the night with §3. The
application's LLM path is not used tonight: `llm_calls` is 0.

---

## 2. The work, in priority order

### G1. The market registry — the item with the longest life

This is the user's requirement that a new market can be added **after the
MVP** without a rewrite. Everything else tonight is its first two
customers.

New module `rusterm/markets.py`: one frozen table, one row per market.

| field | meaning |
|---|---|
| `code` | what `--market` accepts: `US`, `CA`, `OTC` |
| `jurisdiction` | default issuer jurisdiction for the market |
| `venue_kind` | `exchange` or `otc` |
| `provider` | the provider name that serves it — `edgar` for all three today |
| `identifier` | the issuer identifier scheme — `cik` for all three today |
| `default_taxonomy` | **advisory only**: what to expect, never what to apply. The payload decides (§0.3 ruling 2) |

Rules that make it an architecture rather than a constant:

- `--market` is validated against the registry; an unknown code exits 1
  and prints the known codes. Today it is accepted silently, which is how
  a typo becomes an issuer with the wrong jurisdiction.
- **No market literal outside the registry.** A guard test asserts that
  `rusterm/formulas.py`, `rusterm/core/` and `rusterm/normalize/` contain
  no `"US"`, `"CA"` or `"OTC"` literal.
- The docstring states, in two sentences, what adding a market costs: a
  row here, a provider that answers for it, and its own recorded payload.
  Write it for the person who adds the fourth market a year from now.

**Done when** a test asserts the exact code set `{US, CA, OTC}`, that an
unknown `--market XX` exits 1 naming the known codes, and that the
literal guard passes (check it by adding `"CA"` to a core module,
watching it go red, and removing it); `python3 -m pytest -q` exits 0;
acceptance 13/13.

---

### G2. The venue comes from SEC's own file

`company_tickers_exchange.json` (fields `cik, name, ticker, exchange`)
is one request and answers where a ticker trades.

- `add` records `listing.exchange` from that file instead of leaving it
  to the caller, and stores `OTC` as the venue when that is what the file
  says.
- The file is fetched at most once per run and reused — the same
  discipline as the ticker map. It is **not** committed to git (N5).
- A ticker absent from the file: the instrument is still created, the
  venue is `unknown`, and the report says how many were unknown.

**Done when** a test with a hand-built two-row exchange file asserts an
NYSE ticker and an OTC ticker land with the right `listing.exchange`, and
a third absent ticker lands with `unknown` and no exception;
`python3 -m pytest -q` exits 0.

---

### G3. The second dictionary

`rusterm/normalize/concepts.py`, per §0.2 and §0.3 ruling 1.

- `CONCEPT_MAP_IFRS` exactly as the table gives it — not one tag more.
- `CONCEPT_MAP_VERSION_IFRS = "ifrs-full.v1"`.
- `canonical_for` gains a taxonomy argument defaulting to `us-gaap`, so
  every existing call site keeps its behaviour unchanged.

**Done when** a test asserts every tag maps to its concept under
`ifrs-full`; every one of the six forbidden lookalikes maps to `None`;
`st_investments` has no IFRS tag; `canonical_for("Revenue")` is `None`
under `us-gaap` and `revenue` under `ifrs-full`; the `us-gaap` map is
byte-identical; `python3 -m pytest -q` exits 0.

---

### G4. The payload says which taxonomy it is

`CompanyFactsParser` reads `facts["us-gaap"]` today and nothing else.

- Parse whichever taxonomy the payload carries and pass its name to
  `apply_concept_map`.
- Both present → `us-gaap` wins (§0.3 ruling 2); name that issuer in the
  report.
- Which taxonomy produced a fact stays visible afterwards — in the
  locator or an existing column, whichever the store already supports
  without a migration.

**Done when** a test parses a hand-built two-taxonomy payload and asserts
`us-gaap` won; a second parses an `ifrs-full`-only payload and asserts
canonical concepts came out; a mechanical guard asserts
`rusterm/formulas.py` is byte-identical to `origin/main`;
`python3 -m pytest -q` exits 0.

---

### G5. "This issuer files nothing with the SEC" is an answer

Per §0.3 ruling 4 — the honest half of OTC support, and the item that
keeps the terminal from lying.

- `companyfacts` 404 → a `ProviderError`-style **value**, never an
  exception and never a traceback.
- The instrument is created; `coverage` for `fundamentals` is `missing`
  with reason `no_sec_filings`; the command exits 0 and prints one line
  saying the issuer does not file XBRL with the SEC.
- `no_sec_filings` joins the vocabulary in `rusterm/reasons.py` (B15) in
  the same commit.

**Done when** a subprocess test drives `add` + `ingest` for a ticker
whose `companyfacts` 404s and asserts: exit 0, the coverage row with
`no_sec_filings`, no `raw_object`, no `fact`, and a message on stdout;
`python3 -m pytest -q` exits 0.

---

### G6. Payloads: three Canadian and two OTC

Record and trim, per N5. Candidates in this exact order; take the
**first three** for Canada whose `companyfacts` carries `ifrs-full` with
a period ending on or after `2024-01-01`, and the **first two** for OTC
that carry any taxonomy with a current period:

- **CA (IFRS):** Royal Bank `1000275`, Bank of Montreal `927971`,
  Canadian Natural `1017413`, then — only if one of those fails —
  Enbridge `895728`, Suncor `311337`
- **OTC:** `CPTP` Capital Properties `21175`, `HWKE` Hawkeye Digital,
  `NGGTF` National Grid `1004315`

Resolve every CIK through the SEC ticker file rather than trusting the
numbers above where a lookup is possible; if a number disagrees with the
feed, **the feed wins** and the report says so.

`tools/trim_companyfacts.py` keeps `facts["us-gaap"]` today; it must keep
whichever taxonomy is present, by the same four rules — only the
top-level key changes. Regenerate the manifest.

**Done when** `du -sk tests/data/edgar/` is **under 1024**; the manifest
has the new entries and every sha256 matches; a repeat trim on the same
input is byte-identical; `tests/data/golden_m2.json` shows **zero** diff;
`python3 -m pytest -q` exits 0.

---

### G7. `tests/data/golden_m6_ca.json`

The M2 discipline applied to the three Canadian issuers: every expected
value carries the `accn` of the filing it came from and the JSON pointer
that resolves to it, and is the **as-reported** figure — the
earliest-filed entry of its period, exactly as the trim tool collapses
them.

Three most recent complete fiscal years per issuer, over the concepts the
map actually feeds for that issuer. A concept an issuer does not file has
no row; nothing is invented for a gap.

**Done when** a test resolves every expected value through the recorded
payload by `accn` + pointer and asserts equality; the count of expected
values is in the report; `python3 -m pytest -q` exits 0.

---

### G8. The same formulas over the new issuers

A snapshot pass over the three Canadian and two OTC issuers — same
builder, same formulas, same reason vocabulary as the twenty.

- Print the table: measure → how many carry a value, with reason counts,
  in the same format as the M3 table. Copy it into the report verbatim.
- No floors (§0.3 ruling 7).
- Assert: every value that exists agrees with `golden_m6_ca.json`, every
  null carries a named reason, and no measure is computed from a
  taxonomy the issuer did not file.

**Done when** the test passes, the table is in the report, and the bank's
missing `operating_income` and `interest_expense` appear as named
reasons; `python3 -m pytest -q` exits 0.

---

### G9. End to end for the new markets

`rusterm add --ticker RY --market CA` and
`rusterm add --ticker CPTP --market OTC`, then ingest, snapshot, export.

**Done when** a subprocess test runs `init → add → ingest → snapshot →
export` for one CA and one OTC issuer against the recorded payloads,
asserts exit 0 and a non-empty measure table for each, and asserts the
stored issuer carries the jurisdiction and the venue the registry and the
exchange file gave; `python3 -m pytest -q` exits 0.

---

### G10. `status` tells the truth about both maps and the markets

`rusterm status --json` reports one concept-map version today. It must
report both, plus the market codes it serves — **without renaming or
removing the existing key** (a key is a contract).

**Done when** the key-schema test pins the new key set, the old key still
carries `us-gaap.v3`, and `python3 -m pytest -q` exits 0.

---

### G11. The milestone line

In the report's `Milestones` section: **M6 as redefined by the user** —
Canada, not the UK. Name the commands that prove it (G7's golden test,
G8's table, G4's `formulas.py`-unchanged guard) and say plainly that the
UK half was dropped by decision, not missed. Add one line for OTC: how
many of the recorded OTC issuers had XBRL and how the one without it is
reported.

---

### G12. The backlog

`agent/BACKLOG.md`, top down, by ID. Closing an item moves **the whole
block** into `## Done` as one `- [x]` line.

---

### G13. The bookkeeping

`agent/STATE.json` naming this task and this report, real
`net_requests`, ending at `"status": "awaiting_review"`; `## HANDOFF`
filled with real values; `agent/ACCEPTANCE-16.txt` taken at the head you
hand over, `git add`ed before the run.

**Done when** `tests/test_report_sections.py` passes,
`agent/ACCEPTANCE-16.txt` is non-empty and its `HEAD:` line is the commit
before the final `agent/` commit, and
`python3 -c "import json;d=json.load(open('agent/STATE.json'));assert d['task']=='agent/TASK-18.md' and d['status']=='awaiting_review'"`
succeeds.

---

## 3. Night end

```bash
git add agent/ACCEPTANCE-16.txt agent/REPORT-18.md agent/STATE.json
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-16.txt
git add agent/ACCEPTANCE-16.txt
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      G1, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-16.txt)
Tests:           N passed, M skipped, K xfailed
Markets:         the exact code set the registry pins
Issuers taken:   three CA and two OTC, by CIK and venue; who was skipped why
Measure table:   the printed table over the new issuers, verbatim
Golden m6 CA:    how many expected values, all resolved by accn + pointer
No-filings path: the ticker that 404s, and what coverage says about it
formulas.py:     byte-identical to origin/main? — the command and its output
Payload size:    du -sk tests/data/edgar/ — must be under 1024
Both taxonomies: any issuer carrying us-gaap and ifrs-full at once?
Milestones:      M6 (Canada) yes/no; OTC yes/no — what is missing if no
Network:         RUSTERM_SEC_UA set? — N requests of a 40 budget
Model:           app LLM calls 0; your own model id and count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

Out of scope tonight, no exceptions for spare time:

- **any source but SEC EDGAR** — Companies House, SEDAR+, OTC Markets and
  every vendor are outside the decision that authorised Canada and OTC
- the **UK** — dropped by the user's decision
- chasing an issuer that files nothing with the SEC to another source
- ADR ratios, per-share measures, EPS, market capitalisation for non-US
  issuers
- summing two tags into one concept; any composite concept
- a tag not named in §0.2; a third taxonomy
- editing `docs/`, `tests/data/golden_m2.json`, `rusterm/formulas.py`
- floors for the new issuers (the coordinator sets them next task)
- a fourth market — the registry exists so that one is a later decision,
  not a spare-time addition
- Qt or any GUI; price vendors; refactoring green code no item names

## 5. Stack

Python 3.12+, must also run on 3.14. Standard library; `pytest`;
`sqlite3` and `curses` from stdlib; `zstandard` optional with `gzip`
fallback; `httpx`/`requests` only inside `rusterm/providers/`, and
`urllib.request` from stdlib is preferred. `tools/` is a dev-tool
directory outside the application and outside checks 1, 5, 7 and 8.
Forbidden: ORM, `alembic`, `pandas`, `numpy`, async frameworks, `rich`,
`textual`. `from __future__ import annotations` at the top of every
module; builtin generics.

## 6. Acceptance script

`bash agent/acceptance.sh` — thirteen machine checks, 13/13 when you
start, never below it. **Editing that file is forbidden** — check 12
compares it byte for byte against `origin/main`. Think a check is wrong —
write it in `## Disputed`.
