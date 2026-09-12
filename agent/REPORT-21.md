# REPORT-21 — TASK-21: merge of ten lanes, end-to-end paths, M8

## Done

### §0.1/§0.2 — ground truth and the merge (night part, commit a99dfbc)

- Lanes present as branches (`git rev-parse --verify agent/n3-L*`,
  2026-09-12): L1 f1f12f2, L2 e41379a, L3 282f8e3, L4 b9977ff,
  L5 8e3a293, L6 3e9dddc, L7 36d35fc, L8 00e05b6, L9 477629d,
  L10 6f70125 — all ten exist, none absent.
- `python3 -c "import rusterm.providers as p; print(p.available())"`:
  `['asx', 'cvm', 'dart', 'edgar', 'llm-api', 'otcmarkets',
  'synthetic-disclosures', 'synthetic-market']`.
- All ten merged in ADR-0017 order L1..L10; journal `agent/MERGE-3.md`;
  one conflict, inside `agent/` only (REPORT-20-000.md, union per
  §0.2.5); acceptance exit 0 after every lane. L8 was RED on its own
  branch once, re-run per the flicker rule (000), two clean runs, then
  merged.

### H1 — one truth about markets (DONE)

- `cmd_markets` prints per registry row: code, jurisdiction, venue
  kind, provider, identifier, default taxonomy, access,
  provider_status, issuer count in the local base.
- `python3 -m rusterm.cli markets` on a fresh root: six rows, exit 0
  (US/CA/OTC/KR/BR/AU; every provider module present → implemented).
- Absent-module path: tests/test_markets.py
  ::test_markets_consolidated_provider_status_and_issuers stubs the cvm
  module away, asserts the exact string `provider_not_implemented`,
  exit 0, and no ANSI in piped output (B11).

### H3 — currency firewall (DONE; inherited WIP finished here)

- Root cause of the inherited 3 red tests:
  `currency_guard` looked the concept up only in
  `formulas.MEASURE_UNIT_KINDS`; as-reported inputs (`revenue`,
  `total_equity`) are not in that map, so the guard was silently off.
  Fix: new `currency_bound()` in peers.py — a concept absent from the
  unit-kind map is a money input of map V0 and is currency-bound.
- `AggregateMeasure` now carries `currency` when a single currency is
  recorded; the mismatch branch reports `method_version=industry.v1`.
- `tests/test_currency_firewall.py` rewritten to the program's real
  thresholds (percentile needs >=5 peers and a pass-1 own value;
  aggregate needs >=8): a 6-issuer mixed set (3 USD + 3 KRW) —
  net_margin percentile computes, revenue percentile returns
  `currency_mismatch: KRW, USD`; single-currency set behaves exactly as
  before; sector aggregate refuses the mixture and states `USD` for an
  8xUSD set.
- Full suite after the fix: `python3 -m pytest` →
  `516 passed, 3 skipped in 99.10s`, exit 0. goldens m2/m6-ca untouched
  (their tests are part of the suite).

### H5 — refusal path is first-class (DONE)

- `tests/test_refusal_loop.py`: add non-ingestible issuer →
  manual_import_required with the exact import command → explicit
  offline issuer creation → import command runs → facts with
  source_kind='manual', unverified kept out of formulas. 1 passed.

### H7 — the guard against masked exit codes (DONE)

- `tests/test_selfcheck_guard.py`: 3 passed — status read from file
  before piping; selfcheck refuses a dirty tree (behavioural, P3/P4);
  `agent/acceptance.sh` byte-identical to origin/main.

### H8 — secrets proven absent (DONE)

- `tests/test_secrets_absent.py`: 3 passed — no tracked file matches
  key shapes (scan covers `git ls-files`, 298 tracked files); ConfigError
  carries the variable NAME, never a value; doctor reports set/unset by
  name only.

### H4 — end to end per landed market (DONE)

- `tests/test_h4_markets_e2e.py`, 6 tests, all offline on recorded
  payloads. Full paths (US/CA/OTC) run add → ingest --source edgar →
  snapshot → export --format json through `cli.main` with the provider
  class patched to a recorded transport; KR/BR/AU run the honest
  refusal/partial paths through the real provider code (adapters only
  for the EDGAR-centric resolve/venues, same as the L3 lane did).
- Export carries the market code literally: `instrument_id` is
  `<market>-<ticker>` (cmd_add) and the export JSON's
  `snapshot.instrument_id` asserts equal.
