# TASK-24 — M10: Industry View получает входы. Физические метрики, HHI, второй сектор

- **Status: READY** — take it when `agent/TASK-23.md` is finished and
  handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-6` (branch it from the head of `agent/night-5`)
- **Report:** `agent/REPORT-24.md`
- **Sequential, one process** — but the night is large. Items are sized
  for an executor that is faster than the previous tasks assumed; if you
  finish early, the queue continues below, not in idling.
- **Depends on TASK-20 L5/L6 (manual import) for N3–N6.** Everything
  else runs without them.
- **Goal of the night, in one sentence:** twenty industry functions that
  have been written and tested since M1 stop being unreachable code —
  the `physical` category of manual import becomes their input, `hhi`
  stops being a registered name with no implementation, and a second
  sector proves the catalogue procedure works twice.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-5 && git pull
git checkout -b agent/night-6
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
python3 -c "import rusterm.core.industry.maritime_tanker as m; print(len([f for f in dir(m) if not f.startswith('_')]))"
```

`STATUS=0` required. Read `_SCHEMA_VERSION` from the file.

**First commit:** create `agent/REPORT-24.md` with its five section
headers and repoint `agent/STATE.json` at it in the same commit —
`tests/test_report_sections.py` reads the report `STATE.json` names.

Read, in full: `rusterm/core/industry/maritime_tanker.py` (**all of it**),
`rusterm/core/industry/aggregate.py`, `docs/industry-metrics/README.md`,
`docs/industry-metrics/maritime-tanker.md`, `rusterm/formulas.py`,
`rusterm/core/snapshot.py`, `rusterm/tui/model.py`,
`docs/adr/0011-ruchnoy-import-dokumentov.md` (the `physical` category is
the point of this night), `agent/TASK.md`.

## 0.1. What was measured before this task was written

Checked by the coordinator on 10.09.2026:

| Command | Result |
|---|---|
| `grep "^def " rusterm/core/industry/maritime_tanker.py` | **~20 functions**: `spot_TCE_per_day_by_class`, `fleet_utilization_pct`, `vessel_OPEX_per_day_by_class_and_age`, `vessel_breakeven_TCE`, `fleet_age_histogram`, `daily_vessel_margin` and the rest — all written, all tested |
| `grep -rn "maritime" rusterm/ --include="*.py"` | imported in `industry/__init__.py` and **nowhere else** — nothing calls it |
| `grep -n "def hhi\|hhi(" rusterm/formulas.py` | **no implementation** — `hhi` is a registered name in the units table and in the snapshot's allowed concepts, and it resolves to nothing |
| `ls docs/industry-metrics/` | `README.md` and `maritime-tanker.md` — one sector |
| `rusterm/tui/model.py:47` | coverage blocks already include `industry_metrics` — the display is built and always empty |

The pattern is the same one TASK-23 found for prices: **the hard half is
done and starved.** Maritime metrics need vessel days, ship counts and
off-hire days — numbers XBRL does not carry and a regulator never files
in a tagged form. They live in the operational tables of annual reports,
which is precisely what ADR-0011's `physical` category exists to capture.

Manual import is not a side entrance for awkward companies. **It is the
only possible source for half the Industry View.** That is what this
night is about.

## 0.2. Decisions already taken. Not open for re-litigation

1. `maritime_tanker.py` is **not rewritten.** Its function names come
   verbatim from `docs/industry-metrics/maritime-tanker.md` (TASK-8
   U12.1) and that binding stands.
2. A metric without an input is **grey with `no_data`**, never zero,
   never omitted, never guessed. The module already does this — keep it.
3. `docs/` is frozen. The new sector's catalogue page is the one
   exception this night needs, and it is handled by N11 as a **new ADR
   plus a new file under `docs/industry-metrics/`** — check 10 forbids
   editing `docs/`, so N11 states exactly what it may add and you must
   confirm the acceptance stays green after it.

---

## 1. Working protocol. This outranks the task list

Identical to `agent/TASK-19.md` §1 — the cycle, the five prohibitions,
selfcheck, the stuck rule, the stop rule, commit format, R1–R4
bookkeeping, push, the 09:30 line, network rules N2–N7, money and quota.
**Read it there.** Tonight's specifics:

- **P1 applies to `golden_m2.json` and `golden_m6_ca.json`.** Nothing in
  this night may move a fundamental number. A changed golden value is a
  stop under §1.5.
- **This task's network budget is 0 requests.** Nothing here needs a
  source; manual import reads files from disk. If you think you need the
  network, you have misread an item.
- **Model calls: 80 maximum, free models only** — only N4 uses them.
- `docs/` is frozen except as N11 states.

---

## 2. The work, in priority order

### N1. `hhi` перестаёт быть именем без реализации

`rusterm/formulas.py`, `tests/test_formulas.py`.

