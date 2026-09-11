# TASK-26 — M12: вторая половина M5. Чат с цитатами и оборона поверхности модели

- **Status: READY** — take it when `agent/TASK-25.md` is finished and
  handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-8` (branch it from the head of `agent/night-7`)
- **Report:** `agent/REPORT-26.md`
- **Sequential, one process.** Large night.
- **Depends on** TASK-19 F6 / TASK-20 L7 (the API client) and the four
  read-only tools from M5. Runs without TASK-24 and TASK-25.
- **Goal of the night, in one sentence:** milestone M12 — M5 delivered
  the citation guard, the four read-only tools and confirmed mass
  operations, but never the conversation they were built for; tonight
  the user can ask a question in the terminal and get an answer in which
  **every number is traceable**, and the surface that opens by doing so
  is defended rather than assumed safe.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-7 && git pull
git checkout -b agent/night-8
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -c "import rusterm.core.tools as t; print([n for n in dir(t) if not n.startswith('_')])"
printenv RUSTERM_LLM_API_KEY | cut -c1-4
```

`STATUS=0` required. Without the key: do Q1, Q2, Q5, Q6, Q7, Q8, Q11
(all offline, driven by the fake client), write `LLM_KEY UNSET` in
`## Blocked`, and skip the items that need a live model.

**First commit:** create `agent/REPORT-26.md` with its five section
headers and repoint `agent/STATE.json` at it in the same commit.

Read, in full: `rusterm/core/llm.py`, `rusterm/core/tools.py`,
`rusterm/core/ops.py`, `rusterm/core/intent.py`,
`rusterm/providers/llm_api.py`, `docs/llm-prompts.md`,
`docs/watchlist-and-llm.md`, `tests/test_llm_guard.py` (**all of it —
the guard is the law this night obeys**), `agent/TASK.md`.

## 0.1. What was measured before this task was written

| Command | Result |
|---|---|
| `grep -rn "chat" rusterm/ --include="*.py"` | **nothing** — there is no conversational loop |
| `tests/test_llm_guard.py` | the citation guard is built and strict: an invented number rejects the **whole** text; substring numbers, repeated tokens and thousand separators are all handled |
| `rusterm/core/tools.py` | four read-only tools, and a test asserts the database hash is unchanged after calling all four |
| `rusterm/core/ops.py` | mass operations: dry-run by default, `--confirm` applies, 100-item ceiling, every outcome audited |

README §15 defines M5 as «чат с цитатами и массовые операции над
watchlist». The second half shipped in TASK-16. **The first half never
did.** Everything it needs already exists; what is missing is the loop.

## 0.2. The surface this opens, and why half the night is defence

Adding a conversation joins three things that were previously separate:
a model that can call tools, documents brought in from outside by the
user (ADR-0011), and an operations path that can modify a watchlist.

That is a chain worth stating plainly: **text the user did not write
can reach a model that can call tools.** An imported annual report is
attacker-influenced input in exactly the way a web page is. This is not
hypothetical and it is not paranoia — it is the ordinary consequence of
the feature, and the defences below are the price of shipping it.

The existing guarantees are the foundation and are **not** weakened:
tools are read-only and proven so by hash; `ops` is dry-run by default,
capped, confirmed and audited; every number must be cited.

## 0.3. Decisions taken. Not open for re-litigation

1. **The guard is not relaxed for the chat.** A number without a
   citation rejects the whole answer, exactly as in `test_llm_guard.py`.
   If that makes the chat terse, the chat is terse.
2. **The chat never writes.** It reads through the four read-only tools.
   A request to change something is routed to `ops`, which keeps its
   dry-run, its ceiling, its confirmation and its audit.
3. **One LLM option: the API** (ADR-0011 ②). No local model.
4. The key comes from `RUSTERM_LLM_API_KEY` and never enters git, a log,
   a report or a test.

---

## 1. Working protocol. This outranks the task list

Identical to `agent/TASK-19.md` §1. Tonight's specifics:

- **Network budget: 0 requests to data sources.** **Model calls: 200
  maximum, free models only.** Count them in `STATE.json` `"llm_calls"`.
- **P1 applies to `tests/test_llm_guard.py`.** Not one assertion there
  is deleted or loosened. A guard test that becomes inconvenient is a
  finding, not an obstacle — `Disputed`, and move on.
- `docs/` is frozen; a new ADR is the one permitted change.

---

## 2. The work, in priority order

### Q1. Петля разговора, которая ничего не пишет

`rusterm/core/chat.py` (new), `rusterm/cli/__init__.py`.

- `rusterm chat` — a terminal conversation: question, tool calls,
  answer, repeat. History held for the session.
- Only the four read-only tools are reachable. **A tool outside that set
  is refused as a value** and the refusal is visible in the transcript.
- Bounded: a maximum number of tool calls per question and a maximum
  total per session, both configurable, both enforced — a loop that
  cannot terminate is a bug that costs the user money.
- No key → a clear message and exit, never a crash.

**Done when:** a test drives a full question with a fake client and
asserts the answer, the tool calls made, and that the database hash is
**unchanged**; a test asserts the call ceiling terminates a runaway
loop; a test asserts an attempt to call a non-read-only tool is refused.

### Q2. Каждое число в ответе доказуемо

**Needs:** Q1. `rusterm/core/llm.py` — reuse, do not rewrite.

The guard from M5 already rejects an answer containing a number that is
not substituted from a cited source. Apply it to the chat unchanged.

- Every number in an answer resolves to a tool result, and the answer
  carries the reference.
- A failed guard rejects the **whole** answer and says so — it does not
  strip the offending number and serve the rest.
- The transcript records what was rejected, so a user can see the model
  tried.

**Done when:** a test asserts an answer with an invented number is
rejected whole; a test asserts a fully cited answer passes; every
existing assertion in `tests/test_llm_guard.py` still passes untouched.

### Q3. Разговор различает вопрос и приказ

**Needs:** Q1. `rusterm/core/intent.py` — it exists; extend it.

- A request that would change state is **not executed by the chat.** It
  is turned into a proposed `ops` command, shown to the user, and
  applied only through the existing confirmed path.
- The 100-item ceiling, the dry-run default and the audit record are
  unchanged.

**Done when:** a test asserts "добавь MSFT в список" from the chat
produces a **proposal** and writes nothing; a test asserts applying it
goes through `ops` with confirmation and lands in the audit log.

### Q4. Три бесплатные модели, измеренные на этой задаче

**Needs:** Q1, Q2, the key. **Model calls: 200 maximum.**

- Run a fixed set of questions through at least three free models.
- Record, per model: answers produced, answers **rejected by the
  guard**, tool calls used, latency, and cost if any.
- The rejection rate is the number that matters — a model that writes
  beautiful prose full of uncited numbers is useless here.
- The production model is `glm-5.3-flash`; a paid key may be absent, so
  record what free models do and **do not pin a default that needs
  money.**

**Done when:** the comparison table is in the report; no key appears in
it.

### Q5. Импортированный документ — не инструкция

**Needs:** TASK-20 L6. **The most important item of the night.**

Text inside a user-imported document can be written to be read by a
model. The chat can reach document-derived content through tools. So:

- Document-derived text reaching the model is **fenced and labelled as
  data**, never concatenated into the instruction position.
- A test corpus of adversarial documents: text instructing the model to
  ignore prior instructions, to call a write tool, to reveal
  configuration, to emit a number as if cited. **Each is a test case
  with an asserted outcome.**
- The asserted outcome in every case: no write occurs, no tool outside
  the read-only four is called, no configuration value appears in the
  answer, and the database hash is unchanged.
- Where a defence cannot be complete, say so in the report plainly
  rather than claiming safety. **An honest limit stated is worth more
  than a guarantee that is not true.**

**Done when:** the adversarial corpus exists as generated fixtures; every
case asserts the four outcomes above; the report names any case where
the defence is partial and explains what would close it.

### Q6. Ключи и конфигурация не вытекают через разговор

`rusterm/core/chat.py`, `rusterm/providers/llm_api.py`.

- No environment value, key, path outside the data root, or internal
  configuration is reachable through a tool result or an answer.
- A test asks for each of them directly and asserts none is returned.
- The transcript is stored **without** the key, and the test greps the
  stored transcript for the key value.

**Done when:** all three pass; the report states how many distinct
extraction attempts were tested.

### Q7. Разговор знает, чего не знает

**Needs:** Q1, Q2.

An analyst tool that guesses is worse than one that refuses.

- A question whose answer needs data the database does not hold returns
  **the coverage reason**, not an approximation and not general
  knowledge about the company.
- The chat distinguishes "no such issuer", "issuer present, measure
  grey with reason X", and "outside what this program knows".

**Done when:** a test drives all three and asserts distinct, specific
answers; a test asserts a question about an uncollected issuer does not
produce a number from the model's own knowledge.

### Q8. Расшифровка разговора — часть данных, а не экран

`rusterm/store/`, one migration if needed — read `_SCHEMA_VERSION`.

- The transcript is stored with its tool calls, its citations and its
  rejections, and it is exportable.
- A past answer can be **re-verified** later: its citations still
  resolve, or the transcript says which no longer do because the data
  moved on.
- Transcripts are covered by `backup` (TASK-22 J4).

**Done when:** a test round-trips a transcript and re-resolves its
citations; a test asserts a citation invalidated by newer data is
reported as such rather than silently re-resolving to a new number.

### Q9. Стоимость видна до того, как счёт пришёл

`rusterm/core/chat.py`, `rusterm/cli/__init__.py`.

- Per session and cumulatively: calls made, tokens if the endpoint
  reports them, and the model used.
- A configurable ceiling stops the session rather than continuing
  silently.
- `rusterm status` shows the running total.

**Done when:** a test asserts the ceiling terminates a session; `status`
shows the totals on a database with recorded sessions.

### Q10. Экран разговора в терминале

**Needs:** Q1. `rusterm/tui/`.

- A chat screen: question, answer, and **citations a user can open into
  the source panel that already exists.**
- The TUI still computes nothing and writes nothing directly; the chat
  path is invoked through the same functions the CLI uses.
- Pure functions in `model.py`, tested headless.

**Done when:** `python3 -m pytest tests/test_tui_model.py -q` green; a
test builds the screen's rows without importing `curses`.

### Q11. ADR о поверхности модели

`docs/adr/0016-poverhnost-modeli-i-nedoverennyy-tekst.md` (**a new ADR —
the one permitted change to `docs/`**).

Write down what was decided and what was measured in Q5: where
untrusted text enters, what is fenced, what is refused, what remains
open. This is the document the next coordinator reads before widening
the model's reach.

**Done when:** the ADR exists and `bash agent/selfcheck.sh` exits 0.

### Q12. Веха M12, со своими доказательствами

Answers produced and rejected per model, the adversarial results case by
case, cost per session, and what M12 does not cover — named honestly.

**Done when:** `bash agent/selfcheck.sh` exits 0; `agent/STATE.json` is
`"status": "awaiting_review"`.

### Q13. Backlog

`agent/BACKLOG.md`, top-down, only if Q1–Q12 are done before 09:30.

---

## 3. Closing the shift

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      Q1, Q2, …
Items not done:  … and why
Acceptance:      the "Итог" line and the captured exit status
Tests:           N passed, N skipped, N xfailed
Guard:           every assertion in test_llm_guard.py still passing?
Models:          per model — answers, guard rejections, tool calls, latency
Adversarial:     per case — write occurred? tool escaped? config leaked? hash changed?
Partial defences: named plainly, with what would close each
Refusals:        the three "does not know" cases, asserted
Cost:            calls made of the 200 ceiling; tokens if reported
Secrets:         transcript grepped for the key — hits (must be 0)
Schema:          _SCHEMA_VERSION <old> -> <new>, or "unchanged"
Model:           app llm_calls N; your own model id
Pushed:          yes/no
Questions for the coordinator:
1. …
```
