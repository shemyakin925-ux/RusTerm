# REPORT-28 — TASK-28: freeness becomes a machine-checked rule

## Done

### Arrival state (per PROTOCOL §10, before any commit)

- Branch `agent/night-10` (this shift's branch; TASK-28 §0 line 2 done
  once per shift), selfcheck STATUS=0 before this task started
  (TASK-29 closed first, per LAUNCH order: 29, then 28).
- Schema `_SCHEMA_VERSION` = 41 (§0 line 4).
- `sorted(available())` (§0 line 5): ['asx', 'cvm', 'dart', 'edgar',
  'llm-api', 'otcmarkets', 'synthetic-disclosures', 'synthetic-market'].
- Seats still carrying the placeholder ceiling (§0 line 6):
  `grep -rn "nightly_max=5000" rusterm/providers/__init__.py | wc -l`
  -> 6.

### R1 — every external channel declares its cost (DONE)

- `rusterm/providers/__init__.py`: `_TIERS` closed set
  (`open`, `free_key`, `paid`); `_CHANNEL_TIERS` declares a tier for
  every network name; `get_provider` refuses by value a name without a
  tier (`provider_declares_no_tier:<name>`) and a name whose tier is
  `paid` (`paid_channel_refused`) — both before any factory runs, so
  `calls_made` stays 0. Public `channel_tier(name)` added for doctor
  and guards.
- Tiers declared tonight (verbatim, name -> tier):
  asx -> open; cvm -> open; dart -> free_key; edgar -> free_key;
  llm-api -> free_key; otcmarkets -> open.
- `tests/test_free_only.py` (new) asserts all three required things:
  every registered network name carries a tier from the closed set;
  no registered name declares `paid`; a synthetic `paid` seat injected
  into the registry inside the test is refused by value with
  `reason == "paid_channel_refused"`, the factory not called, and
  `gate.calls_made == 0`. Plus: a name with a factory but no tier is
  refused by value.
- Verification: `python3 -m pytest tests/test_free_only.py -q` ->
  4 passed; `tests/test_budget.py tests/test_providers.py` -> 20 passed
  (budget behaviour untouched, no assertion edited).

## Blocked

- (nothing yet)

## What not to trust

- (updated as items land)

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL — shift in progress
Arrival state:   selfcheck STATUS=0 (TASK-29 landed first on this branch)
Items done:      R1
Items not done:  R2, R3, R4, R5, R6 — in numeric order
Acceptance:      last run «Итог: пройдено 13, провалено 0», ACC_EXIT=0
Tests:           test_free_only 4 passed; budget/providers 20 passed
Guards:          tests/test_free_only.py new (R1 part); no existing assertion touched
Schema:          unchanged (41)
Network:         0 requests of 10 budget
Model:           0 calls of 0; GLM-5.3-Flash
Secrets:         no key values anywhere; repr masks from TASK-29 A4 in place
Pushed:          per-commit
Questions for the coordinator:
1. (none yet)

### R2 — doctor prints the freeness section (DONE)

- Registry gained `channel_key_env(name)` (which env name opens the
  channel; None for open channels). `cmd_doctor` builds
  `report["free_channels"]` from the registry alone: host, tier,
  per_second, nightly_max, `ceiling_kind` («проектный потолок» for the
  5000 placeholder, «тариф вендора» for a vendor number), key_env and
  `key_present` (`да`/`нет`/`—`, never a value). An absent key prints
  `нет` and does not change the exit status (verified: doctor exit 0
  with RUSTERM_DART_KEY unset).
- `rusterm doctor` output (keys: dummykey injected for RUSTERM_LLM_API_KEY,
  DART unset), the section verbatim:

