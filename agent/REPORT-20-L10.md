# REPORT-20-L10 — The evidence for the next coordinator

## Done

- Re-probe of 8 channels (8 of 20 requests, 11.09, through
  RequestGate): KR engopendart 200/60B (auth-missing, unchanged);
  BR dados.cvm HEAD 200 (unchanged); AU markitdigital header
  200/364B (unchanged); OTC financial-report 200/752B (unchanged;
  the /content block SHAPE drift 406-vs-softblock is recorded in
  REPORT-20-L4); NZ nzx.com/markets/NZSX/announcements 200/665,913B
  (crawlable, as measured); SG api.sgx.com 403 (still blocked);
  RU iss.moex.com 200/13,740B (reference data works);
  RU e-disclosure.ru RemoteDisconnected (still reset from this
  network).
- docs/adr/0013-poryadok-dobavleniya-rynka.md: the market-number-
  seven procedure with MEASURED per-step costs from tonight, five
  lessons (dataset shapes drift at the source; block shapes drift;
  keys double the night; intra-lane ordering as contract; stale
  common-file pins), and the checklist.
- Taxonomy-gap list for TASK-21: BR native columns (CD_CONTA/
  DS_CONTA/VL_CONTA/ESCALA_MOEDA) are NOT mapped to ifrs-full yet -
  outside the lane's zone; KR tags unknowable until the key exists;
  AU/OTC have no XBRL tags to map.

## Blocked

- Nothing.

## What not to trust

- One probe per host, single session, single IP - same limits as the
  original measurement; SGX verdict stays "unproven" (403 is a stop,
  not a conclusion about the widget path).

## Disputed

- (empty)

## HANDOFF

Lane:            L10
Branch:          agent/n3-L10
Status:          DONE
Items done:      8-channel re-probe, ADR-0013, taxonomy-gap list
Items not done:  -
Zone respected:  yes (docs/adr/0013-*.md new ADR only; report)
selfcheck:       exit 0, "Итог: пройдено 13, провалено 0"
Tests:           suite green via acceptance (no lane tests needed)
Payload:         no data dir needed
Network:         8 of 20 requests
Model calls:     0
Secrets:         no key in git, report or log

READY TO MERGE: agent/n3-L10  9b4d977  selfcheck exit 0  tests suite-green
