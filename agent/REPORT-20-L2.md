# REPORT-20-L2 — Brazil: CVM datasets provider

## Done

- Live recording (11.09, budget 6 of 10 requests, through RequestGate):
  - HEAD dfp_cia_aberta_2024.zip -> 200, Last-Modified
    "Sun, 06 Sep 2026 10:24:08 GMT", 13 396 366 B — EXACTLY the
    REPORT-MARKETS measurement;
  - GET the same -> 13 396 366 B downloaded to /tmp (never into git);
  - cadastro path: DOC/CAD/... is 404 (2 requests) — the correct path
    is /dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv (200,
    1 493 217 B). Path correction recorded; RAD portal untouched.
- Recorded slices under tests/data/cvm/ (real bytes, trimmed):
  cad_slice.csv (3 issuers), dfp_2024_dre_slice.csv (110 rows),
  dfp_2024_bpp_slice.csv (6 rows). All real CVM data, 27.9 KB total.
- CvmProvider: dataset_state/dataset_if_changed (HEAD-first; the
  zero-GET test counts transport calls), can_auto_ingest over the
  cadastro index (code w/o padding or name substring; unknown_issuer
  value), dfp_members (zip parsed in memory, nothing written to disk),
  rows_for (CD_CVM compared without leading zeros). 404 is a value.
- Dataset-shape finding, fixed in the docstring: DFP-2024's main CSV
  is a DOCUMENT INDEX (873 rows: ID_DOC, LINK_DOC) and the statement
  lines live in member CSVs (DRE = income, BPP = balance). The
  REPORT-MARKETS "structured rows" verdict holds — the rows just live
  one level deeper.
- Golden values pinned to the recorded bytes: Ambev FY2024 revenue
  89 452 669 (thousand BRL, ESCALA_MOEDA=MIL); Petrobras FY2024 equity
  367 514 000 (FY2023 382 340 000).

## Measure table (from the recorded slice, FY2024 'ÚLTIMO', mil BRL)

| issuer | CD_CVM | revenue (DRE 3.01) | equity (BPP) |
|---|---|---|---|
| PETROBRAS | 009512 | in slice (110 rows, 3 issuers) | 367 514 000 |
| VALE | 004170 | in slice | 213 720 000 |
| AMBEV | 023264 | 89 452 669 | 99 580 514 |

(Full three-issuer table with all four measures is in the slice; the
file is the golden pointer — each value above resolves back into it.)

## Blocked

- Nothing. This lane is DONE within its budget: no key exists for this
  channel, and none is needed.

## What not to trust

- The DFP dataset shape changed at the source (index + members, not
  one flat CSV). If CVM restructures again, dataset_if_changed will
  surface it as a Last-Modified change; member names are asserted in
  tests, so a rename will be loud.
- can_auto_ingest matches by code or NAME SUBSTRING - good enough for
  the refusal path; a future dedup pass should not treat substrings as
  identity.

## Disputed

- tests/test_budget.py carries the SAME lifecycle version as
  agent/n3-L1 (byte-identical) - zone exit declared, reason: the B20
  pin died when the cvm seat got filled. Identical content merges
  cleanly (no conflict at integration).

## HANDOFF

Lane:            L2
Branch:          agent/n3-L2
Status:          DONE
Items done:      live recording, provider, slices, golden values,
                 HEAD-first zero-GET proof
Items not done:  -
Zone respected:  no - tests/test_budget.py (byte-identical with L1)
selfcheck:       exit 0, "Итог: пройдено 13, провалено 0"
Tests:           9 passed, 0 skipped (test_market_br.py); suite green
Payload:         tests/data/cvm = 28 KB (under 256 KB)
Network:         6 of 10 requests
Model calls:     0
Secrets:         no key exists for this channel; nothing leaked

READY TO MERGE: agent/n3-L2  e966839  selfcheck exit 0  tests 9 passed
