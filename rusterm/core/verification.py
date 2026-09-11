"""Процесс 5 — верификация факта и заземление истины (TASK-7 T8).

Пять узлов по docs/processes.md §263-284:
capture и store_ground_truth превращают ручную правку в пару фактов
(извлечённый не удаляется — получает superseded_by), recompute пересобирает
снапшоты, чей lineage ссылался на неверный факт, propose_golden добавляет
пару (сырьё, ожидаемое) в набор предложений, flag_parser считает
расхождения по (провайдер, концепт) за скользящие 30 дней: порог — 5,
после него парсер деградировавший, и это видно через coverage.reason.

Порог детерминирован и не настраивается.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

DEGRADE_THRESHOLD = 5          # расхождений по (провайдер, концепт)
DEGRADE_WINDOW_SECONDS = 30 * 24 * 3600   # скользящие 30 дней


class VerificationService:
    """Оркестрация узлов процесса 5 над репозиториями."""

    def __init__(self, fact_repo, verification_repo, snapshots_repo,
                 instrument_repo, golden_proposals_path: Path):
        self._facts = fact_repo
        self._verifications = verification_repo
        self._snapshots = snapshots_repo
        self._instruments = instrument_repo
        self._golden_path = Path(golden_proposals_path)

    # ── Узлы 1–2: capture + store_ground_truth ──────────────────────────

    def store_ground_truth(self, wrong_fact_id: str, value: str,
                           note: Optional[str] = None) -> str:
        """Ручной факт origin=manual поверх показанного; извлечённый
        остаётся и получает superseded_by. Возвращает id нового факта."""
        wrong = self._facts.get_fact(wrong_fact_id)
        if wrong is None:
            raise ValueError(f"факт {wrong_fact_id!r} не найден")
        if wrong["superseded_by"]:
            raise ValueError("факт уже superseded — правка не по верхнему")
        import uuid
        correct_id = str(uuid.uuid4())
        self._facts.insert_fact(
            fact_id=correct_id,
            issuer_id=wrong["issuer_id"],
            listing_id=wrong["listing_id"],
            concept=wrong["concept"],
            period_start=wrong["period_start"],
            period_end=wrong["period_end"],
            period_type=wrong["period_type"],
            value=value,
            unit=wrong["unit"],
            currency=wrong["currency"],
            basis=wrong["basis"],
            origin="manual",
            source_ref=wrong["source_ref"],   # ссылка на тот же документ
            locator=json.loads(wrong["locator"]),
            parser_version="manual",
            # правка того же концепта: каноническое имя наследуется,
            # иначе пересчёт не увидит ручной факт (TASK-9 V0)
            canonical_concept=wrong.get("canonical_concept"),
            concept_map_version=wrong.get("concept_map_version"),
        )
        self._facts.mark_superseded(wrong_fact_id, correct_id)
        self._verifications.capture(wrong_fact_id, correct_id, note)
        return correct_id

    # ── Узел 3: recompute ───────────────────────────────────────────────

    def recompute(self, wrong_fact_id: str, builder) -> list:
        """Пересобрать снапшоты инструментов, чьи меры ссылались на факт.
        builder — SnapshotBuilder; возвращает BuildResult каждой сборки."""
        results = []
        for instrument_id in self._snapshots.instruments_for_fact(wrong_fact_id):
            instrument = self._instruments.get_instrument(instrument_id)
            if instrument is None:
                continue
            results.append(builder.build(instrument_id,
                                         issuer_id=instrument.issuer_id,
                                         as_of=_today()))
        return results

    # ── Узел 4: propose_golden ──────────────────────────────────────────

    def propose_golden(self, verification_id: str) -> dict:
        """Добавить пару (сырьё, ожидаемое) в набор предложений golden-file
        (файл в каталоге данных приложения, не в git) и пометить строку."""
        pair = self._verifications.verification_pair(verification_id)
        if pair is None:
            raise ValueError(f"верификация {verification_id!r} не найдена")
        proposal = {
            "verification_id": pair["verification_id"],
            "raw_sha256": pair["raw_sha256"],
            "concept": pair["concept"],
            "period_end": pair["period_end"],
            "expected": pair["expected"],
            "shown": pair["shown"],
            "proposed_at": time.time(),
        }
        self._golden_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._golden_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(proposal, ensure_ascii=False) + "\n")
        self._verifications.promote_to_golden(verification_id)
        return proposal

    # ── Узел 5: flag_parser ─────────────────────────────────────────────

    def degraded_parsers(self, now: Optional[float] = None) -> list:
        """[(провайдер, концепт, счёт)] с расхождениями ≥ порога за окно."""
        now = time.time() if now is None else now
        out = []
        for provider, concept, n in self._verifications.mismatch_counts(
                now - DEGRADE_WINDOW_SECONDS):
            if n >= DEGRADE_THRESHOLD:
                out.append((provider, concept, n))
        return out

    def flag_parser(self, provider: str, concept: str,
                    now: Optional[float] = None) -> bool:
        """Узел 5 по имени из документа: деградировал ли (провайдер,
        концепт) — порог 5 за скользящие 30 дней. Детерминирован."""
        now = time.time() if now is None else now
        counted = 0
        for p, c, n in self._verifications.mismatch_counts(
                now - DEGRADE_WINDOW_SECONDS):
            if p == provider and c == concept:
                counted = n
        return counted >= DEGRADE_THRESHOLD

    def surface_coverage(self, instrument_id: str, coverage_repo) -> list:
        """Деградация парсера видна через coverage.reason, не только в логах:
        блок fundamentals получает error с причиной по каждому затронутому
        (провайдер, концепт) этого эмитента."""
        instrument = self._instruments.get_instrument(instrument_id)
        if instrument is None:
            return []
        reasons = []
        for provider, concept, n in self.degraded_parsers():
            if self._facts.count_for_issuer_concept(
                    instrument.issuer_id, concept):
                reason = (f"parser_degraded:{provider}:{concept}:"
                          f"mismatches={n}/{DEGRADE_THRESHOLD}")
                coverage_repo.upsert(instrument_id, "fundamentals",
                                     "error", reason=reason)
                reasons.append(reason)
        return reasons


def _today() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d")
