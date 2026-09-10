# TASK-25 — M11: governance-светофор загорается. Пять индикаторов получают источник

- **Status: READY** — take it when `agent/TASK-24.md` is finished and
  handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-7` (branch it from the head of `agent/night-6`)
- **Report:** `agent/REPORT-25.md`
- **Sequential, one process.** Large night; items continue past the
  point where earlier tasks would have stopped.
- **Depends on nothing in TASK-24.** Needs the EDGAR path (M2) and,
  for P7–P8, manual import (TASK-20 L6).
- **Goal of the night, in one sentence:** milestone M11 — five
  governance indicators that have been written, tested and displayed
  since M1 stop returning grey for every issuer, because Forms 3/4/5 and
  the proxy statement finally reach them.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-6 && git pull
git checkout -b agent/night-7
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
printenv RUSTERM_SEC_UA | cut -c1-12
```

`STATUS=0` required. Read `_SCHEMA_VERSION` from the file.

**This night needs the network.** Without `RUSTERM_SEC_UA`: do P1, P2,
P7, P9, P10, P11 (all offline), write `SEC_UA UNSET — payloads not
recorded` in `## Blocked`, and skip the items that record payloads. **Do
not simulate a filing and do not hand-write one.**

**First commit:** create `agent/REPORT-25.md` with its five section
headers and repoint `agent/STATE.json` at it in the same commit.

Read, in full: `rusterm/core/governance.py` (**all of it**),
`docs/governance-thresholds.md`, `rusterm/tui/model.py` (lines 85–102 —
the display path already exists), `rusterm/pipeline.py` (the `INSIDER →
ownership` mapping), `rusterm/providers/edgar.py`,
`rusterm/providers/disclosures.py`, `rusterm/store/repos.py`
(`GovernanceRepo`), `agent/TASK.md`.

## 0.1. What was measured before this task was written

Checked by the coordinator on 10.09.2026:

| Command | Result |
|---|---|
| `grep "^def " rusterm/core/governance.py` | five indicators written and tested: `independent_directors`, `ceo_chair`, `related_party`, `insider_net`, `auditor`, each with a grey/`no_data` path |
| `grep -rn "governance\." rusterm/core/snapshot.py rusterm/cli rusterm/pipeline.py` | **nothing calls them** |
| `rusterm/tui/model.py:85–102` | the card **already** reads `repos.governance.latest(...)` and falls back to grey when absent |
| `grep -rn "insider\|ownership" rusterm/providers rusterm/pipeline.py` | a `synthetic://insider-form4` fixture and an `INSIDER → ownership` block mapping — the seat exists, nothing sits in it |

So: the formulas exist, the storage exists, the display exists, and the
producer between them was never written. Every issuer's traffic light is
grey, and it is grey for a reason nobody can see.

## 0.2. Where the inputs actually live. Measured, not assumed

Governance inputs are **not in XBRL company facts.** They are:

| Indicator | Source |
|---|---|
| `insider_net` | **Forms 3/4/5** — free on EDGAR, machine-readable XML, one filing per transaction |
| `independent_directors`, `ceo_chair`, `related_party`, `auditor` | **DEF 14A proxy statement** — free on EDGAR, but **prose and HTML tables, not tagged data** |

That split decides the night. The insider half is a normal provider
path. The proxy half is **narrative** — which is exactly the case
ADR-0011 built manual import for, and P7 routes it there rather than
pretending a regex can read a board table reliably.

**Before writing the insider provider, probe the live feed and record
what you got** — request, status, bytes — the way
`agent/REPORT-MARKETS.md` does. A source you have not probed is not a
source (`agent/TASK.md` §1).

## 0.3. Decisions taken. Not open for re-litigation

1. `governance.py` is **not rewritten.** Its thresholds come from
   `docs/governance-thresholds.md` and that binding stands.
2. **Grey is a legitimate, permanent outcome.** An indicator with no
   input stays grey with a named reason. Never green by default, never a
   guess, never "probably independent".
