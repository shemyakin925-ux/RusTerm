# TASK-37 — Q3, Q7 и Q10: вопрос, приказ, незнание и экран

- **Status: READY**
- **Report:** `agent/REPORT-37.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network 0; model 0 (fake client).
- **Goal in one sentence:** the three undone halves of M12 — the loop
  tells a question from an order, says plainly what it does not know,
  and finally has a screen in the terminal.

**Scope is the text of TASK-26 Q3, Q7 and Q10 as written.**

## Items

### I1. Вопрос и приказ (Q3)

**Done when:** an order produces a **proposal** that executes nothing
until confirmed; a question never proposes; both paths are asserted, and
the audit row distinguishes them.

### I2. Разговор знает, чего не знает (Q7)

**Done when:** the three does-not-know cases (no fact, fact with a
reason, fact too stale) each produce a refusal naming the reason from
`rusterm/reasons.py` — never a hedged sentence, never an invented
number; asserted case by case.

### I3. Экран разговора (Q10)

**Done when:** the TUI screen shows turns, citations and the cost line;
piped output carries no ANSI (existing B11 rule); a test drives the
screen through the fake client and asserts the rendered lines, the way
the industry screen test does.

### I4. Экран не открывает новую дверь

**Done when:** the screen constructs no client of its own — it goes
through `make_intent_client`, and `tests/test_single_door.py` stays
green without an exception being added to it.
