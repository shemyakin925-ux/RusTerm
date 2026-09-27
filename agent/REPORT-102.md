# REPORT-102 — rulings on REPORT-97 Disputed (round 136); do before resuming TASK-97

## Done

| Item | What shipped | Proof |
|---|---|---|
| M1 | A price is now multiplied only by a fresh share count. `core/snapshot.py`: `_SHARES_FRESH_DAYS = _DPS_ANNUAL_STALE_DAYS` — one constant, the 550 the coordinator named, no second number invented; `_share_count_refusal(period_end, as_of)` counts the age from the **build's `as_of`**, not from the issuer's newest fact, and treats an unparseable date as "do not drop", the same convention `_eligible_input` already uses. The check sits at the single `market_cap` site and **before** the currency comparison, so the whole family grown from `market_cap_total` (`ev`, `pb`, `pe`, `ps`, `fcf_yield`, `ev_ebitda`) inherits the named refusal through the propagation that was already there — no second copy of the rule. Refusal text is exactly `stale_input: shares_outstanding (<period_end>)`. The new token had to be registered in `reasons.py` first: the B15 dictionary guard in `SnapshotRepo.insert_measure_with_lineage` refused the honest refusal (Run 2) — a pure addition to the vocabulary, no existing reason redefined. There is no reason→label map in the package: the one place that buckets reasons for display (`tui_model.measure_reason_counts`, shared by `rusterm coverage --json`, the window and the TUI) tokenises on the first `:` and needs no registration, so `stale_input` appears as its own bucket and the dated concept reaches the user without a code change (Run 7). `div_yield` is not touched: its formula is `dps_ttm / price_close`, it has no share input, and M1's wording lists it among the price×shares measures (Disputed 1). Teeth use dates relative to `date.today()` rather than the literal `2026-06-30` of the Done-when clause, so the suite gives the same verdict in any later round (the ТЗ-80 A1 rule). | `tests/test_task102_m1_shares_freshness.py`: 9 teeth — the VALE shape (shares 2012-12-31, price today) refused with the date named, propagation to `market_cap_total`, fresh shares → `10.0 × 270 927 828`, the window boundary inclusive at 550 days and refused at 551, the anchor case (a whole stale filing where the share tag is the **newest** fact — refused; this is the shape that distinguishes `as_of` from the old `_eligible_input` anchor), absent shares still `missing_data: shares_outstanding`, unparseable date pinned to current behaviour, stale + wrong currency refuses for age not for currency, and `div_yield` unaffected. Mutation (threshold → 10 000 000, i.e. the rule switched off): exactly 4 red, the four that assert refusals; reverted and byte-identical to the pre-mutation copy (Run 4). Measurement on a **copy** of the user's base (P7 — `/tmp/rt-q5/data`, 44 instruments, `as_of` 2026-09-23, same rows under both codes): `market_cap` and `market_cap_total` refused on 4 papers that used to carry a number — US-CHTR (2016-06-30), US-CMCSA (2009-12-31), US-VOD (2021-03-31), US-WDAY (2018-11-30) — and 14 measures grown from them lost their value: the price-shares family went 281 → 259 valued cells; 6 further cells were already refused and only changed which input they name (Run 6). |
| M2 | The mention barrier now matches **guard file names** instead of bare tokens. `agent/check_mention.sh`: the pattern became `grep -qiE "${g}_rule\.sh"` (case-insensitive, per guard, still pairwise — naming `p1_rule.sh` is not satisfied by carrying `agent/p6_rule.sh`). The old pattern was `(^|[^a-zA-Z0-9_])${g}([^a-zA-Z0-9_]|$)`, and the `_` that follows the token is a *word* character, so the rule was doubly wrong in opposite directions: it fired on every prose mention of a protocol rule («(P1: удалённых 0)» colored a commit that owed nothing), and it **silently passed a commit that promised the file by its full path** — `agent/p6_rule.sh` in a message matched nothing, which is precisely the shape the round-48 incident took. Both halves of the header comment now say which of the two the barrier is for. Nothing else in the barrier changed: same arguments, same output line naming the file, same exit codes. `tests/test_l1_mention.py` keeps its red/green intent and only stops using the bare token in its own messages, because that case is no longer the contract; the reverse case (token without a file name, must stay green) moved to the new module. The new module writes its scratch into `tmp_path` rather than into `tests/` — the incumbent module leaves `tests/l1-msg.txt` and `tests/l1-files.txt` in the tree, and a second pair of scratch files there would collide with the «no untracked files» acceptance check. | `tests/test_task102_m2_mention_filename.py`: 5 teeth — bare `P1:`/`P6-` tokens with no guard carried → green (the round-137 false red), `p6_rule.sh` named with the file unchanged → red naming `agent/p6_rule.sh`, named **with** the file → green, pairwise (name `p1_rule.sh`, carry only the other one → red), and `agent/p6_rule.sh` vs bare `p6_rule.sh` behaving alike. Red-check against the old script, same five messages: 4 red, 1 green (Run 14). Verdict table old → new on 4 message shapes × 3 file lists (Run 15): token-only mention without the guard `1 → 0`; full-path mention without the guard `0 → 1`; the exact round-137 message `1 → 0` (and `1 → 0` even when a neighbouring guard was carried); mention with the guard carried `0 → 0`; no mention `0 → 0`. The `Done when` clause is measured on real commits too, not only fixtures: `3334a18` and `b9bd607` — messages that name no guard file, no guard file changed — exit 0 under both scripts (Run 16). Legacy module `tests/test_l1_mention.py`: 3 green. |

