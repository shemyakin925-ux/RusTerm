# REPORT-27 — TASK-27: M13 debts whose preconditions arrived

## Done

- §0: branch `agent/night-9` cut from `agent/night-8` head (4fd5e9e);
  selfcheck STATUS=0; extract.py present (L5 landed); the
  make_intent_client PENDING was still open at branch cut.

### N1 — the model client door is wired (DONE)

- `cmd_ops` obtains its client from `make_intent_client(os.environ)`
  and from nowhere else; the `RuleClient` import is gone from cli.
- The door itself hardened: a key present but the client build failing
  (contact/model unset) falls back to the rule client — no network, no
  error (§0.2.2); ConfigError is a VALUE, the door checks for
  `complete` duck-typing, not exceptions.
- The PENDING line for `make_intent_client` is REMOVED from
  tests/test_single_door.py; the flipped guard
  (`test_implementations_are_built_only_behind_their_door`) now
  forbids direct `RuleClient`/`LlmApiClient` construction outside
  `rusterm/core/llm.py`.
- Red-guard demonstration (as required): with `RuleClient()` put back
  into cmd_ops, the guard fails with «реализация конструируется в
  обход make_intent_client» — captured, reverted, green again.
- `tests/test_llm_wiring.py`, 4 passed: no key -> RuleClient; key +
  contact -> LlmApiClient; key without contact -> rule fallback;
  cmd_ops uses the door (spy); the sentinel key value appears in no
  artefact.
- Full suite: 619 passed, 4 skipped; selfcheck STATUS=0.

## Blocked

- N5 (six-market scale pass) needs the network budget and live
  collection — 0 of the 40 requests spent; a projection was not
  accepted, so no number is claimed.
- N7 (BR/AU ingest channels) — started in the remaining window if
  possible; otherwise named below.

## What not to trust

- (updated as items land)

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL
Items done:      §0, N1
Items not done:  N2..N8 pending this night
Acceptance:      STATUS=0 at branch cut and after N1
Tests:           619 passed, 4 skipped
Schema:          41 (unchanged so far)
Pushed:          with this commit
Questions for the coordinator:
1. (none yet)

NOW: N4, step 1
