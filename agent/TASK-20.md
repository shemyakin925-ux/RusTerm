# TASK-20 — Фаза 1: десять полос параллельно. Рынки, ручной импорт, модель по API

- **Status: READY** — take it **only** when `agent/TASK-19.md` is done
  and the tag `n3-foundation` exists and is green. Not before: every
  lane below assumes the migration, the registry rows, the reasons and
  the provider seats are already there.
- **Branch:** one per lane, `agent/n3-<lane>`, cut **from the tag**
  `n3-foundation` — never from another lane.
- **Report:** one per lane, `agent/REPORT-20-<lane>.md`.
- **State:** one per lane, `agent/state/<lane>.json`.
- **Next in queue:** `agent/TASK-21.md` (integration and M8 acceptance),
  `Status: READY`.
- **Goal of the night, in one sentence:** four new markets, a second way
  into the data through files on disk, and a real model behind an API —
  built by ten processes that never touch the same file, each ending on
  a branch that is green on its own.

Section 1 is the working protocol and outranks the lane list.

---

## 0. Start here, once, before any lane

```bash
git fetch --tags
git checkout n3-foundation
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -c "import rusterm.markets as m; print(m.MARKET_CODES)"
python3 -c "import rusterm.providers as p; print(p.available())"
```

`STATUS=0` is required. `MARKET_CODES` must print six codes including
`KR`, `BR`, `AU`. `available()` must list `dart`, `cvm`, `asx`,
`otcmarkets` — the seats TASK-19 F5 pre-registered.

If any of those three fails, **do not start the fan-out.** Write
`FOUNDATION NOT READY` as the first line of `agent/REPORT-20-000.md`,
say which of the three failed with its output, and work TASK-19's
unfinished items sequentially instead.

Read, in full: `docs/adr/0010-rynki-vne-edgar.md`,
`docs/adr/0011-ruchnoy-import-dokumentov.md`,
`docs/adr/0012-parallelnoe-ispolnenie.md`, `agent/TASK.md`,
`agent/REPORT-MARKETS.md`, and — per lane — the files in your own zone.

---

## 1. Working protocol for a parallel night

Everything from `agent/TASK-19.md` §1 applies **unchanged** — the cycle,
the five prohibitions, the stuck rule, the stop rule, the commit format,
the network rules N2–N7, money and quota. Read that section; it is not
repeated here. What follows is only what parallelism changes.

### 1.1. Your zone is the list in your lane. It is not advice

Each lane below has a **Zone**: the exact paths it may create or modify.

- A path outside your zone is **read-only to you**, including tests.
- Need a change outside it? **Stop the item, write it in `Blocked`
  naming the file and the reason, move to your next item.** You do not
  edit it "just this once" — that is precisely the failure ADR-0012 is
  built to prevent.
- These three files belong to no lane and are frozen tonight:
  `rusterm/store/db.py`, `rusterm/markets.py`, `rusterm/reasons.py`.
  Everything you need from them landed in TASK-19. If something is
  genuinely missing, that is a `Blocked` line, not a migration.

### 1.2. Your branch

```bash
git checkout -b agent/n3-<lane> n3-foundation
```

Commit only there. Never merge another lane into yours. Never rebase
onto another lane. Push your own branch and nothing else.

### 1.3. Your branch must be green on its own

`bash agent/selfcheck.sh` must exit 0 on **your** branch before every
commit and at the end. "Green once everything is merged" is not a
result — the coordinator reviews branches, not intentions.

### 1.4. Bookkeeping, per lane

`agent/REPORT-20-<lane>.md`, append-only, rules R1–R4 from TASK-19 §1.7.
`agent/state/<lane>.json` in the same shape as `STATE.json`, plus
`"lane": "<lane>"` and `"branch": "agent/n3-<lane>"`.

**There is no shared report file tonight.** Do not append to another
lane's report, and do not write `agent/STATE.json` — TASK-21 consolidates.

### 1.5. You do not merge yourself

Finish with a push and this exact line at the end of your report:

```
READY TO MERGE: agent/n3-<lane>  <sha>  selfcheck exit 0  tests <N> passed
```

The coordinator merges. A conflict is then seen by a person instead of
being resolved alone at 4 a.m.

### 1.6. Network budget, per lane

Each lane's budget is stated in the lane. **It is not shared and not
transferable**: a lane that wants more stops at its ceiling and reports
it. Per-host limits are enforced by the gate from TASK-19 F5; do not
raise them in code.

### 1.7. Recorded payloads, per lane

Every lane that touches a network writes a **trimmed** payload under
`tests/data/<its own directory>` and a golden test that resolves each
asserted value back into it by pointer. Ceiling: **256 KB per lane.**
No test may reach the network without a key, and every network test
skips cleanly when its key is unset (N7).

