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

- [x] B39 — закрыта ТЗ-50, коммит bdc03de — ошибка прохода refresh называет причину из словаря. Исходная формулировка: — `rusterm refresh --dry-run` prints `US-CLI-DEMO: ошибка (у
  эмитента нет CIK)`. «Ошибка» is not a reason: rule 2 of
  `agent/CONTEXT.md` §3 wants a token from `rusterm/reasons.py`, and a
  planning command that will never resolve an issuer should say so in
  the closed vocabulary — accept: the line carries a reason token and
  `is_known_reason` accepts its first token, asserted by a test —
  size: S

- [x] B40 — закрыта ТЗ-50, коммит 3e75262 — budget/cadence/status/coverage не создают каталог. Исходная формулировка: — audit the remaining read-only commands the way B35 fixed
  `markets`: `budget`, `cadence`, `status` and `coverage` open the data
  directory through `_open`, which creates it. Decide per command
  whether it must create anything at all when the directory is absent —
  accept: each command that only reads is listed in the report with its
  verdict, and the ones that should not create anything are covered by
  the B35-style test — size: M


Refilled by the coordinator 10.09.2026 after accepting TASK-14…18.
Every item is small, pre-approved, and independent of the M8 lanes.
A parallel lane may take one **only inside its own zone** (ADR-0012 §2).

- [ ] B41 — targeted request counters: `add` and every `--source` ingest write provider_requests_used samples; `rusterm budget` and `status --json` show the real spend — accept: after add+ingest budget names a number greater than zero and equal to the requests actually made — size: M — **выдан ТЗ-64 J1**
- [ ] B42 — provenance in the CLI export: `--format json` carries lineage document and hash per measure, like the desktop export — accept: no measure with a value leaves the export without provenance — size: M — **выдан ТЗ-64 J2**
- [ ] B43 — price advice in refusals: `missing_data: price_close` carries a runnable `ingest --source twelvedata` line, substituted from constants — accept: the line parses with the CLI parser — size: S — **выдан ТЗ-64 J3**
- [ ] B44 — stage progress in ingest: fetch/parse/store with counters — accept: on a live companyfacts run the user sees moving stages instead of 74 silent seconds — size: S — **выдан ТЗ-64 J4**
- [ ] B45 — «неотображённых концептов: N» explained in words from the core, with map coverage share — accept: the ingest line explains the number instead of scaring — size: S — **выдан ТЗ-64 J5**
- [ ] B46 — a repeat snapshot on identical inputs does not bump the version (or says «без изменений») — accept: the second run leaves the version unchanged for identical content, a changed input still bumps it — size: M — **выдан ТЗ-64 J5**
- [ ] B47 — desktop collection for KR names `dart_key_unset` and how to get the key, in the same words as the CLI refusal (ТЗ-61 F4) — accept: the window refusal carries the reason and the substituted instruction line — size: S
- [ ] B55 — a guard must not depend on how many rounds passed since it was written: slice live git history by round number, never by head position (`_log_from_top_marker` pinned to the newest marker went red one round after it was written) — accept: appending N synthetic relay markers on top of the live log does not change the guard's verdict — size: S — **выдан ТЗ-80 A1**
- [ ] B56 — `relay.py hand` refusing on red acceptance prints only the phrase; three rounds in a row the review started by digging for the failing test — accept: the refusal names the `FAILED …` lines and the path to the full log, with `acceptance.sh` untouched — size: S — **выдан ТЗ-80 A2**
- [ ] B57 — `test_i5_staged_and_authorised_widening_is_green` fails in a linked worktree (and on uncommitted coordinator files) while a normal clone on the same commit is green — accept: the cause is measured and quoted, and the test either passes in both environments or skips with a reason naming the environment — size: M — **выдан ТЗ-80 A3**
- [ ] B54 — a `РАЗРЕШЕНО ПРАВИТЬ` line that `agent/p6_rule.sh` cannot parse silently revokes the permission (TASK-76/77/78 wrote it as a markdown bullet with backticks; the rule greps `'^РАЗРЕШЕНО ПРАВИТЬ:'` plus a bare path) — accept: a guard reds on the markdown form and names the line — size: S — **найдено исполнителем, ТЗ-78; выдан ТЗ-79 Z2**
- [ ] B52 — L3 is not bounded by the round: `_git_log_name_only()` scans the whole branch, so a repeated item id (`W3`) is satisfied by a TASK-53-era commit. Bound it the way G4 already is (`_commit_for_items(ids, round)`) — accept: an item closed only by an earlier round's commit is reported missing — size: S — **найдено исполнителем, ТЗ-76; выдан ТЗ-78 Y1**
- [ ] B53 — Verizon's shares route: the payload carries `dei:EntityCommonStockSharesOutstanding` and `CommonStockSharesIssued` − `TreasuryStockCommonShares`, not `CommonStockSharesOutstanding` — accept: `shares_outstanding` gets a value on the committed VZ fixture and the per-share measures come alive, with the route chosen by a stated rule — size: M — **выдан ТЗ-78 Y2**
- [ ] B49 — the add-dialog failure path opens a REAL modal `QMessageBox.warning`; an unresolved ticker hangs a headless run for minutes (measured in round 100: a 25s+ sample sat in `QDialog::exec`). Route the desktop's modals through one injectable seat so an offscreen run cannot block — accept: a headless press of «добавить» on an unresolvable ticker returns within a second and names the refusal, with no test-only patching of `QMessageBox` — size: M — **найдено исполнителем, ТЗ-75 S1**
- [ ] B50 — a measure's history year must come from the measure's period, not the snapshot's `as_of` (a base rebuilt today collapses all history into the current year) — accept: a snapshot taken in 2026 for a 2024 period lands in the 2024 column — size: M — **выдан ТЗ-76 W3**
- [ ] B51 — the desktop data layer's dictionary shapes are asserted on real data, so a fix that stops at the model never again misses the screen — accept: the guard reds when `measure_table_rows` is returned to `history[мера][год]` — size: M — **выдан ТЗ-76 W4**
- [ ] B48 — the first-hour scenario becomes a marked test: the measured path (init → add → ingest → snapshot → window → export) runs end to end and prints its own timings — accept: `pytest -m firsthour` passes and the numbers land in the report; default collection deselects it — size: M

