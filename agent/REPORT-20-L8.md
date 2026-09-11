# REPORT-20-L8 — The terminal shows where a number came from

## Done

- List screen gains a market column: the registry code derived from
  the instrument id prefix WHEN it is a registered market
  (rusterm.markets.get_market), else an honest dash - no guessing.
  render_list paints it first; a test covers both the known and the
  unknown-prefix cases, and the rendered line.
- Card screen marks each number's provenance: card_rows reads the
  lineage facts of every measure and derives source_kind ('manual'
  if any input fact is manual, else 'provider') and unverified (any
  input fact status='suspect'). render_card: manual -> ' [manual]';
  unverified manual -> ' [manual · НЕ проверено]' - visibly not
  trusted, distinguishable at a glance. Rules unchanged: pure
  functions in model.py, no curses in tests, no writes, no network.
- Source panel: every source entry now carries kind; a manual fact's
  locator is presented as 'файл, страница N' parsed from
  sha256:<hash>#page=<N> instead of a URL.
- Zone exit, declared: rusterm/store/repos.py - FactRepo._FACT_COLUMNS
  gains 'source_kind' so get_fact returns what migration 40 already
  stores (additive read; the insert-side parameter is the byte-stable
  version from agent/n3-L6). Both sides are supersets; merge order
  L6 -> L8 is conflict-free.

## Blocked / What not to trust

- (empty)

## Disputed

- (empty)

## HANDOFF

Lane:            L8
Branch:          agent/n3-L8
Status:          DONE
Items done:      market column, per-measure source_kind/unverified,
                 manual locator labels, tests
Items not done:  -
Zone respected:  no - rusterm/store/repos.py (additive read column,
                 insert side byte-stable with agent/n3-L6)
selfcheck:       acceptance STATUS=0, 13/13
Tests:           11 passed, 0 skipped (test_tui_model.py)
Payload:         no data dir needed
Network:         0 of 0
Model calls:     0
Secrets:         nothing to leak

READY TO MERGE: agent/n3-L8  66b7677  selfcheck exit 0  tests 11 passed
