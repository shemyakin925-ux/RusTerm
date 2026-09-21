# BACKLOG — pre-approved small tasks for idle executor time

Maintained by the coordinator (Claude). The executor pulls items
top-down **only** when the main `agent/TASK-*.md` queue is empty, and
reports each pulled item in its report file.

## Item format

```
- [ ] <ID> — <one-line objective> — accept: <command or check> — size: <S/M/L>
```

**Closing an item moves the whole block.** Every continuation line of a
bullet belongs to that bullet: either move the whole block into `## Done`
and collapse it to one `- [x]` line, or delete the whole block and write
the `- [x]` line. Deleting only a bullet's first line leaves orphaned
prose in the queue — that happened on 09.09 and the coordinator repaired
it by hand.

## Coordinator rulings — TASK-19 (read once, then obey)

Accepted 11.09.2026, journal `agent/ACCEPTANCE-19.txt`. The three
"Disputed" points of `agent/REPORT-19.md` are settled here.

| # | Executor's point | Ruling |
|---|---|---|
| 1 | P1 in `selfcheck.sh` narrowed to `*.py` | **Upheld.** The guard is about code; `assert` inside Russian backlog prose is not a removed assertion. `acceptance.sh` stays protected by acceptance check 12, a separate mechanism. Do not re-widen. |
| 2 | `llm-api` counted as the eighth name in `available()` | **Upheld.** 5 network seats + 2 synthetic + `llm-api` with its own `HostLimit`. Leave it registered. |
| 3 | `near_miss` shares the `manual_unverified` outcome with `failed` | **Upheld for now.** One bucket until the measure side selects on `source_kind` (TASK-20 L6); the split is `agent/TASK-27.md` N4, not a lane decision. |

Two questions from the REPORT-19 HANDOFF are answered here as well.
**Q1, merge ordering:** settled by **ADR-0017** — the integration night
merges the lanes itself, head-before-lanes, and the one predicted
conflict (the `import` block in `rusterm/cli/__init__.py`) is
pre-decided in favour of the lane. **Q2, `nightly_max` ownership:**
confirmed — the 5000/host default is the project-wide fallback, and a
lane overrides it inside its own provider module with a measured
ceiling. A lane that does not measure one leaves the default and says so
in its report.

Noted, no action required: the honest incident note on commit `51795c9`
(selfcheck ran red, `;` instead of `&&`, the commit landed anyway). The
red was the rewritten-seat-test false positive, not a weakened
assertion — checked line by line by the coordinator. The correction
(`&&` always) is the right one.

## Coordinator rulings — TASK-21 (read once, then obey)

Accepted 12.09.2026, journal `agent/ACCEPTANCE-21.txt`. The one
"Disputed" point and the three HANDOFF questions of `agent/REPORT-21.md`
are settled here. These are rulings, not opinions: do not re-litigate
them inside a night, and do not act on a different reading.

### 1. Disputed — legacy sets where facts record no currency

**Upheld, with an expiry date attached.** The trade-off stands: a set
in which no fact carries a currency computes as before, and a set in
which some facts carry one and the rest are blank computes as that one
currency. Do **not** run a `missing_data` sweep over legacy rows now.

Why: the sweep would move `golden_m2.json` and `golden_m6_ca.json` on
the strength of zero real data. Verified by the coordinator on the
merged tree — `rusterm/parsers/__init__.py` writes `"currency": None`
in all three places, so today **every** fact in the repository is blank.
A rule that flags blanks would therefore turn every existing set red
for a condition nothing in the program can currently satisfy. A guard
that is red by default teaches people to ignore it (same reasoning as
the 109-of-170 measurement above).

**Expiry, stated now so it is not forgotten:** the blank rule lands in
the same item that makes a provider write `fact.currency` — TASK-22 J1,
precondition J1.0. From that commit on, a blank currency on a fact whose
provider does record one is `missing_data`, and a mixed set with blanks
is `currency_mismatch`. The goldens may move **in that commit and only
there**, with the before/after diff quoted in the report.

