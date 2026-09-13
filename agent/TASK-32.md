# TASK-32 — P3 и P4: канал владения (Forms 3/4/5)

- **Status: READY**
- **Report:** `agent/REPORT-32.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **50 requests** to `data.sec.gov` at 5/s; model 0.
- **Goal in one sentence:** TASK-25 P3 and P4 were blocked on
  `RUSTERM_SEC_UA`; the contact exists now, so the ownership channel
  stops being a plan.

**Scope is the text of TASK-25 P3 and P4 as written.** Read them there.

## Items

### D1. Живая проверка канала (P3)

**Done when:** the probe is made through `RequestGate` with the real
contact, and the report states per endpoint: status, bytes, format, and
whether the document is machine-readable. A 403/429 is recorded and the
night continues offline on what was already fetched.

### D2. Провайдер владения (P4)

**Done when:** Forms 3/4/5 for one issuer are collected into `document`
with provenance; the trimmed payload lands under
`tests/data/edgar/ownership/`; an offline test replays it and asserts
the parsed transactions (date, insider, direction, volume) against
hand-checked values from the payload itself.

### D3. Отказ остаётся честным

**Done when:** an issuer that files no ownership forms yields the
existing named reason (`no_sec_filings` or `source_has_no_disclosure`),
never an empty success, asserted by a test.

### D4. Бюджет и провенанс

**Done when:** the report states requests per host, the raw store holds
every fetched object by sha256, and `rusterm doctor` cross-checks the
store against the database in both directions with no orphans.