M1 made three incumbent expectations false, and all three were cases where the
fixture — not the assertion — had become stale data. No assert was deleted and
no test was weakened:

| Test | Was | Now | Still asserted |
|---|---|---|---|
| `test_k4_k6_valuation.py::test_valuation_measures_compute_from_price_and_facts` | `shares_outstanding` dated `2024-12-31` (default fixture date, written when it was recent) | same fact at `FRESH_SHARES` = `today − 90 days`, a new module constant with its own comment | every formula assert verbatim: `market_cap == 70.0`, `ev`, `pb == 2.0`, `ev_ebitda == 72/7`, `roic == 4.8/40` |
| `test_k4_k6_valuation.py::test_k6_ratio_with_mixed_currencies_is_refused` | same stale share date | `FRESH_SHARES` | `pb[null_reason] == "currency_mismatch: KRW, USD"` — the K6 claim, which M1 had silenced into `missing_data: market_cap_total` |
| `test_k4_k6_valuation.py::test_k6_mixed_currency_aggregate_refused_ratio_computes` | 8 members, shares at `2024-12-31` | `FRESH_SHARES` | `currency_mismatch` naming both currencies and `net_margin.n == 8`. **Found while repairing:** this test was green with M1 in place while *no* member carried a value — `build_sector_aggregates` reads the currency of an absolute measure from lineage (`currencies_for_measure`), not from values, so the guard fires on an empty set. That is the gap M4 is meant to say in words (Disputed 2) |
| `test_task96_r3_replay.py::EXPECTED["US-VALE"]["valued"]` | `2` | `0` | one literal inside an unchanged assert; the replay's other five rows (AAPL 23, ADBE 22, KSPI 2, MSFT 23, VZ 17) came out equal before and after — the whole replay test passing is what proves it |

## Blocked

