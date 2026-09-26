# REPORT-90 — ТЗ-90, круг 111

Ветка `agent/night-11`, голова на приходе `f94db0f`, батон `agent/TASK-90.md`.
Язык отчёта — английский по AGENTS.md; цитаты команд — как они вышли.

## Arrival state (measured, first run before any commit)

`bash agent/selfcheck.sh > /tmp/rt90-arrival.log 2>&1; tail` →
**«Итог: пройдено 10, провалено 3»**, `SELFCHECK FAIL (acceptance): exit status 3`.
Полный лог приёмки сохранён: `/var/folders/hb/.../T/selfcheck-acc.5etQdb`.

Three reds, all diagnosed before any code change; none of them is a defect
of the previous round:

1. **check 13 «ничего вне git»** — `?? tools/tz90_ca_range_check.py`, my own
   probe file created between the run's start and its end.
2. **`tests/test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`**
   — same cause, not a guard defect: the test calls `selfcheck.sh` nested and
   P3/P4 inspect the *outer* tree, so one `??` line fails it. Measured again
   after the tree was cleaned, quoted below.
3. **`tests/test_report_sections.py::test_done_items_have_code_commits_in_round`**
   (L3) — genuine intake debt, the same disease TASK-81 B0 was written for:
   `agent/STATE.json` still named the previous round (`task=agent/TASK-81.md`,
   `item=B3`), so L3 read `REPORT-81.md`, whose final HANDOFF declares
   `Items done: … B1, B2, B3`, while the round window (marker 111 → head)
   contains only baton commits:
   `AssertionError: пункты ['B1', 'B2', 'B3'] объявлены сделанными, но коммита
   круга с реализацией (не только tests/) не найдено`.
   Repaired by the first commit of this round: STATE moved to TASK-90 and
   this report opened.

Tree hygiene note: at arrival the index carried a staged edit of
`agent/p6_rule.sh` (+2 duplicated comment lines) — residue of an interrupted
I5 run, not a human edit. Bytes saved to `/tmp/p6-residue-r111.sh`, file
restored from `HEAD` (`git restore --source=HEAD --staged --worktree`), md5
of worktree and `HEAD` blob both `f66337e74fef33da830ed385d3b18a36`.

## Done

### A1 — prices and corporate actions refresh (deadline 2026-09-26)

Disease, measured on the user's base read-only
(`sqlite3 "file:/Users/anton/equitylab/rusterm.db?immutable=1"`):

```
https://api.twelvedata.com/time_series?symbol=AAPL&interval=1day&outputsize=5000|2026-09-21 04:26:03
https://api.twelvedata.com/splits?symbol=AAPL&range=full|2026-09-21 04:26:04
https://api.twelvedata.com/dividends?symbol=AAPL&range=full|2026-09-21 04:26:11
…
US-AAPL|2026-09-18|5000   US-ADBE|2026-09-18|5000   US-KSPI|2026-09-18|669
US-MSFT|2026-09-18|5000   US-VALE|2026-09-18|5000   US-VZ|2026-09-18|5000
```

One `time_series` object per symbol ever, all fetched 2026-09-21, last close
2026-09-18: the cache key carried no date, so the first collection was also
the last one.

**Which branch of the fork was taken: the dated one.** The vendor check ran
first, 4 requests of the 4 allowed, AAPL, `as_of=2026-09-23`
(`python3 tools/tz90_ca_range_check.py AAPL 2026-09-23`):

```
AAPL / as_of 2026-09-23 / запросов: 4 из 4 ({'api.twelvedata.com': {'used': 4, 'refused': 0, 'rate_limited': 3, 'ceiling': 800, 'per_second': 0.13333333333333333}})
dividends range=full 83 событий   неразобрано: 0
dividends dated      83 событий   неразобрано: 0
splits    range=full 5 событий    неразобрано: 0
splits    dated      5 событий    неразобрано: 0
dividends: совпадают = True; только в full = []; только в dated = []
splits: совпадают = True; только в full = []; только в dated = []
```

Event sets are identical, so `/splits` and `/dividends` now send
`start_date=1900-01-01&end_date=<as_of>` (`CA_START` replaces `CA_RANGE`) and
the canonical keyless URL carries the date; the `fetched_at`-equals-`as_of`
fallback was not needed and is not implemented. No fake parameters: `end_date`
is a real vendor parameter already present in `params_for`.

