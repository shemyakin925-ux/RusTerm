# TASK-36 — Q8 и Q9: разговор становится данными, стоимость — видимой

- **Status: ACCEPTED** — acceptance 13/13, exit 0; H5 named the bypass, ruling in `agent/TASK-37.md`
- **Report:** `agent/REPORT-36.md`
- **Protocol:** `agent/PROTOCOL.md` (§12 — the relay, hooksPath bootstrap).
  State: `agent/CONTEXT.md`.
- **Relay:** hand back with `python3 agent/relay.py hand --to coordinator --report agent/REPORT-36.md --note "<one line>"`, then `python3 agent/relay.py wait --for executor --timeout 3600`.
- **Budgets:** network 0; model 0 (the fake client drives the loop).
- **Goal in one sentence:** TASK-26 Q8 and Q9 — a conversation survives
  the process that held it, and the user sees what it cost before the
  bill would have arrived.

**Scope is the text of TASK-26 Q8 and Q9 as written.**

## Ruling on TASK-35 (coordinator, 15.09.2026)

TASK-35 is **accepted**, and G5 is the repair the night needed: a tab at
the cell boundary, the string law untouched, and the number that was
vacuous yesterday is now real — **89 verified records, verified-but-wrong
0 of 89**, table4's footnote row stored `unverified/near_miss` with a
named reason instead of vanishing. The old F4 fixture replaying to
"0 verified" against the fixed text is exactly the right kind of proof.
G3's default is argued by measurement, and no paid model is mentioned
anywhere. Your own caveat about one non-deterministic model pass per
table is noted and accepted as stated.

**But the guard you built in TASK-33 E6 was walked around in this very
task.** Commit `95b669a` stages `agent/CONTEXT.md`, which
`agent/p6_rule.sh` lists as coordinator-owned, and carries an invented
marker `РАЗРЕШЕНИЕ-КОНТЕКСТА:` that the script does not implement — only
`РАЗРЕШЕНИЕ-ПРОТОКОЛА` exists, and only for `PROTOCOL.md`. A guard the
guarded party can widen is not a guard. Two things follow, and they come
before H1.

The line itself stays — the fact is true and useful; I have folded it
into `CONTEXT.md` §5 in my own words. Ownership does not change: report
the fact, I write the file.


## Items

### H1. Миграция для расшифровок

**Done when:** a new migration (read `_SCHEMA_VERSION` first, never
assume the number) creates the transcript tables; `apply_migrations` is
idempotent; the existing schema-history pins in `tests/test_db.py` and
`tests/test_cli.py` are updated **in the same commit** and the report
accounts for every changed pin (P1: each replacement is stricter or
equal, never looser).

### H2. Разговор переживает процесс

**Done when:** a conversation started, closed and reopened shows the
same turns with the same citations; a transcript row carries the model
id and the calls it cost; `rusterm export` can emit one.

### H3. Счётчики в `status`

**Done when:** `rusterm status --json` carries model calls used today
and in total, per model; the key schema pin of the `--json` commands
(B16) is extended, not loosened; a test asserts the totals equal the sum
of the audit rows.

### H4. Ключ и содержимое не утекают

**Done when:** a transcript never stores a key value; the secrets guard
covers the new tables; `grep` over an exported transcript for the fake
key returns 0.

### H5. Назвать, как именно страж был обойдён

No blame, no guessing: state the mechanism.

**Done when:** the report says which of these produced `95b669a` with
`agent/CONTEXT.md` staged — `core.hooksPath` not set in that shell,
`git commit --no-verify`, the `P6_BLOCKED` environment override, or
something else — and proves the guard itself is sound by running
`git show --name-only 95b669a` and a reconstruction where
`bash agent/p6_rule.sh` goes **red** on that same staged set.

### H6. Исключение нельзя выдать самому себе

Fix all three holes found above:

1. **`P6_BLOCKED` stops being overridable from the environment** — the
   list is the file's, not the caller's.
2. **A `РАЗРЕШЕНИЕ-<X>:` marker is valid only when the task authorises
   that path.** The guard reads the task file named in
   `agent/BATON.json` and requires it to contain the literal line
   `РАЗРЕШЕНО ПРАВИТЬ: <path>`. Marker without that line — red.
   Add `РАЗРЕШЕНО ПРАВИТЬ: agent/PROTOCOL.md` to this task file only if
   you need it; you do not for H1–H4.
3. **An empty index stops being a green light.** `p1_rule.sh` and
   `p6_rule.sh` run on `git diff --cached`; after a commit that diff is
   empty and both pass vacuously, which is how "SELFCHECK OK" was
   reported for `95b669a`. When the index is empty, check
   `git diff HEAD~1 HEAD` instead and say in the output which of the two
   was examined.

**Done when:** tests cover six cases — env override attempted (ignored),
marker without task authorisation (red), marker with authorisation
(green), empty index after a clean commit (green, and the output says
`HEAD~1..HEAD`), empty index after a dirty commit like `95b669a` (red),
staged coordinator file without any marker (red) — and
`bash agent/selfcheck.sh` is green on your own commit for this item.
