# TASK-105 — harness and docs: rulings on REPORT-103 Disputed (part 2)

- **Status: READY**
- **Report:** `agent/REPORT-104.md` (same round as TASK-104).
- **Budgets:** network 1 (Q14 recording), LLM 0.
- **Queue:** right after TASK-104, same round.

РАЗРЕШЕНО ПРАВИТЬ: docs/adr/0023-qt-tolko-v-sloe-interfeysa.md

## Rulings

| # | Ruling | Item |
|---|---|---|
| 9 | `census --rebuild` may write; say so | R1 |
| 11 | `PYINSTALLER_CONFIG_DIR` for the build subprocess | R2 |
| 14 | extend the recording by one request | R3 |
| 17 | coordinator points the baton at the task actually worked; no work | — |
| 18 | `-m live` restores the real env file, like HOME | R4 |
| 19 | restate as a per-concept pin | R5 |
| 24 | amend ADR-0023: the window may start core commands (collect via `rusterm follow`); it never writes directly | R6 |

## R1. census says it rebuilds
Help text and docstring of `cmd_census --rebuild`: «пересобирает снимки
(пишет в базу)»; without `--rebuild` it stays read-only.
**Done when:** test — `census` without `--rebuild` leaves the DB byte-identical.

## R2. firsthour build stays inside tmp
Build subprocess gets `PYINSTALLER_CONFIG_DIR=<tmp>`; `HOME_ALLOWED` unchanged.
**Done when:** `pytest -m firsthour` green, substituted HOME holds only `EquityLab/`.

## R3. Offline window reaches a governance colour
Record `dei:EntityCommonStockSharesOutstanding` for the AAPL fixture
(1 request, sanitized like the others); re-point the graduation tooth
back to `colours != {"gray"}`.
**Done when:** that tooth green offline.

## R4. Live tests see the real env file
`_isolated_rusterm_env` keeps `RUSTERM_ENV_FILE` real when the markexpr
selects `live` (mirror `_p7_isolated_home`). Keys never printed.
**Done when:** test on the fixture logic (no network).

## R5. G4 pin restated per concept
`test_g4_payload_taxonomy_us_gaap_wins_and_ifrs_parses` → per-concept
assertion, `xfail` removed; declared pin replacement.
**Done when:** it passes without xfail.

## R6. ADR-0023 names the one allowed path
One sentence: the window may start core commands (collect =
`rusterm follow` in a worker); arithmetic and direct DB writes stay out
of the interface layer.
**Done when:** acceptance check 10 green; ADR diff is that sentence only.
