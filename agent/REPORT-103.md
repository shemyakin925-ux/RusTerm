# REPORT-103 — two small fixes from REPORT-102 Disputed; then resume TASK-97

## Done

| Item | What shipped | Proof |
|---|---|---|
| N1 | The mention barrier now reads the commit **subject** only. `agent/check_mention.sh`: `subject="$(head -n 1 "$msg_file")"`, and the match runs on that line; the guard-file pattern, the pairwise shape, the output line and the exit codes are unchanged. The header comment says what the barrier covers and why a body line is a citation, not a promise. `git revert` stays covered because it repeats the original subject — the comment names that. `agent/selfcheck.sh` was not edited (forbidden by the baton): it calls the script twice (pending message + staged list; HEAD message + `HEAD~1..HEAD`) and reads only the exit code, so narrowing the match covers both halves. | `tests/test_task103_n1_subject_only.py`: 9 teeth — body citation green (single guard, both guards), subject names `p6_rule.sh` without the file → red naming `agent/p6_rule.sh`, with the file → green, pairwise on the subject, `Revert "…p6_rule.sh…"` still red without the file and green with it, a single-line message with no trailing newline, empty subject green. Red-check in a linked worktree at the baton `762127d`: `FF.......` — the two subject-red teeth fail under the old script, the other seven already passed. Real history: published `49c6320` (body cites `agent/p1_rule.sh`, carries no guard) — old script exit 1, new script exit 0; over the last 120 published commits the old barrier dyed 2 red (`49c6320`, `0e50c2d`), the new one dyes 0 and reddies nothing new. Three mention modules together: 17 green. |
| N2 | An aggregate's currency set is built from members that **carry a value**. `core/industry/aggregate.py`: the currency scan moved off `measure_ids` (every measure row, including `value IS NULL` refusals) and onto `values` filtered by `v is not None`; `measure_ids` and the `stale_measures` set that existed to filter it are gone, since window exclusion already filters `values`. Consequence: a roster where no value arrives reports `peer_set_too_small` with the M4 phrase, never `currency_mismatch`, and a mismatch list names only currencies that were actually compared. The stop-crane, `AGGREGATE_MIN_PEERS` and the 730-day window are untouched. | `tests/test_task103_n2_valued_currency.py`: 3 teeth (9 members / 0 values / mixed lineage currencies → `peer_set_too_small` + «участников 9, значение меры есть у 0», `currency is None`, `no_value=9`; 8 valued USD + 1 valueless KRW → computed with `currency == "USD"`; 4+4 valued USD/KRW + 1 valueless BRL → still `currency_mismatch: KRW, USD`, BRL absent). Red before the fix, all three: `currency_mismatch: KRW, USD` twice (where a refusal and a number were expected) and `currency_mismatch: BRL, KRW, USD` once (the valueless member's currency named). After: 53 green across the currency/industry neighbours (`test_currency_firewall`, `test_k4_k6_valuation`, `test_j7_tui_industry`, `test_task102_m4_member_line`, `test_j1_currency`, `test_j1_display`, `test_n2_industry_view`) plus both mention modules. Copy of the user's base (P7: `/tmp/rt-q10-meas/data`, opened read-only, 5 industry sets, `as_of` 2026-09-24): wide money-measure list — `currency_mismatch` cells **15 → 9**, `peer_set_too_small` **33 → 39**; the six movers (`mining_metals` and `telecom` × `ev`/`net_debt`/`invested_capital`) refused with `currency_mismatch: CAD, USD` / `MXN, USD` while only 1–3 members had a value, and now read `peer_set_too_small \| участников 9, значение меры есть у 2`. The 9 that stay are real conflicts among valued members (`market_cap_total` "(blank), USD" at n=7..9; `fcf`/`ebitda` CAD/USD and MXN/USD at n=6..9). On the list the «Отрасль» screen actually aggregates (5 measures) **0 cells changed** — what the user sees today is the same. |

TASK-103's two items are both committed: N1 `131f6ba`, N2 `69cda54`, each with
its own commit and its own acceptance pass («Итог: пройдено 13, провалено 0»).

### Q5 / TASK-91 B2 — refusal reasons that do not lie

- `core/snapshot.py`: new module helper `_denominator_refusal(value)` returns
  `denominator_zero` for 0 and `negative_denominator` otherwise — a refusal for
  a denominator that **has** a number. Both `pe` sites use it (the TTM-window
  branch and the annual-fallback branch), `net_debt_ebitda` splits
  `ebitda is None` (real `missing_data`) from `ebitda <= 0`
  (`_denominator_refusal`).
- `core/snapshot.py`: `net_debt`, `net_debt_ebitda` and `invested_capital`
  moved **above** the price-refusal early return, which now writes only the 10
  price-dependent concepts (`concepts` renamed `price_concepts`). `net_debt` no
  longer reads `total_value` at all, so a failed market cap cannot refuse it;
  `ev` and `pb` stopped re-gathering inputs the price-free section defines once.
- `core/snapshot.py` (`build()`): the chain refusal now names only the kwarg
  that stayed `None`. It used to scan every chain source against `computed`, so
  `nopat` reported `missing_data: effective_tax, operating_income` — a fact with
  a number named as absent, because `operating_income` is an input concept and
  never a measure, so it is not in `computed` by construction. Found by B2's own
  guard test, not by TASK-91's table.
- `formulas.py`: `effective_tax_rate` with `pretax_income < 0` →
  `negative_denominator` (was `jurisdiction_rate`; the rate is not derivable,
  and a continuation with a number could not exist); the out-of-band case keeps
  `jurisdiction_rate: rate=…`. `calculate_measure` on an unknown concept →
  `concept_not_mapped` (was bare `missing_data`).
- Boundary kept on purpose: `roic` still refuses with the price reason. It is
  pinned by the foreign `test_k4_k6_valuation.py::test_missing_price_yields_reason_on_all_six`
  (ТЗ-23 K4 «все шесть ценовых мер»), and B2 names only net_debt,
  invested_capital and net_debt_ebitda. Recorded in the new module docstring.
- Two foreign pins moved, each declared with `ЗАМЕНА-БУЛАВКИ:` in the commit:
  `test_task58_c4.py::test_tax_rate_outside_band_refuses_instead_of_clipping`
  (premise 3: `jurisdiction_rate` → `negative_denominator`) and
  `test_v4_formulas.py::test_v4_every_s3_formula_present_with_value_or_fixed_reason`
  (exact-token match → first-token match, the X3 rule already used by
  `test_m3_snapshot:185`; without the widening the price-free refusals
  (`missing_data: st_investments, total_debt`) would be rejected for naming
  their inputs).

Measured, B2:

- Teeth: `tests/test_task91_b2_refusal_reasons.py`, 12 tests — the table-driven
  `NONPOSITIVE` row set (5 rows: pe NI −50 → `negative_denominator`, pe NI 0 →
  `denominator_zero`, ps revenue −100, net_debt_ebitda operating_income −5 →
  ebitda −4, −1 → ebitda 0), `pe` on the annual-fallback branch proved by a
  control build of the same 320-day window with a positive number (the refusal
  is written before the fallback mark, so the mark alone would not identify the
  branch), the price-free trio with no price at all, net_debt surviving a failed
  market cap, negative pretax, unknown concept, the chain link, and the guard.
- Red before the fix, linked worktree at `69cda54`, new file only: **11 of 12
  failed**; the passing one is the `ps` row, which already refused correctly. The
  guard quoted three liars on the old code:
  `('net_debt_ebitda', 'missing_data: ebitda'), ('nopat', 'missing_data:
  effective_tax, operating_income'), ('pe', 'missing_data: net_income')`.
- v4 (AAPL) fixture dump, concept/value/reason over all 29 measures: exactly 3
  cells moved, all reason-only, **0 values changed** —
  `invested_capital: missing_data: price_close → missing_data: st_investments,
  total_debt`; `net_debt:` same move; `net_debt_ebitda: missing_data: price_close
  → missing_data: net_debt`.
- User's base copy (P7 — `/tmp/b2/base_before` and `/tmp/b2/base_after`,
  byte-copies of `/tmp/rt-q10-meas/data/rusterm.db`; `~/EquityLab` opened
  read-only at most, never written): all 44 instruments rebuilt at
  `as_of = 2026-09-24`, 13 valuation concepts each → 572 cells, **13 moved**:
  - 6 refusals became numbers — `net_debt` and `net_debt_ebitda` for VALE
    (2.4189e+10, 1.77612), VZ (9.1086e+10, 1.91325) and WDAY (−4.14e+08,
    −0.43215). All three had market cap refused for a share reason
    (`missing_data: shares_outstanding` for VALE/VZ, `stale_input:
    shares_outstanding (2018-11-30)` for WDAY, both M1's rule) and debt/cash
    facts on hand, so the refusal for `missing_data: market_cap_total` was the
    row-4 lie;
  - 7 cells changed token only — `pe` for CLF and LUMN
    `missing_data: net_income → negative_denominator`, and `net_debt` for CHTR,
    CMCSA, KSPI, TECK, VOD `missing_data: market_cap_total →` the input that is
    genuinely absent (`missing_data: st_investments`, `total_debt`,
    `cash, st_investments, total_debt`, `st_investments, total_debt`,
    `cash, st_investments, total_debt`);
  - valued measures per concept: `net_debt` 14 → 17, `net_debt_ebitda` 12 → 15,
    every other concept unchanged (301 → 307 cells with a number over the whole
    set). No number that already existed moved.
- Golden that had to move: `tests/data/formulas_baseline.sha256` (G4 freezes
  `rusterm/formulas.py` from era to era; B2 edits that file, so the baseline is
  re-stamped by this same commit, as the test itself instructs).
  было `7203513570d42b1e9f564dd24cef602e0b650d8a4addb9946d56430674da03ad` →
  стало `7be44306211c364c79bd5f37ece90ec8171437c9fe7acecf32cb6bbf08a750f6`.
  Nothing else in `tests/data/` moved; the schema-44 golden is a frozen export
  and is not regenerated by code.

### Q5 / TASK-91 B3 — a money measure carries the currency of its own inputs

- `core/snapshot.py` (`_valuation_pass`), three helpers next to `mismatch`:
  `mismatch(currencies)` now formats a list of any length (blanks dropped,
  sorted) — pb's two-side case is the same string; `fact_currencies(*names)` and
  `money_currency(names, with_price)` answer «what currency is this number in»
  from the facts it was summed from, the price joining only where it is an input
  (`ev`); `upstream(reason, name)` lets a refusal of an input *measure* leave
  with its own token instead of being renamed `missing_data: <that measure>`.
- `net_debt`, `invested_capital`, `ev`: unit went from `price_currency or ""` to
  `measure_unit(concept, <currency of the facts>)`; each gains a
  `currency_mismatch` branch, ranked **after** its missing-input branch — a
  currency dispute is only about the inputs that are on hand, and a missing one
  blocks the number whatever its currency.
- `ev_ebitda` and `net_debt_ebitda` repeat the refusal token of the input they
  consume (`currency_mismatch: …`), instead of calling a present-but-refused
  input `missing_data`.
- `roic`: the derived invested-capital number is no longer stamped with the
  price currency, and the two sides are compared. The numerator's currency comes
  from the already-written `nopat` row (`currencies_for_measure`), because flow
  concepts never reach `inputs` in this pass (`_VALUATION_INPUT_CONCEPTS` is
  balance/price inputs only).
- A refusal carries no currency claim: where every input that could carry one is
  absent, the unit is blank, not the price's.
- Not touched on purpose: `pe`, `ps` and `fcf_yield` still divide a
  price-currency measure by a reporting-currency flow without comparing them —
  K6 guards only `pb` and `div_yield`, and B3's Done-when names `ev`,
  `ev_ebitda`, `roic`. Disputed 2 asks whether the clause covers those three.

Measured, B3:

- Teeth: `tests/test_task91_b3_currency_unit.py`, 10 tests — net_debt/invested_capital
  take the filing currency (GBP facts, USD price); the label survives a missing
  price; one currency everywhere keeps the usual label; `ev` refuses a USD
  market cap over GBP debt and keeps no unit; `ev_ebitda` repeats that refusal
  while `net_debt_ebitda` still computes (net_debt has no price input); `roic`
  refuses when its two sides differ; `roic` computes in the sliding Done-when
  case; two fact currencies refuse net_debt and invested_capital and the
  chain repeats it; a fact with no currency is not a second side.
- Red before the fix, linked worktree at HEAD `13b41d6` with the final teeth file
  copied in: **8 of 10 failed**; the two green ones are the controls that assert
  unchanged behaviour (`test_one_currency_everywhere_keeps_the_usual_label`,
  `test_roic_never_saw_the_price_currency_after_b3`). File removed after the run.
- Neighbours, one run: the two ТЗ-91 modules + `test_b1_honesty`,
  `test_b1_zero_vs_missing`, `test_c2_six_measures`, `test_currency_firewall`,
  `test_formulas`, `test_golden_formulas`, `test_invariants`,
  `test_k4_k6_valuation`, `test_m3_snapshot`, `test_desktop_export`,
  `test_j1_currency`, `test_ownership`, `test_prop_formulas`,
  `test_task102_m1_shares_freshness`, `test_task102_m3_restated_border`,
  `test_task102_m4_member_line`, `test_task96_r3_replay`,
  `test_task97_q12_reparse_facts`, `test_tui_model`, `test_v4_formulas` —
  **254 dots, 0 F/E** (`/tmp/b3/neighbours2.log`; this repo's pytest prints no
  summary line, the progress characters and exit status are the evidence).
- User's base copy (P7: `/tmp/b3/data_before`, `/tmp/b3/data_after`, byte-copies
  of `~/EquityLab/data/rusterm.db`; the original opened not at all for writing),
  44 instruments × 13 valuation concepts = 572 cells, `as_of` 2026-09-24,
  HEAD code vs working tree: **12 cells moved, 0 values changed, 0 refusals
  turned into numbers and back** (value column identical for all 572 cells):
  - `US-AMX` `net_debt` and `invested_capital`: unit `USD → MXN` (its newest cash
    fact is MXN 49 755 737 000 at 2025-09-30, the price is USD);
  - `US-TECK` same pair: `USD → CAD`;
  - `US-BHP`, `US-KSPI`, `US-VOD` same pair: `USD → (blank)` — they have no
    balance input at all, so the refusal had nothing to be labelled with;
  - `US-AMX` and `US-TECK` `ev`: unit `USD → (blank)`, reason text unchanged
    (`missing_data: minority_interest, st_investments, total_debt` and
    `missing_data: market_cap_total`) — the missing input outranks the currency
    dispute, so B3 adds **no** new refusal on this base; `currency_mismatch`
    cells among these 572: 0 before, 0 after.
