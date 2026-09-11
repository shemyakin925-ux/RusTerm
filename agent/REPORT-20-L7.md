# REPORT-20-L7 — The model behind the API, hardened

## Done

- Retries (N3/N4): 429 and 5xx are retried exactly once with a 2 s
  backoff - two attempts, then a ConfigError VALUE
  (llm_http_<code>). 4xx is never retried. Every attempt is a real
  gate-tracked request (budget counts both - asserted).
- Timeouts: READ_TIMEOUT=60 passed explicitly to urlopen; urllib
  bounds both the connection and each blocking read with it - stated
  in the docstring (urllib has no separate connect-timeout; that is
  documented, not hidden). Transport-raised socket.timeout/OSError
  maps to llm_timeout value, also retried once. A test captures the
  urlopen kwarg and asserts the explicit bound.
- Malformed/truncated body: llm_bad_response value (existing F6 test,
  still green).
- Key-leak guard extended: success + retry-give-up + garbage-body
  paths all executed under DEBUG capture; the dummy key appears in
  no artifact.
- Production model is NOT pinned to a paid default: base URL default
  is OpenRouter, the model comes only from the environment (test).

## Blocked

- The three-free-model comparison table (the point of the lane):
  RUSTERM_LLM_API_KEY is unset (an empty line in ~/.rusterm.env is
  not a key). 0 of 100 model calls used. The table needs one command
  with a key: BLOCKED, not faked.

## Zone respected

- yes: rusterm/providers/llm_api.py, tests/test_llm_api.py.
  tests/test_budget.py is byte-identical with agent/n3-L1's lifecycle
  version (same declared exit as L1-L4 - the llm-api seat pin died at
  F6 fill time; on this branch the pin is pre-lifecycle).
- core/llm.py reviewed: no change needed - make_intent_client only
  selects; retry/timeout live in the provider.

## What not to trust

- Backoff is a fixed 2 s (not exponential): one retry only, so
  exponential growth would be ceremony without effect.
- The live-endpoint behavior (real 429 cadence, truncation shapes of
  real providers) is untested for the same no-key reason.

## Disputed

- (empty)

## HANDOFF

Lane:            L7
Branch:          agent/n3-L7
Status:          PARTIAL (offline hardening done; live table BLOCKED)
Items done:      retries, timeouts, value-shaped failures, leak guard,
                 no-paid-default
Items not done:  three-free-model live table - no key
Zone respected:  no - tests/test_budget.py (byte-identical with L1)
selfcheck:       acceptance STATUS=0, 13/13
Tests:           19 passed, 0 skipped (test_llm_api.py)
Payload:         no data dir needed
Network:         0 of 0 data requests
Model calls:     0 of 100 (no key)
Secrets:         dummy key only; nothing leaked anywhere

READY TO MERGE: agent/n3-L7  4eb1bd2  selfcheck exit 0  tests 19 passed