### 1.8. If your source has changed since it was measured

`agent/REPORT-MARKETS.md` was measured on 09–10.09.2026. If a host now
answers differently, that is a **finding**: record request, status and
bytes, do the offline half of your lane, and stop. Do not redesign the
channel, do not go looking for a mirror, do not defeat a block.

---

## 2. The lanes

Ordered by value. If fewer than ten processes are available, run them in
this order. **L1–L4 are independent of each other. L5 must finish before
L6 starts** — it is the only ordering constraint in the fan-out, and
they are written as two lanes rather than one because L5 is large,
deterministic and testable on its own.

---

### L1 — Korea: the official API, and the first non-EDGAR market

**Zone:** `rusterm/providers/dart.py`, `tests/test_market_kr.py`,
`tests/data/dart/`.
**Budget:** 25 requests. **Key:** `RUSTERM_DART_KEY`.

Measured (REPORT-MARKETS): `engopendart.fss.or.kr/engapi/list.json`
answers 200 with `{"status":"100","message":"Authentication Keys is
missing."}` when unkeyed — the API is alive and wants a free registered
key. English filings and XBRL downloads are available; no bot wall.

- `DartProvider(DisclosuresProvider)` declaring host, 2/s, its nightly
  ceiling. No key → `ConfigError` value and the offline path (N2).
- `can_auto_ingest` (TASK-19 F3) answers truthfully for a `corp_code`.
- Facts normalise through the **existing `ifrs-full` dictionary** built
  for Canada in TASK-18. If a Korean tag is genuinely absent from it,
  that is a `Blocked` line naming the tag — `concepts.py` is outside
  your zone.
- **Three Korean issuers** recorded and trimmed.

**Done when:** `python3 -m pytest tests/test_market_kr.py -q` green with
`RUSTERM_DART_KEY` unset (network tests skip) and with it set; a golden
test resolves every asserted value back into the recorded payload by
pointer; a measure table `measure -> n/3 + reasons` is in the report.

---

### L2 — Brazil: the regulator ships files, not an API

**Zone:** `rusterm/providers/cvm.py`, `tests/test_market_br.py`,
`tests/data/cvm/`.
**Budget:** 10 requests (the files are large — see below).

Measured: `dados.cvm.gov.br` lists directories at 200;
`dfp_cia_aberta_2024.zip` HEAD → 200, 13 396 366 bytes,
`Last-Modified: 2026-09-06`. There is no public API before 2026–2028.
The RAD portal timed out once and is **not** your channel.

- The unit of collection is a **dataset**, not a document: CSV/ZIP
  (DFP/ITR/FCA/cadastro). Design for that instead of pretending it is
  per-issuer — `can_auto_ingest` consults the cadastro index.
- **HEAD before GET, always.** A 13 MB body is never fetched to answer
  "has it changed": compare `Last-Modified`/`Content-Length` first.
  Downloaded archives never enter git (N5) — only the trimmed slice does.
- The recorded payload is a **slice of a few rows for three issuers**,
  not the archive. 256 KB ceiling is not a suggestion.

**Done when:** `python3 -m pytest tests/test_market_br.py -q` green
offline; a test proves the HEAD-first path issues **zero** GETs when the
recorded `Last-Modified` is unchanged; three Brazilian issuers produce a
measure table in the report.

---

### L3 — Australia: open endpoints, and the caution they need

**Zone:** `rusterm/providers/asx.py`, `tests/test_market_au.py`,
`tests/data/asx/`.
**Budget:** 15 requests.

Measured: the legacy `/asx/1/...` route is **dead** (404 "uri-not-found")
— do not build on it. `asx.api.markitdigital.com/asx-research/1.0/
companies/<code>/{header,announcements}` answers 200 JSON without
authentication. `prevBusDayAnns.do` returns a 1.2 MB HTML firehose.

- Build on the markitdigital JSON routes. The official route is the
  commercial ASX DataAPI and is out of scope.
- **This is a channel without a contract** (ADR-0010 §5). Say so in the
  module docstring: polite rate, only the headers needed for an answer,
  no bulk pull, no block circumvention. 403/429 → `source_unreachable`
  and stop (N4).
- The market's `access` is `partial`: an ASX code with no machine-
  reachable disclosures must return `manual_import_required`, not a
  hollow issuer. That path is as important as the happy one.

**Done when:** `python3 -m pytest tests/test_market_au.py -q` green
offline; a test drives the `partial` refusal path and asserts **zero**
`issuer` rows created; the docstring carries the no-contract note.

---

### L4 — US-OTC: how deep the free channel actually goes

**Zone:** `rusterm/providers/otcmarkets.py`, `tests/test_market_otc.py`,
`tests/data/otcmarkets/`.
**Budget:** 15 requests.