3. Source stays **SEC EDGAR** for the insider half. This night does not
   authorise a governance data vendor.
4. A governance assessment is **dated and versioned**: it states the
   filing it came from and the date it was true.

---

## 1. Working protocol. This outranks the task list

Identical to `agent/TASK-19.md` §1. Tonight's specifics:

- **Network budget: 60 requests.** Count every one in `STATE.json`.
- **N4 applies hard**: 403/429 is a stop. EDGAR's rate is 5/s and the
  gate holds it — never raise it, never change the User-Agent.
- **P1 applies to `golden_m2.json` and `golden_m6_ca.json`** — nothing
  here may move a fundamental number.
- **Model calls: 60 maximum, free models only** — only P7 uses them.
- `docs/` is frozen; a new ADR is the one permitted change.

---

## 2. The work, in priority order

### P1. Производитель оценок: пустое место между формулой и экраном

`rusterm/core/governance.py` (wiring only), `rusterm/core/snapshot.py`.

- A producer that calls the five indicators with whatever inputs exist
  and writes `governance_assessment` rows through `GovernanceRepo`.
- Every row carries: indicator, colour, `as_of`, the lineage reference
  to the filing it came from, and the reason when grey.
- Called during snapshot assembly, so the card stops being grey by
  accident and becomes grey **on the record**.

**Done when:** a test drives the producer with synthetic inputs and
asserts five rows written with five colours; a test asserts an issuer
with no inputs gets five grey rows **with named reasons**, not zero
rows; `rusterm/tui/model.py` is unchanged (it already reads them).

### P2. Серый перестаёт быть одним цветом на все причины

`rusterm/core/governance.py`, `rusterm/reasons.py`.

Today grey means "no data" and nothing else. A user cannot tell "this
company files no proxy" from "we have not collected it yet".

- Distinct reasons: not collected, source has no such disclosure,
  collected but unparsed, stale beyond the threshold.
- Each reason names what a user could do about it, if anything.

**Done when:** a test drives all four and asserts distinct reasons; the
card shows the reason text, asserted through `tui/model.py`'s pure
functions.

### P3. Живая проверка канала Forms 3/4/5

**Needs the network.** Budget: 10 of the 60.

Before any provider code: probe EDGAR's submissions and ownership
endpoints for two known issuers. Record request, status, bytes, and the
shape of what came back. A changed answer is a finding, not a reason to
improvise.

**Done when:** the probe table is in the report with real numbers; no
provider code was written before it.

### P4. Провайдер владения: Forms 3/4/5

**Needs:** P3. `rusterm/providers/edgar.py` or a sibling module,
`tests/data/edgar/ownership/`.

- Fetch and parse ownership filings into transactions: person, role
  (officer, director, ten-percent owner), date, acquired/disposed,
  shares, price where present.
- Goes through `RequestGate` at EDGAR's declared rate. **No new host.**
- A **trimmed recorded payload**, 256 KB ceiling, and a golden test
  resolving each asserted transaction back into it by pointer.
- The `INSIDER → ownership` block mapping in `pipeline.py` already
  exists — use it rather than inventing a parallel path.

**Done when:** `python3 -m pytest tests/test_ownership.py -q` green with
`RUSTERM_SEC_UA` unset (network tests skip, N7) and with it set; the
golden test resolves every asserted value; the report gives requests
used against the 60 budget.

### P5. `insider_net` загорается

**Needs:** P4. `rusterm/core/governance.py` (inputs only).

- Net insider ratio over the window `docs/governance-thresholds.md`
  defines — **read the threshold from the document, do not invent one.**
- Routine transactions that are not signals (tax withholding, scheduled
  10b5-1 sales where the filing marks them) are classified, and the
  classification is **visible**, not silently netted away.
- Thin data is grey, not green: below a minimum transaction count, the
  indicator refuses to have an opinion.

**Done when:** a test with recorded filings asserts the colour matches a
hand-computed ratio; a test asserts an issuer with two transactions is
grey with the thin-data reason.

### P6. Живая проверка канала DEF 14A

