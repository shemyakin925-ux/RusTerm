# TASK-106 — rulings on REPORT-104 / REPORT-92 Disputed

- **Status: READY**
- **Report:** `agent/REPORT-106.md`
- **Protocol:** `agent/PROTOCOL.md` (§12).
- **Budgets:** network 0, LLM 0.
- **Queue:** after TASK-107. Several small items: one commit may carry
  several ids in its subject («ТЗ-106 S1 S2: …»).

## Rulings

| # | Ruling | Item |
|---|---|---|
| 104/25 | a computed reporting currency is data: `upsert_issuer` never overwrites it; `watch add` passes `XXX` | S1 |
| 104/26 | TJS rows are real subsidiary disclosure — keep. No work | — |
| 104/27 | `build()` passes its own `as_of` to the governance hook | S2 |
| 104/28b | check 10 timing: acceptance.sh is frozen until the merge to main; rule added to PROTOCOL (check `git diff --cached --name-status origin/main -- docs/` before committing) | — |
| 104/29 | read-only commands (`census` w/o `--rebuild`, `metrics`, `doctor`, `status`, `industry`) do not migrate; they print «база: схема N, программе нужна M; обновите: rusterm --root … init» and exit 1 | S3 |
| 104/30 | accepted as shipped | — |
| 104/31 | `core/governance.py` docstring names ADR-0026 for v2 | S4 |
| 92/31, 92/34 | accepted; synonyms are a later item | — |
| 92/32 | no automatic rewrite; window and `doctor` say «база собрана до C1 — выполните rusterm reparse» when detectable | S5 |
| 92/33 | `listing.currency` from a venue → currency table in `markets.py` (`XXX` if unknown) | S6 |

Done-when for each: a test that is red before; S3 — test that a
schema-45 copy stays byte-identical after `census`.

## Do not

Same list as TASK-107.
