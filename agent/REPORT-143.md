# REPORT-143 — TASK-143 (operating income without the line, PFE/XOM; F0a/F0b)

## Done
- F0a — `refresh_one`: ProviderError от submissions теперь отказ
  одной бумаги, а не падение прохода (rusterm/core/refresh.py:
  `isinstance(latest, (ConfigError, ProviderError))`; REPORT-142 Q1).
  Раньше у бумаги с отражённой датой падал TypeError на сравнении
  `latest <= last_filing_date`, у первой сборки ProviderError уезжал в
  issuer_state.put → ProgrammingError — обе ветки одной причины.
  Тест `tests/test_task143_f0a_submissions_refusal.py`: три бумаги,
  у средней submissions отдаёт ProviderError (значением, как живой
  403) → проход завершается (rc 1), AAA и CCC обновлены (факты в
  базе), BBB без фактов, итоговая строка «…новые отчёты: 2 …
  отказов: 1». Красно-зелёное: без фикса тест падает
  ProgrammingError («type 'ProviderError' is not supported»).

## Blocked
- (empty)

## What not to trust
- The copy `/tmp/rusterm-e-base` (49 instruments) was rebuilt fresh
  this round and still carries prices through 2026-10-20; F1's copy
  measurements happen after a reparse + history rebuild on it.

## Disputed
- F3 of the task text («relay.py verify → 13/0 on the final head»)
  contradicts the same file's «How to finish (new rule, 22.10)» and
  the coordinator's baton note («New rule: no separate verify before
  hand»). Implementing per the new rule: the hand's own acceptance
  (two full rolls) is the final-head gate; no standalone verify.

## HANDOFF
(interim — F0a done; F0b, F1, F2 ahead)
Status:          PARTIAL
Arrival state:   baton round 162 (c0d32f8), TASK-142 accepted
Items done:      F0a
Items not done:  F0b, F1, F2 (in progress), F3 per the new rule = the
                 hand's own acceptance; the contradiction is in
                 its section (dispute)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes it
Tests:           F0a test quoted above (green with fix, red without)
Guards:          none touched
Schema:          unchanged (48)
Network:         0 of 100 so far
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator: (none yet)

NOW: F0a, step 6

## HANDOFF
(interim — supersedes the block above; the previous one tripped the
guard with a continuation line starting with the section's name)
Status:          PARTIAL
Arrival state:   baton round 162 (c0d32f8), TASK-142 accepted
Items done:      F0a
Items not done:  F0b, F1, F2 (in progress); F3 goes per the new rule
                 in «How to finish» — the hand's own acceptance is the
                 final-head gate, no standalone run (recorded as a
                 dispute in its section)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes it
Tests:           F0a test quoted above (green with fix, red without)
Guards:          none touched
Schema:          unchanged (48)
Network:         0 of 100 so far
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator: (none yet)

NOW: F0b, step 3

## What not to trust (addendum)
- One continuation line inside this report's FIRST interim HANDOFF
  block was reworded in place («Disputed» → «its section (dispute)»)
  to satisfy the report guard, which reds on any line starting with
  that word outside its section — and the guard scans the whole file,
  so an append-only workaround does not exist. The line carried no
  record content (it pointed to the dispute section).
