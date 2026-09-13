# REPORT-30 — TASK-30: K2 and K7, quotations stop being fixtures

## Done

### B1 — provider in the registry, with the vendor free ceilings (DONE)

- `rusterm/providers/twelvedata.py` (new): `TwelveDataProvider` with
  `build(gate)` per the seat contract; `from_env` without a key
  returns `ConfigError('twelvedata_key_unset')` — the offline path
  (N2). The module `_LIMIT` and the registry declaration carry the
  SAME vendor numbers: 8/min (`per_second=8/60`) and 800/day; a test
  pins the two against each other so doctor cannot drift from the
  operative limit. `repr` masks the key (TASK-29 A4 rule). The key
  never enters the canonical cache URL.
- `python3 -c "import rusterm.providers as p;
  print(sorted(p.available()))"` now lists `twelvedata` among the nine.
- Past the ceiling: `budget_exceeded` returned BY VALUE; the limiter
  is never reached (`limiter.rate_limited == 0` pinned) — never a wait.
- Verification: `tests/test_market_prices.py` B1 tests green
  (3 passed), `tests/test_free_only.py` 11 passed.

### B2 — a live series, recorded and reproducible (DONE)

- Live run against the real vendor (requests spent: **1** of the 40):
  `rusterm ingest --instrument US-AAPL --source twelvedata`
  -> `US-AAPL: строк получено: 5000; записано новых: 5000; запросов: 1; последняя дата: 2026-09-11`, EXIT=0.
  Second run: `... записано новых: 0; запросов: 0; ...` — zero new
  rows (I7) AND zero requests: the payload is found by the canonical
  key-free URL in `raw_object.url` (ADR-0003 caching; the cache key
  never carries the apikey).
- Date range: 2006-10-25 .. 2026-09-11 daily, 5000 rows, currency USD
  from the payload meta. **Vendor fact, pinned by the golden test:**
  the free tier does NOT return `adjusted_close`; `adjusted` stays
  NULL until K3 computes ours, and the golden test will fail if the
  vendor starts sending it without the report being updated.
- Trimmed recorded payload: `tests/data/twelvedata/
  time_series_AAPL_1day_trimmed.json` (31,195 bytes < 256 KB ceiling;
  meta + 100 oldest + 100 newest values). Golden test replays it
  offline: named prices resolve (newest 2026-09-11 close 332.26999,
  oldest 2006-10-25 close 2.91714), rows sorted, currency USD.
- Machine proof of the repeat property (offline, counting transport):
  first collection — exactly 1 request; second — 0 requests, 0 new
  rows (`test_second_collection_same_day_is_zero_requests_zero_rows`).

### B3 — K7: one vendor is a known hole, proven by test (DONE)

- Three vendor failures driven through a fake transport, all values,
  none an exception: 403 -> `source_unreachable:http_403`;
  429 -> `vendor_rate_limited` (stop, N4 — limits are never raised);
  transport timeout -> `source_unreachable:transport` (the provider
  extinguishes OSError/TimeoutError itself, §7).
- Degradation: with no price rows (vendor failed), the snapshot still
  builds; `net_margin` keeps its value from facts while `market_cap`
  carries `missing_data: price_close` — never a stale number as fresh.

### B4 — cadence on the live rows (DONE)

- `rusterm.core.cadence` (the pass as it is named in the code) driven
  against the real row set from the recorded payload:
  - a hole in history -> plan says `incomplete/backfill`, reason
    `gap:...`; after backfill inserts ONLY the missing days (20 of 22
    re-presented rows were duplicates) -> `complete`, `skip`
    (`polled:2026-09-11`);
  - simulated month inside the closedness window (09-01..09-24):
    exactly ONE poll (`2026-09-21`), i.e. **~1 request per 24 days
    (≈0.04/day)** against the real 5000-row live history; the
    backfill itself cost 1 request total.
- Finding, not a bug: from day 15 past the last real date the
  instrument honestly flips back to `backfill`
  (`stale_history:2026-09-11`) — that is ADR-0014 §2 working; the
  month simulation stops at 09-24 for this reason.
- Note for the coordinator: cadence has no CLI command — `refresh`
  covers disclosures only; the pass is reachable from code. If a
  `rusterm cadence` command (or a prices branch of `refresh`) is
  wanted, that is new scope — not taken without a ruling.