```json
{
 "free_channels": {
  "asx": {"host": "asx.api.markitdigital.com", "tier": "open",
          "per_second": 1.0, "nightly_max": 5000,
          "ceiling_kind": "проектный потолок", "key_env": "—", "key_present": "—"},
  "cvm": {"host": "dados.cvm.gov.br", "tier": "open",
          "per_second": 1.0, "nightly_max": 5000,
          "ceiling_kind": "проектный потолок", "key_env": "—", "key_present": "—"},
  "dart": {"host": "opendart.fss.or.kr", "tier": "free_key",
           "per_second": 2.0, "nightly_max": 5000,
           "ceiling_kind": "проектный потолок", "key_env": "RUSTERM_DART_KEY",
           "key_present": "нет"},
  "edgar": {"host": "data.sec.gov", "tier": "free_key",
            "per_second": 5.0, "nightly_max": 5000,
            "ceiling_kind": "проектный потолок", "key_env": "RUSTERM_SEC_UA",
            "key_present": "да"},
  "llm-api": {"host": "openrouter.ai", "tier": "free_key",
              "per_second": 1.0, "nightly_max": 5000,
              "ceiling_kind": "проектный потолок", "key_env": "RUSTERM_LLM_API_KEY",
              "key_present": "да"},
  "otcmarkets": {"host": "backend.otcmarkets.com", "tier": "open",
                 "per_second": 1.0, "nightly_max": 5000,
                 "ceiling_kind": "проектный потолок", "key_env": "—",
                 "key_present": "—"}
 }
}
```

- Reading note, stated honestly: the task's Done-when says «every name
  from available() appears in the section»; the section lists the
  registry's network channels. `available()` also returns two
  synthetic seats (`synthetic-market`, `synthetic-disclosures`) which
  are not external channels, carry no host and no tier; the test
  asserts every available() name THAT HAS a declared tier appears with
  exactly that tier. Declaring synthetics as external channels would
  contradict the registry semantics (budget.py: synthetic seats are
  zero-cost and do not touch the limiter).
- Test: `test_doctor_prints_free_section_without_paid_and_without_key_values`
  — every tier-bearing name from available() in the section with its
  tier; the string `paid` nowhere in the output; `dummykey` nowhere in
  the output (run with RUSTERM_LLM_API_KEY=dummykey); exit 0. 5 passed.

### R3 — the free ceiling stops being a project number where the vendor publishes one (DONE)

- Case: the price provider MODULE does not exist on the tree (TASK-23
  K2 was reported blocked on the key) — so the declaration landed in
  the registry and the module was NOT faked: `twelvedata` seat returns
  `provider_not_implemented:twelvedata` by value (verified by test).
- `twelvedata` declared: host `api.twelvedata.com`,
  `per_second=8/60` (the 8/min equivalent), `nightly_max=800` (Twelve
  Data free tier, ADR-0014 §1), tier `free_key`, key env
  `RUSTERM_TWELVEDATA_KEY`. doctor's `ceiling_kind` now prints
  «тариф вендора» for it and «проектный потолок» for the rest.
- Names still carrying the project placeholder 5000/хост, one line
  each, named as placeholders: `edgar` (data.sec.gov), `dart`
  (opendart.fss.or.kr), `cvm` (dados.cvm.gov.br), `asx`
  (asx.api.markitdigital.com), `otcmarkets` (backend.otcmarkets.com),
  `llm-api` (openrouter.ai). No ceiling was guessed for a vendor that
  does not publish one.
- P1 note, replaced-by-stricter pins (no assertion deleted or loosened):
  - `tests/test_budget.py::test_available_lists_all_eight_names` ->
    `test_available_lists_all_nine_names`: 8 -> 9 names, twelvedata
    added to the membership pin, docstring states why. Stronger: one
    more name pinned.
  - `tests/test_budget.py::test_every_network_provider_declares_host_limit`:
    rates dict gains `"twelvedata": 8.0/60.0` pinned exactly. Stronger:
    one more rate pinned.
- Existing budget behaviour untouched: `budget_exceeded` is still
  returned by value past the ceiling (test_budget.py unchanged in that
  respect and green). Full default run EXIT=0.

