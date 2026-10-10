# TASK-90 — what breaks for the user this week: frozen prices, dead `chat`, crashing snapshot, lost DART key, two catalogs

- **Status: READY**
- **Report:** `agent/REPORT-90.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-90.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600` — do not end the session.
- **Budgets:** network 0, except A1: Twelve Data ≤ 4 requests. LLM 0.
- **How to work:** no questions; forks are closed below; doubtful →
  Disputed, move on; one item = one commit, item id in the subject.
- **Place in queue:** **right after TASK-81**, before TASK-82 (user's
  order, 23.09). **A1 has a calendar deadline** (see «Where we are»);
  A2/A3 are user-facing crashes.
- **Source:** whole-project review of 23.09.2026 on `3f7dcc9`; every
  defect below was reproduced by the reviewer, command quoted.

## Where we are (measured on `3f7dcc9`)

- Acceptance in a linked worktree: «Итог: пройдено 13, провалено 0»,
  exit 0. **Every defect of TASK-90…94 passes all 13 checks** — they
  are structure-green and product-red (CONTEXT §3, TASK-46 N2).
- User base `/Users/anton/equitylab`, opened read-only
  (`file:…/rusterm.db?immutable=1`): last price **2026-09-18** for all
  six papers; the Twelve Data payloads sit in `raw_object` under
  key-free URLs **without a date**
  (`…/time_series?symbol=AAPL&interval=1day&outputsize=5000`, fetched
  2026-09-21).
- `_PRICE_STALE_DAYS = 7` (`core/snapshot.py`) ⇒ from **2026-09-26**
  every valuation measure of every paper (market_cap, ev, pe, ps, pb,
  fcf_yield, div_yield, roic, …) becomes
  `missing_data: price_close_stale:2026-09-18`, and re-running
  `rusterm ingest --source twelvedata` cannot help (A1).
- 0 peer sets, 0 percentile rows, 0 `llm_summary` rows in that base
  (TASK-92…94).

## A1. Prices and corporate actions refresh (deadline 2026-09-26)

`cli/__init__.py` `_ingest_twelvedata_prices` builds
`cache_url(symbol, start=None, end=None)` and reuses any raw object
with that URL: the first run is also the last one — a later run
spends 0 requests and writes 0 new rows, forever. `_ingest_twelvedata_actions`
does the same for `/splits` and `/dividends` (`cache_url_ca`), so a
new dividend is never collected either.

| Question | Rule |
|---|---|
| Cache key for `/time_series` | the request carries `end_date=<as_of>` (a real vendor parameter, `params_for` already has it); the canonical URL therefore contains the date: same `as_of` twice ⇒ 1 request (existing pin in `tests/test_market_prices.py` stays green), next `as_of` ⇒ 1 new request. |
| `/splits`, `/dividends` | send `start_date=1900-01-01&end_date=<as_of>` instead of `range=full` **only if** a live check (≤ 4 requests, AAPL) shows the vendor returns the same events as `range=full` up to `as_of`; otherwise keep `range=full` and accept the cached payload only when its `fetched_at` UTC date equals `as_of`. Report which branch was taken, with the payload counts. |
| Fake URL parameters | forbidden — `raw_object.url` is provenance (ADR-0003). |

**Done when:**
- counting-transport test: ingest with `as_of=D` twice → 1 request;
  then `as_of=D+1` → 1 more request and the rows of the new day are
  written (`put_rows` keeps I7);
- the same test for corporate actions: a dividend that appears only in
  the D+1 payload lands in `corporate_action`;
- `python3 -m pytest -q tests/test_market_prices.py tests/test_c3_actions.py` green.

## A2. `rusterm chat` works for a user who has a key

- `cli/__init__.py:1800` reads `args.max_calls`, but the `chat`
  sub-parser declares no arguments (`:2387`) ⇒ `AttributeError` before
  the first question. `:1817` calls `time.time()` with no module-level
  `import time` ⇒ `NameError` at the end of every session. Reproduced:

  ```
  echo | env -i PATH="$PATH" HOME=<tmp> RUSTERM_ENV_FILE=/dev/null \
    RUSTERM_LLM_API_KEY=fake RUSTERM_LLM_MODEL=fake \
    RUSTERM_SEC_UA="t t@example.com" python3 -m rusterm --root <tmp> chat
  → AttributeError: 'Namespace' object has no attribute 'max_calls'; exit 2
  ```
- Broken since TASK-26 (`4fd5e9e`). The only CLI test
  (`tests/test_free_only.py:247`) drives the no-key path, so 13/13 never
  saw it — the TASK-46 N2 lesson again: drive the door, not the function.

**Done when:**
- `chat` gets `--max-calls` (default `MAX_TOOL_CALLS_PER_SESSION`) and
  optional `--instrument`; `time` is imported;
