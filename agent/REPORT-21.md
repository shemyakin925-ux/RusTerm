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
- H4 lines and the H2 measure table are appended only after their
  commits exist.

## Disputed

- Legacy sets where facts record NO currency behave as before (the
  guard counts no party and invents no USD). A mixed set where only
  some facts carry currency and the rest are blank computes as that one
  currency — blanks are not flagged. This is the night session's
  legacy-compatibility trade-off; closing it needs a missing_data sweep
  over legacy rows and may move goldens. Coordinator's call.

## HANDOFF

Status:          PARTIAL
Lanes merged:    L1-L10, all ten branches existed and merged (agent/MERGE-3.md)
Items done:      §0.1, §0.2, H1, H2 (table; no code change), H3, H4, H5, H7, H8
Items n/a:       H2 as a code change — no concrete ifrs-full tag with a payload
Acceptance:      first mid-shift run 10/13 — the report-sections guard (no HANDOFF yet) plus check 7 (H1 issuer-count SQL in the CLI; moved to InstrumentRepo.issuer_count); at this commit: Итог: пройдено 13, провалено 0, exit 0
Tests:           522 passed, 3 skipped, 0 xfailed
Schema:          unchanged
Markets reached: US 10/10, CA 3/10, OTC 3/10, BR 0/10, AU 0/10, KR refusal — see the H2 table in Done
Golden unchanged: golden_m2.json and golden_m6_ca.json untouched; their tests inside the 522
Manual import:   records produced 1, verified 0, rejected 0 (tests/test_refusal_loop.py; manual fact stays unverified and out of formulas)
Secrets scan:    298 tracked files scanned, 0 hits
M8:              partial — H6, H9 pending
Network:         0 requests used by this session
Model:           app llm_calls 0; GLM-5.3-Flash
Pushed:          with this commit
Questions for the coordinator:
1. Disputed: blank-currency legacy sets — close now or keep the trade-off?
2. BR/AU issuers are addable but the CLI has no collection channel for cvm/asx yet (ТЗ-23/24 territory) — confirm the sequencing.

NOW: H6, step 1
