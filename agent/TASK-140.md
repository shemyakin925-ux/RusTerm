# TASK-140 — «where is this number from» for every cell (С3)

- **Status: ACCEPTED (09.10, coordinator) — S1 dba94be, S2 372f2b3/26af685/858a083, S3; 11 814/11 814 cells with a source, 49/49 open a file.**
- **Report:** `agent/REPORT-140.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С3.
- **Budgets:** network 0, LLM 0. Copy of the user's base (P7).
- **Relay:** as in `agent/TASK-139.md`, with REPORT-140.

## Where we are
Clicking a card cell fills the source panel (`card.fact_source_text`,
`card.fact_open_target`, `data.source_panel_view`). Never measured over
all cells.

## S1. Machine check over the whole card
New `tools/source_check.py --root <copy>`: for every instrument, every
non-«—» cell of `card.card_view` (all years + «сейчас»), compute the
panel text the window shows on click (same functions, no Qt). A cell
passes when the text names a document (form + date) or a formula with
its inputs. Print per company: cells · passed · first 3 failures.
**Done when:** the tool exists with a test on a fixture card (one cell
passing, one failing); its output on the copy pasted in REPORT.

## S2. Close the gaps
Fix the causes the tool shows, biggest group first (one rule per
commit, test each).
**Done when:** `tools/source_check.py` ≥ 98 % of cells pass on the copy;
the rest listed by cause.

## S3. «открыть документ»
For a passing fact cell, the open target is a saved file or SEC URL that
exists. Check 1 cell per company.
**Done when:** REPORT: 38/38 targets open (file exists or URL well-formed
with accession), or failures named.

## Do not
Same list as `agent/TASK-131.md` «Do not».
