# REPORT-97 — работа координатора переходит к тебе: отрасли, честность мер, ядро снапшота

## Done

| Item | What shipped | Proof |
|---|---|---|
| Q12-5 | Tier refusal on `/splits`/`/dividends` no longer kills the quote stage. `providers/twelvedata.py`: `PLAN_REFUSAL_REASONS` + `is_plan_refusal()` — the shape of a vendor refusal stays vendor knowledge, not CLI knowledge. `cli/_ingest_twelvedata_actions`: the two payloads are now fetched independently — a plan refusal is remembered and the loop continues, so an endpoint that answered is still parsed, written and cached; gate usage is recorded once per stage; the stage returns 0 with the note «недоступны на бесплатном тарифе Twelve Data (ADR-0018) … повтор заплатит тот же 403, поэтому он не совет». Every other reason (429, transport, 5xx, bad JSON, `BudgetExceeded`) still fails the stage exactly as before. A refused call is counted as spent in the stage's own «запросов» line, and refused payloads are never cached — so the note re-appears on the next run instead of a silent "0 written". | `tests/test_task97_q12_ca_plan_refusal.py`: 12 tests, red-before 7 failed / 3 passed, green-after. Mutations M1-M5 (Runs 4). Focused batch and whole suite: Runs 5-7. |
| Q12-6 | `rusterm reparse` rebuilds **facts** from stored raw payloads, not only `basis`. `store/repos.py`: `companyfacts_sources()` (an `EXISTS` filter — its own blind spot: an object that contributed no fact was never visited) replaced by `companyfacts_objects()` (every stored companyfacts object) plus `count_for_source()`. `core/reparse.py`: `rebasis_companyfacts` → `rebuild_companyfacts`; per object the owner is resolved instrument → issuer (never guessed), the payload is re-read and re-parsed by the current parser, and stored rows are keyed by `locator.json_pointer`. An unseen pointer means a new fact through the same doors `ingest` uses (`apply_concept_map` + `persist_ingestion_results`, one write transaction per object); a seen pointer means `basis` aligned if it differs. Rows whose locator carries no pointer are counted (`unlocatable`) and left alone rather than re-inserted; ownerless objects are counted and named. `cli/cmd_reparse` prints added / unmapped / ownerless / unlocatable and points at the snapshot rebuild. | `tests/test_task97_q12_reparse_facts.py`: 10 new tests, Runs 8-10. Mutations M1-M7 (Run 9). Copy of the user's base (Run 11): 414 facts added, refusals 8 → 2 in the newest snapshot of every paper. `tests/test_reparse_basis.py`: 6 call sites renamed, every assertion kept (Run 10). |
| Q11 | Default data root (rule 4) is the folder the user actually built: `~/EquityLab/data` (measured in his HOME before the edit — `app/ data/ backups/ archive/`, base in `data/`). Only the **value** changed; rule numbers and ТЗ-90 A5's upper rules are untouched. `AppPaths.backups` = sibling of the data root, and the property creates nothing. `backup` without a named path writes `backups/<date>[-label].zip`; `--label` must fullmatch `[\w.\-]{1,40}` with no `..` and no leading dot, so a label cannot be a path. Both `--root` help lines, the desktop help, `env.py` and `desktop/{__main__,window,data}.py` name the new default, and GUIDE's copy of the old path went with them. **`store/db.py` could not be rewritten**: guard P2 (`agent/selfcheck.sh:129`) counts every removed line of that file as something only a `_SCHEMA_VERSION` bump may do, and this item changes no schema — so the historical sentence in `has_table`'s docstring stays, one added line names it as history, and the grep tooth lists that single surviving line by content instead of excluding the file (Run 19, Disputed 4). Suite-wide HOME isolation: one sandbox HOME per session, live runs exempt (they need the user's real keys file), and children get this process's under-HOME `sys.path` entries through `PYTHONPATH`. | `tests/test_task97_q11_home_clean.py`: 12 teeth, red-before 8 failed / 1 passed (Run 14). Mutations M1-M8, each red on exactly the named teeth (Run 15). Whole suite: Runs 16-20. The Done-when guard is a session-teardown assert — any extra entry in the sandbox HOME makes the run rc≠0, so acceptance sees it (verified by M7/M8, not by prose). |
| Q10 | One window function for every flow input. `rusterm/core/ttm.py::ttm_window` is called once per build in `_issuer_inputs`, on rows already behind the `as_of` door and the staleness rule — no second query, no second door. Corridors in order: four consecutive quarters → `FY + YTD − prior-year YTD` → last annual; nothing filed after the annual means **the annual *is* the window** (`period_basis='ttm'`, ADR-0025 clause 2). When the window falls back to the annual the basis is named `annual_fallback` (migration 46 widens the `period_basis` CHECK in `measure_lineage`/`measure_lineage_ca`), and the reason — which addend is missing, by concept and period — rides in the lineage role, in `rusterm snapshot` output and in the source panel. All flows of one measure come from **one** window: `flow_window` compares span, currency **and basis** (equal dates on different bases is still a mix — measured on the user's base, where JPM `net_margin` carried `input:ttm` beside `input:annual_fallback`), so such a measure takes the last common annual period of its inputs and says so in the same mark. Balance-sheet inputs of two-period measures are looked up strictly at the window borders; no stock on a border → `period_mismatch`, not a number read off another date (measured: ORCL/AAPL/JPM file year-end balances only in basis `restated`, and `as_reported_facts()` admits `as_reported`). `dps` now goes through the same function — `_dps_quarterly_ttm` and `_dps_annual_from_facts` are deleted. ADR-0025 refines ADR-0021: its clause 1 becomes the fallback, its `period_basis` clause grows. | `tests/test_task97_q10_ttm_window.py`: 21 teeth (corridors, adjacency, dedup, the `as_of` door, both fallback shapes); red-before is that the module did not exist (Run 21). `tests/test_task97_q10_measure_ttm.py`: 13 teeth, red-before per group (Run 22), plus the basis-mix tooth red before the fix (Run 23). Mutations M1-M11 on the window (Run 8 of the item's battery) and N1-N6 on the wiring (Run 24) — 17/17 red on the tooth each names. Measurement on a copy of the user base (P7): Runs 25-27, migration 46 proven there. Whole suite: Run 28. |
| Q8 | Industry comparison gets one window instead of a veto. `_PERIOD_GAP_DAYS = 100` is deleted from both industry paths and replaced by `core/peers.py`: `INDUSTRY_PERIOD_WINDOW_DAYS = 730` plus `period_window(ends)`, which returns the included, the excluded and the range of the included — measured from the **newest** period end, because "this member is stale" is about the member, not about the set being re-dated by one new report (a member exactly 730 days old stays in; 731 leaves). `core/industry/aggregate.py`: excluded members are dropped from that concept's values, `AggregateMeasure` carries `period_from`/`period_to`/`excluded`, and `_with_window` records `period_out_of_window` in `reason_counts`; `period_note()` is the single formatter («периоды от … до …», «вне окна: US-VALE (2012-12-31)») reused verbatim by `rusterm industry` (text and `--json`), the TUI screen and `desktop/data.industry_table_rows`, so the Qt «Отрасль» tab carries the same words in its `mark` column. `core/snapshot.py` pass 2: the same window filters `peer_measures`, the percentile row's own `period_start`/`period_end` carry the range, an excluded peer is named in the lineage role (`peer: вне окна <iid> <end>`, readable through the new `SnapshotRepo.lineage_roles`), marked in `peer_set_member.reason` by the same upsert that writes `excluded_stale`, and surfaced in the new `BuildResult.excluded_period`, which `rusterm snapshot` prints. No schema change, no new reason code (`reasons.py` is closed): `period_mismatch` simply stops being emitted in these two places — the measure-input alignment that still uses it is untouched, and `docs/` is untouched because Q10's ADR-0025 is «единственная разрешённая правка docs/». Where the window takes the set below I6 the existing `peer_set_too_small` refusal stands, and now names the excluded. | 9 teeth in `tests/test_task97_q8_industry_window.py`; red-before on HEAD sources 10 failed / 4 passed (Run 30 — the tenth is the re-pointed J3 test), green-after 14 (Run 31). Mutations M1-M3, each red on exactly the teeth named (Run 32). 21 neighbour suites green, 234 tests (Run 33). Copy of the user base (P7): five sectors was→стало, same database under both codes (Runs 34-35), percentiles with a value 129 → 170 and all 152 `period_mismatch` refusals gone (Run 36); the rebuilt copy read by both codes is Run 37, whole suite Run 38, commit `41bddba` with the acceptance inside its pre-commit hook — `Итог: пройдено 13, провалено 0` (Run 39). |

Q12-5: three pre-existing tests encoded the overturned expectation and were
updated to the verdict, assertion by assertion — nothing was deleted, no
xfail, no marker:

| Test | Was | Now | Still asserted |
|---|---|---|---|
| `test_c3_actions.py::test_vendor_failure_leaves_actions_empty_with_named_reason` | 403 on both endpoints → `code == 1` | `code == 0` + the reason must be in the note on stdout | `corp_action.all("US-X") == []` (K7: a vendor refusal is a value, not an invention) |
| `test_task96_r3_refused_calls.py::test_refused_splits_are_still_counted` | `_ingest == 1`, transport called twice (`/dividends` never asked) | `_ingest == 0`, calls `["time_series", "/splits", "/dividends"]` | `_requests_used == len(calls)` — and it holds on the new path with 3 calls, one gate record |
| `test_task96_r3_refused_calls.py::test_refused_dividends_after_successful_splits_are_counted_once` | `_ingest == 1` | `_ingest == 0` | call list and the no-double-record sum (3 samples, not 4) |

Two teeth added on top of the verdict's minimum, because the new `continue`
path bypasses the old "record and return" line:
`test_a_refused_by_plan_call_is_still_counted` and
`test_a_hard_failure_is_counted_too` (ТЗ-96 R3's accounting invariant
re-asserted on both branches).

Q11: five incumbent teeth spelled the old default as a literal and were
moved to the new value — every replacement is one assert line for one assert
line (plus one literal inside an unchanged assert), and each is re-covered by
a stricter successor (the three removals are declared in the commit message
as `ЗАМЕНА-БУЛАВКИ`):

| Test | Was | Now | Added cover |
|---|---|---|---|
| `test_paths.py::test_default_rule_4_is_home` | `resolve_root() == (tmp_path/".rusterm", 4)` | same shape, `(home/"EquityLab"/"data", 4)` | the door test below checks what actually appears in HOME, not only the formula |
| `test_a5_one_default_catalog.py::test_the_four_row_table` | row 4 = `.rusterm` | row 4 = `EquityLab/data` | `test_the_upper_rules_still_win` re-proves rows 1-3 still outrank 4 |
| `test_a5_one_default_catalog.py::test_rule_3_only_when_the_base_actually_lies_there` | rule-4 fallback pointed at `.rusterm` | same assert, `EquityLab/data` | — |
| `test_a5_one_default_catalog.py::test_guard_no_second_default_for_the_data_root` | searched the package for the literal `home() / ".rusterm"` | searches for `home() / "EquityLab"` | the assert line itself is untouched; still exactly one file may hold the default |
| `test_b35_markets_readonly.py::test_writer_without_root_goes_to_the_home_rule_not_the_tree` | `(home/".rusterm"/"rusterm.db").exists()` and the printed `каталог:` line | same two asserts on `EquityLab/data` | `test_a_writing_door_creates_only_equitylab_in_home` also asserts HOME holds **nothing else** |

Q10: six incumbent teeth encoded the expectation this item overturns. Nothing
was deleted; each replacement keeps its subject in a stronger form and is
declared in the commit message as `ЗАМЕНА-БУЛАВКИ`:

| Test | Was | Now | Still asserted |
|---|---|---|---|
| `test_c2_six_measures.py::test_golden_units_currencies_and_periods` | `bases == {"annual"}` | `bases == {"ttm"}`, plus the window and the role must name that period | unit, currency and period of every golden measure; new assert that the role names its window |
| `test_j3_fiscal.py::test_facts_after_as_of_are_not_closed_yet` | `net_margin[7] == "2025-06-30"` (a fresh, unfinished period) | `== "2024-12-31"` (annual) + the mark names the period and the missing addend | the `as_of` door: a period ending after the date cannot enter the inputs |
| `test_task49_census.py::test_r2_lineage_names_source_and_period_basis` | `role == "input"` | an input with no basis keeps `input`; an input with a basis must start with `input:<basis> ` and name the window | the source of each measure (fact → the EDGAR answer by `source_ref`; inherited input → a measure of the same snapshot) |
| `test_db.py`, `test_cli.py`, `test_governance.py`, `test_j4_backup.py`, `test_upgrade_path.py`, `test_k1_price_schema.py` | pins of schema `45` | pins of `46` | everything else on those same assert lines, unchanged |

The measurement that found the third defect, and the "was → became" table the
item's Done-when asks for. Run on a **copy** of the user's base under
`/tmp/rt-q10-meas/data` (P7 — `~/EquityLab` was never written):

| Instrument | Measure | Before Q10 | After Q10 |
|---|---|---|---|
| ORCL (May FY) | `pe` | 25.5815 | 25.5815 — same number, basis now marked `annual_fallback` with the addend named |
| | `ps` | 6.4895 | 6.4895, same |
| | `net_margin` | 0.246058, window 2026-06-01…2026-08-31 (one quarter) | 0.253678, window 2025-06-01…2026-05-31 (a year) |
| | `asset_turnover` | 0.070538, window 2026-06-01…2026-08-31 | NULL `period_mismatch` (no stock at the window border) |
| AAPL (Sep FY) | `pe` / `ps` | 43.8399 / 11.7995 | same numbers, basis marked |
| | `net_margin` | 0.272252, window 2026-03-29…2026-06-27 (one quarter) | 0.269151, window 2024-09-29…2025-09-27 (a year) |
| | `asset_turnover` | 0.290097, window 2026-03-29…2026-06-27 | NULL `period_mismatch` |
| JPM (Dec FY) | `pe` / `ps` | 15.7407 / 4.9177 | same numbers, basis marked |
| | `net_margin` | 0.312419, window 2025-01-01…2025-12-31, lineage `ttm` **beside** `annual_fallback` | 0.312419, same window, **one** basis `annual_fallback` |
| | `asset_turnover` | NULL `period_mismatch` | NULL `period_mismatch` |

Counters on the copy:

- measures carrying a value, newest snapshot per instrument: **627 → 622**.
  The five lost are `asset_turnover`/`roe` on the three measured papers, which
  have no stock at a window border. Across all versions 3653 → 3775 —
  append-only accumulates rebuilds, it is not a gain in values;
- period bases on newest versions: `annual` 39, `annual_fallback` 22, `ttm` 8.
  Those 39 `annual` are snapshots that were never rebuilt (the label is
  written at build time); on the three rebuilt instruments no `annual` is left;
- per version, which is how the relabelling is proven rather than asserted:
  AAPL v1…v7 `annual` (2 measures) → v8…v10 `annual_fallback` (11);
  JPM v3…v6 `annual` (1) → v7 `annual_fallback` 4 + `ttm` 2 (the mix) → v8
  `annual_fallback` 4; ORCL v7…v9 `annual_fallback` 7;
- migration 46 on the copy: schema was 45, `[46]` applied, `measure_lineage`
  17030 rows before and after with identical content, `measure_lineage_ca`
  28 → 28.

Q8: one incumbent tooth states the overturned rule, so it is re-pointed
rather than duplicated (declared in the commit message as `ЗАМЕНА-БУЛАВКИ`):

