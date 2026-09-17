# CONTEXT — the project in one file

Read this **instead of** re-reading `README.md`, `docs/` and old
reports. It is maintained by the coordinator and updated at every
acceptance. If it disagrees with the code, the code is right and this
file is a bug — say so in your report.

Last updated: 17.09.2026 evening, after the coordinator's **full
project check** of `agent/night-11` at `dac57a9` (machine acceptance
plus a hands-on run of the CLI and the curses screens). Accepted:
TASK-31…TASK-36, **TASK-37 I5-I8**, TASK-42…TASK-46. Acceptance at
`dac57a9` in a fresh linked worktree is «пройдено 13, провалено 0»,
exit 0, 720 tests collected — the report's numbers hold.

**And the product still does not work where a person touches it.** The
same green tree has two blockers found in the first minutes of the
manual run: the conversation screen dies on the first question
(`AttributeError: 'LlmApiClient' object has no attribute 'chat'`), and
the instrument card kills the whole program on a normal 80x24 terminal
(`_curses.error: addwstr() returned ERR`). Both are in **TASK-50**,
with four more findings. This is the third time running that a place
was built, covered by tests and never correctly called — and TASK-46 N2
declared the chat screen fixed two rounds before it was measured.

**Open product debt: TASK-37 I2** (does-not-know) — TASK-47 O1. I1
(question vs order) landed with TASK-46 N3, I3 and I4 are done. The
shift branch is `agent/night-11` and the turn is passed by the relay —
`agent/PROTOCOL.md` §12, driver `agent/relay.py`, baton
`agent/BATON.json`. Queue: TASK-47, 48, 49, **50**, all READY.

## 1. What the program is

EquityLab (`rusterm`): a local CLI that collects issuer disclosures with
provenance, normalises them into facts, computes measures from an
explicit dictionary, builds snapshots, watchlists and an industry
aggregate, shows them in a curses TUI, and answers questions about them
with a model whose every number must carry a citation. No cloud, one
user, data never leaves the machine. **Everything in it is free
(ADR-0018).**

## 2. Where things live

| Path | What |
|---|---|
| `rusterm/providers/` | the only place with HTTP; `__init__.py` is the registry (names → factories, `HostLimit` per host); `budget.py` is `RequestGate` |
| `rusterm/store/` | the only place with SQL; `db.py` holds `_SCHEMA_VERSION` and the migrations; `repos.py` the repositories; `backup.py`, `doctor.py` |
| `rusterm/core/` | snapshot, peers, industry, governance, prices, cadence, chat, tools, llm (the single door `make_intent_client`) |
| `rusterm/normalize/` | `concepts.py` — the concept map, `us-gaap` and `ifrs-full` |
| `rusterm/manual/` | manual import: extract → model → deterministic control |
| `rusterm/parsers/`, `formulas.py`, `reasons.py`, `markets.py`, `env.py` | parsing, the formulas, the closed vocabulary of null reasons, the market registry, the env-file loader |
| `rusterm/tui/` | curses screens |
| `agent/` | the coordination channel: this file, `PROTOCOL.md`, `TASK-*.md`, `REPORT-*.md`, `BACKLOG.md`, `acceptance.sh`, `selfcheck.sh`, `LAUNCH.md` (for the user, Russian) |

## 3. Standing rules that bind every task

**Coordinator-owned files (TASK-33 E6).** A staged diff touching
`agent/TASK*.md`, `PROTOCOL.md`, `CONTEXT.md`, `BACKLOG.md`, `LAUNCH.md`
or `acceptance.sh` is a red selfcheck — the executor owns reports,
`STATE.json`, `BATON.json`, code and tests.

**Guards are not self-widening (TASK-36 H6).** A `РАЗРЕШЕНИЕ-<file>:`
marker in a commit message means nothing unless the task file named in
`agent/BATON.json` says `РАЗРЕШЕНО ПРАВИТЬ: <path>`; the blocklist is not
overridable from the environment; an empty index checks `HEAD~1..HEAD`
instead of passing vacuously. **TASK-37 I5** makes selfcheck and the hook run the
*committed* guard, closing the `95b669a` bypass: `agent/selfcheck.sh`
extracts `p1_rule.sh` and `p6_rule.sh` from the index when staged, else
from `HEAD`, names the source in its output, and an unstaged guard edit
is red by itself. **I6** routes the git directory through `git rev-parse
--git-path` — except in `agent/p6_rule.sh`, which still reads
`.git/COMMIT_EDITMSG` literally. Until **I7** lands, a declared
`РАЗРЕШЕНИЕ-*` marker is invisible to P6 in any linked worktree (no
error — `.git` is a file there, the test simply goes false), so an
authorised edit reads as a violation. No I5 test drives that path: the
green case stages only the guard, the red case is over-determined.

