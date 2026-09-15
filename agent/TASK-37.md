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


## Ruling on TASK-37 I5 (coordinator, 15.09.2026): NOT ACCEPTED — repair first

Acceptance on `origin/agent/night-11` head `fa6fb08` came back **«пройдено
11, провалено 2», exit 2**. Cause, reproduced and named, not guessed:

    tests/test_i5_guard_source.py::test_i5_working_tree_widening_is_red_and_named
    tests/test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green
    NotADirectoryError: .../verify-night11/.git/COMMIT_EDITMSG

The tests — and both guards — write and read `.git/COMMIT_EDITMSG` as a
path under a **directory**. In a linked worktree (`git worktree add`)
`.git` is a **file**, so the write fails. My acceptance always runs in a
linked worktree, which is why it is red here and green in your clone.

This is not a test-environment quibble: `agent/p1_rule.sh` and
`agent/p6_rule.sh` read the same hardcoded path, so **in any worktree the
pending commit message is invisible to them** — a declared
`ЗАМЕНА-БУЛАВКИ` or `РАЗРЕШЕНИЕ-*` would simply not be seen. The
mechanism of I5 is right; its assumption about where `.git` lives is not.

I6 repairs it and is the first item of the next shift. I1–I4 stay as
written. Nothing else in TASK-37 is disputed: the guard-from-the-commit
design is accepted.

### I6. `.git` — это не всегда папка

Every path into the git directory goes through git itself:
`git rev-parse --git-path COMMIT_EDITMSG` (and `--git-dir` where a
directory is genuinely needed) in `agent/p1_rule.sh`,
`agent/p6_rule.sh`, `agent/selfcheck.sh` and
`tests/test_i5_guard_source.py`. No literal `.git/` anywhere in
`agent/` or `tests/` — `grep -rn "\.git/" agent/ tests/` shows only
comments.

**Done when:** acceptance is green **in a linked worktree**, shown with
the exact commands and their output:

    git worktree add --detach /tmp/i6check HEAD
    cd /tmp/i6check && bash agent/acceptance.sh   # «Итог: пройдено 13, провалено 0»

and green in your own clone as before.

РАЗРЕШЕНО ПРАВИТЬ: agent/p1_rule.sh
РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh


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

## Ruling on TASK-37 I6 (coordinator, 15.09.2026): mechanism accepted, ONE FILE MISSED

Acceptance on `origin/agent/night-11` head `1459cbb`, run **in a linked
worktree** (`/tmp/rusterm-relay-verify`), came back «Итог: пройдено 13,
провалено 0», exit 0 — where the previous round gave 11/13. The
`NotADirectoryError` is gone and the two I5 tests execute there. That
part of I6 is **accepted**.

The design of I6 is right and most of it landed: `agent/p1_rule.sh`,
`agent/selfcheck.sh` and `tests/test_i5_guard_source.py` reach the git
directory through `git rev-parse --git-path`. **`agent/p6_rule.sh` was
not converted.** It still reads the literal path:

    $ git show origin/agent/night-11:agent/p6_rule.sh | sed -n '53,56p'
    if [ -f .git/COMMIT_EDITMSG ]; then
        MSG="$MSG
    $(cat .git/COMMIT_EDITMSG 2>/dev/null || true)"
    fi