Code: `providers/twelvedata.py` — `ca_params(symbol, as_of)`,
`cache_url_ca(kind, symbol, as_of)`, `splits(symbol, as_of)`,
`dividends(symbol, as_of)`; `cli/__init__.py` — `_ingest_twelvedata_prices`
requests `end=as_of` and caches under that URL, `_ingest_twelvedata_actions`
passes `as_of` to both the URL and the fetch.

**Done when, quoted:**

`python3 -m pytest -q tests/test_a1_refresh.py tests/test_market_prices.py tests/test_c3_actions.py`
→ `................. [100%]` (17 passed, 0 failed).

Red on the parent commit (PROTOCOL: both code files restored from `HEAD`, new
tests kept — `python3 -m pytest -q tests/test_a1_refresh.py`):

```
url = 'https://api.twelvedata.com/dividends?symbol=AAPL&range=full&apikey=TESTONLY-key'
>       return parse_qs(urlparse(url).query)["end_date"][0]
E       KeyError: 'end_date'
FAILED tests/test_a1_refresh.py::test_price_urls_carry_the_date_and_never_the_key
FAILED tests/test_a1_refresh.py::test_same_day_prices_are_free_next_day_prices_ask
FAILED tests/test_a1_refresh.py::test_a_dividend_that_appears_next_day_lands
```

and after restoring the fix: `... [100%]` — 3 passed. The three tests are:
same `as_of` twice → 1 request and the same rows; next `as_of` → 1 more
request and the new day written (`put_rows` I7 holds, 3 dates, no duplicates);
a dividend present only in the `D+1` payload lands in `corporate_action`
with vendor amount and currency.

Committed as `ad4c131` (7 files, +456/−39) and pushed `f94db0f..ad4c131`; the
pre-commit hook's own run: «Итог: пройдено 13, провалено 0», `SELFCHECK OK`.

## Blocked

Nothing blocked in A1.

## What not to trust

- A1 was measured on **AAPL only** — the vendor check is one symbol, 4
  requests. Another issuer's `/dividends` may shape dates differently; the
  parsers are shared, the evidence is not per-symbol.
- The new tests use counting transports with synthetic payloads; the real
  vendor response for the *dated* corporate-action call was checked once,
  live, by the tool — not by a recorded fixture. No payload was written to
  `tests/data/twelvedata/` this item.
- Network budget for A1 is spent (4 of 4); no further live call was made.
- The `.app`/Finder path (TASK-81 B3) is untouched here: A1 changes what a
  collection writes, not which catalog it writes to. That is A4/A5.

## Disputed

None through A1 — see «Disputed (A5)» at the end of this report.

## HANDOFF

Status:          WORKING
Items done:      приём круга (STATE + отчёт), A1
Items not done:  A2, A3, A4, A5
Acceptance:      quoted in the A1 commit message
Tests:           (per commit below)
Guards:          none touched
Schema:          unchanged
Network:         4 of 4 (twelvedata), budget for A1 spent
Model:           Qoder executor, llm_calls 0
Secrets:         0
Pushed:          yes — ad4c131
NOW: A2, step 1

## Done (продолжение круга)

### A2 — `rusterm chat` работает у того, у кого есть ключ

Оба дефекта подтверждены командами на родительском коде (`cli/__init__.py`
восстановлен из `HEAD`, тесты оставлены):

```
python3 -m pytest -q tests/test_a2_chat_cli.py
  FAILED ::test_chat_parser_declares_its_arguments
  FAILED ::test_chat_with_a_key_exits_zero_and_leaves_one_transcript
  FAILED ::test_chat_max_calls_reaches_the_session
```

и живым путём из ТЗ (`echo | env -i … RUSTERM_LLM_API_KEY=fake
RUSTERM_LLM_MODEL=fake RUSTERM_SEC_UA="t t@example.com" python3 -m
rusterm --root <tmp> chat`): **код возврата 2**,
`AttributeError: 'Namespace' object has no attribute 'max_calls'`.
На починке та же команда — **код возврата 0**:

```
чат: пустая строка — выход; модель отвечает только цитированными числами
вопрос> вызовов модели/инструментов за сессию: 0
расшифровка сохранена: chat-1790160403471
```

то есть и `time.time()` в конце сессии (второй дефект, NameError) больше
не падает: строка расшифровки доходит до хранилища.