- `python3 -m pytest -k e2e -q` green; full suite after H4:
  522 passed, 3 skipped, exit 0.

### H2 — measure table per landed market (recomputed on recorded payloads)

One issuer per market, snapshot v1, export json, the ten pass-1
measures (formulas §3 V4). Real output of the recomputation run:

| market | issuers | measures with value | the rest, named |
|---|---|---|---|
| US (AAPL, edgar) | 1 | 10/10 | — |
| CA (RY, edgar, ifrs-full) | 1 | 3/10 | asset_turnover, net_margin, roe compute |
| OTC (CPTP, edgar, us-gaap) | 1 | 3/10 | effective_tax, net_margin, roe compute |
| KR | 0 | n/a | refusal `dart_key_unset` at add; no key, no payloads |
| BR (AMBEV, cvm) | 1 | 0/10 | issuer created from the recorded cadastro slice; CLI has no cvm collection channel yet; native columns unmapped (H2 gap list) |
| AU (BHP, asx) | 1 | 0/10 | issuer created from recorded header+announcements; no fundamentals contract (ADR-0010 §5) |

- golden_m2.json / golden_m6_ca.json untouched — their tests run
  inside the 522.
- No tag added to `rusterm/normalize/concepts.py`: no lane recorded a
  concrete missing ifrs-full tag against a concrete payload (rule H2).

### H9 — milestone M8, stated with its evidence (DONE)

Markets that reach data, by provider (`python3 -m rusterm.cli markets`
— six rows, every module present; quoted under H1). End-to-end proof:
`tests/test_h4_markets_e2e.py`, 6 passed:

```
US:  issuers 1, measures 10/10, export ok   (edgar, AAPL)
CA:  issuers 1, measures 3/10,  export ok   (edgar, RY; asset_turnover, net_margin, roe)
OTC: issuers 1, measures 3/10,  export ok   (edgar, CPTP; effective_tax, net_margin, roe)
KR:  issuers 0, refusal dart_key_unset      (dart; no key, no payloads)
BR:  issuers 1, measures 0/10,  export ok   (cvm; CLI channel not wired yet)
AU:  issuers 1, measures 0/10,  export ok   (asx; no fundamentals contract)
```

Currency each market is stated in — an honest finding, not a claim:
**no provider populates fact.currency yet** (the parsers write None;
`SELECT DISTINCT currency FROM fact ...` over the recorded US/CA/OTC
payloads returns `[None]` for each). The currency string travels in
`fact.unit` (the companyfacts units key), exactly as before M8. The H3
firewall is armed and covered by tests, but on today's sets it sees
"no recorded currency" and — by the documented Disputed trade-off —
computes as before. `AggregateMeasure.currency` fires only when facts
record one (proven synthetically in test_currency_firewall).

Manual-import loop (`tests/test_refusal_loop.py`, 1 passed): records
produced 1, verified 0, rejected 0; the unverified manual fact is
marked in the snapshot and enters no formula (asserted in the test).

LLM path: the model comes only from the environment, never pinned to a
paid default (REPORT-20-L7). The three-free-model comparison was NOT
run: the lane had no key, 0 of 100 model calls (L7 HANDOFF, quoted in
the lane fold below).

M8 does **not** cover, named honestly:
- KR data end to end — blocked on the DART key; today the market
  honestly refuses (`dart_key_unset`).
- BR/AU collection channels in the CLI — `ingest` speaks only edgar
  and synthetic; cvm/asx issuers are addable but not collectable.
- BR measures — native columns (CD_CONTA and friends) are unmapped to
  ifrs-full (L10 gap list; H2 rule kept a tag from being guessed).
- fact.currency — no provider writes it; the firewall waits for data.
- Sector aggregates — need a verified peer set of 8+; no recorded
  payload set reaches that today.
- LLM free-model scoring — no key (L7).

Lane fold (what each lane reported at its end, from
`agent/state/L*.json`, folded into `agent/STATE.json` this commit):
all ten ended `awaiting_review` at item HANDOFF — L1 172c813,
L2 e966839, L3 1fc1565, L4 66edb64, L5 e4f55f1, L6 d071705, L7 4eb1bd2,
L8 66b7677, L9 0747831, L10 9af89da. L7 recorded `Model calls: 0 of
100 (no key)` and the item "three-free-model live table - no key" as
not done.

### H6 — doctor learns the new shapes (DONE)

