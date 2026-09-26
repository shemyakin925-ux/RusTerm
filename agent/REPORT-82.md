# REPORT-82 — ТЗ-82, круг 115

Branch `agent/night-11`, head on arrival `1d50c89`, baton `agent/TASK-82.md`.
English per AGENTS.md; command output quoted as it came out. Budgets: network —
`pip install hypothesis` only (PyPI, Runs 3); LLM calls 0.
Every probe in this round carries an explicit `--root` under `/tmp` or a sandbox
`HOME` (PROTOCOL §2 P7); the formula engine is pure arithmetic and never opens a
base, so no probe reaches `~/.rusterm` or `~/equitylab`.

## Arrival state (measured before the first source edit)

`I5_NESTED=1 bash agent/selfcheck.sh` on `1d50c89`, full log
`/tmp/rt82-arrival-selfcheck.log`:

```
P1: OK (пустой дифф, HEAD~1..HEAD)
P6: HEAD~1..HEAD (last commit) — коммит эстафеты, пропущен
  OK    нет неотслеживаемых файлов и следов правки
Итог: пройдено 11, провалено 2
Не принято. Разбирать по проваленным пунктам сверху вниз.
16:          FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
17:  ПРОВАЛ pytest, код возврата 1
43:          FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
44:  ПРОВАЛ без zstandard код возврата 1 — фолбэк не реализован
SELFCHECK FAIL (acceptance): exit status 2
```

Checks 3 and 11 are the same single test — reproduced on its own, and this is
the only red in the file:

```
$ python3 -m pytest tests/test_report_sections.py -q -o addopts=""
.......F....................                                     [100%]
E       AssertionError: пункты ['F1', 'F2', 'F3'] объявлены сделанными, но коммита круга с
E         реализацией (не только tests/) не найдено
1 failed, 27 passed in 3.11s
```

Why it is red on arrival, and why no source is wrong:
`tests/test_report_sections.py:42 _report_text()` reads the report named in
`agent/STATE.json`, which the previous round left at `agent/REPORT-95.md` (its
final HANDOFF declares `Items done: … F1, F2, F3`), while
`_round_under_review()` takes the round from `agent/BATON.json` — already 115,
already TASK-82. So between the coordinator's `hand` and the next executor's
STATE commit the guard looks for round-115 commits carrying round-114 item ids.
Repair is the first commit of this round, per PROTOCOL §9: `agent/STATE.json`
re-pointed at TASK-82 and this file created. The mechanism itself is an ask for
the coordinator — see Disputed 1.

## Done

### приём круга — STATE + отчёт

`agent/STATE.json` → `task: agent/TASK-82.md`, `report: agent/REPORT-82.md`; this
file created with the five required sections. No source file touched in this
commit: the round's first item is E1 and it starts after this record.

### E1 — профили и зависимость

* `pyproject.toml`: `test = ["pytest>=8", "zstandard>=0.22",
  "hypothesis>=6.100"]`. `dependencies = []` untouched, and the file now pins
  that both facts stay true (`test_hypothesis_is_declared_in_the_test_extra_only`).
* `tests/conftest.py`: registers `default` (`derandomize=True`, `database=None`,
  `deadline=None`, `max_examples=200`) and `deep` (`max_examples=5000`,
  `derandomize=False`), loads the one `HYPOTHESIS_PROFILE` names. The fixed
  decision named only `max_examples`/`derandomize` for `deep`; `database=None`
  was added there too, because Hypothesis's example database is a directory in
  the working tree (`.hypothesis/`) — that is an untracked file during every
  acceptance run (P3, acceptance 13) and a write into whoever's home the suite
  happens to run from (P7). Measured: `settings.get_profile("deep").database`
  is `None`, and the deep run leaves `git status --porcelain` empty.
* `tests/test_prop_formulas.py` (new, E1 part): five machine-checked facts about
  the wiring plus one generated property, so the deep-profile command has a real
  counter to report. `import hypothesis` without `importorskip`, per the task.
* `docs/adr/0024-generatory-vkhodov-v-testakh.md` (new; check 10 allows added
  files under `docs/adr/`), and one sentence in README §15 naming `(0024)` —
  `tests/test_docs_truth.py::test_readme_lists_every_adr` derives the ADR list
  from `docs/adr/`, so an ADR the README does not name is a red suite. README is
  not on P6's blocked list and no count in it was touched (the guard bans
  hand-typed numbers there).

Measured (Runs 5–8): default profile — `200 passing … Stopped because
settings.max_examples=200`, `9 passed in 1.96s`; `HYPOTHESIS_PROFILE=deep` —
`5000 passing … Stopped because settings.max_examples=5000`,
`6 passed in 1.82s`; `grep -rn hypothesis rusterm/` → exit 1 (no output);
collection with the new conftest import → `1146/1161 tests collected (15
deselected) in 1.07s`, no errors. `git status --porcelain` after the deep run
lists only the five files of this item — no `.hypothesis/` directory.