- P1 selfcheck fired on the staged diff, as it must for any replaced
  assert line. The two replacements, side by side:
  - `test_available_lists_all_eight_names`:
    `- assert len(names) == 8` -> `+ assert len(names) == 9`, tuple of
    expected names gains `"twelvedata"`; docstring names R3. Strictly
    stronger: one MORE name pinned, none dropped.
  - `test_every_network_provider_declares_host_limit`:
    rates dict gains `"twelvedata": 8.0 / 60.0`. Strictly stronger:
    one MORE rate pinned exactly.
  Justification follows the ACCEPTANCE-19 precedent (17 removed
  asserts, all verified replacements): the pins could not survive the
  very declaration this item requires.

## Disputed

- Coordination bug inside TASK-28 R3 itself (PROTOCOL §8, task vs
  task): the work section REQUIRES the twelvedata declaration to land
  in the registry («the declaration still lands in the registry»),
  while the Done-when says «the existing tests/test_budget.py
  assertions are untouched». Both cannot hold: the
  `test_available_lists_all_eight_names` pin asserts exactly 8 names
  and the rates pin enumerates 6 names — the ninth name and the
  7th rate break them. Implemented per the work section (the
  declaration landed); the Done-when quote and the two replacements
  are recorded here for the coordinator's ruling. No assertion was
  deleted or weakened; both replacements are strictly stronger.

### R4 — no new host appears past the registry (DONE)

- Guard: `test_every_host_literal_belongs_to_a_declared_channel` in
  `tests/test_free_only.py` (test-only zone, no production change).
  It parses every `rusterm/providers/*.py` with `ast`, collects host
  names from string constants (inside f-strings too, via their static
  fragments), SKIPS docstrings by AST position (module/class/function
  docstrings are prose — otcmarkets.py and asx.py carry refused-paid
  explanations there), and compares registrable domains against the
  registry's declared hosts. Comparison by registrable domain, not by
  exact string, because the tree legitimately reaches subdomains of a
  declared channel's domain (measured, quoted by the sanity print:
  edgar -> www.sec.gov + data.sec.gov; dart ->
  engopendart.fss.or.kr; otcmarkets -> backend + www.otcmarkets.com).
  The multi-label public suffixes in use are an explicit closed tuple
  (.or.kr, .com.br, .gov.br, .com.au, .co.uk, .com.tr).
- Green on the tree as it stands: 8 passed.
- Red on a deliberate offender (scratch edit, then reverted; verbatim):
  `AssertionError: хосты мимо реестра: edgar.py:32: quotes.paidvendor.example`
  — file, line and host named, as required.
- Sanity print proving the guard is not vacuous (hosts actually
  collected, mapped to registrable domains):
  asx.py {asx.api.markitdigital.com: markitdigital.com};
  cvm.py {dados.cvm.gov.br: cvm.gov.br};
  dart.py {engopendart.fss.or.kr: fss.or.kr};
  edgar.py {www.sec.gov: sec.gov, data.sec.gov: sec.gov};
  llm_api.py {openrouter.ai: openrouter.ai};
  otcmarkets.py {backend.otcmarkets.com, www.otcmarkets.com:
  otcmarkets.com}.

### R5 — nowhere is the user offered a paid plan (DONE)

- `GUIDE.md` §0: the env block now names all four channel keys; a cost
  table added (env variable | where issued | what it unlocks | cost =
  бесплатно | documented free ceiling where the vendor publishes one —
  SEC: ≤10 req/s declaration, program keeps 5/s; Twelve Data: 8/min and
  800/day; DART and OpenRouter: no published single number, named as
  the project placeholder). The ADR-0018 card-is-payment rule is
  stated in one sentence.
- `cmd_chat` refusal now names the free tier, verbatim (real run,
  key-less, `RUSTERM_ENV_FILE` pointed nowhere, EXIT=1):
  `chat: модель недоступна: llm_key_unset; задайте RUSTERM_LLM_API_KEY (ключ бесплатный — регистрация на openrouter.ai без карты, ADR-0018)`
- Tests: `test_guide_names_every_channel_key_env_and_costs_nothing`
  (every name in the registry's key-env set appears in GUIDE.md;
  «бесплатно» named); `test_chat_refusal_names_the_free_tier`
  (refusal names «бесплатн», and after removing that word no «платн»
  remains — the paid-plan check is substring-safe). test_free_only:
  10 passed; full default run EXIT=0.