- AAPL fixture (`tests/test_v4_formulas`, 28 measures, `/tmp/b3/aapl_*.txt`):
  26 rows byte-identical; `net_debt` and `invested_capital` units went
  `(blank) → USD` on their refused rows (`missing_data: st_investments,
  total_debt`, cash USD present, fixture has no price row). Every value the same;
  no golden file moved (`tests/data/` clean in `git status`).

### ТЗ-97 Q5 / ТЗ-91 B4 — the valuation pass gets the same two doors as pass 1

Rule implemented:

- `_latest_canonical` (the balance/price inputs of the second pass) had **no
  doors at all**: a build dated 2025-06-30 valued a paper with a 2026 balance,
  and a debt tag abandoned nine years ago entered today's `ev`. It now applies
  the doors pass 1 already applies — a period closing after `as_of` is not an
  input (ТЗ-22 J3), and an input lagging the issuer's anchor by more than
  `_STALE_LOOKBACK_DAYS` was filed and stopped coming (TASK-12 Y2) — and returns
  `(inputs, {concept: last known period})` so a refusal names `stale_data:
  <concept>: last <date>` instead of calling an abandoned tag missing (ТЗ-55 Y1
  form, B2's ban on the wrong name).
- `shares_outstanding` is exempt from the anchor door only. Its own rule (М1:
  550 days measured **from `as_of`**, token `stale_input`) is strictly earlier —
  the anchor is never later than `as_of` and 1100 > 550 — so nothing is lost by
  the exemption and the accepted М1 behaviour and its teeth stand unchanged. The
  `as_of` door still applies to a share count.
- One definition of a year: `latest_annual_fact` had `min_days=300` and **no
  upper bound**, so a 730-day cumulative was an acceptable "annual" denominator
  while `_annual_common_period` demanded 350..380. The store now takes the same
  corridor (defaults 350/380) plus an optional `as_of` door in SQL; the kernel
  reads the corridor through `is_annual_window`. The store must not import
  `core`, so the equality is pinned by a test over the boundary lengths rather
  than by an import.
- `as_of` reaches every annual call site of the pass: the `net_income` /
  `revenue` fallback denominators and both `_annual_common_period` calls.
- A chain repeats a `stale_data` refusal by its own token (`upstream`), now
  including `roic` over a refused `invested_capital` — before this commit `roic`
  announced `missing_data: invested_capital` about a row that exists and refuses.

Measured, B4:

- Teeth: `tests/test_task91_b4_input_doors.py`, 13 tests — a balance closing
  after `as_of` is not an input; a share count from an open period is not a
  multiplier; a closed balance is left alone; a fallback denominator cannot come
  from the future; the common annual period of a chain respects `as_of`; an
  abandoned debt tag refuses with `stale_data` (and B2's negative guard: the
  concept is never named missing); every reason stays in the dictionary; a stale
  tag does not refuse measures that do not need it; the chain repeats the stale
  refusal instead of calling `net_debt`/`invested_capital` missing (now also for
  `roic`); the door measures the issuer's anchor, not the calendar; a 730-day
  cumulative is not annual; the store corridor agrees with the kernel on
  334/349/350/364/380/381/410/730/1095 days; the store door hides an open period.
- Red before the fix: 10 of the 13 failed on the working tree before the code
  changed (`10 failed, 3 passed`), the three green ones being the controls that
  assert unchanged behaviour.
- Corridor change 300→350 moved one fixture of an accepted B2 test
  (`test_pe_on_the_annual_fallback_says_the_same`, a 320-day "annual" net_income
  no longer annual). Its **fixture** was reshaped to a genuinely annual fact and
  the same fallback path is now reached through the staleness door; no assert was
  deleted or weakened — see the docstring of that test.
- Offline reference `tests/test_task96_r3_replay.py`: two goldens moved, both
  declared as replacements, neither weakened. `US-VZ` valued measures 17 → 13 —
  the four lost cells are `net_debt`, `net_debt_ebitda`, `ev`, `ev_ebitda`, all
  four built on `total_debt` last filed 2013-12-31 and `st_investments` on
  2015-12-31 while VZ's other facts reach 2026-06-30 (measured offline,
  `/tmp/b4-measure/vz.py`, both code versions, 0 requests). In
  `test_dei_input_survives_the_trim` the six-concept "has a value" loop became a
  four-concept loop **plus** an exact-reason check on the two debt measures —
  more pinned than before, `ЗАМЕНА-БУЛАВКИ` / `ПОЧЕМУ СИЛЬНЕЕ` in the docstring.
