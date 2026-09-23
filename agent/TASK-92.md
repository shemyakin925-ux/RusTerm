# TASK-92 — facts that survive ingestion, issuers that stay in their market, a manual import that counts

- **Status: READY**
- **Report:** `agent/REPORT-92.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-92.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Budgets:** network 0, except C1: SEC ≤ 2 requests via
  `RequestGate`. LLM 0 (manual import runs on recorded answers).
- **How to work:** as TASK-90. Rule 9 holds: a new alias or tag enters
  the maps only with the payload that proves it.
- **Place in queue:** after TASK-91, numeric order.

## C0. A superseded fact never reaches a formula (take first)

`rusterm verify` inserts the corrected fact and marks the old one
`superseded_by` — but no reader filters that column:
`SnapshotRepo.as_reported_facts` (repos.py) returns both, and the right
one wins only by the accident of `ORDER BY … ingested_at DESC`;
`SnapshotRepo.latest_annual_fact` (repos.py:506, `ORDER BY period_end
DESC`, no tie-break) returns the **wrong** one. Reproduced on
`3f7dcc9`: NI 100 corrected to 200 → `latest_annual_fact` → `100.0`,
so `pe` and `ps` keep the number the user just corrected.

**Done when:** every fact reader that feeds a measure, a tool or the
window adds `superseded_by IS NULL` (list them in the report, grep
`FROM fact` under `rusterm/store/`); the reproduction above is a test
for `latest_annual_fact`, `as_reported_facts` and a snapshot built
after the correction (`pe` uses 200).

## C1. EDGAR dedup keeps the as-reported original

- `parsers/__init__.py:294-303`: dedup key `(concept, unit, start,
  end)`, the newest `filed` wins. In the real companyfacts API a value
  re-appears in **every later filing** as a comparative; the newest
  copy gets basis `restated` (`determine_basis`: the filing's own
  period ends later), and the as-reported original is moved to
  `result.superseded` — which **no caller persists** (`cli`
  companyfacts ingest, `core/refresh.py:59`, `pipeline.py` pass only
  `parsed.facts`). The class docstring says «ничего не выбрасывается».
- Measured by the reviewer on a synthetic payload shaped like the API
  (three 10-Ks, each with three income-statement years and two balance
  sheets): 17 entries → 9 facts kept, **8 dropped**; only the newest
  year stays `as_reported`; `roe` → `missing_prior_period`. User base,
  AAPL: `roe = missing_prior_period`.
- Why no test saw it: every committed payload is trimmed to one filing
  per period (`companyfacts_m3_*`, `m6_*`: 0 duplicate periods).

Rule: dedup key becomes `(concept, unit, start, end, basis)` — the
as-reported fact is the entry of the filing whose own period ends on
the fact's end (earliest `filed` among those); the restated fact is
the newest later filing's entry. Both are persisted. Remaining
same-basis losers are persisted with `superseded_by` pointing at the
winner (the column exists) — nothing is thrown away.

**Done when:**
- a trimmed **duplicate-preserving** AAPL payload is committed under
  `tests/data/edgar/` (≤ 2 SEC requests; trimmed to the concepts of
  `base_concepts`, provenance line in the report);
- on it: `roe` has a value, and `SnapshotDiff.revisions` lists at least
  one period whose restated value differs, if the payload has one
  (else say so);
- `tests/test_task49_census.py` and BR census goldens unchanged, or
  moved with `было → стало`.

## C2. An issuer's registry id belongs to its market

- EDGAR paths accept any all-digit `registry_id`: `core/refresh.py:83`,
  `cli/__init__.py:431` (companyfacts), `:726` (ownership); the CVM
  path `:608` likewise. `cmd_add` (`:1510`) writes
  `issuer_id=f"cik-{id}"`, `reporting_standard="us_gaap"`, currency
  `"USD"` for **every** market, and BR's `CD_CVM` / KR's `corp_code`
  are digits. `refresh` over a list holding a BR issuer therefore asks
  SEC for CIK = <CVM code> and would store another company's facts
  under it; issuer ids of different markets can collide.
- `--cik` is `type=int` (`:2274`): DART's `00126380` becomes `126380`.

Rules:
- new issuers get the prefix of `Market.identifier`: `cik-`, `cvm-`,
  `dart-`, `asx-`; every collection path checks the prefix of its own
  provider and otherwise returns `unknown_issuer: registry is not
  <provider>` (refresh: a result row with that reason, no request);
- `reporting_standard` from `Market.default_taxonomy`; reporting
  currency from a new table in `markets.py`: US `USD`, BR `BRL`, KR
  `KRW`, AU `AUD`, CA and OTC `XXX` (ISO 4217 «no currency» — the
  column is NOT NULL and nothing reads it today; a guess is forbidden);
- `--cik` is a string, validated per scheme (CIK digits; `corp_code`
  exactly 8 digits);
- existing issuers are not renamed; `doctor` lists `cik-` issuers whose
  jurisdiction is not US/CA as a finding.

**Done when:** tests — refresh with a `cvm-` issuer ⇒ 0 SEC requests
(counting transport) and the reason; `add --market BR` ⇒ `cvm-23264`,
`ifrs`, `BRL`; `add --market KR --cik 00126380` keeps the zeros;
doctor finding on a legacy row.

## C3. A manual import survives a failed model call

`manual/pipeline.py:82` writes the `document` row **before** the model
call (`:99`). A 429 / timeout / unparsable answer returns an error but
the row stays; retrying the same file returns `replay` with 0 records
forever, and the raw bytes were never stored (doctor:
`rows_without_file`).

**Done when:** the document row and the raw bytes are written only
after records parse; test: first call with a 429 transport → error, no
`document` row; second call with a 200 recorded answer → records
stored, `replay=False`.

## C4. Verified manual financial records reach the measures

- `manual/pipeline.py:134` inserts facts with `canonical_concept=NULL`
  (the metric is the model's free text); `as_reported_facts` filters on
  `canonical_concept` ⇒ **no manual fact has ever entered a formula**.
  For AU (announcements only) and every `manual_import_required`
  issuer, manual import is the only route — and it yields zero
  measures.
- `manual/records.py:109` `period_bounds` maps `FY2025` to calendar
  2025 whatever the issuer's `--fye` (AU is 06-30); values like
  `"1,234.5"` with unit `"$m"` fail `float()` silently.

Fixed decisions:
- `MANUAL_METRIC_MAP` in `normalize/concepts.py`: canonical →
  lowercase aliases, each alias with a recorded answer under
  `tests/data/manual/` that proves it (rule 9); version string
  `manual.v1` in `concept_map_version`;
- value: thousands separators stripped; scale from unit tokens
  `thousand|k|'000` → 1e3, `million|m|mn` → 1e6, `billion|bn` → 1e9;
  currency = ISO code in the unit, else the issuer's reporting currency
  unless it is `XXX` (C2), else `None`; unknown unit ⇒ fact stored with
  `canonical_concept` NULL (today's behaviour);
- `FY<yyyy>` uses the issuer's `fye`; no `fye` ⇒ calendar year, named
  in the fact's locator.

**Done when:** on the committed manual fixtures the report names how
many records map; a snapshot for that issuer has ≥ 1 measure whose
lineage points at a `source_kind='manual'` fact; unverified and
near-miss records still never map (test).
