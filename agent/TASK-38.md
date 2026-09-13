# TASK-38 — N7, бразильская половина: `ingest --source cvm`

- **Status: READY**
- **Report:** `agent/REPORT-38.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **30 requests** to `dados.cvm.gov.br` at 1/s
  (large files); model 0.
- **Goal in one sentence:** the real half of TASK-27 N7 — BR stops being
  a market where an issuer can be added and nothing can be collected.

**Scope is the BR half of TASK-27 N7 as written.** The standing H2 rule
governs the mapping: a tag enters `concepts.py` **only** with the
payload that proves it; an unprovable column stays unmapped and is named
in the report.

## Items

### J1. Канал сбора

**Done when:** `ingest --source cvm` collects a DFP slice for one issuer
through the landed provider; the trimmed payload is committed under
`tests/data/cvm/`; an offline test replays it.

### J2. Колонки, доказанные payload'ом

`CD_CONTA`, `DS_CONTA`, `VL_CONTA`, `ESCALA_MOEDA` are the named gap.

**Done when:** each mapped column is asserted against the payload row
that proves it; `ESCALA_MOEDA` is applied as a **scale** (`MIL` =
thousands), not as a currency; `fact.currency` is `BRL`; every unmapped
column is listed by name in the report.

### J3. Меры сдвигаются с нуля честно

**Done when:** the measure count for the BR issuer moves off `0/10` and
the report states the new number — `2/10` honestly mapped beats `10/10`
guessed.

### J4. Реестр перестаёт называть канал существующим авансом

**Done when:** `rusterm markets` distinguishes a provider module that
exists from a channel the user can actually run, and the output is
pasted before and after.