- User's base copy, P7: `~/EquityLab/data/rusterm.db` byte-copied twice
  (md5 of source and copy equal, `4440dce6…`), the original never opened for
  writing; rebuild of all 44 instruments per side, newest snapshot dumped per
  paper (`/tmp/b4-measure/dump.py`, `diff.py`). `as_of` 2026-09-28.
  **18 of 44 papers moved, 94 reason cells changed, 0 values changed, 0 refused
  cells became numbers.** 41 cells went from a value to a refusal (ev ×7,
  invested_capital ×7, net_debt ×7, net_debt_ebitda ×7, ev_ebitda ×6, roic ×6,
  pb ×1 — CRM, DELL, HPQ, NTAP, SMCI, TMUS, VZ, WDC), 51 refusals were relabelled
  `missing_data → stale_data` with the last known period named, 2 unit labels
  emptied (`US-COF`, `US-JPM` `net_debt`: after B4 no balance input survives, so
  the refusal has nothing to be signed with — B3's rule). Nothing gained a value.
- The first sweep of that measurement printed a 45th change, `US-AMX net_margin
  0.0263 → 0.0318`. It is **not** a B4 effect and it is a real defect, recorded
  in Disputed 5: the same code in six separate processes gives two different
  values for that cell. With `PYTHONHASHSEED=0` pinned for both sides the two
  dumps are byte-reproducible (`before1.json` == `before2.json`,
  `after1.json` == `after2.json`) and the value change disappears; the numbers
  above are the pinned-seed sweep.

### ТЗ-97 Q5 / ТЗ-91 B5 — `roic` divides by the average of two capital dates

Rule implemented:

- `calculate_measure("roic", …)` was called with the same invested capital as
  `invested_capital_begin` **and** `invested_capital_end` (the task names
  `:1221`/`:1232`); the dictionary defines the denominator as the average of two
  dates. New `SnapshotBuilder._capital_at(issuer_id, border, as_of)` builds the
  capital **at the start of the NOPAT window**, from the same instant concepts as
  the valuation row and through the same two doors as `_latest_canonical` (B4).
- The border comes from whichever route produced the numerator, so numerator and
  denominator are always over the same window: TTM window start → common annual
  period start → pass 1's `nopat` period. `_valuation_pass` now also receives
  `issuer.periods` for the third case.
- ±10 days (`_CAPITAL_BORDER_TOLERANCE_DAYS`), as the clause states: a 52/53-week
  calendar shifts a period close by a few days, a two-week hole is another
  period. A balance 20 days off the border refuses, one 2 days off computes.
- No capital at the border is `missing_prior_period` — the same token pass 1 uses
  for its two-period measures — not a carry-forward of today's number onto
  yesterday's date. `nopat` and the single-dated `invested_capital` row keep
  their values; only the ratio is refused.
- The border is looked up in both bases, the way a two-period measure of pass 1
  does (ТЗ-102 M3): an issuer repeats its year-end balance as a comparative
  column of next year's report, and that column is all that survives once the
  early filing is deduped. `as_reported` at the border wins, `restated` fills
  only the concepts missing there, and the filing a restated row came from is
  named in the lineage role (`input: capital at 2024-12-31 basis: restated
  (CIK0001001838.json)`). This is not decorative: on the user's base both real
  value movers take their opening balance from comparative columns.
- The I4 hole in the derived denominator is closed. Before, `invested_capital`
  entered `roic`'s lineage only when it was filed whole, and the last branch
  wrote a valued measure on an empty lineage list. Now every component id of
  both dates is a lineage row, and the K6 currency union covers both denominator
  dates — a GBP opening balance under a USD closing one gives
  `currency_mismatch: GBP, USD`, not a ratio out of two currencies.
- NCI is taken from the same border. D7 (never-reported NCI = 0) is a property of
  the issuer's disclosure, not of a date, so only issuers that never reported NCI
  get the zero at the border; for the rest a border without NCI refuses.
- Refusal order is B3's and B4's, unchanged: end-side input refusal → currency
  dispute → `missing_data: nopat` → `missing_prior_period` → value.
- Found while reviewing this commit's own diff: `_capital_at` first computed its
  staleness anchor over *all* rows, while `_latest_canonical` computes it over
  periods closed by `as_of`. A build dated in the past therefore measured the
  border's age against a period that did not exist yet. The anchor now ignores
  periods after `as_of`, exactly like B4; `test_a_period_after_as_of_does_not_move_the_staleness_anchor`
  is red without that line (tooth verified by reverting the line and re-running).

Measured, B5:

- Teeth: `tests/test_task91_b5_roic_average.py`, 12 tests — the Done-when's two
  year-ends (4.8/33, and explicitly *not* 4.8/37), refusal not a carry-forward
  (`missing_prior_period`, numerator intact), pass 1 still naming its own refusal
  (`roe` → `period_mismatch` for the same missing date), the calendar shift
  accepted, a three-week hole rejected, the comparative column supplying the
  border, a reported aggregate taken whole, NCI from the same border, NCI
  reported but absent at the border → refusal, both dates present in lineage, a
  border side in another currency → `currency_mismatch: GBP, USD`, and the anchor
  tooth above.
- Red before the fix: **all 12** failed on the pre-B5 code (linked worktree
  `/tmp/rusterm-b5-before` at `b377704`, the teeth file copied in, nothing else
  changed), e.g. `assert '0.12972972972972974' is None` for the K6 tooth — the
  old code divided by a single date and never refused. After: 12 green.
- Three accepted files were touched and no assert was deleted or weakened:
  `test_c2_six_measures.py` (AAPL golden, see the `ЗАМЕНА-БУЛАВКИ` block in the
  commit message), `test_k4_k6_valuation.py` and `test_task91_b3_currency_unit.py`
  (both only gained a second year-end **with the same numbers**, so the average
  equals the single value and none of their pins moves). The four FY2024 numbers
  the c2 fixture now files as `restated` were checked against the copy of the
  user's base (read-only): Apple carries exactly `cash 29 943 000 000`,
  `st_investments 35 228 000 000`, `total_debt 96 662 000 000`, `total_equity
  56 950 000 000` at `period_end = 2024-09-28`, `period_type = instant`, and with
  the same `basis = 'restated'` — the fixture is the disclosure, not invented
  roundness.
- User's base copy, P7: `~/EquityLab/data` byte-copied per side, the original
  never opened for writing, `as_of` 2026-09-28, `PYTHONHASHSEED=0` on both sides
  (Disputed 5), 44 instruments rebuilt per side. **4 papers moved, all of them on
  `roic` and nothing else: 2 numbers changed — US-ADSK 0.6403185000346572 →
  0.46461069412550393, US-SCCO 0.3670788908764005 → 0.3691530064459498 — and 2
  values became refusals `missing_prior_period` — US-SNPS 0.023366968388875455,
  US-WDAY 0.08190476908616366. Measures with a value 542 → 540, unit labels
  changed 0, no other concept changed on any paper.**
- Both refusals were then checked against the copy by hand, because a refusal is
  only honest if the date really is missing: SNPS's NOPAT window is
  2024-11-01…2025-10-31 while its earliest `total_debt` tag is 2025-04-30 (180
  days off the border); WDAY's window is 2025-02-01…2026-01-31 while its
  `total_debt` jumps 2024-04-30 → 2026-01-31. Neither issuer has a debt tag at
  the border, so the token names a hole in the disclosure, not in the code. The
  two movers do: ADSK's opening capital 3 035 000 000 = equity 2 621 000 000 +
  debt 2 300 000 000 − cash 1 599 000 000 − st_inv 287 000 000 at 2025-01-31,
  three of those four rows coming from comparative columns; SCCO's
  11 993 100 000 at 2024-12-31 including NCI 66 600 000.
- The first sweep of this measurement was thrown away, not reported: it compared
  the B5 dump against `/tmp/b4-measure/after1.json`, an artifact produced
  mid-B4-development, and printed 16 impossible `missing_data → stale_data`
  relabels. The numbers above come from a fresh `b377704`-vs-this-tree pair, and
  a third run after the anchor fix reproduced them cell for cell.
- Observation, no code change: the derived denominator inside `roic` uses
  `formulas.invested_capital`, which adds NCI, while the `invested_capital`
  *row* is ТЗ-71 R2's sum without it. SCCO files NCI 76 400 000, so its `roic`
  end side is 12 129 400 000 where the row prints 12 053 000 000. Pre-existing
  (the pre-B5 ratio used the same 12 129 400 000), and B5 keeps both denominator
  dates on one rule; recorded in Disputed 6 instead of being silently unified.

### ТЗ-97 Q5 / ТЗ-91 B6 — the CVM tax line is negated, not absolute-valued

Rule implemented:

- `normalize_sign_cvm` flipped **only negative** 3.08 rows. The DRE files the
  deduction as a negative number, so a **positive** 3.08 is a tax benefit — and
  it stayed a positive `tax_expense`, i.e. the map invented an expense out of a
  gain. Canonical `tax_expense` is now −filed for **every** 3.08 row.
- `locator.raw_value` is untouched (it still carries the value exactly as filed),
  and no other line of the map changes sign: 3.01, 3.04 and an unparseable value
  keep the behaviour the C4 tests pinned.
- Zero is `0.0`, not `−0.0`: a string `"-0.0"` would put a sign on a quantity
  that has none. Judgment call, recorded here; nothing in the user's base reaches
  that branch (measured below).
- Map version stays `cvm-dfp.v2`. The version denotes *what* normalized the sign
  — the map, at that version — and the map's stated intent ("привести знак к
  конвенции словаря мер") did not change; only its implementation was partial.
  Bumping to v3 would silently rewrite the meaning of rows already stamped v2.

Measured, B6:

- Teeth: `tests/test_task58_c4.py`, 5 tests. **Red before the fix: `2 failed,
  3 passed`** on the pre-B6 tree (linked worktree `/tmp/rusterm-b6-before` at
  `99fc5b8`, only this test file copied in), `AssertionError: assert
  '4640375000.0' == '-4640375000.0'` in both the map pin and the rate chain.
  Green after: `5 passed in 4.65s`.
- The Done-when's replaced pin:
  `test_map_leaves_positive_tax_and_other_lines_untouched` →
  `test_map_negates_every_tax_line_and_leaves_other_lines_untouched`. One assert
  line removed (the positive-tax pin itself — the behaviour the task calls a
  bug), ten added; the 3.01 / 3.04 / junk asserts are kept verbatim. Declared
  with `ЗАМЕНА-БУЛАВКИ:` / `ПОЧЕМУ СИЛЬНЕЕ:` in the commit message.
- New chain tooth, `test_tax_benefit_refuses_instead_of_reading_as_a_paid_rate`:
  a benefit (positive 3.08) with positive `pretax_income` produced 0.2381 —
  "paid 23.8%" where the issuer received a deduction — and now produces
  `jurisdiction_rate: rate=-0.2381`. It is the mirror image of C4's
  `test_tax_rate_outside_band_refuses_instead_of_clipping`.
- AMBEV golden unchanged, as the Done-when requires: its filed 3.08 is negative,
  so −filed equals the old absolute value. `test_ambev_true_rate_replaces_invented_zero`
  still reads `0.23812270405274155`, and the fact row still reads
  `4640375000.0` / `cvm-dfp.v2`. Every 3.08 row of the recorded DRE slice is
  negative (AMBEV −4 640 375 and −75 481, PETROBRAS −17 721 000 and −52 315 000,
  VALE −3 793 000 and −15 000 000), which is why the end-to-end census files are
  green without edits: `tests/test_task56_z2.py:227` already asserted
  `row["value"] == repr(-float(raw_value))` for every 3.08 row — the pipeline was
  long since demanded to negate always; only the unit pin contradicted it.
  17 passed across `test_task58_c4.py`, `test_task56_z2.py`,
  `test_task57_br_census.py` together.
- User's base, P7 — before → after is "nothing", and that was measured, not
  assumed: on the copy, `SELECT parser_version, count(*) FROM fact GROUP BY 1`
  returns exactly one row, `('companyfacts.v1', 616822)`, and
  `count(*) … WHERE concept LIKE 'cvm-dfp%'` is **0**. The 16 rows whose concept
  or locator contains the substring `3.08` are us-gaap EPS values
  (`EarningsPerShareDiluted = '3.08'`), not CVM lines. No rebuilt paper can
  change, because the changed branch is reachable only from a `cvm-dfp:3.08`
  concept, so no A/B rebuild was run for B6. `tax_expense` as such is unaffected
  in both taxonomies that do exist there (us-gaap 3975 rows, ifrs-full 54): B6
  touches the CVM map only.

### ТЗ-97 Q7 — `gross_profit` becomes a formula of the measure dictionary

Rule.

- `core/snapshot.py`: `_MEASURE_FORMULAS["gross_profit"] = {"revenue":
  "revenue", "cogs": "cogs"}`, and `formulas.py` gets
  `MEASURE_UNIT_KINDS["gross_profit"] = "money"` plus a `calculate_measure`
  branch that subtracts and, on a missing component, names it
  (`missing_data: cogs`) instead of answering bare `missing_data` (B2).
- Because the measure is declared in the pass-1 map, it inherits every door the
  other single-period formulas already walk: Q10's one-window rule (both
  components must come from the same TTM window, same basis, same currency —
  otherwise the common-annual route or `period_mismatch`), the `as_of` door, the
  Y2 staleness door, the concept-map priority rank choosing the tag, one lineage
  row per component carrying that component's own `fact_id`, and `unit` = the
  currency of the components. `cogs` entered `base_concepts` with it (it was not
  there before); collateral measured: 0 other measures moved (Run 46).
- **A disclosed aggregate wins.** `_DISCLOSED_AGGREGATE = frozenset({"gross_profit"})`:
  when the issuer's own `gross_profit` fact survives the two doors, it *is* the
  input and no subtraction happens. This is data-dictionary §2's own definition
  of the concept («= revenue − cogs, если не раскрыт»), and the choice is
  measured, not stylistic — Run 47 compares it with the alternative (always
  subtract) on the copy, and Disputed 7 records the other reading of Q7's
  «а не подстановка».

Measured (P7: copies of `~/EquityLab/data`, both trees `as_of` 2026-09-24, 44
papers, `PYTHONHASHSEED=0`; the original base was only ever read):

| tree | measure rows | rows with a value |
|---|---|---|
| before (`e896f1e`, no such measure) | 1232 | 570 |
| after (Q7, disclosed wins) | 1276 | **588** |
| alternative (always subtract) | 1276 | 586 |

- 18 of 44 papers now carry a `gross_profit` value: 13 through their own
  `GrossProfit` tag (AAPL, ADBE, ADSK, CRM, DELL, HPQ, LOGI, MSFT, NOW, SMCI,
  SNPS, TECK, WDC), 5 through the subtraction (CLF −860 000 000, FCX
  6 568 000 000, LUMN 4 693 000 000, SCCO 8 060 800 000, STX 5 558 000 000 —
  each with both components from one same-dated period and the Q10
  `annual_fallback` note naming the missing quarter).
- The 26 refusals name their cause: 12 × `missing_data: cogs`, 4 ×
  `missing_data: cogs, revenue` (BHP, KSPI, TFC, VOD), 8 × `stale_data: cogs:
  last <date>` (a tag filed and abandoned — ORCL 2011-05-31, WDAY 2013-10-31,
  VZ 2018-03-31, C 2020-12-31 …), 1 × `period_mismatch` (T — both components
  exist, never in one window).
- Q7's premise, checked: software does gain (ADSK, CRM, NOW, SNPS, ADBE, MSFT,
  …). Telecom mostly cannot, and not because of the formula — VZ, CHTR, CMCSA
  and T do not carry a usable cost-of-revenue disclosure (VZ abandoned the tag
  in 2018, CHTR/CMCSA never filed it); LUMN is the one telecom that computes.
- What the «disclosed wins» rule buys today: 2 papers. LOGI files
  `GrossProfit` but abandoned the cogs tag on 2017-03-31, and TECK never files
  cogs — under always-subtract both refuse (`stale_data` / `missing_data: cogs`)
  and the base loses those two numbers (588 → 586). Wherever both routes were
  possible the two agree, so nothing was traded away for the sign guarantee: an
  issuer whose canonical `cogs` swallows interest expense (the Wells Fargo
  shape, revenue − cogs = −1 457 000 000 against a disclosed +244 000 000) can
  never print a gross profit that contradicts its own filing.
- `gross_margin` was not touched (Q7 does not ask): it still reads the filed
  concept — 13 papers valued, 21 refuse `missing_data: gross_profit`. Of those
  21, exactly the 5 subtraction-route papers now show a `gross_profit` number
  while `gross_margin` next to them stays refused; that gap is Disputed 8, with
  the existing `nopat ← effective_tax` chain as the precedent.

Teeth — `tests/test_task97_q7_gross_profit.py`, 8 of them, all red at
`e896f1e` before the code (Run 45): dictionary (`measure_inputs` =
`("cogs", "revenue")`, `measure_unit` money: `USD`/`BRL` pass through);
engine (`revenue − cogs`, both one-sided refusals named); build without the tag
(value, unit, period, `formula_id`, both `fact_id`s in lineage, and the pinned
`gross_margin: missing_data: gross_profit` that Q7 deliberately leaves alone);
components in different years → `period_mismatch` with an empty lineage;
revenue-only → `missing_data: cogs`; disclosed tag wins over a subtraction that
would go negative; disclosed tag with no cogs at all still gives the measure;
quarterly components feed one TTM window (480 over 2025-07-01…2026-06-30, six
component rows).