Nothing blocked. M1 and M2 are complete; M3 and M4 are not started yet (the
round's queue order is M1 → M2 → M3 → M4, one commit each).

## What not to trust

- The four refused papers are correct refusals of a *mapped* input, not proof
  that the user's base has no fresh share count. US-CHTR's only
  `shares_outstanding` value is 270 927 828 (2016-06-30) while its 2026
  diluted count is ~124 M: the mapped `dei` tag is both stale and probably
  wrong for that issuer. M1 stops the number from being published; which tag
  should be `shares_outstanding` for a multi-class issuer is a mapping
  question for another task, and nothing here answers it.
- No clean-HEAD full-suite baseline was run this round (round 136 closed at
  13/0 in a fresh clone per `CONTEXT.md`). Each red in Run 3 is attributed to
  M1 by the failure message that names the new reason string, not by
  diffing two full runs.
- The `stale_input` token is new vocabulary. What I checked: `is_known_reason`
  (prefix-split, Run 2 forced the registration), the shared display counter
  `tui_model.measure_reason_counts` (tokenises generically — Run 7),
  `docs/data-model.md` (states the I4 rule, never enumerates the tokens) and
  GUIDE's sample output (only `missing_data` lines). What I did not do: a
  sweep for any other place that compares a reason string literal outside
  these files — the coverage `--json` branch special-cases the
  `missing_data:` prefix, but on **coverage** rows, which this item writes
  nowhere.

- M2's red-check and the verdict table were run against **one script at a
  time** with synthetic file lists (Run 14, Run 15), not through the hook:
  the only claim that the barrier actually colors a commit red in a real
  commit is the third one — the `49c6320` measurement, which was produced by
  feeding the published message and the published file list to both scripts.
  The full-suite effect of the change is the acceptance verdict of this
  commit, nothing more.

## Runs

1. Round-137 start: read `agent/TASK-102.md` in full, `agent/CONTEXT.md`
   and `agent/LAUNCH.md`. Baton `b9bd607`, report skeleton shipped by the
   hand commit.
2. First red of the M1 teeth (8 tests, production rule already written):
   `ValueError: null_reason 'stale_input: shares_outstanding (2012-12-31)'
   вне словаря (rusterm/reasons.py, B15)` from `rusterm/store/repos.py:841`
   on 5 of them. The dictionary entry was the missing piece, not the rule.
3. Whole suite, working tree with M1 and the new teeth: 4 red —
   `test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`
   (the documented untracked-file artifact: the nested selfcheck exits on
   P3/P4 «untracked files present», REPORT-97 Run 1; gone after `git add`),
   the two `test_k4_k6_valuation.py` cases and the `test_task96_r3_replay.py`
   pin named in the table above.
4. Teeth green: `tests/test_task102_m1_shares_freshness.py` 9 passed.
   Mutation battery: threshold switched off → 4 red (the four that assert
   refusals), rest green; snapshot.py restored and verified with
   `git diff --stat` (only the M1 block, +25 lines).
5. Repaired fixtures + re-pointed pin:
   `test_k4_k6_valuation.py`, `test_task96_r3_replay.py`,
   `test_task102_m1_shares_freshness.py`, `test_b1_reasons.py` →
   21 passed.
6. M1 «было → стало» on the copy of the user base: rebuild 44 instruments
   (v8/v12 versions written into the **copy** only), then the JSON diff of
   the newest snapshot per paper — 28 changed cells across the price-shares
   family, 22 of them a lost value (281 → 259), the direct refusals naming
   CHTR 2016-06-30, CMCSA 2009-12-31, VOD 2021-03-31, WDAY 2018-11-30.
   `~/EquityLab` was never opened for writing (P7).
7. The new reason read back through the real CLI on the same copy
   (read-only): `rusterm coverage --instrument US-CHTR --json` →
   `measure_reason_counts: {"period_mismatch": 3, "missing_data": 12,
   "concept_not_mapped": 4, "stale_data": 1, "stale_input": 2}` — the token
   lands in its own bucket with no code change; `rusterm snapshot
   --instrument US-CHTR` → «мер: 28 — со значением 6, пусто 22».
8. Neighbours after the teeth were `git add`-ed: 19 files (M1 + the valuation,
   reasons, currency, snapshot, Verizon, Q10-TTM, industry and refresh suites,
   plus `test_i5_guard_source.py`) — exit code 0, 128 tests, and the I5 green
   case is among them, which is the proof Run 3's red was the untracked-file
   artifact. The repo's `addopts` already carries `-q`, so my extra `-q`
   reached `-qq` and swallowed the summary line; the counted re-run of the
   same 19 files without I5 gave rc=0 over 122 tests. I5 restores
   `agent/p6_rule.sh` itself (`git status` clean for the guard after the
   run), so nothing of its staged demo can leak into this commit.
9. `bash agent/selfcheck.sh` on the whole working tree of this item, before
   the commit: «Итог: пройдено 13, провалено 0» → «Принято.» → «SELFCHECK
   OK», 45 minutes because check 3's full-suite run nests I5's own selfcheck
   (acceptance → pytest → I5 → acceptance → pytest). The commit's pre-commit
   hook re-runs the same acceptance over the committed set.
10. M1 landed as `49c6320` with that same verdict printed by the hook («Итог:
    пройдено 13, провалено 0»), pushed `b9bd607..49c6320`.
11. M2 written and measured before it lands; its Done row and its own Runs
    come with the next commit, together with the third entry of the disputes
    section below. One obstacle found on
    the way, because it is a consequence of the rule itself: under name
    matching, the *already published* M1 message cites `p1_rule.sh` in
    prose, and the last-commit half of the L1 barrier reads a citation as an
    unfulfilled promise — measured: the new script exits 1 on `49c6320`, the
    old one exits 0. Published history is not rewritten, so M2 cannot be
    M1's direct child: this bookkeeping commit (report + STATE, script still
    the old one) goes between them, and M2 lands on top of it.
