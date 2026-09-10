# TASK-19 — Фаза 0: фундамент M8. Схема, реестры и причины — до разветвления

- **Status: READY** — this is the task. Start here.
- **Branch:** `agent/night-3` (branch it from the head of `agent/night-2`)
- **Report:** `agent/REPORT-19.md`
- **Blocks everything.** `agent/TASK-20.md` is a **parallel** task and
  must not be started until this one ends green. That is not caution,
  it is arithmetic: migrations are serialisable by definition (ADR-0012).
- **Goal of the night, in one sentence:** every shared thing the seven
  parallel lanes will need — one migration, the market registry with
  its access level, the new reasons, the per-host request budget, the
  extraction and LLM interfaces — lands once, in one branch, so that no
  lane ever touches `db.py`, `markets.py` or `reasons.py`.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-2
git pull
git checkout -b agent/night-3
bash agent/acceptance.sh > /tmp/acc.txt 2>&1; echo "STATUS=$?"; tail -4 /tmp/acc.txt
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
```

Acceptance must print `Итог: пройдено 13, провалено 0` **and**
`STATUS=0`. The second command tells you the next free migration number
— **read it, do not assume 40.**

**First commit of the night: open your journal and claim the state.**
`agent/STATE.json` currently reads `TASK-18 / REPORT-18 / accepted` —
that is the last closed shift, and the guard in
`tests/test_report_sections.py` reads the report it names. So create
`agent/REPORT-19.md` with its five section headers (**Done**,
**Blocked**, **What not to trust**, **Disputed**, **HANDOFF**) and
repoint `STATE.json` at it **in the same commit**. Repointing it before
the file exists turns the suite red, and you would be debugging your own
bookkeeping instead of working.

Note the shape of the acceptance line above: the exit status is captured
*before* anything is piped. Use that shape everywhere tonight; F7 makes it a
tool. Three nights in a row a red acceptance was pushed because `| tail`
swallowed the status (REPORT-15 Disputed, REPORT-17 question 1).

Read, in full and from the repository: `docs/adr/0010-rynki-vne-edgar.md`,
`docs/adr/0011-ruchnoy-import-dokumentov.md`,
`docs/adr/0012-parallelnoe-ispolnenie.md`, `agent/TASK.md`,
`rusterm/markets.py`, `rusterm/reasons.py`, `rusterm/providers/budget.py`,
`rusterm/providers/__init__.py`, `rusterm/store/db.py`,
`rusterm/cli/__init__.py`, `agent/REPORT-MARKETS.md` (the cross-market
table and the KR/BR/AU/US-OTC sections — they are measured, not guessed).

---

## 0.1. Rulings on the previous nights. Not open for re-litigation

The coordinator re-ran the acceptance and the suite on `agent/night-2`
before writing this. **TASK-14 through TASK-18 are ACCEPTED**, all five.
Acceptance 13/13, 361 passed, 2 skipped, 0 xfailed.

Rulings on the `Disputed` items you raised:

| # | Your claim | Ruling |
|---|---|---|
| 14A | A1+A3 in one commit: migration 38 turns a strict-xfail into XPASS, so splitting means a red commit | **Upheld.** The circular constraint is real. The combined commit was correct. |
| 14A | v32 stubs in tests widened to the true schema, not migration narrowed | **Upheld.** That is repair, not weakening. |
| 14A | 8 removed asserts are all 37→38 pin updates, one strengthened | **Upheld, verified.** No behavioural check was weakened. |
| 15 | One unreproducible red run, name not captured | **Not a dispute, a defect.** F7 makes the masking impossible. |
| 18 | G1+G2+G5 in one commit: the changes interleave in `cmd_add` | **Upheld.** Splitting those hunks would have been riskier than the combined commit. |
| 18 | `formulas.py` byte-identical to the start head; `origin/main` has no such file | **Upheld, verified.** `origin/main` carries no `rusterm/` at all — the whole branch is unmerged. Merging to `main` is the coordinator's job, not yours. |

Answers to your questions:

- **TSX-only issuers (CSU class) are unreachable.** Correct, and it is
  now documented where a user will meet it: `manual_import_required`
  (F3) names the manual-import command in its own message.
- **CPTP: the live feed's CIK 202947 beat the task's 21175.** Right
  call. The feed wins over the task on facts about the world, always.
- **venue vs jurisdiction for a CA issuer on NYSE** — read correctly:
  venue NYSE, market CA. Jurisdiction follows the issuer, venue follows
  where it trades. F1 writes this down in the registry docstring.
- **Live tests re-run inside every acceptance** — acceptable as the
  standing cost. Do not gate them behind a flag.
- **`RuleClient` switching on a real key automatically** — yes, and
  that is F6.
- **`list_industry_instruments` returning empty** — keep it; M7 landed,
  wire it in TASK-21.
- **A mechanical guard against the piped-exit-code defect** — yes. F7.

## 0.2. What the user decided on 10.09.2026

1. Markets **KR, BR, AU** and a deepening of **US-OTC** are wanted.
2. **Only auto-downloadable issuers are added.** Everything else is
   refused by name and pointed at manual import.
3. **Manual import of documents in many formats**, not only PDF.
4. **One LLM option: over an API.** No local model.
5. **The UK is dropped from every mention.** Canada is **not** — it is
   built, green, and carries `ifrs-full`. Where old text says
   "providers UK and CA", only the UK half goes.

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
8. RECORD   one line in agent/REPORT-19.md: command + its output (§1.7).
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
fails on it. From F7 onward, `bash agent/selfcheck.sh` runs all four and
is the only form you use.

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

`agent/REPORT-19.md` is **append-only and verified after every write.**

- **R1.** Append only: `printf '%s\n' "…" >> agent/REPORT-19.md` or a
  quoted heredoc with `>>`. Never `>`, never `open(p, "w")`.
- **R2.** After every append: `wc -c agent/REPORT-19.md && tail -3
  agent/REPORT-19.md`, and look at the output.
- **R3.** Chain with `&&`, never `;`.
- **R4.** The final HANDOFF is appended at the end; a section is edited
  in place by line, never by rewriting the file from a variable. After
  writing it, `wc -c` must be larger than before, never smaller.

Sections, in this order: **Done**, **Blocked**, **What not to trust**,
**Disputed**, **HANDOFF**. Last line always `NOW: <item>, step <n>`.

`agent/STATE.json`, same commit as the work (this task is sequential and
keeps the single file; the parallel task moves to `agent/state/<lane>.json`):

```json
{"task": "agent/TASK-19.md", "report": "agent/REPORT-19.md",
 "item": "F1", "step": "4", "status": "working",
 "last_commit": "<sha>", "requests": 0, "net_requests": 0,
 "llm_calls": 0, "model": "<your model id>",
 "updated_at": "<ISO8601 UTC>"}
