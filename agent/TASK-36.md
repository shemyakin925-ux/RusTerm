# TASK-36 — Q8 и Q9: разговор становится данными, стоимость — видимой

- **Status: READY**
- **Report:** `agent/REPORT-36.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network 0; model 0 (the fake client drives the loop).
- **Goal in one sentence:** TASK-26 Q8 and Q9 — a conversation survives
  the process that held it, and the user sees what it cost before the
  bill would have arrived.

**Scope is the text of TASK-26 Q8 and Q9 as written.**

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
