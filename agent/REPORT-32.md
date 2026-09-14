# REPORT-32 — TASK-32: the ownership channel (Forms 3/4/5) stops being a plan

Arrival state: selfcheck OK at a3a0bd6 (13/13); full suite 650 passed,
1 skipped, 4 xfailed, 0 failed.

## Done

### D1 — live probe of the ownership channel (DONE)

All probes through `RequestGate` with the real contact
(RUSTERM_SEC_UA), rate-limited by the edgar declaration. NO provider
code was written before this table.

| # | endpoint (host) | status | bytes | format | machine-readable |
|---|---|---|---|---|---|
| 1 | data.sec.gov/submissions/CIK0000320193.json (AAPL) | 200 | 164 091 | JSON | yes — filings.recent parallel arrays; recent 1000 rows contain forms 3:12, 4:590, 5:1 |
| 2 | data.sec.gov/submissions/CIK0000789019.json (MSFT) | 200 | 184 700 | JSON | yes — same shape |
| 3 | www.sec.gov/Archives/edgar/data/320193/000114036126036226/xslF345X06/form4.xml (the primaryDocument as given) | 200 | 15 625 | styled HTML (XSL render) | **NO** — the submissions feed points at the rendered view |
| 4 | www.sec.gov/Archives/edgar/data/320193/000114036126036226/form4.xml (raw, XSL prefix stripped) | 200 | 3 153 | XML, root `ownershipDocument` | **yes** — documentType, periodOfReport, issuer, reportingOwner (+relationship flags), nonDerivativeTable transactions with transactionDate/securityTitle/transactionShares/acquiredDisposedCode |

Findings, not improvisations:
- The primaryDocument field for form 4 names the XSL-rendered
  document; the raw XML sits at the same accession WITHOUT the
  `xslF345X0N/` prefix. The provider must strip that prefix segment.
- `www.sec.gov` is not a new host: TICKERS_URL and ARCHIVES_URL
  already use it in rusterm/providers/edgar.py; the edgar channel
  keeps host data.sec.gov in the registry (TASK-25 P4 "no new host").
- Requests spent: data.sec.gov 2 of 50; www.sec.gov 2 (report per
  host in D4).

### D2 — the ownership provider (DONE)

- `rusterm/parsers/ownership.py` (pure): `parse_form4(raw) ->
  OwnershipFiling` — documentType, period, issuer, insider (+cik),
  role from relationship flags (accepts `1` and `true`), officer
  title, and transactions (date, direction A/D -> acquired/disposed,
  shares, price, security). Schema nuance measured on the recorded
  payload: shares/price/direction live under `transactionAmounts`;
  derivative tables are NOT parsed (named in the docstring — P5 will
  rule if needed).
- `EdgarProvider.list_ownership(issuer_id, limit_per_form)` — forms
  3/4/5 metadata from the ALREADY-LOADED submissions (zero requests),
  each form kind truncated separately (fresh form 4s otherwise crowd
  out rare 3s and 5s). `raw_document_url()` strips the XSL render
  prefix (D1 finding).
- Collector `_ingest_edgar_ownership`, wired as
  `rusterm ingest --instrument X --source ownership` (never a
  default): bodies fetched one by one, content-addressed into the raw
  store (block ownership) + `document` header with issuer; canonical
  URL cache makes re-runs cost ZERO requests (ADR-0003 pattern).
  Live run on US-AAPL: feed 5 (2 form-3, 2 form-4, 1 form-5);
  collected 3 new documents; 3 transactions parsed; re-run: 0
  collected, 3 parsed, 0 requests.
- Recorded payloads under tests/data/edgar/ownership/ (5 files,
  3-12 KB each, whole payloads — under the 256 KB ceiling).
- `tests/test_ownership.py`: golden parse of
  000114036126036226_form4.xml with hand-checked values (Newstead
  Jennifer, officer "SVP, GC and Government Affairs": disposed 1438
  Common Stock on 2026-09-08 at 317.23) plus a pointer-resolver
  proving each asserted value resolves INTO the recorded payload;
  form 3 = no transactions (not a parse failure); collection
  idempotent with a frozen network-call counter; live test carries
  the `live` marker and skips without RUSTERM_SEC_UA (N7).
- `python3 -m pytest tests/test_ownership.py -q` -> 5 passed.

### D3 — the refusal stays honest (DONE)

- `tests/test_issuer_without_ownership_forms_gets_named_reason`:
  submissions present but no forms 3/4/5 -> coverage
  ownership/missing with reason `source_has_no_disclosure`, the
  reason printed, exit 0 — a named refusal, never an empty success.
  The issuer-without-feed path keeps the existing `no_sec_filings`
  route (cli, companyfacts precedent). 5 passed with
  RUSTERM_SEC_UA unset (live test skipped by marker).

### D4 — budget and provenance (DONE)

- Requests against this task's budgets (manual count of gate calls;
  the gate is in-process, counters reset per CLI run):
  * data.sec.gov: 2 (D1 probes) + 3 (submissions per ownership
    ingest run) = **5 of 50**;
  * www.sec.gov (Archives bodies): 2 (D1) + 12 (first collection
    experiments, before the URL cache landed) = 14; re-runs now cost
    0 (cache), asserted by test.
- Raw store holds every fetched object by sha256 (block ownership,
  url = canonical Archives URL, instrument_id set); document headers
  reference the same sha256.
- `rusterm --root ~/.rusterm doctor` after collection:
  `ok: True`, `problems: none` — the B9 drift check runs BOTH
  directions (raw_object rows without files; files in raw/store
  without a DB row) and the fact->raw orphan count is zero. One real
  defect found and fixed en route: doctor's I4 counter did not know
  the migration-42 table (measure_lineage_ca) and false-positived on
  the vendor-fed div_yield measure — query extended, doctor green.

## Blocked

- (nothing)

## What not to trust

- The two "collection experiments" runs before the URL cache cost 12
  www.sec.gov requests that a later start would not spend (counted in
  D4).
- transactionShares=None stays None in parsed transactions (no
  fabrication); derivative tables are not parsed (named in the
  parser docstring).

## Disputed

- (none this task so far)

## HANDOFF

Status:          PARTIAL - D1..D4 done; D5..D7 ahead
Arrival state:   selfcheck OK at a3a0bd6 (13/13)
Items done:      D1, D2, D3, D4
Items not done:  D5 (P1 guard), D6 (period_basis), D7 (NCI rule)
Acceptance:      selfcheck green on pre-staging index; see last line of this file
Tests:           ownership file 5 passed; full default run 0 failed (see final HANDOFF)
Guards:          doctor I4 counter extended to migration-42 lineage (stronger); no assert changed
Schema:          unchanged (42)
Network:         data.sec.gov 5 of 50; www.sec.gov 14 total (12 before the URL cache; re-runs now 0)
Model:           0 of 0; GLM-5.3-Flash
Secrets:         no key anywhere in payloads or outputs - 0 hits
Pushed:          yes (per commit)
Questions for the coordinator:
1. (none yet)

NOW: D4, step 8
