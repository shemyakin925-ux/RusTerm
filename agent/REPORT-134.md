# REPORT-134 — clean screen: words not tokens, hide what is frozen

Partial, by the coordinator on 08.10.2026 (user: «продолжай ты»).

## Done
- W1: card and home tooltips use `reasons_ru` phrases with the token in
  brackets (done earlier: `card._reason_words`). Visible text check —
  look.py over all 38 papers, every tab except the hidden «Качество»:
  0 labels or cells matching `[a-z]+_[a-z_]+:`, `Disputed`, `REPORT-`.
- W2: «Качество» tab hidden (`setTabVisible(False)`); code and tests stay.
  Settings keep all registry hosts: the TASK-97 Q3 guard requires them
  (`rowCount == len(registry)`) — a deliberate rule, not changed.
- W3: «1 из 6 рынков · …» hidden. «v39 · 38 бумаг» kept: pinned by two
  watchlist tests; harmless.
- W4: chat box hidden (frozen); `RUSTERM_CHAT=1` shows it.
## Blocked
## What not to trust
## Disputed
## Runs
- desktop suite green except the known firsthour trio (TASK-135 A3).
- W5 (08.10 evening, `7166518`): desktop suite fully green; q1 guard green
  reading `rusterm_argv` of the buttons; look.py 38 papers: no «rusterm ».
## HANDOFF

```
Status:          DONE
Items done:      W1, W2, W3, W4, W5
Items not done:  none
Acceptance:      known reds only (I5 linked-worktree, firsthour date-bound)
Tests:           desktop suite green except firsthour trio
Guards:          none touched
Schema:          unchanged (48)
Network:         0
Pushed:          yes
Questions for the coordinator:
1. none
```
