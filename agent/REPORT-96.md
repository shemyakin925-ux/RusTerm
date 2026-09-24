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

### R2 — `rusterm follow`: one call walks the paper to a snapshot

**The command.** `rusterm follow TICKER [--market US]`
(`rusterm/cli/__init__.py`, `cmd_follow`) runs five stages in one process:
`init` → `add --ticker/--market` (the SEC search) → `ingest --source edgar`
→ `ingest --source twelvedata` → `snapshot --instrument`. Each stage prints
one line with its own measured request count; the count is a difference of
the DB counter (`_requests_used`, the same arithmetic as `rusterm budget`),
not a number the stage claims about itself. On a failed stage the command
stops, prints the same stage as an executable line
(`совет: rusterm ingest --source edgar --instrument US-AAPL`) and returns
that stage's exit code — the advice is the command that was just run, so it
cannot drift from the parser. The subcommand list is 27 now (`follow` added
to the 26 counted at arrival, Run 8).

| Requirement | How it holds |
|---|---|
| stage numbers are real | measured from `metric_sample` before/after each stage; the new test counts the transport calls and asserts the DB total equals them (6 = 6, Run 20) |
| idempotent, second run clearly cheaper | **6 requests the first time, 1 the second** (Run 19). The repeat skips the SEC search outright (`_instrument_exists` reads the catalog, so `add`'s unavoidable ticker-map request never happens), the price payloads hit the dated-URL cache (0), and the report stage still pays its single `companyfacts` check. Values unchanged: the test compares every `concept → (value, null_reason)` of the latest snapshot before and after, and the second run prints «без изменений — значения идентичны предыдущей версии» |
| not built on `census --rebuild` | stage 5 calls `cmd_snapshot`, i.e. the full builder `refresh` and `snapshot` use (`price_repo`, `corp_action_repo`, `industry`, `governance`); census is untouched |
| the ТЗ-94 damage does not apply | `test_price_fed_measures_are_not_census_style_refusals` seeds prices, builds the snapshot through `follow`, and fails if `market_cap`/`div_yield`/`pe` carries the bare `missing_data: price_close` refusal that is census's fingerprint (R1's probe produced 12 of them). Prices are in the base and the reason is not census's — the builder got the price repo |
| industry and governance stay out | not in the stage list; the last line says it in words («отрасль и governance в этот путь не входят…») and names `rusterm industry` / `rusterm coverage` |
| unknown market | refused before any write: `test_unknown_market_is_refused_before_any_write` asserts `rusterm.db` does not exist afterwards |

**Two accounting defects found by measuring, both fixed in this commit.**
They are the reason the stage numbers were not trustworthy before:

1. `_ingest_twelvedata_prices` / `_ingest_twelvedata_actions` built a
   `RequestGate` and never recorded it — the price stage of a live path
   spent 3 vendor requests while the DB counter, `rusterm budget` and
   `rusterm status` said 0. `_record_gate_usage`'s own docstring states the
   rule («один хелпер для всякого пути через RequestGate»); the price path
   was the one that skipped it. An injected provider (tests, the desktop)
   leaves the local gate `None`, so no sample is invented for requests this
   command did not make.
2. `cmd_add` recorded its gate immediately after `resolve()`, before
   `can_auto_ingest()` and `ticker_venues()` — the latter is a second SEC
   request (`company_tickers_exchange.json`). `add` reported 1 where 2
   happened. The recording moved to the command's exits, one per path.

Before the fix the same offline path printed `(запросов 0)` for a stage that
had just made three live calls, and reported `5` from a base that had seen
6. The printed total now equals the counted transport calls.

**Tests.** `tests/test_task96_r2_follow.py`, 6 tests, all offline: the
providers are the real classes with a transport over `tests/data`, and the
`_no_network_in_default_run` guard reddens any real socket. Coverage: the
five stage lines and their order; the idempotence pair above; the census
fingerprint; every `совет:` line parsed back through `_build_parser()`;
unknown market refusing to write; the counted-calls equality.

Commit: `eaf3899` (hook: 13 acceptance checks passed, 0 failed).