- a test calls `cli.main(["--root", tmp, "chat"])` with a key in the
  environment, a fake transport injected at the lowest seat that keeps
  `make_chat_client` real, and stdin `"вопрос\n\n"`: exit 0, one
  `chat_transcript` row, zero network (the conftest guard proves it);
- the new test is red on the parent commit (PROTOCOL: temp worktree
  under `$TMPDIR`, last 5 lines in the report).

## A3. A snapshot build never crashes and never leaves half a snapshot

1. `core/snapshot.py:352` `computed = sum(1 for m in metrics …)`
   rebinds the dict of pass-1 values to an **int** inside the
   industry block. Then `:392 own = computed.get(concept)` raises
   `AttributeError` whenever an instrument has a sector with metrics
   **and** peers are passed — exactly what TASK-73 T2 will start
   producing; and the coverage line `("ready", None) if computed`
   follows the industry count: reproduced `net_margin = 0.2` stored
   while coverage says `fundamentals missing: no_as_reported_facts`.
2. `:1092 ps_value = total_value / annual_rev[0]` — annual revenue 0
   (pre-revenue issuer) ⇒ `ZeroDivisionError`, reproduced.
3. `build()` inserts the snapshot row with status `ready` first
   (`:231`) and every measure in its own transaction. After either
   crash above, a `ready` snapshot with 28 measures and no coverage
   stays behind and `SnapshotRepo.latest_snapshot_id` (repos.py:472,
   no status filter) returns it. `desktop/actions.py` promises «половины
   снапшота не бывает» — measured false.

**Done when:**
- the local is renamed; a test with industry metrics + 5 fresh peers
  builds without exception and `fundamentals` coverage is `ready` iff a
  pass-1 measure has a value;
- `ps`: revenue 0 → `denominator_zero`, revenue < 0 →
  `negative_denominator` (dictionary §1.4), both tested;
- the row is created with status `building` (`snapshot.status` has no
  CHECK — no migration needed) and set to `ready` as the build's last
  write; on any exception the rows of that snapshot are deleted and
  the exception re-raised; `latest_snapshot_id` and
  `previous_snapshot` read only `ready`; test: an exception injected
  mid-build ⇒ no new ready snapshot, previous latest unchanged.

## A4. The DART key (and two other names) are read from `~/.rusterm.env`

- `rusterm/env.py:19` `ENV_NAMES` lacks `RUSTERM_DART_KEY`,
  `RUSTERM_LLM_BASE_URL`, `RUSTERM_DATA`; `load_env` ignores every name
  outside the tuple. `GUIDE.md:21` tells the user to put
  `RUSTERM_DART_KEY=...` into `~/.rusterm.env` — that line would never
  reach `providers/dart.py:43`, and the `.app` started from Finder has
  no shell environment at all.
- The desktop key view (`desktop/data.py` `KEY_PURPOSE`) and
  `status`/`doctor` do not list DART.
- Note for the record: TASK-58 C1 is BLOCKED because the key is absent
  from the machine **and** from the file (names-only check, 23.09) —
  getting the free key is the user's action; making it loadable is ours.

**Done when:**
- the three names are in `ENV_NAMES`; test: an env file with
  `RUSTERM_DART_KEY=x` → `load_env()` puts it in the environment;
  `rusterm status` and the desktop key view list it (name + origin,
  never the value);
- guard test: every `RUSTERM_*` name read anywhere under `rusterm/`
  (grep for the literal) is in `ENV_NAMES` — red on the parent commit.

## A5. One default catalog for the CLI and the window

- CLI `--root` default is `"."` (`cli/__init__.py:2255`); the window and
  `rusterm desktop` default to `$RUSTERM_DATA` or `~/.rusterm`
  (`store/paths.py:default_root`, `cmd_desktop` drops `"."` on purpose,
  `:1383`). `cd ~/equitylab && rusterm add … && rusterm desktop` opens a
  different base than the one just written.
- Measured cost: the coordinator measured `~/.rusterm` (a schema-43
  leftover) instead of `/Users/anton/equitylab` in round 100 and built
  TASK-77 on it (CONTEXT, «two coordinator errors»).

| Precedence (one function in `store/paths.py`, used by `cli.main`, `rusterm desktop`, `python3 -m rusterm.desktop`, `app_entry.py`) |
|---|
| 1. explicit `--root` |
| 2. `RUSTERM_DATA` (environment or `~/.rusterm.env`, see A4) |
| 3. `./rusterm.db` exists in the current directory → `.` |
| 4. `~/.rusterm` |

**Done when:**
- a table test for the four rows; grep: no other default for the data
  root remains (`default="."` gone from the parser);
- `rusterm status` prints `каталог данных: <path> (правило: <1-4>)`;
  the window header shows the same line;
- report gives the user one line for `~/.rusterm.env`:
  `RUSTERM_DATA=/Users/anton/equitylab`.

## If all is closed

Take the next task in numeric order.
