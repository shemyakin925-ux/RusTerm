# REPORT-96 — TASK-96: reconciliation of TASK-74 and TASK-77, then the gaps

Round 121, branch `agent/night-11`, executor. Spec: `agent/TASK-96.md`
(items R0–R7; R6 and R7 are constraints, not work). Report language:
English (agent-to-agent); code comments, commit messages and `GUIDE.md`
prose are Russian per the project rule.

## Arrival state (measured before the first source edit)

* Base: `da6cb22` «Эстафета: круг 121, ход у executor — agent/TASK-96.md»,
  working tree clean (`git status --porcelain` → no output).
* Suite as it stands: `1341/1361 tests collected (20 deselected) in 3.26s`
  under the default marker filter. TASK-84 closed at `1316/1336`, so the
  coordinator's two merged branches (`fb3ac93` dei regression + `reparse`,
  `835425b` dividend yield) added 25 tests and 5 collected cases.
* The clone itself died and was rebuilt during this arrival — recorded
  because it is a fact about the working set, not a detail. `/tmp` on this
  machine was swept between the arrival measurements and the first commit
  attempt: `/tmp/rt-night11-exec`, `/tmp/rt84-staging/` and every
  `/tmp/rt84-*.log` disappeared (`ls -d /tmp/rt*` → no matches). Nothing
  committed was lost — origin already held `8e111ca` (K8) and `7e2952a`
  (the hand), verified against `git ls-remote` (`da6cb2237d43…` =
  `refs/heads/agent/night-11`) — and the clone was rebuilt with
  `git clone --branch agent/night-11` + `git config core.hooksPath
  agent/githooks`. Every number in this section was then **re-measured in
  the rebuilt clone**, so no claim below rests on a directory that is gone.
  Two consequences kept honest: (a) the log files `REPORT-84.md` cites by
  path (`/tmp/rt84-k7-teeth3.log` and the rest) no longer exist, so its
  `## Runs` rows are now re-derivable only by re-running the scripts it
  names — TASK-84 is accepted and its commits are on the branch, so no
  accepted claim of mine got weaker, but a re-checker needs to re-run;
  (b) `/tmp` is not a durable place for a round's artifacts, which is why
  the round's scratch tree now lives under `$TMPDIR`
  (`/private/var/folders/hb/…/T/`, unaffected by the sweep).
* Bookkeeping on arrival was red, for the third round in a row, in exactly
  the shape REPORT-83 entry 1 and REPORT-84 recorded:
  `agent/BATON.json` moved to round 121 / `agent/TASK-96.md` while
  `agent/STATE.json` still named the closed round
  (`task: agent/TASK-84.md`, `report: agent/REPORT-84.md`,
  `status: awaiting_review`). The guards take the round under review from
  the baton and the report path from STATE, so TASK-84's accepted items
  were screened against round 121's commits:

```
$ python3 -m pytest tests/test_report_sections.py tests/test_state_report_tracked.py
FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
AssertionError: пункты ['K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7', 'K8'] объявлены
сделанными, но коммита круга с реализацией (не только tests/) не найдено
1 failed, 28 passed in 0.47s
```

  Nothing of TASK-84 is undone — it was accepted («ТЗ-84 ПРИНЯТО целиком» in
  the baton note, coordinator's commit `080e0d0`). The consequence for the
  round is the same rule of order as in rounds 119 and 120: re-pointing
  STATE at TASK-96/REPORT-96 has to be the round's first commit, because the
  `pre-commit` hook runs acceptance and a red tree cannot pass the turn.
  Filed again as a Disputed entry with the measurement, not fixed here.
* Budgets: up to 60 live network requests for the whole spec, spent only on
  R3; every other item is network 0. LLM calls 0. The clone rebuild cost
  `git` traffic to origin (one `ls-remote`, one `clone`, later pushes) — no
  data-provider request was made for it, and the 60-request allowance is
  untouched until R3 says otherwise. P7 governs R3 and R4 in particular:
  the live run writes to a `--root` under a scratch directory, never to
  `/Users/anton/equitylab` or `~/.rusterm`; the user's base is compared
  read-only.
* Authorised by the spec (`РАЗРЕШЕНО ПРАВИТЬ`): `agent/CONTEXT.md`,
  `GUIDE.md`. Everything else keeps the usual limits; `TASK-74.md` and
  `TASK-77.md` are replaced by this spec but not edited.
* Not yet run at the moment of writing this section: the acceptance chain —
  it runs inside this commit's own `pre-commit` hook, so its verdict is
  quoted from the hook log later in `## Runs`, never predicted here.

## Done

### R0 — arrival: clone rebuilt, STATE re-pointed, this report created

Measured facts above; no product or test code touched by this commit.

### R1 — reconciliation of TASK-74 U1–U4 and TASK-77 X0–X4

Every row was checked with a command (Runs 8–17), not copied. The
coordinator's reading holds on 5 rows, is incomplete on 2 and wrong on 2;
the disagreements are Disputed 2–4 with their evidence.

| Item | Reading in `TASK-96` R1 | Verdict after checking | Evidence |
|---|---|---|---|
| 77 X0 — premise «the five-instrument base is gone» | устарел — ТЗ-81 B0 | **устарел as a premise, but not because of B0**; the *rule* X0 states is still open and is exactly R2+R3 | read-only query of `/Users/anton/equitylab`: 44 instruments, every id `US-`-prefixed, schema 45, 153 ready snapshots; all five named papers plus MSFT are present. `git show --stat 46c0c3b` (ТЗ-81 B0) → touches `agent/REPORT-81.md` and `agent/STATE.json` only: no source, no data, no market logic. The `US-` prefix comes from `rusterm add --market US` (Runs 9, the probe's own line «создан инструмент US-AAPL … тикер AAPL на US»). Nothing in the repository re-creates this base — so X0's rule («a criterion may not rest on state no command can re-create») is unsatisfied today |
| 77 X1 + 74 U1 — «one command» | «одно и то же — делается один раз, R2» | **not the same item**: R2 = 77 X1 plus three of 74 U1's four bullets | 26 subcommands, none of them a full path (`ops` classifies a natural-language request over a watchlist, `industry` reads a sector — Runs 8); `cmd_refresh` (`rusterm/cli/__init__.py:807-922`) walks filings + snapshot for a whole watchlist and never ingests prices and never searches SEC (`rusterm/core/refresh.py:116-142` — `latest_filing_date`, `fetch_companyfacts_conditional`); prices appear only in `ingest --source twelvedata`; SEC search appears only inside `add --ticker`; the probe needed 5 calls to reach a snapshot (Runs 9) |
| 74 U1's 4th bullet — «the window offers the same path by a button» | absent from the R1 table | **open, and no owner in this round** → Disputed 2 | `rusterm/desktop/window.py:875-891`: «Собрать» runs the pipeline only for `desktop_actions.demo_instrument_id()`; for any other instrument it calls `collect_synthetic`, which answers with a refusal naming a CLI command (`rusterm/desktop/actions.py:119-136`, docstring: «Синтетический провайдер служит только демо-инструменту»). `grep -n "кнопк" agent/TASK-96.md` → no match |
| 77 X2 + 74 U2 — one live run | «один живой прогон, ≤ 60 на всё, R3» | **agree on one run; R3 is narrower than U2 by two columns** → Disputed 3 | user base today: `governance_assessment` 765 rows over 44/44 instruments, `industry_aggregate` 0 rows, `price` 207 036 rows — so U2's «сколько показателей governance не серые» is measurable now and its «есть ли отрасль» is measurable as zero; R3's table (measure-count / years / requests) asks for neither |
| 77 X3 — offline reference base | открыт — R3 | **open, but its tooling already exists** | `tools/trim_companyfacts.py` plus `tests/test_trim_tool.py`; `RequestGate` in `rusterm/providers/budget.py`; 256 KB cap enforced by `tests/test_payload_size.py`; fixtures: 25 `companyfacts_*.json` (20 `m3`, 5 `m6`) + `company_tickers.json` + `submissions_aapl.json`, but prices exist only for AAPL (`tests/data/twelvedata/` = 5 files) → 5 of the 6 papers need new price fixtures |
| 77 X4 — which run measures which criterion | заменён этой таблицей | **agree** | this section; the T0/U2 criteria that name papers are answered by the rows above (offline = R3's replay, live = R3's run) |
| 74 U3 — first hour per tab | частично — R4 | **agree, with the exact gap named** | `tests/test_task65_k4_firsthour.py` asserts `len(measures) == 28`, `used >= 1` and six timings; the window appears as one `desktop` call under `RUSTERM_APP_SMOKE=1`, so no tab content is checked; the tab set is 4 (`window.py:223,257,274,297` — Компания, Отрасль, Качество, Настройки) → R4 covers 2 by content, 2 by `xfail(strict=True)` |
| 74 U4 — «первые пятнадцать минут» in GUIDE | открыт — R5 | **agree** | `grep -n "^#{1,3} " GUIDE.md` → 12 sections, no such heading; `test_guide_truth` executes every unmarked ```console block (17 today) and pins the marked set by `test_marked_blocks_are_interactive`, so a new block is either executed offline by the guard or has to be added to that pinned list — R5 plans for this |
| R0's «сделано» rows (ТЗ-90 A5, ТЗ-81 B2, ТЗ-95 F3/F1, «тест первого часа частично») | сделано | **confirmed, each named by a commit that touches source and tests** | `0508b7f` A5, `d479eb8` B2, `02ca7a4` F3, `50c8bb9` F1 — `git show --stat` on each lists `rusterm/…` files, not only `agent/` |
| R0's «одна команда полного пути — нет; есть census, но census --rebuild портит данные» | нет / не строить | **confirmed, and the damage measured offline** | see the probe below: `census --rebuild` writes a second snapshot that becomes the latest one, and the price-fed measures of that snapshot lose their values |

Probe for the last row — offline (stub transport from
`tests/test_task65_k4_firsthour.py`, network 0, `--root` under `$TMPDIR`,
`RUSTERM_ENV_FILE` pointed at a nonexistent file so the user's env file is
never read), base built by 5 CLI calls:

| Step | Measures | With a value | Snapshots in the base |
|---|---|---|---|
| after `snapshot --instrument US-AAPL --as-of 2026-04-22` | 28 | **11** | 1 |
| after `census --instrument US-AAPL --rebuild --as-of 2026-04-22` | 28 | **10** | 2 |

`div_yield` went from `0.0038071529155048905` to a refusal, and 12 further
price-fed concepts changed their refusal reason from
`missing_data: price_close_stale:2026-09-11` to the bare
`missing_data: price_close` — the same run made the degraded snapshot the
latest one, so `export`/`show` now read it. Cause, read from the code: the
census builder is constructed without the price repo
(`rusterm/cli/__init__.py:1651-1655` — `SnapshotBuilder(repos.snapshot,
repos.peer_set, coverage_repo=repos.coverage)`), while `refresh`
(`:844-859`) and `snapshot` (`:937-950`) pass `price_repo`,
`corp_action_repo`, `industry` and `governance`. So ТЗ-94 E1's claim is
real, and R2's «не построен на census --rebuild» is satisfied by building
the command on the same full builder the two write commands use, not on
census.

The probe script itself is scratch under `$TMPDIR` and is not committed: R3
replaces it with a committed offline test, and the two tables above are its
whole output.

## Blocked

none

## What not to trust

* The R1 table checked the coordinator's reading item by item (Runs 8–17);
  three rows are called out as wrong or incomplete in Disputed 2–4. What is
  *not* checked by that table is anything about the new command (R2), the
  live run (R3), the first-hour tabs (R4) or `GUIDE.md` (R5): no number for
  those exists yet, and none is quoted here.
* R1's census probe runs against a base whose recorded prices end 2026-04-21
  (the AAPL fixture), so the measured damage is one lost value plus twelve
  less specific refusal reasons. On the user's base, where prices are fresh,
  the same code path has 12 price-fed concepts to lose — that extrapolation
  is read from the code (`cli:1651-1655` vs `cli:844-859`), not measured, and
  it will not be measured by writing anywhere near the user's data (P7).
* Round 119's scratch evidence is gone with the swept `/tmp`
  (`/tmp/rt84-staging/*.py|*.sh`, `/tmp/rt84-*.log`). What survives is what
  was pushed: the tests in `tests/test_concurrency.py`, the three product
  fixes, and the quoted outputs in `REPORT-84.md`. Treat a report row that
  cites a `/tmp/rt84-*` path as "re-run to see it", not "open this file".

## Disputed

1. Third recurrence of the same bookkeeping gap, so it is a rule of the
   protocol rather than an accident: `relay.py hand` moves
   `agent/BATON.json` (round, holder, task, report) and leaves
   `agent/STATE.json` pointing at the round that was just accepted, so
   between the coordinator's hand and the executor's first commit the tree
   is red for its own guard — measured this round:
   `1 failed, 28 passed`, the failure naming TASK-84's `K1…K8` as missing
   implementation commits in round 121. Two of the three recurrences cost a
   full ~14-minute hook run to discover. Ask: should `cmd_hand` stamp
   STATE's `task`/`report`/`status` from the baton it is already writing
   (it has both paths as `--task`/`--report` arguments), so the pair moves
   as one? Not fixed here: `agent/relay.py` is not in this spec's
   `РАЗРЕШЕНО ПРАВИТЬ` list, and the executor's alternative — editing STATE
   during the coordinator's own commit — is exactly what relay's
   «в индексе лежит чужое» guard refuses.

2. Merging ТЗ-74 into this spec dropped one of U1's four bullets without
   naming a new owner for it: «окно предлагает этот же путь кнопкой для
   бумаги, у которой чего-то не хватает» (`agent/TASK-74.md:39`). R2's
   Done-when has no line about the window, and `grep -n "кнопк"
   agent/TASK-96.md` returns nothing. Measured today: the window does have
   a «Собрать» button, and it refuses for every instrument except the demo
   one — `rusterm/desktop/window.py:875-891` calls
   `desktop_actions.collect_synthetic`, whose docstring at
   `rusterm/desktop/actions.py:129-131` says the synthetic provider serves
   only the demo instrument and any other instrument is answered «словами и
   называет команду CLI». So the criterion is neither done nor assigned.
   Ask: add it to R2 (a small, testable change in one handler) or move it
   to ТЗ-73, whose stages the button would have to reach anyway. Not
   implemented here: an item absent from my Done-when list, in desktop
   code, is the coordinator's call, and a round must not grow criteria
   silently.

3. R2's line «отрасль и governance в этот путь не входят — это ТЗ-73» is
   true for отрасль and untrue for governance, and the difference is
   measurable. Governance assessments are not a separate collection stage:
   they are produced *inside* the snapshot builder from facts already in
   the base — `rusterm/cli/__init__.py:850-859` passes
   `governance=lambda iid, issuer: produce_assessments(...)` to
   `SnapshotBuilder`, and the user's base holds 765 `governance_assessment`
   rows across 44/44 instruments while `industry_aggregate` has 0 rows
   (read-only queries, Runs 13). So any R2 that builds a snapshot with the
   same full builder the write commands use — which the census probe says
   it must — produces governance rows as a side effect. Consequence: R3
   reports what the run actually wrote, including governance, instead of
   the words «эта стадия ещё не собрана»; and ТЗ-73's ownership of
   governance should be read as «починка и наполнение отраслью», not «первое
   появление governance». Ask: confirm the wording before a user is told a
   stage is missing that the same command just filled.

4. The fact row in R0 describes the user's base as «шесть бумаг AAPL ADBE
   KSPI MSFT VALE VZ» with the citation «ТЗ-81 B0». Measured read-only: 44
   instruments, schema 45, every id `US-`-prefixed; the six are a subset,
   and the coordinator's own commit `835425b` is titled «1 -> 24 бумага из
   44». `git show --stat 46c0c3b` (ТЗ-81 B0) lists only `agent/REPORT-81.md`
   and `agent/STATE.json`, so it is not the commit that placed anything on a
   market — the `US-` prefix comes from `rusterm add --market US`. This is
   not cosmetic: R3's budget is stated per paper, so R3 will name its own
   count (six chosen papers) instead of repeating «the user's base is six».

## Runs

| # | command | output |
|---|---|---|
| 1 | `git log --oneline -1`, `git status --porcelain` (arrival) | `da6cb22 Эстафета: круг 121, ход у executor — agent/TASK-96.md`, tree clean |
| 2 | the same pair, in the rebuilt clone | identical: `da6cb22`, no output |
| 3 | `ls -d /tmp/rt-night11-exec /private/tmp/rt-night11-exec`; `ls -1 /tmp` | `No such file or directory` for both; `/tmp` holds only `YoM2Q9 cc-socks claude-501 com.kaspersky.kav.autoupdater.plist kav_downloader.log klinstalltype powerlog` — the round's scratch tree is gone |
| 4 | `git ls-remote https://github.com/shemyakin925-ux/RusTerm.git agent/night-11 main` | `da6cb2237d43b91857f58a5562310185636b07cd refs/heads/agent/night-11`, `36d1999… refs/heads/main` — nothing committed was lost |
| 5 | `git clone --branch agent/night-11 … rt-night11-exec`, `git config core.hooksPath agent/githooks` | clone at `da6cb22`, `git status --porcelain` empty, hooks path printed back as `agent/githooks` |
| 6 | `python3 -m pytest --collect-only` (rebuilt clone) | `1341/1361 tests collected (20 deselected) in 3.26s` |
| 7 | `python3 -m pytest tests/test_report_sections.py tests/test_state_report_tracked.py` (rebuilt clone, STATE still on TASK-84) | `1 failed, 28 passed in 0.40s` — `пункты ['K1'…'K8'] … коммита круга с реализацией … не найдено`, i.e. the arrival red reproduced verbatim in the new clone |
| 8 | `python3 -m rusterm.cli --help` (offline, no catalog opened) | `{init,ingest,demo,add,snapshot,export,verify,doctor,backup,restore,status,watchlist,coverage,metrics,budget,tui,desktop,refresh,ops,import,chat,reparse,cadence,census,markets,industry}` — 26 commands, no full path among them; `ops --help` → `--watchlist/--request/--confirm` (bulk watchlist operation, `cmd_ops` at `cli:1125-1143` classifies a natural-language request through `make_intent_client`), `industry --help` → `--sector/--as-of` (a read view) |
| 9 | offline probe: `init` → `add --ticker AAPL --market US` → `ingest --source edgar` → `ingest --source twelvedata` → `snapshot --instrument US-AAPL`, `--root` under `$TMPDIR`, transport stubbed by `tests/test_task65_k4_firsthour.py::_write_stub`, `RUSTERM_ENV_FILE=/nonexistent/…` | `rc=0` on all five; `создан инструмент US-AAPL (эмитент Apple Inc., CIK 320193, тикер AAPL на US, площадка unknown)`; `фактов: 206`; `запросов: 2`; `мер: 28 — со значением 10, пусто 18; перцентилей: 0` — the full path is five calls today, network 0 |
| 10 | same base: `snapshot --as-of 2026-04-22`, then `census --instrument US-AAPL --rebuild --as-of 2026-04-22`, `export --format json` between them | 28 measures, **11 with a value** → after census **10 with a value**, snapshots 1 → 2; `div_yield 0.0038071529155048905` → refusal; 12 price-fed concepts' reason degraded from `missing_data: price_close_stale:2026-09-11` to `missing_data: price_close` |
| 11 | `git show --stat 46c0c3b` (ТЗ-81 B0, cited in R0's fact table) | two files: `agent/REPORT-81.md`, `agent/STATE.json` — no source, no data |
| 12 | `git log --oneline --grep` for the cited rows + `git show --stat` on each | A5 `0508b7f`, B2 `d479eb8`, F3 `02ca7a4`, F1 `50c8bb9`; each lists `rusterm/…` and `tests/…` files; all three coordinator branches (`fd40f7a`, `835425b`, `a258537`) are ancestors of HEAD (`git merge-base --is-ancestor` → «в HEAD» for each) |
| 13 | `sqlite3 "file:/Users/anton/equitylab/rusterm.db?mode=ro"` counts | schema 45; `instrument` 44, all prefixes `US` (one row `US\|44`); ready snapshots 153; `measure` 4284 rows, 1772 with a value; `price` 207 036; `governance_assessment` 765 rows / 44 distinct instruments; `industry_aggregate` 0; `peer_set`, `peer_set_version`, `peer_set_member` 0 — write door never opened, `mode=ro` in every URI (P7) |
| 14 | `grep -n "кнопк" agent/TASK-96.md`; `grep -n "кнопк" agent/TASK-74.md` | TASK-96: no match; TASK-74: `39:- окно предлагает этот же путь кнопкой …` |
| 15 | `sed -n '875,900p' rusterm/desktop/window.py`; `grep -n "def collect_synthetic" -A 12 rusterm/desktop/actions.py` | the button returns `collect_status.setText(f"сбор не удался: {outcome.detail}")` for every non-demo instrument; the action's docstring names the refusal as deliberate («реальные источники — Disputed, тела заперты в CLI») |
| 16 | fixture inventory `ls tests/data/edgar tests/data/twelvedata` | `tests/data/edgar`: 30 json files — 20 `companyfacts_m3_*.json`, 5 `companyfacts_m6_*.json` (BMO/CNQ/CPTP/NGGTF/RY), `company_tickers.json`, `submissions_aapl.json`, `companyfacts_vz_shares.json`, `m3_manifest.json`, plus an `ownership/` dir of Form 3/4/5 XML; `tests/data/twelvedata`: 5 files, all AAPL (`dividends_AAPL_full`, `splits_AAPL_full`, three `time_series_AAPL_*`) — no price fixture for the other five papers |
| 17 | `grep -rn "262144\|256 \* 1024" tests/*.py`; `head -30 tests/test_no_shared_tmp.py` | the 256 KB cap is a guard (`tests/test_payload_size.py::MAX_PAYLOAD_BYTES = 256 * 1024`), not a promise; `tests/test_no_shared_tmp.py` exists and reddens writes to a shared `/tmp` path not built from `tmp_path` |

## HANDOFF

 interim block, rewritten at the close of the round.

Status so far: arrival only. Round 121, spec TASK-96, items R1–R5 open.
One environment event: the working clone under `/tmp` was swept and rebuilt
from origin before the first commit; every arrival number above was
re-measured after the rebuild. Nothing is claimed accepted that has not
been run.