Изменено: `--max-calls` (дефолт `MAX_TOOL_CALLS_PER_SESSION`) и
опциональный `--instrument` у sub-парсера `chat`; модульный
`import time`; `cmd_chat` строит ОДИН `RequestGate` и передаёт его двери
`make_chat_client(gate=…)` — раньше проверка канала и дверь держали по
гейту, и инъекция нижнего сидa в дверь не проходила. Попутно найден и
починен ещё один враньё-след: `_ChatAdapter` не отдавал `model`, и
`save_transcript` getattr'ом писал в `chat_transcript.model` значение
`unknown`, хотя модель была известна. Теперь у адаптера есть
`model`-свойство, и тест закрепляет `model == "fake-model"`.

Тесты (`tests/test_a2_chat_cli.py`, 4 шт.) водят полный путь дверью:
`cli.main(["--root", tmp, "chat"])` с ключом в окружении, настоящим
`make_chat_client` и фейковым гейтом на нижнем сиде (прецедент —
`_StubGate` в `tests/test_chat_door.py`), stdin `вопрос` + пустая строка;
ноль сети доказан autouse-стражем `urlopen` из `conftest.py`.
`--max-calls 0` отдельно закрепляет, что бюджет сессии удерживает вызовы
(отказ с именованной причиной, расшифровка всё равно сохранена).

`python3 -m pytest -q tests/test_a2_chat_cli.py tests/test_free_only.py tests/test_chat_door.py tests/test_desktop_chat.py tests/test_b36_live.py`
→ `........................ [100%]` (24 passed) — прежний пин
свободности (отказ без ключа словами, код 1) не сломан.

Замечание для координатора: колонка `chat_transcript.calls` — счётчик
вызовов **инструментов** (`core/chat.py:83`), а не модели; тест закрепил
это как есть, а не как «ноль сети = ноль вызовов».

## Done (A3) — snapshot build never crashes, never leaves half a snapshot

Report language note: AGENTS.md asks for English in `agent/`; my A1/A2
blocks above drifted into Russian. A3 onward is English again.

### 1. Measured before the change (red on parent)