## Blocked

- (nothing)

## What not to trust

- `adjusted` is NULL on all 5000 live rows (the free tier sends no
  `adjusted_close`). K3's vendor cross-check has no vendor input on
  the free plan until that changes; the golden test pins this fact.
- The trimmed payload holds 200 of 5000 real values; the other 4800
  live only in the local raw store (`/tmp/tz30`), not in git.

## Disputed

- TASK-28 R3 carried (open, from yesterday's commit): the replaced
  pins await the coordinator's ruling.
- New pin replacement, same rule (P1): TASK-28's
  `test_twelvedata_seat_is_refused_until_module_lands` asserted
  `provider_not_implemented` — this task's B1 made the module exist,
  so the pin was unholdable. Replaced by
  `test_twelvedata_seat_builds_the_provider` (strictly stronger: the
  seat builds the client and the key door answers
  `twelvedata_key_unset` through the registry). No assertion deleted
  without a stronger successor.

## HANDOFF

Status:          PARTIAL — TASK-30 items B1-B4 done; final HANDOFF at shift end
Arrival state:   selfcheck STATUS=0 (continued on agent/night-10 after TASK-28)
Items done:      B1, B2, B3, B4
Items not done:  none in TASK-30
Acceptance:      last full selfcheck run pending at commit; previous run «Итог: пройдено 13, провалено 0», ACC_EXIT=0
Tests:           test_market_prices 8 passed; test_free_only 11 passed; full default run EXIT=0
Guards:          registry/limit consistency pinned; ceiling refusal by value pinned; seat pin replaced stronger (Disputed)
Schema:          unchanged (41)
Network:         1 real request spent of 40 (Twelve Data), 1 of 60 overall — the live B2 run; everything else offline
Model:           0 calls of 0; GLM-5.3-Flash
Secrets:         cache URL and trimmed payload carry no key; repr masked; artefacts grepped — 0 hits
Pushed:          per-commit
Questions for the coordinator:
1. Cadence has no CLI surface (see B4 note) — command wanted, or keep
   it code-only until a night owns it?
2. K3's vendor cross-check cannot see vendor adjusted values on the
   free plan — keep the NULL-adjusted state and pin it (current), or
   name a follow-up item?

### Repair — the B2 cache lookup broke I9, caught by acceptance (DONE)

- The first B2 commit put the cache lookup SQL into
  `rusterm/cli/__init__.py` (`repos.conn.execute(...)` over
  raw_object) — invariant I9 violated, acceptance check 7 went red
  (три прогона 12 из 1 подряд; один ранний прогон был 11 из 2 —
  второй провал, m4_scale, тайминг-флак, зелёный в изоляции).
- Fix: lookup moved into the store layer as
  `RawRepo.find_by_provider_url(provider, url)`; the CLI calls the
  repo method, no SQL outside `rusterm/store/`. Acceptance back to
  «Итог: пройдено 13, провалено 0», SELFCHECK OK.

## HANDOFF (final)

Status:          DONE
Arrival state:   selfcheck STATUS=0 (continued on agent/night-10 after TASK-28)
Items done:      B1, B2, B3, B4 + one repair (I9, see above)
Items not done:  none in TASK-30
Acceptance:      «Итог: пройдено 13, провалено 0 — Принято», selfcheck EXIT=0 (real key file in place)
Tests:           test_market_prices 8 passed; test_free_only 11 passed; full default run EXIT=0; 5 live-marked deselected by default
Guards:          registry/limit consistency and ceiling refusal pinned; seat pin replaced stronger (Disputed); SQL-only-in-store restored by repair
Schema:          unchanged (41)
Network:         1 real request spent of 40 (Twelve Data), 1 of 60 overall
Model:           0 calls of 0; GLM-5.3-Flash
Secrets:         cache URL and trimmed payload carry no key; repr masked; artefact grep — 0 hits
Pushed:          yes
Questions for the coordinator:
1. Cadence has no CLI surface (B4 note): command wanted, or code-only
   until a night owns it?
2. K3's vendor cross-check sees no vendor adjusted values on the free
   plan — keep NULL-adjusted pinned as is (current), or name a
   follow-up item?
3. m4_scale tripped once in acceptance today (timing mean-budget,
   green in isolation every time). Watch, or move it to a load-tolerant
   form (ratio-only)?
