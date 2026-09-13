# TASK-30 — K2 и K7: котировки перестают быть фикстурами

- **Status: READY**
- **Report:** `agent/REPORT-30.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **60 requests**, of which Twelve Data no more
  than 8 per minute and 40 in total; model 0.
- **Depends on TASK-29** (a green suite with keys). If TASK-29 was not
  taken, take it first — do not work on a red tree.
- **Goal in one sentence:** the items TASK-23 K2 and K7 were blocked on
  `RUSTERM_TWELVEDATA_KEY`; the key exists now, so the price path stops
  being a schema with fixtures in it.

**Scope is the text of TASK-23 K2 and K7 as written** — read those two
items there, they are the specification. What changed: the key is
present, and ADR-0018 now forbids any fallback to a paid tariff.

## Items

### B1. Провайдер в реестре, с потолками бесплатного тарифа

`rusterm/providers/twelvedata.py` with `build(gate)`, registered under
the name the registry already expects. `HostLimit`: **8 requests per
minute, 800 per day** (ADR-0014 §1) — not the 5000 placeholder.

**Done when:** `python3 -c "import rusterm.providers as p;
print(sorted(p.available()))"` lists it; a test asserts the declared
ceiling is 800/day and the rate no greater than 8/min; a request past
the ceiling returns `budget_exceeded` **by value**, never a wait.

### B2. Живая серия, записанная и воспроизводимая

One instrument (`US-AAPL`), daily closes and `adjusted`, stored through
`PriceRepo`; the trimmed payload lands under `tests/data/twelvedata/`
and a golden test replays it offline.

**Done when:** `rusterm ingest --instrument US-AAPL --source twelvedata`
writes a non-zero number of `price` rows; a second run writes **zero**
new rows (I7); the report states rows, the date range and requests
spent; the offline replay test is green without a key.

### B3. K7: один вендор — известная дыра, доказанная тестом

Vendor failure (403, 429, timeout) stops the price path with a named
reason and leaves the fundamental half working.

**Done when:** a test drives each of the three failures through a fake
transport and asserts: valuation measures read their reason, the
fundamental measures of the same snapshot keep their values, and nothing
stale is presented as fresh.

### B4. Кадентность на живых данных

The completeness rule of ADR-0014 §2 runs against the rows B2 actually
wrote: incomplete instruments take the budget first, complete ones are
polled every 7-14 days.

**Done when:** `rusterm refresh --json` (or the cadence command as it is
named in the code) shows the instrument moving `incomplete → complete`
after the backfill, and the report states requests per day of the
simulated month against the real row set.
