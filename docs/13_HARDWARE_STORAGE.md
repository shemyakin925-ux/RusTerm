# Hardware & Storage Requirements

## Overview

Данный документ описывает требования к аппаратному обеспечению и хранению данных для RusEquity Terminal.

---

## Development Environment

### Minimum Requirements

| Component | Specification | Notes |
|-----------|---------------|-------|
| CPU | 4 cores (Intel i5 / AMD Ryzen 5) | Для разработки |
| RAM | 8 GB | Минимум для Flutter + IDE |
| Storage | 20 GB free space | Код + зависимости |
| OS | Windows 10, macOS 10.15, Linux (Ubuntu 20.04+) | Любая основная ОС |

### Recommended Requirements

| Component | Specification | Notes |
|-----------|---------------|-------|
| CPU | 8 cores (Intel i7 / AMD Ryzen 7) | Комфортная разработка |
| RAM | 16 GB | Для эмуляторов + backend |
| Storage | 50 GB SSD | Быстрая сборка |
| OS | Any modern | Flutter supports all |

### For Local LLM Development

| Component | Specification | Notes |
|-----------|---------------|-------|
| RAM | 32 GB+ | Для больших моделей |
| GPU | NVIDIA with 8GB+ VRAM | Опционально, для ускорения |
| Storage | 100 GB+ | Для хранения моделей |

---

## Production Deployment

### Backend Server

#### Small Scale (Development / Testing)

| Component | Specification | Estimated Cost |
|-----------|---------------|----------------|
| CPU | 2 vCPU | ~$10-20/month |
| RAM | 4 GB | |
| Storage | 40 GB SSD | |
| Provider | Any VPS (DigitalOcean, Hetzner, etc.) | |

#### Medium Scale (Beta Users)

| Component | Specification | Estimated Cost |
|-----------|---------------|----------------|
| CPU | 4 vCPU | ~$40-80/month |
| RAM | 8 GB | |
| Storage | 80 GB SSD | |
| Database | Managed PostgreSQL | ~$15-30/month |
| Cache | Managed Redis | ~$10-20/month |

#### Large Scale (Production)

| Component | Specification | Estimated Cost |
|-----------|---------------|----------------|
| CPU | 8+ vCPU | ~$160+/month |
| RAM | 16+ GB | |
| Storage | 200+ GB SSD | |
| Database | Managed PostgreSQL (HA) | ~$100+/month |
| Cache | Managed Redis (HA) | ~$50+/month |
| CDN | For static assets | ~$20-50/month |

---

## Database Storage Estimates

### Data Types and Sizes

| Data Type | Estimated Size | Retention | Total |
|-----------|----------------|-----------|-------|
| Price Data (all stocks, daily) | ~10 MB/year per stock | All history | ~500 MB |
| Dividend Data | ~100 KB per stock | All history | ~5 MB |
| Financial Statements | ~500 KB per report | 10 years | ~50 MB |
| Analytics Snapshots | ~1 KB per stock per day | 5 years | ~100 MB |
| AI Insights | ~10 KB per insight | 1 year | ~50 MB |
| User Data (future) | ~100 KB per user | Active users | Variable |

### Total Storage Requirements

| Timeframe | Estimated Storage |
|-----------|-------------------|
| Initial (Phase 1) | ~1 GB |
| After Phase 2 | ~2 GB |
| After Phase 3 | ~3 GB |
| Production (1 year) | ~5 GB |
| Production (5 years) | ~10-15 GB |

**Recommendation:** Start with 40 GB, scale as needed.

---

## Frontend Client Requirements

### Mobile (iOS/Android)

| Requirement | Specification |
|-------------|---------------|
| iOS Version | iOS 12.0+ |
| Android Version | Android 6.0 (API 23)+ |
| App Size | ~50-100 MB (initial download) |
| Storage | ~200 MB (with cache) |
| RAM | 2 GB minimum |

### Desktop (Windows/macOS/Linux)

| Requirement | Specification |
|-------------|---------------|
| Windows | Windows 10+ |
| macOS | macOS 10.15+ |
| Linux | Ubuntu 20.04+, Fedora 35+, etc. |
| App Size | ~100-200 MB |
| Storage | ~500 MB (with cache) |
| RAM | 4 GB minimum |

