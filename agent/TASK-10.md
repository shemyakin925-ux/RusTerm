# TASK-10 — the payloads stop starving the formulas

- **Status: READY** — this is the task. Start here.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-10.md`
- **Supersedes:** TASK-9 (**ACCEPTED**, V0–V8 done, 13/13 on a clean
  checkout, `net_margin` 20/20 — better than the 19/20 you reported).
  Do not reopen it.
- **Goal of the night, in one sentence:** the recorded payloads carry
  every tag the V0 map names, pinned to the filing that reported it, so
  that the formulas TASK-9 wrote stop returning `missing_data` on twenty
  real issuers.

You are an autonomous coding agent with the same tools as the
coordinator: shell, file editing, test runs, network. This file gives
contracts, decisions and acceptance commands, not tutorials. Anything
readable from the repository, read from the repository.

No coordinator is online during the run. Every fork below is closed by a
deterministic rule. Where a rule is wrong, follow it and put the
objection in **Disputed** — that channel works: thirteen of thirteen
disputes have been answered, and the three you raised last night are
answered in §0.2 below, one of them by going to the live SEC feed.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git merge origin/main          # brings TASK-10, TASK-11, LAUNCH, BACKLOG
bash agent/acceptance.sh
```

The last command must print `Итог: пройдено 13, провалено 0`. The
coordinator ran exactly this on a clean detached checkout of
`agent/night-2` at `cf1919b` and got 13/13 with
`273 passed, 2 skipped`. Anything else means your environment differs —
record the full output as the first entry in `agent/REPORT-10.md` and
continue. Do not "fix" acceptance.

`origin/main` carries no `docs/` change this time, so acceptance check
10 stays green before the merge as well. Merge anyway, first: the task
files are on it.

Then read, in full and from the repository, the files you will touch:
`rusterm/normalize/concepts.py`, `rusterm/core/snapshot.py`,
`rusterm/formulas.py`, `rusterm/store/repos.py`, `rusterm/cli/__init__.py`,
`tests/test_m3_snapshot.py`, `tests/test_m2_golden.py`,
`tests/data/golden_m2.json`, `docs/data-dictionary.md`.
The recurring failure in this repo is editing a file from a remembered
shape instead of its current one.

---

## 0.1. Where the project stands — measured, not reported

The coordinator re-ran everything on a clean detached checkout at
`cf1919b`. These are facts, not claims from a report:

| Check | Result |
|---|---|
| `bash agent/acceptance.sh` | **13/13**, `Принято` |
| `python3 -m pytest` | **273 passed, 2 skipped**, 0 xfail |
| deleted `assert` during the night | **0** |
| edits to applied migrations | **0** — only `_SCHEMA_VERSION` 35→36 |
| `agent/acceptance.sh` vs `origin/main` | byte-identical |
| `docs/` | untouched; the 3 ADRs predate the night |
| `rusterm add` **offline** (`--cik`, `--name`) by hand | creates `US-AAPL`, second run says `уже существует`, exit 0 |
| `rusterm add` **online** (contact set) by hand | **crashes**, `NameError: get_provider`, exit 2 — see W0 |
| `rusterm status --json` | carries `concept_map_version: us-gaap.v1` |
| `~/.rusterm.env` | `RUSTERM_SEC_UA` set; LLM keys commented out — V7's skip was by the rule |

**Your V5 number was too modest: `net_margin` is 20 of 20, not 19.**
The coordinator raised the test's own threshold to 21 and read the
failure message. V0's mapping and V1's period selection work on real
data, exactly as they were meant to.

**And that is the only measure that works.** The coordinator built all
twenty snapshots and counted every measure:

| measure | with a value | why the rest are null |
|---|---|---|
| `net_margin` | **20/20** | — |
| `asset_turnover` | 5/20 | `missing_data` ×15 |
| `roe` | 4/20 | `missing_data` ×16 |
| `operating_margin` | **0/20** | `missing_data` ×20 |
| `effective_tax` | **0/20** | `missing_data` ×20 |
| `gross_margin` | **0/20** | `missing_data` ×20 |
| `ebitda` | **0/20** | `missing_data` ×20 |
| `fcf` | **0/20** | `missing_data` ×20 |
| `interest_coverage` | **0/20** | `missing_data` ×20 |
| `nopat` | **0/20** | `missing_data` ×20 |
| 18 price/composite names | 0/20 | `concept_not_mapped` — correct, out of scope |

`missing_data` twenty times over is not a formula defect. TASK-9 §V5
said it in advance: `OperatingIncomeLoss`, `IncomeTaxExpenseBenefit` and
the pretax tags **are in none of the committed payloads**, because the
payloads were trimmed to five concepts before the V0 map existed. The
re-trim that was to fix this is the half of V5 that stopped.

So V4 shipped nine formulas that no real issuer can exercise, and the
strengthened M3 test passes on the one measure that never needed the
re-trim. **That is this night's work: feed them.**

**And V3 shipped a crash.** `rusterm add` was reported Done with an
online path that resolves the CIK from the EDGAR ticker map. The offline
path works — the coordinator ran it. The online path raises `NameError`
on its first line of real work, and no test has ever reached it, because
every `add` test forces the offline branch. That is W0.

This does **not** reject the night. Nothing blocking happened: no
assertion was deleted, no applied migration edited, `agent/acceptance.sh`
is byte-identical to `origin/main`, `docs/` is untouched. A defect in
shipped code becomes the first item of the next task — which is what W0
is. The rule that returns a night wholesale is about tampering with the
checks, not about bugs.

Total unmapped facts across twenty issuers: **5**, all of them
`us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`.
That single tag is why `roe` is 4/20. It is ruled on in W3.

| Layer | State |
|---|---|
| store, migrations, WAL, writer lock, repositories | done |
| facts, locators, basis rule, all three parsers | done |
| EDGAR provider through an enforced `RequestGate` | done |
| pipeline, idempotency, coverage, verification, recompute | done |
| us-gaap → concept map, one-period selection, period on the measure | done, **works on real data** |
| the `docs/data-dictionary.md` §3 formula set | written and unit-tested, **starved — W1/W2/W3** |
| recorded payloads | **trimmed to 5 concepts, accn-blind, no tool — W1** |
| `rusterm add` offline, `snapshot`, `export`, `tui`, `doctor` | done |
| `rusterm add` online | **crashes, untested — W0** |
| LLM guard rail | done and tight |
| M1, M2, M3-with-one-value | reached |
| M3-with-the-formula-set, M5 | **not reached** |

---

## 0.2. Rulings on your three questions. All three answered

### 1. JNJ. Your STOP was right. Your diagnosis was wrong

You reported: *"SEC restated JNJ historical figures between fetches —
RFC FY2021 93775000000 → 78740000000"*, and stopped rather than change a
golden value. **Stopping was correct and is commended** — it is exactly
what the rule is for.

But SEC rewrote nothing. The coordinator fetched
`CIK0000200406.json` live and looked at the FY2021 revenue period
(`2021-01-04` … `2022-01-02`). It holds **three** entries, not one:

| val | accn | form | filed |
|---|---|---|---|
| 93 775 000 000 | `0000200406-22-000022` | 10-K | 2022-02-17 |
| 93 775 000 000 | `0000200406-23-000016` | 10-K | 2023-02-16 |
| 78 740 000 000 | `0000200406-24-000013` | 10-K | 2024-02-16 |

`companyfacts` is append-only per filing. All three are still there; the
original was never touched. The golden row pins
`accn 0000200406-22-000022` and `93775000000`, and the live feed still
agrees with it exactly.

**What actually changed is your trim.** It collapses a period to one
entry, and the first trim happened to keep the earliest-filed while the
re-trim kept the newest — which for JNJ is the FY2023 10-K's
continuing-operations figure after the Kenvue separation. Both numbers
are true; they are different *bases* of the same period, and this
project already has a column for that: `fact.basis IN ('as_reported',
'restated')`, filled by `determine_basis` (I3), and
`as_reported_facts()` already filters `basis='as_reported'`. The data
model was never in danger. The trim is what is accn-blind.

