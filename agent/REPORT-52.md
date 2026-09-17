# REPORT-52 — TASK-52 (GUIDE.md stops lying: inserts checked by a run)

Fully offline. The guard is `tests/test_guide_truth.py`; the rewritten
reference is `GUIDE.md` itself. V4 holds: the guard is a plain test,
collected by every acceptance run, acceptance stays «13, провалено 0».

## Done

- **V1, parser**: `parse_guide()` splits GUIDE.md into ```console
  blocks → (file, open-fence line, commands with env prefixes,
  expected output lines). Found **10 blocks**; the full command list
  is pinned by `test_parser_lists_every_command` (init, demo,
  watchlist create/add, ingest, snapshot, export md, status --json,
  coverage, metrics, budget, markets, add, refresh --dry-run, ops
  --json, add FAKE, printf, import, tui). Exactly one block cannot
  run headless and is marked in the guide itself: §9 tui carries
  `# требует терминала`; no block needs network or a key (§6 forces
  offline via its own `RUSTERM_ENV_FILE=…` prefix), so the marker
  count is exactly one.
- **V2, the guard**: `test_guide_blocks_run_and_match` executes every
  unmarked block in file order on a fresh `tmp_path` root with an
  empty 0600 env-file (keys absent from the environment), running the
  GUIDE's own commands (paths rewritten to the tmp root, stdout+stderr
  merged — the guide shows what a terminal shows). Comparison rule,
  stated in the test docstring: dates, UUIDs, absolute paths (data
  root, env file, report file) and the number in «data_lag» are
  placeholders; a guide line containing «...» consumes any number of
  output lines; everything else is verbatim. `test_tui_block_is_
  marked_as_interactive` pins the marker.
- **V3, drift found and the guide fixed**: every drifted block was
  rewritten from a real run:
  - §1: «миграций: 39; schema_version=40» → 44/45;
  - §4 export md: map version v3 → v4, the measure table grew 23 → 27
    (valuation measures of ТЗ-23), causes renumbered — rewritten with
    elisions;
  - §5 status --json: the old six-key pretty-print does not exist —
    today it is a one-line JSON with schema counters, coverage,
    budgets, env and chat sections; coverage row
    `industry_metrics` is now `missing причина: industry_no_sector`;
    metrics gained three rows (peer_set_coverage, peer_set_churn,
    locator_resolve_failures); markets gained the `implemented` and
    version columns.
  - §7 ops: today's JSON carries `"reason": null` (ТЗ-50 T4); the
    note now says a keyed model may answer `clarification` (ТЗ-50 T3)
    — the keyed behaviour is a deliberate product choice, so the
    guide shows the keyless run and names the keyed one.
  - §8 import: the old story («format_unsupported») is gone from the
    product: import now refuses first when the instrument does not
    exist (`инструмент 'US-FAKE' не найден; импорт не создаёт
    эмитентов — сначала rusterm add`) and, with an instrument, the
    dry-run extracts («извлечено, sha … (dry-run: ничего не
    записано)»). Rewritten as the real two-step flow.
  - §9 tui: marked `# требует терминала`.
  Product-vs-guide verdicts: in every case the PRODUCT is right (the
  drift was guide-rot), so only GUIDE.md was touched. No guide edit
  papers over broken behaviour: each new output is today's real
  keyless run, and each behavioural change traces to an accepted task
  (ТЗ-23 valuation measures, ТЗ-50 T3/T4, ТЗ-20 L6 import guard).

## Blocked

- Nothing.

## Disputed

- (empty)

## What not to trust

- The guard executes the guide on macOS tmp (`/private/var/...`
  normalised) with GNU/BSD `printf`/`sh`; on another OS the shell
  built-ins could differ (the two shell lines are init-free).
- `data_lag` and the cascade reason are normalised because they are
  genuinely volatile (`data_lag` is wall-clock-based; the cascade
  reason depends on internal pass order) — the guard cannot catch a
  lie THERE by design.
- The guide's §4 export block shows an elided table by intent; the
  elision rule («...» eats lines) means the guard proves the shown
  rows and the trailing causes, not every one of the 27 rows.

## HANDOFF

Status: PARTIAL (shift in progress, interim block)
Items done: V1 parser + block inventory (10 blocks, 1 marker); V2 guard with stated shape rule; V3 all drifted blocks rewritten from real runs (§1 §4 §5 §7 §8 §9); V4 guard collected by acceptance
Items not done: TASK-50 T6 (hook trap) — unreproduced this shift, evidence plan in REPORT-50
Acceptance: this commit's selfcheck prints «Итог: пройдено 13, провалено 0», exit 0
Tests: guide suite 3 cases green; full suite green in this commit's selfcheck
Guards: new tests/test_guide_truth.py — no guard weakened
Schema: unchanged (45)
Network: 0 requests of any budget
Model: 0 llm_calls
Secrets: no key values anywhere; the guard runs keyless by construction
Pushed: yes (with the hand)
Questions for the coordinator:
1. none