Linked worktree of the parent commit, per PROTOCOL §12
(`git worktree add --detach "$TMPDIR/rt90-a3-parent" 30eacd2`, new test
file copied in, removed after the run — `git worktree list` is back to
the clone + the coordinator's own `rusterm-relay-verify`):

`python3 -m pytest -q tests/test_a3_snapshot.py -p no:randomly` → 7
failed, each naming its own defect:

```
E   AttributeError: 'int' object has no attribute 'get'      # A3.1 crash
E   AssertionError: ('ready', None)  assert 'ready' == 'missing'  # A3.1 lying coverage
E   ZeroDivisionError: division by zero                     # A3.2 ps, revenue 0
E   AssertionError: ('-1.4', None)  assert '-1.4' is None   # A3.2 ps, revenue < 0
E   AssertionError: [['ready', 'ready']] == [['ready', 'building']]  # A3.3 status
E   AssertionError: assert '4b7f1648-…' == 'a45f6282-…'     # A3.3 latest = the half snapshot
E   TypeError: SnapshotRepo.previous_snapshot() got an unexpected keyword argument 'before_version'
```

`addopts` already carries `-q`, so a second `-q` prints no count line;
counts below are read off the progress line and the exit code.

### 2. What changed

**A3.1 — the rebound local** (`core/snapshot.py`). The industry block
assigned `computed = sum(1 for m in metrics …)` over the pass-1 dict of
the same name. Renamed to `industry_computed`; the block's `status` and
`reason` use the new name and the `reason` text stays byte-identical to
before (`f"computed {n}/{m} method {v}"`), so the existing industry pins
hold. `own = computed.get(concept)` in pass 2 and
`("ready", None) if computed` in coverage see the dict again.

**A3.2 — ps denominators** (`core/snapshot.py`, `_valuation_pass`).
`ps` is the only valuation measure in that pass dividing by hand without
checking the denominator (`pe`/`pb`/`ev` go through
`calculate_measure`). Two branches added, words taken from the closed
dictionary §1.4 (`rusterm/formulas.py:13`): revenue 0 →
`denominator_zero`, revenue < 0 → `negative_denominator`, value stays
NULL. `pe`'s `ni_value <= 0 → "missing_data: net_income"` was left
alone — pinned by `tests/test_b1_zero_vs_missing.py`, not in this item.

**A3.3 — building → ready** (`core/snapshot.py`, `store/repos.py`).
`build()` keeps its signature and now: creates the row as `building`,
calls the moved body `_assemble(…, snapshot_id, version)`, and on
`BaseException` calls `delete_snapshot(snapshot_id)` and re-raises;
`set_status(snapshot_id, "ready")` is the last write of a successful
build. `BaseException` rather than `Exception` so Ctrl-C during a build
also leaves nothing behind. No migration: `snapshot.status` has no CHECK
(`store/db.py:163`). `SnapshotRepo` gained `set_status` and
`delete_snapshot` (drops `measure_lineage` → `measure` →
`snapshot_block` → `snapshot` in one transaction — those FKs carry no
`ON DELETE CASCADE`). `latest_snapshot_id` filters `status='ready'`;
`previous_snapshot(instrument_id, before_version=None)` — with a version
(inside a build) it takes the newest ready row below that version,
without it the old `OFFSET 1` over ready rows, which is what
`cli/__init__.py:960` and `desktop/actions.py:233` call after a finished
build. `_diff` passes the version, because the row of the build in
flight is already in the table and would otherwise eat the offset.

`desktop/actions.py`'s promise «половины снапшота не бывает» is now true
of the storage, not only of the UI.

### 3. Tests

`tests/test_a3_snapshot.py`, 7 tests, all offline:
- industry metrics + 5 fresh peers build without exception, the
  percentile is computed from the pass-1 own value, and `fundamentals`
  coverage is `ready`;
- coverage truth both ways: no facts + 3 computed industry metrics →
  `missing` with a named reason; facts + all-grey industry metrics
  (counter 0) → `ready`;
- `ps` parametrised over revenue 0 and −50;
- the row is read as `building` from inside the build (by the industry
  resolver, which runs after pass 1) and is `ready` afterwards — read
  straight from the `snapshot` table, not through the repo, so the test
  does not lean on the reader it also pins;
- a `RuntimeError` injected mid-build: nothing of that snapshot remains
  (no orphan rows in `snapshot_block`, `measure`, `measure_lineage`),
  `latest_snapshot_id` still returns the previous ready snapshot, and
  the next build lands on version 2 — the version was not burned;
- `previous_snapshot(before_version=…)` inside a build returns the last
  ready version, not the row under construction.

`python3 -m pytest tests/test_a3_snapshot.py -q -p no:randomly` →
`....... [100%]`, exit 0.

Snapshot-adjacent subset (a3, coverage, currency_firewall,
k4_k6_valuation, snapshot_export, j1_display, j3_fiscal,
n2_industry_view, industry_aggregate, b1_zero_vs_missing, repos,
desktop_actions) → exit 0, no FAILED line. Whole default suite
(`python3 -m pytest -q tests/ -p no:randomly`) → exit 0, `[100%]`, one
`x` and four `s` (marker exclusions), no failures: `/tmp/a3-suite.log`.

### 4. Not to trust (A3)

- The industry resolver in these tests is a synthetic dict in the shape
  `build()` reads (`sector/reason/metrics/unmapped`), not the maritime
  module's own output — `tests/test_n2_industry_view.py` covers the real
  resolver; both paths meet at the same block.
- `ps` was tested through hand-inserted `fact` rows (revenue 0 and −50),
  not through a real pre-revenue filing; how a zero-revenue issuer gets
  parsed from EDGAR/vendor is untouched by this item.
- Only the mid-build exception path was tested. A build killed with
  SIGKILL still leaves a `building` row: readers ignore it and the next
  successful build reuses the same version number, but nothing deletes
  that row — no cleanup job exists for it.
- `latest_per_instrument()` and `snapshots_of_instrument()` still do not
  filter by status (outside this item's text), so a killed build's row
  could show in `rusterm status` and in the ТЗ-75 version history.
  Reported rather than fixed silently.

## Done (A4) — every name the code reads loads from `~/.rusterm.env`

### 1. Measured before the change (red on parent)

Evidence tree (main tree untouched):

```
git worktree add --detach /tmp/rt-a4-parent HEAD
cp tests/test_a4_env_names.py /tmp/rt-a4-parent/tests/
cd /tmp/rt-a4-parent && python3 -m pytest tests/test_a4_env_names.py -q
```

→ exit 1, 5/5 red. The failing lines name the defect, not the fixture:

- `E KeyError: 'RUSTERM_DART_KEY'` — `load_env()` returns no entry for the
  name, because `parse_env_file` keeps a line only `if name in ENV_NAMES`
  (`rusterm/env.py:69`). The `RUSTERM_DART_KEY=` line `GUIDE.md:21` tells
  the user to write is dropped silently.
- `E AssertionError: assert 'https://openrouter.ai/api/v1' == 'https://llm.example.invalid/v1'`
  — the file's base URL never reaches `LlmApiClient.from_env`; the client
  keeps the built-in default.
- `status`: `'RUSTERM_DART_KEY: задана' in <output>` false — the printed
  environment block lists six names, DART is not one of them.
- key view: `assert 'RUSTERM_DART_KEY' in {'RUSTERM_SEC_UA', …}` — the
  settings panel renders six rows.
- guard: `{'RUSTERM_DART_KEY': 'rusterm/providers/__init__.py:79',
  'RUSTERM_LLM_BASE_URL': 'rusterm/providers/llm_api.py:30'}` — the two
  names the package reads from the environment are exactly the two
  missing from the tuple.

### 2. What changed

- `rusterm/env.py` — `ENV_NAMES` gained `RUSTERM_DART_KEY` and
  `RUSTERM_LLM_BASE_URL`. The task names three; `RUSTERM_DATA` has been in
  the tuple since ТЗ-81 B3, so this item lands two and pins all three by
  name in the guard test (a future drop of `RUSTERM_DATA` reddens it).
- One edit propagates: `load_env`, `report()` (→ `doctor`), the `status`
  environment block and `keys_view` all iterate `ENV_NAMES`, so no
  surface-specific patch was needed.
- `rusterm/desktop/data.py` — `KEY_PURPOSE` rows for both names; a panel
  row without a purpose is a silent line (C9.1).
- `GUIDE.md` — the §5 `status --json` sample regenerated verbatim (the
  documented JSON carries both new keys). `tests/test_guide_truth.py`
  replays that block byte for byte, so it is not an optional edit.
- `tests/test_desktop_settings.py` — three pinned name sets widened,
  entries added inside each literal; 0 assert lines removed.
- Deliberate limit: `RUSTERM_LLM_BASE_URL` is not added to the §0 key
  table. That table answers "where do I register to get this" — a free
  API key. The base URL is an optional endpoint override with a working
  default (ADR-0018); listing it as a key would tell the user it is
  required. Recorded here instead of decided silently.

### 3. The guard, and which direction it checks

`test_guard_every_env_name_read_by_the_package_is_loadable` walks
`rusterm/**/*.py` with `ast`, takes every string constant shaped exactly
like `RUSTERM_[A-Z0-9_]*`, and requires each to be in `ENV_NAMES` or in an
explicit `NOT_LOADABLE` exemption carrying its reason
(`RUSTERM_ENV_FILE` locates the file itself; `RUSTERM_APP_SMOKE` is a
window self-check flag, not user configuration).

- AST rather than grep: docstrings and comments name variables that are
  never read from the environment (`«нет RUSTERM_SEC_UA — сети нет»`), and
  multi-line f-strings do not hold a bare name; grep would need exemptions
  for prose, which is how such a guard dies.
- The guard also reddens on an exemption whose name nothing reads any more
  (`NOT_LOADABLE` is a claim, not a dump).
- Direction is one-way and said in the test docstring: a name in
  `ENV_NAMES` that nobody reads stays invisible (the tuple is itself a
  constant in the package, so widening it cannot redden this guard). The
  opposite half — "in the list but no purpose row" — is covered by
  `assert all(r["purpose"] for r in view["rows"])` in this item's own test.

### 4. Tests

- New `tests/test_a4_env_names.py`: 5 tests, offline. Values are synthetic
  (`test-dart-value-0123456789`, `https://llm.example.invalid/v1`); the
  real `DartProvider.from_env` / `LlmApiClient.from_env` are constructed —
  they read the environment only, and the conftest network sentinel would
  fail the test if a request were attempted.
- `python3 -m pytest tests/test_a4_env_names.py tests/test_env.py
  tests/test_desktop_settings.py -q` → 17 dots, `[100%]`, exit 0.
- `python3 -m pytest tests/test_guide_truth.py tests/test_a4_env_names.py
  -q` → exit 0 (`/tmp/a4-run1.log`).
- Full default suite: `python3 -m pytest tests/ -q -p no:cacheprovider` → exit 0, `[100%]`,
1119 progress dots, no FAILED line (`/tmp/a4-full.log`). That run
collected `tests/test_a4_env_names.py` before the three-name pin was
added to the guard test; the pinned file was then re-run with its
neighbours — `python3 -m pytest tests/test_a4_env_names.py
tests/test_env.py tests/test_desktop_settings.py
tests/test_guide_truth.py -q` → exit 0, 20 dots (`/tmp/a4-run2.log`) —
and the whole suite runs again inside the pre-commit hook
(selfcheck → acceptance step 3 `pytest -q`) on this exact tree.

### 5. Not to trust (A4)

- The guard sees exact literal names. A name built at runtime
  (`"RUSTERM_" + suffix`) is invisible to it — `providers/__init__.py`
  keeps one literal per channel today; a future dynamic table would slip
  through quietly. Fixing that means an import-time check, out of scope.
- `KEY_PURPOSE` wording ("без него — OpenRouter") restates
  `providers/llm_api.py`'s default and ADR-0018; no test pins panel prose.
- `doctor` was not re-tested for the new names: it prints the same
  `env.report()` dict that `status` covers here. Same source, other
  printer.
- Nothing here makes the user's DART key exist. TASK-58 C1 stays blocked
  on obtaining the key; this item only makes the file line loadable.
- Housekeeping: a standalone `bash agent/selfcheck.sh` appends
  `# i5 green case: staged widening` to `agent/p6_rule.sh` and stages it.
  Before this commit the file was restored and `git diff HEAD --
  agent/p6_rule.sh` is empty — no guard file is in this item's diff.

## Done (A5) — one default data catalog for the CLI and the window

### 1. Measured before the change (parent `4d0c4d2`, sandbox HOME)

| door | command | what it picked |
|---|---|---|
| CLI | `cd work && rusterm status` | `/private/tmp/a5-probe2/work` |
| window / `.app` | `default_root()` in the same cwd | `/tmp/a5-probe2/home/.rusterm` |

One directory, two catalogs: the CLI's default was the parser's
`default="."`, the window knew only `$RUSTERM_DATA` and `~/.rusterm`. And
neither said *why*: `status` on the parent prints
`каталог данных: /private/tmp/a5-parent-probe` — a path with no reason,
so «открылась не та база» and «здесь нет данных» look identical.

Measured on the user's machine after the change (paths only, nothing
read from the base):

| cwd | rule | catalog |
|---|---|---|
| `/Users/anton/equitylab` | 3 | `.` — the working 60 MB base |
| `/tmp` (what a Finder launch looks like) | 4 | `/Users/anton/.rusterm` — the round-100 leftover |

Line for `~/.rusterm.env`, as the task asks (the file has four key lines
today and no `RUSTERM_DATA`):

```
RUSTERM_DATA=/Users/anton/equitylab
```

With it, every door — CLI from any directory, `python3 -m
rusterm.desktop`, double-clicked `.app` — resolves to rule 2 and the
same catalog.

### 2. What changed

- `rusterm/store/paths.py` — `default_root()` became
  `resolve_root(explicit=None) -> (Path, int)`: the task's four-row
  table, and the rule number is part of the result because both doors
  print it.
- `rusterm/cli/__init__.py` — the parser's `--root` default is `None`
  and `main()` resolves once before dispatch. `load_env()` runs above
  it, so rule 2 already covers a shell-less launch. `cmd_status` prints
  `каталог данных: <path> (правило: N)`. `cmd_desktop` forwards the
  root only when it is rule 1: forwarding a path chosen by rules 2-4
  would make the window door re-read it as explicit and print a false
  rule in the header.
- `rusterm/desktop/__main__.py`, `rusterm/desktop/app_entry.py` — the
  same function, and the rule travels to the window.
- `rusterm/desktop/window.py` — `_build_window(..., rule=1)`; header
  `QLabel` `objectName="root_rule"` holds exactly the `status` line; the
  `RUSTERM_APP_SMOKE` line became `rusterm-app root=<path> (правило: N)`
  (the existing `root=` substring assertions still hold — they were not
  loosened).
- `GUIDE.md` — the executed `desktop --help` block regenerated, §1 and
  §10.1 prose now state the four rules, and the smoke-line paragraph
  says the rule is in the line.

### 3. Tests

- New `tests/test_a5_one_default_catalog.py` (5 tests): the table test
  walks the four rows and each row is checked where it *contradicts* the
  next one (explicit beats the environment, the environment beats
  `./rusterm.db`, that beats home); rule 3 does not fire in an empty
  directory; an env-file line is rule 2 for a Finder launch; `status`
  prints rule 1 for `--root` and rule 3 by default; and the grep
  guard — `default="."` gone from the parser, `default_root` has no
  readers left, `environ.get("RUSTERM_DATA")` and
  `home() / ".rusterm"` each appear in exactly one module.
- The two window assertions first lived in that file and were **moved**
  to `tests/test_desktop_window.py` (`test_header_names_the_catalog_and_the_rule`,
  `test_header_and_cli_print_the_same_line`) because acceptance step 6
  forbids Qt outside `rusterm/desktop/` and `tests/test_desktop_*.py` —
  measured: `ПРОВАЛ Qt вне слоя интерфейса`, three lines named
  `tests/test_a5_one_default_catalog.py:41,149,164` (log
  `/var/folders/…/selfcheck-acc.aCuW3F`). Where they now live they use
  the file's own migrated base and its `env` fixture, so the header is
  checked against a real catalog rather than a `repos=None` window.
- Touched: `tests/test_desktop_door.py` (the recorder now captures the
  rule; `test_door_without_root_uses_the_window_default`, whose premise
  *was* the divergence, became `test_door_without_root_shares_the_cli_default`),
  `tests/test_paths.py` (rules 2 and 4 pinned with their numbers, and
  with `chdir` so rule 3 cannot leak in from the repo directory),
  `tests/test_task81_b3_build.py` (`resolve_root() == (catalog, 2)`).
- Collateral, found by this item and fixed in it:
  `tests/test_task58_c3.py` and `tests/test_b35_markets_readonly.py`
  launched the CLI as a subprocess **inheriting `HOME`** and without
  `--root`, which was safe only while the parser's default was `"."`.
  With one precedence they resolved to rule 4 — the developer's real
  `~/.rusterm`, present on this machine. Five read-only refusal tests
  stopped refusing (their base existed), the writer tests wrote outside
  the tree they assert on, and the I5 case went red as collateral
  because acceptance's own `pytest -q` failed. Both `_run` helpers now
  sandbox `HOME` next to the tree and drop an inherited `RUSTERM_DATA`;
  the writer positive controls name `--root .` (their assertions are
  unchanged), and `test_b35_markets_readonly.py` gained
  `test_writer_without_root_goes_to_the_home_rule_not_the_tree`, which
  asserts the base appears in the sandbox `~/.rusterm`, the printed
  `каталог:` line names it, and the git tree stays clean. **Real side
  effect before the fix:** that run applied migration 45 to
  `/Users/anton/.rusterm/rusterm.db`, added `metric_sample` rows
  (`locator_resolve_failure`, `peer_set_coverage`, provider
  `synthetic`) and appended a traceback to
  `/Users/anton/.rusterm/logs/app.log`. Nothing was deleted; the base
  is 45 rows of schema and 5 metric samples.
- On the parent the new file cannot even be collected:
  `E ImportError: cannot import name 'resolve_root' from
  'rusterm.store.paths'` (worktree `/tmp/rt-a5-parent`, exit 2).
- Runs.
  - Targeted, final tree: `QT_QPA_PLATFORM=offscreen python3 -m pytest
    -q tests/test_task58_c3.py tests/test_b35_markets_readonly.py
    tests/test_a5_one_default_catalog.py tests/test_desktop_door.py
    tests/test_paths.py tests/test_task81_b3_build.py
    tests/test_desktop_window.py` → `[100%]`, `exit=0`, 77 tests
    (`/tmp/a5-targeted.log`).
  - Full suite on the staged tree: `python3 -m pytest -q
    -p no:cacheprovider` (`/tmp/a5-full2.log`) → 1124 tests, 1114
    passed, 5 skipped, 4 xfailed, **1 failed**:
    `tests/test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`.
    Cause is the mid-work state, not the change: that case re-runs
    `agent/selfcheck.sh` against the *outer* staged tree and P1 reads
    its declaration from `.git/COMMIT_EDITMSG`, which during a bare
    `pytest` holds the previous commit's message (A4's) — so my A5
    `ЗАМЕНА-БУЛАВКИ` lines were not there to be seen. Measured with the
    A5 message placed in `COMMIT_EDITMSG`, same staged tree:
    `bash agent/p1_rule.sh` → `P1: OK (staged)`, exit 0 — the guard is
    satisfied by the declaration, which is exactly what the skipped-in-
    the-hook case asserts.
  - First commit attempt (message + this tree): the hook's acceptance
    passed step 3 — `OK pytest, код возврата 0` on the A5 tree with the
    I5 cases skipped by `I5_NESTED=1` — and stopped at step 6 on Qt
    outside the UI layer (quoted above). No commit was created; the
    window tests were moved and the suite re-run.
  - The five refusals and the two positive controls that were red at
    the first full run are green in the targeted run above.

