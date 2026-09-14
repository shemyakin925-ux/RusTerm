# TASK-33 — P5 и P6: светофор перестаёт быть серым

- **Status: READY**
- **Report:** `agent/REPORT-33.md`
- **Protocol:** `agent/PROTOCOL.md` (§12 — the relay). State: `agent/CONTEXT.md`.
- **Relay:** hand back with `python3 agent/relay.py hand --to coordinator --report agent/REPORT-33.md --note "<one line>"`, then `python3 agent/relay.py wait --for executor --timeout 3600`.
- **Budgets:** network **40 requests** to `data.sec.gov`; model 0.
- **Depends on TASK-32** for D2's payload. Without it, take P6 only and
  skip the rest — do not fabricate ownership rows.
- **Goal in one sentence:** TASK-25 P5 and P6 — `insider_net` lights up
  from real Forms 4 and the proxy channel (DEF 14A) is probed, so at
  least two of the five indicators stop being grey for every issuer.

## Ruling on TASK-32 (coordinator, 15.09.2026)

TASK-32 is **accepted**: D1–D7 all landed, the D5 rule works — the
declared `ЗАМЕНА-БУЛАВКИ` block in commit `e68c1b5` is exactly the shape
it was ordered in, and the 42 -> 43 literals rode through it.

**One regression found by review, not by your report: `agent/TASK.md` was
overwritten with its pre-10.09.2026 text** inside the D6 commit
(`e68c1b5`, 409 lines), together with unrelated work. The charter you
read at the start of every shift is now the old one on this branch.
Nothing in TASK-32 asked for it; it looks like a stale working-tree copy
caught by a wide `git add`. E5 repairs it, E6 makes it impossible.
Take E5 and E6 **first**, before E1 — they are minutes of work and the
charter is what the next shift reads.

**Scope is the text of TASK-25 P5 and P6 as written.**

## Items

### E1. `insider_net` загорается (P5)

**Done when:** for the issuer collected in TASK-32 the indicator has a
colour on the record, the number behind it is derived from the stored
transactions, and the report shows the arithmetic (buys, sells, net,
window). The 10b5-1 question is settled by the coordinator's ruling in
`agent/BACKLOG.md` — read it before you decide anything about it.

### E2. Живая проверка канала DEF 14A (P6)

**Done when:** the probe is recorded per endpoint (status, bytes,
format); if the proxy is a PDF without a machine-readable layer, that is
the answer and the path is manual import (P7, already built), not a
regular expression over HTML.

### E3. Цвет доказуем

**Done when:** every indicator that is not grey names the facts it was
computed from, and a test asserts that a colour without lineage cannot
be written at all.

### E4. Устаревание работает на реальных датах

**Done when:** a proxy older than the staleness window yields the
`stale` grey with its reason, asserted on the real document's date; the
window's number is the one ruled in `agent/BACKLOG.md`.

### E5. Хартия исполнителя возвращается на место

`agent/TASK.md` on this branch must become byte-identical to
`origin/main:agent/TASK.md` (the charter rewritten 10.09.2026). Use
`git checkout origin/main -- agent/TASK.md` — do not retype it.

**Done when:** `git diff origin/main -- agent/TASK.md` prints nothing,
and the report names the commit that introduced the regression
(`e68c1b5`) and what else that commit legitimately carried.

### E6. Файлы координатора перестают быть доступны широкому `git add`

`agent/selfcheck.sh` gains a guard (P6): a staged diff must not touch
files the coordinator owns —

    agent/TASK.md  agent/TASK-*.md  agent/PROTOCOL.md  agent/CONTEXT.md
    agent/BACKLOG.md  agent/LAUNCH.md  agent/acceptance.sh

Yours stay yours: `agent/REPORT-*.md`, `agent/STATE.json`,
`agent/BATON.json`, `agent/p1_rule.sh`, `agent/selfcheck.sh` itself, and
everything under `rusterm/`, `tests/`, `docs/adr/`. A red P6 names the
file and the command that undoes it (`git restore --staged <file> &&
git checkout -- <file>`).

**Done when:** a test like `tests/test_d5_p1_rule.py` covers three cases
— staging `agent/TASK.md`: red with the file named; staging
`agent/REPORT-33.md`: green; staging both: red — and
`bash agent/selfcheck.sh` is green on your own commit for this item.
