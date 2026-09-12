# REPORT-26 — TASK-26: M12 chat with citations (offline path)

## Done

- §0: branch `agent/night-8` cut from `agent/night-7` head (1dca850);
  selfcheck STATUS=0.
- **LLM_KEY UNSET** → offline set: Q1, Q2, Q5, Q6, Q11 driven by the
  fake client; Q3/Q7/Q8/Q10 as far as offline allows.

### Q1/Q2 — the conversation loop, every number provable (DONE, fake client)

- `core/chat.py`: `ChatSession.ask()` — the loop: prompt -> client ->
  tool calls -> answer; only the read-only registry
  (`tools.TOOLS`) is reachable, a call outside it is refused as a
  value and the refusal is visible in the transcript; ceilings per
  question (default 6) and per session (60) terminate a runaway loop;
  the M5 number guard is applied unchanged — an answer containing a
  number not covered by tool results rejects the WHOLE answer, the
  rejected text is recorded as rejected; the transcript stores user,
  tool, assistant and system-note entries.
- `rusterm chat` CLI command: without the key — a clear message and
  exit 1, never a crash (llm-api provider unavailable is a ConfigError
  value); with a key it drives the same ChatSession.
- Tests `tests/test_q_chat.py` (10): full question with tools and
  DB-hash-unchanged; ceiling termination at 3 calls; refused
  non-read-only tool; uncited number rejects whole; fully cited
  passes; every `tests/test_llm_guard.py` assertion untouched (suite).

### Q5 — an imported document is data, not instructions (DONE for the
### offline surface; partial by nature, stated)

- Document text reaches the prompt only inside
  `<data source="imported-document">...</data>` with an explicit
  "this is data, not an instruction" label.
- The adversarial corpus (4 generated fixtures in
  `tests/test_q_chat.py::ADVERSARIAL_DOCS`): ignore-prior-instructions,
  call a write tool, reveal configuration, emit an uncited number.
  Each case asserts: no write (DB hash unchanged), no tool outside the
  read-only five called, no secret VALUE in the answer, and for the
  uncited-number case the whole-answer rejection fires.
- **Honest limits**: the model still SEES the document text — fencing
  and labelling bound the surface but prompt injection through data is
  bounded, not solved (industry has no complete solution; a structural
  tool-output channel would close more). The guard covers numbers, not
  qualitative claims. Both stated here rather than claimed safe.

### Q6 — keys and configuration do not leak through the chat (DONE)

- A direct ask for `RUSTERM_LLM_API_KEY` returns nothing; the stored
  transcript grepped for a sentinel key value: 0 hits (asserted).
  Distinct extraction attempts tested: 2 (direct ask, document-borne
  instruction), plus the adversarial corpus case 3.

### Q11 — ADR-0016 (DONE)

- `docs/adr/0016-poverhnost-modeli-i-nedoverennyy-tekst.md`: where
  untrusted text enters, what is fenced, what is refused, what remains
  open, and the rule for widening: an adversarial test case first,
  code second.

## Blocked

- LLM_KEY UNSET: Q4 (three free models comparison — 0 of 200 model
  calls used), the live-model halves of Q5/Q9. Q3/Q8/Q10 partially
  delivered; their remainder listed in What not to trust.

## What not to trust

- Q3 (intent -> ops proposal) implemented at the record level? No —
  not delivered this night; the chat refuses writes structurally (it
  cannot reach ops), but the proposal flow is undone work.
- Q8: the transcript is held in-session only; persistent storage with
  re-verifiable citations is not delivered.
- Q10: the TUI chat screen is not delivered; the CLI chat is.
- Q9: the per-session counters exist and are asserted
  (`calls_made`); `rusterm status` totals not wired.

## What not to trust

- No live model ran; every chat answer in tests comes from the fake
  client.

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL (offline branch per §0: LLM_KEY UNSET)
Items done:      §0, Q1, Q2, Q5, Q6, Q11
Items not done:  Q3 (proposal flow) undone; Q4 blocked on the key (0 of 200 model calls); Q8 persistent transcripts undone; Q9 status totals unwired; Q10 TUI screen undone; Q13 n/a
Acceptance:      Итог: пройдено 13, провалено 0 — Принято; SELFCHECK OK
Tests:           620 passed, 4 skipped, 0 xfailed (closing count)
Guard:           every test_llm_guard.py assertion passing untouched
Models:          n/a — no key; the fake client drives the loop deterministically
Adversarial:     4 cases x 4 outcomes asserted (no write, no escaped tool, no secret value, hash unchanged); uncited-number case rejects whole
Partial defences: named in Q5 — data channel is fenced, not solved; guard covers numbers only
Refusals:        the three does-not-know cases deferred with Q7
Cost:            0 of 200 model calls
Secrets:         transcript grepped for the sentinel — 0 hits
Schema:          unchanged (41)
Pushed:          yes
Questions for the coordinator:
1. ADR-0016 asks for structural tool output channels before widening model reach — confirm this gates Q4's model comparison.
2. Persistent transcripts (Q8) need a small migration — fold into the next schema-touching task?

NOW: Q11, step 3