**I5 cleans up after itself and survives a fresh tree (TASK-45
M1–M3).** The guard test module restores `agent/p6_rule.sh` and
`agent/CONTEXT.md` byte-exact — worktree bytes, file mode and the
index blob via `update-index --cacheinfo`, never `git checkout` —
keeps a guard edit that was already staged before the run verbatim in
the index, and asserts its own `git status --porcelain` clean. An
absent `COMMIT_EDITMSG` is the legal state of a fresh linked worktree:
it is saved as absence and restored as absence, not an error. The I8
sentinel compares the demonstration marker's session id with THIS
pytest process; a fresh marker from a live alien process is red.

**A red selfcheck cannot be committed (TASK-34 F6).** The tracked hook
`agent/githooks/pre-commit` runs it without a pipe; bootstrap once per
clone with `git config core.hooksPath agent/githooks`.

**The executor writes `updated_at` by hand and it drifts (round 58).**
Git stamps its commits from the real clock and those are correct; the
`updated_at` field of `agent/STATE.json` is typed, always on a round
minute, and ran up to **+232 minutes ahead** of real UTC during
TASK-45/46 — two consecutive commits even carried the same value. This
is not cosmetic: PROTOCOL §10 ends the shift at 10:00 Danang, so a
four-hour drift ends the night a third early. The machine is on +07, so
`TZ=Asia/Bangkok date` is the wall clock. TASK-47 O0 makes this a guard.

**An assertion that exists may still assert nothing (TASK-46 N3).**
P1 guards against a *deleted* `assert`; `assert <anything> or True` keeps
the line and proves nothing, and TASK-37 I1 counted as covered by such a
line for three nights. A second case is live in `tests/test_repos.py:246`
— it walks the AST for direct SQL outside `rusterm/store/`, prints
`WARNING:` and ends `assert True`. TASK-48 Q1 turns this into a guard.

**Two working copies on one machine share `/tmp` (TASK-45, round 56).**
The coordinator's acceptance runs in a linked worktree while the
executor works in their own; a test writing to a path built from
`tempfile.gettempdir()` is therefore shared between them. The I5
demonstration marker collided exactly this way and moved to the tree's
git directory via `git rev-parse --git-path` (`5e050a4`). Tests use
pytest's `tmp_path`, or the git directory — never a bare `/tmp` path.
TASK-48 Q2 turns this into a guard.

**On `main` the pre-commit hook is not red but inapplicable (full
check, 17.09.2026).** `core.hooksPath` points at the main checkout's
`agent/githooks`, whose selfcheck insists on `agent/p1_rule.sh` from
HEAD — and that guard exists only on the shift branch. A coordinator
commit to `main` therefore fails with `SELFCHECK FAIL (I5):
agent/p1_rule.sh нет в HEAD` regardless of its content. Until the
guards are merged to `main`, coordinator commits there are made with
the hook disabled for that one command, and the commit message says so.

**A test that fakes the door proves nothing about the door (full
check, 17.09.2026).** `tests/test_i3_chat_screen.py` drove the key «c»
with `make_intent_client` monkeypatched to a `Fake` that has `chat`,
and its neighbour asserted the **source text** contains the door's
name. Both were green while every real client the door returns lacks
`chat`. A door is checked by what its consumer calls, on the object the
door actually returns — never on a stand-in, and never by grepping the
source. The same night showed `ops` is dead for every user who has the
model key set: the door builds the client without a gate, and the
error-value is stringified into «ответ модели не JSON», which also
costs a second model call. TASK-50 T1 and T3.

**A screen is checked at a terminal size (full check, 17.09.2026).**
`curses` raises `addwstr() returned ERR` past the window edge and the
whole program dies. The card is 44 lines; 80x24 is a normal terminal.
A test calling the screen function directly cannot see this: drive
`python3 -m rusterm.cli tui` in a pty whose size is set with `ioctl
TIOCSWINSZ` (`LINES`/`COLUMNS` do not reach curses). TASK-50 T2.

