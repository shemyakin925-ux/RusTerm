# TASK-35 — Q4: три бесплатные модели, измеренные на этой задаче

- **Status: READY**
- **Report:** `agent/REPORT-35.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network 0; **model 200 calls, free models only** (ADR-0018).
- **Goal in one sentence:** TASK-26 Q4 was blocked on the key — three
  free models are measured on the chat task, and the project's default
  model becomes a number, not a preference.

**Scope is the text of TASK-26 Q4 as written.** ADR-0016 gates the
widening of model reach — read the ruling in `agent/BACKLOG.md` before
you interpret it.

## Items

### G1. Один и тот же корпус вопросов на три модели

**Done when:** the report holds a table — model id, questions asked,
answers with every number cited, answers rejected by the citation guard,
refusals, median latency, calls spent. The corpus is committed.

### G2. Враждебные случаи входят в замер

**Done when:** the four adversarial cases of Q5 run against each model
and the table states, per model, whether any produced a write, an
escaped tool call, a secret, or an uncited number.

### G3. Дефолт выбирается числами

**Done when:** `RUSTERM_LLM_MODEL`'s documented default is the model the
table justifies; the justification is two sentences in the report and
one line in `agent/CONTEXT.md`; a paid model is not compared, not
mentioned as an option and not recommended.

### G4. Прогон воспроизводим без ключа

**Done when:** the recorded responses are committed and an offline test
replays the corpus through the fake transport.