The generator earned its place before E2 started: the first version of E1's
smoke property asserted `gross_margin(x, x) == 1.0` for every finite `x`, and
Hypothesis shrank the counterexample to `x < 0` — which refuses with
`negative_denominator` (Run 9; the rule lives at formulas.py:222, not a defect).
The property now states all three branches.

### E2 — закрытость: `non_finite` и честный `missing_data`

Red first (Run 10): a temp worktree of `ca7d9c2` (E1, before this fix) with
only the new test file copied in — `18 failed, 11 passed in 9.73s`. Each
counterexample below is what Hypothesis shrank to on that tree; the third
column is the same call after the fix (Runs 11–13).

| formula | shrunk counterexample on `ca7d9c2` | after |
|---|---|---|
| asset_turnover | `TypeError: unsupported operand(s) for /: 'NoneType' and 'float'` at (None, 0.0, 1.0) | `missing_data` |
| roe | same TypeError (net_income None, equity pair finite) | `missing_data` |
| roe_incl_nci | same TypeError | `missing_data` |
| roic | same TypeError (nopat None, 0.0, 1.0) | `missing_data` |
| cagr | `OverflowError: (34, 'Result too large')` — `**` on a huge ratio | `non_finite` |
| drawdown | `TypeError: '<=' not supported between 'NoneType' and 'int'` — None price in the series | `missing_data: null_price` |
| effective_tax_rate | `([inf, inf])` gave `nan` | `non_finite` |
| ev_to_ebitda | `([222867937.0, 1.2397440473680309e-300])` gave `inf` | `non_finite` |
| gross_margin | `([3.0361003942458523e+215, 1.6888869047599635e-93])` gave `inf` | `non_finite` |
| market_cap_per_class | `([3.4915624281554496e+137, 5.14867819737657e+170])` gave `inf` | `non_finite` |
| net_margin | `([inf, 1.0])` gave `inf` | `non_finite` |
| operating_margin | `([1.2883469708212328e+16, 7.166667913653163e-293])` gave `inf` | `non_finite` |
| price_to_book | `([inf, 1.0])` gave `inf` | `non_finite` |
| price_to_earnings | `([inf, 1.0])` gave `inf` | `non_finite` |
| price_to_sales | `([0.0, nan])` gave `nan` | `non_finite` |
| total_return | `([[('2022-12-31', nan), ('2022-12-31', 0.0)]])` gave `nan` | `non_finite` |
| ttm | `([[0.0, 0.0, 0.0, inf]])` gave `inf` | `non_finite` |
| calculate_measure | `ebitda(operating_income=0.0, d_and_a=inf)` gave `inf` | `non_finite` |

Mechanism — one decorator, `refuses_non_finite` in `rusterm/formulas.py`, put
above all 21 paired formulas (the census test pins the number): a non-finite
float anywhere in the inputs, an arithmetic result that is not finite, and
`OverflowError`/`ZeroDivisionError` from the arithmetic all become
`non_finite`. `TypeError` becomes `missing_data` **only** when one of the
inputs is `None` — otherwise it re-raises, so a real coding error in a formula
stays loud instead of hiding behind a refusal. That last rule is the second
family in the table: formulas annotated `float` are called from
`calculate_measure` with facts that may be absent, and only the denominator was
checked for `None` in roic/roe/roe_incl_nci/asset_turnover.

Beyond the decorator:
* `rusterm/reasons.py`: `non_finite` added to `NULL_REASONS` (documented as
  "the fact is present and spoiled", which is a different conversation from
  "the fact is absent") and to the `NullReason` literal.
* `effective_tax_rate` keeps an explicit `math.isfinite(rate)` *inside* the
  function, because the next line formats the rate into the reason string
  (`jurisdiction_rate: rate=…`) — without it the refusal would have carried
  `rate=inf` as its explanation.
* `drawdown` names its own reason `missing_data: null_price` for a gap in the
  middle of the series, next to the existing `nonpositive_price` rule.
* `calculate_measure` screens the value it computed inline (ebitda, fcf,
  interest_coverage, invested_capital, nopat go around the wrapper functions),
  so no non-finite number reaches the `measure` table from that door either.
* `tests/data/formulas_baseline.sha256` re-pinned
  `015bab5d… → 72035135…` — that is the procedure its own docstring names
  ("обновляется ТОЛЬКО коммитом своей задачи с учётом в отчёте"); this line is
  that account. `tests/test_ifrs_map.py` is unchanged, the assertion is intact.
* ADR-0024 §4 corrected in this commit: it told the reader to run
  `pip install -e ".[test]"`, which is the command Disputed 2 shows to be unsafe
  on a shared machine. Statement about the requirement stays, the recipe does
  not.

`hhi` keeps its documented rule and it is not a hole: `[0.5, None, 0.5]` → 0.5
because the surviving shares do sum to 1.0, and `[0.5, None]` →
`missing_data: shares_sum:0.5` — the sum rule is what makes a dropped
participant visible (measured, Run 13).

### E3 — метаморфные свойства

