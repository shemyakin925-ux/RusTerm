# TASK-28 — Бесплатность становится правилом, которое проверяет машина

- **Status: ACCEPTED** 14.09.2026 — journal `agent/ACCEPTANCE-30.txt`; acceptance 13/13 on `agent/night-10`, merged into `main`.
- **Branch:** the shift branch, cut from `main` (`agent/PROTOCOL.md` §11)
- **Report:** `agent/REPORT-28.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Sequential, one process.** Small night by design: one rule, one
  registry field, one guard file, one doctor section.
- **Depends on nothing.** Every item runs on whatever state TASK-22…27
  left behind; if a channel this task names does not exist yet, it is
  declared in the registry and **not invented** in code.
- **Goal of the night, in one sentence:** the user's ruling of
  13.09.2026 — *everything must be free* — stops being prose in a
  README and becomes a declaration every external channel carries and a
  guard that goes red when an obligatory route would cost money.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout main && git pull
git checkout -b agent/night-10        # once per shift, not per task
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
python3 -c "import rusterm.providers as p; print(sorted(p.available()))"
grep -rn "nightly_max=5000" rusterm/providers/__init__.py | wc -l
```

Line 3 must print `STATUS=0`. **If it does not, the first commit of the
night is the repair**, and the report says what was red on arrival —
this task does not build on top of a red tree. Line 5 prints the real
list of registered provider names: R1 declares a tier for **those**
names, not for the names written in this file. Line 6 says how many
seats still carry the placeholder ceiling.

## 0.1. Where we are. Say what you measured, not what you assume

The coordinator has **not** re-run acceptance on `agent/night-9` — the
queue TASK-22…27 is reported finished and is not yet reviewed. So this
task takes nothing about that tree on faith:

| Thing | Source of truth for tonight |
|---|---|
| Acceptance state | your own `selfcheck.sh` run in §0, quoted in the report |
| Registered providers | `rusterm.providers.available()` output, quoted |
| Schema version | line 4 of §0, never assumed |
| Free-tier ceilings | the vendor's own documented number, or the placeholder named as a placeholder |

Two things are already true and are **not** re-litigated: quotations
come from Twelve Data's free tier (ADR-0014), and the model is reached
through OpenRouter with the user's key (ADR-0011, ADR-0016).

## 0.2. Decisions taken. Not open for re-litigation

1. **ADR-0018 is the rule**, accepted 13.09.2026: no function named in
   README requires money. Disagreement is a `Disputed` entry in the
   report, never an edit of the rule.
2. **A card is payment.** A free tier that asks for a payment card at
   registration is a paid channel. A contact address, an email
   registration or a free key is not payment.
3. **No paid channel is added tonight, not even as an option.** What is
   built is the door that refuses one. A paid seat exists only inside a
   test as a synthetic fixture.
4. **A number about a free tier is quoted from the vendor or absent.**
   No ceiling is invented, and the 5000/host project placeholder is
   printed as a placeholder, not as a vendor limit.
5. **P1 holds**: not one existing assertion is deleted or loosened, in
   `tests/test_budget.py`, `tests/test_llm_api.py`,
   `tests/test_invariants.py` or anywhere else.
6. **A key value never reaches stdout, stderr, a log line or a report.**

---

## 1. Working protocol. This outranks the task list

Identical to `agent/TASK-19.md` §1. Tonight's specifics:

- **Network budget: 10 requests** across all data hosts, through
  `RequestGate` only — this night is offline by nature. **Model calls:
  0.** Count both in `STATE.json`.
- `agent/selfcheck.sh` is chained with `&&`, never `;`.
- `docs/` is frozen: ADR-0018 already exists and is **not** edited. No
  new ADR is needed tonight; if you think one is, that is a `Disputed`
  entry.
- `README.md` §1, §7, §9, §12 and §15 already carry the rule — written
  by the coordinator 13.09.2026. Do not restate it there; R5 touches
  `GUIDE.md` only.

---

## 2. The work, in priority order

### R1. Каждый внешний канал объявляет свою стоимость

**Zone:** `rusterm/providers/__init__.py`, `tests/test_free_only.py` (new).

Today the registry declares a host and a rate for every network name and
says nothing about what the channel costs. The declaration gains one
closed-set field:

| Tier | Meaning | Example today |
|---|---|---|
| `open` | no key at all, or a contact header | `cvm`, `asx`, `otcmarkets` |
| `free_key` | key issued by registration, no card | `edgar` (contact), `dart`, `llm-api` |
| `paid` | subscription, tariff, deposit, card at registration | none |

- The field lives beside `HostLimit`, is required for every entry in
  `_NETWORK_PROVIDERS`, and a name without it is a `ConfigError` value
  at registry build time — the same door as TASK-8 U5, not a convention.
- The registry **refuses** to hand out a provider declared `paid`:
  the return is a named `ConfigError` value (`paid_channel_refused`),
  `calls_made` stays 0, and nothing is logged that names a key.
