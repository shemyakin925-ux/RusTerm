# CONTEXT — the project in one file

Read this **instead of** re-reading `README.md`, `docs/` and old
reports. It is maintained by the coordinator and updated at every
acceptance. If it disagrees with the code, the code is right and this
file is a bug — say so in your report.

Last updated: 22.09.2026, after round 100 on `agent/night-11`.

**Round 100 (TASK-75) is accepted**, measured in a clean clone of
`f926b43`: acceptance «пройдено 11, провалено 2» where **both reds are
one test**, `test_done_items_have_code_commits_in_round` (L3); no
assert removed (`git diff e1889ee..f926b43 -- tests/ | grep -c
'^-.*assert'` → 0); `acceptance.sh`, `selfcheck.sh` and
`agent/githooks/` untouched. The desktop now shows measure history,
honest watchlist labels, a collapsed stale-input line, an executable
`rusterm add` refusal, a non-empty window without watchlists and a
worded thin-source summary; every one of the window's 21 controls is
driven by a press test.

**Two guard defects were the executor's finding and the coordinator's
fix** (they deadlocked the relay itself, since `relay.py hand` runs
acceptance and refuses on red — so neither side could pass the baton):
L3 split `git log --name-only` on a blank line, but git puts that
blank AFTER the subject, so a block's first line was a FILENAME and no
subject ever matched — the guard only ever passed through its staged
fallback, i.e. verified nothing, and went red on a clean tree. It now
splits on `%x1e`. `_sections` merged repeated identical `## HANDOFF`
headers via `setdefault`; they are now numbered, so «the last block
decides» no longer needs a unique FINAL suffix. TASK-76 W1/W2 make the
executor put teeth on both.

**Verizon is an accepted Blocked**, not a failure: the shares tag needs
the VZ payload, the round's network budget was 0, and substituting a
look-alike tag is forbidden by rule 9. Budget is granted in TASK-76 W5.