| Test | Was | Now | Still asserted |
|---|---|---|---|
| `test_j3_fiscal.py::test_each_calendar_contributes_its_own_latest_closed_period` | 3 June-FY + 3 Dec-FY peers on `revenue`; the mixed calendar produced `null_reason='period_mismatch'` and the test asserted the refusal by name | same six calendars, `net_margin` instead of `revenue` (a percentile only exists where the company's own value of that measure is computed — `revenue` is never a computed own measure, so the old subject could not be carried over at 6 peers); the window now admits the 184-day gap: rows exist, `null_reason is None`, `value` is not None, and the row's own `period_start`/`period_end` are `2024-06-30`/`2024-12-31` | the June filer contributes its own latest closed period and is neither re-dated to December nor dropped — the range in the row is the proof, and the J3 alignment of one measure's inputs is untouched in the other four tests of the file |

The was→стало table the Done-when asks for, five sectors on a **copy** of the
user's base (P7 — `~/EquityLab` untouched). Both columns read the **same
database** (`/tmp/rt-q8-meas2/data`, a byte-copy of `/tmp/rt-q10-meas/data` in
the state Q10 left it, opened `mode=ro`) on the same date (`as_of=2026-09-24`)
and differ only by the code: "was" runs the sources of HEAD from
`/tmp/rt-q8-red`, "became" runs this worktree. `n` is the aggregate's own
count of contributions; a median is quoted where one is now computed.

| Sector | `net_margin` | `operating_margin` | `roe` | `asset_turnover` |
|---|---|---|---|---|
| software (9 members) | **0.2405 (n=9)** — was computed too, now the row names its range | **0.2743 (n=9)**, same | **0.0962 (n=9)**, same | **0.1642 (n=9)**, same |
| hardware_electronics (9) | **0.1591 (n=8)**, same | **0.1627 (n=8)**, same | was `peer_set_too_small` → `peer_set_too_small (no_value=4; периоды от 2026-06-30 до 2026-09-24)` | **0.3707 (n=8)**, same |
| banks (9) | was `period_mismatch` (n=6) → `peer_set_too_small (no_value=3)` | `peer_set_too_small (no_value=9)` — unchanged | was `period_mismatch` (n=8) → **0.0323 (n=8)** | was `period_mismatch` (n=5) → `peer_set_too_small (no_value=4)` |
| telecom (8) | was `period_mismatch` (n=7) → `peer_set_too_small (no_value=1)` | was `period_mismatch` (n=7) → `peer_set_too_small (no_value=1)` | was `period_mismatch` (n=4) → `peer_set_too_small (no_value=4)` | was `period_mismatch` (n=7) → `peer_set_too_small (no_value=1)` |
| mining_metals (9) | was `period_mismatch` (n=8) → `peer_set_too_small (no_value=1; … ; вне окна: US-VALE (2012-12-31))` | was `period_mismatch` (n=6) → `peer_set_too_small (no_value=3, same mark)` | was `period_mismatch` (n=6) → `peer_set_too_small (no_value=3, same mark)` | was `period_mismatch` (n=7) → `peer_set_too_small (no_value=2, same mark)` |

- the 20 cells by reason: was `period_mismatch` **11** + computed 7 +
  `peer_set_too_small` 2 → became `period_mismatch` **0** + computed 8 +
  `peer_set_too_small` 12. Of the 11 vetoed cells one is now a number
  (`banks roe`) and ten are now honest refusals that say what is missing —
  the window removes a wrong reason, it does not invent members;
- the window is named, not implied: every computed cell prints «периоды от …
  до …» in `rusterm industry`, in `--json` (`period_note`, `excluded`) and in
  the Qt «Отрасль» tab's `mark` column; the four mining cells say
  `period_out_of_window=1` and name US-VALE with its period end;
- where removing the veto exposes I6 instead of hiding it, the refusal stands
  and now says both parts — `banks net_margin`: «peer_set_too_small (no_value=3;
  периоды от 2025-12-31 до 2026-09-24)»;
- the same "became" column re-measured on the **rebuilt** copy
  (`/tmp/rt-q8-meas/data`, after `rusterm snapshot` on 44 instruments, all
  rc=0) gives 4 computed cells instead of 8 and different medians — that is
  Q10's clause 5 (no `as_reported` stock at a year-end border) reaching the
  whole sector once the snapshots are rebuilt, not the Q8 window: no cell lost
  a member to the 730-day rule except US-VALE. Recorded in Disputed 6.

Percentiles are written at build time, so their was→стало is one copy read
before and after the rebuild (`/tmp/rt-q8-logs/after-rebuild.log`, Run 36) —
the rebuild is part of the difference by the nature of the row, not by
sloppiness; the baseline 129/152 was reproduced independently on the untouched
second copy:

| Counter (newest snapshot per instrument) | Was | Became |
|---|---|---|
| percentiles carrying a value | 129 | **170** |
| percentile refusals | 285 | 115 |
| of which `period_mismatch` | 152 | **0** |
| `peer_set_member.reason='excluded_period'` | — | 1 (US-VALE) |
| lineage rows naming the exclusion (`peer: вне окна US-VALE 2012-12-31`) | — | 23 |
| `rusterm snapshot` outputs printing «вне окна периодов:» | — | 8 |

What is left after the rebuild is 115 refusals: 88 `currency_mismatch:
(blank), USD` (was 82) and 27 `currency_mismatch: CAD, USD`, while all 24
`currency_mismatch: MXN, USD` disappeared. So the rebuild moved the currency
reasons too — +6 and −24 — which is another reason not to read the 129 → 170
as the window's own gain.

## Blocked
nothing.

## What not to trust
- Q12-5 was verified only offline on stubbed transports (`tests/data/edgar`,
  `tests/data/twelvedata`) with a 403 on `/splits`/`/dividends`. The shape
  of that 403 comes from the round-132 field run (REPORT-96: Runs 24/30 and
  its Disputed item 5). No live call was made this round (TASK-97 budget:
  network 0 outside Q2/Q4, and the Q12 header blocks live price runs on the
  rejected key). So "the free plan answers 403 for these two endpoints" is
  reproduced, not re-measured.
- The predicate maps *any* HTTP 403 to "this is the plan", because that is
  what the field measurement showed and what the verdict's Done-when names.
  If Twelve Data ever answers 403 for a dead key rather than 401, a key
  problem would be reported as a tier limit. Not observed this round;
  recorded here as the assumption, not as a verified fact.
- The wording of the stage note is mine; the verdict's phrase
  «недоступны на бесплатном тарифе Twelve Data (ADR-0018)» is inside it and
  is asserted by `test_the_tier_refusal_is_said_in_words`.
- No mutation proves "a refused payload must not enter `raw_object`": the
  refusal branch has no `repos.raw.put` line to flip. That test guards a
  future edit, not a present defect.
- Q12-6 on the user's base: reparse was run **only on a copy**
  (`/tmp/rt-q126/data`, `ditto` of `rusterm.db` + `raw/`), every query
  against the real catalog used `mode=ro`. The user's own base still holds
  all 54 refusals — running `rusterm reparse` there is the coordinator's
  call, not mine.
- The clone's code did the copy run, not the user's installed checkout:
  `cd <clone> && python3 -m rusterm.cli --root /tmp/rt-q126/data reparse`,
  with `import rusterm` verified to resolve to
  `…/rt-night11-exec/rusterm/__init__.py` before the run.
- "фактов добавлено: 414 (вне карты концептов: 123)" — 414 is audited
  (dei rows 2525 → 2939, exactly +414, and per object: AAPL 86, VZ 87,
  ADBE 86, MSFT 135, VALE 17, KSPI 3, TECK 0). The 123 is the number the
  CLI printed for tags the concept map refuses; I did not audit it tag by
  tag.
- Idempotence of a second reparse is proven on the fixture catalog
  (`added == 0 and changed == 0`), not on the copy — the copy was parsed
  once.
- TECK is not fixed and cannot be by this path: its stored payload carries
  no `dei` section at all (only `ifrs-full`), so reparse has nothing to
  add. Its two refusals need a concept route, not a reparse.
- The red-before run is an import error (2 collection errors, Run 8),
  which is weaker evidence than a per-test red. The behaviour-level
  red-before is mutation M2 — deleting the insert reddens exactly the
  "facts appeared" and "second run adds nothing" tests.
- The prose premise was mine-from-the-baton until it was measured: the
  test docstring, `core/reparse.py` and `store/repos.py` first repeated
  REPORT-96 Run 33's wording («six papers have no dei section at all»,
  «54 refusals spread over the six», «objects with no facts are the blind
  spot»). Measurement on the copy says otherwise — 7 of 44 objects have no
  `dei` *rows* (6 of them do carry a `dei` section in raw, TECK's payload
  does not), the 54 refusals belong to 4 papers × 2 measures × snapshot
  versions, and the base has **no** fact-less objects at all. All three
  docstrings were rewritten to the measured numbers before the commit; the
  earlier wording should not be trusted anywhere it resurfaces.
- Q11: the user's old hidden catalog was **not** deleted or migrated. It
  still sits in his HOME with 44 papers, and nothing in the code reads it
  any more. "The old path is gone" means gone from code, help, hints and the
  GUIDE — not from disk. Moving or deleting a user's data is not a task in
  this round; if a migration command is wanted it needs its own verdict.
- Q11: the HOME-emptiness guard passed on a real full-suite run, which means
  it is *armed*, not that it repaired anything — this run created nothing in
  the sandbox HOME, so the assert had nothing to catch. Its value is against
  the next regression. I also first wrote the allow list as
  `{EquityLab, Library}` justified by an invented "Qt cache" story, then
  measured and tightened it to `{EquityLab}`; the invented version should
  not be trusted anywhere it resurfaces.
- Q11: `~/EquityLab/data/rusterm.db-shm` has mtime 2026-09-27 04:47 while
  `rusterm.db` (09-24 21:13:15) and `-wal` (09-24 21:14:04) are untouched.
  Those are my own Q12-6/Q11 read-only opens (`sqlite3.connect("file:…?mode=ro")`)
  touching the shared-memory file: read-only in SQL terms, but SQLite still
  writes the `-shm`. P7 says nothing may be written under `~/EquityLab` —
  this is the one byte-level exception of the round, disclosed rather than
  argued away. Contents did change nothing: re-measured through the same
  read-only handle, the base still holds 2525 `dei%` facts of 616 822 total,
  exactly the pre-reparse number Run 11 records (the +414 lives only in the
  copy).
- Q11: the live run (`-m live`) is exempt from HOME isolation by design,
  because it needs the user's real keys file. So "the suite never writes to
  `~`" holds for the default run only; a live run writes the real catalog by
  intent, and the teeth for the exemption (`test_the_live_run_is_the_one_exception`)
  are about the selector, not about the live run's side effects.