**Ruling:**

- **Golden expected values are never adopted from a restatement.**
  93 775 000 000 stays. The rule you followed is confirmed, permanently.
- **The trim becomes accn-aware and becomes a committed tool** — W1.
- **`json_pointer` stops being positional.** `/units/USD/0/val` names an
  array index, which is why a re-trim can move a pointer under a fixed
  expected value. Golden rows are located by `accn` — W1.

You could not have known this without the live feed and the accn list;
raising it and stopping was the right move on the information you had.

### 2. V1 period matching: instants on `end` only

**Confirmed, as you implemented it.** An instant fact has no meaningful
`period_start` — the project writes `start = end` for it — so matching
instants on `end` alone is correct, and requiring an identical
`period_start` for durations is correct. No change. Write the rule into
the docstring of the selection function so the next reader does not
re-derive it — W6.

### 3. `cagr` registered as `concept_not_mapped`

**Upheld: it should not be in the measure list at all.** `cagr(V, n)` in
`docs/data-dictionary.md` §3 is a *function over a named series*, not a
measure of an issuer — there is no "the CAGR" of a company the way there
is "the net margin". Reporting it as an unmapped concept is a small lie
about a thing that was never a measure. Remove it from
`_UNMAPPED_FORMULAS`, keep the function in `formulas.py` with its own
unit test — W5. The other seventeen names in that tuple stay: they are
genuinely blocked on price data or on `total_debt`, both out of scope.

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
8. RECORD   one line in agent/REPORT-10.md: command + its output (§1.7).
```

Steps 6 and 7 do not get deferred. One item, one commit, one push bounds
any loss to the item in flight.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong. A genuinely obsolete assertion is **replaced
by a stronger one**, and the report says how the new one is stricter.

**P2. Never edit an existing migration.** Schema change = **new**
migration, new number, `_SCHEMA_VERSION` bumped. Next free number is
**37** (34 does not exist and never will; 36 is `canonical_concept`).

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

`agent/REPORT-10.md` is **append-only and verified after every write.**
The empty-report incident cost a whole night's history. Three rules,
now project rules and not personal ones:

- **R1.** Never open the report with a truncating mode. Append only:
  `printf '%s\n' "…" >> agent/REPORT-10.md`, or a quoted heredoc with
  `>>`. Never `>`, never `open(p, "w")` on it.
- **R2.** After every append, run
  `wc -c agent/REPORT-10.md && tail -3 agent/REPORT-10.md` and look at the
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
{"task": "agent/TASK-10.md", "report": "agent/REPORT-10.md",
 "item": "W1", "step": "4", "status": "working",
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
`agent/REPORT-10.md`, keep committing locally, and at the end produce
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
shape and is small. That exception is what W1 and W2 use.

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

W0 is a crash on the path a person walks first — twenty minutes, do it
first. W1 and W2 are the night. Everything below them is worth doing
and none of it changes what the program can compute.

---

### W0. `rusterm add` crashes on the online path. Do this first

`rusterm add --ticker AAPL --market US` **with a SEC contact set** —
V3's headline, the thing a person types first — dies at
`rusterm/cli/__init__.py:353`:

```
$ rusterm add --ticker AAPL --market US
внутренняя ошибка; подробности: logs/app.log
NameError: name 'get_provider' is not defined
```

`get_provider` is defined in `rusterm/providers/__init__.py:47` and is
never imported by the CLI module. The function above it imports `_PE`,
`ConfigError`, `NetworkGate` and `RequestGate` locally and misses this
one. Every `add` test sets `RUSTERM_SEC_UA` empty and points
`RUSTERM_ENV_FILE` at a blank file, so all of them take the offline
branch — **no test has ever executed these seven lines.** That is the
defect behind the defect.

Two more faults sit on the same lines, both to be fixed in this item:

- `get_provider` returns a `ConfigError` **value** when a network
  provider gets no gate; the code calls `.resolve()` on the result
  without checking, so a misconfigured gate gives an `AttributeError`
  instead of a message. Check the return value first, print its
  `reason`, exit 1.
- `EdgarProvider.resolve()` returns `{"ticker", "cik"}` — there is no
  `"title"` key, so `resolution.get("title")` is always `None` and the
  issuer is created named `AAPL` instead of `Apple Inc.`. The name is
  available and thrown away: `_ticker_map()` builds
  `{ticker: cik}` from rows that carry `title`
  (`{"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}`).
  Have `_ticker_map()` keep `{ticker: (cik, title)}` and `resolve()`
  return `{"ticker", "cik", "title"}`. Existing callers of `resolve()`
  read `["cik"]` — check each one before you change the shape.

**Test it hermetically.** The online branch must be covered without a
network request: `EdgarProvider` already takes a `transport` callable,
and `tests/test_m3_snapshot.py` shows the pattern. A test that only
passes when the machine has a contact is not coverage.

**Done when** a test injects a fake transport serving
`tests/data/edgar/company_tickers.json`, calls `cmd_add` on the online
branch, and asserts exit 0, the issuer named `Apple Inc.` and cik
`320193`; a second test asserts a gate-less `get_provider` result gives
exit 1 with the reason and no traceback in `logs/app.log`;
`python3 -m pytest -q` exits 0; `bash agent/acceptance.sh` stays 13/13.

---

### W1. The trim becomes a committed, deterministic, accn-aware tool

The payloads were trimmed by hand twice and the two trims disagreed
(§0.2). A procedure nobody can re-run is not a procedure.

Write `tools/trim_companyfacts.py`. It lives **outside `rusterm/`** on
purpose: acceptance checks 5, 7 and 8 scope to `rusterm/`, so a dev tool
at the repo root may use `urllib.request` and needs no provider. It is
not imported by the application and not covered by check 1.

Contract, all of it deterministic:

- **Input** a full `companyfacts` JSON on stdin or at a path; **output**
  the trimmed JSON on stdout, `json.dumps(..., separators=(",", ":"),
  sort_keys=True)` so two runs on one input are byte-identical.
- **Tags kept:** exactly those in `rusterm.normalize.concepts.CONCEPT_MAP`
  (import it; do not retype the list), plus any tag named by a
  `json_pointer` in `tests/data/golden_m2.json`.
- **Entries kept:** `form == "10-K"` only. Group by `(start, end)`. Per
  period keep **one** entry — **the earliest `filed`**, which is the
  as-reported figure, the one `fact.basis` calls `as_reported`. A later
  filing restating the same period is dropped here; the store's
  `determine_basis` (I3) is what handles restatements at ingest, not the
  fixture.
- **Periods kept:** the **six most recent** by `end`, per tag per unit.
- **Fields dropped:** `label`, `description`, and every unit that no
  kept tag uses. Keep `val`, `accn`, `form`, `filed`, `fy`, `fp`,
  `start`, `end`, `frame` if present.
- **Top level kept:** `cik`, `entityName`, `facts.us-gaap`. Nothing else.

The coordinator ran this shape against the live AAPL feed: 3 789 099
bytes in, **24 182 bytes out, 26 of 33 tags present**, which puts twenty
issuers at about **0.46 MB** — comfortably inside the 1 MB ceiling. If
your output is far off that, the rule you implemented is not this one.

Then make the golden file survive a re-trim. `tests/data/golden_m2.json`
locates each value by `"json_pointer": "/facts/us-gaap/<Tag>/units/USD/0/val"`
— an **array index**, which moves whenever entries are dropped or
reordered. That is the mechanism that nearly rewrote a JNJ value.

- Add `"accn"` to the lookup path used by `tests/test_m2_golden.py`: the
  test finds the entry whose `accn` equals the row's `accn` and whose
  `(start, end)` match, and asserts its `val` equals `expected`. Each row
  already carries `accn`.
- Keep `json_pointer` in the file — it documents where the value sat —
  but **regenerate it after the re-trim** so it stays true. The
  `expected` value is never regenerated; it is compared.

**Done when** `python3 tools/trim_companyfacts.py` run twice on one
recorded payload produces byte-identical output (`cmp` exits 0); a new
`tests/test_trim_tool.py` asserts on a hand-built two-filing fixture
that the **earliest-filed** entry survives and the restatement does not;
`python3 -m pytest tests/test_m2_golden.py -q` exits 0 with the
accn-based lookup; `python3 -m pytest -q` exits 0.

---

### W2. Re-fetch and re-trim the twenty. The formulas get fed

Skip **entirely** if `RUSTERM_SEC_UA` is unset — record
`SEC_UA UNSET — payload refresh not exercised`, do W3 onward, and do not
simulate it. `rusterm doctor` tells you whether it is set; the
application reads `~/.rusterm.env` itself.

- One `companyfacts` request per issuer, twenty in total, through the
  same path as before. Count them in `STATE.json` `"net_requests"` —
  and this time actually update the file (§1.7; last night it ended
  pointing at TASK-8 with a request count from two commits earlier).
- Trim each through W1's tool. **One file per issuer**, named
  `tests/data/edgar/companyfacts_m3_<TICKER>.json`, for all twenty.
- Delete the five `companyfacts_m2_*.json`. Repoint
  `tests/test_m2_golden.py`, `tests/test_concept_map.py`,
  `tests/test_v4_formulas.py` and `tests/test_m3_snapshot.py`'s
  `_payload_path` at the single set. `_payload_path`'s m2/m3 fallback
  disappears with them.
- Regenerate `tests/data/edgar/m3_manifest.json` for all **twenty**
  tickers with cik and sha256. It currently lists fifteen.
- `tests/data/edgar/companyfacts_aapl.json` stays — `test_edgar_parser.py`
  needs an untrimmed-shape payload. Add a one-line comment at the top of
  that test saying so. (This closes backlog B14.)

**The JNJ check is the proof the design works.** After the re-trim,
`companyfacts_m3_JNJ.json` must carry, for period
`2021-01-04`…`2022-01-02`, `val 93775000000` with
`accn 0000200406-22-000022` — the as-reported figure, not
`78740000000` from `0000200406-24-000013`. Assert it by name in
`tests/test_m2_golden.py`. If it comes out 78 740 000 000, W1's
earliest-filed rule is wrong and **that is a stop, not a golden edit**.

**Done when** `python3 -m pytest tests/test_m2_golden.py -q` exits 0
with all 125 rows resolving and no `expected` value changed
(`git diff tests/data/golden_m2.json | grep '^[-+].*expected'` is
empty); `du -sk tests/data/edgar/` is under 1024; every manifest sha256
matches its file; `python3 -m pytest -q` exits 0.

---

### W3. `total_equity` and the one tag that is not mapped

Across twenty issuers exactly **five** facts have a `NULL`
`canonical_concept`, and all five are
`us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`.
That is why `roe` is 4/20.

The two tags are not synonyms: `StockholdersEquity` is equity
attributable to the parent; the `Including…` tag adds the
non-controlling interest. `docs/data-dictionary.md` already carries
`total_equity` and `minority_interest` as separate concepts, and the
V0 map's own docstring says two tags are never summed.

**Ruling, implement it exactly:**

- `total_equity` keeps `StockholdersEquity` as its only tag. `roe` uses
  `total_equity` and therefore stays parent-only. No change there.
- Add a new canonical concept **`total_equity_incl_nci`** mapped to
  `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
  alone. It is a mapped concept with no formula consuming it yet — that
  is fine and is the point: the fact stops being invisible.
- `CONCEPT_MAP_VERSION` becomes **`us-gaap.v2`**. The version string
  exists so two mappings can be told apart; changing the table without
  changing it is the failure it was built to prevent.
- Do **not** derive `total_equity` from the `Including…` tag minus
  `minority_interest`. Composite concepts are out of scope (§4).

**Done when** a test asserts the new concept maps, that `total_equity`
does **not** absorb the `Including…` tag, and that
`rusterm status --json` reports `us-gaap.v2`; the count of `NULL`
`canonical_concept` facts over the twenty issuers is **0** (assert it in
`tests/test_m3_snapshot.py`); `python3 -m pytest -q` exits 0.

---

### W4. The M3 test asserts the formula set, not one measure

`tests/test_m3_snapshot.py` asserts `net_margin >= 15 of 20`. That bar
was cleared by the one measure that never needed the re-trim, which is
how a night of nine starved formulas passed green.

Replace it with a per-measure table, asserted by name. After W2 the
floors below are what the coordinator's own count says the data
supports; a measure that lands under its floor is a defect to report,
not a floor to lower.

| measure | floor, of 20 |
|---|---|
| `net_margin` | 20 |
| `operating_margin` | 15 |
| `effective_tax` | 15 |
| `gross_margin` | 10 |
| `fcf` | 12 |
| `ebitda` | 10 |
| `interest_coverage` | 8 |
| `nopat` | 12 |
| `roe` | 12 |
| `asset_turnover` | 12 |

- Every non-null measure keeps the assertion it already has: a real
  `period_start` and `period_end`.
- Every null still carries a reason from the fixed set.
- The test **prints** the full `measure → n/20 + reasons` table so the
  report can quote it verbatim.
- **If `RUSTERM_SEC_UA` was unset and W2 was skipped**, the payloads are
  the old ones and every floor but `net_margin`'s will fail. In that
  case, and only that case, mark the new assertions
  `@pytest.mark.xfail(strict=True, reason="W2 skipped: SEC_UA unset, payloads still trimmed to 5 concepts")`
  — never delete them, never lower a floor. Say so in **Blocked**.

**Done when** `python3 -m pytest tests/test_m3_snapshot.py -q -s` exits
0 and its printed table is copied into `agent/REPORT-10.md`;
`python3 -m pytest -q` exits 0.

---

### W5. `cagr` leaves the measure list

Per §0.2 ruling 3. Remove `"cagr"` from `_UNMAPPED_FORMULAS` in
`rusterm/core/snapshot.py`. Keep the function in `rusterm/formulas.py`
and give it a unit test if it has none: a series growing 100 → 200 over
4 years has a CAGR of `2 ** 0.25 - 1`, to the project's rounding.

The other seventeen names stay. Do not touch them.

**Done when** a test asserts no measure row is ever written with
`concept = 'cagr'`, and a test asserts the function's value on the
series above; `python3 -m pytest -q` exits 0.

---

### W6. `rusterm add` on a database that was never initialised

Verified by hand by the coordinator:

```
$ rusterm add --ticker AAPL --market US --cik 320193 --name "Apple Inc."
внутренняя ошибка; подробности: logs/app.log
$ tail logs/app.log
sqlite3.OperationalError: no such table: instrument
```

Exit 2 and a raw traceback where the answer is one sentence. The offline
branch of the same command already gets this right — it says what is
missing and how to supply it.

- `cmd_add` checks the schema before it touches a repository, and on an
  uninitialised database prints `база не создана; выполните rusterm init`
  and exits **1**, not 2.
- Do this in one place if the CLI already has one: check whether other
  commands share a guard and reuse it rather than adding a second.

**Done when** a test on a directory with no database asserts exit code 1
and that the message names `rusterm init`, and that `logs/app.log`
carries no traceback for it; `python3 -m pytest -q` exits 0.

---

### W7. Say why two AAPL payloads exist

Folded into W2's last bullet. If W2 was skipped for lack of a contact,
do the comment on its own: `tests/test_edgar_parser.py` gets a one-line
header saying `companyfacts_aapl.json` is the untrimmed-shape payload
the parser is tested against, distinct from the trimmed M3 fixtures.

**Done when** the comment is in the file and `python3 -m pytest -q`
exits 0.

---

### W8. The bookkeeping, again — three of last night's four slipped

Not a code item. Last night: `agent/STATE.json` was handed over pointing
at `agent/TASK-8.md`, `agent/REPORT-8.md` and commit `7e4184f`, with
`net_requests: 44` unchanged after roughly twenty-five more requests;
the `HANDOFF` line `Tests:` was handed over as the literal template
`N passed, M skipped, K xfailed`; and the three real disputes were filed
under `Questions for the coordinator` while `## Disputed` was left empty
— and `## Disputed` is the section the coordinator reads first.

Commit `b67c096` says `журнал, отчёт, состояние` and contains only
`agent/ACCEPTANCE-7.txt`. A commit message is a claim like any other.

- `agent/STATE.json` names **this** task and **this** report, carries the
  real `net_requests`, and ends at `"status": "awaiting_review"`.
- `## HANDOFF` has every line filled with a real value. `Tests:` is the
  number `python3 -m pytest` printed.
- **Anything you disagree with goes under `## Disputed`.** Questions go
  under `Questions for the coordinator`. Both sections exist; use both.
- `agent/ACCEPTANCE-8.txt` comes from the branch head you hand over: the
  final acceptance run is the last thing before a final `agent/`-only
  commit. You got this one right last night — keep it.

**Done when** `python3 -c "import json;d=json.load(open('agent/STATE.json'));assert d['task']=='agent/TASK-10.md' and d['report']=='agent/REPORT-10.md' and d['status']=='awaiting_review'"` succeeds;
`grep -q '^## HANDOFF' agent/REPORT-10.md` and no line of the HANDOFF
block still reads `N passed, M skipped`; `agent/ACCEPTANCE-8.txt` is
non-empty and its `HEAD:` line is the commit before the final `agent/`
commit.

---

### W9. Queue empty

All of W0–W8 done before 09:30 — **take `agent/TASK-11.md`**, which is
`Status: READY` and waits for no review of this one. Only if that is
also done, take `agent/BACKLOG.md` top down. Do not invent work beyond
them.

---

## 3. Night end — you run the final acceptance yourself

```bash
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-8.txt
git add agent/ACCEPTANCE-8.txt agent/REPORT-10.md agent/STATE.json
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

A night whose acceptance log is missing is reviewed as if it printed
zero. A night whose log was taken from an earlier commit is reviewed at
the head anyway.

---

## HANDOFF (template — fill it, do not delete headings)

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      W0, …
Items not done:  … + one line why for each
Acceptance:      пройдено N, провалено M   (agent/ACCEPTANCE-8.txt)
Tests:           N passed, M skipped, K xfailed
Measure table:   the printed table from W4, verbatim
Payloads:        du -sk tests/data/edgar/ = N; manifest entries = N
JNJ FY2021:      val = …, accn = …
Concept map:     version = …; facts with NULL canonical_concept = N
Milestones:      M3-with-the-formula-set yes/no, M5 yes/no
Network:         RUSTERM_SEC_UA set? — N requests, M refused, K rate-limited
Model:           app LLM calls N; your own model id and call count
Pushed:          yes/no
Questions for the coordinator:
```

---

## 4. Scope boundary

In scope now, new since TASK-9: the recorded payloads and the tool that
makes them, the golden file's way of locating a value, the one unmapped
equity tag, and a test that asserts the formula set instead of one
measure.

Out of scope tonight, no exceptions for spare time:

- Qt or any GUI — acceptance check 6 forbids it, the TUI is the answer
- price vendors (ADR-0008 proposes; the user decides) — and therefore
  every measure in `_UNMAPPED_FORMULAS` that needs a price
- IFRS, UK and CA providers (M6), Industry View (M7)
- industry metrics beyond Maritime/Tanker
- a second taxonomy beside `us-gaap` — `ifrs-full` waits for M6
- `total_debt`, `invested_capital` and any other composite concept
- restatement handling beyond what `determine_basis` already does
- writes from the TUI, bulk operations without confirmation
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
what else you did. Think a check is wrong — write it in **Disputed**.
That channel has a perfect record: every dispute raised so far was
answered, and eleven of thirteen were upheld against the coordinator.
