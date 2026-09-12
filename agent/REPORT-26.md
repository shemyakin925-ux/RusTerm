# REPORT-26 — TASK-26: M12 chat with citations (offline path)

## Done

- §0: branch `agent/night-8` cut from `agent/night-7` head (1dca850);
  selfcheck STATUS=0.
- **LLM_KEY UNSET** → offline set: Q1, Q2, Q5, Q6, Q11 driven by the
  fake client; Q3/Q7/Q8/Q10 as far as offline allows.

## Blocked

- LLM_KEY UNSET: Q4 (three free models), live-model halves of Q5/Q9.

## What not to trust

- No live model ran; every chat answer in tests comes from the fake
  client.

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL
Items done:      §0
Items not done:  Q1..Q12 pending
Acceptance:      STATUS=0 at branch cut
Tests:           not counted yet this shift
Pushed:          with this commit
Questions for the coordinator:
1. (none yet)

NOW: Q1, step 1