### 2. Question 1 — same point

Answered by ruling 1: keep it until J1.0, then close it in J1.

### 3. Question 2 — BR/AU collection channels, "confirm the sequencing"

**The premise is wrong; the sequencing was not confirmed because the
item did not exist.** The coordinator checked TASK-23 (K1-K9, quotations)
and TASK-24 (N1-N13, industry): neither carries an `ingest` channel for
`cvm` or `asx`. BR and AU issuers being addable-but-not-collectable was
a hole in the queue, not a deferred decision.

**Closed now:** the item is `agent/TASK-27.md` **N7** (quotations and
industry keep their nights; M13 is the night for debts whose
preconditions have arrived, and this one's have). Do not take it from
the backlog and do not smuggle it into TASK-22 — it is a night's work,
not idle-time work.

### 4. Question 3 — should `fact.currency` wiring precede TASK-23?

**Yes, and it is now a precondition inside TASK-22, not a separate
night.** The executor is right about the risk and the coordinator
verified the cause: TASK-22 J1 as written ("every displayed and exported
absolute number carries its currency") **cannot be satisfied** on a tree
where every parser writes `None`. Without J1.0 the executor would have
had to either fake a currency or report J1 blocked.

TASK-23 K6 ("price in its own currency") then builds on facts that
really state one, and the H3 firewall starts guarding data instead of
synthetic fixtures. Read TASK-22 J1.0 before J1.

### 5. H2 — no tag added to `concepts.py`

**Upheld, and the rule is now general.** No lane recorded a concrete
missing `ifrs-full` tag against a concrete recorded payload, and nothing
was added. That was the right call and it is the standing rule: a
taxonomy tag enters `rusterm/normalize/concepts.py` only together with
the payload that proves it. A tag without a payload is a guess, and a
guess in a concept map is indistinguishable from data.

The BR gap list (`CD_CONTA`, `DS_CONTA`, `VL_CONTA`, `ESCALA_MOEDA`
unmapped) is real and belongs to TASK-27 N7 with the collection channel
that will produce the payloads.

## Coordinator rulings — TASK-29, 28, 30 (14.09.2026)

Accepted 14.09.2026, journal `agent/ACCEPTANCE-30.txt`. The shift's
questions and its two `Disputed` entries are settled here.

| # | Question (report) | Ruling |
|---|---|---|
| 1 | R3's Done-when («test_budget.py untouched») contradicted R3's own work section («the declaration lands in the registry») (28) | **Executor upheld; the task text was the bug.** Implementing per the work section was right, and both replacements are strictly stronger. The general rule follows: a pin over the registry is **derived from the registry**, never hand-typed — TASK-40 L7. |
| 2 | `test_twelvedata_seat_is_refused_until_module_lands` replaced once the module landed (30, Disputed) | **Upheld.** The successor asserts more: the seat builds the client and the key door answers `twelvedata_key_unset`. |
| 3 | B33 closed as already done by TASK-27 N6 (28) | **Confirmed**, and TASK-40 L4 now names B34 and B35 only. |
| 4 | `selfcheck.sh` prints only the tail of a red acceptance run, so the flake could not be attributed (29) | **Fix it** — TASK-40 L5. A guard whose failure cannot be read teaches people to re-run instead of read. |
| 5 | `test_m4_scale` timing flake under load (29, 30) | **Make it load-tolerant** — TASK-40 L6: assert the shape (ratio with a stated tolerance), never a wall-clock budget. |
| 6 | Cadence has no CLI surface (30) | **Yes, a command** — TASK-31 C5, with a `--json` form joining the B16 key pin and one line in `doctor`. |
| 7 | The free tier sends no vendor `adjusted`, so K3's cross-check has no input (30) | **Recorded as a decision, not a gap: ADR-0019.** `price_adj` is the only source of adjusted values; `adjusted IS NULL` is pinned by the golden test so the day the vendor starts sending it the pin goes red; TASK-31 C1 is rewritten to three internal proofs. Buying the paid plan is not an option (ADR-0018). |
| 8 | The leaked OpenRouter key prefix from the 13.09 arrival red (29) | **Not a repository defect** — nothing tracked carries it (re-verified). Re-issuing the key is the user's action; the executor has nothing to do here. |

Noted, no action required: the I9 violation in TASK-30 B2 (cache lookup
SQL written into `rusterm/cli/__init__.py`) was caught by acceptance
check 7 and repaired into `RawRepo.find_by_provider_url` inside the same
shift. That is the guard system working as designed — reported honestly,
fixed in the open.

## Coordinator rulings — TASK-22…27 (read once, then obey)

Accepted 13.09.2026 as they stand, journal `agent/ACCEPTANCE-27.txt`,
merged into `main`. The fourteen HANDOFF questions of REPORT-22…27 are
settled here. These are rulings, not opinions.

| # | Question (report) | Ruling |
|---|---|---|
| 1 | J3 landed without a migration — accept? (22) | **Accepted.** P2 protects applied migrations; it does not require a new one for a column that already existed. A migration that changes nothing is noise. |
| 2 | `origin` keeps the verification vocabulary, composition in its own field (22) | **Confirmed.** One column, one meaning. |
| 3 | `extract_text` seat still refuses while `extract.py` works (22) | **Wire it through** — TASK-34 F5. A door built and bypassed is the F6 defect. |
| 4 | 14-day completion grace vs 10-day poll interval (23) | **Confirmed.** A missed pass flips the instrument into backfill; it never stays "complete but stale". |
| 5 | Dividend factor needs the prior day's close; events without it skipped (23) | **Confirmed.** Skipped and named, never invented. |
| 6 | K2/K7 once the key exists — handover or fold in? (23) | **Own tasks:** TASK-30 (K2, K7) and TASK-31 (the vendor half of K3/K4). |
| 7 | Widen check 10 for `docs/industry-metrics/*.md`? (24) | **Yes, and it is already done** — the coordinator widened `agent/acceptance.sh` on 13.09.2026: an **added** catalogue page counts like an added ADR. Editing an existing `docs/` file is still a failure, and the executor still never edits `acceptance.sh`. |
| 8 | N4 — later night or the coordinator's key-holding run? (24) | **TASK-34.** The executor holds the keys from 13.09.2026. |
| 9 | Tools registry pin 4 → 5 (`get_industry_metrics`) (24) | **Confirmed** as the intended surface. |
| 10 | `STALENESS_DAYS = 550` — confirm or set? (25) | **Set to 450 days.** An annual proxy plus a late-filing grace; 550 lets a two-season-old document pass as current. Name the constant once and let the prose refer to the name. |
| 11 | 10b5-1 sales — keep in `insider_net` or split? (25) | **Keep them in, and name the share.** The indicator's detail states how much of the net came from 10b5-1 plans, so a scheduled sale cannot distort the colour invisibly. TASK-33 E1. |
| 12 | Does ADR-0016 gate Q4's model comparison? (26) | **No.** ADR-0016 gates *widening the model's reach*. A read-only comparison on a fixed corpus is measurement, not reach. TASK-35 proceeds. |
| 13 | Transcripts need a migration — fold into the next schema task? (26) | **TASK-36 H1**, with the schema-history pins updated in the same commit. |
| 14 | N7 — one dedicated night, or split BR from AU? (27) | **Split:** TASK-38 (BR, the real half) and TASK-39 (AU, announcements only). N5's scale pass is TASK-40 L1 with a 40-request budget. |

Three defects the coordinator found while reviewing are tasks, not
backlog items: the self-adjustable formulas baseline (**TASK-40 L2**),
the widened reason assertion (**TASK-40 L3**), and the suite going red
on a machine that has the keys (**TASK-29**, whole task).

## Standing rule — everything is free (user, 13.09.2026)

Written as **ADR-0018** and into README §1, §7, §9, §12, §15. It binds
every task and every backlog item from this date on, idle-time work
included.

| Question | Answer |
|---|---|
| May an item depend on a paid tariff, subscription, deposit or pay-as-you-go channel? | No. |
| Is a free tier that asks for a payment card at registration free? | No — a card is payment. |
| Is a free key issued by registration free? | Yes (DART, Twelve Data free, OpenRouter). A contact header (`RUSTERM_SEC_UA`) is not payment either. |
| A channel is closed unless you pay — what happens? | The existing named refusal (`source_unreachable`, `manual_import_required`) and manual import. Never a paid detour. |
| May a paid vendor be named? | In an ADR, as a rejected alternative with its price. Never in code as a default, never in acceptance, tests or CI. |
| Which model? | Free models through the user's OpenRouter key. Budget is counted in free-tier requests; the project counts no money, because it spends none. |
| A free ceiling is unknown — may it be estimated? | No. Quote the vendor's number or say «проектный потолок» and name it as a placeholder. |

The rule is made machine-checkable by **`agent/TASK-28.md`** (registry
tier field, refusal door, doctor section, undeclared-host guard). Until
that lands, the rule is still binding — it is simply checked by reading.

## Guards the coordinator added 11.09.2026. Do not weaken them

Two guard tests were written by the coordinator, not by a lane. **P1
covers them: not one assertion in either file is deleted or loosened.**
A guard that becomes inconvenient is a `Disputed` entry, never an edit.

| File | What it forbids | How it is satisfied |
|---|---|---|
| `tests/test_docs_truth.py` | a hand-typed number about the repository in README («402 пройдено», «тринадцати ADR») | say no number, or derive it; every file in `docs/adr/` must be named in README §15 — so a new ADR forces a roadmap update |
| `tests/test_single_door.py` | a door built and then bypassed — the TASK-19 F6 defect, where `make_intent_client` was written, tested and called by nothing while `cmd_ops` constructed `RuleClient()` directly | while the door is listed in `PENDING`, the debt stays visible and addressed to a task item; **wiring it means deleting that line**, and the rule flips to forbidding any direct construction |

The second guard is deliberately narrow. A blanket "every public
function must have a caller" rule was measured on this repository and
fires 109 times out of 170 — it would flag the twenty industry
functions and every formula reached from a registry by name. A guard
that is red by default teaches people to ignore it.

## Queue

Coordinator, 17.09.2026, after the full project check. Three notes on
items already here, then two new ones:

- **B35 and B37 are now inside TASK-50** (T6 and its Done-when). B35 is
  also implemented on the coordinator's `fix/connectivity` branch —
  `rusterm markets` no longer creates `rusterm.db`, `exports/`, `logs/`
  and `raw/` in the current directory, with a test that runs the command
  from a foreign directory and asserts it stays empty.
- **B36 (the live model path) is worth taking only after TASK-50 T1.**
  Until the chat door returns a client that implements what
  `ChatSession.ask` calls, a live-model test measures a fake.

- [ ] B39 — `rusterm refresh --dry-run` prints `US-CLI-DEMO: ошибка (у
  эмитента нет CIK)`. «Ошибка» is not a reason: rule 2 of
  `agent/CONTEXT.md` §3 wants a token from `rusterm/reasons.py`, and a
  planning command that will never resolve an issuer should say so in
  the closed vocabulary — accept: the line carries a reason token and
  `is_known_reason` accepts its first token, asserted by a test —
  size: S

- [ ] B40 — audit the remaining read-only commands the way B35 fixed
  `markets`: `budget`, `cadence`, `status` and `coverage` open the data
  directory through `_open`, which creates it. Decide per command
  whether it must create anything at all when the directory is absent —
  accept: each command that only reads is listed in the report with its
  verdict, and the ones that should not create anything are covered by
  the B35-style test — size: M


## External review, 21.09.2026 — six items taken, the rest rejected

Source: a 30-point improvement list produced by an outside model from
the README and the commit titles. The coordinator checked every point
against the code. Six are real and are queued below as B41-B46, in
priority order. The rest are recorded here **with the reason they were
rejected, so they are not re-proposed**:

| Proposed | Verdict |
|---|---|
| structured logging instead of `print` | Already done — `rusterm/applog.py` is `logging` + `RotatingFileHandler`; zero `print(` in `rusterm/` outside `cli/`, where it is the program's output |
| a `ProviderError` class | Exists — `rusterm/providers/base.py:8` |
| exception subclasses `RateLimitError` / `AuthError` | **Forbidden.** Errors are values, not exceptions, on every provider path (CONTEXT §3 rule 5) |
| Alembic | Versioning exists — `_SCHEMA_VERSION`, `_MIGRATIONS`, `_CUSTOM_MIGRATIONS` in `rusterm/store/db.py`; P2 protects applied migrations |
| break the import cycles between `store`/`core`/`providers` | No cycle was named. I9/I10 forbid it and acceptance checks 7-9 enforce it machine-side |
| formulas as a YAML/TOML DSL | **Rejected.** A measure carries `null_reason`, `lineage` and `method_version` and must refuse rather than invent; a DSL re-implements Python and weakens that. The live defect (`clip()` in `effective_tax`) is about honesty, not declarativeness |
| pydantic / structlog / pybreaker / jinja2 / fuzzywuzzy / plotext / reportlab / babel / redis / semantic-release | `pyproject.toml` declares `dependencies = []` by decision; heavy things live in extras. A new mandatory dependency is a task with an ADR, never a backlog item |
| benchmarks | `tests/test_m4_scale.py` exists (TASK-40 L6 made it load-tolerant) |
| canary / feature flags for new markets | ADR-0013 already fixes the order of adding a market |
| i18n (gettext/babel) | One local user, no value |
| build a PySide6 desktop | Done — `rusterm/desktop/`, ADR-0004 and ADR-0023, lane C merged |
| `tomllib` with a `tomli` fallback, for Python 3.10/3.11 (external review, 21.09.2026) | **Rejected.** `requires-python = ">=3.12"`; `tomllib` is stdlib from 3.11. A fallback is a new *mandatory* dependency for a Python the project does not support, and pip already refuses to install below the floor. Measured here: Python **3.14.6**, `import tomllib` ok |
| disable `pytest-qt` in `addopts` / a root `conftest.py` (external review, 21.09.2026) | **Rejected.** The project neither uses nor installs `pytest-qt`; it is absent from this environment and the suite runs. A third-party plugin broken in someone else's environment is not a repository defect |
| release notes, rollback CI, bandit | No release channel, no network-facing surface, no untrusted input outside the manual-import path that ADR-0016 already governs |

- [ ] B41 — the model door caches its answers, so a repeated question
  costs no free-tier request (ADR-0018). Key = sha256 over
  (model name, full prompt, tool-result payloads); **only an accepted
  answer is cached** — an answer rejected for an uncited number
  (ADR-0016) is never stored. **Placement:** the table and its repo live
  in `rusterm/store/` (SQL only there, check 7), the lookup is done by
  the single door `make_intent_client` / `core/llm.py`; `providers/`
  gets no SQL, or acceptance check 7 goes red the way TASK-30 B2 did —
  accept: a test with a counting fake client asserts two identical asks
  make **one** provider call, a different model name makes two, and a
  rejected answer leaves the cache empty; `_SCHEMA_VERSION` bumped with
  the schema-history pins updated in the same commit — size: M

- [ ] B42 — a host that answered 403/429 is not hit again until it has
  cooled down. Today `twelvedata` stops by value and `llm_api` retries
  once with a backoff, but nothing remembers the refusal, so the next
  command walks into the same wall and burns the nightly ceiling.
  `RequestGate` gains a per-host `cooling_until`, set from `Retry-After`
  when the response carries one and otherwise from a named constant; a
  request to a cooling host returns `source_unreachable: cooling` as a
  **value** and makes no HTTP call. **I10 holds:** `budget.py` imports
  no store and no `sqlite3` — the state lives behind an injected
  get/set port whose default is an in-process dict; a store-backed
  implementation is a later item, not this one — accept: a test drives
  a fake sender that answers 429, then asserts the next call inside the
  window sends nothing and returns a reason whose first token
  `is_known_reason` accepts, and that a call after the window sends
  again; `gate.calls_made` unchanged by the suppressed call — size: M

- [ ] B43 — an ingest killed in the middle leaves a database that still
  opens and still tells the truth. The base is WAL with
  `isolation_level=None`, i.e. autocommit, so a multi-step ingest can
  commit half of itself; nothing measures what that half looks like —
  accept: a test runs a synthetic-fixture ingest in a subprocess,
  `kill -9`s it at a named step, then asserts `PRAGMA integrity_check`
  returns `ok`, `doctor` reports no dangling reference in either
  direction (B9), and re-running the same ingest is idempotent (B3).
  Any inconsistency found is **reported, not fixed**, in the same pass;
  the fix is a task — size: M

- [ ] B44 — the commit hook runs a linter. `agent/githooks/pre-commit`
  already runs selfcheck; add `ruff check` over the **staged** `*.py`
  only, with the rule set written into `pyproject.toml`. Two hard
  conditions: ruff stays an optional dev tool (`dependencies = []` is
  untouched, `[project.optional-dependencies].dev` at most), and an
  absent ruff prints one named skip line and leaves the hook green —
  never red, never a silent pass. `mypy` is out of scope of this item —
  accept: a staged file with an undefined name makes the hook red and
  the commit fail; with ruff uninstalled the same commit succeeds and
  the hook prints the skip line; `bash agent/selfcheck.sh` still green
  — size: S

- [ ] B45 — the TUI answers `?` with a key overlay and `/` with a
  search over the current list (watchlist, snapshot rows, industry).
  Both must survive 80x24 — the 44-line card crash is the precedent, so
  the overlay paginates rather than assumes height. The test **drives
  the key**, not the screen function: a function called directly proves
  nothing about the key that opens it (CONTEXT §3, the `_chat_screen`
  defect) — accept: a test feeds `?` then `q` and `/` + a substring
  through the key loop at an 80x24 geometry and asserts the overlay
  appears, filters, and closes without an exception — size: M

- [ ] B46 — the TUI uses colour where it carries meaning (governance
  green/amber/red, a null reason, a changed value). Measured
  21.09.2026: `init_pair`, `color_pair` and `start_color` appear **zero**
  times in `rusterm/tui/`. Colour is added only behind
  `curses.has_colors()`, the monochrome path stays a first-class path,
  and nothing here may put ANSI into piped output (B11) — accept: a test
  asserts the screens render identically in content with colours forced
  off, and that a terminal reporting no colour support takes the
  monochrome path without an exception — size: S

Refilled by the coordinator 10.09.2026 after accepting TASK-14…18.
Every item is small, pre-approved, and independent of the M8 lanes.
A parallel lane may take one **only inside its own zone** (ADR-0012 §2).

- [ ] B38 — the interim `## HANDOFF` blocks pile up in a shift report:
  `REPORT-45.md` ends with two of them and a reader must know that the
  second supersedes the first. Once TASK-46 N1 makes the guard read the
  last one, collapse the convention into one line in `agent/PROTOCOL.md`
  §5 — interim HANDOFF is headed `## HANDOFF` and the final one
  `## HANDOFF (FINAL)` — accept: `grep -c '^## HANDOFF' agent/REPORT-46.md`
  is the number of passes, and the guard names the final block — size: S

- [ ] B37 — `agent/selfcheck.sh` leaks its guard temp dir: the
  `mktemp -d` for the extracted `p1_rule.sh`/`p6_rule.sh` copies (TASK-37
  I5) has no trap, and the later `trap ... EXIT` for the acceptance file
  would replace one anyway — so every selfcheck run, i.e. every commit,
  leaves a `selfcheck-guards.XXXXXX` directory behind. Remove both dirs
  from a single EXIT trap — accept: run `bash agent/selfcheck.sh`, then
  `ls -d "${TMPDIR:-/tmp}"/selfcheck-guards.* 2>/dev/null` prints
  nothing — size: S

- [ ] B36 — the M5 live model path, implemented behind the `live`
  marker (debt guarded by the TASK-9 V7 tripwire, which on 13.09.2026
  became a `live`-marked test instead of a default-run failure, see
  TASK-29 A3): a real model answers through the read-only tools with
  every numeric claim cited — at most 2 model calls, a mass operation
  executes nothing (the TASK-7 T16 contract) — accept:
  `python3 -m pytest -m live tests/test_llm_real.py` with the key set
  is green — size: M
- [ ] B34 — the OTC universe drift (12,794 live vs 12,867 in
  `agent/REPORT-MARKETS.md`) gets a written tolerance instead of a
  finding repeated every night — accept: REPORT-MARKETS states the
  tolerance band and the date of the last live count — size: S


- [→] B22, B27, B29 — **promoted to `agent/TASK-27.md`** (items N2,
  N3, N5) on 11.09.2026. Each was deferred in TASK-19 for a stated
  reason — `extract.py` absent, measure-side `source_kind` selection
  absent, six-market providers absent — and each reason is gone by the
  night TASK-27 is taken. Do not take them from here: they are a
  night's work now, not idle-time work.

## Done

- [x] B35 — closed with ТЗ-57 A3 (commit of 19.09.2026 on
  `agent/night-11`): `markets`, `markets --json` and `--help` leave
  `git status --porcelain` empty from a clean tree, positive control
  asserts `init`/`ingest` still create the catalog —
  `tests/test_b35_markets_readonly.py`, agent/REPORT-57.md. The
  remaining `_open`-vs-`_open_readonly` divergences found by the same
  sweep (metrics, doctor, census, tui) are reported, not fixed —
  agent/REPORT-57.md A3.
- [x] B33 — selfcheck reads its expected check count from acceptance.sh instead of hard-coding "пройдено 13" — landed with TASK-27 N6; re-verified 13.09.2026 (scratch 14-check copy counts 14, the pass condition matches 14, a 12/1 outcome fails the match as seen live at arrival) — TASK-28 R6, agent/REPORT-28.md

**ID reuse, noted 12.09.2026.** The numbers B19-B25 were handed out
twice — once in the TASK-7/11/12/14 era and again in the TASK-19 era —
so two different items can share one ID. The era is named in every line
below; read the description, not the number. Numbering continues from
B35 and is not reused again.

On the same date the coordinator removed 35 exactly-duplicated bullets
from this section: closing an item had appended the whole TASK-19 F11
block a second time on each pass. No item was deleted, only its copies.

- [x] B32 — README states no hand-typed count of itself — done by the coordinator 11.09.2026, not by an idle evening: guard `tests/test_docs_truth.py` (bans «N пройдено», «N тестов», «N ADR», and requires every file in docs/adr/ to be named in §15), README §15 cleaned of «402 пройдено» and «тринадцати ADR». Both tests were shown red before the fix.
- [x] B21 — import --dry-run writes nothing — TASK-19 F11, verified 11.09 (database sha256 unchanged; extraction attempts on the F8 seat, pipeline lands with L5/L6)
- [x] B31 — ADR number uniqueness guard — TASK-19 F11, verified 11.09 (deliberate 0011 duplicate ran red, removed, green)
- [x] B30 — GUIDE.md user guide — TASK-19 F11, verified 11.09 (every pasted output from real runs in /tmp/rusterm-guide; tui described, not screenshotted)
- [x] B28 — raw store retention pass — TASK-19 F11, verified 11.09 (prune_raw_store: fact/document-referenced survive, unreferenced rows+files and orphan files removed, manifest append-only)
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — payload size guard as a test — TASK-19 F11, verified 11.09 (256 KB per file under tests/data/, offender named)
- [x] B23 — verify near-miss bucket — TASK-19 F11, verified 11.09 (verify_status: thousands/apostrophe mismatches land near_miss)
- [x] B20 — provider seat without module never reaches RequestGate — TASK-19 F11, verified 11.09 (ConfigError + calls_made == 0)
- [x] B19 — `rusterm markets --json` — TASK-19 F11, verified 11.09 (json.tool parses; all registry fields asserted)
- [x] B1 — invariant numbering contiguity guard — TASK-7, verified 08.09
- [x] B2 — fixtures are synthetic, as a test — TASK-7, verified 08.09
- [x] B3 — job-queue idempotency on a second run — TASK-7, verified 08.09
- [x] B4 — second golden issuer with preferred class — TASK-7, verified 08.09
- [x] B5 — `price_adj` split/dividend order independence — TASK-7,
  verified 08.09 (first commit was red, fixed in the next one)
- [x] B6 — `doctor` reports schema drift, test added — TASK-7, verified 08.09
- [x] B7 — coverage blocks doc/code drift guard — TASK-7, verified 08.09
- [x] B8 — zstd branch covered by a fake module — TASK-7, verified 08.09
- [x] B9 — doctor cross-checks the raw store against the database in both
  directions — TASK-11 X5, verified 09.09
- [x] B10 — `watchlist show --version N` — TASK-11 X5, verified 09.09
- [x] B11 — piped output carries no ANSI, with a test — TASK-11 X5,
  verified 09.09
- [x] B12 — the audit JSONL failure path returns an error value and the
  database row is still written — TASK-12 Y7, verified 09.09
  (the CLI printing that value is TASK-14 A5)
- [x] B13 — `export --format md` with footnoted nulls — TASK-12 Y7,
  verified 09.09
- [x] B14 — two AAPL payloads: folded into TASK-10 W2/W7 as a task item,
  removed from the queue 09.09
- [x] B15 — the null-reason vocabulary collected in `rusterm/reasons.py`
  with a repository-level guard — TASK-12 Y7, verified 09.09
- [x] B16 — the key schema of the four `--json` commands pinned —
  TASK-11 X5, verified 09.09
- [x] B17 — `resolve()` duplicate-ticker behaviour pinned (last feed row
  wins) — TASK-12 Y7, verified 09.09
- [x] B18 — `tools/README.md` added — TASK-12 Y7, verified 09.09
- [x] B19 — `logs/app.log` rotation: the test strengthened to the accept
  criterion (exactly two files, newest holds the last line) — TASK-12 Y7,
  verified 09.09
- [x] B20 — `refresh --json` request totals pinned to the sum of
  `RefreshResult.calls`, normal and mixed (error) pass — TASK-14 A8,
  verified 09.09
- [x] B21 — `IssuerStateRepo.get` returns `None` for a known issuer
  under a different source — TASK-14 A8, verified 09.09
- [x] B22 — the 1100-day rule named once (`_STALE_LOOKBACK_DAYS`),
  prose refers to the name — TASK-14 A8, verified 09.09
- [x] B23 — `trim_companyfacts` byte-stability on a recorded payload,
  sha256 of two runs — TASK-14 A8, verified 09.09
- [x] B24 — `audit.jsonl` capped and rolled over like `app.log` (same
  constants, imported) — TASK-14 A8, verified 09.09
- [x] B25 — `status --json` reports `schema_version_observed` beside
  `schema_version_expected` — TASK-14 A8, verified 09.09
