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
  odds, and it is not part of acceptance.
- The three probes the coordinator measured on `dd11fbd` are refused now
  (`gross_margin(nan, 100.0)`, `gross_margin(1e308, 1e-308)`,
  `effective_tax_rate(inf, inf)` → `non_finite`, Run 12) — but that is three
  numbers out of a 21-function domain. What the whole domain gets is the
  property, and its strength is the search described above, not an enumeration.
- E1 shipped wiring only (profiles, the dependency, one smoke property); the
  arithmetic claims start with E2.
- The suite now hard-requires `hypothesis`: per the fixed decision there is no
  `importorskip`, so collecting the whole suite fails on a machine without the
  package. That is the documented consequence of the task's own choice, not an
  accident of this commit — but it is a new hole in the "run the suite anywhere"
  story, and Disputed 2 records why the install command that closes it is not
  one this round can run here. Acceptance is unaffected in this environment,
  where 6.168.1 is installed.
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
  The value comparison is strict at rel 1e-9 as written. Ruling needed: accept
  the token, or take the continuation out of reason strings (a source change in
  `formulas.py`, outside E3's letter).

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

## HANDOFF

Status: PARTIAL — E1, E2, E3 приняты, очередь продолжается.
Items done: приём круга, E1 (профили и зависимость, ADR-0024), E2
(closure-свойство по 21 формуле и calculate_measure, non_finite), E3
(метаморфные свойства: масштаб, порядок, кэр-бэк cagr, границы drawdown/hhi).
Items not done: E4 (ноль не пропуск), E5 (бюджет времени).
Arrival state: `Итог: пройдено 11, провалено 2`, repaired by `bad057a`.
Network: pip only — `pip install hypothesis` and one `pip install --dry-run`
(Runs 3 and Disputed 2); no data-provider request, LLM 0.
NOW: E4, step 1
