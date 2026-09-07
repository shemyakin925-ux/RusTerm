# BACKLOG — pre-approved small tasks for idle executor time

Maintained by the coordinator (Claude). The executor pulls items
top-down **only** when the main `agent/TASK-*.md` queue is empty, and
reports each pulled item in its report file. The executor never edits
this file.

## Item format

```
- [ ] <ID> — <one-line objective> — accept: <command or check> — size: <S/M/L>
```

## Queue

- [ ] B1 — Guard the invariant-numbering gap that hid I16: add a test
  asserting the `test_iNN_` functions in `tests/test_invariants.py` run
  contiguously from 01 with no missing number — accept:
  `python3 -m pytest tests/test_invariants.py -q -k numbering` green, and
  it fails if any `test_iNN_` is deleted — size: S
- [ ] B2 — Fixture discipline as a test, not only a convention: assert
  every file under `fixtures/` has `synthetic` in its name and in its
  body — accept: `python3 -m pytest -q -k fixtures_are_synthetic` green;
  add a temp non-synthetic file and see it go red — size: S
- [ ] B3 — Pipeline idempotency is proven for the raw store and for
  facts, but not for the job queue: assert a second `ingest` run creates
  no new `job` rows — accept: new test in `tests/test_pipeline.py`,
  `python3 -m pytest tests/test_pipeline.py -q` green — size: S
- [ ] B4 — Second golden-file issuer: a multi-class synthetic emitter
  exercising `market_cap_total` and the preferred-stock rule in `ev`,
  with a hand-computed reference — accept:
  `python3 -m pytest tests/test_golden_formulas.py -q` green with two
  issuers — size: M
- [ ] B5 — `price_adj` order-independence: applying a split and a
  dividend on disjoint dates in either order yields the same adjusted
  series — accept: new test in `tests/test_formulas.py` green — size: S
- [ ] B6 — `doctor` should report schema drift: if
  `current_schema_version(conn) != _SCHEMA_VERSION`, say so with both
  numbers. Check first whether it already does; if it does, add the
  missing test instead — accept: `rusterm doctor` on a schema-32
  database prints the drift, covered by a test — size: S
- [ ] B7 — Docs/code drift guard for coverage blocks: assert every block
  name in the `docs/watchlist-and-llm.md` §1.3 table exists in the code's
  block list, and vice versa — accept: new test green; renaming a block
  in code turns it red — size: M

- [ ] B8 — The zstd branch has never actually run: `zstandard` is not
  installed in this environment, so only the gzip fallback is exercised.
  Add a test that fakes a minimal `zstandard` module (compress/decompress
  round-trip) so the zstd path, the `compression='zstd'` label and
  reading a zstd object back are covered without the package — accept:
  `python3 -m pytest -q -k zstd` green with the fake, and acceptance
  check 11 still green — size: M
- [ ] B9 — Request budget and provider rate limiter are specified in
  `docs/processes.md` §6a and do not exist. They only bind once a real
  provider exists, so build the deterministic core now: a budget counter
  per (provider, window) and a limiter that refuses over quota, wired
  into the provider registry, with the synthetic providers reporting
  zero cost — accept: new test asserting the (N+1)-th call in a window
  is refused rather than delayed — size: M

## Done

(empty)
