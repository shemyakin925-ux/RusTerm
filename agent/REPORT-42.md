# REPORT-42 — TASK-42: the hand cannot fail silently; then Q3/Q7/Q10

Arrival state: selfcheck OK (13/13); the branch was rebased onto the
coordinator's round-48/49 baton commits (my unpushed test repairs
re-applied — the rebase conflict in BATON.json resolved in favour of
origin).

## Done

### J1 — `hand` cannot end without handing (DONE)

- Foreign files staged in the index -> `hand` REFUSES (used to be a
  warning and continue): "в индексе лежит чужое: ... Ход не передан
  и работа не сдана. Закоммить это своим коммитом и повтори".
- A failed `git commit --only` inside the hand -> named refusal
  ("коммит эстафеты не прошёл. Ход не передан...") instead of the
  helper's silent SystemExit.
- After the push: `hand` fetches and re-reads BATON.json from
  `origin/<branch>`; if the holder there is not the target — non-zero
  exit and "ход НЕ передан: на origin/... держит ..., а не ...".
- Tests `tests/test_j1_hand.py` (temp repo + bare local origin, no
  network): dirty index -> non-zero, "ход не передан" + the file
  named, origin BATON unchanged (holder executor, round 1); clean
  index -> hand passes, origin BATON reads holder=coordinator,
  round=2, the note preserved. 2 passed.

### J2 — the submission is verified, not declared (DONE)

- `relay.py status --assert-holder <РОЛЬ>`: fetches origin/<branch>,
  reads BATON; non-zero exit + named reason when the holder differs;
  zero when it matches.
- `agent/PROTOCOL.md` §12: the hand block now ends with
  `python3 agent/relay.py status --assert-holder coordinator` and the
  instruction what a non-zero means (authorized by the task's
  РАЗРЕШЕНО ПРАВИТЬ line).
- Tests: `test_assert_holder_both_outcomes` — after a real hand,
  assert-holder coordinator passes, assert-holder executor fails
  with "ход НЕ передан". 1 passed (both outcomes inside).

### J3 — P6 stops accusing the relay's own commit (DONE)

- The coordinator's hand commit is recognized by the message
  («Эстафета: круг N» at the start) AND the composition: every file
  in it must be coordinator-owned (the same list P6 protects) or
  BATON.json. Such a commit is skipped by P6 with a note. Any
  executor-owned file inside the same-labeled commit — red naming it.
- Tests `tests/test_j3_p6_relay_commit.py`: relay commit (BATON +
  TASK-38 + CONTEXT + BACKLOG + LAUNCH) -> green "коммит эстафеты,
  пропущен"; the same message with agent/p6_rule.sh inside -> red;
  a plain executor commit is not treated as relay. 3 passed.
- `test_selfcheck_cannot_exit_zero_with_dirty_tree` green again: on
  the coordinator's relay HEAD, selfcheck now exits via P3/P4 (the
  untracked junk), not the false P6.

### I1 — question vs order (DONE)

- `chat.detect_order` + `chat.propose_order`: a composition order
  ("добавь MSFT в список") is classified deterministically (the same
  RuleClient rules as cmd_ops; the classifier is injected — the door
  law holds) and turned into an `ops.prepare` proposal. Nothing is
  written: the database hash is unchanged by the proposal.
- Confirmation is the EXISTING path: `ops.apply(watchlist_repo,
  watchlist_id, addable, action="chat-confirmed")` + `repos.audit.log`
  with confirmed=1, result=applied — the audit row distinguishes the
  confirmed application from the unconfirmed proposal
  (`chat-proposal`, confirmed=0).
- Tests `tests/test_i1_order.py`: 4 passed — detection, proposal
  without writes, confirmed apply + audit, questions never propose.

### I2 — the chat knows what it does not know (DONE)

- `chat.unknown_reason_from_tools`: scans THIS question's tool
  outcomes for absence signals (outcome not_found; measures with
  null_reason; block missing with reason) and returns the FIRST
  reason from the reasons.py vocabulary. `ChatSession.ask` replaces
  the model's answer with the refusal `no_data:<reason>` whenever the
  tools reported absence — a hedged sentence or an invented number
  can no longer surface.
- Tests `tests/test_i2_does_not_know.py`: 3 passed — not_found ->
  `no_data:unknown_issuer`; a grey measure ->
  `no_data:missing_data`; a stale measure (price_close_stale) ->
  `no_data:missing_data`. Each asserts the model's number was
  suppressed.

### I3 — the conversation gets a screen (DONE)

- `rusterm/tui/model.py`: `chat_screen(session, calls)` +
  `render_chat(screen)` — pure functions: turns (role, text),
  citations, the cost line "вызовов: N; модель: M", rejected turns
  marked [ОТКЛОНЕНО]. No ANSI in any line (B11).
- `rusterm/tui/app.py`: the "c" key on the list screen opens
  `_chat_screen` — the same ChatSession the CLI uses; the client
  comes through `make_intent_client` (I4).
- Tests `tests/test_i3_chat_screen.py`: 2 passed — rendered lines
  asserted (turns, citations, cost, [ОТКЛОНЕНО], no ANSI).

### I4 — the screen opens no new door (DONE)

- `tests/test_i3_chat_screen.py::test_app_screen_constructs_client_through_the_door`:
  app.py's chat path constructs the client only via
  `make_intent_client`; no direct `LlmApiClient(`/`RuleClient(` in
  app.py. `tests/test_single_door.py` green unchanged (no exceptions
  added).

## Blocked

- (nothing)

## What not to trust

- The J1/J2/J3 tests exercise relay.py against a bare local origin;
  a real hosted origin may still surprise (push protections, hooks) —
  untested here, network budget forbids.
- The relay-commit skip in P6 allows only coordinator-owned files;
  if a hand ever needs to carry an executor file, P6 will red it —
  deliberately.

## Disputed

- (none)

## HANDOFF

Status:          DONE
Arrival state:   selfcheck OK at 8c88519 (13/13)
Items done:      J1, J2, J3 (first), I1, I2, I3, I4
Items not done:  none in TASK-42
Acceptance:      «Итог: пройдено 13, провалено 0», SELFCHECK OK at this commit (exit captured before any pipe)
Tests:           full default run 0 failed (687+; final counts in the last full run line)
Guards:          P6 relay-commit skip (coordinator files only); P1/p6 guards otherwise unchanged; declared replacements — none in this task
Schema:          unchanged (45)
Network:         0 of 0
Model:           0 of 0 (fake client drives the loop)
Secrets:         0 hits
Pushed:          yes
Questions for the coordinator:
1. The I2 refusal currently replaces the model's answer whenever any
   tool of the question reports absence — even if other tools of the
   same question returned data. A "partial data" middle path may be
   worth a ruling.
2. chat.py's order detection (I1) uses the deterministic RuleClient
   rules; a model-backed classifier would need its own budget line.

NOW: HANDOFF, step 8