`hhi` is registered in the units table as `"index"` and listed among the
snapshot's allowed concepts, and **no function computes it.** A concept
name that resolves to nothing is worse than an absent one: it looks
supported.

- Herfindahl–Hirschman index over shares of a whole: sum of squared
  shares. State in the docstring **which convention** you use — fractions
  (0…1) or percent (0…10 000) — and make the unit string agree with it.
- Inputs that do not sum to the whole within a tolerance are a
  **reason**, not a silent renormalisation.
- An empty or single-member set: define both, test both.

**Done when:** `python3 -m pytest tests/test_formulas.py -k hhi -q`
green; a test asserts a known set gives the hand-computed value; a test
asserts shares summing to 0.8 yield a reason rather than a number.

### N2. Модуль отрасли соединён со снапшотом

`rusterm/core/snapshot.py`, `rusterm/core/industry/__init__.py`.

Twenty functions are imported and never called.

- The snapshot's `industry_metrics` block is produced by the sector
  module registered for the instrument's sector.
- An instrument in a sector with no module gets an honest empty block
  with a reason — not a missing block.
- `method_version` (`maritime.v1`) is recorded with every produced
  metric, so a recomputation years later is attributable.

**Done when:** a test builds a snapshot for a tanker instrument and
asserts the block is present and populated; a test asserts an instrument
in a sector without a module gets the reason; `golden_m2.json` unchanged.

### N3. Физические метрики становятся входами, а не записями в стороне

**Needs:** TASK-20 L6 (manual import). `rusterm/core/industry/`,
`rusterm/store/repos.py`.

Manual import already produces `physical` records with a unit, a period,
a verbatim quote and a page. They currently land as records and stop.

- A mapping from `physical` record metrics to the module's named inputs
  (`voyage_days`, `ships_in_class`, `off_hire_days`, `vessel_days`, …).
  The mapping is **explicit and per sector**, in one file, the way
  `concepts.py` maps XBRL tags — not inferred from strings at runtime.
- A record that maps to nothing is kept and reported, never dropped
  silently. The count of unmapped metrics is a report line.
- **`verified=no` records do not feed a metric** — same rule as
  ADR-0011 ③ for financial facts. A vessel count a model misread out of
  a wide table must not silently become a fleet utilisation figure.

**Done when:** a test drives a synthetic annual-report page through
import and asserts `fleet_utilization_pct` computes from it; a test
asserts a `verified=no` physical record yields grey with
`manual_unverified`, not a number; the report gives mapped/unmapped
counts.

### N4. Извлечение физических метрик проверено на настоящей форме таблицы

**Needs:** N3. **Model calls: 80 maximum, free models only.**

The prototype's hard-won lesson (ADR-0011 context): a model reading a
wide operational table can name the metric from the header and take the
number from the wrong column. Fleet tables are exactly that shape.

- Build synthetic operational tables of increasing nastiness: a clean
  two-column table, a ten-column fleet table by vessel class, one with a
  total row, one with a footnote marker inside a number.
- Run the real extraction path over them and record, per table:
  records produced, verified, and **how many were verified-but-wrong**
  (the quote is genuinely on the page, the number is genuinely in the
  quote, and it is still the wrong column).
- That last number is the honest measure of this feature and it belongs
  in the report. **Do not tune the prompt until the number looks good** —
  record what it is.

**Done when:** the four tables exist as generated fixtures; the table of
results is in the report with the verified-but-wrong count stated
plainly; no fixture is a real company's report.

### N5. Единицы физических метрик не смешиваются

`rusterm/core/industry/`, `rusterm/formulas.py`.

Tons, days, ships and dollars per day are not interchangeable, and a
model that read "million tons" as "tons" is off by a million.

- A physical input carries its unit **with scale** (`million tons`,
  `USD/day`), and a metric refuses inputs whose units it does not expect
  — a reason, not a conversion guess.
- Scale words (`thousand`, `million`, `billion`, and their non-English
  equivalents where the document is not in English) normalise into an
  explicit multiplier, and the multiplier is recorded.

**Done when:** a test asserts `USD` fed where `USD/day` is expected
yields a reason; a test asserts `million tons` and `tons` produce values
differing by exactly 1e6; a test asserts an unrecognised scale word is a
reason rather than a silent 1.

### N6. Покрытие отрасли говорит, чего не хватает

`rusterm/core/snapshot.py`, `rusterm/cli/__init__.py`.

The `industry_metrics` coverage block exists and is always empty.

- Per metric: computed, or grey with the **named missing input**
  ("no `voyage_days` for 2024").
- A user must be able to read the block and know **which page of which
  report they should import next** to fill the gap.

**Done when:** `rusterm coverage` on a tanker instrument names the
missing inputs per metric; a test asserts the named input matches the
module's actual parameter name.

### N7. Концентрация отрасли, теперь что `hhi` существует

**Needs:** N1, M7's aggregate. `rusterm/core/industry/aggregate.py`.

