# TASK-82 — property-based tests for the formula engine (Hypothesis)

- **Status: READY**
- **Report:** `agent/REPORT-82.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-82.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600` — do not end the session.
- **Stop:** day round — by the list; night round — PROTOCOL §10.
- **Budgets:** network — `pip install hypothesis` only. LLM 0.
- **How to work:** no questions; forks are closed by the rules below;
  doubtful → Disputed, move on; one item = one commit, item id in the
  subject.
- **Taken after:** TASK-81 and the queue it names. Numeric order.

РАЗРЕШЕНО ПРАВИТЬ: pyproject.toml

## Where we are

- ~915 test functions, 8 `parametrize`, **zero** generated inputs.
- `clip()` in `effective_tax` invented 0.0 from AMBEV's ≈23.8% and
  lived three rounds (TASK-58 C4). That class of bug — a measure that
  fits instead of refusing — is exactly what a property catches.
- Coordinator's probe, **measured** on `dd11fbd`:
  `gross_margin(nan, 100.0)` → `(nan, None)`;
  `gross_margin(1e308, 1e-308)` → `(inf, None)`;
  `effective_tax_rate(nan, 1.0)` → `(nan, None)`. `_divide_checked`
  (`rusterm/formulas.py:250`) checks `== 0` and `< 0` — NaN passes both.

## Fixed decisions (no forks)

| Question | Rule |
|---|---|
| Library | Hypothesis, added to `[project.optional-dependencies] test`. Free (MPL-2.0), ADR-0018 holds. |
| Missing Hypothesis | plain `import hypothesis` — **no `importorskip`**. A property test that skips is a vacuous test. |
| Determinism | profile `default`: `derandomize=True`, `database=None`, `deadline=None`, `max_examples=200`. Profile `deep`: `max_examples=5000`, not derandomized. Chosen by env `HYPOTHESIS_PROFILE`. Registered in `tests/conftest.py`. |
| Non-finite input or result | refusal with a **new** reason `non_finite` in `rusterm/reasons.py` (comment: TASK-82). Never a NaN/inf value, never `missing_data` (that would hide corrupt input). |
| Doc vs code disagree on a bound | Disputed with numbers. Do not edit `docs/` (acceptance 10), do not bend code to the doc. |
| Red before fix | the pre-commit hook blocks red commits, so test+fix go in one commit; show the red by running the new test file against the parent commit in a temp worktree under `$TMPDIR`; command + last 5 lines in the report. |

## E1. Profiles and dependency

**Done when:**
- `pip install -e ".[test]"` installs Hypothesis;
- `HYPOTHESIS_PROFILE=deep python3 -m pytest tests/test_prop_formulas.py -q`
  runs the deep profile (report shows the example count from
  `--hypothesis-show-statistics`);
- new ADR `docs/adr/0024-*.md` (new ADR files are allowed): why a
  generator in tests, licence, free, runtime never imports it;
  `grep -rn hypothesis rusterm/` → empty.

## E2. Closure property — every formula, automatically

File `tests/test_prop_formulas.py`.

For every public function in `rusterm/formulas.py` whose return
annotation is `Tuple[Optional[float], Optional[NullReason]]`, with each
argument drawn from `floats(allow_nan=True, allow_infinity=True) | none()`
(lists for list args):
- no exception;
- exactly one of `value`, `reason` is `None`;
- `value`, when present, satisfies `math.isfinite`;
- `reason` satisfies `reasons.is_known_reason`.

Census guard in the same file: the set of such functions is found by
introspection and must equal the set covered — a new formula without a
property is red.

**Done when:** `python3 -m pytest tests/test_prop_formulas.py -q` green;
every defect found is fixed with `non_finite`; report lists each
function that was fixed, with the shrunk counterexample Hypothesis gave.

## E3. Metamorphic properties

Same file. Inputs here: finite floats with 1e-6 ≤ |x| ≤ 1e12 (closure
is E2's job, not this one). Money-in, ratio-out measures are unit-free:
- `gross_margin`, `operating_margin`, `net_margin`, `roe`, `roic`,
  `asset_turnover`, `effective_tax_rate`, `price_to_earnings`,
  `price_to_book`, `price_to_sales`, `ev_to_ebitda`, `dividend_yield`:
  all money inputs × k,
  k ∈ {1e-3, 1e3, 1e6} → same value (rel 1e-9) or same reason;
- `ttm`: permuting the last four quarters changes nothing; fewer than
  four or any `None` in the window → `missing_data`;
- `market_cap_total`: any `None` class → refusal, **never** a partial sum;
- `cagr(v, v*(1+g)**n, n)` ≈ `g` for g ∈ (-0.99, 10), n ∈ 1..30;
  `v_start <= 0` → refusal;
- `hhi`: permutation-invariant, within the bounds the code documents;
- `total_return` of a constant series = 0; `drawdown` ∈ [-1, 0].

**Done when:** all green; every property that fails is either fixed
(code) or Disputed (bound unclear) — not weakened.

## E4. Zero is not missing

For every two-arg ratio: numerator `None` → `missing_data`, never `0.0`;
numerator `0` with a valid denominator → value `0.0`, reason `None`.

**Done when:** green; `git diff <base>..HEAD -- tests/ | grep -c '^-.*assert'` → 0.

## E5. Time budget

**Done when:** default profile, `tests/test_prop_*.py` total < 20 s
(`--durations=5` output in the report); `bash agent/acceptance.sh` green.
