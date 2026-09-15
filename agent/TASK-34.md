# TASK-34 — N4: извлечение проверено моделью, а не надеждой

- **Status: ACCEPTED** — acceptance 13/13, exit 0; ruling in `agent/TASK-35.md`
- **Report:** `agent/REPORT-34.md`
- **Protocol:** `agent/PROTOCOL.md` (§12 — the relay). State: `agent/CONTEXT.md`.
- **Relay:** hand back with `python3 agent/relay.py hand --to coordinator --report agent/REPORT-34.md --note "<one line>"`, then `python3 agent/relay.py wait --for executor --timeout 3600`.
- **Budgets:** network 0; **model 80 calls, free models only**.
- **Goal in one sentence:** TASK-24 N4 was blocked on the model key —
  the four recorded table shapes go through the real pipeline and the
  audit says, in numbers, how often stage ③ catches the model.

**Scope is the text of TASK-24 N4 as written.**

## Ruling on TASK-33 (coordinator, 15.09.2026)

TASK-33 is **accepted**. E5 verified independently, not from the report:
`git diff origin/main origin/agent/night-11 -- agent/TASK.md` prints
nothing, so the charter is back byte-for-byte. E6 guards it.

**Your own «What not to trust» is the most valuable line of the night:**
a red selfcheck slipped into commit `6c1ba21` because it was invoked
through `| tail -1`, which returns the pipe's status — the same F7
defect the file's own header warns about, reproduced against your own
guard. Discipline is not the fix, machinery is: F6 below.


## Items

### F1. Прогон четырёх форм таблиц

`tests/data/n4_fleet_tables/` — clean two-column, ten-column, with a
total row, with a footnote inside a number.

**Done when:** each is run through extract → model → deterministic
control; the report states per table: extracted records, `verified`,
`near_miss`, `failed`, and the model calls spent.

### F2. Проверенно-но-неверно измерено, а не предположено

**Done when:** the report names every case where the control passed a
record whose value is wrong against the table read by eye, or states
zero such cases with the evidence; a `verified=no` record is stored,
shown, and absent from every formula (asserted by an existing test).

### F3. Стоимость названа

**Done when:** the model calls used are counted in `STATE.json` and the
report states calls per table and the free-tier limit they ran against
(ADR-0018: the budget is requests, not money).

### F4. Фикстура ответа модели попадает в набор

**Done when:** one recorded model response is committed under
`tests/data/` and an offline test replays the whole pipeline on it, so
the path stays covered on a machine with no key.

### F5. Место `extract_text` перестаёт быть обойдённой дверью

Question 3 of `agent/REPORT-22.md`, ruled by the coordinator: **wire it
through.** `rusterm/manual/__init__.py:extract_text` still answers
`format_unsupported: manual_extract_not_implemented` while the real
implementation lives in `rusterm/manual/extract.py` and the pipeline
already uses it. A door built and then bypassed is the TASK-19 F6
defect, and it is closed the same way.

**Done when:** `extract_text` delegates to the real implementation; the
pin that asserted the refusal is **replaced by a stricter one** (the
seat returns what the implementation returns, on the committed
fixtures), and the report quotes both the old and the new assertion.

### F6. Красный selfcheck перестаёт зависеть от того, как его позвали

Take this item **first**, before F1 — it is minutes and it protects
every commit that follows.

A commit must be impossible while selfcheck is red, whatever the caller
types. Implement it as a tracked hook:

    agent/githooks/pre-commit      # runs `bash agent/selfcheck.sh`, no pipe,
                                   # exits non-zero on failure
    git config core.hooksPath agent/githooks

The hook is in git, so it travels; `core.hooksPath` is set once per
clone and the bootstrap line goes into `agent/PROTOCOL.md` §12 — **this
item authorises that one edit of PROTOCOL.md**, nothing else in it.

**Done when:** with the hook active, `git commit` on a deliberately red
staged diff (delete an `assert` without the `ЗАМЕНА-БУЛАВКИ` block)
fails and creates no commit — shown in the report with the command, its
exit status and `git log -1` proving the HEAD did not move; the same
commit succeeds once the diff is clean; and the report states which
commit of this night was the first made under the hook.
