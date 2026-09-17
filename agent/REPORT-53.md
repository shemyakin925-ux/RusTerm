# REPORT-53 — TASK-53 (acceptance stops depending on load; live model)

## Done

- **W1**: C2 and M4 measure WORK, not wall-clock seconds.
  - C2: statement counting via `conn.set_trace_callback` — first half
    7050 operations, second half 7050, ratio **1.00**; the seconds
    budget removed (it red at ratio 1.65 under the coordinator's load
    with a green solo run — round 59).
  - M4: per-instrument control and the total budget converted from
    seconds to SQL statement counts (measured 607 statements per
    instrument, budget with x3 headroom; the per-instrument linear
    checkpoint preserved on statements). Second-pass assertions were
    already work-based (transport log + row counts).
  - Full timing audit of `tests/` (time.time / perf_counter /
    monotonic / sleep) — every remaining site with a verdict:
    - fake `sleep(self, s)` implementations injected into
      RateLimiter/gates (test_budget, test_m3_snapshot, test_metrics,
      test_cli, test_edgar) — deterministic fakes, no real sleeping;
    - `test_budget.py:74` pins that RateLimiter's default clock IS
      `time.monotonic` — a wiring pin, not a duration;
    - `test_repos.py:182`, `test_verification.py:190` — time.time()
      as stored DATA (session timestamp, staleness fixture), no
      duration assertion;
    - `test_tui_pty.py:78-79` — a pty read TIMEOUT ceiling for a
      subprocess (waits up to N seconds for the TUI to answer), not a
      duration assertion; red only if the machine is busy for the
      entire ceiling.
    No other accepted check asserts on durations.

## Blocked

- Nothing.

## Disputed

- (empty)

## What not to trust

- (interim — filled in the final HANDOFF)

## HANDOFF

Status: PARTIAL (shift in progress, interim block)
Items done: W1 code (C2 statements 7050/7050 ratio 1.00; M4 on statements), timing audit complete
Items not done: W1 stability campaign (10 runs, 3 under load), W2 count, W3 live model
Acceptance: interim — per-commit selfcheck, see git notes
Tests: m4 suite green on statement counts; full suite green in this commit's selfcheck
Guards: none weakened; C2/M4 seconds budgets replaced by deterministic work budgets
Schema: unchanged (45)
Network: 0 requests (W3 budget separate)
Model: 0 llm_calls so far
Secrets: no key values anywhere
Pushed: no (with the hand)
Questions for the coordinator:
1. none yet
