# REPORT-14 — SEDAR+ (CA) access channels: live probe, session 2026-09-09

## Scope and authority
- Not from a TASK file. Direct user instruction in chat ("протестируй варианты доступа и положи в следующий отчёт для Клода") — per AGENTS.md conflict rule, user instruction overrides the "no work without TASK" queue. TASK-13 stays `awaiting_review`; STATE.json left untouched (task/report still point to TASK-13/REPORT-13 deliberately).
- No code touched. No tests affected. Report is evidence-only.
- Prior chat analysis (no live data) claimed: no official SEDAR+ API; ToS forbids scraping; three viable channels (EDGAR route, semi-manual import, browser automation). This report replaces claims with measurements.

## Results

| # | Channel | Probe | Result | Verdict for project |
|---|---|---|---|---|
| 1 | EDGAR (interlisted CA issuers) | 8 requests, all logged below | works end-to-end | **viable** — satisfies full `DisclosuresProvider` contract |
| 2 | SEDAR+ via plain HTTP client | 4 requests | 403 at edge (Radware), incl. document URLs | **dead** for `fetch_document` |
| 3 | SEDAR+ via embedded Chromium (IAB, real JS) | 2 page loads | 403 at edge, hard block, no JS challenge served | **dead** for automation |
| 4 | SEDAR+ semi-manual (file import) | not network-tested; implied by #2/#3 | user's own browser is the only reliable fetcher | **viable** as manual `ingest --file` channel |

## Channel 1 — EDGAR route: evidence

SEC requires a contact-format User-Agent. Default curl UA is blocked:
- `curl https://www.sec.gov/files/company_tickers.json` (no UA / descriptive UA) → `HTTP 403`, body: "SEC.gov | Request Rate Threshold Exceeded" (2 requests).
- Same URL with `-H "User-Agent: PersonalResearch rusterm@example.com"` → `HTTP 200`, 796,513 bytes, 10,407 tickers.
- Confirms the existing `RUSTERM_SEC_UA` design gate is mandatory, not cosmetic.

Ticker→CIK works for interlisted Canadian issuers (`company_tickers.json`):
SHOP→1594805, ENB→895728, TD→947263, RY→1000275, BAM→1937926, CNQ→1017413, TRI→1075124. **CSU (Constellation Software) NOT IN EDGAR** — TSX-only issuers are the structural coverage gap.

Forms differ per issuer; do not hardcode form sets:
- SHOPIFY (CIK 1594805) full history: `6-K`×177, but recent filings are `10-Q`/`10-K` era (domestic-filer treatment); historical `40-F`×8.
- TORONTO DOMINION BANK (CIK 947263) recent 1000: `6-K`×28, `40-F` annual. Latest 40-F: accession `0001562762-25-000289`, filed 2025-12-04, primary `40f20251031.htm`.

Document fetch works (`DisclosuresProvider.fetch_document`):
- `GET /Archives/edgar/data/947263/000156276225000289/index.json` → 200; exhibits ex991–ex998 (0.9–6.4 MB HTML) + R*.htm rendering files.
- `GET .../ex992.htm` → 200, 3,988,704 bytes, text begins: "TD BANK GROUP • 2025 ANNUAL REPORT • **MANAGEMENT'S DISCUSSION AND ANALYSIS** … for the year ended October 31, 2025" — exactly the CA-market document class the README promises (MD&A). ex991/ex993 not inspected (assumed AIF / financial statements; unverified).

`poll_index` candidates ("one request per source"):
- EDGAR full-text search: `GET https://efts.sec.gov/LATEST/search-index?q=%22annual+information+form%22&forms=40-F&dateRange=custom&startdt=2026-08-01&enddt=2026-09-09` → `HTTP 200` JSON, `hits.total.value = 2` (ADURO CLEAN TECHNOLOGIES, 2026-08-31). One request covers all issuers per time window.
- Caveat: FTS is free-text — a 40-F lacking the literal phrase would be missed. For the watched-set, the per-CIK submissions API + conditional GET (already built in M4, REPORT-13 Z1/Z2) remains the precise incremental mechanism; FTS is a source-wide discovery supplement.

## Channels 2/3 — SEDAR+ direct access: evidence

