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
- F7 (commit 5a85ccf): agent/selfcheck.sh; acceptance untouchable.
  Verify: clean tree -> SELFCHECK OK, exit 0; deliberately removed
  assert staged -> 'SELFCHECK FAIL (P1)', exit 1 (reverted);
  deliberately broken test staged -> acceptance prints 11/2 and
  'SELFCHECK FAIL (acceptance): exit status 2', exit 1 (reverted);
  git ls-files agent/selfcheck.sh finds it. Tree clean after demos.
- F8 (commit f07bdd0): rusterm/manual package;
  verify fully implemented (verbatim quote on its page + value
  numeral as a quote token; thousands merged text-wide before
  tokenizing; string law, no rounding); extract_text is an honest
  seat refusing with format_unsupported value until lane L5.
  Verify: 12 tests passed; selfcheck exit 0.
- F9 (commit 49a2cf0): README section 15 tells
  the truth (app works, 13/13, 402+2 tests, 13 ADRs, milestones
  M0-M7 reached with closing task numbers, M8 in progress); all 11
  UK mentions removed repo-wide per user decision section 0.2.5.
  Verify: grep UK README empty; grep 'Кода приложения' empty;
  selfcheck exit 0.
- F10 (commit aa333bb): agent/state/.gitkeep created; foundation
  tagged n3-foundation at aa333bb and pushed. Verify: git tag
  --list prints it; git push origin n3-foundation succeeded;
  fresh 'git checkout -b probe n3-foundation && bash
  agent/selfcheck.sh' -> SELFCHECK OK exit 0; probe branch deleted.
- B20 (commit 51795c9, backlog ba4a0a0): seat test strengthened
  (ConfigError + calls_made==0 + refused==0 across all four seats;
  U5 door unchanged). 9 passed in test_budget.py.

### Incident, honest note (B20 commit 51795c9)
- selfcheck ran RED (P1) before commit 51795c9 and the commit still
  landed: my shell chain used ';' before 'echo' so the exit status
  did not gate the commit - the exact pipe-mask defect class F7
  exists to kill, now caused by my own chaining. Correction: selfcheck
  is always chained with '&&' from here on.
- why P1 was red at all: P1 is a line-level guard. The B20 edit
  REWROTE the seat test; three assert lines were removed and re-added
  verbatim inside the same block plus six new asserts (calls_made==0,
  refused==0, per-seat loop). Strictly stronger replacement, per P1
  rule; the guard cannot see re-additions - it reports and the
  executor justifies line by line, which is this note.
- F11 backlog (commits c7ffd05..7d84813): B19, B20, B21, B23, B24,
  B25, B26, B28, B30, B31 closed; each in BACKLOG.md ## Done with
  verify note. Not pursued, with reasons: B22 (asserts formats table
  of extract.py - module does not exist until lane L5; a table of the
  refusing seat would be a lie), B27 (coexistence needs the
  measure-side source_kind selection that lane L6 builds; the
  fact-level half alone would be a half-check), B29 (L-size scale
  pass needs the six-market providers that TASK-20 lanes bring).

## What not to trust

- F5 live probe: status and byte counts recorded per host, raw bodies
  not stored (sniff = first 60 bytes only). OTC universe count
  12,794 vs 12,867 in REPORT-MARKETS - one-session drift, finding
  only, no redesign.
- GUIDE.md outputs are real but were taken in a throwaway root
  (/tmp/rusterm-guide); doctor JSON is long, the guide points to the
  command instead of pasting all of it.
- nightly_max defaults 5000/host are the project-wide provisional
  ceiling, not measured per-source ceilings; lanes override in their
  modules.

## Disputed

- selfcheck.sh P1 narrowed to '*.py' (commit ca3085a). My own tool,
  acceptance.sh untouched. Reason: diff marker '-' plus the word
  "assert" in backlog PROSE fired P1 (case B24); the rule is about
  code. Coordinator may re-widen, but then md files need excluding
  some other way.
- "available() lists all eight names": counted as 5 network seats +
  2 synthetic + llm-api (F6, registered with HostLimit openrouter.ai
  1/s 5000). If the intended eighth was something else, un-registering
  llm-api is one line.
- B23 near_miss semantics: loose digit-only match bucket; near_miss
  is stored and visible but excluded from measures exactly like
  failed (single reason manual_unverified). If near_miss needs its
  own null_reason later, that is one dictionary line plus lane work.
NOW: F11, step 8

## HANDOFF

Status:          DONE
Items done:      F1, F2, F3, F4, F5, F6, F7, F8, F9, F10; backlog B19,
                 B20, B21, B23, B24, B25, B26, B28, B30, B31
Items not done:  B22 (needs extract.py from lane L5), B27 (needs
                 measure-side source_kind selection from lane L6),
                 B29 (L-size scale pass needs the six-market providers
                 from TASK-20 lanes)
Acceptance:      "Итог: пройдено 13, провалено 0"; last run via
                 agent/selfcheck.sh (STATUS captured before pipes):
                 exit 0
Tests:           411 passed, 2 skipped, 0 xfailed (full run at the
                 end of the shift)
Schema:          _SCHEMA_VERSION 39 -> 40, migration 40 (document,
                 manual_extraction, fact.source_kind DEFAULT 'provider')
Markets:         ('US', 'CA', 'OTC', 'KR', 'BR', 'AU')
Reasons added:   manual_import_required, manual_unverified,
                 format_unsupported, no_text_layer, unknown_issuer,
                 source_unreachable
Probe results:   engopendart.fss.or.kr 200, 60 B, auth-missing JSON
                 (matches REPORT-MARKETS); dados.cvm.gov.br 200,
                 application/zip HEAD (matches);
                 asx.api.markitdigital.com 200, 376 B JSON (matches);
                 backend.otcmarkets.com 200, 407 B JSON (matches;
                 universe 12,794 vs 12,867 recorded - drift, finding)
Tag:             n3-foundation at aa333bb, pushed yes; backlog commits
                 B19-B31 landed AFTER the tag (c7ffd05..7d84813) - the
                 lanes may ignore them, but L5/L6 should know the
                 import seat command (B21/B26) lives on the branch head
selfcheck.sh:    exit 0 on a clean tree; deliberate removed-assert ->
                 FAIL (P1) exit 1; deliberate broken test -> acceptance
                 prints 11/2 then FAIL (acceptance: exit status 2),
                 exit 1; both demos reverted
Secrets:         no key appears in git, reports, logs or tests; only
                 env names and synthetic dummies; RUSTERM_DART_KEY was
                 never touched (no key exists on this machine)
Network:         4 requests used of the 12 budget (one per new-market
                 host, through RequestGate with HostLimit)
Model:           app llm_calls 0; executor model GLM-5.3-Flash
Pushed:          yes (agent/night-3 + tag n3-foundation)
Questions for the coordinator:
1. Merge ordering: lanes branch from the tag (aa333bb); the branch
   head carries backlog extras including the `import` seat command
   that L5/L6 will replace. Integrate head-before-lanes, or expect
   this one small conflict in cli/__init__.py?
2. nightly_max 5000/host is provisional (rates are measured,
   ceilings are not). Lanes override inside their provider modules -
   confirm that is the intended ownership.
3. "eight names" in available(): I registered llm-api as the eighth
   (5 seats + 2 synthetic + llm). If you meant another name, say so.
4. B23: near_miss shares the manual_unverified outcome with failed.
   Own null_reason for near-misses later, or keep one bucket?
NOW: HANDOFF, step 8