**The user's five-paper base no longer exists** — measured: `SELECT
instrument_id FROM instrument` returns only `US-AAPL`. This makes the
acceptance criteria of TASK-73 (T0) and TASK-74 (U2), which name
numbers for five papers, unrunnable. TASK-77 turns that base into a
reproducible command before those two are taken. Standing rule from
this: **an acceptance criterion may not rest on state that no command
in the repository can recreate.**

**Round 102 (TASK-76) is accepted**, verified on the branch head in a
separate worktree: «Итог: пройдено 13, провалено 0», exit 0; no assert
removed; guard scripts, hooks and `docs/` untouched. The coordinator
checked the new teeth **by mutation, not by quotation**: restoring the
blank-line split reds `test_l3_finds_the_item_by_subject_with_files_
attached`, restoring `setdefault` reds three W2 tests with `KeyError:
'HANDOFF #2'`. `FAKE_LOG` is a literal, so the guard no longer depends
on branch history.

**A guard hole the coordinator created, found by the executor:** L3
bounds nothing by round — `_git_log_name_only()` scans the whole branch,
so `\bW3\b` is satisfied by TASK-53-era commits (`d549f2a`, `892d4c1`,
`94ed9fa` — they exist). Item ids repeat across tasks, so this is a live
hole, not a theoretical one; the coordinator's round-99 claim that «the
guard now discriminates» was too broad (`Z9` was caught only because no
commit ever mentioned it). TASK-78 Y1 bounds L3 the way G4 already is.

**Verizon: the payload proved a different route, not absent data.** The
committed fixture (2.7 KB) has no `CommonStockSharesOutstanding`, but it
does carry `dei:EntityCommonStockSharesOutstanding` plus
`us-gaap:CommonStockSharesIssued` and `TreasuryStockCommonShares`. Rule
9 is therefore satisfied and extending the map is now legal — TASK-78 Y2.
`rusterm/normalize/` was untouched in round 102, as the executor said.

**Round 103 (TASK-78): Y2 accepted, Y1 returned.** Y2 is verified by
data: the three removed asserts are exactly the ones stating the OLD
behaviour (`dei_fact["canonical_concept"] is None`), assert count in the
file 18 → 40, and the route is pinned by tests for priority, «map not
widened», «dei map is only the cover-page fact» and a measured
divergence of 508 818 shares.

**Ruling: the dei route supersedes TASK-18 G4 §0.3 in part.** That rule
was about the *outcome* — `us-gaap` wins when both taxonomies carry the
tag — and the outcome is preserved and pinned. Read literally («dei never
reaches the map») it made VZ's only proven route unreachable. Not a
formula: it is a fact from the filing's cover page.

**Ruling: `РАЗРЕШЕНО ПРАВИТЬ` was mute, and that is the coordinator's
defect.** `agent/p6_rule.sh:63` greps `'^РАЗРЕШЕНО ПРАВИТЬ:'` and then
`grep -qF "РАЗРЕШЕНО ПРАВИТЬ: <path>"`: the line must start the line and
carry a bare path. TASK-75 wrote it correctly; TASK-76/77/78 wrote it as
a markdown bullet with backticks, so the permission never existed and the
executor's refusal to edit `CONTEXT.md` was correct obedience. All task
files now use the flat form; TASK-79 Z2 makes a mute permission loud.

**Y1 returned: the round bound is green for the executor and red for the
coordinator** — i.e. it fails exactly where acceptance runs. Work of round
N lies BETWEEN the markers of round N and N+1; bounding by «newer than
marker(round_no)» is right only while the baton is with the executor,
because `hand` increments the round and the new marker becomes the newest
commit, collapsing the window to nothing. This deadlocked the relay again
(`hand` runs acceptance), so as in round 101 the coordinator applied the
minimal fix: the upper bound is the marker of `round_no + 1` when it
exists, plus `_round_under_review()` (round − 1 while the coordinator
holds the baton). The executor's own teeth were untouched and all 20 pass.
Measured after the fix: `Y1,Y2 → []`, `W1,W5 → ['W1','W5']`, `W3 → ['W3']`,
`Z9 → ['Z9']`.

**Round 105 (TASK-79): Z2 accepted, Z1 returned.** Z2's guard emulates
`p6_rule.sh`'s own greps and, beyond what the task asked, covers the
comma-list case (`test_two_paths_on_one_line_leave_the_second_
unauthorized`). The coordinator independently found that exact defect in
the queue: TASK-74's `РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md, GUIDE.md` left
`GUIDE.md` mute, and TASK-73 had the same plus a continuation line. Both
task files are fixed — **one path per line**, verified with the parser's
own grep.

**Z1 returned for the disease it was written to cure.**
`test_strictness_holds_on_the_real_branch` is red on the branch head:
`_log_from_top_marker()` slices the log at the *newest* relay marker while
the test pins `round_no=104`. It was green while marker 105 was on top;
the coordinator's own `hand` put marker 106 there and the test went red
without changing. A guard tied to the position of HEAD is green for the
executor and red at acceptance — exactly the failure mode Z1 addressed.
Fixed by the coordinator (`_log_from_top_marker(log, round_no)` slices at
marker `round_no + 1`); guards run 31 passed.

**Standing rule, now third time earned: a guard may not depend on how
many rounds have passed since it was written.** Slice live history by
round number, never by head position. TASK-80 A1 puts teeth on it.

**Three deadlocks in a row have the same shape:** a red report-guard
blocks `relay.py hand` for *both* sides, so a defect in the guard stops
the relay itself and the coordinator has to fix it in place. TASK-80 A2
at least makes the refusal name the failing tests instead of the bare
phrase «приёмка красная».

**`verify` runs acceptance in a linked worktree — measured green.**
TASK-80 A3 ran `relay.py verify` on a fresh worktree at `f45e07d`: the
pytest check passed and acceptance reported 13 checks passed, 0 failed.
The claim that `test_i5_staged_and_authorised_widening_is_green` fails
*because* the tree is linked did not survive the measurement, and its
stated cause was wrong — no guard reads `.git/COMMIT_EDITMSG` as a
literal, all four take the path from `git rev-parse --git-path` (§3
corrected in the same round). What really reddens that case is an
**untracked file in the tree acceptance runs in**: the test calls
`selfcheck.sh` nested, and P3/P4 check the outer tree, so one
`?? path` line fails the assertion for a reason unrelated to the guard
being demonstrated — that is the same mechanism as the "uncommitted
coordinator files" observation measured twice this round. The verify
worktree is where it recurs: `cmd_verify` reuses one machine-global
path and refreshes it with `checkout --detach` and `reset --hard`,
which clean tracked state and leave untracked residue in place. Filed
as Disputed #3 in `agent/REPORT-80.md`.

## Measured 23.09 from the user's screenshot — two coordinator errors

**The five-paper base exists.** It lives in `/Users/anton/equitylab`
(schema 45; AAPL, ADBE, KSPI, MSFT, VALE, VZ; watchlist «Мой список»;
28 snapshots), not in the default root. Round 100's «only US-AAPL
remains» was measured against `~/.rusterm` — the default root, schema
43, a forgotten leftover. **The coordinator accepted that measurement
and built TASK-77 on it; TASK-77 is rewritten.** Standing rule earned:
**when measuring «the live base», name the directory you measured** —
the default root and the user's working catalog are different things.

Values on the real base: AAPL 40 of 56 measures valued, ADBE 40, MSFT
184 of 504, VZ 14, VALE 12, **KSPI 0**; all six registered on market
`US` (KSPI and VALE as depositary receipts).

**The user runs a branch without any of our work.** Their checkout is on
`agent/night-13`, which is missing **124 commits** of the shift branch
(merge base `5357b51`, TASK-C10). Every symptom in the screenshot — the
stale-input wall instead of one line (Д4), the «no lists» label under a
selected list (Д2), the empty history (V1) — is that branch, not a
broken fix. TASK-81 B1 brings the one night-13 commit over and makes the
shift branch fast-forwardable into `main`.

**Even on the shift branch the year columns are mostly empty.** Measured
on the real base with shift-branch code: the 2026 cell fills (20
measures, `asset_turnover` = 0.2901) while 2025/2024/2023 say «нет
данных», because every snapshot was taken in 2026 and the measure period
is June 2026. The «no empty column» rule only fires when history is
empty *entirely*. TASK-81 B2 extends it to partially empty tables.

**The `.app` is not reproducible.** TASK-C10 built `dist/EquityLab.app`
with `--windowed`, but its spec file is in `.gitignore`, so the build
exists only as a local artifact from lane-C-era code — and the user
launches `python3`, which is why a Terminal window sits beside the app.
TASK-81 B3 puts the spec in the repository.

## Round 107 (TASK-80) accepted; night shift retired; one coordinator

**TASK-80 accepted whole** — fresh clone at `f92eb92`: «Итог: пройдено
13, провалено 0», exit 0; no assert removed; guard scripts, hooks and
`docs/` untouched. A2 edited `relay.py` itself, so the coordinator checked
the gate separately: a red acceptance still stops `hand` (`if rc != 0:
die(...)`), only the refusal text changed. **A3 corrected a two-week-old
explanation:** a linked worktree does not break acceptance by itself (a
fresh `verify` at `f45e07d` is 13/0); `test_i5` reds on an *untracked file
in the tree acceptance runs in*. The coordinator had seen it red on its
own uncommitted task files and blamed the worktree — wrongly. TASK-88
fixes `verify`'s shared default path that let one run's residue poison
the next.

**No night shift, no 10:00 stop** (user, 23.09). Removed from
`CLAUDE.md`, `AGENTS.md`, `PROTOCOL.md` §10–§11 and this file. Work stops
only on `wait` exit `3`/`4` or a direct user order. The branch name
`agent/night-11` is historical and stays. `acceptance.sh` still calls
itself «приёмка ночной работы» in line 2 — left, check 12 pins it to
`main`.

**One coordinator.** A second coordinator session wrote TASK-82…87 on
this branch at 02:11 and 02:43 UTC while the baton sat with the
coordinator. The user ruled that this session leads. TASK-82…87 are kept
and queued; old task files are not rewritten (user, 23.09).

## Round 109 (TASK-81): B0–B2 accepted, B3 returned

Fresh clone at `88448c8`: «пройдено 13, провалено 0». 12 asserts removed,
legitimately — every touched test file grew (`test_desktop_data.py` 81 → 95),
each commit carries `ЗАМЕНА-БУЛАВКИ` blocks, and only assertions of the old
behaviour the task changed went away. **B1** verified by content: `git cherry`
calls `0472136` unpicked (conflicts were resolved), but all 78 lines it added
are in the working branch and `main` fast-forwards. **B2** measured on the
user's base read-only: AAPL 1 year column (was 4, three empty) 20 of 28
filled; MSFT 2026/2024/2023/2022 with the empty 2025 dropped, 47 of 112.

**B3 returned: the `.app` does not open for the user.** The coordinator built
it from `EquityLab.spec` (22 s, 167 MB) and launched it with `open`, as Finder
does: no Terminal appeared — but no window either; the process was gone in 9
s with `no such table: chat_transcript`. A Finder-launched app has no shell
environment, so no `RUSTERM_DATA`, so it opens `~/.rusterm` (schema 44), and
the read-only window crashes instead of speaking. Catalog choice is TASK-90
A4/A5; not crashing on an older schema is TASK-95. **Acceptance was 13/0 the
whole time** — the executor's own line «nobody double-clicked» named the gap.

## Round 111 (TASK-90) accepted

Fresh clone at `97673a8`: «пройдено 13, провалено 0». 10 asserts removed in
catalog-default tests that A5 changed; no file lost assertions
(`test_desktop_door.py` 18 → 19), 6 `ЗАМЕНА-БУЛАВКИ` blocks. The coordinator
checked A5 end to end without a shell: a fake HOME whose `~/.rusterm.env`
holds `RUSTERM_DATA`, `env -i`, the `.app` built from `EquityLab.spec` →
`rusterm-app root=<that dir> (правило: 2)` and the window stays alive after
10 s. `app_entry.py` and `desktop/__main__.py` call `load_env()` before
`resolve_root()`. So for the user one line in `~/.rusterm.env` —
`RUSTERM_DATA=/Users/anton/equitylab` (schema 45) — makes a double-click
open their base. An older-schema base still crashes the window: TASK-95.
Disputed (A5): `rusterm init` in a fresh directory lands in `~/.rusterm`
because rule 3 needs `./rusterm.db` that `init` is about to create — upheld
as a real gap, BACKLOG B61.

Queue order (user, 23.09 — TASK-90 right after TASK-81, TASK-91…94 at the tail): **TASK-95 → TASK-82 … TASK-87 → TASK-88 → TASK-89 → TASK-77 → TASK-73 → TASK-74 → TASK-91 → TASK-92 → TASK-93 → TASK-94 → coordinator: `agent/CLEANUP.md`** (commit everything, fast-forward `main`, delete dead branches and worktrees, prune old `agent/` files — user, 23.09; not an executor task). TASK-89 (round boundary by data, not subject; `hand` must not leak `BATON.json` into the index — the reason marker 107 is missing from history) was issued after the coordinator's own `hand` went red in round 108.

**Whole-project review, 23.09 (user's request, separate session) —
TASK-90…94.** Acceptance on `3f7dcc9` is 13/0, and every finding below
passes it; each is reproduced by a command quoted in its task. Most
urgent: Twelve Data payloads are cached under a date-less URL, so
prices never refresh — the user base's last close is 2026-09-18 and
every valuation measure goes `price_close_stale` on **2026-09-26**
(TASK-90 A1); `rusterm chat` crashes for everyone with a key (A2); the
citation guard accepts digits taken from measure UUIDs and flipped signs
(TASK-93 D1). On the user base (read-only): AAPL `roe` is
`missing_prior_period` because EDGAR dedup drops the as-reported
original (TASK-92 C1); 0 peer sets, 0 percentiles, 0 `llm_summary`
rows — pass 2 of the snapshot is called by no command (TASK-94 E2).

## Round 113 (TASK-95): F1, F2, F3 — awaiting review

**F1 — an older base speaks.** `header_info` gained `schema_notice`:
«база в <каталог> — схема 44, программе нужна 45; обновите: rusterm --root
<каталог> init», shown in a `QLabel` named `schema_notice` under the header,
`None` (hidden) on a current base. Two doors that died there — `chat_sessions`
and `llm_usage_line` — now answer `[]` and «вызовы: —» through a new store door
`db.has_table`, so SQL stays in `rusterm/store/` (acceptance check 7). The
window still does not migrate: a test builds it on the schema-44 fixture and
re-reads the version. Measured one step back, `44 → 45`.

**F2 — the double-click is a test.** `tests/test_desktop_f2_double_click.py`,
marker `firsthour` (deselected by `addopts`; `integration` runs in the normal
set and would not do): builds the bundle with the GUIDE's command into the
test's own tmp dir, launches it the way Finder does — `open -n -W`, so the
child has no terminal environment — requires the process alive after 5 s, then
closes it and asserts nothing is left. Current catalog and schema-44 catalog:
`2 passed in 50.69s`. On a bundle from `242656a` (before F1) the second case is
red with `no such table: chat_transcript` — the round-109 B3 gap now has a
tooth instead of a ritual.

**F3 — a hole in the year row is named.** `data.year_gap_note(years)` folds
«пропущен 2025 год» into the existing `history_note` line (no new door key, no
`window.py` change). ТЗ-81 B2 spoke only when columns were fewer than the
ceiling; on the MSFT shape — 2026, 2024, 2023, 2022 at a ceiling of four —
nothing was missing by that rule while the hole stayed on screen. Years below
the oldest column are the edge of the history, not a hole, so a contiguous row
is still silent.

Accepted:
TASK-31…TASK-36, **TASK-37 I5-I8**, TASK-42…TASK-58, TASK-B1, TASK-C1…C10,
TASK-60. Acceptance on the branch head in a clean clone: **13/0, exit 0**.

**Parallel lanes are over.** The three shift branches were merged into
`main` (PR #9, `36d1999`) and `main` was merged back into
`agent/night-11` (`a396a72`). Old lane branches are deleted; one lane,
one branch from here on. The lesson is recorded as a standing rule:
**one clone per session.** Linked worktrees share config, refs and the
stash — three lanes in one clone produced a real collision.

**What lane C left behind, found by TASK-60 E1:** the desktop introduced
five refusal reasons outside the closed vocabulary. The vocabulary is
the promise that a refusal is honest — TASK-61 F1 audits the desktop
against the core's own rules.

**Still blocked:** `RUSTERM_DART_KEY` is absent from the machine
(measured, round 72). Korea shows no measures; TASK-61 F4 makes that
visible instead of promising.

**Open product debt: TASK-37 I2** (does-not-know) — TASK-47 O1. I1
(question vs order) landed with TASK-46 N3, I3 and I4 are done. The
shift branch is `agent/night-11` and the turn is passed by the relay —
`agent/PROTOCOL.md` §12, driver `agent/relay.py`, baton
`agent/BATON.json`.

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
| `rusterm/desktop/` | the PySide6 window (read-only, ADR-0023); opened by `python3 -m rusterm.desktop` and `rusterm desktop` — one shared entry |
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
--git-path`. This paragraph used to claim one exception — a guard still
reading `.git/COMMIT_EDITMSG` as a literal, with an **I7** to fix it —
and measured on TASK-80 A3 (`f45e07d`, 2026-09-23) the exception is not
in the code: `agent/p6_rule.sh:75`, `agent/p1_rule.sh:36`,
`agent/p7_relay_rule.sh:25` and `agent/selfcheck.sh:59` all take the
message path from `git rev-parse --git-path COMMIT_EDITMSG`, which
resolves to the per-worktree directory. A declared `РАЗРЕШЕНИЕ-*` marker
is visible in a linked worktree: **I7** landed as
`tests/test_i7_p6_worktree.py`, and the warning above predates it.

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
is not cosmetic: the coordinator reads `updated_at` to judge whether the
executor is alive or stuck. The machine is on +07, so
the wall clock is +07 — but the stamp is written in UTC with a `Z`, so
the command is **`date -u +%Y-%m-%dT%H:%M:%SZ`** and never
`TZ=Asia/Bangkok date` (TASK-76 ruling 1 on the REPORT-75 dispute: O0
compares `updated_at` to real UTC within ±15 min, so a +07 wall clock
stamped `Z` reds it by +420 min). TASK-47 O0 makes this a guard.

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
| M8 six markets, manual import | registry of six; US/CA/OTC collect, KR honest `None`: measured 2026-09-20 — `RUSTERM_DART_KEY` is NOT in the environment despite §5 (ТЗ-58 C1 Blocked); the DART door code exists (C6), the key is the missing piece, **BR collects** (annual DFP datasets, `rusterm ingest --source cvm`, ТЗ-56 Z2; consolidated DRE/BPP -> cvm-dfp.v1 map, incremental by Last-Modified), AU has a provider but **no `ingest` channel** (`rusterm markets` shows the channel column honestly); since ТЗ-60 E4 every `rusterm markets` row and the window carry the channel's **degree** — «сырьё» / «факты» / «меры» — computed from what the channel actually produced in the catalog (raw by provider, facts by the source's provider, measures by the market's instruments), never hand-written |
| M9 quotations | **real vendor rows**: AAPL 5000 daily closes 2006-10-25…2026-09-11 in one request, cached by a key-free URL, second run costs 0 requests; vendor failures named (`source_unreachable:http_403`, `vendor_rate_limited`, `source_unreachable:transport`); **the free tier sends no `adjusted`** (ADR-0019) and **`price_adj` applies dividends only** — the vendor `close` is already in today's share base (ADR-0020, three anchors); corporate actions collected from the vendor (splits + dividends) with provenance; `rusterm cadence` is a CLI command and a doctor line (TASK-31 C5); schema **44** |
| M10 industry inputs | `hhi`, physical inputs, two sectors, industry screen |
| M11 governance | producer, grey reasons, proxy through manual import; **ownership channel is live** — Forms 3/4/5 collected with provenance, golden form-4 parse, honest refusal (TASK-32 D1-D4); **`insider_net` is yellow on a real AAPL record** (10b5-1 named), DEF 14A probed and routed through manual import, colour provable at write, staleness 450 days (TASK-33) |
| M12 chat (TASK-35, 36, 42, 46) | three free models measured, default by numbers; transcripts survive the process (migration 45), export and re-verify, cost counters in `status`, no key or content leak; **the chat screen is reachable** — key «c» opens it and a test drives the key, not the function (TASK-46 N2); order vs question produces a proposal that applies nothing until confirmed, both audit rows asserted (TASK-46 N3). **I2, does-not-know, is the last open item of TASK-37** |
| M14 manual import + model | repaired in TASK-35 G5 — a tab at the cell boundary, the string law untouched: the same four tables now give **89 verified records, verified-but-wrong 0 of 89**, the footnote row stored `unverified/near_miss` with a named reason; three free models measured on the chat corpus, default `glm-5.3-flash` by numbers (G3) |
| M13 debts | single door wired, `manual_near_miss` split, selfcheck reads its count |