12. First attempt at this bookkeeping commit was rejected by its own hook:
    «Итог: пройдено 11, провалено 2», both reds the same test —
    `test_report_sections.py::test_disputed_lines_live_only_in_disputed_section`,
    because a wrapped line of Run 11 began with the word «Disputed» outside
    the disputes section. Reworded and re-run; the tree was left intact by
    the failure (both files stayed staged), which is what ТЗ-100 K2 buys.
13. The bookkeeping commit landed as `3334a18` on the second attempt:
    «Итог: пройдено 13, провалено 0», `SELFCHECK OK`, pushed
    `49c6320..3334a18`. Acceptance again spent most of its time inside
    check 3, which nests selfcheck → acceptance → the full suite through
    the I5 module fixture (round 136 measured 45 minutes for the same path).
14. M2's red-check against the **old** script, before the new one was
    installed: the same 5 messages, run out of /tmp so the repo tree stayed
    clean — `4 failed, 1 passed`. The single green is the case where the
    guard is actually carried, which both scripts must pass. The four reds
    are the false red (token mention, no guard), the escape (path mention,
    no guard — old script exits 0 on a promise it should keep), the pairwise
    case, and the prefix case.
15. Old-vs-new verdict table, 4 message shapes × 3 file lists, run directly
    against both scripts (exit codes only):

    | message | no guard | carries `agent/p6_rule.sh` | carries both |
    |---|---|---|---|
    | `ТЗ-43 K1: p6 — пропуск…` (bare token) | old 1 → new 0 | 0 → 0 | 0 → 0 |
    | `правка agent/p6_rule.sh…` (path) | old 0 → new 1 | 0 → 0 | 0 → 0 |
    | `(P1: удалённых 0), P6-проверка…` | old 1 → new 0 | old 1 → new 0 | 0 → 0 |
    | no mention at all | 0 → 0 | 0 → 0 | 0 → 0 |

    The middle row of the third line is the round-137 incident exactly: a
    commit that mentioned both rules by token and carried only one of the
    two files was red under the old barrier for the wrong reason.
16. `Done when` measured on published history, not only on fixtures: the
    new script on `3334a18` (report + STATE, no guard, message names no
    guard) and on the round-137 hand commit `b9bd607` — both exit 0 under
    the old and the new script. On `49c6320` (M1) the new script exits 1
    while the old exits 0 — that is the obstacle written up as Run 11 and
    as the third entry below, and it is why M2 sits on `3334a18` rather
    than directly on M1.