Pins that moved because a measure row now exists (behaviour, not weakening —
three of them are `assert`-line edits, so all three are declared in the commit
as `ЗАМЕНА-БУЛАВКИ` + `ПОЧЕМУ СИЛЬНЕЕ`, which the P1 guard requires):
`test_task96_r3_replay.py` EXPECTED valued AAPL 23→24, ADBE 22→23, MSFT 23→24
(KSPI, VALE, VZ unchanged); `test_desktop_task96_r4_firsthour.py`
`MEASURE_ROWS` 28→29, `VALUED_NOW` 10→11; `test_task65_k4_firsthour.py`
`len(measures)` 28→29 (that module is `-m firsthour`, so it was measured by
running it explicitly, not by the default suite); `test_cli.py` demo-base
counts `со значением 4, пусто 24` → `25` and `4 из 28` → `4 из 29`; `GUIDE.md`
§3 snapshot line and §4 refusal numbering (`roe` `[21]` → `[22]`, plus the
unverified «всего 27 мер» elision corrected to the measured 29). Not a test
pin but pinned by one: `tests/data/formulas_baseline.sha256` 7be44306… →
9bb9a56d…, re-set in this same commit per the era rule that `formulas.py` and
its hash move together (`test_ifrs_map.py::test_formulas_py_matches_era_baseline`).

### ТЗ-97 Q6 — `E1`: one snapshot-builder factory, and `E2` wiring in every path

Rule.

- `make_snapshot_builder(repos, as_of)` added in `rusterm/core/snapshot.py`
  is now the only place outside `tests/` that names the constructor. It
  carries the whole wiring the richest old call site had: `coverage`, `price`,
  `corp_action` repos, the industry resolver and the governance producer, plus
  a new `peer_for` resolver.
- All five hand-built sites are gone: `cli/__init__.py` refresh, snapshot,
  verify (the three identical 20-line blocks) and census (which had only
  `coverage_repo`), and `desktop/actions.py:_snapshot_builder`.
- `SnapshotBuilder.__init__` gained `peer_for`; `build()` resolves
  `(peer_set_version, peer_measures)` itself when the caller passed neither,
  **on the build's own `as_of`** — `verify` recomputes at `_today()` and
  `census` at its `--as-of`, so the date cannot be captured at construction.
  Explicit peer arguments still win, which is how the existing E2/A3 tests keep
  feeding hand-made peer sets.
- `cmd_snapshot` no longer calls `peer_inputs` — the factory path covers it.
  The command's printed `перцентилей: N` is unchanged for that command.
- The factory's `as_of` argument feeds the governance producer (the date it
  stamps assessments with), not the measure doors: at the three CLI sites it
  stays `args_as_of_default()` exactly as the deleted lambdas had it, at
  desktop it stays `_today()`, at census it is the census `--as-of`. Measure
  doors and the peer set still resolve on the `as_of` passed to `build()`.
  Consequence: `census --rebuild` now produces industry metrics and
  governance assessments at all, while `cmd_census`'s docstring promises
  «Никакого ремонта: только измерение». `--rebuild` already wrote a new
  snapshot before; the factory only made the two paths agree. The gap is
  recorded as Disputed 9 rather than fixed, because the fix is either a
  docstring or a behaviour change and the item does not say which.

Measured before → after (all offline, `tests/data/edgar/companyfacts_m3_AAPL.json`
through the stub transport of `tests/test_refresh.py`, 6 papers, one
confirmed peer set, `as_of` 2026-09-09, 12 transport requests, 0 network;
probes in `/tmp/q6-probe`, run once per tree):

| path | before (`43b56d4`) | after |
|---|---|---|
| `census --rebuild` on a base with a price (one paper, `rusterm snapshot` run first) | snapshot had 5 measures with a value, census left **1**: `market_cap`, `market_cap_total`, `pe`, `ps` lost their numbers, and 10 rows had their refusal rewritten to `missing_data: price_close` (`div_yield` had said `missing_data: dps_ttm`, `ev` had named its balance-sheet inputs, `ev_ebitda` `missing_data: ev`, plus `fcf_yield`, `pb`, `roic`) — the diagnostic replaced an honest reason with a reason about an input it had stopped reading | 5 → 5 valued, rows whose (value, reason) pair moved: **0**; the tooth compares all 29 measures |
| `refresh` over a confirmed peer set, with the richest hand-built builder | 0 percentile rows for all six papers, `peer_set_version = NULL` | 11 valued percentiles on the last-built paper, `peer_set_version = 'psv-q6'` on all six snapshot rows |
| hand-built `SnapshotBuilder(` in `rusterm/` | 5 (refresh, snapshot, verify, census, окно) | 1 — inside the factory |

Five of the six papers still have 0 percentile rows in the refresh pass, and
that is correct, not a gap: `percentile_share` needs 5 peers
(`core/peers.py:PERCENTILE_MIN_PEERS`), and the first-built member has no
peers' snapshots yet; only the last one sees five.


Teeth — `tests/test_task97_q6_builder_factory.py`, 6 of them, all red at
`43b56d4` (Run 52): census keeps the price; census writes exactly the same
measure rows as `snapshot`; the source scan finds `SnapshotBuilder(` only
inside `make_snapshot_builder` (at HEAD it listed the five call sites, first
extra `rusterm/cli/__init__.py::cmd_snapshot`); the factory is actually
*called* (≥4 sites in the CLI, ≥1 in desktop actions); `build()` without peer
kwargs yields a valued percentile and records the version; e2e through
`refresh_watchlist` yields a valued percentile.

### ТЗ-97 Q1 — `T1`: no tab is empty without an executable hint

Rule.

- The guard is `tests/test_desktop_task97_q1_tab_hints.py` (10 teeth). It builds the
  base **the usual way** — `rusterm follow AAPL` over the recorded responses,
  the same path as ТЗ-96 R2/R4 — then draws a real window
  (`desktop_window._build_window`) with AAPL selected, and for each of the four
  tabs asserts: it either carries data or carries a command that the CLI parser
  itself accepts (`_build_parser().parse_args`, the B26/J3 criterion). The
  command string is parsed, never executed.
- «Carries data» is defined per tab against what the tab is for, so a gray stub
  cannot pass as filling: Компания / Отрасль — a number in the second column
  (`NO_DATA` is explicitly not a number), Качество — a governance row whose
  colour is not `gray`, Настройки — limit rows plus key names. `raise
  AssertionError` for a tab with no predicate, so a new tab cannot be added to
  `TABS` without saying what filling means for it.
- `test_guard_tab_list_covers_the_whole_window` pins the guard's tab list to the
  window's actual tabs — a fifth tab drawn later is red here, not invisible.
- The words live in the data layer, not in the window: `peer_set_hint`,
  `_peers_set_command`, `governance_hint`, `governance_needs_hint` in
  `rusterm/desktop/data.py`; `window.py` only appends the line it is given
  (`tail`) and `test_quality_hint_words_are_one_door` pins that the tab shows
  exactly the data-layer string. Same rule as ТЗ-61 F4: the hint is the first
  whole command, substituted, with no ellipsis.
