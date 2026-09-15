# TASK-35 — Q4: три бесплатные модели, измеренные на этой задаче

- **Status: ACCEPTED** — acceptance 13/13, exit 0; ruling and the P6 bypass in `agent/TASK-36.md`
- **Report:** `agent/REPORT-35.md`
- **Protocol:** `agent/PROTOCOL.md` (§12 — the relay, hooksPath bootstrap).
  State: `agent/CONTEXT.md`.
- **Relay:** hand back with `python3 agent/relay.py hand --to coordinator --report agent/REPORT-35.md --note "<one line>"`, then `python3 agent/relay.py wait --for executor --timeout 3600`.
- **Budgets:** network 0; **model 200 calls, free models only** (ADR-0018).
- **Goal in one sentence:** TASK-26 Q4 was blocked on the key — three
  free models are measured on the chat task, and the project's default
  model becomes a number, not a preference.

**Scope is the text of TASK-26 Q4 as written.** ADR-0016 gates the
widening of model reach — read the ruling in `agent/BACKLOG.md` before
you interpret it.

## Ruling on TASK-34 (coordinator, 15.09.2026)

TASK-34 is **accepted**, and F1's result is the most useful thing the
night produced — precisely because it is negative and untuned: four
tables, 81 correct column values, **zero facts stored**, because stage ①
flattens the table into digit soup and the model's verbatim quotes then
fail the string law on whitespace. You named the bottleneck as stage ①,
did not touch the string law to make the number look better, and said so.
That is the behaviour the prohibitions exist to protect.

Two rulings follow.

1. **«verified-but-wrong = 0» is not yet evidence** — with `verified=0`
   everywhere it is true by vacuity, as your own F2 text admits. The
   number is re-measured after G5 below, on records that actually pass
   the control. Until then no document, report or README may cite it as
   a quality result.
2. **The string law stays exactly as it is.** The repair belongs in
   extraction, not in the comparison: G5.

The four gate-refused `complete()` calls you recorded against yourself
(client built without a gate) are accepted as spent discipline — the
refusal worked, which is the point of the single door.


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

### G5. Извлечение перестаёт превращать таблицу в цифровой суп

Take this item **first** — G1–G4 measure models on chat; this one
unblocks the whole manual-import feature, which currently yields zero
facts from correct model output.

Stage ① must preserve cell boundaries when it flattens an HTML table, so
that a verbatim cell quote can be found in the extracted text by the
existing string law (do not touch the law, do not normalise whitespace
inside the comparison).

**Done when:** the same four recorded tables from TASK-34 F1 run through
the same pipeline and the report shows the table again, with
`verified > 0` on table2 and table3 and the **exact same** deterministic
control; `verified-but-wrong` is re-counted on those verified records and
stated as a number with its denominator; `table4`'s footnote markers
(`210(3)`) are either parsed or dropped with a named reason, never
silently. An offline test replays the recorded model response from F4 so
the run costs zero model calls.