## Disputed

1. TASK-102 M1 lists «dividend yield» among the measures that multiply a
   price by shares, but `div_yield = dps_ttm / price_close` has no share
   input at all, so no staleness rule about share counts can reach it. I
   implemented the rule at the share input (which covers market_cap,
   market_cap_total and everything grown from them) and pinned `div_yield`
   as unaffected. If the intent was that **dps** freshness should gate the
   yield too, that is a second rule — dps already has `_DPS_ANNUAL_STALE_DAYS
   = 550` on its annual fallback path, so the numbers would coincide but the
   input and the reason text would not. Say the word and it is a small
   follow-up.
2. Measured while repairing the K6 aggregate fixture: a sector aggregate for
   an absolute measure reports `currency_mismatch` even when **zero** members
   carry a value, because the currency is read from lineage rather than from
   values (`core/industry/aggregate.py:173-178`). M4's «участников N,
   значение меры есть у K» is the right cure for the user-visible half of
   this; flagging it now so M4 is written knowing that `n` must count
   members **with a value**, not members of the set.

3. M2 as specified makes a *citation* of a guard file an unfulfilled
   promise, and the barrier then blocks the commit that only quotes it.
   Measured: the new script exits 1 on the published M1 commit `49c6320`
   (its message cites `agent/p1_rule.sh` in prose, line 28, and that commit
   carries no guard), the old script exits 0 on the same pair. Two
   consequences, in order of how much they worry me:
   - while such a commit is HEAD, every selfcheck — mine, the hook's, the
     coordinator's fresh-clone acceptance — goes red on the last-commit half
     of the barrier. History is not rewritten, so the only way out in this
     round was to land a commit that pushes M1 off HEAD (this report's Run
     11); M2 sits on `3334a18`, not on M1.
   - the same trap reopens for any later commit whose message quotes a path:
     "relands the guard fix", "reverts the p6_rule.sh change of 1234abc" and
     a plain `git revert` (whose message repeats the original subject) all
     promise a file they may not carry.
   Candidate cures, none of which I am allowed to pick myself: (a) restrict
   the barrier to the commit *subject* line — promises live there, prose
   citations in the body are references, and `git revert` copies the subject
   so it stays covered; (b) drop the last-commit half and keep only the
   pending check, which is where the round-48 incident actually happened;
   (c) require the mention to be in the imperative form ("правка such-and-such
   file") — undecidable in general; (d) accept it and write into PROTOCOL
   that a commit message must not name a guard file it does not carry, even
   in prose. (a) is what I would choose and it is a two-line change plus one
   tooth, but `check_mention.sh` is only authorized for the M2 edit as
   specified, so I did not do it.

## HANDOFF

Status: PARTIAL — M1 and M2 are finished by their own commits; M3 and M4
still have to be done in this round (one commit per item), then TASK-97
resumes at Q5 (→ Q7 → Q6 → Q1 → Q2 → Q3 → Q4 → Q12 (2, 7)).

Open question for the coordinator, blocking nothing right now: the third
entry above (a citation of a guard path now reads as a promise, and the
barrier can go red on a commit that only quotes it). Cure (a) — subject-line
only — is two lines plus one tooth, and needs its own authorization for
`agent/check_mention.sh`.

M3 is drafted and its teeth are already red-checked out of tree (`/tmp/m3`:
8 teeth, 4 red on HEAD `3334a18`, 4 pins green; implementation sketch, the
ADR-0025 clause-5 replacement text and the measured before-state on the copy
of the user's base are all in that directory). One fact found while drafting
it: the EDGAR accession number is parsed but never persisted
(`FactRepo.insert_fact` drops `accn` and `filed`), so lineage can name the
source object a restated balance was read from, not the filing itself —
naming the filing properly needs a schema change, which M3 does not have.

NOW: M3, step teeth (the four red ones go in `tests/`, then the rule).
