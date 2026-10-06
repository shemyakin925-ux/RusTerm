# TASK-136 — С6: export to Excel

- **Status: READY**
- **Report:** `agent/REPORT-136.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С6. Queue rules: `agent/TASK-131.md`.
- **Last on purpose:** user 03.10 excluded Excel from the MVP; PRODUCT.md
  (approved 06.10) has it as С6. Take it only if its status is still READY.
- **Budgets:** network 0, LLM 0. `openpyxl` (free, MIT) may be added to
  the `desktop` extra in `pyproject.toml`.

## X1. «В Excel» for the card (first)
Button «В Excel» next to the existing export buttons. Saves the card
exactly as shown (`card.card_view`): sheet «Карточка», sections as bold
rows, Russian names in column A, years old→new, «сейчас» last, numbers as
numbers (not text) with number formats (млрд shown via format, value
stored in full), «—» as empty cell with a comment holding the reason.
Second sheet «Источники»: label · year · document · period · locator.
**Done when:** test — export a fixture card, reopen with openpyxl:
section rows bold, B-column header is the oldest year, a money cell is
numeric, a dashed cell is empty with a comment.

## X2. «В Excel» for peers
Same button on «Аналоги» (TASK-132) exports the peer table with the
median row.
**Done when:** test — reopened sheet has n+1 data rows, last row
«Медиана группы».

## X3. Old csv/md/png buttons
Keep png. Replace «экспорт csv» / «экспорт md» with the single «В Excel»
unless a test proves a user path depends on them (then keep and say so in
the report).
**Done when:** look.py: the export row shows «В Excel» and «график в png».

## Do not
Same list as `agent/TASK-131.md` «Do not».