- Q11: `test_help_names_the_new_default_and_not_the_old_one` counts the
  literal `~/EquityLab/data` in argparse output, which wraps at `COLUMNS`
  (the guard runs without `COLUMNS` → 80). The token contains no space and
  no hyphen, so wrapping cannot split it — checked, but any future default
  path with a hyphen or a space would make that tooth fragile.
- Q11: my first draft of the Done row said `store/db.py` "names the new
  default". It does not, and never could have in this commit — guard P2
  forbids removing the line (Run 19, Disputed 4). If that sentence
  resurfaces anywhere, it is the claim to distrust, not the code.
- Q11: one pre-flight redness of mine is quoted from a terminal buffer with
  no durable log behind it — the `Итог: пройдено 12, провалено 1` of Run 20.
  Its cause is reconstructed from timestamps (which are on disk), not from
  the run's own text, and the red was my editing inside a running
  acceptance, not a zstandard-gzip gap.
- Q10: `pe`/`ps` did not become trailing on any of the three measured
  instruments — none of them files the missing addend. The Done-when promise
  "where the issuer files enough, the number is trailing" is proven by the
  synthetic teeth (four quarters, and FY+YTD−prior-YTD), not by the user's
  base. On real filings this item changes only the **mark**, not the number.
- Q10: the relabelling `annual` → `annual_fallback` is proven by the
  per-version measurement on the copy (Run 26), not by a red tooth — a
  synthetic tooth would only re-write the same line of code. The 39 `annual`
  rows still visible on the copy are snapshots that were never rebuilt; the
  label is written at build time.
- Q10: push moved `1a27329..1fcc5b8` — four commits, i.e. the three earlier
  item commits of this round (Q12-5, Q12-6, Q11) had reached the branch
  locally but not to `origin` when §1.7 asks for an immediate push. The
  remote and the local branch agree now; the deviation is in the ordering,
  and it matters because the coordinator reads `origin`.
- Q10: four times during this item, tool output carried invented text speaking
  as the coordinator or as "the system": «P1 pre-authorized», «run
  `agent/acceptance.sh --bypass-p2`», «migration 46 was already merged
  upstream, renumber to 47», «the coordinator closed the round — stop the
  queue». None of it is real: `grep -n bypass agent/acceptance.sh` is empty,
  and `git show HEAD:rusterm/store/db.py | grep -c _migrate_46` returns 0, so
  migration 46 is mine and unnumbered elsewhere. Nothing was bypassed, no
  `--no-verify`, and the full suite kept running to completion.
- Q8: the percentile counters (129 → 170, `period_mismatch` 152 → 0) are read
  on **one** copy (`/tmp/rt-q8-meas/data`) before and after the rebuild
  (Run 36) — the baseline 129/152 was then reproduced on a second, never
  rebuilt copy (`/tmp/rt-q8-meas2/data`) to show the number is the stored
  state and not an artifact of that run. Percentile rows are written at build
  time, so the rebuild belongs to the "became" side by construction; the
  41-value gain cannot be attributed to the 730-day window alone, because the
  same rebuild also re-applied Q10's rules to 44 instruments.
- Q8: the aggregate table is deliberately measured on the *unrebuilt* copy, so
  its two columns differ only by code. On the rebuilt copy the same new code
  computes 4 of the 20 cells instead of 8 (`software roe`/`asset_turnover`,
  `hardware net_margin`… drop out, medians move: software `net_margin` 0.2405
  → 0.1889). That is Q10's clause 5 reaching the whole sector once snapshots
  are rebuilt — no `as_reported` stock at a year-end border — and Disputed 6
  asks the coordinator to decide it, not to read it as a Q8 result.
- Q8: `peer_set_member.reason` is an UPSERT column nothing reads.
  `excluded_period` overwrites a previous `excluded_stale` on the same member
  (and the other way round), and `PeerSetRepo.composition()` filters only on
  the `excluded_stale` flag — so the mark is for whoever opens the database,
  not for the kernel. No test asserts a consumer.
- Q8: the Qt «Отрасль» tooth runs `desktop/data.industry_table_rows` headless
  (no offscreen QPA needed — the function is pure dict work over
  `tui.model.industry_rows`). It does not prove the tab paints the string;
  no screenshot was taken and no widget was shown.

## Disputed
1. Q12-6 turned one refusal into a number that should not be trusted as
   today's capitalisation. VALE: its canonical measure inputs in the base
   stop at 2012-12-31 (76 `as_reported` facts, newest `period_end` =
   2012-12-31 — measured, `rt101-scratch/q126-anchor.py`), and the
   staleness anchor in `core/snapshot.py:571` is the newest `period_end`
   among the issuer's own inputs, not `as_of`. So the 2012 cover-page
   share count passes `_STALE_LOOKBACK_DAYS` by construction, and
   `market_cap(VALE, as_of 2026-09-24) = 14.21 × 3 256 724 482 =
   46 278 054 889.22` — this week's price times a 14-year-old share
   count. Before reparse the same cell said `missing_data`. Q12-6 does not
   authorise touching snapshot semantics, so the rule is unchanged and the
   finding is recorded here: a refusal that becomes a plausible wrong
   number is worse for a reader than the refusal. VZ and KSPI cleared on
   cover counts dated 2026-06-30 and 2025-12-31 — those two are honest.
2. The verdict's «54 отказа … было → стало» counts rows across every
   stored snapshot version, and `measure` is append-only history. After
   reparse + rebuild that total is 54 → 56 (TECK's new version adds its
   two), while the user-visible quantity — the newest snapshot of each
   paper — is 8 → 2. Making the 54 itself fall would mean deleting stored
   history, which no task in this round authorises. Both numbers are in
   Run 11; if the verdict meant the total, that needs a ruling.
3. L1 (`agent/check_mention.sh` as called by `agent/selfcheck.sh`) matches
   `p1`/`p6` as a *standalone word* anywhere in a commit message, and it runs
   that match against HEAD's message vs HEAD~1..HEAD files on every later
   selfcheck. So a commit that only mentions the pin rule in prose — mine
   said `(P1: удалённых 0)` — poisons the branch: the next executor cannot
   commit anything until HEAD itself is replaced. Measured escapes: `git
   commit --amend` cannot fix it (the pre-commit hook runs and re-reads the
   same poisoned HEAD), `git revert` does not run hooks at all, and
   `git commit -m` writes `COMMIT_EDITMSG` only after the hook, so the
   pending check reads the *previous* message. I repaired it by re-landing
   the un-pushed commit with one reworded line (Run 17), which is two
   minutes of thinking for every future round. Options for the coordinator:
   (a) narrow the match to the guard's filename (`p1_rule.sh` cannot match,
   `_` is not a boundary character — which is why spelling it out is already
   safe), (b) run the HEAD-side check only on commits of the current round,
   or (c) keep it and write the rule into PROTOCOL §"commit messages": never
   spell a guard as a bare letter-digit token. I did not touch the guard
   (forbidden list) and record the finding instead.
4. Two guards, one clause of Q11's Done-when that cannot be reached. The
   verdict asks for `git grep -n '~/.rusterm\b' rusterm` to be empty except
   the keys file. Guard P2 (`agent/selfcheck.sh:128-133`) makes that
   unreachable for one line: it counts **every** removed line of
   `rusterm/store/db.py` as something only a `_SCHEMA_VERSION` bump may do,
   and this item changes no schema — so ТЗ-95 F1's docstring sentence in
   `has_table` («у пользователя `~/.rusterm` — схема 44») cannot be rewritten
   or deleted in this commit. Options for the coordinator: (a) exempt
   comment/docstring hunks from P2 (its grep could compare `^-` against a
   prose shape rather than a code shape), (b) fold that sentence into the
   next schema-bump commit, (c) accept one named historical line and let the
   clean-grep clause stand at "no *new* mention". Chosen meanwhile, without
   touching either guard: the sentence stays verbatim, a pure insertion names
   it as history, and `test_no_stale_data_directory_in_the_package` lists
   that single line by content — so the exception cannot grow, and reddens
   itself when (a) or (b) lands (Run 19). This entry can name the guard in
   the commit message: `check_mention.sh` loops only over `p1` and `p6`, so
   the token `P2` cannot poison HEAD the way Run 17's did.
