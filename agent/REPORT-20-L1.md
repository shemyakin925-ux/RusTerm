# REPORT-20-L1 — Korea: Open DART provider

## Done

- Branch agent/n3-L1 cut from f7c2495 (see REPORT-20-000.md for the
  tag-vs-main gate finding and the Disputed ruling request).
- Real recorded payload: tests/data/dart/engapi_list_unkeyed.json -
  LIVE request 11.09.2026 through RequestGate: 200, 60 bytes,
  {"status":"100","message":"Authentication Keys is missing."} -
  matches REPORT-MARKETS; the F5 probe had shown the same. Status
  '100' parsing is tested on these real bytes.
- DartProvider(DisclosuresProvider): poll_index (list.json date
  window), list_documents (issuer-filtered), fetch_document
  (documentDownload.nav, raw bytes + sha256 - DART serves a zip;
  parsing is a parser's job, I10). can_auto_ingest: company.json
  '000' -> True, '013' -> unknown_issuer, other -> source_unreachable
  value. BudgetExceeded passes through as a value (found and fixed by
  test). No key -> dart_key_unset ConfigError value from build()
  (N2). Host declared in the module: engopendart.fss.or.kr, 2/s,
  passed to the gate on every call; U5 door intact (no gate -> no
  provider).
- Zone exit, declared: tests/test_budget.py - the B20 pin
  ('provider_not_implemented:dart') was invalidated by L1 itself.
  Replaced by a lifecycle-aware form: for EVERY network provider
  name - absent module -> provider_not_implemented value (not
  ImportError); present module -> provider or build's ConfigError
  value; zero requests at get_provider time in both cases. Stronger
  than the old pin (it now holds for all seats forever), nothing
  weakened (P1 satisfied).

## Blocked

- Golden payload of three Korean issuers: impossible without
  RUSTERM_DART_KEY (unset on this machine). The live network test
  exists and skips cleanly (N7). The measure table `measure -> n/3`
  needs the key: BLOCKED, not faked - synthetic bodies in tests are
  inline test doubles, clearly labelled, never passed off as recorded
  data. ONE request of the 25 budget used (the unkeyed probe).
- can_auto_ingest truthfulness for real corp_codes: same key.

## What not to trust

- Endpoint shapes for company.json/list.json/documentDownload.nav are
  from DART English docs and REPORT-MARKETS, exercised only through
  synthetic bodies; first live run with a key must confirm field
  names (report_nm/report_tp/business_year) before anything consumes
  them.

## Disputed

- tests/test_budget.py zone exit (above): propose ADR-0017 §3-style
  named exception - where the seat pin meets its own filled seat, the
  lane side wins. The lifecycle form makes the question disappear for
  L2-L4.

## HANDOFF

Lane:            L1
Branch:          agent/n3-L1
Status:          PARTIAL (offline half; live half needs the key)
Items done:      provider, unkeyed real payload, status parsing,
                 three-outcome can_auto_ingest, gate discipline,
                 lifecycle seat test
Items not done:  golden 3-issuer payload + measure table - no key
Zone respected:  no - tests/test_budget.py (declared above, P1-safe)
selfcheck:       exit 0, "Итог: пройдено 13, провалено 0"
Tests:           15 passed, 1 skipped, 0 xfailed (test_market_kr.py);
                 full suite green via selfcheck
Payload:         tests/data/dart = 4 KB (under 256 KB)
Network:         1 of 25 requests
Model calls:     0
Secrets:         no key in git, report or log (key does not exist here)

READY TO MERGE: agent/n3-L1  172c813  selfcheck exit 0  tests 15 passed
