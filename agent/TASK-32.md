# TASK-32 — P3 и P4: канал владения (Forms 3/4/5)

- **Status: ACCEPTED** — acceptance 13/13, exit 0; ruling and the TASK.md regression in `agent/TASK-33.md`
- **Report:** `agent/REPORT-32.md`
- **Protocol:** `agent/PROTOCOL.md` (§12 — the relay). State: `agent/CONTEXT.md`.
- **Relay:** hand back with `python3 agent/relay.py hand --to coordinator --report agent/REPORT-32.md --note "<one line>"`, then `python3 agent/relay.py wait --for executor --timeout 3600`.
- **Budgets:** network **50 requests** to `data.sec.gov` at 5/s; model 0.
- **Goal in one sentence:** TASK-25 P3 and P4 were blocked on
  `RUSTERM_SEC_UA`; the contact exists now, so the ownership channel
  stops being a plan.

**Scope is the text of TASK-25 P3 and P4 as written.** Read them there.

## Rulings on TASK-31 Disputed (coordinator, 15.09.2026)

TASK-31 is **accepted**. Read these before D1; none of them requires
rework of work already done.

1. **Split ex-date — you are right, the task was wrong.** The AAPL 4:1
   ex-date is **2020-08-31**; 28.08.2020 is the last pre-split close.
   Your own numbers say so (124.80750 = 499.23 / 4 on 28.08, raw
   129.039993 on 31.08). TASK-31 C1's wording is corrected here and the
   proof stands as written.
2. **ADR-0020 — confirmed.** Three independent anchors (4:1, 7:1, and
   the 2006 row) agree, and the dividend/close ratio argument holds.
   Keep the anchors pinned by the golden test. **Do not edit ADR-0019**:
   `docs/` is frozen and ADR-0020's "уточняет ADR-0019" header is the
   whole cross-reference.
3. **Replaced pins — accepted, both the TASK-31 C2 set and the carried
   TASK-28 R3 one.** Checked against the diff, not the report: all 14
   removed `assert` lines are schema-version literals with a 41 -> 42
   counterpart, the migration lists gained 42 rather than losing 41, and
   the four unholdable pins are `xfail(strict=True)` with named
   successors. No rework. The tooling gap you named is real: D5.
4. **ev_ebitda / roic denominators — approved as annual, not TTM**, on
   your evidence that the Q4 3-month fact is never filed. The
   approximation must stop being invisible: D6.
5. **minority_interest — absence is not zero.** Zero needs positive
   evidence: D7.

**Order of work.** D1–D4 first. If the SEC channel refuses (403/429),
do not idle: switch to D5–D7 and record the refusal. D5–D7 may run past
the night into the next task.


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

### D5. P1 перестаёт мешать законной замене булавки

`agent/selfcheck.sh` greps any removed `assert`, so every migration
trips it and the sanctioned "replace by a stronger pin" route cannot
pass the gate. **This item authorises editing `agent/selfcheck.sh`.**
`agent/acceptance.sh` stays untouched — acceptance check 12 guards it.

Rule to implement: a removed `assert` line passes only when the commit
message carries, for that file, the block

    ЗАМЕНА-БУЛАВКИ: <file>::<test> -> <successor file>::<test>
    ПОЧЕМУ СИЛЬНЕЕ: <one line>

**and** the same file gains at least as many `assert` lines as it lost.
Everything else stays red.

**Done when:** a test of the guard itself (temp repo or staged-diff
fixture) shows three cases — removal without the block: red; removal
with the block but fewer asserts added: red; declared replacement with
equal or more asserts: green — and `bash agent/selfcheck.sh` is green
on your own commit for this item.

### D6. Приближение по годовому периоду перестаёт быть невидимым

**Done when:** every measure carries `period_basis` (`ttm` | `annual`)
in its lineage; `ev_ebitda` and `roic` for AAPL report `annual` with the
period named (FY2025), asserted by a test; a new ADR records why TTM is
not buildable from XBRL for an issuer that files no Q4 3-month fact.
`docs/` is otherwise untouched.

### D7. Отсутствие NCI — не ноль

**Done when:** `minority_interest` is `0.0` only where the fact set
contains the equity block and no NCI concept, with reason
`nci_absent_in_equity_block` visible in lineage; with no equity block it
is `missing_data` with the existing named reason. Both branches asserted
by a test on real facts.
