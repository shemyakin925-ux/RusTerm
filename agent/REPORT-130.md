# REPORT-130 — С2: fill the control ten to ≥ 90 % (concept-map gaps)

## Done
## Blocked
## What not to trust
## Disputed
## Runs
## HANDOFF
Status: NOT STARTED
# REPORT-130 — TASK-130 (C2: card fill ≥ 90 %)

Executor: GLM 5.3, night of 07.10.2026. Branch `agent/night-11`.
Base copy: `/tmp/rt-task130` (sqlite .backup of `~/EquityLab/data/rusterm.db`,
never touched the original), `history --all --rebuild` run on it.

Arrival: selfcheck 13/0 at `dcae6f6` (TASK-111 U3 commit landed before this
task; see REPORT-111). Baseline measured:

```
US-JPM 100%  US-BAC 91%  US-DELL 97%  US-HPQ 94%  US-AAPL 96%
US-MSFT 99%  US-T 78%    US-AA 59%    US-FCX 95%  US-ORCL 63%
ИТОГ 1389/1614 = 86% (цель 90%)
```

## Done

### K1 — the missing tag behind each gap (no code)

Method: for every gap line of `tools/card_fill.py` the raw facts of the
company were queried (`fact.concept` with `canonical_concept IS NULL`,
`superseded_by IS NULL`, `status='ok'`), values matched against the
10-K line they carry. One base for the whole task: 1.11 M facts carry no
`concept_map_version` at all (ingested before v4/v5) — a **reparse** is
required for any map addition to reach them (K2 does it).

