"""Конвейер сбора — процесс 1 по docs/processes.md §46-123.

Девять узлов: plan_refresh, poll_source_index, enqueue, fetch, store_raw,
parse, validate, persist, cascade. Сеть — только в узлах 2 и 4 (здесь —
провайдеры, ошибки которых приходят значениями). Ветки ошибок E1-E5
обрабатываются по таблице processes.md §110-121: внешняя ошибка не должна
выглядеть как отсутствие данных.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4

from rusterm.core.fact import locator_from_json, resolve_locator
from rusterm.parsers import parse_auto
from rusterm.normalize.concepts import (
    canonical_for,
    map_version,
    priority_rank,
    strip_taxonomy,
)
from rusterm.providers.base import ProviderError
from rusterm.providers.disclosures import FetchedDocument, IndexRecord
from rusterm.store.repos import RepoRegistry, persist_ingestion_results

# Блок конвейера по типу документа индекса.
_BLOCK_BY_DOC_TYPE = {
    "10-K": "fundamentals",
    "10-Q": "fundamentals",
    "INSIDER": "ownership",
    "PRICES": "prices",
}

# Блоки, помечаемые stale каскадом после свежих fundamentals (§14-24).
_CASCADE_DEPENDENTS = ("industry_metrics", "llm_summary")

# Блоки источника раскрытий — помечаются error при недоступном индексе (E1).
_DISCLOSURE_BLOCKS = ("fundamentals", "ownership")


@dataclass
class PipelineResult:
    """Итог прогона конвейера — по узлам, для отчёта и тестов."""
    unmapped_concepts: int = 0
    jobs_done: int = 0
    facts_stored: int = 0
    suspects: int = 0          # E5: записаны со статусом suspect
    duplicates: int = 0        # узел 5: объект уже в store, парсинг пропущен
    deduped_jobs: int = 0      # узел 3: задание уже было по ключу
    needs_verification: int = 0  # E4: парсер не справился
    fetch_failures: int = 0    # E2/E3 исчерпаны
    coverage_errors: int = 0   # E1: индекс недоступен


@dataclass
class PruneResult:
    kept_needs_verification: int = 0
    deleted_without_facts: int = 0


def _peek_doc_kind(content: bytes) -> str | None:
    """doc_kind из метаданных документа, без разбора всего тела как фактов."""
    try:
        doc = json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if isinstance(doc, dict):
        kind = doc.get("doc_kind")
        return kind if isinstance(kind, str) else None
    return None


def _validate_fact(fact: dict, getter: Callable[[str], bytes]) -> list[str]:
    """Узел 7: единицы, период, resolve(locator) == value (processes.md §69).

    Возвращает список проблем; пустой — факт валиден.
    """
    problems: list[str] = []
    if not fact.get("unit"):
        problems.append("unit_missing")
    if fact.get("period_end", "") < fact.get("period_start", ""):
        problems.append("period_order")
    try:
        loc = locator_from_json(fact["locator"])
        resolved = resolve_locator(loc, getter)
        if resolved != fact.get("value"):
            problems.append("resolve_mismatch")
    except Exception as e:  # локатор обязан разрешаться; не разрешился — проблема
        problems.append(f"resolve_error:{type(e).__name__}")
    return problems


def apply_concept_map(fact: dict) -> int:
    """Заполнить canonical_concept/concept_map_version у словаря факта
    (TASK-9 V0; TASK-18 G3/G4). Возвращает 1, если тег не отобразился
    (факт остаётся, каноническое имя — NULL: считается, а не
    выбрасывается). Таксономия берётся из префикса концепта факта
    (us-gaap/ifrs-full — свои карты и свои версии карт)."""
    taxonomy, local = strip_taxonomy(fact.get("concept", ""))
    effective = taxonomy or "us-gaap"
    canonical = canonical_for(local, effective) \
        if effective in ("us-gaap", "ifrs-full") else None
    if canonical is not None:
        fact["canonical_concept"] = canonical
        fact["concept_map_version"] = map_version(effective)
        return 0
    fact["canonical_concept"] = None
    fact["concept_map_version"] = None
    return 1


class IngestionPipeline:
    """Сбор по одному источнику раскрытий и одному инструменту.

    providers — словарь имя -> DisclosuresProvider (синтетические в тестах);
    sleep подменяется в тестах, чтобы паузы повторов не ждали реального времени.
    """

    def __init__(self, repos: RepoRegistry,
                 providers: dict[str, object],
                 sleep: Callable[[float], None] = time.sleep,
                 max_attempts: int = 3):
        self._repos = repos
        self._providers = providers
        self._sleep = sleep
        self._max_attempts = max_attempts

    def run(self, instrument_id: str, issuer_id: str,
            provider_name: str, index_kind: str = "disclosures") -> PipelineResult:
        result = PipelineResult()
        provider = self._providers[provider_name]  # нет имени — программная ошибка

        # ── Узел 2: poll_source_index — один запрос на источник (E1) ──
        cursor = self._repos.job.get_cursor(provider_name, index_kind) or ""
        poll = None
        for attempt in range(1, self._max_attempts + 1):
            outcome = provider.poll_index(cursor)
            if not isinstance(outcome, ProviderError):
                poll = outcome
                break
            self._sleep(2.0 ** attempt)  # экспоненциальная пауза
        if poll is None:
            # E1: coverage=error по блокам источника с причиной; не молчаливый пропуск.
            for block in _DISCLOSURE_BLOCKS:
                self._repos.job.coverage_upsert(
                    instrument_id, block, "error",
                    f"E1:index_unavailable:{provider_name}")
            result.coverage_errors += 1
            return result
        self._repos.job.set_cursor(provider_name, index_kind, poll.cursor)

        # ── Узел 3: enqueue — дедупликация по ключу идемпотентности ──
        jobs: list[tuple[str, IndexRecord]] = []
        for rec in poll.records:
            job_id = str(uuid4())
            key = f"{provider_name}:{rec.url}"
            placed = self._repos.job.enqueue(
                job_id=job_id,
                instrument_id=instrument_id,
                block=_BLOCK_BY_DOC_TYPE.get(rec.doc_type, "fundamentals"),
                provider=provider_name,
                target_date=rec.period,
                url=rec.url,
                priority=0,
                idempotency_key=key,
            )
            if placed:
                jobs.append((job_id, rec))
            else:
                result.deduped_jobs += 1

        # ── Узлы 4-8 по каждому заданию ──
        blocks_touched: set[str] = set()
        for job_id, rec in jobs:
            block = _BLOCK_BY_DOC_TYPE.get(rec.doc_type, "fundamentals")
            closed, stored, suspects = self._run_job(
                job_id, rec, block, instrument_id, issuer_id,
                provider_name, provider, result)
            result.jobs_done += closed
            result.facts_stored += stored
            result.suspects += suspects
            if stored or suspects:
                blocks_touched.add(block)

        # ── Узел 9: cascade — зависимые блоки помечаются stale ──
        if blocks_touched:
            for block in blocks_touched:
                for dep in _CASCADE_DEPENDENTS:
                    self._repos.job.coverage_upsert(
                        instrument_id, dep, "stale",
                        f"cascade:after_{block}")

        return result

    def _run_job(self, job_id: str, rec: IndexRecord, block: str,
                 instrument_id: str, issuer_id: str, provider_name: str,
                 provider: object, result: PipelineResult) -> tuple[int, int, int]:
        """Один документ: fetch -> store_raw -> parse -> validate -> persist.
        Возвращает (заданий закрыто, фактов записано, suspect-фактов)."""
        self._repos.job.claim(job_id)

        # ── Узел 4: fetch (E2/E3) ──
        doc: FetchedDocument | None = None
        for attempt in range(1, self._max_attempts + 1):
            outcome = provider.fetch_document(rec.url)
            if isinstance(outcome, FetchedDocument):
                doc = outcome
                break
            self._sleep(2.0 ** attempt)  # уважение паузе источника
        if doc is None:
            # E3: повторители исчерпаны — dead-letter с причиной, coverage=error.
            self._repos.job.fail(job_id, "E3:fetch_failed", retry=False)
            self._repos.job.coverage_upsert(
                instrument_id, block, "error",
                f"E3:fetch_failed:{rec.url}")
            result.fetch_failures += 1
            return 0, 0, 0

        # ── Узел 5: store_raw; дубль sha256 — закрыть без парсинга (I7) ──
        if self._repos.raw.has(doc.sha256):
            self._repos.job.finish(job_id)
            result.duplicates += 1
            return 1, 0, 0
        obj = self._repos.raw.put(
            doc.content, provider=provider_name, url=doc.url,
            instrument_id=instrument_id, block=block,
            content_type=doc.content_type)

        # ── Узел 6: parse (E4) ──
        metadata = {
            "content_type": doc.content_type,
            "doc_type": rec.doc_type,
            "doc_kind": _peek_doc_kind(doc.content),
        }
        context = {"issuer_id": issuer_id, "source_ref": obj.sha256}
        parsed = parse_auto(doc.content, metadata, context)
        if parsed is None:
            # E4: сырьё сохранено; задание — needs_verification, блок —
            # missing с причиной, не молчаливый пропуск.
            self._repos.job.fail(job_id, "E4:needs_verification", retry=False)
            self._repos.job.coverage_upsert(
                instrument_id, block, "missing",
                f"needs_verification:{obj.sha256}")
            result.needs_verification += 1
            return 0, 0, 0

        # ── Узел 7: validate; не прошедшие пишутся как suspect (E5) ──
        getter = self._repos.raw.get
        fact_dicts: list[dict] = []
        suspects = 0
        unmapped = 0
        for f in parsed.facts:
            fact = dict(f)
            fact["fact_id"] = str(uuid4())
            if _validate_fact(fact, getter):
                fact["status"] = "suspect"
                suspects += 1
            unmapped += apply_concept_map(fact)
            fact_dicts.append(fact)
        result.unmapped_concepts += unmapped

        # ── Узел 8: persist — факты + coverage одной транзакцией ──
        if not fact_dicts:
            # Разобрано, но ничего не извлечено — пустой разбор, объект
            # помечается как удаляемый при facts_only (I13 его не защищает).
            self._repos.job.fail(job_id, "E4:empty_parse", retry=False)
            self._repos.job.coverage_upsert(
                instrument_id, block, "missing",
                f"empty_parse:{obj.sha256}")
            return 0, 0, 0
        # У coverage нет статуса «частично»: проблема живёт в reason
        # (suspect-факты в расчёты не попадают, но из вида не пропадают).
        coverage_status = "ready"
        coverage_reason = None
        if suspects:
            coverage_reason = f"suspect:{suspects}"
        elif parsed.unparsed:
            coverage_reason = f"unparsed:{parsed.unparsed}"
        persist_ingestion_results(
            self._repos.conn, fact_dicts,
            [(instrument_id, block, coverage_status, coverage_reason)])
        self._repos.job.finish(job_id)
        return 1, len(fact_dicts), suspects

    def prune_unparsed(self, policy: str = "facts_only") -> PruneResult:
        """Очистка объектов без фактов. policy='facts_only': объекты с пометкой
        needs_verification в coverage не удаляются никогда — неразобранное
        остаётся на месте (I13). Файлы и манифест не трогаются: убирается
        только запись индекса."""
        result = PruneResult()
        if policy != "facts_only":
            raise ValueError(f"unknown prune policy: {policy}")
        rows = self._repos.raw.objects_without_facts()
        for sha, block, instrument_id in rows:
            cov = self._repos.job.get_coverage(instrument_id, block)
            reason = (cov or {}).get("reason") or ""
            if "needs_verification" in reason:
                result.kept_needs_verification += 1
                continue
            self._repos.raw.delete_index_entry(sha)
            result.deleted_without_facts += 1
        return result
