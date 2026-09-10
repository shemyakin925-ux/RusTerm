# REPORT-19 — TASK-19, Phase 0 of M8 (branch `agent/night-3`)

## Done

- Section 0: `git pull` on `agent/night-2` (already up to date), branched
  `agent/night-3`; `bash agent/acceptance.sh` → `STATUS=0`,
  `Итог: пройдено 13, провалено 0`; `_SCHEMA_VERSION` read from file: **39**
  (next free migration number 40, not assumed).
- Report journal opened and `agent/STATE.json` repointed at it (this commit).

## Blocked

- (empty)

## What not to trust

- (empty yet)

## Disputed

- (empty yet)

## HANDOFF

- (pending, end of shift)

NOW: section 0, step 4
- F1 (commit 3af771f): Market.access + KR/BR/AU rows (providers
  intentionally unresolved), per-market venue prefixes, docstring
  jurisdiction/venue ruling. tests/test_db.py synthetic 'UK'->'GB'.
  Verify: pytest tests/test_markets.py tests/test_db.py -q -> 15 passed;
  acceptance STATUS=0 13/13; grep UK in rusterm/ tests/ empty.
  P1 note: 3 removed asserts replaced by strictly stronger pins
  (ordered 6-tuple; 7-code stderr listing).
- F2 (commit 299c1c1): six reasons added with
  ADR comments; guard untouched. pytest test_repos+test_metrics+
  test_invariants -q -> 38 passed; acceptance STATUS=0 13/13.
- F3 (commit f315247): can_auto_ingest on
  protocol + EDGAR/synthetic (True); cmd_add uses registry provider
  and asks before creating. Verify: test_add_refusal 4 passed,
  cli/edgar/providers/venue_filings 54 passed, acceptance 13/13.
  Scope note: offline add (--cik/--name) has no provider to ask —
  unchanged; per-market add flows belong to TASK-20 lanes.
- F4 (commit bf15ff0): migration 40 + two
  repos; version pins 39->40; drift tests now drop the top version
  row too (MAX() ignores gaps); b25 strengthened to a REAL v39 db
  via monkeypatched _SCHEMA_VERSION at init instead of deleting
  schema_version rows (migration 40 ALTER is not re-playable on a
  vandalized db - status exits 2; real users never see that state).
  Verify: test_db 12, test_repos 39, test_cli 34 - all passed;
  acceptance STATUS=0 13/13.
- F5 (commit e74924d): HostLimit + per-host
  pools in RequestGate; registry holds host declarations and lazy
  seats (dart/cvm/asx/otcmarkets/llm-api) with build(gate) contract;
  network provider without declaration refused (U5 hinge widened).
  Live probe 4/12 requests: dart 200 60B auth-missing JSON; cvm 200
  zip HEAD; asx 200 376B JSON; otcmarkets 200 407B JSON - all match
  REPORT-MARKETS; OTC universe now 12,794 vs 12,867 recorded (drift,
  finding only). Verify: 39 tests passed; acceptance 13/13.
- F6 (commit e4fa0c2): llm_api.py client seat
  (env-only config, ConfigError values, gate-gated per host,
  build(gate) seat contract) + core/llm.make_intent_client selector
  (key -> API client, no key -> RuleClient). cmd_ops call-site
  rewiring belongs to the chat/integration night (scope note).
  Verify: test_llm_api 12 passed; guard+ops green with key unset and
  dummy-set (13+13); acceptance 13/13; dummy key absent from logs.
