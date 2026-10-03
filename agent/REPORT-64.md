# REPORT-64 — TASK-64, round 82

## Done

- J1. The request counter no longer lies.
  - `_record_gate_usage(repos, provider, gate)` — one recorder: writes the
    gate's `calls_made` (a property) into metric_sample immediately.
  - Wired into the paths that had none: `cmd_add` (ticker-map resolve; the
    gate is now captured in `add_gate`), `_ingest_edgar_companyfacts`
    (right after `fetch_companyfacts`), `_ingest_edgar_ownership` (right
    after `list_ownership`). cvm/asx/twelvedata already recorded.
  - `rusterm budget` now prints the cumulative «использовано запросов: N»
    (the sum over ALL gate-probe rows) and keeps the last-probe line
    `provider_requests_used = X` that ТЗ-56/57 pins; `status --json`
    carries `budget.used` (the same sum). The old name-keyed dict silently
    collapsed multiple samples per host — that was the second half of
    the lie.
  - Equality test (offline, no network): 3 requests through a real
    RequestGate recorded → budget json `used == 3 == gate.calls_made`;
    per-host rows 3/2 asserted; empty catalog → used 0 (no invention).
  - Live run on a fresh catalog: add (14.5 s) + ingest edgar (168.9 s) →
    `budget --json`: `{"used": 2, "samples": {"provider_requests_used":
    2.0}}` — больше нуля и равно числу сделанных запросов (1 карта
    тикеров + 1 companyfacts).
  - Paths that counted wrongly before: `add` (never recorded), edgar
    companyfacts (never), edgar ownership (never); cvm/asx/twelvedata
    recorded already.

## Blocked

## What not to trust

- The live equality proof counts 2 requests for add+ingest; the split
  inside `add` (headers vs ticker-map) is not user-visible anywhere —
  the gate's total is.

## Disputed

## HANDOFF

Status: PARTIAL (J1 done; J2 provenance, J3 advice, J4 progress, J5
explanations ahead)
Arrival state: task taken round 82 on 5e9ee84, selfcheck green
Items done: J1
Items not done: J2 export provenance, J3 advice lines, J4 ingest
progress, J5 explanations and version churn — each is committed only
when its own commit lands, so this section stays truthful per commit
Acceptance: hook verdict on this commit (see commit body)
Tests: 57 passed (task64_j1_budget_truth, j1_display, cli) plus
task56_z2 and task57_au_channel pins green
Guards: none touched
Schema: unchanged
Network: 2 live requests in the J1 live proof (of the 10 allowed)
Model: GLM-5.3, app llm_calls 0
Secrets: no key material in this report
Pushed: this commit pushes immediately
Questions for the coordinator:
1. The last-probe line («provider_requests_used = X») and the new
   cumulative «использовано запросов: N» coexist — the pins of
   ТЗ-56/57 stayed untouched.

NOW: J2, step 1

- J2. Export carries provenance: `lineage_facts`, `format_source_cell` and
  `source_lineage_cell` moved to `core/export.py` — one implementation for
  the CLI export, the desktop table and the compact export shape
  (data/actions delegate). `export --format json` now attaches
  `provenance` per measure through `attach_provenance`; `--format md`
  appends a «Источники:» section (document, hash, period; «входов нет»
  for refusals). Test: valued measures carry provenance with the fact's
  source_ref; the refusal row carries `missing_data: total_equity`, not
  emptiness. Export goldens: none exist (the golden files are formula
  baselines); the currency/number pins stayed green unchanged.
- J3. `core.export.refusal_advice(token, instrument_id)` — advice only
  where the action is obvious (`price_close` → «цены: rusterm ingest
  --source twelvedata --instrument …»); `concept_not_mapped` gets none
  (no invented advice). The advice is substituted from constants and is
  parsed by the real CLI parser (`_build_parser` extracted from `main` —
  parse-only, no network). The same words appear in the window's source
  panel («что делать: …»).
- J4. `ingest --source edgar` no longer goes silent: stage lines on
  stderr («стадия загрузки…», «стадия разбора — получено N байт…»);
  stdout stays pipe-clean. Live: full run 11.6 s, stage lines visible
  within the first seconds, 16363 facts, exit 0.
- J5. The ingest summary explains itself: «неотображённых концептов: N
  (теги вне карты концептов мерами не стали — это норма; карта узнала X
  из Y)». The second snapshot on identical inputs prints «без изменений —
  значения идентичны предыдущей версии» (the version still increments —
  append-only store; the comparator `snapshot_measures_identical` is the
  core pin, a changed input drops the label and bumps the version).
- Verified: `pytest tests/test_task64_j1_budget_truth.py tests/test_task64_
  j2_export_provenance.py tests/test_task64_j3_advice.py tests/test_task64_
  j5_explain.py tests/test_j1_display.py tests/test_cli.py tests/test_e2e_
  cli.py tests/test_desktop_data.py tests/test_desktop_quality.py -q` →
  75 passed.

## HANDOFF (FINAL — supersedes the interim above)

Status: DONE
Arrival state: task taken round 82 on 5e9ee84, selfcheck green
Items done: J1 (amended round-82 commit), J2-J5 (this commit)
Items not done: none
Acceptance: hook verdict on this commit; live J1 proof (used=2) and
live J4 proof (11.6 s with stage lines) recorded above
Tests: 75 passed in the nine suites listed above
Guards: none touched
Schema: unchanged
Network: live proofs used 2 requests (J1) + 1 (J4) — within the 10
allowed for J1/J4
Model: GLM-5.3, app llm_calls 0
Secrets: no key material in this report
Pushed: this commit pushes immediately
Questions for the coordinator:
1. Budget's cumulative «использовано запросов: N» coexists with the
   ТЗ-56/57 last-probe line — both readings kept.

NOW: J5, step 2 — task complete, handing the baton back
