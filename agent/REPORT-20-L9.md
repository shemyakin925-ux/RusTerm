# REPORT-20-L9 — Provenance survives the export

## Done

- attach_provenance(measures, lineage): every measure gains a
  provenance block - source_kind ('manual' if ANY input fact is
  manual, else 'provider') plus one entry per input fact. A provider
  entry carries source_ref; a manual entry carries the DOCUMENT HASH,
  the PAGE (parsed from sha256:<hash>#page=<N>), the locator string,
  and the fact status (an unverified manual fact stays visible and
  marked, never silently dropped).
- snapshot_to_json gains an OPTIONAL provenance parameter: given -
  measures carry the block; omitted - the output is byte-identical to
  before (test pins the absence of the key and the presence/order of
  every pre-existing field).
- CSV and MD are untouched entirely - the addition lives only in the
  JSON path via the separate parameter; a test pins the exact CSV
  header line and the MD table header.
- The consumer test answers "regulator or PDF?" from the export TEXT
  alone (json.loads -> provenance.source_kind == 'manual' with
  document hash and page) without opening the database.

## Blocked / What not to trust / Disputed

- (empty)
- Note: the CLI wiring (cmd_export passing lineage) belongs to the
  integration phase - the export functions themselves are complete and
  tested; cmd_export is outside this lane's zone (cli belongs to L6's
  import block tonight).

## HANDOFF

Lane:            L9
Branch:          agent/n3-L9
Status:          DONE
Items done:      attach_provenance, optional JSON parameter, pins for
                 unchanged formats, round-trip consumer test
Items not done:  cli wiring of provenance into export command
                 (outside zone; integration/TASK-21 item)
Zone respected:  yes (rusterm/core/export.py,
                 tests/test_snapshot_export.py)
selfcheck:       acceptance STATUS=0, 13/13
Tests:           12 passed, 0 skipped (test_snapshot_export.py)
Payload:         no data dir needed
Network:         0 of 0
Model calls:     0
Secrets:         nothing to leak

READY TO MERGE: agent/n3-L9  0747831  selfcheck exit 0  tests 12 passed
