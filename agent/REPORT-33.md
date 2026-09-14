# REPORT-33 — TASK-33: insider_net lights up; the proxy channel is probed

Arrival state: selfcheck OK at 34d6f68 (13/13); full suite 661 passed,
1 skipped, 4 xfailed, 0 failed.

## Done

### E5 — the executor charter is back in place (DONE)

- `agent/TASK.md` restored from `origin/main` with
  `git checkout origin/main -- agent/TASK.md`;
  `git diff origin/main -- agent/TASK.md` prints nothing
  (byte-identical, verified at this commit).
- Regression commit: `e68c1b5` ("ТЗ-32 D6: period_basis ...") — my
  `git add -A` swept a stale working-tree copy of `agent/TASK.md`
  (its pre-10.09.2026 text) into an otherwise legitimate commit. That
  commit legitimately carried: migration 43 (period_basis in both
  lineage tables), the snapshot writer/`div_yield`/`ev_ebitda`/`roic`
  basis stamps, the ADR-0021 file, README §15 ADR line, the D6
  assertions in tests/test_c2_six_measures.py, and the 42 -> 43
  version-literal replacements declared under the D5 rule. Nothing
  else in the branch touched the charter.
- Guard so it cannot recur: E6 (next commit).
