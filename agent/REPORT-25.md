# REPORT-25 — TASK-25: M11 governance traffic light (offline path)

## Done

- §0: branch `agent/night-7` cut from `agent/night-6` head (547ed44);
  selfcheck STATUS=0; `_SCHEMA_VERSION` read from the file: 41.
- **SEC_UA UNSET — payloads not recorded** (printenv exit 1): the
  offline item set of §0 — P1, P2, P7 (synthetic proxy through the
  deterministic verify), P8, P9, P10, P11. P3/P4/P5/P6 (live probes,
  the ownership provider, recorded payloads) are blocked.

### P1 — the producer (DONE)

- `governance.py`: `produce_assessments(governance_repo, instrument_id,
  as_of, inputs, now=None)` — calls the five indicators with whatever
  inputs exist and writes five `governance_assessment` rows via
  `GovernanceRepo.record`; every row carries indicator, colour, as_of,
  lineage_ref, reason. Missing input -> grey `not_collected` ON THE
  RECORD, not zero rows. Wired into snapshot build via an optional
  `governance` resolver (cmd_snapshot/export/verify wire the producer
  over the manual records).
- Tests: synthetic inputs -> five rows, five colours, lineage on
  every row; no inputs -> five grey rows `no_data:not_collected`;
  `tui/model.py` untouched (it already reads them).

### P2 — grey stops being one colour for all reasons (DONE)

- `GREY_REASONS` — four named states with the action a user can take:
  not_collected (run refresh/import), source_has_no_disclosure
  (nothing to do), collected_unparsed (re-import), manual_unverified
  (verify by hand), plus stale (P9). The card now carries each
  indicator's reason text (`tui/model.py` card_rows), asserted
  through the pure functions.

### P7 — the proxy goes through manual import, not regex (DONE, offline)

- `GOVERNANCE_RECORD_MAP` + `governance_inputs_from_records()`:
  other-category records with verbatim quote and page map to indicator
  inputs; lineage_ref = document sha + page. A verified
  `independent_directors_share=0.6` turns the indicator green with
  that lineage; a `verified=no` extraction leaves it grey — never a
  colour from an unverified read (asserted).

### P8 — every colour is provable (DONE)

- `_assess` raises on empty lineage (pre-existing invariant);
  `GovernanceRepo.latest()` prefers override rows
  (`lineage_ref` prefix `override:`); the producer skips indicators
  with an override — a user correction survives recomputation with its
  own provenance (asserted).

### P9 — last year's proxy does not describe today's board (DONE)

- `STALENESS_DAYS = 550` (annual proxy cadence + half-year slack —
  the doc names no number; flagged to the coordinator). A colour older
  than the threshold turns grey `stale:assessed:<date>` under a fake
  clock (asserted); a fresh one keeps its colour.
- doctor: governance ages land with the P10 batch (below).

### P10 — the traffic light on screen and in export (DONE)

- card_rows: five indicators, five colours, no collapsing, each with
  reason + lineage_ref; export `snapshot_to_json` gained an additive
  `governance` section (indicator, colour, reason, lineage) — without
  the parameter the output is byte-identical (asserted); existing
  fields keep names and order.

### P11 — milestone M11, honest state (offline)

- Per indicator across the collected issuers: all five are grey for
  every issuer — because nothing has been collected yet (no SEC_UA,
  no ownership corpus); every grey row now states its reason on the
  record (`no_data:not_collected`), which is the night's real
  deliverable: the producer, the reasons, the override and the
  staleness machinery are in place and tested (7 tests).
- M11 does **not** cover: Forms 3/4/5 collection and the insider_net
  colour (P3-P5 blocked on SEC_UA); the DEF 14A probe (P6); real
  model-side proxy extraction with verified-but-wrong accounting
  (model calls need a key — 0 of 60 used).

## Blocked

- SEC_UA UNSET — payloads not recorded: P3 (live Forms 3/4/5 probe),
  P4 (ownership provider + 256 KB recorded payload + golden), P5
  (insider_net on real filings), P6 (DEF 14A probe) wait for the
  contact header.

## What not to trust

- No live EDGAR probe was made; every governance assessment in tests
  comes from synthetic inputs/records.

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL (offline branch per §0: SEC_UA UNSET)
Items done:      §0, P1, P2, P7, P8, P9, P10, P11
Items not done:  P3, P4, P5, P6 — blocked on SEC_UA and a recorded ownership corpus; P12 — the 09:30 condition not met, the queue continues with TASK-26
Acceptance:      Итог: пройдено 13, провалено 0 — Принято; SELFCHECK OK
Tests:           604 passed, 4 skipped, 0 xfailed
Schema:          unchanged (41)
Golden:          golden_m2.json and golden_m6_ca.json unchanged; inside the 604
Probes:          not made — SEC_UA UNSET; no payload simulated
Indicators:      all five grey for every issuer, each grey on the record with a named reason
Grey reasons:    not_collected / source_has_no_disclosure / collected_unparsed / manual_unverified / stale — distinct, asserted
Proxy path:      synthetic verified record -> green with quote lineage; verified=no -> grey manual_unverified (asserted)
Payload:         none recorded (du: no tests/data/edgar/ownership yet)
Network:         0 requests used of the 60 budget
Model:           app llm_calls 0 of 60; GLM-5.3-Flash
Pushed:          yes, every work commit pushed to origin/agent/night-7
Questions for the coordinator:
1. STALENESS_DAYS = 550 is derived (the doc names no number) — confirm or set.
2. 10b5-1 sales remain included per the doc's open question — keep, or split the indicator?

NOW: P11, step 3
