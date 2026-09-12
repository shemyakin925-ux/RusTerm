# TASK-27 — M13: долги, у которых появились предпосылки. Связать построенное и перестать врать о состоянии

- **Status: READY** — take it when `agent/TASK-26.md` is finished and
  handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-9` (branch it from the head of `agent/night-8`)
- **Report:** `agent/REPORT-27.md`
- **Sequential, one process.** Medium night — every item here was
  deferred earlier **for a stated reason**, and every one of those
  reasons is gone by the time this task is taken.
- **Depends on** TASK-20 L5/L6 (manual import pipeline) for N2 and N3,
  on TASK-20 L7 (the hardened API client) for N1, and on TASK-20 L2/L3
  plus TASK-22 J1.0 for N7. Nothing here depends on TASK-24, 25 or 26.
- **Goal of the night, in one sentence:** three things the executor
  honestly refused to fake (B22, B27, B29) get built now that their
  prerequisites exist, the LLM client stops being a seat nobody sits in,
  and the repository stops stating numbers about itself that rot within
  one shift.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-8 && git pull
git checkout -b agent/night-9
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
python3 -c "import rusterm.manual.extract as e; print(e.__file__)"
grep -rn "make_intent_client" --include=*.py rusterm/ | grep -v core/llm.py
```

Line 3 must print `STATUS=0`. Line 4 gives the next free migration
number — **read it, never assume it**. Line 5 must not raise: if
`rusterm/manual/extract.py` does not exist, TASK-20 L5 has not landed,
and **N2 and N3 are skipped, not faked** — write `SKIPPED — L5 absent`
against them and go on to N1, N4, N6. Line 6 shows whether N1 is still
open (empty output = still open; that is the expected state).

## 0.1. Where we are. Measured, not assumed

Facts from the coordinator's own run on `agent/night-3` (journal
`agent/ACCEPTANCE-19.txt`), 11.09.2026:

| Thing | State |
|---|---|
| `agent/acceptance.sh` | 13 of 13, exit 0, byte-identical to `origin/main` |
| Full suite | 413 tests, 0 failures, 0 errors, 5 env skips |
| Schema | `_SCHEMA_VERSION` 40 after TASK-19 F4 |
| Markets | `('US','CA','OTC','KR','BR','AU')`, each with `access` |
| Removed assertions in TASK-19 | 17, all checked, all strictly stronger replacements |
| `rusterm/core/llm.make_intent_client` | **defined, tested, called by nothing** |
| `rusterm/cli/__init__.py` `cmd_ops` | still constructs `RuleClient()` directly |
| README §15 | claims "402 пройдено, 2 пропущено"; the same shift ended at 411 |

The last three rows are this task's reason to exist. The first five are
the ground you stand on: do not re-verify them, do not "improve" them.

## 0.2. Decisions taken. Not open for re-litigation

1. **The selector is the only door.** After N1, no module outside
   `rusterm/core/llm.py` names `RuleClient` or the API client class
   directly. Choosing between them is one function's job, decided by the
   presence of a key, and nothing else.
2. **No key means no network and no error.** An absent key is the
   normal case, not a failure: `make_intent_client` returns the rule
   client, the command works, and nothing is logged about it.
3. **`near_miss` gets its own `null_reason`** (`manual_near_miss`). The
   TASK-19 ruling deferred this to exactly this night; the bucket is
   split here, not in a lane.
4. **A number about the repository is generated or absent.** Hand-typed
   counts of tests, ADRs or formats are forbidden in README.md from this
   night on — that is what N6 enforces with a guard.
5. **B29's scale pass is measured, not estimated.** If the six-market
   providers cannot supply 500 instruments, the report states the real
   number reached and the wall-clock seconds per issuer. A projection is
   not a measurement and is not accepted.

---

## 1. Working protocol. This outranks the task list

Identical to `agent/TASK-19.md` §1. Tonight's specifics:

- **Network budget: 40 requests** across all data hosts, through
  `RequestGate` only. **Model calls: 50 maximum, free models only.**
  Count both in `STATE.json`.
- **P1 applies to `tests/test_llm_api.py`, `tests/test_budget.py` and
  `tests/test_invariants.py`.** Not one assertion there is deleted or
  loosened. If one becomes inconvenient, that is a `Disputed` entry and
  you move on.
- `agent/selfcheck.sh` is chained with `&&`, never `;` — the TASK-19
  incident on commit `51795c9` is not repeated.
- `docs/` is frozen; a new ADR is the one permitted change.

---

## 2. The work, in priority order

### N1. Клиент модели перестаёт быть местом, в которое никто не садится