- [ ] B38 (координаторский — правит agent/PROTOCOL.md §5, исполнителю не выдаётся) — the interim `## HANDOFF` blocks pile up in a shift report:
  `REPORT-45.md` ends with two of them and a reader must know that the
  second supersedes the first. Once TASK-46 N1 makes the guard read the
  last one, collapse the convention into one line in `agent/PROTOCOL.md`
  §5 — interim HANDOFF is headed `## HANDOFF` and the final one
  `## HANDOFF (FINAL)` — accept: `grep -c '^## HANDOFF' agent/REPORT-46.md`
  is the number of passes, and the guard names the final block — size: S

- [x] B37 — закрыта ТЗ-50 T6, коммит adad2e5; перепроверена 71d6fa9. Исходная формулировка: — `agent/selfcheck.sh` leaks its guard temp dir: the
  `mktemp -d` for the extracted `p1_rule.sh`/`p6_rule.sh` copies (TASK-37
  I5) has no trap, and the later `trap ... EXIT` for the acceptance file
  would replace one anyway — so every selfcheck run, i.e. every commit,
  leaves a `selfcheck-guards.XXXXXX` directory behind. Remove both dirs
  from a single EXIT trap — accept: run `bash agent/selfcheck.sh`, then
  `ls -d "${TMPDIR:-/tmp}"/selfcheck-guards.* 2>/dev/null` prints
  nothing — size: S

- [x] B36 — закрыта ТЗ-58 C2, коммит eaa91d7 (живая модель под гвардом цитат; принято кругом 72). Исходная формулировка: — the M5 live model path, implemented behind the `live`
  marker (debt guarded by the TASK-9 V7 tripwire, which on 13.09.2026
  became a `live`-marked test instead of a default-run failure, see
  TASK-29 A3): a real model answers through the read-only tools with
  every numeric claim cited — at most 2 model calls, a mass operation
  executes nothing (the TASK-7 T16 contract) — accept:
  `python3 -m pytest -m live tests/test_llm_real.py` with the key set
  is green — size: M
- [x] B34 — закрыта ТЗ-56, коммит 71d6fa9 — полоса допуска и даты живого счёта в agent/REPORT-MARKETS.md. Исходная формулировка: — the OTC universe drift (12,794 live vs 12,867 in
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
