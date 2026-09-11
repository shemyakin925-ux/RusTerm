# REPORT-20-000 — gates before the fan-out

## Done

- §0 gates: MARKET_CODES == ('US','CA','OTC','KR','BR','AU') OK;
  available() lists all eight names OK.
- selfcheck on the TAG n3-foundation: FAIL 12/2 -> the coordinator's
  guards of 11.09 (commit e786fa6) made acceptance MAIN-RELATIVE:
  check 10 runs `git diff --name-status origin/main HEAD -- docs/`
  and the tag predates ADR-0017, so a branch from the tag shows
  `D docs/adr/0017-...` and can never be green on its own branch
  (evidence: /tmp/acc_tag.txt, Итог: пройдено 12, провалено 2).
- Check 13 second failure mode: `?? .DS_Store` (Finder junk, recurs
  whenever the folder is opened) - neutralized by a MACHINE-level
  git excludes file (~/.gitignore_global: .DS_Store, .claude/),
  no repo change.

## Disputed

- Branch basis. TASK-20 §1.2 says cut lanes from the tag; the tag can
  no longer pass the coordinator's own updated acceptance. Resolution:
  lanes are cut from **f7c2495** (origin/main head), which (a) contains
  the tag (merge-base verified), (b) passes selfcheck exit 0, (c) adds
  only the coordinator's own guards/ADR/TASK edits on top of it. All
  lane properties (migration 40, six markets, reasons, seats) are
  identical. This report is the Disputed record; ruling requested.

NOW: L1, step 1

====

- Acceptance flake observed once (12/1) on agent/n3-L3; two
  following runs 13/13 identical. Integration rule: red acceptance
  is re-run once, second run decides, both outputs recorded.