| concept | company | tag (us-gaap) | 10-K line it matches | value (proof) |
|---|---|---|---|---|
| cogs | AA | `CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization` | «Cost of goods sold (exclusive of expenses shown separately below)» | FY2021 9 153 M |
| cogs | T | `OtherCostOfOperatingRevenue` | «Operating expenses: Cost of revenues» | FY2024 27 032 M |
| cogs | ORCL | not in the filing | Oracle reports expense components (cloud/license support, hardware, services), no COGS line; mapped `CostOfRevenue` stops 2011 | — |
| dps | AA | `CommonStockDividendsPerShareCashPaid` exists, **do not map**: annual windows carry the quarterly rate (FY2023 = 0.10 while 4×0.10 was paid) — mapping would serve dps 4× understated | «Cash dividends declared per common share» | Q 0.10, FY window also 0.10 (contradiction) |
| dps | BAC | facts exist (`CommonStockDividendsPerShareDeclared`) but with `period_start = period_end` = declaration dates (2023-02-01, 04-26, 07-19, 10-18; 0.22/0.22/0.24/0.24) — the dps TTM window wants periods, so it refuses; fix = K4 | «Dividends declared per common share» | 2023 sum 0.92 |
| dps | ORCL | mapped `CommonStockDividendsPerShareDeclared` stops 2011; no unmapped per-share tag since | not in the filing (in stored facts) | — |
| operating_income | AA | not in the filing | AA income statement has no operating-income subtotal (2021 dump: Sales → COGS → SG&A → R&D → D&A → restructuring → interest → pretax); no `OperatingIncomeLoss` facts at all | — |
| pretax_income | ORCL | not in the filing (stored facts) | only the Domestic/Foreign split is tagged (`IncomeLossFromContinuingOperationsBeforeIncomeTaxes{Domestic,Foreign}`); the combined line is absent | — |
| total_debt | ORCL | `DebtLongtermAndShorttermCombinedAmount` — **already mapped** (us-gaap.v5, ТЗ-108 W2), but 245 facts predate the map → reparse | «Debt» (notes payable, total) | FY2023 90 481 M, FY2024 86 869 M, FY2025 92 568 M |
| total_debt | AAPL 2021 | not in the filing as one tag: term debt 118.1 B is `DebtInstrumentCarryingAmount` (per-instrument tag, lookalike risk), commercial paper 6.0 B separate; `LongTermDebt` resumes only 2022-06-25 | «Total term debt» + «Commercial paper» | 118.1 + 6.0 B |
| total_equity | T | no parent-only tag; T files only `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` (+ `MinorityInterest`); fix = identity incl_nci − NCI in the capital assembly | «Total stockholders' equity» − «Noncontrolling interest» | FY2024 118 245 − 13 873 = 104 372 M |
| total_equity | AA 2025 | same shape as T at 2025-12-31: incl_nci 6 118 M, no plain tag, no NCI at the date | «Total stockholders' equity» | 6 118 M |
| eps_diluted | FCX 2022–25, DELL 2022 | no annual EPS facts in the filing feed (quarterly + YTD only); FY EPS from quarters would be a per-share sum — refused | — | — |
| invested_capital inputs | AA 2024–26 | **guard defect, not a tag**: `unmapped_current_investments` (repos.py) middle arm `LIKE '%MarketableSecurities%Current%'` has no `Noncurrent` exclusion and SQLite LIKE is case-insensitive — `MarketableSecuritiesNoncurrent` (AA files it 2024+) blocks the legitimate st_investments = 0 | balance has no current investments line | — |
| st_investments | T, AA, ORCL | legitimately zero (`st_investments_never_reported: us-gaap balance`, coordinator's 06.10 rule) | — | 0 |
| effective_tax | AA | honest «—»: computed rate −5.17 % is outside the plausibility band (`jurisdiction_rate`) — Alcoa's one-off-heavy years; Yahoo shows the same wild rates | — | — |
| effective_tax | ORCL | blocked by pretax_income (above) → «—» | — | — |
| invested_capital/roic | HPQ 2021–23 | 2021: year snapshot assembles through `_issuer_inputs`, where the 1100-day staleness door eats `minority_interest` (last 2016) and `st_investments` (last 2009) before the zero-rules can answer; 2022+ take another path and compute | — | — |

Expected honest gain: T 78→~93 %, AA 59→~69 % (capped: operating income,
dps, effective tax are structurally absent or unusable), ORCL 63→~69 %
(capped: pretax, cogs, dps absent), BAC 91→97 % (K4). Total ≥ 90 % is
reachable; **every company ≥ 80 % is NOT reachable honestly for AA and
ORCL** — evidence above, coordinator's call in Disputed.

NOW: K1 done, step 5

## HANDOFF (FINAL — пауза по приказу пользователя, 07.10)

```
Status:          PARTIAL (K1 done; K2 (1/2) committed; K2 (2/2) staged, tests green, hook commit not yet run)
Arrival state:   selfcheck 13/0 at dcae6f6 (after STEP 0: U3 commit + rebase)
Items done:      K1 (aeb6335); K2 1/2 (868da63: map us-gaap.v6 + stinv guard Noncurrent; reparse 1219 facts; fill 86%→89%, T 83, AA 65, ORCL 79)
Items not done:  K2 2/2 STAGED (equity identity incl_nci−NCI; tests green incl. TЗ-56 Z2 pin; VZ replay pin updated; commit blocked only by the pending selfcheck hook — on resume: cp /tmp/commit-msg-k2c.txt .git/COMMIT_EDITMSG && git commit -F /tmp/commit-msg-k2c.txt, the files are already in the index). K3, K4, K5 — designed, not started. Reparse+rebuild+measure after K2 2/2, look.py pass, final fill paste.
Acceptance:      last full hook run: Итог 11/2 (K2c blockers found: c2 map pin + GUIDE v5→v6 — fixed in 868da63; then 13/0 for K2 1/2). K2c selfcheck NOT run (user pause).
Tests:           targeted green: test_task130_k2_equity_identity 4/4, test_task56_z2 7/7, test_task96_r3_replay green after pin, stinv/guard/map tests green
Guards:          repos.py unmapped_current_investments — middle arm gained Noncurrent exclusion (stricter); snapshot.py _stinv/identity doors unchanged for all previously-green cases; no guard files touched
Schema:          unchanged (48)
Network:         0 of 0
Model:           GLM 5.3
Secrets:         no keys touched
Pushed:          yes up to 868da63 (K2 1/2); K2c sits in the local index ONLY
Questions for the coordinator:
1. PRODUCT C2 gate "каждая компания ≥ 80%" недостижим честно для AA (~69%) и ORCL (~69%): в их 10-K нет строк operating income / pretax / COGS / dps — таблица доказательств в разделе K1. Предлагаю: либо считать их мерами «не применимо к этой отчётности» (скрыть, как у банков), либо принять потолок с причиной. Решение — за вами/пользователем.
2. AA dps: тег CommonStockDividendsPerShareCashPaid подан годовыми окнами с квартальной ставкой (FY2023 = 0.10 при 4×0.10) — мапить нельзя (4× занижение). Оставил «—».
```

NOW: K2 (2/2) staged, awaiting user resume

## ПОПРАВКА к HANDOFF (07.10, сразу после паузы)

`git commit` книги состояния (4efdc3e) без pathspec забрал и staged-файлы
K2c — код тождества капитала уехал в коммит раньше объявления. Содержимое
проверено вручную тем же селфчеком (bash agent/selfcheck.sh, выход 2):
pytest — из красных только test_i5_staged_and_authorised_widening_is_green
и test_i5z_demonstration_ran (известная инфраструктурная пара I5 из
BATON: вложенный полный селфчек) и
test_report_sections::test_last_handoff_does_not_call_committed_items_undone
— страж отчёта справедливо поймал сам текст HANDOFF выше: «K2c in the
local index ONLY» стало ложью в момент, когда 4efdc3e содержал K2c.
Этой поправкой текст исправлен; факты: код K2c в 4efdc3e, целевой
селфчек 13/0 не получен ни разу на этой голове (11/2 с двумя I5-красными
и одним красным самого стража отчёта), приёмка на возобновлении — первым
же хук-коммитом.

NOW: paused; K2c content in 4efdc3e, K3–K5 not started
