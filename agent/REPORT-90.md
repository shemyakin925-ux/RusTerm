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

None yet.

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

## HANDOFF

Status:          WORKING
Items done:      приём круга (STATE + отчёт), A1, A2, A3
Items not done:  A4, A5
Acceptance:      quoted in each item's commit message (hook run)
Tests:           full default suite green on the A3 tree (quoted in the
                 A3 block); per-item subsets quoted per item
Guards:          none touched
Schema:          unchanged (A3 needed no migration — `snapshot.status`
                 has no CHECK)
Network:         4 of 4 (twelvedata, A1); A2 and A3 — zero network
Model:           Qoder executor, llm_calls 0
Secrets:         0
Pushed:          yes — A1 ad4c131, A2 30eacd2
NOW: A4, step 1
