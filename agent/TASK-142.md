# TASK-142 — «Обновить» end to end (С5) and peers for newly added companies (С4)

- **Status: READY** (take after TASK-141)
- **Report:** `agent/REPORT-142.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С5 (one button, progress, one line
  «what changed»), С4 (a new company lands in a peer group).
- **Budgets:** network ≤ 400 (one full refresh pass over the copy +
  the five TASK-139 tickers), LLM 0. Copy of the user's base (P7).
- **Relay:** as in `agent/TASK-139.md`, with REPORT-142.

## Where we are (coordinator, 09.10)
TASK-140 ACCEPTED: 11 814 / 11 814 cells name a source, 49/49 open a
file. «Обновить» (TASK-133 R1) runs the same pass as the background one;
never measured end to end on a real-size base.

## E1. One refresh pass on the copy
Press the button's door (`desktop_actions.refresh_pass`, the same as
the window) on the copy, prices stale by ≥ 1 day. Time it; count
requests; record the final one-line summary the window shows.
**Done when:** REPORT: seconds, requests, the summary line verbatim;
after the pass every instrument's latest price date = last trading day
(or a named refusal per instrument); `card_fill.py` on the control ten
still ≥ 90 %.

## E2. The summary says what changed
The final line names counts in words: new prices, new reports, measures
changed, refusals (e.g. «цены: 49, новые отчёты: 2 (KO 10-Q, …), мер
изменилось: 37, отказов: 1»). If today's line does not, make it so in the
data layer (one function, tested), the window only prints it.
**Done when:** fixture test (one new filing, one refusal) → the line
names both; the line from E1 pasted in REPORT.

## E3. New company → peer group
For each of NVDA, KO, XOM, PFE, WMT on the copy: does «Аналоги» show a
group with ≥ 3 companies? If a new company gets no group, assign it by
the same rule as existing members (SIC → group), never by hand.
**Done when:** REPORT table ticker · group · members; every one has a
group of ≥ 3 or a named reason (e.g. no other company with that SIC).

## E4. Verify
**Done when:** `python3 agent/relay.py verify` → 13/0 on the final head.

## Do not
Same list as `agent/TASK-131.md` «Do not».