### 4. Not to trust (A5)

- The table says what a fresh project gets: `cd ~/new && rusterm init`
  with no `rusterm.db` nearby lands in `~/.rusterm` (rule 4). Before
  this item the same command wrote into `./`. That follows the task's
  row 3 literally — reported in Disputed rather than quietly patched
  with an init-specific exception.
- `status --json` does not carry the rule (its `data_dir` is unchanged),
  so the GUIDE's JSON sample did not need regenerating for this item.
- `_build_window(..., rule=1)`'s default is a claim, not a measurement:
  a window built without a rule says «правило: 1». True for
  `on_switch_root` (the user picked the folder) and for tests; the
  production doors always pass the number.
- Nothing migrates data: the stale `~/.rusterm` base still exists on
  this machine and still wins rule 4 until the user adds the
  `RUSTERM_DATA` line above. Deleting it is the coordinator's or the
  user's call, not an executor's.
- The TUI door (`cmd_tui`) now receives the resolved catalog instead of
  `"."`; its own screens were not re-checked beyond the existing PTY
  tests.

## Disputed (A5)

- TASK-90 A5, table row 3 + `rusterm init`. With one precedence for
  every door, creating a base in a fresh directory lands in `~/.rusterm`
  because `./rusterm.db` does not exist yet — `init` is the one command
  whose job is to create that file, so the rule it consults is always
  false at the moment it is asked. Either the table gains a row for
  «init creates where the user stands» (and then `init` must say the
  rule it used, as `status` now does), or the guide must tell the user
  to pass `--root` on the first run. Left as specified; the code prints
  the rule, so the choice is at least visible. Today's GUIDE §1 passes
  `--root` in every block, so nothing in the docs promises the other
  behaviour.

