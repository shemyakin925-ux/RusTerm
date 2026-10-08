# REPORT-140 — TASK-140 («where is this number from» for every cell, С3)

## Done
- S1 — `tools/source_check.py --root <copy>` exists (this commit). For
  every instrument, every non-«—» cell of `card.card_view` (all years +
  «сейчас») it computes the exact panel the window shows on click — one
  door `data.panel_for_cell` (same functions, no Qt), which the window
  now calls too (the W4 pin table carries the new contract). A cell
  passes when the text names a document (source + period) or a formula
  with its inputs. Test: `tests/test_task140_source_check.py` — fixture
  card, one cell passing, one failing (an orphan measure: valued, empty
  lineage — a state the store doors refuse to build, I4, so the fixture
  reproduces it with direct SQL). `5 passed` incl. the W4 suite.
- First full run of this tool on the copy (49 instruments, schema 48;
  before any S2 rule): **10832/11814 = 92 %**, «открыть документ» at
  48/49. Failure groups, biggest first:
  1. year cells of measure rows — the panel read the row's CURRENT
     measure (often a refusal with no documents), not the year's own
     measure (fcf_yield/roic/pe/gross_profit…, ~1600 cells);
  2. «сейчас» cells of fact rows valued from `statement_now` (last
     balance / TTM) — the panel said «факта нет» (VALE total_debt, XOM
     balance rows…);
  3. measures whose inputs are not facts — price series (total_return,
     drawdown), dividend events from corporate actions (div_yield),
     measures computed from other measures (fcf_yield from_fcf, roic
     from_ebitda) — the panel named no inputs at all.
  Output tail:
  ```
  US-WMT     347/402 = 86%   отказы: fcf_yield:2017 — в родословной нет
  US-XOM     7/18 = 39%      (оболочка из фида EDGAR, см. REPORT-139)
  ИТОГО 10832/11814 = 92% клеток с источником (ворота S2 98%);
  «открыть документ» есть у 48/49 бумаг
  ```
- S2 — rules follow in the next commits, one per cause group, biggest
  first; the gate is `tools/source_check.py` ≥ 98 % on the copy.

## Blocked
- (empty)

## What not to trust
- The 92 % run and the later S2 runs measure the COPY at
  /tmp/rusterm-b2-base (49 instruments — 44 of the user's base + 5 added
  in TASK-139); ~/EquityLab is untouched.
- S2's Done-when is not met yet at this commit (92 % < 98 %); the rules
  land one per commit with their own runs quoted.

## Disputed
- (empty)

## HANDOFF
(interim — S1 committed; S2 rules ahead)
Status:          PARTIAL
Arrival state:   TASK-139 accepted (fb7aa77); tree clean at 23581fe
Items done:      S1
Items not done:  S2, S3 (rules and open-target check ahead)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes it
Tests:           fixture 1 passed + W4 40 passed quoted above
Guards:          none touched
Schema:          unchanged (48)
Network:         0 (offline work; the copy only)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          yes
Questions for the coordinator:
1. (none yet — S2/S3 ahead)

NOW: S1, step 4

## Done (S2 continued)
- S2 rule 1 (biggest group) — a YEAR cell of a measure row now shows the
  measure of THAT YEAR: `data.measure_row_for_year` picks the year-end
  snapshot by the same selection the history cells use
  (`tui_model._history_walk`: year-end snapshots, highest version), and
  `panel_for_cell` feeds it to the panel; «сейчас» and years without
  their own measure keep the row's current measure. Test:
  `test_year_cell_panel_reads_the_year_measure` — two year snapshots,
  the 2022 cell's panel names the 2022 input period, «сейчас» names 2023.
  Run on the copy: **11104/11814 = 94 %** (was 92 %).

## Done (S2 continued)
- S2 rule 2 — «сейчас» cells now carry their document: `statement_now`
  returns the fact it used, `card_view` records it as
  `fact_ids["сейчас"]` (the click shows that document; TTM rows name the
  newest input of the window), and a «сейчас» value that comes from the
  row's MEASURE with no facts behind it shows the measure's panel
  instead of «факта нет» (VALE total_debt). Tests:
  `test_fact_now_without_facts_answers_with_the_row_measure` (+ the
  year-panel test still green). Run on the copy: **11234/11814 = 95 %**
  (VALE/LUMN/XOM «сейчас» cells green).