- The tier of every name that exists tonight is `open` or `free_key`.
  Do not add a paid name to prove the door works — the test injects a
  synthetic one.

**Done when:** `python3 -m pytest tests/test_free_only.py -q` is green
and asserts all three: every registered network name declares a tier
from the closed set; **no** registered name declares `paid`; a synthetic
`paid` seat injected into the registry inside the test is refused by
value with `calls_made == 0`. The report quotes `available()` with each
name's tier beside it.

### R2. `doctor` печатает раздел «бесплатность»

**Zone:** the `doctor` command, `tests/test_free_only.py`.

The rule is worth as much as the user's ability to see it holding. A new
section prints, per registered channel: name, host, tier, the documented
free ceiling (or the word «проектный потолок» when it is the 5000
placeholder), and whether the key is present — `да` / `нет`, never the
value.

- The numbers come from the registry, not from prose in the command.
- A channel whose key is absent is **not** an error here: it prints
  `нет` and the command's exit status does not change.

**Done when:** `rusterm doctor` output is pasted into the report; a test
asserts every name from `available()` appears in the section with its
tier, that the string `paid` appears nowhere in the output, and that
`grep -c` for a dummy key value over the whole output is 0 (run with
`RUSTERM_LLM_API_KEY=dummykey` set).

### R3. Потолок бесплатного тарифа перестаёт быть проектной цифрой

**Zone:** `rusterm/providers/__init__.py`, the price seat,
`tests/test_free_only.py`.

`nightly_max=5000` is a project placeholder from the night when no
vendor limit had been measured. Where a vendor documents its free
ceiling, the registry carries **that** number:

- quotations (Twelve Data free tier): **8 requests/min and 800/day** —
  ADR-0014 §1, the rate carried as the per-second equivalent, the day
  ceiling as `nightly_max=800`;
- every other name keeps the placeholder **and is named as carrying a
  placeholder** in the report, one line each. Do not guess a ceiling for
  a vendor that does not publish one.

If the price provider module does not exist on the tree you branched
from (TASK-23 K2 was reported blocked on the key), the declaration still
lands in the registry — **the module is not faked to host it**, and the
report says which of the two cases you were in.

**Done when:** a test asserts the quotations channel declares
`nightly_max == 800` and a per-second rate no greater than `8/60`; the
existing budget behaviour is unchanged (`budget_exceeded` returned by
value past the ceiling, never a wait) and the existing
`tests/test_budget.py` assertions are untouched.

### R4. Новый хост не появляется мимо реестра

**Zone:** `tests/test_free_only.py`.

The rule fails quietly the day someone adds a URL to a provider module
for a channel nobody declared. A guard closes it: every host literal
reachable in `rusterm/providers/*.py` belongs to a host declared in the
registry.

- Collect host literals by parsing the module source (`ast`), not by a
  regex over comments — a hostname inside a docstring that explains a
  **refused** paid alternative (`otcmarkets.py`, `asx.py` both carry
  one) is prose, not a channel, and must not turn the guard red.
- The guard names the offending file, line and host when it fires.
- Show it red once: add a literal for an undeclared host in a scratch
  edit, paste the red output into the report, revert.

**Done when:** the guard is green on the tree as it stands and red on
the deliberate offender, both outputs in the report.

### R5. Пользователю нигде не предлагается платить

**Zone:** `GUIDE.md`, the advice string for a missing key,
`tests/test_free_only.py`.

Every place where the program asks the user for a key says what it
costs — and the answer is always «бесплатно»:

- `GUIDE.md` gains one table: env variable, where the key is issued,
  what it unlocks, **cost = бесплатно**, and the documented free ceiling
  where the vendor publishes one;
- the refusal a command prints when a key is absent names the free tier
  and never suggests a paid plan.

**Done when:** a test asserts every key env name used by
`rusterm/providers/` appears in the `GUIDE.md` table; the pasted output
of one key-less command run is in the report.

### R6. Backlog

Take items from `agent/BACKLOG.md` top-down until 10:00. Each pulled
item gets its verify line in the report.

---

## 3. Closing the shift

Stop at **10:00 Danang (UTC+7)** whatever the state, push, and fill this
in at the end of `agent/REPORT-28.md`:

```
Status:          DONE | PARTIAL | BLOCKED
Arrival state:   selfcheck STATUS= on the first run, before any commit
Items done:      R1, R2, …
Items not done:  … and why
Acceptance:      the "Итог" line and the exit status captured before any pipe
Tests:           N passed, N skipped, N xfailed
Tiers:           available() with the declared tier of each name, verbatim
Ceilings:        which names carry a vendor number, which carry the placeholder
Guards:          R1 paid-seat refusal and R4 undeclared-host — red output pasted?
Secrets:         artefacts grepped for the dummy key — hits (must be 0)
Network:         requests used of the 10 budget, per host
Pushed:          yes/no
Questions for the coordinator:
1. …
```