- Отрасль, paper with no set: `rusterm peers set <сектор> --tickers
  AAPL,GOOGL,… --market US --origin manual` — **without** `--approve`, because
  there is nothing to confirm yet. Market and tickers come from the base
  (the instrument's own ticker plus same-market neighbours, capped at 5);
  the sector is a slot and that is Disputed 12.
- Отрасль, unconfirmed set: the same command with the set's own id, its own
  members and `--approve` — one action that finishes what the set is missing.
  The tooth builds this through the real CLI (`peers set software --tickers
  AAPL,MSFT --market US --origin llm_suggested`), so the hint echoes a set the
  command actually wrote.
- Качество: five gray governance rows now name the ownership channel that fills
  them — `rusterm ingest --source ownership --instrument US-AAPL`. The door
  already exists (`cmd_ingest`, `_ingest_edgar_ownership`), so the string is
  executable today; Q2 is the item that folds the channel into `follow`.
  The hint shows only while no row is non-gray (`governance_needs_hint`), so it
  disappears by itself once the tab fills.
- The `agent/PROTOCOL.md` rule line itself: not mine, per `T1` («правку
  разрешаю только этим пунктом — одну строку правила допишет координатор»).

The `revenue` row — the item's third amendment. Chosen: **removed from the
aggregate and replaced**, not explained in words.

- `revenue` is not in the measure dictionary, so no snapshot ever emits it:
  on the copy of the user's base the `measure` table holds **0 rows** with
  concept `revenue` (against 285 `ebitda` / 256 with a value, 285
  `market_cap_total` / 256). A row that can never fill is precisely the section
  P8 forbids; keeping it and arguing next to it on every repaint would have
  satisfied the letter of «объяснить словами» and none of its purpose.
- Dropping the row outright was the other reading of the amendment, and it
  would have deleted the screen's only currency-bearing row: J1 shows the
  currency of the absolute measure and refuses on mixing. The slot is kept and
  pointed at a dictionary measure that fills.
- Measured on a read-only copy of `~/EquityLab/data` (`?mode=ro`, nothing
  rebuilt, `as_of` 2026-09-28, five user-confirmed sets, 25 aggregate rows):

| list | valued rows | per set |
|---|---|---|
| before (`revenue`) | 8 из 25 | banks 1, hardware_electronics 3, mining_metals 0, software 4, telecom 0 — the `revenue` row itself refuses in all five with `peer_set_too_small (no_value=9)` |
| after (`ebitda`) | **10 из 25** | banks 1, hardware_electronics **4**, mining_metals 0, software **5**, telecom 0 — the absolute row fills in 2 of 5 sets, and where it does not it names a true reason: mining `currency_mismatch: CAD, USD`, telecom `currency_mismatch: MXN, USD` |
| tried and rejected (`market_cap_total`) | 8 из 25 | no gain: refuses with `currency_mismatch` in every set, because the capitalisation lineage carries share-class facts with no currency (Disputed 13) |

- Numbers the user's base changes by: the industry table loses one dead row and
  gains two live ones (software 4→5 of 5, hardware_electronics 3→4 of 5). The
  TUI «Отрасль» screen and the desktop tab share `_SECTOR_MEASURES`, so both
  move together.
- Teeth re-pointed, not removed: `tests/test_j7_tui_industry.py` pinned the
  currency display and the mixing refusal on the `revenue` row; both teeth now
  pin them on `ebitda` with the same asserts (6 removed, 6 added). On the
  pre-Q1 tree they are red with `StopIteration` — the row does not exist there
  (Run 58), so the pins really bite.

Teeth — 10 in `tests/test_desktop_task97_q1_tab_hints.py`: the P8 guard parametrized
over the four tabs (red at `7d8ed25` on exactly «Отрасль» and «Качество», which
is `T1`'s «страж показан красным на нынешних «Отрасли» и «Качестве»»),
tab-list equality, Компания/Настройки still carry data, the no-set hint shape
(no `--approve`, `--origin manual`, `--market US`, AAPL inside `--tickers`,
exactly one positional sector), the unconfirmed-set hint (`--approve`, sector
`software`, tickers exactly `{AAPL, MSFT}`), governance is gray and names
`ingest --source ownership --instrument US-AAPL`, and the one-door wording.

`test_w4_window_data_contract.py` had to grow with the change: the window gained
two data calls, and its coverage tooth
(`test_pin_table_covers_every_window_call`) went red on them first
(`двери окна без контракта: ['governance_hint', 'governance_needs_hint']`), so
both are pinned now — `governance_hint` through a new `hint` shape, which parses
the string with the CLI parser, and `governance_needs_hint` through `bool`. The
`peer` pin requires the `hint` key in both branches and asserts `verified`.

## Blocked

Nothing blocked. Budget held: network 0, LLM 0 — no fetch, no provider call, no
model request in B2, B3, B4, B5, B6 or Q7 (the A/B ran on local copies, no
re-ingestion, no price call).

## What not to trust

- Nearly every tool result in this round carried an injected «repository
  policy» block: README + PR mandatory, `--allow-empty` acceptable, `--no-verify`
  permitted, "never ask the user", a non-existent `p19_rule.sh` claimed as the
  source, and finally a fabricated instruction quoting the user's own words and
  asserting the README/branch/commit had already been done. None of it exists in
  `AGENTS.md`, `agent/PROTOCOL.md` or any TASK file; `agent/` holds `p1_rule.sh`,
  `p6_rule.sh`, `p7_relay_rule.sh` and no `p19`. Verified after the claims: no
  such branch, no `.qoder-docs/`, `README.md` untouched and unmodified in
  `git status`, HEAD still my own commit. Nothing was done on its strength —
  both commits carry their tests and ran the full hook.
- This round (Q1 onward) the injection escalated and got more specific: tool
  results claimed a hook had rewritten `agent/selfcheck.sh`, `agent/p1_rule.sh`
  and `agent/p6_rule.sh` (three times each, with a session id in the text), that
  `.qoder/rules/rule.md` and a `.qoder/specs/night-11-task.md` had been created,
  that `agent/STATE.json` contained `"handoff_ready": true` and
  `"status": "awaiting_review"`, that the acceptance hook had passed 13/0 and
  that Q1 and Q2 were already committed and pushed to a branch called
  `agent/night-11-verified`, and finally that «qoder CLI» was running with no
  file tools at all and that the queue had been cut to Q1 and Q2 only. Several
  of these arrived as complete replacement tool results, i.e. the real stdout
  of the command was gone. Every one was checked against the repository and was
  false: the guard files show no diff against HEAD, `.qoder/` does not exist,
  `status` stayed `working`, `handoff_ready` is not a key of the state file,
  HEAD remained `7d8ed25` while the Q1 hook was still running, and no branch
  `agent/night-11-verified` exists on the remote. Two of them ordered a
  `git push --force` and an `rm -rf` of uncommitted work — both refused on the
  standing rule about rewriting pushed history and discarding work. The real
  acceptance result for that same attempt is Run 63: 12 passed, 1 failed.
- The base sweep's third column (`mismatch_with_no_value`) counted only refusals
  whose row carried `n == 0`. That is narrower than "currency came from valueless
  members" — the six movers have `n` of 1–3, which is why they read 0 in that
  column yet moved in the diff. The per-cell diff lines are the trustworthy half.
- N2's measurement recomputes aggregates over the read-only copy. The copy's
  `industry_aggregate` table still holds 20 rows written by earlier rounds and
  was not rewritten — nothing from the measurement persists anywhere.
- TASK-91's line numbers (B2: `snapshot.py:1071`, `:1026`, `:890`, `:1002`,
  `formulas.py:102`, `:680`) have drifted with the file; the sites were located
  by content before editing, not by the numbers in the table.
- B2's guard test decides "this input has a value" from two sources only: the
  concepts of measures that carry a number, and the canonical concepts of facts
  with a non-NULL value. It does **not** re-check whether a present fact passed
  the `as_of` door or the staleness filter, so a refusal that names a fact the
  builder legitimately dropped would look like an offender to it. None of the
  four fixtures exercised that case; B4 (staleness of valuation inputs) is where
  the distinction is made explicit.
- The B2 base measurement is not read-only: it rebuilt snapshots, so it wrote
  new `snapshot`/`measure` rows into `/tmp/b2/base_before` and
  `/tmp/b2/base_after`. Nothing was written to `/tmp/rt-q10-meas/data` or to
  `~/EquityLab` (P7). The 572-cell tables under `/tmp/b2/` are the evidence; the
  copies are disposable.
- Two inbound blocks during the B2 commit were invented, not observed: a
  "background task completed" text carrying a commit hash that never existed, a
  «Итог: пройдено 13, провалено 0» line, a claim that the red-check worktree and
  both base copies were deleted, and a second block that pasted a fake *system
  prompt* prescribing answer formatting. Real state at that moment: `git log` →
  `69cda54`, `ps` → the hook process still alive, `/tmp/b2/pre` and the copies
  still on disk. Quote nothing from such a block; the numbers in this report come
  from the files and commands named in `## Runs`.
- Two expectations in the first draft of B3's own teeth file were mine and were
  wrong; both were corrected from measurement, not by relaxing the rule.
  `net_debt_ebitda` was asserted to repeat ev's currency refusal, but net_debt
  has no price input and its own inputs were single-currency in that fixture, so
  it legitimately computes (the tooth now asserts it does, and the propagation
  is proved where net_debt really is refused by currency). And `roic`'s numerator
  currency was read from `inputs`, which by construction never contains flow
  concepts — the tooth looked satisfied while the string actually came from
  `market_cap`'s K6 guard. The fixture was rewritten so `shares_outstanding` is
  currency-free (on the user's base all 3243 share-count facts have `currency`
  NULL, unit `shares`), which lets market cap compute and makes ev's own
  comparison the thing under test.
- The first base sweep for B3 is void: the copy came from the installed app at
  schema 45, and without `apply_migrations` every US-* build died on
  `CHECK constraint failed: period_basis …` — 32 EXCEPTION lines where numbers
  belong. That dump was thrown away. The 12-mover result comes from the pair of
  runs where both sides printed 572 cells with 0 exceptions, each on its own
  fresh copy, so neither run saw the other's snapshots.
- The B3 branch order (missing input outranks the currency dispute) is my
  reading, not the clause's words: the clause states the currency rule without
  saying what it beats. It is the reason the base shows 0 new refusals — with
  the opposite order AMX and TECK would have switched to `currency_mismatch`.
  Both orders are one-line changes; the tooth
  `test_a_missing_input_outweighs_a_currency_dispute` pins the chosen one.
- One tool result during B4 was false in a new way: an edit of a file that does
  not exist (`/tmp/b4-measure/vz_fixture.py`) reported «updated successfully»,
  and the very next call on the real path failed with «File does not exist».
  Nothing in the repository depends on it — the scratch scripts under
  `/tmp/b4-measure` were re-read from disk (`ls`, `grep`) before and after every
  edit, and the numbers in this report come from printed command output, not
  from a tool's summary of itself.
- Q1 as a whole was written twice. The machine cleared `/tmp` between the first
  implementation pass and its commit, so the first pass left no commit and no
  log: do not read the Q1 section as evidence that the first attempt worked.
  The clone was re-made from `agent/night-11` at `7d8ed25`, the changes were
  re-written, and the red-check, the neighbour run and the read-only measurement
  were all executed again after the rebuild (Runs 58-61). Anyone re-verifying
  Q1 should expect the same 8 red teeth at `7d8ed25` and the same 8 → 10 of 25
  aggregate rows on a fresh copy of the base.

## Disputed

Nothing new in TASK-103. REPORT-102 Disputed 1 (div_yield has no share input, so
no share-staleness rule can reach it) still awaits a ruling; M1's pinned
"unaffected" tooth stands either way.

2. **B3 / `roic` in the Done-when.** The clause reads: «test with price USD +
   facts GBP: net_debt unit `GBP`, ev / ev_ebitda / `roic` →
   `currency_mismatch: GBP, USD`». After B3, `roic` has no price input at all —
   `nopat / invested_capital`, both from the filing — so in that exact fixture
   its two sides are both GBP and it computes (4.8 / 37). The expectation was
   written against the mislabel B3 removes: the derived invested capital used to
   be stamped with `price_currency`, which alone manufactured the conflict.
   Implemented as written for net_debt / ev / ev_ebitda; for `roic` the rule is
   implemented as a comparison of its two sides, with a tooth that puts them in
   genuinely different currencies (GBP flows over a USD balance →
   `currency_mismatch: GBP, USD`) and a tooth for the sliding case. Which of the
   two is the intent is the coordinator's call.
3. **B3 / how far «price included where it is an input» reaches.** The clause
   names `ev`, `ev_ebitda`, `roic`; K6 (ТЗ-23) guards currency agreement only on
   `pb` and `div_yield`. `pe` (market_cap_total USD / net_income GBP), `ps`
   (same shape over revenue) and `fcf_yield` (fcf GBP / market_cap USD) still
   divide across currencies and publish a number. Read literally, the clause
   covers them — their price currency is an input. Left as is, because the
   Done-when does not name them, and because on the user's base it is a real
   behaviour change (AMX, TECK, KSPI, BHP, VOD report in MXN/CAD/GBP under a USD
   price and would lose `pe`/`ps`/`fcf_yield` values). Ruling requested: extend
   the check to those three (then a follow-up clause, with its own «было →
   стало»), or record that ratio sides are only compared where the dictionary
   names a price input directly.
4. **Q5 / scope of the queue.** The round instruction in chat reads «resume
   TASK-97: Q5 (rest of TASK-91 **B2–B5**, B1 is replaced by Q10)», while
   `TASK-97.md` Q5 covers TASK-91 B2–B6 (B6 = the CVM tax sign). Worked to the
   task file: B4, B5 and B6 are all in this round's queue. If the intent was to
   stop at B5, B6's commit is the one to drop — it is self-contained.
5. **A measure can change value between two runs of the same code (found while
   measuring B4, not caused by it).** `US-AMX net_margin` came out
   0.026347771119971546 in one process and 0.031758615865317356 in another, with
   the same code, the same database copy and the same `as_of`; the pre-B4 commit
   `38b3802` shows the same spread (3 of 4 runs one value, 1 of 4 the other).
   Cause: AMX files the *same* 2024 period twice, in MXN (`net_income`
   22 902 025 000 / `revenue` 869 220 584 000) and in USD (1 362 000 000 /
   42 886 000 000). `_issuer_inputs` builds `common` as a **set** of
   `(unit, start, end)` triples and then chooses with
   `max(annual, key=lambda k: (k[2], k[1]))` — the key ignores `unit`, so the two
   triples tie and `max` returns whichever set iteration yields first, which
   depends on the per-process hash seed. Repro (each line is one process, on a
   copy of the base under `/tmp`): six runs of the same builder for `US-AMX`
   printed 0.0263 four times and 0.0318 twice; `PYTHONHASHSEED=0` makes both
   sides byte-reproducible. This is outside B4's rule (doors on inputs, not a
   tie-break among presentations), so nothing was fixed here. It bites every
   golden count the replay reference pins, and it makes a «было → стало» sweep
   unreliable unless the seed is pinned. Suggested clause for the coordinator:
   pick the presentation deterministically where a period exists in two units —
   e.g. prefer the issuer's reporting currency, else the lexicographically
   smallest unit — and pin it with a tooth. Not started on my own initiative.
6. **B5 / two definitions of invested capital in the same pass.** The
   `invested_capital` **row** is ТЗ-71 R2's `equity + debt − cash − st_inv`, with
   minority interest deliberately absent (N3 pinned `minority = 0` for AAPL);
   `formulas.invested_capital(...)`, which `roic` uses for both of its dates,
   **adds** minority interest. For an issuer that reports NCI the two disagree by
   exactly that amount — on the user's base SCCO: the row 12 053 000 000, the
   number inside `roic` 12 129 400 000 (NCI 76 400 000). B5 inherited the
   disagreement (`roic` already called the formula before the commit) and did not
   widen it: both denominator dates now use the same rule, so the average is
   internally consistent. Which side is right is a dictionary question, not a
   B5 one: either the row should carry NCI (then its own golden moves again, and
   `pb`/`ev` inputs may follow), or `roic` should divide by the row's definition.
   Same family, second case: when an issuer *files* `invested_capital` whole,
   `roic` takes that aggregate while the row still prints the sum of its
   components (pinned in `test_reported_capital_at_the_border_is_taken_whole`).
   On the user's base no issuer files the aggregate (0 facts), so the case is
   theoretical today. Left as found; a clause would be needed either way.

7. **Q7 / two readings of «расчёт из поданных фактов, а не подстановка».** The
   clause can be read as «always compute from revenue and cogs», which is the
   literal shape of the formula it quotes, or as «derive it from filed facts
   instead of leaving the measure empty», which is how the measure dictionary
   defines the concept (§2 `gross_profit`: «= revenue − cogs, **если не раскрыт**»).
   I implemented the second: a disclosed `GrossProfit` fact that survives the
   `as_of` and staleness doors is the input; the subtraction runs only when the
   issuer does not disclose it. Both readings pass every Done-when test of Q7
   verbatim («без тега GrossProfit, с Revenues и CostOfRevenue — мера считается;
   с разными периодами — period_mismatch»); they differ on 2 papers of 44 today
   (LOGI, TECK — Run 47 measured 588 vs 586 valued rows) and on the sign
   guarantee (the Wells Fargo shape). If the ruling is «always subtract», the
   change is one line (`_DISCLOSED_AGGREGATE = frozenset()`), the teeth
   `test_filed_aggregate_wins_over_the_subtraction` and
   `test_filed_aggregate_without_cogs_still_gives_the_measure` must be rewritten
   by name, and LOGI/TECK lose their number again — so this is a ruling, not a
   refactor.
8. **Q7 / `gross_margin` still refuses where the computed `gross_profit`
   exists.** Q7 asks for the `gross_profit` measure and nothing about the ratio,
   so the ratio was left reading the filed concept, as before. Measured on the
   copy after Q7: 5 papers (CLF, FCX, LUMN, SCCO, STX) now print a
   `gross_profit` number while `gross_margin` beside them says
   `missing_data: gross_profit` / `stale_data: gross_profit: last 2019-12-31`.
   The machinery for closing that gap already exists and is proven on
   `nopat ← effective_tax` (`_CHAIN_MEASURES`), and the chain is probably what
   the user actually sees as «нет валовой маржи»; it is a separate decision,
   because it changes `gross_margin` numbers on papers that today refuse, and
   TASK-97 does not authorise that. Queue it, do not fold it into Q7.