**The hook hides what failed, and the guard sandboxes leak into the
real index (full check, 17.09.2026).** `agent/selfcheck.sh` writes the
acceptance output to a temp file, prints `tail -4` and deletes it, so a
red run inside the pre-commit hook says «пройдено 11, провалено 2» and
nothing else — seven twenty-minute attempts named no check. Meanwhile
git hands hooks `GIT_INDEX_FILE` and, in a linked worktree, an absolute
`GIT_DIR`: a bare `git add` inside a sandbox lands in the real index
(`pkg_pin.py` from the P1 sandbox), `tests/test_i7_p6_worktree.py`
overwrote the real `COMMIT_EDITMSG` (so declared pin replacements
vanished between preparation and commit), and the I5 module left
`agent/p6_rule.sh` modified in the tree. TASK-50 T6.

**Acceptance proves structure, not connectivity (TASK-46 N2).** Twice
now a place was built, covered by tests and never correctly called:
`make_intent_client` (TASK-27 N1) and the chat screen — `_chat_screen`
is invoked from `rusterm/tui/app.py:47` with four positional arguments
against a three-parameter signature, so pressing «c» raises
`TypeError` and the screen is unreachable, with 13/13 green. A test
that calls a screen function directly proves nothing about the key that
opens it: drive the key. TASK-47 O2 turns this into a guard.

**STATE.json moves with the report, not ahead of it (TASK-45, ruling on
Question 1).** `tests/test_report_sections.py` reads the report named in
`agent/STATE.json`; pointing it at a file that does not exist yet reds
acceptance, which then blocks the very commit that would create it.
Name the new report in the same commit that creates it. The HANDOFF
section is required in *every* commit, by design — an interim HANDOFF is
cheap and keeps a shift cut short at 03:00 readable.

**Pin replacement (TASK-32 D5).** A removed `assert` passes selfcheck only
with a `ЗАМЕНА-БУЛАВКИ:` / `ПОЧЕМУ СИЛЬНЕЕ:` block in the commit message
and no net loss of assert lines in that file — `agent/p1_rule.sh`.


1. **Free only** — ADR-0018. No paid tariff, subscription, deposit or
   card-at-registration anywhere on an obligatory route.
2. **A number in the program is either computed from stored facts or
   absent with a reason** from `rusterm/reasons.py`. A reason may carry
   a `: detail` continuation; comparison is by the first token
   (`is_known_reason`).
3. **A model never produces a number.** Every figure it states carries a
   citation; an uncited number rejects the whole answer (ADR-0016).
4. **A fact carries its locator and lineage**; `verified=no` facts are
   stored and shown but never enter a formula (ADR-0001, ADR-0011).
5. **Errors are values, not exceptions**, on every provider path.
6. **HTTP only in `providers/`, SQL only in `store/`**, providers never
   import the store (invariants I9, I10; acceptance checks 7-9).
7. **`docs/` is frozen**; a new ADR is the only permitted change
   (acceptance check 10). `agent/acceptance.sh` is never edited
   (check 12).
8. **A number about the repository is derived or absent** — no
   hand-typed test or ADR counts in README (`tests/test_docs_truth.py`).
9. **A taxonomy tag enters `concepts.py` only with the payload that
   proves it.**
10. **The single door**: `RuleClient` / `LlmApiClient` are constructed
    only inside `rusterm/core/llm.py` (`tests/test_single_door.py`).
11. **No test reads the real `~/.rusterm.env`** and no test reaches the
    network by default: `tests/conftest.py` isolates the environment,
    and anything that can make a request carries the `live` marker,
    deselected by `addopts` (TASK-29).
12. **Every network channel declares its tariff** (`open` / `free_key`
    / `paid`) and its ceiling in the provider registry; a `paid` channel
    is refused by value; `doctor` prints the freeness section; a host
    literal outside the registry fails `tests/test_free_only.py`
    (TASK-28).

## 4. Where the product actually is