Measured, and this is the one to read carefully: with a full browser
header set, `otcapi/market-data/active` returns 200 JSON (12 867
records) and `otcapi/company/{SYM}/financial-report` returns 200 JSON
(the disclosure list and its metadata). `profile/full` and the document
`/content` routes stay soft-blocked. Roughly 882 OTC issuers report to
the SEC and already work through EDGAR.

So the honest shape is: **index and metadata are reachable; document
bytes are not.**

- SEC-reporting OTC issuers keep going through `edgar` — do not
  re-route what already works.
- The new provider covers OTC-only issuers to the depth that exists:
  the disclosure index and its metadata. A document whose bytes are
  unreachable yields `manual_import_required` naming the filing, so the
  user can fetch that one PDF and import it (ADR-0011).
- Headers: **only what the host needs to answer.** This is a
  no-contract channel; the rule from L3 applies identically. Do not
  escalate headers to defeat the `/content` block — it is a stop.

**Done when:** `python3 -m pytest tests/test_market_otc.py -q` green
offline; a test asserts the `/content` path yields
`manual_import_required` with the filing named, and never a retry loop;
the report states, with counts, how many of the recorded issuers reach
metadata and how many reach documents.

---

### L5 — Files become pages, deterministically

**Zone:** `rusterm/manual/extract.py`, `tests/test_manual_extract.py`,
`tests/data/manual/`.
**Budget:** 0 requests. This lane never touches a network.
**L6 depends on you. Finish and push before L6 starts.**

Implement the ① contract from ADR-0011 against the interfaces TASK-19 F8
already fixed. Do not change the interface — L6 is coding against it.

- Format detected **by content, not by extension**. A `.txt` holding a
  PDF header is a PDF.
- Standard library: `.txt`, `.md`, `.csv`, `.tsv`, `.json`, `.htm`,
  `.html`. Library-backed: `.pdf`, `.docx`, `.xlsx`. A missing library
  is `format_unsupported` **as a value, naming the package** — never an
  exception, never silence.
- A page with no text layer is `no_text_layer`. **There is no OCR in
  this project** and you are not to add one.
- PDF text is extracted **sorted by coordinates so table rows read
  across, not down columns.** This is the single most valuable lesson
  from the user's `~/TextConv/rusconv` prototype, and getting it wrong
  poisons everything L6 does.
- Test fixtures are **generated by the test**, small and synthetic
  (`fixtures/` stays synthetic, N6). Do not commit a real annual report.

**Done when:** `python3 -m pytest tests/test_manual_extract.py -q` green
with **every** optional library absent (all such formats return
`format_unsupported`) and again with them present; a test builds a
two-column table and asserts the extracted line reads across; the same
file extracted twice gives byte-identical pages and the same `sha256`.

---

### L6 — Pages become records, and records earn the right to be facts

**Zone:** `rusterm/manual/records.py`, `rusterm/manual/pipeline.py`,
`rusterm/cli/__init__.py` (**the `import` subcommand only** — you own
CLI tonight; no other lane may touch it), `tests/test_manual_pipeline.py`.
**Budget:** 0 network requests. **Model calls: 60 maximum, free models
only.** **Starts after L5 is pushed.**

Contracts ② and ③ from ADR-0011.

- `rusterm import <path> --issuer <ticker> [--market <code>]`.
- Extraction goes through `rusterm/providers/llm_api.py` (TASK-19 F6).
  **No key → the command stops after ① with a clear message.** No local
  model, no second option, no fallback (ADR-0011 ②) — the user gave one
  option deliberately.
- Categories exactly `financial` | `physical` | `other`.
- Every record carries a **verbatim quote and a page number**. A record
  without a quote is dropped whole, and the count of dropped records is
  reported.
- `verify` from TASK-19 F8 decides `verified`. `verified=no` records are
  **stored and marked**, and their facts get `manual_unverified` — such
  a fact appears in the source card and the export but **enters no
  formula's numerator** (ADR-0011 ③).
- Facts get `source_kind='manual'` and locator
  `sha256:<hash>#page=<N>`; lineage carries model name and prompt
  version. **A manual fact never overwrites a provider fact.**
- Re-importing the same file is idempotent: same `sha256`, no duplicate
  rows. Assert it by count.

**Done when:** `python3 -m pytest tests/test_manual_pipeline.py -q`
green with `RUSTERM_LLM_API_KEY` unset (fake client) and with a dummy
value; a test asserts a `manual_unverified` fact is absent from every
measure while present in the export; a test asserts the same file
imported twice leaves the row counts unchanged; the report states how
many records survived verification out of how many the model produced.

---

### L7 — The model behind the API, exercised for real

**Zone:** `rusterm/providers/llm_api.py`, `rusterm/core/llm.py`,
`tests/test_llm_api.py`.
**Budget:** 0 network requests to data sources. **Model calls: 100
maximum, free models only.**