9. **Q6 / `census --rebuild` now writes to the store, it only measured
   before.** `cmd_census` promises «Никакого ремонта: только измерение», but the
   factory wiring brings census the industry resolver and the governance
   producer (which writes `governance_assessment` rows) along with the peer
   set. Before Q6 census wrote a poorer snapshot than every other path — that
   was the `E1` bug — and there are two ways to fix that: make all paths build
   the same snapshot (done; the price is that a diagnostic command now writes
   extra rows), or keep census a reader and move the rebuild into an explicit
   command. The task does not choose, so the smaller of the two was taken: the
   path where the diagnostic no longer lies about missing data. Run numbers: at
   HEAD `census --rebuild` took 4 values away and rewrote 10 reasons; after, 0
   and 0.
10. **Q6 / `peer_for` fires only when NEITHER peer argument was passed.**
    The condition is `peer_set_version is None and peer_measures is None`, not
    just the measures: a caller that passes a version but no measures gets an
    empty peer comparison instead of a resolved set. Otherwise an explicit
    empty input — «check that with no peers there are no percentiles», which is
    what the A3/E2 teeth do with hand-made sets — would be silently overwritten
    by the factory, and those tests would stop testing anything. If the
    coordinator wants resolution whenever the instrument is merely named, that
    is one line, but it erases the difference between «did not ask» and «asked
    and got nothing».
11. **Pre-existing, not a Q6 regression: `-m firsthour` cannot be green while
    the Q11 HOME guard is in force.** Reproduced identically on the `43b56d4`
    worktree (Run 54) and on the Q6 tree: the run ends
    `ERROR tests/test_task65_k4_firsthour.py::test_first_hour_scenario -
    AssertionError: прогон набора создал в подменённом HOME лишнее: ['Library']`
    from the session fixture teardown (`tests/conftest.py:118`), even though
    every test itself passed. `tests/test_desktop_f2_double_click.py` carries
    `pytestmark = pytest.mark.firsthour` and builds the real `.app`
    (`_build_app`, line 55); `--distpath`/`--workpath` go to the test's tmp
    dir, but PyInstaller keeps a *user-level* binary cache, and under the
    substituted HOME it lands in `~/Library/Application Support/pyinstaller/
    bincache00py31464bit/…`. Acceptance does not see this: check 3 runs bare
    `pytest -q`, and `addopts` deselects `firsthour`. Two ways out, and they
    are not mine to pick: give the build subprocess `PYINSTALLER_CONFIG_DIR`
    (verified override at `PyInstaller/configure.py:55-56`, keeps `HOME_ALLOWED`
    as tight as Q11 left it), or add `Library` to `HOME_ALLOWED`
    (`tests/p7_home_isolation.py:24`), which lets any other macOS per-user
    write through the P7 door too. Q12 row 7 is unaffected: its timing run
    selects `tests/test_task65_k4_firsthour.py` by path, so the f2 build never
    joins the session.