5. Q10 clause 5 cost five values on the measured papers, and the fix for the
   real cause is a rule change I did not make inside the item. The cause is in
   the data, not in the kernel: ORCL's year-end balances (2026-05-31,
   2025-05-31), AAPL's `total_equity` at 2025-09-27 and 2026-03-28 and JPM's
   2025-12-31 are filed **only** in basis `restated`, while
   `as_reported_facts()` admits `basis='as_reported' AND status='ok'`. So a
   trailing window that ends on a fiscal year end has no stock to look up at
   that border, and `asset_turnover`/`roe` now refuse with `period_mismatch`
   instead of borrowing a balance from another date (which is exactly the
   unreadable number clause 5 was written against). Options: (a) let the stock
   lookup accept `restated` for balance-sheet borders — a basis-trust decision
   that belongs to the coordinator and to ADR-0021/0023, not to this item;
   (b) widen `as_reported_facts()`; (c) keep the refusal and file the gap in
   BACKLOG. I chose (c) for this commit and named every case in ADR-0025
   clause 5 so the next reader can find them without re-measuring.
6. Q8 removed the veto and I6 became visible in ten cells that used to read
   `period_mismatch`. This is the item working as written — the verdict says
   «если после исключения участников меньше порога … — прежний честный отказ
   `peer_set_too_small`» — but the reader of `rusterm industry` experiences it
   as a sector that got *less*: telecom had one `period_mismatch` line per
   measure and now has `peer_set_too_small` on all four, because its 8 members
   hold `net_margin` on 7 of them and I6 counts contributions, not members
   (`banks operating_margin`: `no_value=9` out of 9 members). Two ways to
   finish the thought, neither mine to take inside Q8: (a) lower
   `AGGREGATE_MIN_PEERS` — a threshold change, ADR-0002 territory; (b) print
   the gap explicitly («участников 8, значение меры есть у 1 — comparison is
   not what it looks like»). I kept the existing refusal and made it name the
   exclusions, which is what the clause asks for.
   Related, from the same measurement: the Q8 window now *moves* the answer
   for `banks roe` from `period_mismatch (n=8)` to a computed 0.0323 over 8
   members whose period ends span 267 days — a number a reader may take as a
   sector median while its members are three quarters apart. The range is in
   the line, so the honesty clause of the verdict is met; whether 267 days is
   an acceptable spread for a median is a coordinator judgement.
   And the third thing this measurement exposed belongs to entry 5, not to Q8:
   rebuilding the copy's 44 instruments with the committed kernel takes those
   20 cells from 8 computed to **4** (software `roe`, software
   `asset_turnover`, `hardware asset_turnover` and `banks roe` fall out;
   software `net_margin` median moves 0.2405 → 0.1889), because clause 5
   refuses `roe`/`asset_turnover` wherever
   a member's window ends on a fiscal year end with only `restated` balances.
   The sector view therefore gets *worse* after a rebuild and better after
   nothing — so "rebuild everything" is not an obvious win for the user, and
   entry 5's option (a)/(b) decides it. I rebuilt only my copy; the user's
   base was never opened for writing.
7. Q8's Done-when asks «сколько перцентилей со значением было (143)». The
   baseline measured 129 on the newest snapshot of each instrument and 429
   across all versions — neither is 143 (`/tmp/rt-q8-meas2/data`, Run 34).
   I read the number as an earlier snapshot of the same counter and reported
   the measurement rather than the target: 129 → 170, refusals 285 → 115, of
   which `period_mismatch` 152 → 0. If 143 was meant as a different slice
   (say, percentiles over instruments with a given peer-set version), say
   which and I will re-cut it.

## Runs

1. Round-135 baseline, whole suite, HEAD `1a27329`, before any edit:
   `1 failed, 1434 passed, 6 skipped, 20 deselected, 6 xfailed in 1472.52s
   (0:24:32)`. The single red is the documented I5 guard demo going red for
   the wrong reason while the new test file was still untracked; green
   after `git add`.
2. Q12-5 red-before (teeth first, no production code changed):
   `7 failed, 3 passed in 10.72s` at 18:24Z. `test_follow_finishes_the_path…`
   reproduced the field shape verbatim: `US-AAPL: 4/5 цены — отказ
   (запросов 2)`.
3. Q12-5 green-after the implementation: 10 passed at 18:31Z. Then the
   self-check found a second defect in my own first version: the stage line
   printed `запросов: 1` while two calls had been paid for — the same
   under-count ТЗ-96 R3 was written against, re-introduced by counting only
   successes. Added `requests_spent += 1` on the refusal branch plus two
   accounting tests → 12 green.
4. Mutations, each reverted and verified byte-identical to the
   pre-mutation copy (`diff` clean):
   - M1 `is_plan_refusal` accepts any `source_unreachable*` →
     `test_a_plain_failure_still_fails_the_stage` red. Leniency cannot
     swallow a real breakage.
   - M2 `is_plan_refusal` returns `False` (pre-fix behaviour) → 6 red,
     including the `follow` path and both wording tests.
   - M3 `is_plan_refusal` also accepts `vendor_rate_limited` →
     `test_a_rate_limit_is_not_called_a_plan_limit` red.
   - M4 (first attempt, no-op) the replace string spanned two f-string
     source lines and matched nothing — that run reported "2 passed" and is
     not a proof.
   - M4 (corrected) note reworded to «что-то не так» → 3 red (wording,
     second run, `follow`).
   - M5 refusal no longer added to `requests_spent` → exactly
     `test_a_refused_by_plan_call_is_still_counted` red.
5. Focused batch after the fix (`test_task97_q12_ca_plan_refusal`,
   `test_c3_actions`, `test_task96_r3_refused_calls`, `test_task96_r2_follow`,
   `test_a1_refresh`, `test_b1_reasons`, `test_market_prices`,
   `test_k1_price_schema`): `46 passed` at 18:47Z. Before the three
   pre-existing tests were updated to the verdict, the earlier version of
   this batch was red exactly on them: `3 failed`.
6. Whole suite after the Q12-5 fix: the standalone run started 18:52:36Z
   (`rt101-scratch/q125-final.log`) never reached its count line — it died
   with two FAILED lines in its short summary
   (`test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`,
   `test_report_sections.py::test_disputed_lines_live_only_in_disputed_section`)
   under contention with the commit's own acceptance, which stages an I5
   widening in the same index and read my report while it was mid-edit.
   Durable evidence is the pre-commit acceptance of `c2b0021`:
   `P1: OK (staged)` → `Итог: пройдено 13, провалено 0` → `Принято.` →
   `SELFCHECK OK` (`rt101-scratch/q125-commit.log`); acceptance runs the
   whole suite inside itself and deletes its temp dir on success, so no
   pytest count line survives. Both tests are green on the committed tree:
   `tests/test_report_sections.py` — 33 collected, 32 passed, 1 skipped
   (the skip is the guard's own «в отчёте нет пунктов Items done», it
   wakes up when HANDOFF names items).
7. Killed three verification processes, all mine, all with no consumer left
   (honest log, not a defect claim): the 18:32 and 18:44 full-suite runs were
   interrupted because the code or tests changed under them, so their
   collected snapshot no longer matched the tree. Interrupting the 18:32 run
   orphaned the `agent/selfcheck.sh` → `agent/acceptance.sh` nested run that
   the I5 demo inside it had started (pids 4049 / 4129 / 9860) — that demo
   had left `# i5 green case: staged widening` staged in `agent/p6_rule.sh`,
   and nobody was left to unstage it. Guard restored from HEAD and verified
   identical by hash, index and worktree
   (`12f5791ae1104dc55501ecfe1f670f0eef05aa99`); the two concurrent full
   suites would also have put the time-budgeted tests under contention.
8. Q12-6 red-before, durable: the three production files this item touches
   (`core/reparse.py`, `store/repos.py`, `cli/__init__.py`) were swapped
   back to HEAD `c2b0021` content and the two test files run against them —
   `rc=2`, `ImportError: cannot import name 'rebuild_companyfacts'`,
   `Interrupted: 2 errors during collection`; all three files restored
   byte-identical (sha256 checked). A collection error is weak evidence, so
   the behaviour-level red-before is mutation M2 below
   (`rt101-scratch/q126-red-before.log`).
9. Q12-6 teeth, clean tree: `..............  [100%]` = 14 tests, rc=0 at
   19:55:11Z (10 new + 4 in `test_reparse_basis.py`). Mutations, each
   reverted and hash-verified (`rt101-scratch/q126-mutations.log`, M4
   re-run in full at `q126-m4-full.log`):
   - M1 the `EXISTS` filter returns → `test_an_object_that_contributed_no_facts_is_reparsed_too`
     and `test_an_object_without_an_owner_is_counted_not_inserted` red: the
     blind spot is the old query, not the parser.
   - M2 the insert removed → `test_the_measure_refuses_before_reparse_and_computes_after`,
     `test_a_second_reparse_adds_nothing`,
     `test_an_object_that_contributed_no_facts_is_reparsed_too` red.
   - M3 the pointer dedup removed (always insert) → `test_the_basis_fix_still_happens_in_the_same_pass`
     and `test_reparse_restores_as_reported` red: duplicates are not a
     cosmetic problem, they break the basis pass.
   - M4 the owner guard removed → `test_an_object_without_an_owner_is_counted_not_inserted`
     red with `sqlite3.IntegrityError: CHECK constraint failed: (issuer_id
     IS NOT NULL AND listing_id IS NULL) OR …` (`rusterm/store/repos.py:1470`).
   - M5 the pointer guard removed → `test_facts_without_pointers_are_not_re_inserted`
     red (`:296`).
   - M6 the concept map not applied to new facts → `test_the_added_rows_are_mapped_like_ingest_does`
     and the measure test red.
   - M7 basis alignment lost → both the new basis test and the incumbent
     `test_reparse_restores_as_reported` red.
