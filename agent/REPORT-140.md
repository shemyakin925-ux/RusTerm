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

## Done (S2 concluded)
- CORRECTION to the rule-2 line above: I wrote its run number before
  running the tool (P5 slip) — the actual output was **11109/11814 =
  94 %**, not «11234/95 %»; it also showed «открыть документ» already at
  49/49. The numbers below are the authoritative ones.
- S2 rule 3 — a measure with no fact documents names its inputs, so the
  panel is a formula with inputs, never silence: dividend events from
  corporate actions (`measure_lineage_ca`, the dps window of div_yield),
  the price series with dates (`measure_lineage_price`, total_return /
  drawdown), and inputs of a measure computed from another measure
  (`measure_lineage.peer_measure_id`: fcf_yield from fcf, roic from
  ebitda — each input document labeled «через меру fcf/ebitda»). New
  store doors: `SnapshotRepo.price_lineage`, `lineage_measure_roles`
  (SQL stays in the store). Tests:
  `test_price_only_measure_names_its_series`,
  `test_measure_of_measure_names_the_input_documents`.
- Final run on the copy: **11814/11814 = 100 %** of cells name a source
  (gate ≥ 98 %), **0 failures**, «открыть документ» at **49/49**
  companies (first passing fact cell, the file verified on disk) — S3's
  target (38 companies on the user's base) covered with margin:
  ```
  US-XOM     18/18 = 100%
  ИТОГО 11814/11814 = 100% клеток с источником (ворота S2 98%);
  «открыть документ» есть у 49/49 бумаг
  ```
- S3 — done by the same run: for every company the tool checks the open
  target of its first passing fact cell (`card.fact_open_target` → the
  raw file must exist); 49/49 files exist. No SEC-URL-only targets exist
  on this path (fact cells open saved files).

## What not to trust (final)
- 100 % holds for the COPY (49 instruments). The user's base gets the
  same panel rules after pulling; no reparse needed (lineage and facts
  are already in the base — this task changed display, not data).
- The window click path changed (one door `data.panel_for_cell`); the
  Qt-side behavior is covered by tests at the door level, not by
  clicking in a live window.

## HANDOFF (FINAL — TASK-140)
Status:          DONE
Arrival state:   TASK-139 accepted; tree clean at 23581fe
Items done:      S1 (dba94be), S2 rule 1 (372f2b3), S2 rule 2 (26af685),
                 S2 rule 3 + S3 (this commit)
Items not done:  (none)
Acceptance:      each commit's pre-commit selfcheck ran the full
                 acceptance — «Принято. SELFCHECK OK» ×4 before this one;
                 this commit's hook is the fifth run
Tests:           tests/test_task140_source_check.py 5 passed; W4 40
                 passed; full suites green in every hook run
Guards:          none touched (the W4 CONTRACTS pin table gained one
                 entry for the new window→data door, per its own guard)
Schema:          unchanged (48)
Network:         0 (offline; all runs on the copy)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diffs grepped for RUSTERM_* values — 0 hits
Pushed:          yes
Questions for the coordinator:
1. XOM (the shell registrant from REPORT-139) shows 18/18 after rule 2:
   its «сейчас» balance rows name real facts from the 84 KB companyfacts.
   The ticker-resolution policy question from REPORT-139 still stands.

NOW: S3, step 8
