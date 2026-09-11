# REPORT-20-L6 — Pages become records; records earn the right to be facts

## Done

- Branch agent/n3-L6 is cut from agent/n3-L5's head (8e3a293), NOT
  from f7c2495: this lane imports rusterm/manual/extract.py, and the
  task's own ordering constraint ("L5 must finish before L6 starts")
  is satisfiable only by including L5's work. Integration note: L6's
  diff vs the fan-out base contains L5's diff; merging L5 then L6 is
  conflict-free by construction.
- records.py (stage 2): prompt (verbatim quote + page number, JSON
  only, no invented numbers), response parsing as values (broken JSON
  -> parse_failed:not_json / not_a_list; whitespace-only quote ->
  dropped_no_quote counter; empty quote / missing keys ->
  dropped_bad_shape counter; foreign category ->
  dropped_bad_category; code fences stripped),
  period_bounds (FY2025 -> year bounds, duration; ISO date ->
  instant).
- pipeline.py: extract -> complete -> verify -> store, through
  repositories only (no SQL in manual/, check 7). Document
  idempotent by sha256 (replay outcome, counts from the stored
  document). No key -> ConfigError AFTER stage 1, nothing written.
  verified -> fact: source_kind='manual', origin='manual', locator
  sha256:<hash>#page=<N>, parser_version manual:<model>:<prompt>,
  source_ref = the document itself in the raw store (fact.source_ref
  FK points at real bytes). unverified -> record stored and MARKED
  (manual_extraction verified=0), NO fact row: it cannot enter any
  measure by construction; visible via source-card counts; export
  presentation is lane L9's surface (see Disputed). A manual fact
  never overwrites a provider fact (test asserts kinds
  {provider:1, manual:1} for the same concept).
- cli import block (this lane's zone): real command replaces the
  B21/B26 seat: dry-run = stage 1 only; the issuer must exist (import
  creates no issuers, ADR-0011); no key -> stops after stage 1 with a
  message; per-file outcomes printed with drop/verify counts.

## Blocked

- Live model calls (60 ceiling): RUSTERM_LLM_API_KEY is unset (an
  empty line exists in ~/.rusterm.env - not a key). 0 of 60 used.
  All model paths are tested through the fake client with recorded
  bodies.

## Zone exits, declared

- rusterm/store/repos.py: insert_fact gains `source_kind:
  str = "provider"` - additive, default keeps every existing caller
  byte-identical in behavior. Only this lane touches it tonight ->
  no integration conflict.
- tests/test_add_refusal.py: B21/B26 pins referenced the STUB this
  lane replaces (dry-run exit 1 -> 0 on an extractable file; refusal
  line now on stderr with the lane tag; the B21 fixture seeds an
  instrument and opens the db via the app's own open_connection so
  the "nothing written" sha comparison is fair - first open flips WAL).
- tests/test_budget.py: byte-identical lifecycle version (L1-L4).

## What not to trust

- The prompt/parse contract is exercised only against the fake
  client; the first live model run must confirm the JSON-array
  discipline of real models (L7's whole point).
- period_bounds maps unknown period strings to themselves (start=end,
  instant) - honest but coarse; a mapping pass may want better.

## Disputed

- Interpretation of ADR-0011 3: an unverified record is stored and
  marked, but gets NO fact row. ADR wording "fact ... visible in the
  export" is taken as: the RECORD is visible (source card counts now;
  export surface - L9). If the coordinator wants unverified FACT ROWS
  too (status='suspect'), that is a small change here plus a formula-
  side filter outside this lane's zone - ruling requested.

## HANDOFF

Lane:            L6
Branch:          agent/n3-L6
Status:          PARTIAL (everything offline; live model calls need the key)
Items done:      records.py, pipeline.py, real import command,
                 idempotency, manual-unverified exclusion by
                 construction, never-overwrite test
Items not done:  live model records (no key)
Zone respected:  no - three declared exits above
selfcheck:       acceptance run separately: STATUS=0, 13/13 (P1 flag
                 on staged rewrites is the known line-level blindness,
                 justified in the zone-exit notes)
Tests:           16 passed (test_manual_pipeline.py); full suite green
Payload:         no data dir needed
Network:         0 of 0 requests
Model calls:     0 of 60 (no key)
Secrets:         no key in git, report or log

READY TO MERGE: agent/n3-L6  d071705  selfcheck exit 0  tests 16 passed