Plain HTTP client (4 curl GETs, browser-like UA, Accept header):
- `https://www.sedarplus.ca/landingpage/` → `HTTP 301`, `Location: https://www.sedarplus.ca`, response header `server: rdwr` (= Radware).
- `https://www.sedarplus.ca/` → `HTTP 403`, 334-byte block page: "403 Forbidden … Transaction ID: 62bf8576…".
- `https://www.sedarplus.ca/csa-party/records/document.html?id=111…1` (the "Generate URL" document pattern) → `HTTP 403`, same block page. So even a valid generated document URL is unreachable for non-browser clients — the edge block fires before any document lookup.

Embedded Chromium browser (ZCode IAB — real JS execution, not curl):
- `goto landingpage/` → redirected to `/`, `title: "403 Forbidden"`; reload + 8 s wait → same; page body: "403 Forbidden Transaction ID: 119d19a7…", **zero `<script>` tags** — a hard deny, no solvable JS challenge is even served.

Requests to SEDAR+ deliberately stopped at 6 total to avoid IP escalation.

**Inference (not fully verified, see What not to trust):** blocking is client-fingerprint based (TLS/HTTP2/automation heuristics), not IP based — curl and IAB were blocked from the same residential IP where normal interactive Chrome/Safari sessions are known to work. Consequence for the project: rusterm cannot fetch SEDAR+ documents itself — not via requests/curl, not via an embedded/automated browser. The user's own interactive browser is the only reliable downloader; therefore the semi-manual channel must be **file-based** (user saves the PDF in their browser → `rusterm ingest --file` → content-addressed store keeps the sha256 idempotency invariant), not URL-based.

## XBRL reality check (no network test needed)
- CSA XBRL filing is voluntary; CSA states "Filing with XBRL filings are not yet available in SEDAR+" (securities-administrators.ca/industry-resources/xbrl-filing/). CA statements are PDF/HTML either way → fact extraction from CA documents is parsing work regardless of channel; EDGAR-route 40-F exhibits are likewise untagged (foreign private issuers).

## Verdict mapped to docs/module-contracts.md
- `DisclosuresProvider` for market CA: implementable **only on the EDGAR route** (poll_index = per-CIK submissions conditional GET, already proven in M4; list_documents = filing index.json; fetch_document = direct HTTPS, idempotent). Suggest `ca_interlisted` profile: market=CA, source=edgar, forms {40-F, 6-K, and 10-K/10-Q where issuer switched}.
- SEDAR+ cannot be a `DisclosuresProvider` (no reachable fetch, no index). Manual `ingest --file` channel sits outside the provider contract — same tier as `rusterm add --cik` offline path.
- Threat model: `docs/threat-model-sources.md` class A treatment stays correct for the EDGAR route (it inherits EDGAR's existing monitoring); SEDAR+ as a source is effectively human-only.

## What not to trust
- Fingerprint-vs-IP blocking on SEDAR+ is an inference from 6 data points on one IP; not verified against the user's daily browser profile.
- ex991/ex993 content assumed (AIF / financial statements) — only ex992 (MD&A) was opened and read.
- FTS hit objects returned `_id: None` in my parse — response shape needs a proper look before building on it.
- SHOP 10-K/10-Q vs 40-F eras show per-issuer form drift: any CA profile must derive form sets from submissions data, not constants.
- Vendor/third-party APIs (NewHedge, commercial feeds) not tested at all — out of scope.

## Questions for the coordinator
1. Accept "CA market = EDGAR route (40-F/6-K, derived form sets) + manual ingest --file for SEDAR+-only docs" as the interim CA doctrine? If yes this belongs in README §7 and threat-model-sources as a decision note.
2. Approve scope for a manual import command (`rusterm ingest --file <pdf> [--source-url https://www.sedarplus.ca/...]`): store raw + sha256 + provenance; parsing deferred?
3. Discovery for TSX-only issuers (CSU-class): source TBD — TSX/TSXV official directories untested here. Separate spike?
4. SEDI (insider reports) explicitly out of scope for now?

## Request budget spent (honesty)
- SEC: 8 total (2 blocked 403 by UA policy, 6 successful). SEDAR+: 6 (all blocked). Other hosts: 0.
- App LLM calls: 0. Network requests by the app itself: 0 (manual curl/browser only).

## HANDOFF
Status:          DONE
Items done:      3 channels probed live with logged evidence; verdicts mapped to DisclosuresProvider contract; STATE.json intentionally untouched
Items not done:  user's own-browser SEDAR+ check (fingerprint inference unverified); TSX/TSXV discovery; third-party vendors — open questions 1–4 above
Tests:           not run (no code change)
Pushed:          commit on agent/night-2 only