## HANDOFF

Status:          DONE — очередь TASK-90 закрыта (A1–A5)
Items done:      приём круга (STATE + отчёт), A1, A2, A3, A4, A5
Items not done:  нет в TASK-90; BACKLOG не открывался
Acceptance:      selfcheck в хуке на каждом коммите предмета; зелёный
                 случай I5 хук пропускает (`I5_NESTED=1`), поэтому его
                 утверждение (стейдж + декларация = зелёный) замерен
                 напрямую: `bash agent/p1_rule.sh` → `P1: OK (staged)`
Tests:           полный дефолтный прогон: дерево A3 — зелёный, дерево A4 —
                 зелёный, дерево A5 — 1114 из 1124 с одним артефактом
                 недокоммиченного состояния (объяснён в блоке A5)
Guards:          не тронуты — в диффе ни одного предмета нет
                 `agent/*_rule.sh` (демо-строка I5 возвращена в байты HEAD
                 перед каждым коммитом)
Schema:          unchanged
Network:         4 of 4 (twelvedata, A1); A2–A5 — ноль
Model:           Qoder executor, llm_calls 0
Secrets:         0 — наружу только имена; в A4 staged diff посчитан по
                 вхождениям значений (0 на каждый ключ)
Pushed:          yes — A1 ad4c131, A2 30eacd2, A3 faea1ca, A4 4d0c4d2;
                 A5 — этот коммит
User line:       `RUSTERM_DATA=/Users/anton/equitylab` в ~/.rusterm.env
                 (A5); что первый прогон A5 написал в ~/.rusterm — в
                 блоке A5
Questions:       1) Disputed (A5): `rusterm init` в пустом каталоге теперь
                 создаёт базу в ~/.rusterm — предназначена ли строка 3
                 таблицы для пишущих команд? 2) Очередь TASK-90 пуста:
                 следующий файл ТЗ или проход по BACKLOG?
NOW: hand → coordinator, затем wait