- `rusterm/store/doctor.py` (SQL stays in the store layer) now checks:
  1. documents in both directions — a `document` row whose body file
     is missing from the raw store, and an imported file
     (raw provider='manual-import') without a `document` row;
  2. facts with source_kind='manual' whose document does not exist;
  3. MARKETS registry rows whose provider module is absent (same
     importlib door as H1; a gap names code:provider);
  4. per-market coverage — issuers, facts, last successful collection
     (issuer_ingest_state MAX(updated_at)) keyed by the instrument_id
     market-code prefix, so OTC does not double-count US.
- Report payload gains additive keys: documents,
  manual_facts_missing_document, registry_gaps, market_coverage.
- `tests/test_h6_doctor.py`, 4 tests: healthy db → ok, exit 0; damaged
  db (all four shapes deliberately inflicted) → every problem named,
  CLI exit 1 with all four phrases in the printed json.
- Full suite after H6: 526 passed, 3 skipped, exit 0.

## Blocked

- none

## H2 — taxonomy gaps (no code change; see the rule)

- L10 gap list: BR native columns (CD_CONTA/DS_CONTA/VL_CONTA/
  ESCALA_MOEDA) are not mapped to ifrs-full; KR tags unknowable until
  the key exists; AU/OTC have no XBRL tags.
- No lane recorded a concrete missing ifrs-full tag against a concrete
  recorded payload → per the H2 rule nothing is added to
  `rusterm/normalize/concepts.py`. A tag without a payload is guessing.
- The recomputed measure table per landed market: see the H2 subsection
  of Done below (appended with the H4 commit).

## What not to trust

- Root `agent/STATE.json` was stale (still TASK-19) at the start of
  this session; repointed in the same commit as this report.
- The night part (merge) was verified by the night session, not
  re-verified line by line here; MERGE-3.md is its record.
- H1/H5/H7/H8 code and tests were inherited uncommitted from the night
  session; H3 was inherited broken (3 red tests) and finished here —
  the rewrite of its test file is documented under H3.
- H4's BR/AU "export ok" proves the honest-empty path only: zero
  measures, every row with a named reason.

## Disputed

- Legacy sets where facts record NO currency behave as before (the
  guard counts no party and invents no USD). A mixed set where only
  some facts carry currency and the rest are blank computes as that one
  currency — blanks are not flagged. This is the night session's
  legacy-compatibility trade-off; closing it needs a missing_data sweep
  over legacy rows and may move goldens. Coordinator's call.

## HANDOFF

Status:          DONE
Lanes merged:    L1-L10, all ten branches existed and merged (agent/MERGE-3.md)
Items done:      §0.1, §0.2, H1, H2 (measure table; no code change per rule), H3, H4, H5, H6, H7, H8, H9
Items n/a:       H2 as a code change — no concrete ifrs-full tag with a recorded payload; H10 — the 09:30 line passed long before H9 closed, and the queue continues with TASK-22
Acceptance:      Итог: пройдено 13, провалено 0 — Принято; SELFCHECK OK, captured exit status 0 at the commit
Tests:           526 passed, 3 skipped, 0 xfailed
Schema:          unchanged (_SCHEMA_VERSION 40)
Markets reached: US 10/10, CA 3/10, OTC 3/10 (all edgar); BR 0/10 (cvm, addable, no CLI channel); AU 0/10 (asx, partial, no fundamentals contract); KR refusal (dart, no key) — see the H2 table and the H9 section
Golden unchanged: golden_m2.json and golden_m6_ca.json untouched; both golden tests inside the 526
Manual import:   records produced 1, verified 0, rejected 0 (tests/test_refusal_loop.py; the manual fact stays unverified and out of formulas)
Secrets scan:    298 tracked files scanned, 0 hits
M8:              reached, with named gaps — see the H9 section (KR key, BR/AU CLI channels, BR column mapping, fact.currency unwritten, no verified 8-peer set, no LLM key)
Network:         0 requests used by this session (all evidence from recorded payloads)
Model:           app llm_calls 0; GLM-5.3-Flash
Pushed:          yes, every work commit pushed to origin/agent/night-3 as it landed
Questions for the coordinator:
1. Disputed: blank-currency legacy sets — close now (a missing_data sweep) or keep the trade-off until a provider starts writing fact.currency?
2. BR/AU issuers are addable but the CLI has no collection channel for cvm/asx yet (ТЗ-23/24 territory) — confirm the sequencing.
3. Parsers write fact.currency = None everywhere; should wiring providers to record currency precede ТЗ-23 (quotations), so the H3 firewall guards real data, not synthetic tests?

NOW: H9, step 3