### R3 — the live run over six papers, and the offline reference built from it

**The live run.** Six `rusterm follow` invocations, one per paper, into
`$TMPDIR/rt96-r3/live` with an explicit `--root` (P7: the user's base was
opened `mode=ro` for the comparison rows and never written). The six logs are
Runs 24.

| Paper | How far the path got | Measures with a value | Years of price history | Requests out / named by the base |
|---|---|---|---|---|
| AAPL | stages 1–5, snapshot v1 | **21 / 28** | 21 (2006-11-06 … 2026-09-23, 5000 rows) | 6 / 6 |
| ADBE | 1–4, aborted at corp actions | **20 / 28** | 21 (5000 rows) | 5 / 4 |
| KSPI | 1–4, aborted | **2 / 28** | 3 (2024-01-19 …, 672 rows) | 5 / 4 |
| MSFT | 1–4, aborted | **22 / 28** | 21 (5000 rows) | 5 / 4 |
| VALE | 1–4, aborted | **17 / 28** | 21 (5000 rows) | 5 / 4 |
| VZ | 1–4, aborted | **16 / 28** | 21 (5000 rows) | 5 / 4 |

Prices landed in all six rows — stage 4 wrote 5000 (KSPI: 672) quote rows and
*then* the optional corp-actions call failed — so five of the six papers were
complete enough for a snapshot; `follow` itself built only one. The other five
`мер со значением` numbers come from a snapshot built afterwards by
`rusterm snapshot --instrument …` in the same catalog, i.e. the very builder
stage 5 calls, and that five-command run moved the request counter
26 → 26, delta 0 (Runs 25, 26). That `follow` built one snapshot of six is the
behaviour named as entry 5 of the list below.