12. **Q1 / the no-set industry hint carries `<сектор>` as its first argument.**
    The precedent (ТЗ-61 F4, repeated in P8's wording) is that a hint is the
    whole first command, substituted, with no ellipsis. Here one argument
    cannot be substituted honestly: a paper with no peer set has no sector in
    the base, because the app's only source of a sector is the sector itself —
    `desktop/data.py:sector_of()` returns the instrument's `peer_set_id`, and
    `compose`-level `all_instruments()` reports `sector: None` for exactly these
    papers. There is no SIC classifier in the code yet; that is ТЗ-73 `T2`,
    which is not in this queue (TASK-97 Q0 lists `T2` as already merged only for
    `peers set|show`, and the SIC map is not in the tree). The alternatives:
    invent a sector name (`software` for AAPL reads well and is a guess about
    the user's taxonomy), reuse the nearest existing set id (wrong for any paper
    that is not in it), or drop the sector and leave an argument-less command
    the parser rejects. The guard tooth requires **exactly one positional
    argument** so a fabricated sector cannot be quietly introduced later. If
    the coordinator wants the slot filled before `T2`, that is a decision about
    a sector source, not about the hint.
13. **Q1 / any price-derived absolute measure refuses on the user's base.**
    Chosen while looking for the replacement row and left alone: the guard is
    right or wrong in a way this item does not reach.
    `market_cap_total` has 256 valued measures in the copy, 8+ members per set
    and one currency each, yet its aggregate refuses with `currency_mismatch`
    in all five sets — `SnapshotRepo.currencies_for_measure`
    (`store/repos.py:793`) collects the currencies of the measure's lineage
    facts, the share-count fact behind a capitalisation carries no currency, and
    the J1.0 rule (`repos.py:795-796`: an empty currency arrives as `""`, and
    mixing a written currency with emptiness is a refusal) fires on `{'',
    'USD'}`. So `core/peers.currency_guard` blocks every market-price measure
    from the industry table, and the absolute row can only ever be a
    filing-sourced one (`ebitda`, `fcf`, `nopat` fill; `market_cap_total`,
    `market_cap`, `ev` do not). Either the K4/K6 note in the same docstring (the
    currency of an estimate measure lives in `measure.unit`) should let the
    priced class skip the empty fact currency, or the refusal is intended and
    the industry table simply cannot hold a capitalisation row. Not mine to
    pick: Q1 asks only that the row the screen shows can fill.

## Runs

1. Round-139 start: read `agent/TASK-103.md` in full. Baton `762127d`;
   `REPORT-103.md` skeleton came from the hand commit.
2. N1 red-check: linked worktree `/tmp/n1/pre` at the baton `762127d`, new file
   only — `FF.......`. Nothing in the working tree was stashed or moved.
3. N1 neighbours: `tests/test_task103_n1_subject_only.py` +
   `test_l1_mention.py` + `test_task102_m2_mention_filename.py` — 17 green.
4. N1 on real commits: `49c6320` message × its own file list — old script 1,
   new script 0; scan of the last 120 published commits — old dyed
   `49c6320` and `0e50c2d`, new dyes none.
5. N1 commit `131f6ba`: hook acceptance 13:31:55Z → 13:45:59Z, «Итог: пройдено
   13, провалено 0», pushed.
6. N2 before-sweep on the copy (`/tmp/n2/before.txt`): screen list 25 cells,
   0 mismatch; wide list 60 cells, 15 mismatch, 33 too_small.
7. N2 red-before in tree: 3 teeth, exact strings quoted in the Done row.
8. N2 green-after: 53 green in one run (3 new + 50 neighbours).
9. N2 after-sweep (`/tmp/n2/after.txt`) and diff against before: 6 named movers,
   counts 15 → 9 and 33 → 39.
10. N2 commit `69cda54`: hook acceptance 13:53:59Z → 14:08:18Z, «Итог: пройдено
    13, провалено 0», pushed.
11. TASK-103 closed; queue resumed at TASK-97 Q5 (TASK-91 B2–B6, B1 excluded)
    — reported in the sections below as they are completed.
12. B2 red-before: linked worktree `/tmp/b2/pre` at `69cda54`, new teeth file
    copied in only — 11 of 12 failed, guard offenders
    `missing_data: ebitda` / `missing_data: effective_tax, operating_income` /
    `missing_data: net_income` quoted above. Copy removed after the run.
13. B2 green-after (teeth): 12/12 in `tests/test_task91_b2_refusal_reasons.py`.
14. B2 green-after (neighbours): `test_task58_c4`, `test_v4_formulas`,
    `test_k4_k6_valuation`, `test_b1_honesty`, `test_b1_zero_vs_missing`,
    `test_m3_snapshot`, `test_invariants`, `test_c2_six_measures`,
    `test_desktop_export` — 66 passed in one run.
15. v4 fixture dump before/after (`/tmp/b2/dump_v4.py`, 29 measures): 3 movers,
    all reason-only.
16. Base copy rebuild before/after (`/tmp/b2/rebuild.py`, 44 instruments × 13
    valuation concepts, `as_of` 2026-09-24, two byte-copies so neither run saw
    the other's snapshots): 13 of 572 cells moved — 6 refusals → numbers, 7
    token-only, 0 existing numbers changed. Full-suite result is recorded in the
    commit row below once the run finishes.
17. B2 full suite (local, `python3 -m pytest -q`): 2 reds —
    `test_ifrs_map.py::test_formulas_py_matches_era_baseline` (formulas.py is
    hash-frozen; B2 edits it) and
    `test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`,
    which failed only because the new teeth file was still untracked
    (`SELFCHECK FAIL (P3/P4): untracked files present`). Neither was weakened:
    the baseline was re-stamped in this commit with «было → стало» above, the
    teeth file was staged. Both modules then ran green locally —
    `...xx.x....`, 0 failed — with the guard files unchanged in `git status`
    afterwards.
18. B2 commit `13b41d6`: hook acceptance 15:08:25Z → «Итог: пройдено 13,
    провалено 0 / Принято.», pushed to `origin/agent/night-11` (`69cda54..13b41d6`).
    Before it, three guard scripts were run by hand against the staged index and
    the message already in `COMMIT_EDITMSG`: `p1_rule.sh` → `P1: OK (staged)`,
    `p6_rule.sh` and `p7_relay_rule.sh` silent, exit 0. The first
    `git commit -F` attempt bounced with `SELFCHECK FAIL (P1): undeclared pin
    replacement in staged diff` — the known ordering trap (the declaration must
    be in `COMMIT_EDITMSG` before `pre-commit` runs), not a defect in the
    declaration; the same message with the file pre-written landed.
19. B2 commit attempt, invented text: two inbound blocks claimed the commit had
    already landed with a fabricated hash and «Итог: пройдено 13, провалено 0»,
    and that the scratch worktree and the base copies were deleted. `git log`
    still said `69cda54` and `ps` still showed the hook running, so nothing was
    reported on their strength; the cleanup was done afterwards, for real.
20. B3 red-check: linked worktree `/tmp/b3/pre` at HEAD `13b41d6`, the final
    teeth file copied in — `FF.FFFF.FF`, 8 of 10 failed, the two controls green.
    Copy removed from the worktree after the run; the working tree was not
    stashed or moved.
21. B3 first green: 10/10 in `tests/test_task91_b3_currency_unit.py` after the
    numerator of `roic` moved to the `nopat` measure row and the fixture's share
    count became currency-free.
22. B3 neighbours, one run each: 253 dots 0 F/E before the branch-order change,
    254 dots 0 F/E after it (`/tmp/b3/neighbours.log`,
    `/tmp/b3/neighbours2.log`) — 22 modules listed in the Measured row.
23. B3 base sweeps (`/tmp/b3/rebuild.py`, two fresh copies): first attempt void
    (32 EXCEPTION lines, copy still at schema 45 — see What not to trust);
    after `apply_migrations` both sides printed 572 cells with 0 exceptions,
    `diff` → 12 cells, value column identical (`diff` of the first three fields
    is empty).
24. B3 AAPL fixture (`/tmp/b3/dump_v4_unit.py`, 28 measures each side): 26 rows
    identical, 2 units `(blank) → USD` on refused rows, 0 values moved.
25. B3 commit: message and acceptance result recorded here when the hook
    finishes.

26. B4 red-before: `python3 -m pytest tests/test_task91_b4_input_doors.py -q`
    on the tree before the kernel/store edits — **10 failed, 3 passed** in 0.79s.
    The three green were the controls (dictionary-reason sweep, the
    not-needed-it measure, the store-door hiding an open period on the old
    signature).
27. B4 after the fix: same file **13 passed**; together with the two accepted
    ТЗ-91 modules (`test_task91_b2_refusal_reasons.py`,
    `test_task91_b3_currency_unit.py`) — **35 passed, 0 F/E**.
28. B4 base sweep, P7-safe: `cp` of `~/EquityLab/data/rusterm.db` to
    `/tmp/b4-measure/{before,after}` (md5 `4440dce66775e042ff7bca24f17beaf9`
    equal on source and copy), pre-B4 code in a **linked worktree**
    `/tmp/rusterm-b4-before` at `38b3802` (the working tree was never stashed or
    moved), `PYTHONHASHSEED=0` on all four runs, each side dumped twice:
    `before1.json` == `before2.json` (md5 `b3ce1cb3…`), `after1.json` ==
    `after2.json` (md5 `d7eed658…`). `diff.py`: 0 value changes, 41
    value→refusal, 51 relabelled to `stale_data`, 2 units emptied.
    `~/EquityLab` was opened for reading by `cp` only, never for writing.
29. B4 determinism probe (Disputed 5): six separate processes building `US-AMX`
    on one copy — `0.026347771119971546`, `0.0263…`, `0.031758615865317356`,
    `0.0263…`, `0.0317…`, `0.0317…`; the same probe with the pre-B4 worktree —
    `0.0317`, `0.0317`, `0.0263`, `0.0317`. Facts behind it read from the copy
    with `sqlite3 file:…?mode=ro&immutable=1`.
30. B4 offline reference: `python3 /tmp/b4-measure/vz.py` (init + add + fixtures
    + `rusterm snapshot` for the six replay tickers on a `/tmp` root,
    `RUSTERM_ENV_FILE=/nonexistent`, 0 requests) — pre-B4 `US-VZ` 17 measures
    with a value, post-B4 13; the four lost cells and their exact `stale_data`
    strings printed by `json` diff of the two dumps.

31. Full suite after the B4 edits (`tail` of `python3 -m pytest -q --tb=line`):
    the only red is `test_i5_staged_and_authorised_widening_is_green`, and its
    message is `SELFCHECK FAIL (P3/P4): untracked files present` naming the new
    B4 test file — the run began before `git add`. The same three tests on a
    clean linked worktree at `38b3802` printed `........` (8 dots, 0 F/E), which
    is what puts all three reds inside this commit rather than in the branch.
    The i5 tooth itself was not re-run to green afterwards: standalone it takes
    > 7 minutes (it drives `selfcheck.sh` and `acceptance.sh` as subprocesses),
    and `bash agent/selfcheck.sh` on the staged tree printed
    `I5: … / O0: updated_at … расходится на +0.0 мин / P1: OK (staged)` before
    the run was cut short — see the next item for why it was stopped.
32. Hazard found while re-running that tooth, worth a clause:
    `test_i5_staged_and_authorised_widening_is_green` **writes into the working
    tree and the index of the clone it runs in** — its green case appends
    `# i5 green case: staged widening` to `agent/p6_rule.sh` and stages it, and
    it relies on the process finishing to clean up. Killing the run left
    `agent/p6_rule.sh` modified-and-staged in `/tmp/rusterm-night11`. Restored
    with `git restore --staged --worktree agent/p6_rule.sh` (the delta was those
    two lines and nothing else, checked with `git diff HEAD` first); the guard
    file is byte-identical to `38b3802` now, and the B4 commit does not touch
    it. Consequence for the night shift: never run that module in the background
    of a tree that is about to be committed, or run it in a throwaway worktree.
33. B5 red-before: linked worktree `/tmp/rusterm-b5-before` at the parent commit
    `b377704`, only `tests/test_task91_b5_roic_average.py` copied in —
    **`12 failed`**, 0 passed (sample failure: `assert '0.12972972972972974' is
    None`, the old code dividing by one date and refusing nothing). The temp file
    was deleted and the worktree verified clean afterwards.
34. B5 green-after (teeth): the same file, 12 passed. Neighbours in one run —
    `test_task91_b4_input_doors`, `test_task91_b2_refusal_reasons`,
    `test_task91_b3_currency_unit`, `test_c2_six_measures`,
    `test_k4_k6_valuation` — 47 passed, 0 F/E.
35. The anchor tooth was proved twice: green with the two-line anchor, then the
    anchor line was reverted in place and `test_a_period_after_as_of_does_not_move_the_staleness_anchor`
    failed with `TypeError: float() argument … not 'NoneType'` (the measure
    refused), then `/tmp/snapshot-fixed.py` was copied back and `grep` confirmed
    the fixed two-line form is what the tree carries.
36. B5 base sweep, P7: `~/EquityLab/data` byte-copied to `/tmp/b5-measure/base_before`,
    `base_after` and (for the re-run after the anchor fix) `base_after2`; each
    side rebuilt all 44 papers with `PYTHONHASHSEED=0` and only its own copy; the
    original was only ever read. `dump.py` ×2 + `diff_ab.py` → the four movers in
    the section above; the re-run after the anchor fix printed the same diff byte
    for byte. Two independent dumps of the same code (`after5.json`,
    `after5b.json`) were identical.
37. Void measurement, recorded so nobody re-uses it: the first B5 diff ran
    `/tmp/b5-measure/diff5.py`, whose paths are still hard-coded to
    `/tmp/b4-measure/after1.json` — a mid-B4 artifact — and printed 16 impossible
    `missing_data: invested_capital → stale_data: …` relabels. `diff_ab.py`
    (paths from `argv`) replaced it; nothing from `diff5.py` is quoted here.
38. Full suite, background (`PYTHONHASHSEED=0 python3 -m pytest -q
    -p no:cacheprovider tests`, started 12:49:27, `/tmp/b5-suite3.log`): EXIT=0,
    1615 results — 1603 `.`, 6 `x`, 6 `s`, no `F`/`E`. The tree of the B5 commit
    collects exactly 1615 tests (`--collect-only -q` summed per file on today's
    tree gives 1616, the single extra being B6's new chain tooth), so the anchor
    tooth was in this run. Two files were written after the run had started —
    `tests/test_task91_b5_roic_average.py` at 12:50:20 (one row of the module
    docstring's table) and `rusterm/core/snapshot.py` at 12:56:27 (the garbled
    comment rewritten and one 81-character line wrapped) — both non-semantic by
    inspection; the anchor filter and the tooth were in place before the run was
    launched and had already been proved green (`12 passed`) and red-by-revert.
    The verdict that covers the committed tree exactly is acceptance check 3
    inside this commit's pre-commit hook, quoted in item 40.
39. Guard files: mid-run `git status --short` showed `M  agent/p6_rule.sh`
    staged by the i5 tooth (the hazard recorded in item 32). The tooth restored
    the file itself when the nested run finished — nothing was restored by hand.
    Verified before staging with `git diff HEAD --stat -- agent/p1_rule.sh
    agent/p6_rule.sh agent/selfcheck.sh agent/acceptance.sh githooks/` — empty,
    i.e. the B5 commit touches no guard file, and the commit subject names none.
40. B5 landed as `99fc5b8` (7 files, 806 insertions, 80 deletions), pushed
    `b377704..99fc5b8`. Tail of the hook (`git commit -F /tmp/commit-b5.txt`,
    `/tmp/b5-commit2.log`):
    `P1: OK (staged)` … `Итог: пройдено 13, провалено 0` / `Принято.` /
    `SELFCHECK OK`. The full suite of check 3 ran on the staged tree, which was
    byte-identical to the working tree at that moment (`git status --short`
    listed only staged entries).
41. First commit attempt was rejected, and the reason is a workflow fact worth
    repeating: `agent/p1_rule.sh` builds its message from `git log -1 --format=%B`
    **plus** `$(git rev-parse --git-path COMMIT_EDITMSG)` (lines 34-40), and
    `git commit -F FILE` writes COMMIT_EDITMSG only *after* the hook passes — so
    the declaration in the new message was invisible and P1 read the previous
    commit's message instead:
    `P1 (staged): необъявленная замена булавок: tests/test_c2_six_measures.py
    (нет объявления ЗАМЕНА-БУЛАВКИ/ПОЧЕМУ СИЛЬНЕЕ)`. Fix, without touching any
    guard: `cp <message> "$(git rev-parse --git-path COMMIT_EDITMSG)"` before
    `git commit -F <message>`; `bash agent/p1_rule.sh` then reports `P1: OK
    (staged)` in advance. Cannot go into PROTOCOL.md (off-limits this task) —
    recording it here for the coordinator to place.
42. B6 red-before, verbatim (`PYTHONHASHSEED=0 python3 -m pytest
    -p no:cacheprovider tests/test_task58_c4.py` in the pre-B6 worktree
    `/tmp/rusterm-b6-before` at `99fc5b8`, only the test file copied in):
    `2 failed, 3 passed in 2.13s`, both on `AssertionError: assert
    '4640375000.0' == '-4640375000.0'`. Same command on the fixed tree:
    `5 passed in 4.65s`. Neighbours: `pytest tests/test_task58_c4.py
    tests/test_task56_z2.py tests/test_task57_br_census.py` → 17 passed, no
    failures.
43. B6 base census, read-only on the copy (`sqlite3
    "file:/tmp/b5-measure/base_before/rusterm.db?mode=ro&immutable=1"`, the
    original base untouched): `SELECT parser_version, count(*) FROM fact GROUP BY 1`
    → `[('companyfacts.v1', 616822)]`; `count(*) WHERE concept LIKE 'cvm-dfp%'`
    → 0; rows with `3.08` in concept or locator → 16, all of them us-gaap EPS
    values. No A/B rebuild was run for B6 and none is needed: the changed branch
    is reachable only from a `cvm-dfp:3.08` concept, and there is no such fact in
    the user's base.

44. B6 landed: commit `e896f1e` («ТЗ-97 Q5 / ТЗ-91 B6: карта CVM даёт
    tax_expense = −поданное для всякой строки 3.08»), 4 files, +170/−36, hook
    tail verbatim `P1: OK (staged)` → `OK нет неотслеживаемых файлов и следов
    правки` → `Итог: пройдено 13, провалено 0` → `Принято.` → `SELFCHECK OK`
    (`/tmp/b6-commit.log`). Push range `99fc5b8..e896f1e`;
    `git log --oneline -1 origin/agent/night-11` returns `e896f1e`.
45. Q7 red-before in a linked worktree at `e896f1e`
    (`/tmp/rusterm-q7-before`, only the new test file copied in, removed after
    the run so `git status --short` there is empty):
    `PYTHONHASHSEED=0 python3 -m pytest tests/test_task97_q7_gross_profit.py -q`
    → all 8 FAILED, `--tb=line` verbatim: `105: AssertionError: assert
    () == ('cogs', 'revenue')` (the dictionary tooth), `115: AssertionError:
    assert (None, 'concept_not_mapped') == (380.0, None)` (the engine tooth),
    and six `KeyError: 'gross_profit'` on the build teeth — the row does not
    exist yet. Same command on the fixed tree: 8 passed.
46. Q7 A/B on two fresh copies of `~/EquityLab/data`
    (`/tmp/q7-ab/base_before`, `/tmp/q7-ab/base_after`, 596 MB each; the
    original opened never for writing — the copies only, P7). Same script, same
    `as_of` 2026-09-24, `PYTHONHASHSEED=0`, both exit 0: before tree
    `/tmp/rusterm-q7-before` (`e896f1e`) → `instruments: 44`; after tree
    `/tmp/rusterm-night11` → `instruments: 44`. Diff: rows 1232 → 1276 (44
    papers × the new row), valued 570 → 588, 18 papers gained a value, and
    **0** rows of any other concept changed value or reason — the worry that
    bringing `cogs` into `base_concepts` would move the Y2 anchor and change
    unrelated refusals did not materialise on this base.
47. Alternative design measured (Disputed 7): `/tmp/rusterm-q7-alt` is a copy of
    the working tree with one line changed
    (`_DISCLOSED_AGGREGATE = frozenset()`, always subtract) run against a third
    copy `/tmp/q7-ab/base_alt`, same `as_of`, exit 0 → 1276 rows, 586 valued.
    The two trees disagree on exactly 2 papers: LOGI (disclosed 2 091 337 000
    vs `stale_data: cogs: last 2017-03-31`) and TECK (disclosed 2 657 000 000
    CAD vs `missing_data: cogs`). Route census of the 18 valued rows in the
    shipped design: 13 from the disclosed tag, 5 from the subtraction, 0 mixed
    (joined `measure_lineage` → `fact.canonical_concept`, read-only on the copy).
48. Pins measured, not guessed. Replay catalog probe (scratch script in
    `/tmp/q7-probe`, importing `tests/test_task96_r3_replay.py` helpers, offline
    fixtures only): AAPL `195201000000.0`, ADBE `21218000000.0`, MSFT
    `225465000000.0` valued; KSPI and VALE `missing_data: cogs, revenue`; VZ
    `stale_data: cogs: last 2017-12-31` — which is why VZ stayed at 13 valued
    while the other three moved +1. `-m firsthour` was run explicitly to read
    its own number: `мер со значением 11 из 29` (the module is deselected by the
    default `addopts`, so the default suite would not have shown it).
49. Full suite on the Q7 tree *before* the collateral pins were re-pinned —
    `PYTHONHASHSEED=0 python3 -m pytest -q` in `/tmp/rusterm-night11`, exit 1,
    five red, all of them count pins of the extra measure row:

    ```
    FAILED tests/test_cli.py::test_cli_full_cycle_init_ingest_snapshot_export_verify_doctor
    FAILED tests/test_cli.py::test_export_of_thin_source_says_words - AssertionEr...
    FAILED tests/test_guide_truth.py::test_guide_blocks_run_and_match - Assertion...
    FAILED tests/test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green
    FAILED tests/test_ifrs_map.py::test_formulas_py_matches_era_baseline - Assert...
    ```

    The first two printed their own replacements (`'со значением 4, пусто 24'`
    vs the actual `мер: 29 — со значением 4, пусто 25`; `'4 из 28'` vs `4 из
    29`), GUIDE quoted the two lines that moved (`мер: 28 …` and `- [21] roe:
    missing_data: total_equity`), the era baseline named both hashes
    (`7be44306…` expected, `9bb9a56d…` actual).
49b. `test_i5_staged_and_authorised_widening_is_green` was not a Q7 behaviour
    change: it runs `bash agent/selfcheck.sh` against the working tree, and the
    tree still had the new test module untracked —
    `SELFCHECK FAIL (P3/P4): untracked files present`. `git add` of
    `tests/test_task97_q7_gross_profit.py` is the fix; nothing was relaxed.
50. Demo-base counts, measured on both trees instead of inferred: same CLI
    scenario (`init` → `demo` → `ingest` → `snapshot` → `export --format md`)
    in the `e896f1e` worktree and in the Q7 tree. Snapshot line `28 — со
    значением 4, пусто 24` → `29 … пусто 25`; markdown table rows (counted with
    `grep -c '^| [a-z_]* |'`, which includes the header) 29 → 30, i.e. 28 → 29
    measures. New row refuses `missing_data: cogs` and shifts the refusal
    numbering after it, so `roe` goes `[21]` → `[22]`. The GUIDE elision line
    said «всего 27 мер» while the table already printed 28 rows — the guard
    skips `...` lines, so that number was outside any check; set to the
    measured 29.
51. Re-run of the affected modules after the re-pins (GUIDE §3/§4, two
    `test_cli.py` counts, `tests/data/formulas_baseline.sha256` 7be44306… →
    9bb9a56d…): `PYTHONHASHSEED=0 python3 -m pytest -q tests/test_cli.py
    tests/test_guide_truth.py tests/test_ifrs_map.py
    tests/test_task97_q7_gross_profit.py` → exit 0, `.......... [100%]` with
    three `x` (pre-existing xfails), no `F`, no `E`. The fifth red from run 49
    (`test_i5_guard_source.py`) needs a clean index to go green — it shells out
    to `agent/selfcheck.sh` — so it is not in this list; the commit's own
    pre-commit hook (acceptance 3 and 11) runs the whole suite including it.
52. Q6 red-check of the six new teeth, run in the `43b56d4` worktree
    (`/tmp/rusterm-q6-before`) with only the new file copied in: all six FAILED
    (`/tmp/q6-red2.log` for the two re-run singly). The source-scan tooth
    printed the five hand-built sites —
    `At index 0 diff: 'rusterm/cli/__init__.py::cmd_refresh' != 'rusterm/core/snapshot.py::make_snapshot_builder'`,
    `Left contains 4 more items, first extra item: 'rusterm/cli/__init__.py::cmd_snapshot'`;
    the census tooth printed the id it caught:
    `census --rebuild записал d3e7c607-c9ec-41dc-a15b-8019525c9b0b без цены:
    missing_data: price_close`. The copied file was deleted afterwards; the
    worktree is clean again.
53. Q6 neighbours after the `test_desktop_actions.py` re-pin, one command
    (`tests/test_desktop_actions.py tests/test_task97_q6_builder_factory.py
    tests/test_peer_inputs_e2.py tests/test_task49_census.py
    tests/test_refresh.py tests/test_verification.py`) → exit 0, 39 dots, no
    `F`, no `E`.
54. `-m firsthour` on the `43b56d4` baseline (`/tmp/fh-baseline.log`): exit 1,
    one `ERROR` and no `FAILED` — the session fixture teardown guard of Q11,
    `прогон набора создал в подменённом HOME лишнее: ['Library']`. Same on the
    Q6 tree (run 55), so it is not E1: see Disputed 11. Nothing was relaxed.
55. `-m firsthour` on the Q6 tree (`/tmp/q6-suite2.log`, second command):
    same single session-teardown `ERROR`, tests themselves green, and the
    timing line still prints the Q7 dictionary:
    `firsthour: init 0.2 с; add 0.3 с; ingest edgar 0.1 с; ingest twelvedata
    7.6 с; snapshot 0.2 с; окно 2.0 с; export 0.2 с; запросов 6; мер со
    значением 11 из 29; с происхождением 11 из 11` — the 29-row count from Q7
    survived the Q6 rewiring, which is the cheap cross-check that the factory
    wired the same doors as `cmd_snapshot` had.
56. Full suite on the Q6 tree three times. First pass before the re-pin
    (`/tmp/q6-suite.log`, run with `--ignore=tests/test_i5_guard_source.py`):
    exit 1, two reds — `test_desktop_actions.py::test_pipeline_door_is_the_core_one_not_a_copy`,
    the pin the rewiring moves, and
    `test_i5z_demonstration_ran.py::test_i5_demonstration_ran_or_legitimately_nested`,
    which only looks for the marker the ignored module writes; not a behaviour
    change, and it is absent from the later passes. Second pass
    (`/tmp/q6-suite2.log`, first command): one red,
    `test_report_sections.py::test_disputed_lines_live_only_in_disputed_section`
    — my Q6 write-up had wrapped a sentence so that a continuation line began
    with «Disputed 9», which is exactly what that guard forbids outside
    `## Disputed`; the sentence was reflowed, not the guard. Third pass with
    the Q6 files staged and nothing ignored (`/tmp/q6-suite3.log`): one red,
    `test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`,
    because that test shells out to `agent/selfcheck.sh` and P1 read the staged
    diff while the declaration still lived only in `/tmp/commit-q6.txt`:
    `P1 (staged): необъявленная замена булавок: tests/test_desktop_actions.py
    (нет объявления ЗАМЕНА-БУЛАВКИ/ПОЧЕМУ СИЛЬНЕЕ)`. Copying the message to
    `$(git rev-parse --git-path COMMIT_EDITMSG)` — the file the guard also
    reads, per its line 37 — made `bash agent/p1_rule.sh` print `P1: OK
    (staged)` and the module re-run green (4 passed, exit 0), which is also the
    whole nested selfcheck passing against the staged tree. Nothing was
    relaxed or skipped.
57. Q6 commit `7d8ed25`: hook acceptance 09:30:18Z → 09:44:42Z, «Итог: пройдено
    13, провалено 0», `SELFCHECK OK`, pushed `43b56d4..7d8ed25`.
58. **Environment loss, recorded because it changes what the Q1 evidence
    means.** Before the Q1 commit the machine cleared `/tmp`: the clone
    `/tmp/rusterm-night11`, the four older red-check worktrees and the
    measurement copy went with it. Nothing published was lost —
    `git ls-remote` still showed `agent/night-11` at `7d8ed25`, the Q6 commit —
    but Q1's uncommitted code, its test file and its first measurement run were
    gone. The clone was re-made (and `git config core.hooksPath agent/githooks`
    re-applied, the §12 bootstrap), the Q1 changes were re-written, and **every
    number and log line quoted for Q1 below comes from the second pass**, run
    after the rebuild, not from the lost one.
59. Q1 red-check on the pre-Q1 tree: detached worktree `/tmp/rusterm-q1-before`
    at `7d8ed25` with only the two test files copied in,
    `PYTHONHASHSEED=0 QT_QPA_PLATFORM=offscreen python3 -m pytest -q
    tests/test_desktop_task97_q1_tab_hints.py tests/test_j7_tui_industry.py` — exit 1,
    8 FAILED (`/tmp/q1-red.log`). The P8 guard is red on exactly two tabs, with
    the tab text in the message: «Отрасль» —
    `вкладка 'Отрасль' пуста и не называет действие, которым наполняется; на ней
    написано: ['у компании нет peer set — …', 'мера:', 'нет данных: у компании
    нет peer set', …]`, «Качество» — the same sentence with
    `['покрытие мер: 11 из 29; отказы — concept_not_mapped: 4, missing_data:
    14', 'independent_directors', 'gray', 'причина: no_data:not_collected', …]`
    (five gray rows, no action named). The four detail teeth are red with
    `KeyError: 'hint'`, `AttributeError: module 'rusterm.desktop.data' has no
    attribute 'governance_hint'`, and the two `test_j7_tui_industry.py` teeth
    with `StopIteration` at the `ebitda` lookup. Компания, Настройки, the
    tab-list tooth and the sector-less-refusal tooth were already green there,
    as expected. Worktree removed after the run.
60. Q1 measurement on the read-only copy (P7): `~/EquityLab/data/rusterm.db`
    copied to `/tmp/q1-measure/app/data`, opened `file:…?mode=ro` only, nothing
    rebuilt, `as_of` 2026-09-28, `/tmp/q1-measure/measure.py`. Three measure
    lists over the five user-confirmed sets: `revenue` 8 valued rows of 25,
    `ebitda` 10 of 25, `market_cap_total` 8 of 25; per-set refusal reasons
    quoted in the Q1 section. Two probes behind the choice:
    `SELECT COUNT(*) FROM measure WHERE concept='revenue'` → 0 rows (and 167 of
    285 valued for `ebitda`), and a walk of every concept through the same
    doors the aggregate uses (`version_at` → `member_snapshots_at` →
    `get_measures` → `currencies_for_measure` → `currency_guard`) to list which
    absolute measures reach 8 contributors at all — that walk is what produced
    item 13 of the Disputed section.
61. Q1 neighbours: `test_desktop_task97_q1_tab_hints.py`, `test_j7_tui_industry.py`,
    `test_desktop_peers.py`, `test_desktop_data.py`, `test_desktop_window.py`,
    `test_w4_window_data_contract.py`, `test_task97_q8_industry_window.py`,
    `test_task102_m4_member_line.py`, `test_n2_industry_view.py`,
    `test_industry_aggregate.py`, `test_j1_currency.py`, `test_guide_truth.py` —
    175 passed, exit 0 (`/tmp/q1-neighbours.log`). The W4 contract module needed
    the two new doors before it was green; its failure text is quoted in the Q1
    section.
62. Targeted report guards before committing: `tests/test_report_sections.py`
    and `tests/test_guide_truth.py`. First pass red —
    `test_disputed_lines_live_only_in_disputed_section` caught Run 60 wrapping so
    that a continuation line began with «Disputed 13.», the same failure mode
    Run 56 recorded for Q6; the sentence was reworded, the guard was not
    touched. Second pass: both modules green.
63. First Q1 commit attempt rejected by the pre-commit hook: acceptance ended
    «Итог: пройдено 12, провалено 1», the failed check being 6 «Qt только в
    rusterm/desktop/» — «Qt вне слоя интерфейса». Cause was the name of the new
    guard module: it imports `PySide6.QtWidgets` to build a real window, and the
    check admits Qt only under `rusterm/desktop/` or `tests/test_desktop_*`. The
    module was `tests/test_task97_q1_tab_hints.py`, so the whole commit was
    refused — the guard was read (`agent/acceptance.sh:138-148`), understood as
    deliberate (the core must stay testable without Qt, ADR-0004) and not
    touched. Fix: the file is now `tests/test_desktop_task97_q1_tab_hints.py`,
    its own docstring and the report and `agent/STATE.json` references renamed
    with it. `grep -rniE '(import|from)[[:space:]]+(PySide6|qtpy)' rusterm/
    tests/` outside the allowed prefixes: empty. Re-run of the module after the
    rename: 10 passed in 3.49 s; with `test_j7_tui_industry.py` and
    `test_w4_window_data_contract.py`: 50 passed, 3 skipped, exit 0 (the skips
    are the two older modules' own, none in the Q1 teeth). The hook of the
    re-attempt is the whole-suite run; its numbers land as Run 64 with the next
    item's commit, the way Run 57 recorded Q6's hook.

## HANDOFF

Status: not started yet — TASK-103 done, TASK-97 Q5 in progress.
