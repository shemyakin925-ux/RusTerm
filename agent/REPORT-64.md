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
