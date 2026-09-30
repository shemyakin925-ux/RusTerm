"""Инкрементальный проход по списку наблюдения (TASK-13 Z2/Z4).

Один проход = на каждый инструмент ровно один запрос submissions; если
дата последней отчётности не новее отражённой в состоянии эмитента —
companyfacts не запрашивается вовсе («не изменилось — не скачивается»).
Валидаторы кеша (ETag, Last-Modified) передаются провайдеру значением
и хранятся в базе (issuer_ingest_state, миграция 37) — провайдер о
базе не знает (I10). Пропуск виден: строка результата с причиной, а
не молчание. Демона нет: проход — одна команда, её ставят в cron.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from rusterm.markets import registry_prefix_owner
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.providers.budget import ConfigError
from rusterm.providers.edgar import NotModified
from rusterm.store.repos import link_superseded, persist_ingestion_results


@dataclass
class RefreshResult:
    """Итог прохода по одному инструменту; action: planned | updated |
    unchanged | error. calls — фактические вызовы по видам URL
    (для planned — оценка)."""
    instrument_id: str
    issuer_id: str
    action: str
    facts: Optional[int] = None
    last_filing_date: Optional[str] = None
    reason: Optional[str] = None
    calls: dict = field(default_factory=dict)
    # calls: фактические сетевые вызовы по видам URL (для planned — оценка)


def _persist_companyfacts(repos, doc: dict, issuer_id: str, cik: int) -> int:
    """companyfacts -> raw -> parse -> факты. Возвращает число ЖИВЫХ
    фактов: проигравшие дедупликации тоже ложатся в базу, но помеченные
    `superseded_by` (TASK-92 C1) — в расчёт они не входят."""
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
    sha = hashlib.sha256(raw).hexdigest()
    if repos.raw.has(sha):
        return 0  # байт-в-байт тот же ответ: факты уже в базе
    obj = repos.raw.put(
        raw, provider="edgar", block="fundamentals",
        url=("https://data.sec.gov/api/xbrl/companyfacts/"
             f"CIK{cik:010d}.json"))
    parsed = CompanyFactsParser().parse(
        raw, {"issuer_id": issuer_id, "source_ref": obj.sha256})
    fact_dicts = []
    for fact in parsed.all_facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        fact_dicts.append(fact)
    link_superseded(fact_dicts)
    persist_ingestion_results(repos.conn, fact_dicts, [])
    return sum(1 for f in fact_dicts if not f.get("superseded_by"))


def refresh_watchlist(repos, provider_factory: Callable,
                      watchlist_id: str, as_of: str, dry_run: bool = False,
                      builder=None) -> list[RefreshResult]:
    """Один инкрементальный проход. provider_factory(cik) отдаёт
    настроенного EdgarProvider (гейт общий на проход). dry_run не
    делает ни одного запроса и печатает план. Снапшот
    пересобирается только там, где приехали новые факты; при builder
    = None снапшоты не строятся вовсе."""
    results: list[RefreshResult] = []

    for member in repos.watchlist.members(watchlist_id):
        instrument = repos.instrument.get_instrument(member["instrument_id"])
        if instrument is None:
            results.append(RefreshResult(
                instrument_id=member["instrument_id"], issuer_id="",
                action="error",
                reason="unknown_issuer: instrument not found"))
            continue
        issuer = repos.instrument.get_issuer(instrument.issuer_id)
        # ТЗ-92 C2: проход говорит с EDGAR, поэтому чужой префикс
        # идентификатора — отказ ДО запроса. Без этого шага CD_CVM
        # бразильского эмитента уходил в SEC как CIK и чужие факты
        # ложились под этот id (замер: 2 запроса на одного такого —
        # `/tmp/c2-red.log:348`, транспорт посчитан).
        owner = registry_prefix_owner(instrument.issuer_id)
        if issuer is not None and owner not in (None, "edgar"):
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="error",
                reason="unknown_issuer: registry is not edgar"))
            continue
        cik_raw = (issuer.registry_id or "") if issuer else ""
        if not cik_raw.isdigit():
            # B39: «ошибка» — не причина; словарь rusterm/reasons.py
            # называет её unknown_issuer, продолжение — что именно
            # не задано
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="error",
                reason="unknown_issuer: registry_id is empty"))
            continue
        cik = int(cik_raw)
        state = repos.issuer_state.get(instrument.issuer_id)

        if dry_run:
            # ни одного запроса: план из состояния базы
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="planned",
                last_filing_date=state and state["last_filing_date"],
                reason=("первый сбор: submissions + companyfacts"
                        if state is None else
                        "submissions; companyfacts только при изменении"),
                calls={"submissions": 1,
                       "companyfacts": 0 if state else 1}))
            continue

        provider = provider_factory(cik)
        if isinstance(provider, ConfigError):
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="error",
                reason=f"провайдер недоступен: {provider.reason}"))
            continue

        latest = provider.latest_filing_date()
        calls = {"submissions": 1, "companyfacts": 0}
        if isinstance(latest, ConfigError):
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="error",
                reason=f"submissions недоступен: {latest.reason}",
                calls=calls))
            continue

        if state and state["last_filing_date"] and latest is not None \
                and latest <= state["last_filing_date"]:
            # не изменилось: submissions не новее отражённой даты —
            # companyfacts не запрашивается вовсе
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="unchanged",
                last_filing_date=state["last_filing_date"],
                reason="последняя отчётность не новее отражённой",
                calls=calls))
            continue

        validators = None
        if state and (state.get("etag") or state.get("last_modified")):
            validators = {k: state[k] for k in ("etag", "last_modified")
                          if state.get(k)}
        outcome = provider.fetch_companyfacts_conditional(validators)
        calls["companyfacts"] = 1
        if isinstance(outcome, ConfigError):
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="error",
                reason=f"companyfacts недоступен: {outcome.reason}",
                calls=calls))
            continue
        if isinstance(outcome, NotModified):
            # 304 по валидатору: тело не изменилось, хотя дата подачи
            # сдвинулась — запоминаем дату, данных не привозилось
            repos.issuer_state.put(instrument.issuer_id, latest,
                                   etag=state.get("etag") if state else None,
                                   last_modified=state.get("last_modified")
                                   if state else None)
            results.append(RefreshResult(
                instrument_id=instrument.instrument_id,
                issuer_id=instrument.issuer_id, action="unchanged",
                last_filing_date=latest,
                reason="companyfacts: 304 Not Modified",
                calls=calls))
            continue

        doc, fresh = outcome
        facts = _persist_companyfacts(repos, doc, instrument.issuer_id, cik)
        repos.issuer_state.put(instrument.issuer_id, latest,
                               etag=fresh.get("etag"),
                               last_modified=fresh.get("last_modified"))
        repos.coverage.upsert(instrument.instrument_id, "fundamentals",
                              "ready")
        if facts and builder is not None:
            builder.build(instrument.instrument_id,
                          instrument.issuer_id, as_of)
        results.append(RefreshResult(
            instrument_id=instrument.instrument_id,
            issuer_id=instrument.issuer_id,
            action="updated" if facts else "unchanged",
            facts=facts, last_filing_date=latest,
            reason=None if facts else
            "companyfacts уже в store (дедупликация по sha256)",
            calls=calls))
    return results