**Zone:** `rusterm/cli/__init__.py`, `rusterm/core/llm.py`,
`tests/test_llm_wiring.py` (new).

TASK-19 F6 built `make_intent_client`; TASK-20 L7 hardened the client
behind it. Neither wired it: `cmd_ops` still constructs `RuleClient()`
at the call site, so a configured key changes nothing the user can see.

- `cmd_ops` obtains its client from `make_intent_client(os.environ)` and
  from nowhere else.
- With no key: the rule client, byte-identical behaviour to today's
  output for the three existing ops fixtures.
- With a key: the API client, exercised through the fake transport of
  `tests/test_llm_api.py` — no live call in the test.
- **The guard already exists** — `tests/test_single_door.py`, written by
  the coordinator 11.09.2026. It holds the debt visible: while
  `make_intent_client` is listed in its `PENDING`, the tests assert the
  bypass is still there. **Wiring the door means deleting that PENDING
  line**, and the rule flips to forbidding any direct construction of
  `RuleClient` / `LlmApiClient` outside `rusterm/core/llm.py`. Do not
  add an exception to the guard: the line comes out, it does not grow.
- The key value never reaches stdout, stderr, a log line or a report.

**Done when:** the `PENDING` line for `make_intent_client` is gone from
`tests/test_single_door.py` and `python3 -m pytest
tests/test_single_door.py tests/test_llm_wiring.py tests/test_llm_api.py
-q` is green; the guard test red when `RuleClient()`
is put back into `cmd_ops` (show that red output in the report, then
revert); `RUSTERM_LLM_API_KEY=dummy rusterm ops "..."` takes the API
path and `grep -c dummy` over every produced artefact is 0.

### N2. Таблица форматов в README пишется кодом (backlog B22, promoted)

**Zone:** `README.md`, `rusterm/manual/extract.py`, `tests/test_docs_formats.py`.

Deferred in TASK-19 with the correct reason — `extract.py` did not
exist and a table of a refusing seat would have been a lie. It exists
after L5.

- The formats table in README is produced from the handler registry in
  `extract.py`, not typed by hand.
- A test asserts every format the module handles appears in the table
  and nothing else does.

**Done when:** `python3 -m pytest tests/test_docs_formats.py -q` green;
adding a fake handler to the registry turns it red (show it, revert).
**Skipped, not faked, if `extract.py` is absent.**

### N3. Ручной и машинный факт сосуществуют (backlog B27, promoted)

**Zone:** `rusterm/store/repos.py`, `rusterm/core/measures.py`,
`tests/test_source_kind_coexistence.py`.

Deferred because the measure-side selection on `source_kind` belonged to
L6. It exists after L6.

- The same concept and period may hold one `provider` fact and one
  `manual` fact; neither overwrites the other.
- The measure prefers the `provider` fact; the manual one stays
  readable and stays attributable.
- A `manual_unverified` fact never enters a measure — the existing
  invariant is not weakened to make this pass.

**Done when:** the new test is green and
`python3 -m pytest tests/test_invariants.py -q` is still green with
every assertion intact. **Skipped, not faked, if L6 is absent.**

### N4. `near_miss` получает свою причину

**Zone:** `rusterm/reasons.py`, `rusterm/manual/`, `tests/`.

Coordinator ruling 3 on TASK-19: one bucket was right *until* the
measure side could tell the two apart. N3 is that moment.

- `manual_near_miss` joins the reason dictionary with its ADR comment.
- A digit-only loose match reports `manual_near_miss`; a failed match
  keeps `manual_unverified`. Both stay out of measures.

**Done when:** `python3 -m pytest tests/test_reasons.py
tests/test_manual_seats.py -q` green and the two outcomes are
distinguishable in `rusterm verify --json` output.

### N5. Масштаб на шести рынках, измеренный (backlog B29, promoted)

**Zone:** report only — no production code changes.

- Run the M4 scale pass with the six markets and prices together.
- Record: instruments reached, wall-clock seconds per issuer, requests
  spent per host, and whether the M4 budget still holds.
- If 500 instruments are not reachable, the real number is reported.
  **A projection is not a measurement.**

**Done when:** the report carries the table, and the requests spent
match `rusterm budget --json` for the night.

### N6. Репозиторий перестаёт врать о себе числами

**Zone:** `agent/selfcheck.sh`, `agent/REPORT-MARKETS.md`.
Closes backlog **B33 and B34**. **B32 is already done** — the
coordinator wrote `tests/test_docs_truth.py` and cleaned §15 on
11.09.2026; do not redo it, and do not weaken that guard.
- `agent/selfcheck.sh` reads the expected number of acceptance checks
  from `acceptance.sh` instead of hard-coding «пройдено 13». Adding a
  fourteenth check to a **scratch copy** must not make selfcheck lie.
  `agent/acceptance.sh` itself is not touched — acceptance check 12
  compares it to `origin/main` byte for byte.
