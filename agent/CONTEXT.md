# CONTEXT — the project in one file

Read this **instead of** re-reading `README.md`, `docs/` and old
reports. It is maintained by the coordinator and updated at every
acceptance. If it disagrees with the code, the code is right and this
file is a bug — say so in your report.

Last updated: 15.09.2026, after accepting TASK-31 on `agent/night-11`
(acceptance 13/13, exit 0). The shift branch is `agent/night-11` and the
turn is passed by the relay — `agent/PROTOCOL.md` §12, driver
`agent/relay.py`, baton `agent/BATON.json`.

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

| Milestone | State after TASK-31 (`agent/night-11`, not yet merged to `main`) |
|---|---|
| M1-M4 core, snapshot, watchlist | done and in use |
| M5 LLM layer | citation guard, four read-only tools, confirmed mass ops |
| M6 CA + OTC | both collected through EDGAR |
| M7 industry aggregate | done |
| M8 six markets, manual import | registry of six; US/CA/OTC collect, KR needs its key, BR/AU have providers but **no `ingest` channel** |
| M9 quotations | **real vendor rows**: AAPL 5000 daily closes 2006-10-25…2026-09-11 in one request, cached by a key-free URL, second run costs 0 requests; vendor failures named (`source_unreachable:http_403`, `vendor_rate_limited`, `source_unreachable:transport`); **the free tier sends no `adjusted`** (ADR-0019) and **`price_adj` applies dividends only** — the vendor `close` is already in today's share base (ADR-0020, three anchors); corporate actions collected from the vendor (splits + dividends) with provenance; `rusterm cadence` is a CLI command and a doctor line (TASK-31 C5); schema **42** |
| M10 industry inputs | `hhi`, physical inputs, two sectors, industry screen |
| M11 governance | producer, grey reasons, proxy through manual import — **five indicators still grey for every issuer** (TASK-32, 33) |
| M12 chat | loop, citation guard, adversarial corpus, ADR-0016 — **no TUI screen, no transcripts, no model comparison** (TASK-35, 36, 37) |
| M13 debts | single door wired, `manual_near_miss` split, selfcheck reads its count |

Data reaching a user today: **US 10 measures of 10 plus real prices; CA 3/10; OTC 3/10**
(all three through EDGAR). Everything else is a named refusal.

## 5. Keys (all free — ADR-0018)

`RUSTERM_SEC_UA` (a contact string, not a key), `RUSTERM_DART_KEY`,
`RUSTERM_TWELVEDATA_KEY` (free tier: 8/min, 800/day),
`RUSTERM_LLM_API_KEY` (OpenRouter, free models). Loaded from the
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
untrusted text · 0017 lane merge rule · 0018 **everything is free** · 0019 no vendor `adjusted` on the free tier, the correction is ours alone · 0020 **the free `close` is already split-adjusted** — never apply splits twice, dividends only (narrows 0019).

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
