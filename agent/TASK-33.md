# TASK-33 — P5 и P6: светофор перестаёт быть серым

- **Status: READY**
- **Report:** `agent/REPORT-33.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **40 requests** to `data.sec.gov`; model 0.
- **Depends on TASK-32** for D2's payload. Without it, take P6 only and
  skip the rest — do not fabricate ownership rows.
- **Goal in one sentence:** TASK-25 P5 and P6 — `insider_net` lights up
  from real Forms 4 and the proxy channel (DEF 14A) is probed, so at
  least two of the five indicators stop being grey for every issuer.

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
