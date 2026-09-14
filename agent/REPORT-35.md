# REPORT-35 — TASK-35: three free models measured on the chat task

Arrival state: selfcheck OK at 68dde89 (13/13); full suite 675 passed,
1 skipped, 6 deselected, 4 xfailed, 0 failed.

## Done

### G5 — extraction stops turning a table into digit soup (DONE, taken first)

- `rusterm/manual/extract.py` `_html_to_text`: `<td>`/`<th>` now emit
  a TAB at the cell boundary — the same convention the docx and xlsx
  paths already used ("\t".join). The verify string law is untouched;
  whitespace normalisation inside the comparison — none.
- Effect on the SAME four recorded tables, SAME pipeline, SAME
  deterministic control, one fresh model run (4 calls):

| table | records | verified | unverified | near_miss | dropped | facts stored |
|---|---|---|---|---|---|---|
| table1_clean_two_column | 0 | 0 | 0 | 0 | 2 | 0 |
| table2_ten_column_fleet_by_class | 36 | **36** | 0 | 0 | 0 | 36 |
| table3_with_total_row | 45 (36+9 Total) | **45** | 0 | 0 | 0 | 45 |
| table4_footnote_in_number | 9 | **8** | 1 | 1 | 0 | 8 |

  verified > 0 on table2 and table3 as ordered. table4's footnote
  marker is NOT silent: the "210(3)" record is stored unverified with
  a near_miss status — a named outcome (its value cannot pass the
  value check), and "Voyage days = 4" mirrors the corrupt cell
  verbatim — the corruption is in the fixture row (11 cells for 10
  columns), faithfully preserved.
- **verified-but-wrong, re-counted per ruling 1: 0 of 89 verified
  records** (36+45+8) — every verified record names the value its
  cell shows; the vacuous flag from TASK-34 F2 is cleared. table1's
  two dropped records: the two-column shape yields no
  category-quotable record — counted, not hidden.
- Offline replay: the F4 fixture (recorded BEFORE the fix) still
  replays the whole pipeline offline — its soup quotes now honestly
  fail against the fixed tab-separated text (36 stored, 0 verified,
  0 facts); the test docstring names the pre/post-G5 distinction.
- New test: `test_stage1_preserves_cell_boundaries` (tab between
  cells on all four fixtures; "12\t365" present; "12365" absent).
- Model calls: 4 (one per table); free tier glm-5.3-flash. STATE
  ledger: 12 of 200 for the task budget (8 were TASK-34's).