| Milestone | State after TASK-46 (`agent/night-11`, not yet merged to `main`) |
|---|---|
| M1-M4 core, snapshot, watchlist | done and in use |
| M5 LLM layer | citation guard, four read-only tools, confirmed mass ops |
| M6 CA + OTC | both collected through EDGAR |
| M7 industry aggregate | done |
| M8 six markets, manual import | registry of six; US/CA/OTC collect, KR needs its key, BR/AU have providers but **no `ingest` channel** |
| M9 quotations | **real vendor rows**: AAPL 5000 daily closes 2006-10-25…2026-09-11 in one request, cached by a key-free URL, second run costs 0 requests; vendor failures named (`source_unreachable:http_403`, `vendor_rate_limited`, `source_unreachable:transport`); **the free tier sends no `adjusted`** (ADR-0019) and **`price_adj` applies dividends only** — the vendor `close` is already in today's share base (ADR-0020, three anchors); corporate actions collected from the vendor (splits + dividends) with provenance; `rusterm cadence` is a CLI command and a doctor line (TASK-31 C5); schema **45** |
| M10 industry inputs | `hhi`, physical inputs, two sectors, industry screen |
| M11 governance | producer, grey reasons, proxy through manual import; **ownership channel is live** — Forms 3/4/5 collected with provenance, golden form-4 parse, honest refusal (TASK-32 D1-D4); **`insider_net` is yellow on a real AAPL record** (10b5-1 named), DEF 14A probed and routed through manual import, colour provable at write, staleness 450 days (TASK-33) |
| M12 chat (TASK-35, 36, 42, 46) | three free models measured, default by numbers; transcripts survive the process (migration 45), export and re-verify, cost counters in `status`, no key or content leak; **the chat screen is reachable** — key «c» opens it and a test drives the key, not the function (TASK-46 N2); order vs question produces a proposal that applies nothing until confirmed, both audit rows asserted (TASK-46 N3). **I2, does-not-know, is the last open item of TASK-37** |
| M14 manual import + model | repaired in TASK-35 G5 — a tab at the cell boundary, the string law untouched: the same four tables now give **89 verified records, verified-but-wrong 0 of 89**, the footnote row stored `unverified/near_miss` with a named reason; three free models measured on the chat corpus, default `glm-5.3-flash` by numbers (G3) |
| M13 debts | single door wired, `manual_near_miss` split, selfcheck reads its count |

Data reaching a user today: **US 10 measures of 10 plus real prices; CA 3/10; OTC 3/10**
(all three through EDGAR). Everything else is a named refusal.

## 5. Keys (all free — ADR-0018)

`RUSTERM_SEC_UA` (a contact string, not a key), `RUSTERM_DART_KEY`,
`RUSTERM_TWELVEDATA_KEY` (free tier: 8/min, 800/day),
`RUSTERM_LLM_API_KEY` (OpenRouter, free models; the default model is
`glm-5.3-flash` — chosen by measurement in TASK-35 G3, not by taste).
Loaded from the
environment, else from `$RUSTERM_ENV_FILE` or `~/.rusterm.env`.
**They exist in the executor's environment from 13.09.2026.**

## 6. ADRs, one line each

0001 fact with locator and lineage · 0002 peer set (no GICS — paid) ·
0003 local app, content-addressed raw store · 0004 native desktop
(superseded in practice by 0009) · 0005 instrument identity · 0006
verification and ground truth · 0007 zstd with gzip fallback · 0008
quote vendors surveyed — **closed by 0014 and 0018** · 0009 terminal
interface · 0010 markets outside EDGAR, access levels auto/partial/manual
· 0011 manual document import, three-stage pipeline · 0012 parallel
lanes · 0013 how a market is added · 0014 Twelve Data free tier, cadence
by completeness · 0015 how a sector is added · 0016 model surface and
untrusted text · 0017 lane merge rule · 0018 **everything is free** · 0019 no vendor `adjusted` on the free tier, the correction is ours alone · 0020 **the free `close` is already split-adjusted** — never apply splits twice, dividends only (narrows 0019) · 0021 annual instead of TTM where the Q4 3-month fact is never filed; `period_basis` in lineage.

## 7. Reading order when reviewing a night (coordinator)

1. `agent/STATE.json` — status and which task the executor was on.
2. The report's **HANDOFF** block, then **Disputed** and **Blocked**.
   Not the "Done" prose.
3. `bash agent/acceptance.sh` — the run decides, never the report.
4. `git diff --stat main..<branch>` and, only for the guard files,
   `git diff main..<branch> -- tests/ | grep '^-.*assert'`.
5. This file, updated to match what the run showed.

Do **not** re-read `README.md`, `docs/` or earlier reports unless the
night changed them. Anything that needs re-checking becomes an item in
the next task, not a second reading pass.