---

## Caching Strategy

### Redis Cache Tiers

| Tier | Data Type | TTL | Memory Estimate |
|------|-----------|-----|-----------------|
| L1 | Current prices | 5 min | ~10 MB |
| L2 | Daily prices | 1 hour | ~50 MB |
| L3 | Analytics data | 24 hours | ~100 MB |
| L4 | Static data | 7 days | ~50 MB |

**Total Redis Memory:** 256 MB - 1 GB recommended

### Local Cache (Client-side)

| Platform | Storage Type | Max Size |
|----------|--------------|----------|
| Mobile | Hive/SQFlite | 100 MB |
| Desktop | Hive/LocalStorage | 500 MB |
| Web (future) | IndexedDB | 200 MB |

---

## Backup Requirements

### Database Backups

| Frequency | Type | Retention | Storage |
|-----------|------|-----------|---------|
| Hourly | Incremental | 24 hours | ~100 MB |
| Daily | Full | 7 days | ~5 GB |
| Weekly | Full | 4 weeks | ~20 GB |
| Monthly | Full | 12 months | ~80 GB |

**Total Backup Storage:** ~150 GB recommended

### Backup Strategy

```yaml
backup:
  database:
    provider: pg_dump (PostgreSQL)
    schedule: "0 2 * * *"  # Daily at 2 AM
    retention_days: 30
    destination: S3-compatible storage
  
  files:
    include:
      - /uploads
      - /exports
    schedule: "0 3 * * *"
    retention_days: 14
```

---

## Network Requirements

### Bandwidth Estimates

| Operation | Data Transfer | Frequency |
|-----------|---------------|-----------|
| Initial app load | ~5 MB | Per session |
| Stock list refresh | ~100 KB | Every 5 min |
| Stock detail load | ~50 KB | Per view |
| Analytics calculation | ~200 KB | On demand |
| AI insights | ~10 KB | On demand |

### API Rate Limits (External Sources)

| Source | Limit | Strategy |
|--------|-------|----------|
| MOEX ISS | ~60 req/min | Cache aggressively |
| E-disclosure | Unknown, be conservative | Rate limit to 10 req/min |
| CBR | ~100 req/day | Cache daily rates |

---

## Scalability Considerations

### Horizontal Scaling

- **Stateless backend** — можно масштабировать горизонтально
- **Database read replicas** — для увеличения read throughput
- **Redis Cluster** — для распределённого кэша

### Vertical Scaling

- **Database** — увеличивать RAM и CPU по мере роста данных
- **Cache** — увеличивать память для большего hit rate

### Auto-scaling Triggers

```yaml
autoscaling:
  cpu_threshold: 70%
  memory_threshold: 80%
  min_instances: 2
  max_instances: 10
  cooldown_period: 300s
```

---

## Cost Estimates (Monthly)

### Development / Testing

| Item | Cost (USD) |
|------|------------|
| VPS (2 vCPU, 4 GB) | $10-20 |
| Database (managed) | $15-30 |
| **Total** | **$25-50/month** |

### Beta / Small Production

| Item | Cost (USD) |
|------|------------|
| VPS (4 vCPU, 8 GB) | $40-80 |
| Database (managed) | $30-60 |
| Redis (managed) | $15-30 |
| Storage/Backup | $10-20 |
| **Total** | **$95-190/month** |

### Full Production

| Item | Cost (USD) |
|------|------------|
| Compute (8+ vCPU) | $160-320 |
| Database (HA) | $100-200 |
| Redis (HA) | $50-100 |
| Storage/Backup | $50-100 |
| CDN | $20-50 |
| Monitoring | $20-50 |
| **Total** | **$400-820/month** |

---

## Monitoring & Alerts

### Key Metrics to Monitor

- CPU usage
- Memory usage
- Disk I/O
- Database connections
- Cache hit rate
- API response times
- Error rates

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| CPU | >70% | >90% |
| Memory | >80% | >95% |
| Disk | >70% | >90% |
| DB Connections | >80% | >95% |
| Cache Hit Rate | <70% | <50% |
| Response Time | >500ms | >2000ms |

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial hardware/storage doc |