M7 promised "цикл индустрии, концентрация" and delivered the aggregate
half.

- Sector concentration by revenue: `hhi` over member shares, with `n`
  and the members that contributed.
- The measure states the **currency** it was computed in, and a
  mixed-currency sector refuses (the rule from TASK-21 H3): shares of a
  sum that mixes won and dollars are meaningless.
- Reproducible as of a date, the same way M7's aggregate is: it reads
  the peer set version and snapshot versions in force then.

**Done when:** a test asserts concentration for a known sector matches a
hand-computed value; a test asserts a mixed-currency sector returns
`currency_mismatch`; a test asserts recomputation as of a past date
returns the same number after new data lands.

### N8. Экран отрасли показывает физику, а не только финансы

**Needs:** TASK-22 J7 (the industry screen). `rusterm/tui/model.py`.

- The sector screen gains the industry-metric rows beside the financial
  aggregate, each with its `method_version`.
- Grey metrics show their missing input, not a blank.
- A metric sourced from manual import is **visibly distinguished** from
  one sourced from a filing — the same rule as TASK-20 L8 for facts.
- Pure functions in `model.py`, tested headless; `curses` only paints.

**Done when:** `python3 -m pytest tests/test_tui_model.py -q` green; a
test builds the rows without importing `curses`; a test asserts a
manual-sourced metric differs in a field a renderer can key on.

### N9. Инструмент отрасли для модели отдаёт метрики

**Needs:** TASK-22 J6. `rusterm/core/tools.py`.

`list_industry_instruments` was wired in TASK-22. The model still cannot
see the sector's operating metrics.

- A read-only tool returning the industry metrics for an instrument or a
  sector, with `method_version`, units and reasons.
- **Read-only stays read-only**: the test asserting the database hash is
  unchanged after calling every tool keeps passing.

**Done when:** the tool returns real metrics with units and reasons; the
read-only hash test still passes.

### N10. Порядок добавления сектора, выведенный из практики

`docs/adr/0015-poryadok-dobavleniya-sektora.md` (**a new ADR — the one
permitted change to `docs/`**).

Write down what adding a sector actually costs, measured from N11 rather
than imagined: catalogue page, module, input mapping, fixtures, wiring.
Name what is mechanical and what needs judgement.

**Done when:** the ADR exists and `bash agent/selfcheck.sh` exits 0.

### N11. Второй сектор — доказательство, что процедура работает дважды

**Needs:** N2, N3, N10.

One sector proves nothing about a procedure. Add a second, and pick one
whose operating metrics are genuinely different in shape from shipping —
**mining or upstream energy** (production volumes, grades, reserves,
cost per unit) rather than another asset-day business.

- `docs/industry-metrics/<sector>.md` — the catalogue page, in the style
  of `maritime-tanker.md`. **Check 10 permits only new ADRs inside
  `docs/`; a new file under `docs/industry-metrics/` is not an ADR.**
  Therefore: **add the file, run `bash agent/selfcheck.sh`, and if
  check 10 fails, put the catalogue page beside the module in
  `rusterm/core/industry/` as a docstring instead and record the whole
  thing in `Disputed`** with the check's output quoted. Do not edit
  `agent/acceptance.sh` — that is a blocking violation.
- `rusterm/core/industry/<sector>.py` with its own `METHOD_VERSION`.
- Its physical-input mapping (N3), its units (N5), its coverage (N6).
- Function names come **verbatim from the catalogue page**, as U12.1
  binds for maritime.

**Done when:** a test computes at least six metrics of the new sector
from a synthetic import; the acceptance is green **or** the Disputed
entry exists with the check output; the report states which path was
taken and why.

### N12. Веха M10, со своими доказательствами

Append to the report, each claim beside the command that proves it:
metrics computed per sector, mapped/unmapped physical records, the
verified-but-wrong count from N4, concentration per sector with its
currency, and what M10 does not cover.

**Done when:** `bash agent/selfcheck.sh` exits 0; `agent/STATE.json` is
`"status": "awaiting_review"`.

### N13. Backlog

`agent/BACKLOG.md`, top-down, only if N1–N12 are done before 09:30.

---

## 3. Closing the shift

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      N1, N2, …
Items not done:  … and why
Acceptance:      the "Итог" line and the captured exit status
Tests:           N passed, N skipped, N xfailed
Golden:          golden_m2.json, golden_m6_ca.json — unchanged? assert output
hhi:             convention chosen, unit string, hand-computed check
Sectors:         which, how many metrics each, method_version
Physical inputs: mapped / unmapped counts, per sector
Extraction:      per table — produced / verified / verified-but-wrong
Concentration:   per sector, with currency
docs/ path:      catalogue page added, or Disputed with check 10 output
Network:         0 expected — state actual
Model:           app llm_calls N of 80; your own model id
Pushed:          yes/no
Questions for the coordinator:
1. …
```