TASK-19 F6 built the seat. This lane makes it survive a real endpoint.

- Retries with backoff on 429 and 5xx; **2 attempts then give up as a
  value** (N3/N4). A refusal is never worked around.
- Timeouts on connect and read, both explicit, both tested.
- A malformed or truncated model response is a **value**, never an
  exception and never a silent empty result.
- Try **at least three different free models** through the configured
  endpoint and record, per model: name, latency, whether the response
  parsed, and how many records survived `verify`. This table is the
  point of the lane — the user will choose the production model from it.
- The production model is `glm-5.3-flash`; a paid key is not available
  tonight, so record what free models do and **do not** pin a default
  that needs money.
- **The key is never logged, echoed, committed, or written into a
  report.** Assert it: a test greps every produced artefact for the key
  value and fails if found.

**Done when:** `python3 -m pytest tests/test_llm_api.py -q` green with
no key (every network test skips) and with a dummy key (fake transport);
the three-model comparison table is in the report; the key-leak test
exists and passes.

---

### L8 — The terminal shows where a number came from

**Zone:** `rusterm/tui/`, `tests/test_tui_model.py`.
**Budget:** 0 requests.

- The list screen gains a **market** column showing the registry code.
- The card screen marks each number's `source_kind`: a provider number
  and a manual number are distinguishable **at a glance**, and a
  `manual_unverified` number is visibly not trusted.
- The source panel shows the manual locator (`file, page N`) in place of
  a URL for manual facts.
- Rules unchanged: the TUI computes nothing, writes nothing, and never
  reaches a network. Content is built by pure functions in `model.py`
  and tested headless; `curses` only paints (ADR-0009).

**Done when:** `python3 -m pytest tests/test_tui_model.py -q` green; a
test asserts the model's row for a manual unverified fact differs from a
provider fact in a field a renderer can key on; no `curses` import is
needed by any test.

---

### L9 — Provenance survives the export

**Zone:** `rusterm/core/export.py`, `tests/test_snapshot_export.py`.
**Budget:** 0 requests.

- Every exported fact carries `source_kind`, and manual facts carry the
  document hash and page.
- A consumer of the export can answer "was this number filed with a
  regulator or typed out of a PDF by a model?" **without** opening the
  database.
- Existing export fields and their order do not change — this is an
  addition. Existing golden expectations must still pass untouched.

**Done when:** `python3 -m pytest tests/test_snapshot_export.py -q`
green; a test asserts every pre-existing exported field kept its name
and position; a test round-trips a manual fact and finds its hash and
page.

---

### L10 — The evidence for the next coordinator

**Zone:** `docs/adr/0013-*.md` (**a new ADR only** — the rest of `docs/`
is frozen by check 10), `agent/REPORT-20-L10.md`.
**Budget:** 20 requests.

The one lane whose product is knowledge rather than code.

- Re-probe the four channels of the new markets **plus** New Zealand,
  Singapore and Russia from `agent/REPORT-MARKETS.md`, and record what
  changed since 09–10.09.2026. Same method: exact request, exact status,
  exact bytes.
- Write `docs/adr/0013-poryadok-dobavleniya-rynka.md`: the procedure for
  adding market number seven, derived from what L1–L4 actually cost
  tonight — not from theory. What is one registry row, what is a
  provider file, what is a payload, what is a taxonomy gap, and how many
  hours each took.
- Where a lane hit a taxonomy gap in `ifrs-full`, collect the tags into
  one list. `concepts.py` is outside every lane's zone tonight; TASK-21
  closes them in one pass, and it needs the list.

**Done when:** the ADR exists and `bash agent/selfcheck.sh` exits 0
(check 10 permits **new** ADRs and nothing else in `docs/`); the probe
table names every host with status and bytes; the taxonomy-gap list is
in the report even if empty.

---

## 3. Closing the shift, per lane

No new item after 09:30. Each lane appends `## HANDOFF` to **its own**
report:

```
Lane:            <L1…L10>
Branch:          agent/n3-<lane>
Status:          DONE | PARTIAL | BLOCKED
Items done:      …
Items not done:  … and why
Zone respected:  yes | no — and exactly which foreign file you needed
selfcheck:       exit code, and the "Итог" line
Tests:           N passed, N skipped, N xfailed
Payload:         du -sk tests/data/<yours> — must be under 256 KB
Network:         requests used of <your budget>
Model calls:     N of <your ceiling>, which models
Secrets:         confirm no key in git, report or log
READY TO MERGE: agent/n3-<lane>  <sha>  selfcheck exit 0  tests <N> passed
```

The last line is what the coordinator greps for. A lane that cannot
write it honestly writes `NOT READY: <reason>` instead — that is a
respectable outcome, and a false green is not.