Nine properties in `tests/test_prop_formulas.py`, inputs finite and inside
1e-6 ≤ |x| ≤ 1e12 (E3's own domain; the NaN/±inf corner belongs to E2):

* `test_the_ratio_list_matches_the_signatures` — the arity table below is
  checked against `inspect.signature`, so a formula that grows an argument
  cannot quietly narrow the property.
* `test_money_scale_does_not_move_a_ratio` — the twelve money-in/ratio-out
  measures named by the task: every argument × k, k ∈ {1e-3, 1e3, 1e6}, drawn
  together with the arguments so the counterexample names the real parameters
  (`gross_profit`, `revenue`, …). Same value within rel 1e-9, or the same
  refusal.
* `test_ttm_does_not_care_about_the_order_of_its_window` (reverse, rotation,
  sort of the last four) and `test_ttm_refuses_a_short_or_gapped_window`
  (fewer than four, or any `None` in the window → `missing_data`).
* `test_market_cap_total_is_never_a_partial_sum`.
* `test_cagr_reads_back_the_growth_it_was_hand` — `cagr(v, v·(1+g)^n, n) ≈ g`
  for g ∈ (-0.99, 10), n ∈ 1..30, within rel 1e-6; and
  `test_cagr_refuses_a_nonpositive_start` — `v_start ≤ 0` → `negative_
  denominator` (the reason the code actually gives, not the one the task
  paraphrases as "refusal").
* `test_hhi_ignores_order_and_stays_in_its_documented_bounds` (0..1, the
  fraction convention `hhi` documents).
* `test_a_flat_series_has_no_return_and_no_drawdown` (constant series → 0.0)
  and `test_drawdown_lives_between_minus_one_and_zero`.

Teeth, measured rather than assumed (Run 15): a scratch copy of the tree with
three deliberate defects — `gross_margin` dividing by `revenue + 1.0` (a
constant in the wrong unit), `net_margin` turning an absent numerator into
`0.0`, and `ttm` weighting the last quarter of its window. The scale property
named the first, the order/refusal pair named the third, and each was red with
a shrunk example. (The same run also reddens
`test_hypothesis_is_declared_in_the_test_extra_only`, which reads
`pyproject.toml` — that file was not part of the scratch copy; artifact of the
demonstration, not a finding.)

One deliberate deviation from the wording of E3, recorded as Disputed 3 (see below):
"same reason" is compared by the first token of the reason, because
`jurisdiction_rate: rate=…` carries a number in its continuation, and
`(a·k)/(b·k)` reproduces that number only to ~1e-16 — measured:
`effective_tax_rate(28143926709.0, 1e-06)` → `rate=28143926709000000.0000`
against `×1e-3` → `rate=28143926708999996.0000`. Comparing whole strings would
make the property red on a correct engine; the value comparison stays strict.

### E4 — ноль не равен пропуску

Two properties added to `tests/test_prop_formulas.py`; no source changed (the
parent tree is already green for them — Run 17, the same demonstration as E3's
Run 14, is the honest form of "this item fixes nothing"):

* `test_arity_two_pairs_are_not_an_empty_list` — the set below is built by
  introspection (functions returning the pair with exactly two parameters), and
  the guard says so out loud when introspection stops seeing formulas instead of
  quietly checking nothing. Measured count: 10.
* `test_absent_numerator_is_refused_zero_numerator_is_a_number` — for every
  two-parameter measure: `f(None, d)` is exactly `(None, "missing_data")` and
  `f(0.0, d)` is exactly `(0.0, None)`, with `d` drawn finite and positive so
  the denominator rules stay out of the way. The ten are the nine ratios of
  E3's list plus `market_cap_per_class` — introspection picks it by arity, and
  it answers the same way, which is the behaviour worth pinning there too.

Why a fence rather than a fix: a missing fact becoming `0.0` is invisible in the
base (it looks like a measured zero), and E2's closure property does not see it
— measured in the mutation run of E3 (Run 15), where `net_margin` taught to
answer an absent numerator with `0.0` reddened exactly this property and left
the closure property green. The two checks catch different defects; that is why
both are in the file.

`git diff 1d50c89..HEAD -- tests/ | grep -c '^-.*assert'` → 0 (Run 19): E1–E4
added to `tests/` without removing or rewriting a single assert line, which is
the "Done when" this item names.

### E5 — бюджет времени, и два дефекта, которые нашёл deep-профиль

Budget (the item's own letter): `tests/test_prop_*.py` is one file, 75 tests at
the default profile, `10.04 s` and `11.87 s` on two quiet runs — under the 20 s
ceiling; the five slowest calls are all parametrizations of the E2 closure
property, 0.22–0.32 s each (Runs 20, 25). The `deep` profile is not part of the
ceiling and is not what acceptance runs (`grep -rn HYPOTHESIS_PROFILE
agent/acceptance.sh agent/selfcheck.sh` — no match); it costs 237–240 s for the
same file and is recorded separately so nobody reads "< 20 s" as a statement
about it (Run 24). `bash agent/acceptance.sh` first went **red** on this tree —
11/2 — for a reason outside both code and tests: a wrapped report line began
with the word "Disputed" outside `## Disputed`, which
`test_disputed_lines_live_only_in_disputed_section` forbids and which the I5
chain then repeats (Run 26). Rewrapped, the two reddened guards pass
(`32 passed` twice); the verdict of the whole script is Run 27 — the same
acceptance chain the E5 commit's hook performs:
`Итог: пройдено 13, провалено 0`, `Принято.`

The budget measurement is what surfaced two properties that were green only at
the default profile — 200 examples, derandomized, `database=None`. Both were
reported rather than worked around, and neither was fixed by deleting a check:

* **`hhi` contradicts its own docstring.** `formulas.hhi` documents
  "диапазон 0..1" and, in the same paragraph, "доли обязаны суммироваться в 1.0
  с допуском 1e-6". The second rule lets `hhi([1.0, 1.192092896e-07])` answer
  `1.0000000000000142` (Run 21) — and the reachable maximum is not a float
  artifact: a single participant with a 1.0000009 share answers `1.0000018`,
  i.e. 1.8e-6 above the documented ceiling, which is what `(1 + 1e-6)²`
  predicts (Run 22). The property now bounds each branch by the rule the code
  itself declares — `≤ 1.0` when the drawn shares sum to exactly `1.0`
  (measured: no counterexample among 400 000 normalized draws), and
  `≤ (1 + 1e-6)²` inside the declared tolerance. Which of the two sentences
  wins is Disputed 4: clamp the value, tighten the tolerance to an exact sum,
  or widen the documented range — all three change a measure that already lives
  in the user's base, so none is the executor's call.
  `test_hhi_still_outruns_its_own_documented_range` pins the contradiction: it
  goes red the day the code stops outrunning 1.0, so a ruling cannot leave the
  two sentences disagreeing quietly.
* **A fixed relative tolerance is the wrong claim for a cancelling
  denominator.** `test_money_scale_does_not_move_a_ratio[roic-3]` went red at
  deep: `roic(1e12, 999999999215.0, -999999962869.0)` = `55026687.943652675`,
  with every input ×1e-3 → `55026688.01006897` — relative 1.2e-9, just past the
  1e-9 that E3 pinned (Run 21). Cause is conditioning, not the measure: the
  denominator is the mean of two ~1e12 numbers cancelling to 3.6e4, so rounding
  one input by 1 ulp moves the answer by 0.185 absolute (3.4e-9 relative), and
  the observed 0.066 sits inside that. Two changes, both strengthening:
  (a) `test_a_binary_scale_of_two_leaves_the_same_bits` — ×2**k is exact in
  binary floats, so the same twelve ratios are compared with `==`, no tolerance
  at all; 30 000 random tuples × 12 formulas × 3 scales produced no mismatch
  (Run 22). (b) the decimal property keeps `_same_number` (rel 1e-9) as its
  normal path and only when that fails measures the granularity double
  precision actually offers (`_ulp_noise`: one ulp per argument, both
  directions, summed) and demands the difference exceed it — so a loose bound
  is never a number someone typed. Teeth re-measured on the mutated engine
  (`gross_margin` dividing by `revenue + 1.0`): both properties red, the binary
  one at `gross_margin[1.0, 1.0] = 0.5` against `9.31e-10` for ×9.31323e-10
  (Run 23). Entry 3's "value comparison is strict at rel 1e-9" is amended to
  point here.

Both deep findings are re-told without a generator, which is what ADR-0024's
consequences section demands before a deep failure is fixed (`derandomize=False`
plus `database=None` makes a deep seed unreproducible):
`test_hhi_still_outruns_its_own_documented_range` and
`test_the_deep_scale_failure_is_retold_without_a_generator` name the two
examples literally, run in every profile including acceptance's, and each goes
red in the direction that closes its Disputed entry rather than in the
direction that hides it.

Source of `rusterm/` is untouched by E5: the two findings are recorded as
entries 4 and 5 of the `## Disputed` section, which is what E3's own "Done
when" prescribes for a bound that is unclear rather than wrong.

## Blocked

- none.

## What not to trust

- The metamorphic properties of E3 sample a wide domain, so "green" is a
  statement about 200 drawn cases per property at the default profile. The
  mutation run above (Run 15) is the evidence they can fail at all; it is not a
  proof that every unit-scale defect is found at this seed.
- The closure property is a search, not an enumeration: on the pre-fix tree 17
  of 21 formulas went red, and the four that stayed green were open too —
  `dividend_yield(inf, 1.0)` gave `(inf, None)`, `market_cap_total([1e308,
  1e308])` gave `(inf, None)`, `enterprise_value(inf, …)` gave `(inf, None)`,
  and `hhi([inf])` refused with `missing_data: shares_sum:inf` where the honest
  reason is `non_finite` (Run 13, hand probes). Those four are fixed by the same
  decorator, but the green column of the E2 table is evidence about this seed,
  not a proof of coverage — `HYPOTHESIS_PROFILE=deep` is the way to raise the
  odds, and it is not part of acceptance. E5 did run it (three times, Runs
  21, 24), and it found two things the default profile had missed; read that as
  "the default column of this report is thin", not as "deep is now enough".
- Deep is not a proof either. It is 5000 random examples with `database=None`,
  so a green deep run says nothing about the next seed — and the two defects E5
  found arrived at different depths: the `hhi` one on the first deep run, the
  `roic` one on the second pass over the same file. Neither is registered
  anywhere as a reproducible case beyond the numbers quoted in Disputed 4 and 5.
- `_ulp_noise` is a measured estimate of first-order sensitivity, not a bound in
  the proof sense: it perturbs one argument at a time, so interaction between
  simultaneous perturbations is outside it (the factor is generous for the
  measured case — 0.185 against a 0.066 difference, ~3×). What closes that gap
  is the binary-scale property, which admits no tolerance at all; if a future
  scale bug has a magnitude inside one ulp, it will be caught there or not at
  all, and the escape hatch in the decimal branch will stay silent.
- The permutation asserts in E3 (`hhi`, `ttm`) still compare exactly. Probed:
  400 000 random normalized draws of `hhi` reordered three ways gave no
  mismatch (Run 22), and no deep run has flagged them — but that is the same
  class of claim as the one Disputed 5 just corrected, on a domain the deep
  profile reaches only by luck. If a seed ever reddens them, the fix is the
  tolerance Disputed 5 names, not a deleted check.
- The three probes the coordinator measured on `dd11fbd` are refused now
  (`gross_margin(nan, 100.0)`, `gross_margin(1e308, 1e-308)`,
  `effective_tax_rate(inf, inf)` → `non_finite`, Run 12) — but that is three
  numbers out of a 21-function domain. What the whole domain gets is the
  property, and its strength is the search described above, not an enumeration.
- E1 shipped wiring only (profiles, the dependency, one smoke property); the
  arithmetic claims start with E2.
- The suite now hard-requires `hypothesis`: per the fixed decision there is no
  `importorskip`, so collecting the whole suite fails on a machine without the
  package. That is the consequence the task chose, not an accident of this
  commit — but it is a new hole in the "run the suite anywhere" story. The way
  to close it is to install the `.[test]` group, and Disputed 2 records why the
  usual `pip install -e` recipe is not one this round can run on this machine.
  Acceptance is unaffected here, where 6.168.1 is installed.
- The arrival numbers come from a tree where `pip install hypothesis` had
  already been issued (it ran while the arrival selfcheck was in progress).
  Nothing imported the package then — no test file used it yet — so it could not
  have changed the result, but the pairing is stated rather than assumed.

## Disputed

- Entry 2 (budget vs. this machine, not code): the natural way to satisfy E1 —
  `pip install -e ".[test]"` — is unsafe here, and the task does not name the
  command. Measured: `python3 -m pip show rusterm` →
  `Editable project location: /Users/anton/AI agents/RusTerm`, i.e. the user's
  real working copy is what `import rusterm` resolves to system-wide; and
  `python3 -m pip install --dry-run --force-reinstall -e ".[test]"` from
  `/tmp/rt-night11-exec` →
  `Would install Pygments-2.21.0 hypothesis-6.168.1 iniconfig-2.3.0 packaging-26.3
  pluggy-1.6.0 pytest-9.1.1 rusterm-0.1.0 sortedcontainers-2.4.0 zstandard-0.25.0`
  — it would repoint that editable install at a `/tmp` clone and drag pytest,
  zstandard and the rest along with it (round 114 measured the same class of
  collision on PyInstaller bundles). So the budgeted action was narrowed to
  `python3 -m pip install hypothesis` (Run 3), which adds exactly
  `hypothesis-6.168.1 sortedcontainers-2.4.0` and leaves the editable install
  and the other test packages as they were. Consequence to rule on: whether the
  executor should get a per-clone venv instruction in `§9`, so
  `.[test]` becomes safe to install verbatim.
- Entry 1 (guard mechanism, not code): `relay.py hand` flips `agent/BATON.json`
  (task/report/round) but leaves `agent/STATE.json` pointing at the closed
  round's report, and `test_done_items_have_code_commits_in_round` reads the
  round from one file and the report from the other. Measured above: the branch
  head `1d50c89` is red for the next executor until their first commit, and a
  red acceptance blocks that very commit (the pre-commit hook runs acceptance),
  so the repair has to be the first commit of the round. Fix belongs on the
  transport side: `hand` could stamp STATE's `task`/`report` fields with the
  baton's, or the guard could read the report named in BATON.json. Not touched
  here — `agent/STATE.json` is mine to write, `relay.py` and the guard are not
  named by this task.

- Entry 3 (wording of E3, mine to raise): "all money inputs × k → same value
  (rel 1e-9) **or same reason**" is read as the same *reason token*, not the
  same string. Reason continuations carry numbers
  (`jurisdiction_rate: rate=%.4f`, `missing_data: shares_sum:<x>`), and
  `(a·k)/(b·k)` reproduces `a/b` only to ~1e-16, so a literal string
  comparison reddens a correct engine — measured counterexample in the docstring
  of `_reason_token` (28143926709000000.0000 against 28143926708999996.0000).
  The value comparison was strict at rel 1e-9 as written — amended by E5, see
  Entry 5: at the deep profile even that could not hold on a cancelling
  denominator. Ruling needed: accept the token, or take the continuation out of
  reason strings (a source change in `formulas.py`, outside E3's letter).
- Entry 4 (wording of `formulas.hhi`, found by E5's deep run): the docstring
  states "диапазон 0..1" and "доли обязаны суммироваться в 1.0 с допуском 1e-6"
  in one breath, and the second sentence breaks the first — measured
  `hhi([1.0, 1.192092896e-07])` = `1.0000000000000142` (Run 21) and reachable up
  to `1.0000018` on a single 1.0000009 participant (Run 22), so the excess is
  1.8e-6, not a last-bit artifact. Three ways out and all three change what is
  already stored in the user's base, so the executor picks none: clamp the
  result to 1.0, refuse sums that are not exactly 1.0, or document the range as
  `0..(1+1e-6)²`. Until then the property bounds each branch by the rule the
  code declares (`≤ 1.0` at an exact sum, `(1+1e-6)²` inside the tolerance) and
  `test_hhi_still_outruns_its_own_documented_range` keeps the contradiction
  loud — it goes red the moment the code stops outrunning 1.0, which is the
  signal to close this entry.
- Entry 5 (wording of E3, found by E5's deep run): "all money inputs × k → same
  value" cannot carry a fixed relative tolerance, because the tolerance measures
  the conditioning of the drawn inputs rather than the measure. Measured:
  `roic(1e12, 999999999215.0, -999999962869.0)` = `55026687.943652675`, ×1e-3 on
  every input = `55026688.01006897` — 1.2e-9 relative, past the 1e-9 E3 asked
  for, with the denominator a mean of two ~1e12 numbers cancelling to 3.6e4
  (Run 21). Adopted reading, in the stronger of the two available forms: for
  scales that are exact in binary (×2**k) the answers must be bit-identical, and
  for decimal scales the 1e-9 comparison stays the normal path, loosening only
  past a measured bound (one ulp per argument, both directions, summed).
  Ruling needed: keep this reading, or restrict E3's generator to inputs whose
  denominator does not cancel (a narrower domain, and the roic case would leave
  the property's coverage altogether).

## Runs

| # | command | output |
|---|---|---|
| 1 | `I5_NESTED=1 bash agent/selfcheck.sh` (arrival, `1d50c89`) | `Итог: пройдено 11, провалено 2`, `EXIT=1` |
| 2 | `python3 -m pytest tests/test_report_sections.py -q -o addopts=""` | `1 failed, 27 passed in 3.11s` |
| 3 | `python3 -m pip install hypothesis` | `Successfully installed hypothesis-6.168.1 sortedcontainers-2.4.0` |
| 4 | `python3 -m pytest tests/test_report_sections.py -q -o addopts=""` (после перевода STATE) | `27 passed, 1 skipped in 2.93s` |
| 5 | `python3 -m pytest tests/test_prop_formulas.py tests/test_docs_truth.py tests/test_adr_numbers.py -q -o addopts="" --hypothesis-show-statistics` ; `HYPOTHESIS_PROFILE=deep python3 -m pytest tests/test_prop_formulas.py -q -o addopts="" --hypothesis-show-statistics` | `200 passing, 0 failing` + `Stopped because settings.max_examples=200`, `9 passed in 1.96s` ; `5000 passing, 0 failing` + `Stopped because settings.max_examples=5000`, `6 passed in 1.82s` |
| 6 | `grep -rn hypothesis rusterm/` | (нет вывода), `grep exit=1` |
| 7 | `python3 -m pytest --collect-only` | `1146/1161 tests collected (15 deselected) in 1.07s` |
| 8 | `git status --porcelain` (после deep-прогона) | только пять файлов E1 + отчёт; каталога `.hypothesis/` нет |
| 9 | `python3 -c "from rusterm import formulas as f; print(f.gross_margin(-5.0,-5.0), f.gross_margin(0.0,0.0), f.gross_margin(7.0,7.0))"` | `(None, 'negative_denominator') (None, 'denominator_zero') (1.0, None)` |
| 10 | `git worktree add --detach "$TMPDIR/rt82-e2-prefix-ca7d9c2" ca7d9c2` → `cp tests/test_prop_formulas.py` (версия E2) → `python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""` в том дереве | `FAILED …[roe_incl_nci]`, `FAILED …[roic]`, `FAILED …[total_return]`, `FAILED …[ttm]`, `FAILED tests/test_prop_formulas.py::test_the_calculate_measure_door_is_closed_too`, `18 failed, 11 passed in 9.73s` |
| 11 | `python3 -m pytest tests/test_prop_formulas.py tests/test_ifrs_map.py -q -o addopts=""` (клон, после правки, baseline перепинен) | `33 passed, 3 xfailed in 4.44s` |
| 12 | `python3 -c "…gross_margin(nan,100.0); gross_margin(1e308,1e-308); effective_tax_rate(inf,inf); cagr(1.0,inf,2.0); calculate_measure('ebitda', operating_income=0.0, d_and_a=inf)…"` (после правки) | все пять → `non_finite` |
| 13 | те же пробы на `ca7d9c2` (до правки) + пробы `hhi` | `div_yield(inf,1.0) = (inf, None)`, `mct([1e308,1e308]) = (inf, None)`, `ev(inf,…) = (inf, None)`, `hhi([inf]) = (None, 'missing_data: shares_sum:inf')`, `hhi([0.5,None,0.5]) = (0.5, None)`, `hhi([0.5,None]) = (None, 'missing_data: shares_sum:0.5')` |
| 14 | worktree на 88e880f (родитель E3) + `cp tests/test_prop_formulas.py` (версия E3) + `python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""` | `50 passed in 7.40s` — E3 не меняет исходников, зелёный на родителе и есть смысл пункта |
| 15 | scratch-копия `rusterm/`+`tests/` с тремя намеренными поломками (`gross_margin` → `revenue + 1.0`; `net_margin` → `0.0` при отсутствующем числителе; `ttm` → вес последнего квартала), `python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""` | `FAILED …test_money_scale_does_not_move_a_ratio[gross_margin-2]`, `FAILED …test_ttm_does_not_care_about_the_order_of_its_window`, `FAILED …test_ttm_refuses_a_short_or_gapped_window`, `FAILED …test_absent_numerator_is_refused_zero_numerator_is_a_number[net_margin]`, `6 failed, 54 passed in 13.02s` (двое из шести — артефакт scratch: нет pyproject.toml, и E1-свойство дыма) |
| 16 | `python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""` (клон, E3) | `50 passed in 7.40s` |
| 17 | worktree на d2af2ff (родитель E4) + `cp tests/test_prop_formulas.py` (версия E4) + `python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""`, затем `git worktree remove --force` | `61 passed in 9.91s` — E4 не меняет исходников, зелёный на родителе и есть смысл пункта |
| 18 | `python3 -m pytest tests/test_prop_formulas.py -q -o addopts="" --durations=5` (клон, E4) | slowest: `enterprise_value 0.31s`, `market_cap_total 0.23s`, `drawdown 0.23s`, `roe_incl_nci 0.22s`, `test_ttm_refuses_a_short_or_gapped_window 0.22s` ; `61 passed in 8.13s` |
| 19 | `git diff 1d50c89..HEAD -- tests/ \| grep -c '^-.*assert'` ; то же против рабочего дерева с неоткоммиченным файлом E4 (`git diff 1d50c89 -- tests/`) | `0` и `0`; `grep '^-.*assert'` — пустой вывод (нечего показывать) |
| 20 | `python3 -m pytest tests/test_prop_*.py -q -o addopts="" --durations=5` (default, до правок E5; `HYPOTHESIS_PROFILE` не задан) | slowest: `enterprise_value 0.31s`, `drawdown 0.23s`, `market_cap_total 0.23s`, `roe_incl_nci 0.22s`, `test_ttm_refuses_a_short_or_gapped_window 0.22s` ; `61 passed in 8.05s`, повтор — `61 passed in 10.00s` |
| 21 | `HYPOTHESIS_PROFILE=deep python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""` (до правок E5), затем то же после правки `hhi` | `FAILED …test_hhi_ignores_order_and_stays_in_its_documented_bounds` → `AssertionError: hhi([1.0, 1.192092896e-07]) = 1.0000000000000142`, `1 failed, 60 passed in 189.71s` ; затем `FAILED …test_money_scale_does_not_move_a_ratio[roic-3]` → `55026687.943652675` против `55026688.01006897` (`shares`-пример: `nopat=1e12, invested_capital_begin=999999999215.0, invested_capital_end=-999999962869.0`), `1 failed, 61 passed in 196.47s` |
| 22 | пробы `python3 -c` на движке: `hhi` на 400 000 случайных нормированных наборов с тремя перестановками; максимум `hhi` при сумме на краю допуска; то же при `sum == 1.0` ровно; двоичный масштаб на двенадцати отношениях (30 000 наборов × 3 масштаба) | `reordering counterexample: None` ; `max hhi с суммой ≈ 1+9e-7: 1.0000018` (один участник с долей `1.0000009`) ; `total==1.0 exactly but hhi>1: None` ; `binary-scale mismatches: 0` |
| 23 | scratch-копия `rusterm/`+`tests/`+`pyproject.toml` с одной поломкой (`gross_margin` делит на `revenue + 1.0`), `python3 -m pytest tests/test_prop_formulas.py -q -o addopts="" -k "scale or ratio"` | `FAILED …test_a_binary_scale_of_two_leaves_the_same_bits[gross_margin-2]` (`gross_margin[1.0, 1.0] = 0.5, ×9.31323e-10 → 9.313225737481168e-10`) и `FAILED …test_money_scale_does_not_move_a_ratio[gross_margin-2]`, `2 failed, 23 passed, 49 deselected in 5.43s` |
| 24 | `HYPOTHESIS_PROFILE=deep python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""` трижды, свежие сиды (после правок E5) | `74 passed in 237.23s`, `74 passed in 239.58s`, `74 passed in 237.26s` — вне бюджета пункта (он про default) и вне приёмки: `grep -rn HYPOTHESIS_PROFILE agent/acceptance.sh agent/selfcheck.sh` → пусто |
| 25 | `python3 -m pytest tests/test_prop_*.py -q -o addopts="" --durations=5` (default, финальное состояние E5), затем без `--durations` | slowest: `enterprise_value 0.32s`, `market_cap_total 0.24s`, `drawdown 0.23s`, `roe_incl_nci 0.22s`, `total_return 0.22s` ; `75 passed in 10.04s` ; повтор на тихой машине — `75 passed in 11.87s` |
| 26 | `bash agent/acceptance.sh` (клон, рабочее дерево E5) | `Итог: пройдено 11, провалено 2`, `Не принято`, `EXIT=2`: `FAILED tests/test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green` и `FAILED tests/test_report_sections.py::test_disputed_lines_live_only_in_disputed_section` — перенос строки в отчёте начался со слова «Disputed» вне секции `## Disputed` (секция про это и предупреждает); исходники и тесты не при чём. После перебивки — `python3 -m pytest tests/test_report_sections.py tests/test_i5_guard_source.py -q -o addopts=""` → `32 passed in 558.82s`, повтор `32 passed in 565.24s`. Итог приёмки после правки — строка 27 (её даёт только следующий прогон: этот коммит держит её в своём хуке) |
| 27 | `bash agent/acceptance.sh` внутри хука коммита `22afb31` (`I5_NESTED=1 bash agent/selfcheck.sh` → `agent/acceptance.sh`) | `Итог: пройдено 13, провалено 0`, `Принято.` |
| 28 | `HYPOTHESIS_PROFILE=deep python3 -m pytest tests/test_prop_formulas.py -q -o addopts=""` (после финальных правок файла, свежие сиды) | `75 passed in 238.06s (0:03:58)` |

## HANDOFF

Статус ниже — финальный, он заменяет промежуточный блок, который был
написан по итогам E4.

Status: DONE — все пять пунктов ТЗ-82 приняты очередью, эстафета
координатору.

Items done: приём круга (STATE + отчёт, `bad057a`), E1 (hypothesis в
зависимости, профили default/deep, ADR-0024 — `ca7d9c2`), E2 (closure-свойство
по 21 формуле и по двери `calculate_measure`, причина `non_finite`, честный
`missing_data` — `88e880f`), E3 (метаморфные свойства: масштаб денег, порядок
кварталов, кэр-бэк cagr, границы drawdown/hhi — `d2af2ff`), E4 (ноль не равен
пропуску: десять двухместных мер по интроспекции — `7987b3e`), E5 (бюджет
времени плюс два расхождения, найденных deep-профилем: `hhi` против собственного
docstring и недопустимость фиксированного относительного допуска для
вычитающего знаменателя).

Items not done: none.

Verification, in the words of the item that owns it: default-профиль —
`75 passed in 10.04 s` и `75 passed in 11.87 s` под потолком в 20 s (Runs 25);
deep — три зелёных прогона по 237–240 s (Run 24) и ещё один после финальной
правки файла (Run 28); `bash agent/acceptance.sh` — первый прогон круга дал
11 из 2 и «Не принято» из-за переноса строки в этом отчёте (слово «Disputed»
вне секции), а не из-за кода; после перебивки два покрасневших стража зелёные
(32 passed дважды, Run 26), а полный прогон даёт `Итог: пройдено 13, провалено
0` и `Принято.` — это хук коммита `22afb31` (Run 27). Рука-коммит держит ту же
цепь, и её собственный итог изнутри себя не цитируется. Ни одна проверка не исчезла молча: две булавки сняты, для
каждой в сообщении коммита названа преемница и сказано, чем она сильнее
(снято 2 assert-строки, добавлено 10).

Open for the coordinator (ничего из этого исполнитель решить не может):
- Entry 4 — какая из двух фраз docstring `hhi` побеждает (зажимать
  значение, требовать точной суммы долей или расширить диапазон до
  (1+1e-6)²); капкан в тестах покраснеет на любом из трёх решений.
- Entry 5 — прочтение «same value» в E3: принятое (двоичный масштаб до
  бита + измеренный шум ulp для десятичного) или сужение области генератора.
- Entry 3 — сравнение причин по первому токену против чисел в continuation.
- Entry 2 — рецепт установки `.[test]`: `pip install -e` перенацеливает
  глобальную editable-установку `rusterm` на `/tmp`-клон; нужен пункт §9 про
  отдельный venv на клон.
- Entry 1 — `relay.py hand` не переносит `task`/`report` в `STATE.json`,
  из-за чего голова ветки красная для следующего исполнителя.

Network: pip only — `pip install hypothesis` и один `pip install --dry-run`
(Runs 3 и Disputed 2); ни одного запроса к провайдерам данных, LLM 0.

NOW: hand to coordinator.
