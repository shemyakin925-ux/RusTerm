# TASK-31 — K4: вендорская сверка и шесть оценочных мер со значениями

- **Status: READY**
- **Report:** `agent/REPORT-31.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **40 requests** (Twelve Data only); model 0.
- **Depends on TASK-30** — without real price rows this task has no
  input and is **skipped, not faked**.
- **Goal in one sentence:** the vendor half of TASK-23 K3/K4 — our
  `price_adj` is compared with the vendor's `adjusted` on a real series,
  and the six valuation measures stop reading `missing_data`.

## Items

### C1. Наша корректировка против вендорской, числом

**Done when:** for one issuer with at least one split or dividend in the
window, the report prints a table: date, our `price_adj`, vendor
`adjusted`, difference, and the count of days where they agree exactly.
A disagreement is reported with both numbers — never resolved silently
in favour of the vendor. Our function is not rewritten (ADR-0014 §4).

### C2. Шесть мер получают входы

`market_cap`, `enterprise_value`, `ev_ebitda`, `price_to_book`,
`dividend_yield`, `roic` on US-AAPL.

**Done when:** `rusterm snapshot --instrument US-AAPL` shows all six
with values; the report pastes them with their `as_of` and currency; a
golden test on the recorded payload pins the six numbers so the next
night cannot move them silently.

### C3. Корпоративные действия из реального источника

**Done when:** at least one split and one dividend land in
`corporate_action` from the vendor payload, with lineage; a test asserts
`price_adj` is independent of the order in which they are applied (the
existing B5 property holds on real rows).

### C4. Валюта цены не теряется

**Done when:** a price row of a non-USD market keeps its own currency
and the currency firewall (ТЗ-21 H3) refuses to mix it into an absolute
peer aggregate — asserted by a test, with the refusal reason quoted.