```

### 1.8. Push, every time

```bash
git push origin agent/night-3
```

Push fails — do not retry in a loop. `PUSH UNAVAILABLE` as the first line
of the report, keep committing locally, and at the end
`git bundle create ../RusTerm-handoff.bundle --all` outside the repo.

### 1.9. Stop time

**10:00 Danang (UTC+7).** No new item after 09:30. Finish the current
item to a commit and a push, then §3.

### 1.10. Precedence when sources disagree

This file → `agent/TASK.md` → `docs/` → existing code → your judgement.
A conflict between the first two is a coordination bug: implement per
this file and record both quotes in **Disputed**. Green code is
extended, never refactored, except where an item names the file and the
defect.

### 1.11. What you may assume

- `python3` is 3.14.6 here; the code must also run on 3.12. `pytest` is
  installed, `zstandard` is not, and check 11 reruns the suite without it.
- Acceptance is 13/13 at your start and is ground truth about your work.
- `docs/` is frozen. **New ADRs are the one permitted change.**
  ADR-0010, 0011 and 0012 already exist — read them, do not rewrite them.

### 1.12. Network rules. Read before the first request

**N1 (replaced).** The source is no longer one. **The source is the
`provider` column of the market registry** (ADR-0010). Tonight you add
*no* new network provider — you add the seats they will sit in. Your
only network use tonight is F5's live probe of one host per new market,
capped below.

**N2. Identify yourself or do not go.** `RUSTERM_SEC_UA` must carry a
real contact. Unset or empty → `ConfigError` **value**, the offline path,
and `SEC_UA UNSET` in the report. Never hardcode, commit or invent a
contact. The same rule now covers `RUSTERM_LLM_API_KEY` and
`RUSTERM_DART_KEY`: **a key never enters git, a report, a log, a
fixture or a commit message.**

**N3.** Per-host rate and budget (F5). **This task's total budget is 12
requests.** Count every one in `STATE.json` `"net_requests"`.

**N4.** 403 or 429 is a stop, not a puzzle. Back off, record, move on.
Never change the User-Agent to defeat a refusal, never proxy, never
mirror. 404 is an answer, not an error.

**N5.** Fetched data never enters git **except** trimmed payloads under
`tests/data/<provider>/`.

**N6.** `fixtures/` stays synthetic-only.

**N7.** A network test skips cleanly when its key or UA is unset.

### 1.13. Money and quota

Free tier only for your own model; record a switch to a paid one in
`STATE.json`. At 800 of your own calls, close the night with §3. The
application's LLM path is not exercised tonight: `llm_calls` stays 0.

---

## 2. The work, in priority order

Ordered so that if the night runs short, the top items are the ones the
parallel lanes cannot start without.

### F1. The registry gains an access level, and the UK leaves

`rusterm/markets.py` only.

- `Market` gains `access: str` — `auto` | `partial` | `manual`
  (ADR-0010 §2). Existing rows: `US` auto, `CA` auto, `OTC` partial.
- Three new rows, **with provider names that do not resolve yet**:
  `KR` (jurisdiction KR, venue_kind exchange, provider `dart`,
  identifier `corp_code`, default_taxonomy `ifrs-full`, access `auto`);
  `BR` (BR, exchange, `cvm`, `cvm_code`, `ifrs-full`, `auto`);
  `AU` (AU, exchange, `asx`, `asx_code`, `ifrs-full`, `partial`).
- `venue_in_market` learns the new venues: KRX/KOSPI/KOSDAQ for KR,
  B3/BVMF for BR, ASX for AU. The `unknown` rule is unchanged.
- The docstring records the ruling from §0.1: **jurisdiction follows the
  issuer, venue follows where it trades** — a CA issuer on NYSE is
  market CA, venue NYSE.
- `grep -rin '\bUK\b\|companies house\|\bNSM\b' rusterm/ tests/` returns
  nothing. `docs/` is frozen — do **not** touch it; the UK lines there
  are handled by F9.

**Done when:** `python3 -m pytest tests/test_markets.py -q` green; a new
test asserts `MARKET_CODES == ("US","CA","OTC","KR","BR","AU")` and that
every row's `access` is one of the three words; an unknown `--market`
still exits 1 listing all six.

### F2. Six new reasons, one dictionary

`rusterm/reasons.py` only. Add, each with the comment naming its ADR:

| Reason | Meaning |
|---|---|
| `manual_import_required` | issuer exists on the market, disclosures are not machine-reachable (ADR-0010 §3) |
| `manual_unverified` | fact came from manual import and failed the deterministic check (ADR-0011 ③) |
| `format_unsupported` | the file's format needs a library that is not installed |
| `no_text_layer` | a scan; there is no OCR in this project |
| `unknown_issuer` | the market does not know this identifier |
| `source_unreachable` | the provider's host refused or timed out (403/429/timeout) |

**Done when:** `python3 -m pytest tests/test_repos.py tests/test_metrics.py -q`
green; a test asserts every new string passes `is_known_reason` and that
a reason outside the dictionary is still rejected by the `SnapshotRepo`
guard.

### F3. `add` refuses by name instead of creating a hollow issuer

`rusterm/cli/__init__.py`, and a capability question on the provider
protocol in `rusterm/providers/disclosures.py`.

- `DisclosuresProvider` gains `can_auto_ingest(identifier) -> bool |
  ProviderError`. Default implementation for existing providers returns
  `True` — EDGAR's behaviour does not change.
- `rusterm add` asks it before creating anything. Three outcomes exactly
  as ADR-0010 §3: ingest / `manual_import_required` / `unknown_issuer`.
- The `manual_import_required` message **names the manual-import
  command** with the ticker filled in. This is the only place the
  program advises the user of an action.

**Done when:** a test drives all three outcomes through a fake provider;
the refusal path leaves **zero** rows in `issuer` (asserted by count,
not by eye) and exits 0; the unknown path exits 1.

### F4. One migration for the whole night

`rusterm/store/db.py` and `rusterm/store/repos.py`. **This is the only
item all night that touches `db.py`, and no lane in TASK-20 may touch
it.** Read `_SCHEMA_VERSION` first.

- Table `document`: `sha256` (primary), `filename`, `format`,
  `page_count`, `issuer_id` nullable, `imported_at`, `bytes`.
- `fact` gains `source_kind` with a `CHECK` constraint over exactly
  `('provider','manual')`, defaulting to `'provider'` so every existing
  row keeps its meaning.
- Table `manual_extraction`: `document_sha256`, `page_no`, `category`
  (`financial`|`physical`|`other`), `metric`, `value`, `unit`, `period`,
  `quote`, `verified`, `model`, `prompt_version`.
- Repos: `DocumentRepo` and `ManualExtractionRepo`, same style as the
  existing ones. SQL stays inside `rusterm/store/` (check 7).

**Done when:** migration applied twice in a row produces no duplicates
(assert row counts); an existing v39 database migrates and every
pre-existing `fact` row reads back `source_kind == 'provider'`;
`python3 -m pytest tests/test_db.py tests/test_repos.py -q` green.

### F5. Budget per host, not per project

`rusterm/providers/budget.py` and `rusterm/providers/__init__.py`.

- `RequestGate` keys its rate limiter and its counter **by host**.
  SEC's 5/s does not leak onto `opendart.fss.or.kr` and vice versa.
- A provider declares `host`, `per_second` and `nightly_max`. The
  registry refuses to hand out a network provider that declares none —
  the same door as TASK-8 U5, one hinge wider.
- Defaults from the measured report: SEC 5/s, DART 2/s, CVM 1/s (bulk
  files), ASX 1/s, OTC 1/s.
- **Pre-register the four names now, lazily.** `_NETWORK_PROVIDERS` gains
  `dart`, `cvm`, `asx`, `otcmarkets`, each a lambda that imports
  `rusterm/providers/<name>.py` **inside the call** and returns
  `ConfigError("provider_not_implemented:<name>")` when the module is
  absent. This is the whole reason the item exists: without it, four
  parallel lanes all edit `providers/__init__.py` and all four conflict
  (ADR-0012 §2). After tonight **no lane touches this file** — a lane
  creates only its own module, and the seat is already there.
- **Live probe, 12 requests maximum, one or two per host**: confirm the
  four channels still answer as `agent/REPORT-MARKETS.md` recorded.
  Record status and byte counts in the report. A changed answer is a
  finding for the coordinator, **not** a reason to redesign tonight.

**Done when:** a test proves two hosts exhausting independently (host A
at its ceiling still lets host B through); `get_provider("dart", gate)`
returns `ConfigError("provider_not_implemented:dart")` rather than
raising `ImportError`, asserted by a test; `available()` lists all eight
names; `net_requests` in `STATE.json` matches the number of probes you
actually made.

### F6. The LLM client seat, and the switch onto a real key

`rusterm/providers/llm_api.py` (new) and `rusterm/core/llm.py`.

- OpenAI-compatible client: `RUSTERM_LLM_BASE_URL`, `RUSTERM_LLM_MODEL`,
  `RUSTERM_LLM_API_KEY`. HTTP lives here because check 8 says so.
- **No key → `ConfigError` value.** No key is ever hardcoded, logged,
  echoed into a report, or written into a test.
- `core/llm.py` selects: key present → the API client; key absent →
  today's `RuleClient`. That is the answer to REPORT-16 question 1.
- **No test requires a key.** The API path is covered by a fake
  transport returning recorded bodies.

**Done when:** `python3 -m pytest tests/test_llm_guard.py tests/test_ops.py -q`
green with `RUSTERM_LLM_API_KEY` unset **and** set to a dummy value; a
test asserts the key string never appears in any produced log line,
audit record or report path.

### F7. The masked exit code becomes impossible

`agent/selfcheck.sh` (new; `agent/acceptance.sh` is untouchable —
check 12 compares it to `origin/main`).

The defect: `bash agent/acceptance.sh | tail -5` reports the status of
`tail`, which is always 0. It shipped a red acceptance three nights
running. The fix is a tool, not a resolution:

- runs the four §1.3 checks, captures acceptance output to a file,
  reads **its** status, and exits non-zero if any check failed;
- prints the last lines only after the status is known;
- refuses to exit 0 when `git status --porcelain` shows anything
  untracked.

Use it for every commit from here on. §1.3 above is superseded by it.

**Done when:** `bash agent/selfcheck.sh; echo $?` prints 0 on a clean
tree; deliberately staging a failing test makes it print non-zero **and**
say which check failed; `git ls-files agent/selfcheck.sh` finds it.

### F8. The seats for the manual-import lanes

`rusterm/manual/__init__.py` (new package) — **interfaces and their
tests, no implementation.** The lanes L5 and L6 in TASK-20 fill them,
and they must not have to agree with each other at 3 a.m.

- `Page(page_no: int, text: str)` and
  `Document(sha256, filename, format, pages, byte_len)`.
- `extract_text(path) -> Document | ProviderError` — the ① contract.
- `Record(company, category, metric, value, unit, period, quote,
  page_no)` — the ② contract.
- `verify(record, document) -> bool` — the ③ contract: quote present
  verbatim on its page, and the numerals of `value` present in `quote`.
  **Implement this one fully** — it is deterministic, small, and both
  lanes depend on its exact behaviour.
- No HTTP in this package (check 8). No SQL (check 7).

**Done when:** `verify` has a test table of at least eight cases
including a fabricated number, an altered quote, a right number on the
wrong page, and a number formatted differently in quote and value;
`extract_text` returns `format_unsupported` as a **value** for an
unknown format.

### F9. README tells the truth about the milestones

`README.md` §15 only. `docs/` stays frozen; README is not under check 10.

- `M6. UK и CA` → `M6. Канада и площадка OTC` — **достигнута**
  (TASK-18). The UK half was dropped by the user, not missed.
- New row `M8. Рынки KR, BR, AU и ручной импорт` — in progress.
- M1–M5 and M7 marked reached, with the task number that closed each.

**Done when:** `grep -n 'UK' README.md` returns nothing;
`bash agent/selfcheck.sh` still exits 0.

### F10. Hand the fan-out a clean head

- `agent/state/` created with a `.gitkeep`, per ADR-0012.
- The final commit of the night is **tagged** `n3-foundation` and
  pushed. TASK-20's lanes branch from that tag by name, not from a sha
  you have to look up.
- The report's HANDOFF names the tag and the acceptance line.

**Done when:** `git tag --list n3-foundation` prints it;
`git push origin n3-foundation` succeeded; a fresh
`git checkout -b probe n3-foundation && bash agent/selfcheck.sh` exits 0.

### F11. Backlog

Queue in `agent/BACKLOG.md` — take items top-down only if F1–F10 are
done before 09:30.

---

## 3. Closing the shift

Append `## HANDOFF` to `agent/REPORT-19.md` with, each on its own line:

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      F1, F2, …
Items not done:  … and why
Acceptance:      the "Итог" line, and the exit status you captured
Tests:           N passed, N skipped, N xfailed
Schema:          _SCHEMA_VERSION <old> -> <new>, migration <number>
Markets:         the exact tuple MARKET_CODES prints
Reasons added:   the six strings
Probe results:   host -> status, bytes, compared to REPORT-MARKETS
Tag:             n3-foundation at <sha>, pushed yes/no
selfcheck.sh:    exit code on a clean tree, and on a deliberately red one
Secrets:         confirm no key appears in git, reports or logs
Network:         requests used of the 12 budget
Model:           app llm_calls 0; your own model id
Pushed:          yes/no
Questions for the coordinator:
1. …
```

Then set `agent/STATE.json` to `"status": "awaiting_review"` and push.
