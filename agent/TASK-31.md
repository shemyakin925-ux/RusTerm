# TASK-31 — K4: вендорская сверка и шесть оценочных мер со значениями

- **Status: ACCEPTED** — acceptance 13/13, exit 0; rulings in `agent/TASK-32.md`
- **Report:** `agent/REPORT-31.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **40 requests** (Twelve Data only); model 0.
- **Depends on TASK-30** — without real price rows this task has no
  input and is **skipped, not faked**.
- **Goal in one sentence:** the vendor half of TASK-23 K3/K4 — our
  `price_adj` is compared with the vendor's `adjusted` on a real series,
  and the six valuation measures stop reading `missing_data`.

## Items

### C1. Корректировка доказывается изнутри — вендорского мнения нет

**Rewritten 14.09.2026 after the measurement in TASK-30 B2 and
ADR-0019:** the free tier sends **no `adjusted_close`**, so the
cross-check ADR-0014 §4 promised has no input. It is not faked and not
bought (ADR-0018). Three internal proofs replace it:

- `price_adj` is computed over the **real** corporate actions collected
  in C3, not over synthetic ones;
- order independence is shown on those real events — split before
  dividend and the reverse produce the same series;
- one known event — the AAPL 4:1 split of 28.08.2020, inside the
  recorded range — is recalculated **by hand in the report** and
  compared with the function's number, digit for digit.

**Done when:** the three proofs are in the report with their numbers;
`python3 -m pytest tests/test_k3_adjusted.py -q` is green including the
real-event case; the golden test pins `adjusted IS NULL` on the
recorded payload, so the day the vendor starts sending the field the pin
goes red and the vendor cross-check returns **with** its input.

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

### C5. Кадентность получает поверхность, а не только код

Ruling on question 1 of `agent/REPORT-30.md`: **yes, a command.** A rule
the user cannot see is a rule they cannot trust.

- `rusterm prices --cadence` (or the name already used in the code)
  prints per instrument: state (`incomplete` / `complete`), last stored
  date, number of gaps, when the next poll is due.
- The `--json` form carries the same fields and joins the pinned key
  schema of the `--json` commands (B16) — the pin is extended, never
  loosened.
- `doctor` gains one line: how many instruments are incomplete and how
  many requests the next pass would cost against the 800/day ceiling.

**Done when:** both outputs are pasted in the report; a test asserts the
JSON keys and that an incomplete instrument is listed before a complete
one.