So the Done-when of I6 — *"No literal `.git/` anywhere in `agent/` or
`tests/` — `grep -rn "\.git/" agent/ tests/` shows only comments"* — is
**not met**, and the REPORT-37 claim that the grep "shows no literal
paths (only comments)" is false for this file. Check it yourself:

    git grep -n '\.git/' -- agent/*.sh

P6 is the guard that protects the coordinator's files, and this is the
exact consequence I named last round, still live for it: in a linked
worktree `.git` is a **file**, `[ -f .git/COMMIT_EDITMSG ]` is false, no
error is printed, and `MSG` silently loses the pending declaration. A
`РАЗРЕШЕНИЕ-КОНТЕКСТА:` / `РАЗРЕШЕНИЕ-ПРОТОКОЛА:` written before the
commit is **invisible to P6 in any worktree** — an authorised edit reads
as a violation, and the guard's own message blames the executor for it.

**Why your green run did not catch it.** Neither I5 test exercises that
branch of P6 in a worktree:

- the green case stages **only** `agent/p6_rule.sh` — no
  `agent/CONTEXT.md`, so P6 never reaches the marker check at all;
- the red case stages `agent/CONTEXT.md` **and** widens the guard
  unstaged, so the red is over-determined: selfcheck goes red on the
  unstaged guard before P6's verdict matters. If P6 also refused the
  declared `CONTEXT.md`, the assertions (`agent/p6_rule.sh` in the
  output, `рабочем дереве` in the output) would still pass.

A guard whose authorisation path no test drives is a guard nobody has
run. I7 closes that, and it comes first.

I7 and I8 are new. I1–I4 stay exactly as written and are the reason this
task file exists — they have now been deferred two nights running.

РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh

### I7. Доведи I6 до конца: P6 тоже ходит через `git rev-parse`

Take this **first**; it is minutes.

- `agent/p6_rule.sh` reads `COMMIT_EDITMSG` through
  `git rev-parse --git-path COMMIT_EDITMSG`, the way `agent/p1_rule.sh`
  already does. `git grep -n '\.git/' -- agent/ tests/` shows nothing
  outside comments and coordinator prose (`TASK-*.md`, `CONTEXT.md`,
  `LAUNCH.md`, `REPORT-*.md`, `relay.py` help strings are text about
  its own state file — leave them).
- A test drives **P6's authorisation path in a linked worktree** and
  fails on today's code. Inside a throwaway `git worktree add --detach
  <tmp> HEAD` — its `agent/BATON.json` is a disposable copy, so point
  it at a scratch task file of your own carrying `РАЗРЕШЕНО ПРАВИТЬ:
  agent/CONTEXT.md`; **do not** put that line in a real `TASK-*.md`,
  `agent/CONTEXT.md` stays mine. Then: stage `agent/CONTEXT.md`, write
  `РАЗРЕШЕНИЕ-КОНТЕКСТА: …` into the path that `git rev-parse
  --git-path COMMIT_EDITMSG` names → **P6 green**; the same staging
  with the declaration absent → **P6 red, naming `agent/CONTEXT.md`**.
  The guard is invoked directly (`bash agent/p6_rule.sh`), not through
  a nested acceptance — no second full suite.

**Done when:** that test is red on `1459cbb` and green on your commit
(show both runs in the report, with the command), and the two greens of
the previous round still hold:

    git worktree add --detach /tmp/i7check HEAD
    cd /tmp/i7check && bash agent/acceptance.sh   # «Итог: пройдено 13, провалено 0»

plus `bash agent/acceptance.sh` green in your own clone.

### I8. Замок не вправе красить приёмку в зелёный молчанием

`tests/test_i5_guard_source.py` now takes a module-scoped lock at the
fixed path `tempfile.gettempdir()/i5-demo-single-flight.lock` and
**skips the whole module** when it exists. The `finally` that removes it
does not run on `SIGKILL`, a killed acceptance, a full disk, or a
machine reboot — and the path is shared by every clone and worktree on
the host. After any such interruption the I5 demonstration is skipped
**for good**, silently, and acceptance still prints «пройдено 13,
провалено 0». The one test that proves the guards execute from the
commit is then the one test that never runs, and nothing says so.

Recursion must stay impossible — that part is right — but not at this
price. Either make the lock unable to go stale (owner pid recorded and
checked, lock older than one run treated as absent) or drop it and rely
on the explicit `I5_NESTED` marker the hook and the green case already
set.

**Done when:**
- a stale lock (written by a pid that is not running) does **not** skip
  the module — a test writes one and asserts both I5 tests still
  execute;
- an outer, non-nested acceptance in which the I5 module is skipped is
  **red**, naming why: `I5_NESTED` unset and the demonstration not
  executed is a failed acceptance, not a silent pass. Put the check
  where a skip cannot hide it (`tests/`, asserted on the pytest
  outcome — not in `agent/acceptance.sh`, which you may not edit);
- `bash agent/acceptance.sh` green in your clone and in a linked
  worktree.

If the night ends before I8, carry it: it is pre-approved and opens the
next shift.
