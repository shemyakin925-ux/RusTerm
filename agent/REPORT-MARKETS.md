# REPORT-MARKETS — disclosure access probes: SG, AU, KR, NZ, BR, RU — session 2026-09-09

**Unnumbered on purpose.** Side research requested by the user in chat
("проверь всё то же самое для Сингапура, Австралии, Кореи, Новой Зеландии,
Бразилии и России... добавь в отдельный отчёт без номера, чтобы не сбивать
Клода"). Per AGENTS.md conflict rule the chat instruction overrides the TASK
queue; it does NOT enter the TASK-14 / REPORT-14A chain. STATE.json untouched
(still `task: TASK-14`, `report: REPORT-14A`, `status: working`).

## Scope and method
- No code touched, no tests affected. Evidence-only, same method as REPORT-14 (Appendix A = that report, verbatim).
- Live probes: polite curl (browser-like UA, 1–2 requests per host) from this machine (residential IP, Danang UTC+7). One embedded-Chromium (IAB) probe where curl outcome was unclear (SG). No scraping runs, no bulk downloads.
- Plus: web research (official APIs, XBRL reality, vendors) and GitHub repository research per market.
- Probe log: exact commands and responses summarized below; raw bodies not stored.

## Cross-market summary

| Market | Primary filings channel | Live probe result | Verdict for `DisclosuresProvider` |
|---|---|---|---|
| KR | DART (FSS) — Open DART official API | `engopendart.fss.or.kr/engapi/list.json` no-key → `HTTP 200` JSON `{"status":"100","message":"Authentication Keys is missing."}`; `dart.fss.or.kr/main.do` → 200 full HTML; `data.krx.co.kr` → 200 | **viable, first-class** — official free API (registration key), English filings + XBRL downloads, no bot wall observed |
| BR | CVM open data — `dados.cvm.gov.br` | directory listing 200; `dfp_cia_aberta_2024.zip` HEAD → 200, 13,396,366 bytes, `Last-Modified: 2026-09-06`; RAD portal: connect timeout ×1 | **viable, bulk/structured** — regulator-run CSV/ZIP datasets (DFP/ITR/FCA/FRE/cadastro); public API planned 2026–2028 |
| AU | ASX announcements (exchange site) | legacy `/asx/1/...` → 404 JSON "uri-not-found" (dead); `asx/v2/statistics/prevBusDayAnns.do` → 200, 1.2 MB HTML firehose; `asx.api.markitdigital.com/asx-research/1.0/companies/CBA/{header,announcements}` → 200 JSON | **viable** — open endpoints, no auth, no blocking observed; ToS review needed; official route is commercial (ASX DataAPI) |
| NZ | NZX announcements + MBIE registries | `nzx.com` 200; `/markets/NZSX/announcements` → 200, 665 KB, announcement ids embedded in `__NEXT_DATA__`; no public JSON API found; `api.business.govt.nz` → portal (official APIs, account required) | **partial** — site is server-rendered and crawlable; third-party NZXplorer API (free tier) exists; no official free filings API |
| SG | SGX company announcements | `www.sgx.com` SPA 200; `api.sgx.com/announcements/v1.0/` → **403** to curl ×2; IAB Chromium: shell + `api2.sgx.com/content-api` load fine, but announcements widget stuck "Loading..." ~30 s, zero announcements-data requests fired | **unproven** — neither curl nor our embedded browser demonstrably fetches announcements; needs check from user's daily browser profile; paid fallbacks exist (Apify, SGX data products) |
| RU | e-disclosure.ru (ЦРКИ) + MOEX ISS | `iss.moex.com/iss/securities/SBER.json` → 200 JSON (no auth); `e-disclosure.ru` → connection reset ×2 (also via HTTP/1.1); `disclosure.ru` → 200/302; `cbr.ru` → 200 | **restricted from this network** — ISS market/reference data works; filings portal appears foreign-IP-blocked (inference); official e-disclosure API gateway exists but is contract/paid |

## EDGAR cross-route (interlisted foreign issuers)

`GET https://www.sec.gov/files/company_tickers.json` with contact UA → 200, 796,513 bytes. Spot checks (ticker → CIK):
- AU: BHP→811809, RIO→863064. BR: VALE→917851, PBR→1119639. KR: KEP→887225. SG: GRAB→1855612.
- **SE (Sea Limited) NOT found** by exact ticker in this snapshot — surprising for an NYSE issuer; verify via EDGAR FTS before relying on the file for ticker lookups.
- NZ: no major issuer checked/expected (essentially no NZ large-caps file 20-F).
- The 40-F machinery proven in REPORT-14 generalizes to 20-F/6-K for all these issuers; no extra probes run (same host, same UA policy).

## Market details

### South Korea (KR) — best-in-class
- Open DART is the FSS official disclosure API: free key, JSON, includes filing lists, corp registry, original documents and **XBRL financial statements**; English mirror `engopendart.fss.or.kr/engapi/` and English filings repository `englishdart.fss.or.kr`.
- Probes: `opendart.fss.or.kr/api/list.json` (no key) → 302 → error1.html (KR host alive); `engopendart.fss.or.kr/engapi/list.json` (no key) → 200 JSON status 100 "Authentication Keys is missing" — clean, documented error, no bot wall.
- `dart.fss.or.kr/main.do` → 200, 157 KB plain HTML. `data.krx.co.kr` → 200. `kind.krx.co.kr/main/main.do` → 404 (path moved; not investigated).
- GitHub: `josw123/dart-fss` ★378 (upd 2026-08) — de-facto standard client, extracts XBRL statements; `sharebook-kr/pykrx` ★1089 (KRX quotes); `raccoonyy/pykrx-openapi` ★15.
- Reality check: filings are structured at source (XBRL mandatory for financial statements) — unlike CA/AU/NZ, fact extraction may not need PDF parsing for statements.
- Contract mapping: `DisclosuresProvider` = Open DART API (poll_index = list.json per corp_code/date window; fetch_document = document download endpoints). Needs a registered free API key → coordinator decision.

### Brazil (BR) — best-in-class, bulk style
- `dados.cvm.gov.br` is the regulator's open-data portal: `CIA_ABERTA` datasets = cadastro, FCA, FRE, **DFP** (annual statements), **ITR** (quarterly), delivered as per-year ZIPs of CSV; XBRL is the source format CVM receives, portal publishes structured extracts. Probed: DOC dir 200; `dfp_cia_aberta_2024.zip` HEAD 200, 13.4 MB, refreshed 2026-09-06.
- CVM published an open-data plan 2026–2028 promising a **public API** (not yet probed — doesn't exist yet).
- RAD (the filing portal itself, `rad.cvm.gov.br/ENET/`) — connect timeout ×1 from this network; NOT needed for the dataset route.
- B3: `COTAHIST_A2024.ZIP` → 200 (verified by partial 7.6 MB download before deliberate timeout cut); historical market data is open.
- GitHub: `phoemur/fundamentus` ★238, `mv/fundamentus-api` ★111 (fundamentals via fundamentus site), `robertoecf/OpenFinData` ★9 (upd 2026-09, open infra for BR public financial data); commercial: Apify "CVM Financials DFP & ITR".
- Contract mapping: `DisclosuresProvider` = CVM datasets (poll_index = re-fetch dataset dir / per-year ZIP by ETag; list_documents = dataset rows; documents = structured rows, not PDFs). Caveat: full original filing documents (PDFs behind RAD) are NOT in the open datasets — only structured statement rows; decide if that satisfies "disclosures" for this project.

### Australia (AU) — open, but scraping-shaped
- Legacy JSON API dead: `www.asx.com.au/asx/1/company/CBA/announcements` → 404 `{"error_code":"uri-not-found"}` (community: all `/asx/1/` endpoints 404 since ~2026).
- Live and open (probed): `https://asx.api.markitdigital.com/asx-research/1.0/companies/CBA/header` → 200 JSON (name, sector, prices, dateListed); same host `/companies/CBA/announcements` → 200 JSON (headline, date, isPriceSensitive, documentKey, fileSize). `https://www.asx.com.au/asx/v2/statistics/prevBusDayAnns.do?count=5` → 200, 1.2 MB HTML (daily all-company firehose).
- PDF chain (repo-verified, not live-verified by me): announcement HTML → `displayAnnouncement.do?display=pdf&idsId=...` terms page → hidden `pdfURL` → `announcements.asx.com.au/asxpdf/{date}/pdf/{hash}.pdf`; URLs permanent, no tokens; fresh repo (2026-09) reports 40/40 rapid requests unblocked, 461/461 parallel PDFs OK, site behind Imperva but pass-through.
- Official/licensed route exists (ASX DataAPI / TMX-style licensing) — commercial, untested.
- GitHub: `itisaevalex/australia-scraper` (upd 2026-09-01, pure HTTP, reverse-engineered endpoints — best current reference), `desiguel/asx-announce-analysis` ★10, `niallCDS/ASX-Announcements-Discord-Bot` ★3.
- Contract mapping: `DisclosuresProvider` implementable (poll_index = prevBusDayAnns.do once/day or markitdigital announcements per ticker; fetch_document = two-step PDF). ToS review required (site terms vs. automated access).

### New Zealand (NZ) — thin market, workable
- `www.nzx.com` → 200 (Next.js). Real announcement pages: `/markets/NZSX/announcements` → 200, 665 KB, announcement ids (e.g. `/announcements/479472`) **embedded in `__NEXT_DATA__`** — server-rendered, so listing+documents are curl-crawlable without JS; wrong paths (`/api/announcements`, `/markets/announcements`) → NZX-styled 404. No public JSON API found; NZX sells data commercially.
- Third-party: **NZXplorer** (nzxplorer.co.nz) — independent API over NZX announcements/companies/directors/financials (64k+ announcements, iXBRL financials claims); free tier 10 req/min with API key; MCP server without key; GitHub org `mambaventures`. Not live-tested (no key).
- Official registries: Companies Office / MBIE APIs behind `api.business.govt.nz` portal (→ 301 to portal; free account required) — company registry, not filings.
- GitHub: `DrCoco/NZXScraper` ★1 (2022, stale) — ecosystem is thin; confirm with site-based crawler.
- Contract mapping: no clean provider; realistic = lightweight crawler over nzx.com announcement pages + manual `ingest --file` fallback; NZXplorer as metadata enrichment.

### Singapore (SG) — not proven, likely JS/walled
- `www.sgx.com/securities/company-announcements` → 200 (SPA shell, 14.8 KB, client-rendered); `api.sgx.com.sg` NXDOMAIN. Community docs point to `https://api.sgx.com/announcements/v1.0/` as the data API → probed twice with browser-like UA + Referer → **HTTP 403**, 62-byte JSON body (blocked).
- IAB Chromium probe: page shell loads, cookie banner renders, menus/pages/alerts come from `api2.sgx.com/content-api` (persisted-query GraphQL; requests succeed from browser) — **but the announcements widget stayed "Loading..." for ~30 s and never fired a data request** (performance entries show no announcements/host call; no data iframe). Whether this is regional gating, consent gate, or widget bug — undetermined from one visit.
- Paid ecosystem fills the gap: Apify actors "SGX Company Announcements" (from $100/1k items) and "SGX Announcements Watcher"; SGX official data products (commercial). ACRA registry API is separate and paid per-call.
- GitHub: thin — Selenium gist, `Jon-hattan/SGX-Assistant` ★0, RSS hack (2019). Nothing showing a working keyless HTTP path.
- Contract mapping: manual `ingest --file` fallback same as SEDAR+; re-test `api.sgx.com` from the user's normal browser profile (same open question as SEDAR+ fingerprinting) before writing SG off.

### Russia (RU) — network-restricted from our side
- `iss.moex.com/iss/securities/SBER.json` → **200**, 13.7 KB JSON, no auth — MOEX ISS official free API works from this IP (reference/quotes/market data; not filings).
- `www.e-disclosure.ru` (Интерфакс ЦРКИ, the main disclosure wire) → **connection reset ×2** (HTTPS and HTTP/1.1) — foreign-IP blocking suspected (inference, 2 data points, one IP). Its official API gateway exists ("Шлюз API" page) but is authorized/contract access.
- `disclosure.ru` → 200/302 (alternative disclosure agent, page loads); `www.cbr.ru` → 200 (regulator site).
- GitHub: `WLM1ke/apimoex` ★138 (MOEX ISS client), `moexalgo/moexalgo` ★150 (MOEX-backed), `WLM1ke/poptimizer` ★163 ecosystem.
- Reality check: issuer disclosures live on e-disclosure/disclosure.ru as PDFs; no free programmatic filings channel reachable from this network. Sanctions/ToS considerations for automating RU sources are a coordinator-level decision, out of scope here.
- Contract mapping: if RU stays in scope, MOEX ISS can serve reference/quote data; filings require a RU-side network path or a paid gateway contract; otherwise exclude RU.

## GitHub tooling digest (live/maintained only)

| Repo | ★ | Market | Notes |
|---|---|---|---|
| josw123/dart-fss | 378 | KR | DART client, XBRL statement extraction, upd 2026-08 |
| sharebook-kr/pykrx | 1089 | KR | KRX quotes/metrics scraping |
| phoemur/fundamentus | 238 | BR | BOVESPA fundamentals (site) |
| robertoecf/OpenFinData | 9 | BR | open infra over CVM/B3 public data, upd 2026-09 |
| itisaevalex/australia-scraper | 1 | AU | reverse-engineered ASX endpoints + PDF resolution, upd 2026-09 |
| WLM1ke/apimoex | 138 | RU | MOEX ISS client |
| moexalgo/moexalgo | 150 | RU | MOEX official lib |
| (NZ, SG) | — | NZ/SG | no maintained keyless tooling found; NZ has NZXplorer (mambaventures) as SaaS+MCP |

## What not to trust
- SG verdict is genuinely inconclusive: one IAB visit, widget hang may be environment/region-specific; `api.sgx.com` 403 body (62 B JSON) not saved — content not recorded beyond status/size.
- SEA/Sea Limited absence from `company_tickers.json` — single exact-ticker match; verify via FTS before building anything on it.
- AU PDF two-step chain and "no blocking" claims come from one third-party repo (2026-09), not from my own PDF download; I verified only header/announcements JSON and the firehose HTML.
- NZX `__NEXT_DATA__` confirmed to contain announcement ids, but the exact announcement/document field structure was not parsed to schema level.
- CVM RAD timeout and e-disclosure resets are single-IP, 1–2 attempts each; geo-blocking is inference, not verified from a RU endpoint.
- NZXplorer claims (iXBRL financials, 64k announcements) taken from its own site/docs — no request made.
- XBRL statements: KR/BR structured-ness asserted from official docs + dataset shapes, not from parsing an actual XBRL artifact.

## Questions for the coordinator
1. Market priority order for the next milestones? Suggested by effort/legality: KR (official API, needs free key — approve registering one) → BR (CVM bulk datasets) → AU (ASX endpoints, ToS review) → NZ (crawler) → SG/RU (manual import only until a working channel is proven).
2. Does BR structured-rows (no original PDFs) satisfy the project's "disclosures" bar, or do we need RAD PDFs?
3. RU: in scope at all? If yes — who provides a RU-side network path or gateway contract; sanctions/ToS review first.
4. Same open item as CA: user-profile browser check for SGX announcements (and whether `ingest --file` doctrine extends to SG/NZ defaults).
5. Approve formalizing per-market channel doctrine in README §7 / threat-model-sources once priorities are set.

## Request budget spent (honesty)
- SG: sgx.com ×2 curl + ~8 browser page/XHR loads (all OK); api.sgx.com ×2 (403); api.sgx.com.sg ×1 NXDOMAIN.
- AU: asx.com.au ×2 (404, 200); markitdigital ×2 (200); asic.gov.au ×1 (301).
- KR: opendart ×1 (302), engopendart ×1 (200), dart.fss ×1 (200), data.krx ×1 (200), kind.krx ×1 (404).
- NZ: nzx.com ×7 (mix 200/404 — path discovery); companies register hosts ×3 NXDOMAIN; companiesoffice ×1 (200); api.business.govt.nz ×1 (301).
- BR: dados.cvm ×3 (200); rad.cvm ×1 (timeout); b3 COTAHIST ×1 (200, partial download aborted).
- RU: iss.moex ×1 (200); e-disclosure ×2 (reset); disclosure.ru ×2 (200/302); cbr.ru ×1 (200).
- SEC: ×1 (tickers.json, 200). GitHub API: ~14 unauthenticated search/list calls. Other: 0.
- App LLM calls: 0. Network requests by the app itself: 0 (manual curl/browser only).

## HANDOFF
Status:         DONE (probe scope) — SG stays unproven by design of the evidence
Items done:     6 markets probed live (curl, +1 browser session), official/API/scraper channels mapped, EDGAR cross-route checked, GitHub + vendor landscape researched; unnumbered report as instructed
Items not done: no code, no key registrations (KR/BR/NZ keys exist but require accounts), no RU-side network test, no NZXplorer/ASX-PDF live runs
Tests:          not run (no code change)
Pushed:         commit on agent/night-2 only; STATE.json untouched (TASK-14 chain intact)

---

# Appendix A — REPORT-14 (CA), verbatim copy

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
