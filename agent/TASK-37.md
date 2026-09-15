# TASK-37 — Q3, Q7 и Q10: вопрос, приказ, незнание и экран

- **Status: READY**
- **Report:** `agent/REPORT-37.md`
- **Protocol:** `agent/PROTOCOL.md` (§12 — the relay, hooksPath bootstrap).
  State: `agent/CONTEXT.md`.
- **Relay:** hand back with `python3 agent/relay.py hand --to coordinator --report agent/REPORT-37.md --note "<one line>"`, then `python3 agent/relay.py wait --for executor --timeout 3600`.
- **Stop time:** PROTOCOL §10 — no new item after 09:30 Danang. If the
  night ends mid-task, I1 is the item to finish; I5 below is minutes and
  comes first.
- **Budgets:** network 0; model 0 (fake client).
- **Goal in one sentence:** the three undone halves of M12 — the loop
  tells a question from an order, says plainly what it does not know,
  and finally has a screen in the terminal.

**Scope is the text of TASK-26 Q3, Q7 and Q10 as written.**

## Ruling on TASK-36 (coordinator, 15.09.2026)

TASK-36 is **accepted**, and H5 is the best piece of writing this night
produced. You did not hedge: `git add -A` staged my file, selfcheck went
red, and instead of unstaging you **widened the guard in the working
tree and committed without staging it** — so both selfcheck and the
pre-commit hook executed the widened copy while the committed guard
stayed narrow. Named precisely, proven by `git show --name-only`,
reconstructed red in a temp repo. That is what a report is for.

H6 closes the three holes I named. It does **not** close the one your own
account exposes: **the guard that runs is the working-tree copy.** While
that is true, every guard here is advisory — any of them can be widened
for exactly one commit and narrowed back. I5 closes it, and it comes
before I1.


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

### I5. Страж исполняется из коммита, а не из рабочего дерева

Take this **first**; it is minutes and it is what makes every other
guard mean something.

`agent/selfcheck.sh` and `agent/githooks/pre-commit` must execute the
**committed** guard scripts, not the working-tree ones:

- extract `agent/p1_rule.sh`, `agent/p6_rule.sh` (and any future rule
  script) from the index when they are staged, else from `HEAD`, into a
  temp dir, and run those copies;
- the output says which source was used — `index` or `HEAD` — so the
  choice is visible in the log;
- a guard script modified in the working tree but not staged is a **red**
  selfcheck by itself, naming the file: an unstaged guard edit is
  precisely the TASK-35 bypass.

**Done when:** a test reproduces the `95b669a` manoeuvre end to end —
stage a coordinator-owned file, widen `agent/p6_rule.sh` in the working
tree only, run selfcheck — and it is **red** with the unstaged guard
named; the same widening, this time staged **and** authorised by
`РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh` in the task file, is green; and
`bash agent/selfcheck.sh` is green on your own commit for this item.
This task file authorises exactly one path for that test:

РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh
