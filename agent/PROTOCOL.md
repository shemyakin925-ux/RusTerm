# PROTOCOL — the working protocol for every task from TASK-29 on

This file replaces the §1 that used to be copied into every task. A task
file names its branch, its report, its budgets and its items; everything
else is here. **This file outranks the task list.** When a task and this
file disagree, the task wins only where it says so explicitly.

## 1. The cycle. One item = one pass

```
1. READ     the file you are about to change, in full. Not from memory.
2. SHOW     current state with a command, and look at the output.
3. CHANGE   exactly one item. Not two.
4. VERIFY   with the command from that item's "Done when".
5. SELFCHECK  bash agent/selfcheck.sh  (chained with &&, never ;)
6. COMMIT   immediately, before moving to the next item.
7. PUSH     immediately.
8. RECORD   one line in the task's report: command + its output.
```

## 2. Five prohibitions

- **P1. Never delete an `assert`.** A genuinely obsolete assertion is
  **replaced by a stronger one**, and the report says how the new one is
  stricter. Widening an assertion with `or …` to admit a new value is a
  deletion in disguise: either the vocabulary is extended where it is
  defined, or the test compares the way the code compares.
- **P2. Never edit an applied migration.** New migration, new number,
  `_SCHEMA_VERSION` bumped. Read the number from the file first.
- **P3. Leave nothing outside git.** Everything reported must be in
  `git ls-files`. Fetched data is the exception in §6.
- **P4. No `.bak`, `.orig`, temp databases, junk.**
- **P5. Never claim a check you did not run.** "Not run" is acceptable;
  "works" without command output is not.

## 3. Selfcheck before every commit

`bash agent/selfcheck.sh` runs all of it: no removed assertion, no
edited migration, nothing untracked, acceptance still green. A red
selfcheck means the commit does not leave your machine.

## 4. When stuck, and when something breaks

- The same thing fails after **three different hypotheses** about the
  cause (not three retries of one idea): stop, mark the test
  `@pytest.mark.xfail(strict=True, reason="…")` — never delete, never
  weaken — report what failed and which three hypotheses you tried, and
  move to the next item.
- A passing test starts failing: stop immediately,
  `git checkout -- <file>`.

## 5. Bookkeeping

- Commits: Russian, imperative, one thought. First line — what was done.
  Body — how it was verified, with the command's real output.
- The report is **append-only** (`>>` or a quoted heredoc; never `>`),
  verified after every write with `wc -c && tail -3`. Sections, in this
  order: **Done**, **Blocked**, **What not to trust**, **Disputed**,
  **HANDOFF**. Last line always `NOW: <item>, step <n>`.
- `agent/STATE.json`, same commit as the work:

```json
{"task": "agent/TASK-NN.md", "report": "agent/REPORT-NN.md",
 "item": "A1", "step": "4", "status": "working",
 "last_commit": "<sha>", "requests": 0, "net_requests": 0,
 "llm_calls": 0, "model": "<your model id>",
 "updated_at": "<ISO8601 UTC>"}
```

- Push after every commit. Push fails — do not retry in a loop:
  `PUSH UNAVAILABLE` as the first line of the report, keep committing
  locally, and at the end `git bundle create ../RusTerm-handoff.bundle
  --all` outside the repo.

## 6. Network and keys

- **The source is the `provider` column of the market registry**
  (ADR-0010), and every request goes through `RequestGate` — there is no
  other door.
- **Identify yourself or do not go.** `RUSTERM_SEC_UA` must carry a real
  contact. Unset or empty → `ConfigError` **value** and the offline
  path. Never hardcode, commit or invent a contact.
- **A key never enters git, a report, a log, a fixture or a commit
  message.** This covers `RUSTERM_SEC_UA`, `RUSTERM_LLM_API_KEY`,
  `RUSTERM_DART_KEY`, `RUSTERM_TWELVEDATA_KEY`. The keys exist in the
  environment from 13.09.2026 on: *having* them is normal, *printing*
  them is a defect.
- Per-task budget is named in the task file and counted in
  `STATE.json`. 403 or 429 is a stop, not a puzzle: back off, record,
  move on. Never change the User-Agent to defeat a refusal, never proxy,
  never mirror. 404 is an answer, not an error.
- Fetched data never enters git **except** trimmed payloads under
  `tests/data/<provider>/`. `fixtures/` stays synthetic-only.
- A network test skips cleanly when its key or UA is unset, and **never
  runs by default when it is set** — live tests carry the `live` marker
  (TASK-29 A2).

## 7. Money

**Everything in this project is free — ADR-0018.** No task may require a
subscription, a paid tariff, pay-as-you-go, a deposit or a card at
registration. Your own model: free tier only; a switch to a paid one is
recorded in `STATE.json` and is a `Disputed` entry, not a decision you
make alone.

## 8. Precedence when sources disagree

This file → the task file → `agent/CONTEXT.md` → `docs/` → existing
code → your judgement. A conflict between the first two is a
coordination bug: implement per the task file and record both quotes in
**Disputed**. Green code is extended, never refactored, except where an
item names the file and the defect.

## 9. What you may assume

- `python3` here is 3.14.x; the code must also run on 3.12. `pytest` is
  installed, `zstandard` is not, and acceptance check 11 reruns the
  suite without it.
- Acceptance is 13/13 at your start and is ground truth about your work.
  **If it is not green on arrival, the first commit of the night is the
  repair**, and the report says what was red when you arrived.
- `docs/` is frozen. A new ADR is the one permitted change.

## 10. Stop time and the shift's end

**10:00 Danang (UTC+7).** No new item after 09:30. Finish the current
item to a commit and a push, then fill in the HANDOFF block at the end
of the report:

```
Status:          DONE | PARTIAL | BLOCKED
Arrival state:   selfcheck STATUS= on the first run, before any commit
Items done:      …
Items not done:  … and why
Acceptance:      the "Итог" line and the exit status captured before any pipe
Tests:           N passed, N skipped, N xfailed
Guards:          which guard files were touched and how they got stricter
Schema:          _SCHEMA_VERSION <old> -> <new>, or "unchanged"
Network:         requests used of the budget, per host
Model:           app llm_calls N of the budget; your own model id
Secrets:         artefacts grepped for each key — hits (must be 0)
Pushed:          yes/no
Questions for the coordinator:
1. …
```

A night ends when the clock says so, not when the queue is empty: take
the next `Status: READY` task in numeric order and keep going.

## 11. Branches, and how a shift is taken from 13.09.2026 on

Tasks are now sized so that **five or six fit into one shift**. A shift
therefore has **one branch**, not one per task:

```bash
git checkout main && git pull
git checkout -b agent/night-<N>     # N = 10 for the first shift after 13.09.2026
```

Take tasks in **numeric order**, lowest `Status: READY` first, each with
its own report file, all on the shift branch. A task whose precondition
is missing is **skipped, not faked** — write `SKIPPED — <reason>` in its
report and take the next one. Do not merge into `main`: the release is
the coordinator's, by the user's word.

## 12. The relay: how a task is taken and handed back from 14.09.2026 on

A task no longer waits to be noticed. `agent/BATON.json` on the shift
branch names whose turn it is, and `agent/relay.py` blocks until the turn
comes. **Two commands bracket every task:**

```bash
# ход пришёл: ветка подтянута, следующее ТЗ названо
python3 agent/relay.py wait --for executor --timeout 3600

# работа сдана: отчёт запушен, ход у координатора
python3 agent/relay.py hand --to coordinator --report agent/REPORT-NN.md \
  --note "<one line: what is done, what is not>"
```

Rules:

- **Bootstrap (once per clone):** `git config core.hooksPath agent/githooks`
  — the tracked pre-commit hook (ТЗ-34 F6) then runs `bash
  agent/selfcheck.sh` without a pipe on every commit, so a red
  selfcheck cannot be committed whatever the caller types.
- **Commit and push your work first, then `hand`.** `hand` only moves the
  baton (plus files named with `--add`); it is not a substitute for §1.6-7.
- **Never push to the shift branch while the baton is not yours.** It is
  the coordinator's turn to write there; your push will be rejected as
  non-fast-forward. `wait` and `hand` rebase you onto the coordinator's
  commit by themselves (`pull --rebase --autostash`).
- `wait` exit codes: `0` your turn, `2` timeout (run it again), `3`
  paused by the user, `4` the cycle is closed — in cases 3 and 4 stop and
  write nothing further.
- The baton does not replace `agent/STATE.json`: keep writing it per §5.
- The relay is transport, not permission: §10 (stop time) and the
  prohibitions of §2 outrank it.
