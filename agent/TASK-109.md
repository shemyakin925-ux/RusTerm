# TASK-109 — collection never dies on one stage; retries; offline shows what is there

- **Status: ACCEPTED (round 145, coordinator verify — see LAUNCH.md 03.10)**
- **Report:** `agent/REPORT-109.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 30 requests (live check), LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

03.10, empty base: `rusterm follow MSFT` — stages 1–3 in 232 s, stage 4
(ownership) `source_unreachable:transport:URLError` → whole path stopped:
no prices, no snapshot. Analogs show what they have, fetch the rest later.

## R1. Optional stages do not stop the path
Required: catalog, SEC search, filings, snapshot (always runs on what
exists). Optional: ownership, prices, corporate actions. A failed optional
stage prints «<stage>: пропущено — <reason>; повтор: <command>» and the path
continues.
**Done when:** test — ownership transport error → `follow` exit 0,
snapshot exists, output names skipped stage + retry command; required
stage failure still non-zero.

## R2. Transport retries with backoff
URLError/timeout/5xx/429 → 3 retries (1 s, 4 s, 15 s), counted in the
budget; no retry on other 4xx.
**Done when:** fake transport failing twice then OK → success, 3 requests
counted; 404 → 1 request.

## R3. Resume only what failed
Next `follow` on that paper runs only skipped stages + snapshot (state in
the store).
**Done when:** test — run 1 skips prices; run 2 makes price requests only
(0 SEC), prints «повтор: цены».

## R4. Offline window
No network → window opens on the last snapshot, header «нет сети —
данные от <date>»; «Собрать» says the same instead of failing mid-way.
**Done when:** offscreen test with an always-failing transport → window
built, banner present, no traceback.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