Data reaching a user today: **US 10 measures of 10 plus real prices;
CA 4/10 on CNQ; OTC 7/10 on NGGTF; AAPL first-hour: 20/28 measures
valued after ТЗ-68 N1 + ТЗ-69 P1 (five measures moved into the
valuation pass per the dictionary)** (all three through EDGAR; the
TASK-49 census also measured RY 4/10, BMO 5/10, CPTP 3/10 offline).
Everything else is a named refusal with the missing concept in the
continuation (full table: `agent/REPORT-49.md`, replay offline via
`tests/test_task49_census.py`).

## 5. Keys (all free — ADR-0018)

`RUSTERM_SEC_UA` (a contact string, not a key), `RUSTERM_DART_KEY`,
`RUSTERM_TWELVEDATA_KEY` (free tier: 8/min, 800/day),
`RUSTERM_LLM_API_KEY` (OpenRouter, free models; the default model is
`glm-5.3-flash` — chosen by measurement in TASK-35 G3, not by taste).
Loaded from the
environment, else from `$RUSTERM_ENV_FILE` or `~/.rusterm.env`.
Measured 20.09.2026 via `load_env()` (ТЗ-61 F4): `RUSTERM_SEC_UA`,
`RUSTERM_LLM_API_KEY` and `RUSTERM_LLM_MODEL` and
`RUSTERM_TWELVEDATA_KEY` are present; **`RUSTERM_DART_KEY` is absent**
(Korea stays a named refusal, ТЗ-58 C1) and `RUSTERM_LLM_PROVIDER` is
absent (the measured default is used).

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