**Spend.** 31 requests out: 18 to SEC (2 ticker-map + 1 `companyfacts` per
paper) and 13 to TwelveData (6 quotes, AAPL's 2 actions, 5 refused `/splits`).
The base's own counter names 26 — that gap is the third accounting defect
below, and it is why the aborted rows print `(запросов 4)`. Diagnostics after
the run: 8 more (Runs 30–32). **39 of the 60 the spec allows**, R4 and R5 need
none.

**Where it stopped, and why the run cannot be repeated today.** Both ends are
the vendor's, and both are measured rather than assumed:

* `/splits` and `/dividends` answer 403 with the plan named in words:
  `/splits is available exclusively with grow or pro or ultra or venture or
  enterprise plans.` — while AAPL's own two calls had succeeded forty minutes
  earlier (88 actions are in the base, Run 24). The gate is the vendor's, and
  it is not stable across one evening.
* ~40 minutes after the run the *key itself* began to be refused on
  `/time_series`: `{"code":401,"message":"**apikey** parameter is incorrect or
  not specified…"}` — for the exact URL shape the run used
  (`time_series?symbol=AAPL&interval=1day&outputsize=5000&end_date=2026-09-24`,
  which had returned 5000 rows) and for a minimal one (Runs 31, 32).

Consequence, stated plainly: the table above is one evening's record, and a
`follow` on this key today fails at stage 4 with `http_401` where it failed
with `http_403` last night. What carries R3's Done-when now is the offline
reference below.

**The same numbers from the user's base, read-only, differences explained by
source.** Latest snapshot per paper, `percentile` rows excluded (only a base
with a peer set has them: 8–12 per snapshot in the user's base, 0 in the run —
Runs 27, 28).

| Paper | Run | User's base | Concepts that differ | Source of the difference |
|---|---|---|---|---|
| AAPL | 21 | 21 | none | the run wrote 86 `dei:*` facts the base does not have; AAPL already had `us-gaap:CommonStockSharesOutstanding` to 2026-06-27, so no measure moved |
| ADBE | 20 | 21 | `roe` | the run's filing is *newer* (15368 facts vs 15102) and the new period has no pair: `missing_prior_period` |
| KSPI | 2 | 0 | `market_cap`, `market_cap_total` | base reason `missing_data: shares_outstanding`; the base has **0 rows on both** shares tags, the run parsed 3 `dei:` rows out of the same payload |
| MSFT | 22 | 22 | none | as AAPL |
| VALE | 17 | 7 | 10: `ev, ev_ebitda, fcf_yield, market_cap, market_cap_total, net_debt, net_debt_ebitda, pb, pe, ps` | foreign issuer (6-K/20-F): the cover `dei:` fact is the only shares source, and the base has none of it (17 `dei:*` rows in the run) |
| VZ | 16 | 8 | 8: `ev, ev_ebitda, market_cap, market_cap_total, net_debt, net_debt_ebitda, pe, ps` | same cause: `missing_data: shares_outstanding` in the base, 87 `dei:*` rows in the run |

The pattern is a date, not a code path: 37 of the user's 44 issuers *do* carry
`dei:*` facts and every one of those rows was ingested 2026-09-24 05:30–05:45,
i.e. after the coordinator's `fd40f7a`; the 7 issuers with no `dei:*` at all
include exactly this round's six papers, last ingested 2026-09-21
04:25–05:39 (Runs 33). The payloads themselves are in the base and
byte-identical to the run's — VZ `raw_object.sha256`
`69e11989…082ed1` / 345682 bytes in both, AAPL `4ac7958f…53496` — so this is a
parse-time loss that no command today can undo: `ingest` skips the object
because its sha is already in the store (`cli:486-488`) and `reparse` rewrites
only `basis` (`cmd_reparse`, `cli:1566-1586`, «меняется только basis»). Filed
as Disputed 6: a data-recovery gap, not a criterion of this spec.

**The offline reference.** 12 fixtures committed under `tests/data/` — the
run's own responses, cut with `tools/trim_companyfacts.trim` plus the `dei`
section and, for the two foreign issuers, `ifrs-full` through the same rules.
Largest 121 KB, all ≤ 256 KB, each pinned by sha256 inside the test, so they
are a recording and not something a test regenerates; a secrets scan over
every byte of all twelve is one of the tests.

`tests/test_task96_r3_replay.py` (4 tests): the catalog is seeded offline with
`add --cik/--name` and asserted at 0 requests; then each paper goes through the
real post-response doors (`CompanyFactsParser` → `apply_concept_map` →
`persist_ingestion_results`; `_ingest_twelvedata_prices` over a `RequestGate`
whose transport raises if it is ever called) and a real `rusterm snapshot`.
Pinned numbers, with `gate.calls_made == 0` per paper and the DB counter at 0
at the end:

| Paper | Facts | Fact years | Price rows | Price years | Measures with a value |
|---|---|---|---|---|---|
| AAPL | 230 | 20 | 1000 | 5 | 23 |
| ADBE | 191 | 19 | 1000 | 5 | 22 |
| KSPI | 3 | 3 | 672 | 3 | 2 |
| MSFT | 217 | 18 | 1000 | 5 | 23 |
| VALE | 5 | 2 | 1000 | 5 | 2 |
| VZ | 181 | 20 | 1000 | 5 | 17 |

Read that as *the same path*, not *the same base*: trim keeps six fresh periods
per tag/unit and one taxonomy, and the price fixture holds 1000 of the run's
5000 days. That is why VALE is 2 here and 17 live (its 4712 facts trim to 5),
and it is why the live table is printed with its own numbers instead of being
replaced by the reference. `test_dei_input_survives_the_trim` keeps the one
input the finding rests on (`dei:EntityCommonStockSharesOutstanding` →
`market_cap` → `ev`/`pe`/`ps`) inside VZ's trimmed file, so the reference cannot
silently stop covering it.

**Third accounting defect, found by measuring and fixed.** A refused call
through a `RequestGate` was invisible to `budget`: both TwelveData doors
returned on `ProviderError` *before* `_record_gate_usage`, so the five aborted
`/splits` calls of the run above are in the vendor's log and not in ours —
`rusterm budget` reads 26 for a base that spent 31. Both doors now record on
the refusal exit. `tests/test_task96_r3_refused_calls.py` (3 tests) pins
refused splits (2 transport calls, counter 2), refused dividends after
successful splits (3 calls, counter 3 — no double count from a cumulative
gate), and a refused quote through the price door (counter 1).

**Done-when, line by line.** Live run over six papers in a `/tmp` catalog:
done. ≤ 60 requests: 39 spent. Table бумага → меры со значением → лет истории →
запросов: done, with both the counted and the recorded request numbers. Same
numbers from the user's base read-only, differences explained by source: done
(the `dei` / `shares_outstanding` mechanism above). Responses as fixtures
≤ 256 KB via `trim_companyfacts`: done. Offline replay "rebuilding the same
base": **partially — it rebuilds the same code path over reduced payloads, and
the reduction is visible in VALE's 2 vs 17**. Zero requests proven by the
`RequestGate` counter: done (7 tests green, Run 34; adjacent suites 17 and 36
green, Runs 35, 36).

## Blocked

* **TwelveData free key: the corp-actions half of the price stage, and as of
  22:20 the quotes too.** `/splits` and `/dividends` answer 403 «available
  exclusively with grow or pro or ultra or venture or enterprise plans», and
  ~40 minutes after the six-paper run the same key began to answer 401
  «**apikey** parameter is incorrect or not specified» for `/time_series` in
  the exact shape that had returned 5000 rows. Nothing in the code can be
  finished against that: R3's live table is closed at six papers, the
  reference is offline, and the corp-actions path is exercised offline only by
  the pre-existing fixtures (`tests/data/twelvedata/{splits,dividends}_AAPL_full`).
  What the coordinator needs to decide: whether the project buys a plan that
  has these endpoints, or drops the claim that `follow` collects corporate
  actions. Spending more of the 60 will not tell us anything Runs 30–32 do not
  already say.

## What not to trust

* The R1 table checked the coordinator's reading item by item (Runs 8–17);
  three rows are called out as wrong or incomplete in Disputed 2–4. What is
  *not* checked by that table is anything about the new command (R2), the
  live run (R3), the first-hour tabs (R4) or `GUIDE.md` (R5): no number for
  those exists yet, and none is quoted here. (R2 does have its own numbers,
  in its section below; this sentence is about what the *table* checked.)
* R1's census probe runs against a base whose recorded prices end 2026-04-21
  (the AAPL fixture), so the measured damage is one lost value plus twelve
  less specific refusal reasons. On the user's base, where prices are fresh,
  the same code path has 12 price-fed concepts to lose — that extrapolation
  is read from the code (`cli:1651-1655` vs `cli:844-859`), not measured, and
  it will not be measured by writing anywhere near the user's data (P7).
* Every R2 number is an **offline** number: the transport is stubbed from
  `tests/data`, so 6/1 (run 1 / repeat) is what the path costs on the AAPL
  fixture, not what it will cost on a live paper. A live `follow` is R3's
  job and nothing in this commit has been run against a vendor. Expect the
  live repeat to be *more* than 1 request per paper if a new filing has
  arrived since (`_ingest_edgar_companyfacts` always pays one request to
  find that out, and `add`'s skip is mine, not the vendor's).
* The two accounting fixes change what `rusterm budget` names from now on;
  they do not back-fill history. The user's own base recorded 44 instruments
  of `add` runs and every price ingest of the last ten rounds without the
  requests those stages really made, so the numbers in earlier reports
  (including `REPORT-90`'s) are floors, not counts. Nothing in this round
  rewrites that base (P7: read-only).
* Round 119's scratch evidence is gone with the swept `/tmp`
  (`/tmp/rt84-staging/*.py|*.sh`, `/tmp/rt84-*.log`). What survives is what
  was pushed: the tests in `tests/test_concurrency.py`, the three product
  fixes, and the quoted outputs in `REPORT-84.md`. Treat a report row that
  cites a `/tmp/rt84-*` path as "re-run to see it", not "open this file".
* R3's live table is **not reproducible**: it was one evening on one key, and
  the vendor closed both endpoints (Blocked). The six logs and the run's catalog
  live under `$TMPDIR/rt96-r3/`, which is as disposable as the `/tmp` that ate
  round 119's scratch; what is durable is the fixtures and the 7 tests. If a
  re-checker needs the live numbers again, they cost requests and today they
  would come back as 401/403.
* The offline reference is *a* reference, not *the* base: trimmed fundamentals
  (230 facts for AAPL where the run wrote 12452) and 1000 of 5000 price days.
  The pinned per-paper numbers are only comparable with themselves; the live
  column of the comparison table is the one that describes a real base. VALE's
  2-vs-17 difference is the fixture rule, not a defect in the formulas.
* The `dei` finding is a statement about **the user's base as it stands**
  (7 issuers with no `dei:*`, six of them this round's papers, payloads
  byte-identical to the run's). It is read from a `mode=ro` connection plus the
  source of `ingest`/`reparse`; it was not verified by *fixing* anything,
  because fixing it means writing to the user's data (P7 forbids that here).
* 39 of 60 requests are spent and the accounting fixes record only what happens
  after them: the 5 refused calls of this run are still missing from that base's
  counter (26 vs 31 out). `rusterm budget` is now right going forward, not
  retroactive.

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
   not cosmetic: R3's budget is stated per paper, so R3 named its own count
   (six chosen papers, 31 requests out of them) instead of repeating «the
   user's base is six».

5. `follow` treats a refusal from an *optional, plan-gated* endpoint as the
   failure of the whole price stage, and the live run measured what that costs:
   five of six papers wrote their quotes (5000 rows, KSPI 672) and then the
   command stopped with rc=1 and no snapshot, because `/splits` answered 403
   (Run 24). The printed advice — `совет: rusterm ingest --source twelvedata
   --instrument US-ADBE` — leads the user to the same wall: successful payloads
   are the only thing cached under the canonical URL, so a retry re-pays the
   `/splits` request and gets the same plan message (Runs 30), deterministically,
   as long as the key is on this plan. Two of R2's accepted properties are in
   tension here: «стадия не прошла → стоп, дальше не идём» and «цены —
   обязательная часть пути». Ask: when quotes landed and only corporate actions
   failed, say so in words, count the stage as passed, and let stage 5 build the
   snapshot (the numbers above show the snapshot is meaningful without actions:
   VZ 16 measures with a value, KSPI 2); or keep the abort and print
   «решение вендора, не данные» instead of a retry command that cannot succeed.
   Not implemented in R3: R2 is accepted with the current behaviour, the fix is
   a product decision about what a stage means, and changing it silently in the
   round that measures it would make this table describe a command that no
   longer exists.

6. Facts that the *current* parser would produce from an *already stored*
   payload cannot be recovered by any command in the tree. Measured on the
   user's base, read-only: 7 issuers have no `dei:*` facts at all (six of them
   are this round's papers, last ingested 2026-09-21), while their stored
   `companyfacts` payloads are byte-identical to the ones the live run parsed
   into 3–135 `dei:*` rows each (Run 33). The two candidate doors both miss it:
   `ingest --source edgar` short-circuits on `repos.raw.has(sha)` with «уже в
   store — пропущено» and returns 0 (`cli:486-488`), and `reparse` — the command
   this round's `fd40f7a` added precisely for a parser fix — recomputes `basis`
   only (`cli:1566-1586`). So the coordinator's own «данные (новая команда
   `rusterm reparse`)» recovery route does not reach the class of loss its
   parser fix created: 54 measures in the user's base refuse with
   `missing_data: shares_outstanding` for exactly this reason, and a user who
   re-runs every documented command keeps them empty. Ask: either extend
   `reparse` to re-persist facts from the raw store (0 requests, same doors
   `ingest` calls after a response), or record in `GUIDE.md` that a parser fix
   needs `ingest --force` and name that command. Related to ТЗ-92 `C1`, which
   R6 assigns to me in the same parser file — the two should be decided
   together, and this round deliberately touched neither (P7: the fix would
   have to be run against the user's base to prove anything). Not a re-opening
   of ТЗ-76 W5 («`us-gaap:CommonStockSharesOutstanding` отсутствует у VZ, карту
   не расширяем», `REPORT-76.md:227-245`): the `dei.v1` map that came later
   does answer that input, which is exactly why a base that never re-parsed is
   now the odd one out.

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
| 18 | `python3 -m pytest tests/test_task96_r2_follow.py -q` (first run of the R2 file) | `1 failed, 4 passed` — `rusterm add: error: argument --cik: invalid int value: 'ЧИСЛО'`: my own advice line did not parse, which is exactly what the advice test exists to catch; fixed by making the advice the failed stage's argv |
| 19 | offline `follow AAPL` twice into `$TMPDIR/rt96-staging/follow-root3` (`--root` explicit, stub transport, `RUSTERM_ENV_FILE=/nonexistent/…`) | run 1: `1/5 каталог (запросов 0)`, `2/5 поиск в SEC (2)`, `3/5 отчётность (1)`, `4/5 цены (3)`, `5/5 снапшот (0)`, «всего запросов: 6», `мер: 28 — со значением 10, пусто 18`; run 2: `2/5 — инструмент уже есть, поиск пропущен (0)`, `3/5 (1)`, `4/5 (0)`, `5/5 (0)`, «всего запросов: 1», `снапшот v2 … без изменений — значения идентичны предыдущей версии` |
| 20 | transport call trace of the same path (every URL the stub served, with the gate's counter at that moment) | 6 calls: `company_tickers.json`, `company_tickers_exchange.json` (both `add`, gate=1 then 2), `companyfacts/CIK0000320193.json`, `time_series`, `splits`, `dividends`; `metric_sample` after the fixes sums to **6** — before them it summed to 5 and the price stage printed `(запросов 0)` |
| 21 | `python3 -m pytest tests/test_i5_guard_source.py -q` (with the new test file staged) | `4 passed` — the earlier `1 failed` in the full run was `SELFCHECK FAIL (P3/P4): untracked files present`, i.e. my uncommitted test file, not the guard |
| 22 | `python3 -m pytest -q --tb=no` (full default run, after both accounting fixes) | exit code 0, progress reached `[100%]`. The run's own `N passed` line is *not* in the captured output (the pty tests leave a child on the same pipe and the summary is lost), so no test count is quoted here |
| 23 | the commit's own hook: `I5_NESTED=1 bash agent/selfcheck.sh` → `agent/acceptance.sh` (two full pytest passes inside) | `Итог: пройдено 13, провалено 0` / `Принято.` → `eaf3899` — 13 is the number of acceptance checks, not of tests; the guard prints no test count either |
| 24 | six live runs, one per paper: `python3 -m rusterm --root "$TMPDIR/rt96-r3/live" follow <TICKER>` (cwd the clone, `--root` explicit — P7; each log kept as `$TMPDIR/rt96-r3/live-<TICKER>.log`) | AAPL: `2/5 поиск в SEC — готово (запросов 2)` → `фактов: 12452` (1) → `строк получено: 5000 … корп.действия: сплитов 5; дивидендов 83; записано новых: 88` (3) → `снапшот v1`, `мер: 28 — со значением 21`, `всего запросов: 6`. ADBE/KSPI/MSFT/VALE/VZ: same three stages, then `twelvedata: splits: source_unreachable:http_403`, `4/5 цены — отказ (запросов 1)`, `совет: rusterm ingest --source twelvedata --instrument US-<T>`, rc=1; quotes had already been written (5000 rows; KSPI 672), facts 15368 / 7 / 16498 / 4712 / 14254 |
| 25 | `python3 "$TMPDIR/rt96-r3/snap_five.py"` — five `python3 -m rusterm --root "$TMPDIR/rt96-r3/live" snapshot --instrument US-<T>` calls | `rc=0` for all five; last line `запросов: до 26.0 после 26.0 (дельта 0)` |
| 26 | `python3 "$TMPDIR/rt96-r3/table_final.py"` (the run's own base, `mode=ro`) | `budget: 26.0`; `status фактов: {'ok': 63291}`; per paper the measures/years/rows of the two tables in the R3 section; `корп-действий` 88 for AAPL and 0 for the other five |
| 27 | `python3 "$TMPDIR/rt96-r3/like_for_like.py"` (both bases, `mode=ro`, `concept<>'percentile'`, latest snapshot by `built_at`) | user base 21 / 21 / 0 / 22 / 7 / 8 valued with 8–12 percentile rows and 35–110 governance rows per instrument; run 21 / 20 / 2 / 22 / 17 / 16 with 0 percentile rows and 5 governance rows |
| 28 | `python3 "$TMPDIR/rt96-r3/user_base.py ~/equitylab "$TMPDIR/rt96-r3/live"` | user base: 44 instruments, 285 snapshots, 207036 price rows, prices to 2026-09-18; run: 6 instruments, 6 snapshots, 25672 rows, prices to 2026-09-23 |
| 29 | `python3 "$TMPDIR/rt96-r3/diff_concepts.py"` | per-concept disagreements: ADBE `roe` (base has the value, run `missing_prior_period`); KSPI 2 concepts, VALE 10, VZ 8 — all valued only in the run; 0 measure differences for AAPL and MSFT; every `dei:*` concept «база 0 / прогон 3…135» |
| 30 | `python3 "$TMPDIR/rt96-r3/probe6.py"` — the real provider, real transport, 3 requests out, key redacted in every print | `splits: error code=403 message=/splits is available exclusively with grow or pro or ultra or venture or enterprise plans. Consider upgrading your API Key now at https://twelvedata.com/pricing`; `dividends:` the same wording for `/dividends`; `/time_series` (with `start_date`) reported `code=401` — `запросов outward: 3` |
| 31 | `python3 "$TMPDIR/rt96-r3/probe7.py"` — the exact shape the run used: `time_series?symbol=AAPL&interval=1day&outputsize=5000&end_date=2026-09-24` (1 request) | `как живой прогон (без start_date): HTTP 401 status=error code=401 строк=0 message='**apikey** parameter is incorrect or not specified…'` |
| 32 | `python3 "$TMPDIR/rt96-r3/probe8.py"` (1 request, `outputsize=5`, whole body with the key replaced by `<KEY>`) | `HTTP 401` / `{"code":401,"message":"**apikey** parameter is incorrect or not specified. You can get your free API key instantly following this link: https://twelvedata.com/pricing. If you believe that everything is correct, you can contact us at https://twelvedata.com/contact/customer","status":"error"}` |
| 33 | `dei` census and payload hashes over the user's base (`mode=ro` only, P7) | `dei:EntityCommonStockSharesOutstanding` 1951 rows / 37 issuers, all ingested `2026-09-24 05:30:48 … 05:45:38`; **7 issuers with no `dei:*` at all, six of them this round's six papers** (last ingestion `2026-09-21 04:25:49 … 05:39:45`); `raw_object.sha256` for VZ fundamentals `69e11989…082ed1` 345682 bytes **identical in both bases**, AAPL `4ac7958f…53496` identical; 54 measures in the base carry a `shares_outstanding` refusal; the base's VZ rows on both shares tags: 0 |
| 34 | `python3 -m pytest tests/test_task96_r3_replay.py tests/test_task96_r3_refused_calls.py -v` | `7 passed in 8.55s` |
| 35 | `python3 -m pytest tests/test_task96_r3_refused_calls.py tests/test_task96_r3_replay.py tests/test_task96_r2_follow.py tests/test_task64_j1_budget_truth.py -v` | `17 passed in 40.80s` |
| 36 | `python3 -m pytest tests/test_budget.py tests/test_c3_actions.py tests/test_c5_cadence_cli.py tests/test_div_yield_from_filings.py tests/test_task65_k4_firsthour.py tests/test_a1_refresh.py tests/test_free_only.py -v` | `36 passed, 1 deselected in 38.36s` |

## HANDOFF

 interim block, rewritten at the close of the round.

Status so far: arrival only. Round 121, spec TASK-96, items R1–R5 open.
One environment event: the working clone under `/tmp` was swept and rebuilt
from origin before the first commit; every arrival number above was
re-measured after the rebuild. Nothing is claimed accepted that has not
been run.