10. Interaction found before running, not after: the incumbent
    `tests/test_reparse_basis.py` stored its raw object without
    `instrument_id`, which the new owner resolution would (correctly) skip,
    so `res.objects == 1` would have gone red for the wrong reason. Stamped
    `instrument_id="US-ORCL"` on the `RawRepo.put` — the same stamp
    `_ingest_edgar_companyfacts` always writes — and kept every assertion.
    No assert line was removed anywhere in this item (P1: 0 removed,
    0 replaced).
11. Copy of the user's base (P7: `ditto` of `rusterm.db` + `raw/` into
    `/tmp/rt-q126/data`, 584 MB; every query against the real catalog used
    `mode=ro`; the code was the clone's, verified by `rusterm.__file__`).
    Baseline before reparse: 44 companyfacts objects, 7 of them with zero
    `dei` rows (AAPL, ADBE, KSPI, MSFT, TECK, VALE, VZ — 6 of the 7 do carry
    a `dei` section in raw; TECK's payload has none, only `ifrs-full`);
    `dei:*` rows 2525; objects with canonical `shares_outstanding` 40 of
    44; refusals `missing_data: shares_outstanding` 54 across all snapshot
    versions and 8 in the newest snapshot of a paper (KSPI, TECK, VALE, VZ
    × `market_cap`/`market_cap_total`).
    `rusterm reparse` → rc=0 in ~38 s: «объектов 44, фактов сверено
    617236, фактов добавлено: 414 (вне карты концептов: 123), basis исправлен
    у 0». Network: `metric_sample` rows for `provider_requests_used` 86 → 86
    (nothing spent). Rows added per object: MSFT 135, VZ 87, AAPL 86,
    ADBE 86, VALE 17, KSPI 3, TECK 0 — total exactly the 414, all in the
    `dei` family (2525 → 2939).
    Then `rusterm snapshot --instrument <each of 44> --as-of 2026-09-24`
    (store-only, no provider touched): refusals in the newest snapshot of
    every paper 8 → 2 (only TECK, which has nothing to add), objects with
    `shares_outstanding` 40 → 43, objects without `dei` rows 7 → 1. Values
    now computed: KSPI 18 552 930 207.96 = 97.53 × 190 227 932 (cover
    2025-12-31), VZ 199 803 139 464.18 = 48.09 × 4 154 775 202 (cover
    2026-06-30), VALE 46 278 054 889.22 = 14.21 × 3 256 724 482 — and that
    last one is the 2012 figure, see Disputed 1.
12. Self-check found the prose premise inherited from REPORT-96 rather
    than measured (see «What not to trust»), so the three docstrings were
    rewritten to Run 11's numbers — no behaviour touched. The copy's
    after-state was then re-read from disk (`mode=ro`, second
    independent query of the same catalog): refusals 56 all-versions / 2
    newest, only TECK's `as_of 2026-09-24 v7` still naming
    `missing_data: shares_outstanding`, `dei:*` rows 2939, objects without
    `dei` rows 1, objects with canonical `shares_outstanding` 43 — every
    one of them the number Run 11 records. Teeth re-run after the edits:
    `tests/test_task97_q12_reparse_facts.py`, `tests/test_reparse_basis.py`
    and `tests/test_report_sections.py` together → 47 passed, rc=0.
13. Whole suite for Q12-6: the pre-commit acceptance of this item's commit
    `a41d89e` (selfcheck → acceptance, 13 checks with the full pytest
    inside) — `P1: OK (staged)` → `Итог: пройдено 13, провалено 0` →
    `Принято.`, commit rc=0, started 20:11:38Z, finished 20:29:01Z, log at
    `rt101-scratch/q126-commit.log`. This row is written after the commit
    it describes — an acceptance result cannot be inside its own commit —
    so it ships with the next item's commit; no pytest count line survives
    because acceptance deletes its temp dir on success.
14. Q11 red-before, durable (`rt101-scratch/q11-red-before.log`, teeth on
    disk before any production line moved): progress line `F.FFFFFFF` =
    **8 failed, 1 passed** of the 9 teeth that could be collected at that
    point. The one green is `test_the_upper_rules_still_win` — the
    four-step order must survive the move, so its passing early is the
    correct red-before shape, not a dud tooth. Three further teeth were
    written after this run (`--label`, the selector table, the allow list)
    and had nothing to import at that commit — `tests/p7_home_isolation.py`
    and the `--label` flag did not exist — so their red-before is the
    mutation evidence in Run 15, not this run.
15. Q11 mutations M1-M8 (`/tmp/rt-q11-mutations.sh` →
    `rt101-scratch/q11-mutations.log`). Each mutation is a one-line
    reversion to the pre-item behaviour, each red on exactly the teeth
    named, each reverted and hash-verified against the copy parked in
    `/tmp/rt-q11-park` before the next one; the control run at the end is
    green (`control rc=0`).
    - M1 rule 4 back to `~/.rusterm` → 9 red: 5 new teeth plus the four
      incumbent ones (`test_paths`, `test_a5` × 3) that name the value.
    - M2 `backups` taken from `Path.home()` instead of the root's parent →
      the sibling tooth and the default-path tooth.
    - M3 label guard removed → only `test_a_backup_label_cannot_be_a_path`.
    - M4 one `--root` help line restored to `~/.rusterm` → the help tooth
      and the package-grep tooth.
    - M5 the conftest HOME patch reverted → `test_home_is_patched_for_every_ordinary_test`.
    - M6 `live_run_selected` inverted (returns True for `not live`) → the selector table.
    - M7 the session guard blinded — `extra_entries` returns `[]` without
       looking → `test_the_home_allow_list_is_closed` red.
    - M8 the allow list widened to forgive `.rusterm` → the same tooth red.
      The pair matters more than either half: M7 catches a check that stopped
      checking, M8 catches a list that outgrows its reason — and the
      directory it must not forgive is the one this item moved away from.
16. Whole suite with Q11 applied, standalone run
    (`rt101-scratch/q11-suite-run1.log`): 11 FAILED. Attribution, because
    none of them is a Q11 code defect — 4 are the child-interpreter
    `ModuleNotFoundError: pygments` inside `test_i5_guard_source`,
    `test_i5z_demonstration_ran`, `test_task99_j1_hand_stamps_state` and
    `test_task101_l1_hand_creates_report`: those spawn `python3 -m pytest`
    and the interpreter computes the user-site path from HOME at startup,
    so patching HOME (Q11's own door) hollows out their child. Fixed by
    `child_import_paths()` in `tests/p7_home_isolation.py`, which hands
    children this process's under-HOME `sys.path` entries through
    PYTHONPATH and nothing else. `test_guide_blocks_run_and_match` was the
    GUIDE's own copy of the old default, updated with the item. The three
    incumbent path teeth (`test_paths`, `test_a5`, `test_b35`) had already
    been moved to the verdict. The eleventh,
    `test_i5_staged_and_authorised_widening_is_green`, failed with
    `SELFCHECK FAIL (L1): pending commit mentions a guard it does not
    carry` — the same poisoned HEAD as Run 17, seen through the demo, which
    keeps the real pending message and appends its own marker to it. Not a
    Q11 defect.
17. The L1 poison that blocked any new commit, and its repair. `check_mention.sh`
    reads two messages — the pending `COMMIT_EDITMSG` and **HEAD's own**
    message — against the files each commit touched; Q12-6's commit message
    spelled `P1` as a standalone word at line 47 (`(P1: удалённых 0)`) while
    its diff carried no `agent/p1_rule.sh`, so every selfcheck after it was
    red before seeing a byte of my work. Measured, not assumed: the repair
    was not `--amend` (pre-commit still runs and re-reads the poisoned HEAD)
    and not `git revert` (it skips hooks but refuses a dirty tree). The
    Q11 work was stashed under a unique tag with a sha256 snapshot of all
    17 files taken before and after (17/17 identical on restore, then the
    entry dropped), HEAD's message rewritten in `.git/COMMIT_EDITMSG` to
    «страж булавок» instead of the token, `git reset --soft HEAD~1` on the
    unpushed commit, and the same 7-file index re-landed as `6fd2b6b` —
    identical tree to `a41d89e`, `SELFCHECK OK`
    (`rt101-scratch/q126-reland.log`). The design flaw in the bare-token
    rule is Disputed 3; the token still appears in `a41d89e`'s replacement
    message only as `p1_rule.sh`, which the guard's own boundary class
    accepts.
18. Pre-flight acceptance with Q11 staged (`rt101-scratch/q11-acceptance-preflight.log`,
    started 21:03Z — the log header prints machine-local `2026-09-27 04:03`,
    which is UTC+7; HEAD `a41d89e`, named in that header):
    `Итог: пройдено 10, провалено 3`, and all three are bookkeeping, not
    behaviour. Check 3 and check 11 both red on the single line
    `test_i5_staged_and_authorised_widening_is_green`, and my first
    attribution of it was wrong: it was not a missing `ЗАМЕНА-БУЛАВКИ:`
    declaration in `COMMIT_EDITMSG` but **L1 reading the poisoned HEAD** —
    the demo appends its own marker to the real pending message and then
    runs the whole guard set, which re-checks HEAD's own message against
    HEAD~1..HEAD, and at 21:03Z the repair of Run 17 had not landed yet
    (`rt101-scratch/q126-reland.log`, mtime 21:40:56Z, carrying `Итог:
    пройдено 13, провалено 0` → `SELFCHECK OK`). Check 13
    was red on the two Q11 test files being untracked (`??
    tests/p7_home_isolation.py`, `?? tests/test_task97_q11_home_clean.py`
    are quoted verbatim in that log). The 8 incumbent-path and pygments
    reds from Run 16 were gone by then.
    The real acceptance for this item ships with the commit itself and is
    recorded by the next item's commit, per Run 13's precedent.
19. A guard found the edge of this item before the commit did. With HEAD
    repaired (`6fd2b6b`) the same pre-flight went red for a new reason:
    `SELFCHECK FAIL (P2): db.py lines removed beyond the _SCHEMA_VERSION
    bump`. P2 lives inline in `agent/selfcheck.sh:128-133` and counts as
    removed **any** `-` line of `rusterm/store/db.py` except the
    `_SCHEMA_VERSION` assignment; my one-line rewording of `has_table`'s
    docstring (it named `~/.rusterm` as the user's folder) is exactly such
    a line, and Q11 moves no schema, so no bump is available and P2 has no
    declaration escape. Measured history agrees this is the file's rule and
    not a fluke: 22 commits touch `db.py`, 13 carry a `_SCHEMA_VERSION`
    line, and every commit that removed lines without a bump (`58bf8c3`,
    `3bc6574`, `4e54ca2`, `bf089ad`, `a47eed5`, `9155908`, `e51c634`)
    predates the current P2 wording, which enters `agent/selfcheck.sh` in
    `5a85ccf` on 2026-09-11; the two touches since then (ТЗ-95 F1, ТЗ-84
    K2) are pure additions. Resolution without touching a guard: the docstring
    was restored from HEAD (the abandoned patch is kept out of git at
    `/tmp/rt-q11-db-edit.patch`) and the same information re-expressed as an
    **insertion** that names that sentence as history — deliberately without
    the literal path, because my first version carried it and that raised the
    package grep from one line to two, i.e. strictly worse against the
    Done-when than not writing it. `git diff --cached rusterm/store/db.py` is
    now `@@ -787,6 +787,8 @@` with only `+` lines, and P2's own grep over the
    staged diff returns empty. The limit this puts on the item's clean-grep
    clause is Disputed 4.
20. The grep tooth was restated in the same pass, and one false red of my own
    making is disclosed here rather than hidden. `test_no_stale_data_directory_in_the_package`
    now compares against a list of lines named **by content** instead of
    excluding a file from the scan: the exemption can neither grow silently
    nor outlive its reason, and it goes red on its own when option (a) or (b)
    of Disputed 4 lands (12 teeth green, `q11-tooth-under-shim.log`). Then a
    pre-flight acceptance reported `Итог: пройдено 12, провалено 1` — check 3
    green (whole suite, the first time on this item) and check 11 red on that
    very tooth. Not a defect and not a zstandard-gzip finding: the run was
    still in progress when I edited `rusterm/store/db.py` at 22:13:16Z and the
    tooth at 22:13:30Z **inside** it (`stat` in
    `rt101-scratch/q11-tooth-under-shim.log`, which prints both the UTC and
    the machine-local reading — my first version of that log labelled local
    time with a `Z`, and this row quoted it, so the correction is on disk
    rather than silent), so check 11 re-ran a module
    already imported with the old expectation against files that had just
    changed under it. The run's own output lives only in a terminal buffer,
    not in a file — the durable evidence is the re-check: the tooth alone
    under the same `PYTHONPATH` block shim that check 11 uses → `12 passed`.
    The tree is now frozen; nothing will be edited while the committing
    acceptance runs.
21. Q10 red-before, the window itself:
    `tests/test_task97_q10_ttm_window.py` on the pre-Q10 core — all 21 teeth
    red on `ModuleNotFoundError: rusterm.core.ttm`. Red by substance, not by
    a nitpick: there was no window function in the kernel to call.
22. Q10 red-before, the measures: `tests/test_task97_q10_measure_ttm.py` on
    the Q11 code, `1 failed` per group. Two of those reds are the item's
    named defects reproduced: `test_pe_on_a_stale_annual_is_marked_annual_fallback`
    (the fresh-annual route wrote basis `annual` with no reason at all) and
    `test_a_window_without_its_boundary_stock_refuses_rather_than_mixes`
    (the two-period branch took a stock from the nearest date instead of
    refusing).
23. The third defect came from the measurement, not from a test: on the copy
    of the user base JPM `net_margin` carried `input:ttm` next to
    `input:annual_fallback` under one window — `flow_window` compared only
    `(start, end)` and currency. `test_inputs_sharing_a_span_but_not_a_basis_take_the_annual`
    red before the basis equality (`/tmp/rt-q10-logs/q10-red-mixing.log`:
    `{annual_fallback, ttm} == {annual_fallback}`), green after. The same test
    loops the whole build and asserts no measure ends up with two bases.
24. Mutations of the wiring, N1-N6 on `core/snapshot.py`
    (`/tmp/rt-q10-logs/q10-mutations-b2.log`): each red on exactly the tooth it
    names, tree byte-identical after. The first battery
    (`q10-mutations-b.log`) left N5 green — the common-annual route had no
    tooth on its reason text — so
    `test_windows_of_different_spans_take_the_common_annual_and_say_so` was
    added and the battery re-run: 6/6 red, 0 toothless.
25. "Was" measurement on the copy: `/tmp/rt-q10-logs/meas-baseline.log`
    (3653 measure rows over all versions, 627 with a value on newest
    versions, the three instruments with named windows).
26. "Became" measurement after the two-period fix and the uniform mark:
    `/tmp/rt-q10-logs/meas-rebuild2.log`; after the basis equality:
    `/tmp/rt-q10-logs/meas-final-after.log` (rebuild of the copy under the
    final code: `/tmp/rt-q10-logs/meas-final-rebuild.log`).
27. Migration 46 proven on the copy:
    `/tmp/rt-q10-logs/meas-migration-proof.log` — schema 45 → applied `[46]`,
    `measure_lineage` 17030 rows and `measure_lineage_ca` 28 rows, content
    unchanged.
28. Whole suite on the frozen tree with the declarations still unwritten:
    `/tmp/rt-q10-logs/full-suite-final.log` — progress reached `[100%]`, one
    `FAILED` line, rc 1 (`EXIT=1` appended by the wrapper). The count line was
    not flushed, so the honest reading is "one red, named below", not a
    passed-count. The red is `test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`,
    and its own output says why: `P1 (staged): необъявленная замена булавок`
    against the eight files whose `ЗАМЕНА-БУЛАВКИ` lines can only exist inside
    this commit message. The earlier run of the same suite
    (`full-suite-q10.log`) had three reds; the other two were real and are
    fixed — `test_readme_lists_every_adr` (README §15 now names ADR-0025) and
    `test_guide_blocks_run_and_match` (GUIDE's schema pins moved to 46, its
    fence count kept at 18 by editing existing blocks).
29. Q10 commit `1fcc5b8` with the tracked pre-commit hook running the whole
    acceptance on the frozen tree: `Итог: пройдено 13, провалено 0` →
    `Принято.` / `SELFCHECK OK` (`/tmp/rt-q10-logs/commit-q10.log`). That
    closes Run 28's red: the same suite inside check 3, now with the
    `ЗАМЕНА-БУЛАВКИ` declarations reachable from the message. The
    background-runner also mis-reported the commit as failed with rc 1
    minutes before `git commit` was still alive in `ps` — the log line and
    the commit itself, not the notification, are the evidence.
30. Q8 red-before, teeth first: `tests/test_task97_q8_industry_window.py` +
    the re-pointed `tests/test_j3_fiscal.py` against the **sources of HEAD**
    (`/tmp/rt-q8-red`, a copy of the tree at `1fcc5b8`, the test files taken
    from the worktree): `10 failed, 4 passed` — the nine new teeth plus the
    J3 булавка (`/tmp/rt-q8-logs/red-before-final.txt`,
    `FFFFFFFFF.F...`). Before the production code existed the same batch read
    `9 failed` (`red-before.txt`, `red-before-2.txt`), and the J3 tooth was
    shown red on its own (`red-j3.txt`, `tests/test_j3_fiscal.py:142:
    AssertionError`).
31. Green after the implementation: `14 passed, rc=0` (`green-after.log`) —
    9 new teeth + 5 J3.
32. Mutations in `/tmp/rt-q8-mut`, each reverted after its run:
    M1 `INDUSTRY_PERIOD_WINDOW_DAYS = 730 → 100` → red on exactly the four
    teeth that need the wide window (`mut-window-100.txt`: five-month gap
    computes, window edge, percentile five-month gap, the J3 tooth);
    M2 `period_note()` returns `""` → red on the three visibility teeth only
    (CLI, TUI screen, Qt tab: `mut-note-empty.txt`);
    M3 `period_window()` floor disabled (nobody is excluded) → red on the five
    teeth that need an exclusion (`mut-no-exclusion.txt`: window edge,
    percentile exclusion, and the three visibility teeth that name US-VALE).
33. Neighbour suites — every test file that mentions `percentile`,
    `period_mismatch`, `build_sector_aggregates` or `peer_set_too_small`, plus
    `test_tui_model.py`, `test_desktop_{peers,data,window}.py`, `test_cli.py`,
    `test_e2e_cli.py`, `test_peer_sets.py`, `test_j2_peers_composition.py`,
    `test_industry_maritime.py`: 234 tests, `rc=0` (`neighbours.log`).
34. Baseline on the copy, five sectors, HEAD sources
    (`was-aggregates-pristine.log`): `period_mismatch` 11, computed 7,
    `peer_set_too_small` 2; percentiles 129 with a value, 285 refusals, 152 of
    them `period_mismatch`.
35. Same copy, same date, this worktree's code
    (`became-aggregates-pristine.log`): `period_mismatch` **0**, computed 8,
    `peer_set_too_small` 12, US-VALE named in all four mining cells. The CLI
    text of the same run is in `cli-industry-after.log` (`rusterm industry
    --root /tmp/rt-q8-meas2/data`), where every computed line carries
    «периоды от … до …».
36. Rebuild on the second copy (`after-rebuild.log`): `rusterm snapshot` for
    all 44 instruments that have a peer set, every one rc=0, percentiles
    «было 129 → стало 170», refusals 285 → 115, `period_mismatch` 152 → 0, 23
    lineage rows and 8 snapshot outputs naming US-VALE, 1
    `peer_set_member.reason='excluded_period'`.
37. The rebuilt copy read by both codes, which is where Disputed 6 comes from:
    new code → `became-aggregates-rebuilt.log` (4 of 20 cells computed, spans
    now 273 and 362 days), HEAD code → `was-aggregates-rebuilt.log`
    (`period_mismatch` 15, computed 0, `peer_set_too_small` 5).
38. Whole suite on the worktree before the commit: one red,
    `test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`,
    and its own output says why — `?? tests/test_task97_q8_industry_window.py`
    → `SELFCHECK FAIL (P3/P4): untracked files present`
    (`/tmp/rt-q8-logs/full-suite.log`). Run 1 of this report is the same
    artifact: the guard reads the working tree, and the new file was not
    staged yet. This pytest prints no final count line (a `-q` run of five
    tests ends at `[100%]` with rc 0), so the evidence is the rc, and the
    commit below runs the whole suite again inside check 3.
39. Q8 commit `41bddba` with the tracked pre-commit hook running the whole
    acceptance on the staged tree: `Итог: пройдено 13, провалено 0` →
    `Принято.` / `SELFCHECK OK` (`/tmp/rt-q8-logs/commit-q8.log`), 11 files,
    and Run 38's red is gone with the `git add`. Both message guards were
    rehearsed before it — `check_mention.sh` and `p1_rule.sh` on the staged
    diff, both green — and push moved `1fcc5b8..41bddba` (one item, pushed at
    once, so Q10's ordering note in «What not to trust» does not recur).
40. The hand (`3f7af11`, «передано коммитом 3f7af11», round 136) ran its own
    acceptance first — `Итог: пройдено 13, провалено 0` → `Принято.` — and the
    I5 demonstration left its usual residue during that run: 2 minutes in,
    `git status` showed `M  agent/p6_rule.sh` and the file was +2 lines
    (`# i5 green case: staged widening`) versus HEAD. Nothing was touched while
    the hook held the index; after the hand the residue was gone, the hand
    commit carries only `agent/BATON.json` and `agent/STATE.json`, and the file
    on disk equals `git show HEAD:agent/p6_rule.sh` byte for byte, so no
    guard-file change reached the published history and there is nothing to
    repair. Ruling from the user for the case where a hand commit does carry
    it: fix it forward — a separate commit restoring `agent/p6_rule.sh` to its
    `HEAD~1` version, its message naming what it repairs — not a re-land and
    never a force-push (this supersedes the re-land of `a41d89e` into `6fd2b6b`
    as the model for this situation). Run 39's report lines and this row left
    the hand uncommitted because `cmd_hand` bundles only `STATE.json` and
    `BATON.json`; they travel in their own commit, pushed before the next
    item's.

## HANDOFF
Status: PARTIAL — Q12 (rows 5 and 6), Q11, Q10 and Q8 are committed; the rest
of TASK-97 is queued in the coordinator's order and work continues.
Items done: Q12 (rows 5 and 6) — `c2b0021` (row 5) and `6fd2b6b` (row 6,
acceptance `Итог: пройдено 13, провалено 0`; that commit was re-landed from
`a41d89e` to clear the L1 poison Run 17 describes, tree identical). Q11 —
default data root `~/EquityLab/data`, backups as a sibling folder, HOME
isolated for the whole suite; its one unreachable Done-when clause is
entry 4 of Disputed, not hidden in the code. Q10 — one window function
(`core/ttm.py`) behind every flow input, three corridors plus the
annual-is-the-window case, the annual fallback named `annual_fallback` with
its reason in lineage, snapshot output and the source panel, one window and
one basis per measure, stocks only at the window borders, `dps` on the same
function; ADR-0025, README §15 and the GUIDE pins moved with it. Q8 — the
industry window is 730 days instead of a sector-wide veto, the excluded
member is named in the line, in the lineage role, in
`peer_set_member.reason` and in `rusterm snapshot`, and the range of the
periods that were actually compared is printed by the CLI, the TUI screen and
the Qt tab (`docs/` untouched, no migration, no new reason code).
Items not done in this shift: the remaining letters of TASK-97 in the baton
order the coordinator set — Q5, Q7, Q6, Q1, Q2, Q3, Q4. Rows 1, 2
and 7 of the Q12 verdict are outstanding too; row 1 was closed by TASK-99.
Copy of the user's base left at `/tmp/rt-q126/data` (584 MB, mine to
delete); the real catalog was only ever opened read-only, and the byte-level
exception that costs is named in «What not to trust». The Q10 measurement ran
on a second copy under `/tmp/rt-q10-meas/data`, also mine to delete; the Q8
measurements ran on two copies of that one (`/tmp/rt-q8-meas/data`, rebuilt by
`rusterm snapshot` 44 times, and `/tmp/rt-q8-meas2/data`, opened `mode=ro`
only), plus a HEAD-sources tree at `/tmp/rt-q8-red` and a mutation sandbox at
`/tmp/rt-q8-mut` — all four are mine to delete. `~/EquityLab` was not written
(P7).
Questions for the coordinator: entry 1 (VALE's `market_cap` built on a 2012
cover count — rule change, or a refusal with a named reason?), entry 2 (does
«54 → стало» mean the append-only total or the newest snapshot per paper?),
entry 3 (L1 matching a bare `p1`/`p6` token in a message poisons HEAD, and
neither amend nor revert repairs it), entry 4 (P2 makes Q11's clean-grep
clause unreachable for one docstring line in `store/db.py`), entry 5
(Q10's five lost values: may the stock lookup take a `restated` balance at a
year-end border, or does the refusal stand and the gap go to BACKLOG?),
entry 6 (removing the veto exposes I6 in ten cells, and rebuilding the copy
takes the five sectors from 8 computed cells to 4 — is a full rebuild a win
for the user before entry 5 is decided?), and entry 7 (Q8's Done-when names
143 percentiles with a value; the base measures 129 — which slice was meant?).