- `agent/REPORT-MARKETS.md` states a tolerance band for the OTC
  universe count and the date of the last live count (the 12,794 vs
  12,867 drift stops being re-reported as a finding every night).

**Done when:** `python3 -m pytest tests/test_docs_truth.py -q` still
green (you did not weaken it); `bash agent/selfcheck.sh` exit 0 on a
clean tree and exit 1 on a deliberately broken test (show both, revert).

### N7. BR и AU перестают быть рынками, куда можно добавить эмитента и нельзя собрать данные

**Added by the coordinator 12.09.2026**, answering question 2 of the
`REPORT-21.md` HANDOFF. The executor asked whether this was TASK-23/24
territory; it was not — neither task carries the item. The hole is
closed here, in the night whose whole subject is debts whose
preconditions have arrived. Preconditions: the `cvm` and `asx`
providers landed and are tested on recorded payloads (TASK-20 L2/L3,
TASK-21 H4).

**Zone:** `rusterm/cli/__init__.py` (the `ingest --source` door only),
`rusterm/normalize/concepts.py`, `tests/test_market_br.py`,
`tests/test_market_au.py`.

Measured state at acceptance of TASK-21: `ingest` speaks `edgar` and
`synthetic` and nothing else. A BR or AU issuer can be added and then
has no channel — `markets` calls the provider `implemented`, which is
true of the module and false of the user's path.

- **BR, the real half.** `ingest --source cvm` collects a DFP slice
  through the landed provider. The native columns are mapped to
  `ifrs-full` **against the recorded payload that proves each one** —
  `CD_CONTA` / `DS_CONTA` / `VL_CONTA` / `ESCALA_MOEDA` are named in
  the L10 gap list, and `tests/data/cvm/dfp_2024_dre_slice.csv` is the
  payload. The standing H2 rule holds: a tag enters `concepts.py` only
  with the payload that proves it, never because a mapping table
  elsewhere suggests it. A column you cannot prove stays unmapped and
  is **named in the report**.
- **`ESCALA_MOEDA` is a scale, not a currency** (`MIL` means the value
  is in thousands). Applying it is part of the mapping; leaving it
  unapplied silently is the defect this bullet exists to prevent.
  Currency goes to `fact.currency` per TASK-22 J1.0 — `BRL` here.
- **AU, the honest half.** ADR-0010 §5 records that ASX has no
  fundamentals contract. `ingest --source asx` therefore collects
  **announcements and header metadata only** and says so: the issuer
  gets documents, not facts, and the refusal for facts is the existing
  named one, not an empty success. Do **not** invent a fundamentals
  channel, and do **not** scrape a PDF here — that path is manual
  import, which already exists.
- `markets` stops calling a market `implemented` on the strength of the
  module alone: the column distinguishes a provider that exists from a
  channel the user can actually run.

**Done when:** `ingest --source cvm` on the recorded BR payload produces
a non-zero number of `ifrs-full` facts for the AMBEV slice and the
measure count in the report moves off `0/10` (say the new number,
whatever it is — 2/10 honestly mapped beats 10/10 guessed);
`ingest --source asx` produces documents and a named refusal for facts,
asserted by a test; `python3 -m rusterm.cli markets` output is pasted
before and after; every unmapped BR column is listed by name in the
report.

### N8. Backlog

Take items from `agent/BACKLOG.md` top-down until 10:00. Each pulled
item gets its verify line in the report.

---

## 3. Closing the shift

Stop at **10:00 Danang (UTC+7)** whatever the state, push, and fill this
in at the end of `agent/REPORT-27.md`:

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      N1, N2, …
Items not done:  … and why (SKIPPED — L5/L6 absent is a valid reason)
Acceptance:      the "Итог" line and the exit status captured before any pipe
Tests:           N passed, N skipped, N xfailed
Guards:          test_llm_api / test_budget / test_invariants — all assertions intact?
Wiring:          grep -rn "RuleClient(" rusterm/ — output verbatim
Scale (N5):      instruments, seconds per issuer, requests per host
Truth (N6):      counts removed from README? selfcheck reads the number?
Schema:          _SCHEMA_VERSION <old> -> <new>, or "unchanged"
Network:         requests used of the 40 budget, per host
Model:           app llm_calls N of 50; your own model id
Secrets:         artefacts grepped for the key — hits (must be 0)
Pushed:          yes/no
Questions for the coordinator:
1. …
```