**Needs the network.** Budget: 10 of the 60.

Probe the proxy-statement route for two issuers. Record status, bytes,
and **what form the content is in** — tagged, HTML tables, or prose.
That measurement decides P7's shape; do not assume it.

**Done when:** the probe table is in the report, including a plain
statement of whether any part of the proxy is machine-tagged.

### P7. Прокси идёт через ручной импорт, а не через регулярное выражение

**Needs:** P6, TASK-20 L6. **Model calls: 60 maximum, free models only.**

Board independence, CEO/chair separation, related-party ratios and
auditor history live in prose and HTML tables. A regex over a proxy
statement is a defect generator, and this project already owns the right
tool for narrative documents.

- The proxy is fetched (or supplied by the user) and goes through the
  manual-import pipeline as an `other`-category document.
- Extracted governance facts carry the **verbatim quote and page**, and
  `verify` decides `verified`.
- **`verified=no` never sets a colour.** It stays grey with
  `manual_unverified`. A model that misread a board table must not turn
  a light green.
- Every non-grey colour is traceable to a quote a user can read.

**Done when:** a test drives a synthetic proxy page and asserts
`independent_directors` gets a colour with a quote attached; a test
asserts a `verified=no` extraction leaves the indicator grey; the report
states, out of the indicators attempted, how many earned a colour.

### P8. Цвет всегда доказуем

`rusterm/core/governance.py`, `rusterm/cli/__init__.py`.

- Every non-grey assessment resolves to its source: filing, page or
  section, and quote where it came from a document.
- `rusterm verify` (the existing manual-correction path) can override an
  assessment, and the override is recorded as an override — never
  indistinguishable from a collected one.

**Done when:** a test asserts every produced colour resolves to a source
reference; a test asserts an override is stored with its own provenance
and survives a recomputation.

### P9. Устаревание: прошлогодний прокси не описывает сегодняшний совет

`rusterm/core/governance.py`.

- An assessment older than the threshold in
  `docs/governance-thresholds.md` goes grey with a staleness reason —
  it does not quietly keep its colour.
- `doctor` reports the age of the newest governance assessment per
  instrument.

**Done when:** a test with a fake clock asserts a colour goes grey at
the threshold; `doctor` shows the ages.

### P10. Светофор на экране и в экспорте

`rusterm/tui/model.py`, `rusterm/core/export.py`.

- The card shows five indicators in five colours **without collapsing**
  them (`tui/model.py` already promises "пять отдельных цветов без
  свёртки" — make it true with real data).
- The list screen shows an issuer-level governance cell.
- The export carries each indicator, its colour, its reason and its
  source reference. Existing export fields keep their names and order.

**Done when:** `python3 -m pytest tests/test_tui_model.py
tests/test_snapshot_export.py -q` green; a test asserts pre-existing
export fields are unmoved.

### P11. Веха M11, со своими доказательствами

Per indicator across the collected issuers: how many green, yellow, red,
grey, and the reason distribution for grey. Plus what M11 does not
cover — named honestly.

**Done when:** `bash agent/selfcheck.sh` exits 0; `agent/STATE.json` is
`"status": "awaiting_review"`.

### P12. Backlog

`agent/BACKLOG.md`, top-down, only if P1–P11 are done before 09:30.

---

## 3. Closing the shift

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      P1, P2, …
Items not done:  … and why
Acceptance:      the "Итог" line and the captured exit status
Tests:           N passed, N skipped, N xfailed
Golden:          golden_m2.json, golden_m6_ca.json — unchanged? assert output
Probes:          Forms 3/4/5 and DEF 14A — status, bytes, tagged or prose
Indicators:      per indicator — green/yellow/red/grey counts
Grey reasons:    the distribution across the four reasons
Proxy path:      indicators attempted / coloured / left grey by verify
Payload:         du -sk tests/data/edgar/ownership/ — under 256 KB
Network:         requests used of the 60 budget
Model:           app llm_calls N of 60; your own model id
Pushed:          yes/no
Questions for the coordinator:
1. …
```
