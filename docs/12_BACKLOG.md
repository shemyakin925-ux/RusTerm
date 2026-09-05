# Backlog

## Overview

Бэклог задач проекта RusEquity Terminal, организованный по фазам и приоритетам.

---

## Priority Legend

| Priority | Description |
|----------|-------------|
| 🔴 Critical | Блокирует разработку, должно быть сделано сейчас |
| 🟠 High | Важно для текущей фазы |
| 🟡 Medium | Нужно сделать в ближайших фазах |
| 🟢 Low | Можно отложить на потом |
| ⚪ Nice to Have | Опционально, если останется время |

---

## PHASE 0.1 — Documentation & Structure Setup ✅ COMPLETE

| ID | Task | Priority | Status | Assignee |
|----|------|----------|--------|----------|
| 0.1-01 | Create `00_MASTER_SPEC.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-02 | Create `01_PROJECT_STATUS.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-03 | Create `02_ROADMAP.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-04 | Create `03_ARCHITECTURE.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-05 | Create `04_DATA_MODEL.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-06 | Create `05_ANALYTICS_MODEL.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-07 | Create `06_DATA_SOURCES.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-08 | Create `07_AI_LAYER.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-09 | Create `08_FRONTEND.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-10 | Create `09_DECISIONS.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-11 | Create `10_KNOWN_ISSUES.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-12 | Create `11_CHANGELOG.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-13 | Create `12_BACKLOG.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-14 | Create `13_HARDWARE_STORAGE.md` | 🟠 High | ✅ Done | LLM Agent |
| 0.1-15 | Create `15_AGENT_RULES.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-16 | Create `16_NEXT_TASK.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-17 | Create `17_VERIFICATION_PROTOCOL.md` | 🔴 Critical | ✅ Done | LLM Agent |
| 0.1-18 | Update `README.md` | 🟠 High | ✅ Done | LLM Agent |

---

## PHASE 0.2 — Project Skeleton

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 0.2-01 | Initialize Flutter project | 🔴 Critical | ⏳ Pending | `flutter create` |
| 0.2-02 | Initialize Backend project | 🔴 Critical | ⏳ Pending | Python/Go |
| 0.2-03 | Setup folder structure | 🔴 Critical | ⏳ Pending | Per architecture docs |
| 0.2-04 | Configure CI/CD pipeline | 🟠 High | ⏳ Pending | GitHub Actions |
| 0.2-05 | Setup pre-commit hooks | 🟠 High | ⏳ Pending | lint, format, tests |
| 0.2-06 | Add basic unit test framework | 🟠 High | ⏳ Pending | pytest + flutter_test |
| 0.2-07 | Create `.gitignore` | 🟠 High | ⏳ Pending | Include `.env`, build artifacts |
| 0.2-08 | Add LICENSE file | 🟡 Medium | ⏳ Pending | MIT/Apache 2.0 |
| 0.2-09 | Setup dependency management | 🟡 Medium | ⏳ Pending | pubspec.yaml, requirements.txt |
| 0.2-10 | Add initial documentation to repo | 🟡 Medium | ⏳ Pending | Copy from `/docs` |

---

## PHASE 1.1 — MOEX ISS Integration

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 1.1-01 | Implement MOEX ISS client | 🔴 Critical | ⏳ Pending | REST API wrapper |
| 1.1-02 | Fetch historical prices | 🔴 Critical | ⏳ Pending | OHLCV data |
| 1.1-03 | Fetch dividend history | 🔴 Critical | ⏳ Pending | Dividend payments |
| 1.1-04 | Implement data normalization | 🔴 Critical | ⏳ Pending | Standardized format |
| 1.1-05 | Add caching layer | 🟠 High | ⏳ Pending | Redis/in-memory |
| 1.1-06 | Implement rate limiting | 🟠 High | ⏳ Pending | Respect MOEX limits |
| 1.1-07 | Write unit tests | 🟠 High | ⏳ Pending | >80% coverage |
| 1.1-08 | Write integration tests | 🟡 Medium | ⏳ Pending | Against live API |
| 1.1-09 | Add error handling | 🟠 High | ⏳ Pending | Retry logic |
| 1.1-10 | Document API usage | 🟡 Medium | ⏳ Pending | Examples in docs |

---

## PHASE 1.2 — Additional Free Sources

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 1.2-01 | E-disclosure parser | 🟠 High | ⏳ Pending | HTML parsing |
| 1.2-02 | RFSD data fetcher | 🟡 Medium | ⏳ Pending | If available |
| 1.2-03 | Company website scraper | 🟡 Medium | ⏳ Pending | Selective |
| 1.2-04 | CBR currency rates | 🟠 High | ⏳ Pending | For currency conversion |
| 1.2-05 | Data validation | 🟠 High | ⏳ Pending | Cross-source validation |
| 1.2-06 | Unified data model | 🔴 Critical | ⏳ Pending | Merge all sources |

---

## PHASE 2.1 — Valuation Metrics

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 2.1-01 | P/E, P/B, P/S calculations | 🔴 Critical | ⏳ Pending | Basic multiples |
| 2.1-02 | EV/EBITDA calculation | 🔴 Critical | ⏳ Pending | Enterprise value |
| 2.1-03 | Percentile ranking | 🔴 Critical | ⏳ Pending | Historical/sector |
| 2.1-04 | PEG ratio | 🟡 Medium | ⏳ Pending | With growth |
| 2.1-05 | Valuation dashboard UI | 🟠 High | ⏳ Pending | Frontend component |

---

## PHASE 2.2 — Factor Analysis

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 2.2-01 | ROE, ROA, ROIC calculations | 🔴 Critical | ⏳ Pending | Profitability |
| 2.2-02 | Margin analysis | 🟠 High | ⏳ Pending | Gross/Operating/Net |
| 2.2-03 | Productivity metrics | 🟠 High | ⏳ Pending | Turnover ratios |
| 2.2-04 | Value Score algorithm | 🔴 Critical | ⏳ Pending | 0-100 score |
| 2.2-05 | Quality Score algorithm | 🔴 Critical | ⏳ Pending | 0-100 score |
| 2.2-06 | Composite Score | 🔴 Critical | ⏳ Pending | Weighted average |

---

## PHASE 2.3 — Relative Strength & Dividends

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 2.3-01 | Relative Strength calculation | 🔴 Critical | ⏳ Pending | vs IMOEX |
| 2.3-02 | Momentum Score | 🟠 High | ⏳ Pending | Factor score |
| 2.3-03 | Dividend Yield | 🔴 Critical | ⏳ Pending | Current yield |
| 2.3-04 | Dividend Growth (CAGR) | 🟠 High | ⏳ Pending | 1Y, 3Y, 5Y |
| 2.3-05 | Dividend Consistency Score | 🟠 High | ⏳ Pending | 0-100 score |
| 2.3-06 | Total Return calculation | 🔴 Critical | ⏳ Pending | Price + Dividends |

---

## PHASE 3.1 — Remote AI API Integration

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 3.1-01 | OpenAI client implementation | 🔴 Critical | ⏳ Pending | GPT-4, GPT-3.5 |
| 3.1-02 | Anthropic client implementation | 🟠 High | ⏳ Pending | Claude models |
| 3.1-03 | Prompt templates | 🔴 Critical | ⏳ Pending | Stock summary, Q&A |
| 3.1-04 | Response parsing | 🟠 High | ⏳ Pending | Validate output |
| 3.1-05 | API key management | 🔴 Critical | ⏳ Pending | Environment variables |
| 3.1-06 | Rate limiting | 🟠 High | ⏳ Pending | Per provider limits |
| 3.1-07 | Response caching | 🟡 Medium | ⏳ Pending | Reduce API calls |

---

## PHASE 3.2 — Local LLM Support

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 3.2-01 | Ollama client | 🔴 Critical | ⏳ Pending | Local inference |
| 3.2-02 | LM Studio support | 🟡 Medium | ⏳ Pending | Alternative |
| 3.2-03 | Model selection UI | 🟠 High | ⏳ Pending | User choice |
| 3.2-04 | Offline mode | 🟠 High | ⏳ Pending | No internet required |
| 3.2-05 | Fallback to remote | 🟡 Medium | ⏳ Pending | If local unavailable |

---

## PHASE 4.1 — Core UI Components

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 4.1-01 | Stock list screen | 🔴 Critical | ⏳ Pending | Search, filter, sort |
| 4.1-02 | Stock detail screen | 🔴 Critical | ⏳ Pending | Full info view |
| 4.1-03 | Price chart component | 🔴 Critical | ⏳ Pending | Interactive |
| 4.1-04 | Metric cards | 🟠 High | ⏳ Pending | Key metrics display |
| 4.1-05 | Navigation/Routing | 🔴 Critical | ⏳ Pending | go_router |
| 4.1-06 | Theme system | 🟠 High | ⏳ Pending | Light/dark mode |

---

## PHASE 4.2 — Analytics Dashboard

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 4.2-01 | Valuation dashboard | 🔴 Critical | ⏳ Pending | Percentiles view |
| 4.2-02 | Factor analysis view | 🔴 Critical | ⏳ Pending | Scores visualization |
| 4.2-03 | Comparison tools | 🟠 High | ⏳ Pending | Multi-stock compare |
| 4.2-04 | Screening results | 🟠 High | ⏳ Pending | Filtered lists |
| 4.2-05 | Export functionality | 🟡 Medium | ⏳ Pending | CSV/PDF export |

---

## PHASE 4.3 — Mobile Optimization

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 4.3-01 | Responsive layouts | 🔴 Critical | ⏳ Pending | All screen sizes |
| 4.3-02 | Touch gesture support | 🟠 High | ⏳ Pending | Swipe, pinch |
| 4.3-03 | Mobile-specific features | 🟡 Medium | ⏳ Pending | Haptic feedback |
| 4.3-04 | Performance optimization | 🟠 High | ⏳ Pending | Smooth scrolling |
| 4.3-05 | Desktop layout refinement | 🟠 High | ⏳ Pending | Large screens |

---

## PHASE 5.1 — Testing & QA

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 5.1-01 | Unit tests (>80% coverage) | 🔴 Critical | ⏳ Pending | Backend + Frontend |
| 5.1-02 | Integration tests | 🔴 Critical | ⏳ Pending | API + DB |
| 5.1-03 | E2E tests | 🔴 Critical | ⏳ Pending | Full user flows |
| 5.1-04 | Performance testing | 🟠 High | ⏳ Pending | Load tests |
| 5.1-05 | Security audit | 🟠 High | ⏳ Pending | Vulnerability scan |
| 5.1-06 | Bug fixing | 🔴 Critical | ⏳ Pending | From testing |

---

## PHASE 5.2 — Release Preparation

| ID | Task | Priority | Status | Notes |
|----|------|----------|--------|-------|
| 5.2-01 | Complete documentation | 🔴 Critical | ⏳ Pending | User + Dev docs |
| 5.2-02 | Performance optimization | 🟠 High | ⏳ Pending | Final polish |
| 5.2-03 | App store preparation | 🟠 High | ⏳ Pending | iOS/Android |
| 5.2-04 | Desktop installers | 🟠 High | ⏳ Pending | Win/Mac/Linux |
| 5.2-05 | Marketing materials | 🟡 Medium | ⏳ Pending | Screenshots, demo |
| 5.2-06 | Release announcement | 🟡 Medium | ⏳ Pending | Blog, social |

---

## Future Considerations (Post v1.0)

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| FUT-01 | Web version | 🟡 Medium | Phase 4+ |
| FUT-02 | Portfolio tracking | 🟠 High | User portfolios |
| FUT-03 | Alerts system | 🟠 High | Price/metric alerts |
| FUT-04 | Real-time data | 🟡 Medium | WebSocket |
| FUT-05 | Other markets (CIS) | 🟡 Medium | Expansion |
| FUT-06 | Advanced AI features | 🟡 Medium | Portfolio optimization |
| FUT-07 | Social features | ⚪ Nice | Community insights |
| FUT-08 | API for developers | 🟡 Medium | Public API |

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial backlog            |
