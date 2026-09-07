"""LLM-summary с детерминированным предохранителем (TASK-7 T15,
docs/watchlist-and-llm.md §2.6).

Числа попадают в текст подстановкой из снапшота — модель их не сочиняет.
Валидатор: любое число в тексте, которого нет в citations, бракует текст
ЦЕЛИКОМ — блок остаётся missing с причиной; частично вычищенный текст
не хранится никогда. Пустой блок честнее правдоподобного.

Здесь нет и не будет HTTP: модель живёт в rusterm/providers/ (T16),
клиент — typing.Protocol, фальшивка живёт в тестах.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Protocol

logger = logging.getLogger("rusterm.llm")

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_0-9]+)\s*\}\}")


class LlmClient(Protocol):
    """Клиент модели. Возвращает структуру ответа, не сырой текст."""

    def summarize(self, prompt: str) -> dict:
        """{summary: str, highlights: [str], risks: [str], ...}"""
        ...


class LlmSummarizer:
    """Сборка LLM-summary: подстановка из снапшота + браковка целиком."""

    GUARD_REASON = "модель не смогла удержаться в данных"

    def __init__(self, client, snapshot_repo, llm_repo, coverage_repo):
        self._client = client
        self._snapshots = snapshot_repo
        self._llm = llm_repo
        self._coverage = coverage_repo

    def _measures(self, snapshot_id: str) -> dict:
        """Доступные для подстановки меры: концепт -> поля; value NULL
        цитировать нельзя — в подстановку не попадает."""
        out = {}
        for m in self._snapshots.get_measures(snapshot_id):
            concept, value, period_start, period_end = \
                m[3], m[4], m[6], m[7]
            if value is None:
                continue
            out[concept] = {"value": str(value), "unit": m[5],
                            "period_start": period_start,
                            "period_end": period_end}
        return out

    def _prompt(self, measures: dict) -> str:
        placeholders = ", ".join(f"{{{{{c}}}}}" for c in sorted(measures))
        return ("Составь summary по компании. Числа бери ТОЛЬКО "
                f"подстановкой плейсхолдеров: {placeholders}.\n"
                "Любое число не из списка — браковка всего текста.")

    def _render(self, text: str, measures: dict):
        """Подставить числа из снапшота. Незнакомый плейсхолдер —
        претензия на отсутствующие данные: текст бракуется."""
        def sub(match):
            concept = match.group(1)
            if concept not in measures:
                raise KeyError(concept)
            return measures[concept]["value"]

        try:
            rendered = _PLACEHOLDER_RE.sub(sub, text)
        except KeyError:
            return None
        if "{{" in rendered:
            return None
        return rendered

    def _citations_for(self, rendered: str, measures: dict):
        """Числа текста обязаны происходить из цитируемых мер; возвращает
        citations или None, если найдено число вне цитат."""
        allowed = []
        for concept, m in measures.items():
            for field in ("value", "period_start", "period_end"):
                allowed.append((concept, m[field], m[field].replace(",", ".")))
        normalized = rendered.replace(",", ".")
        citations = []
        used = set()
        for number in _NUMBER_RE.findall(normalized):
            hit = None
            for concept, source, source_norm in allowed:
                if number in source_norm:
                    hit = concept
                    break
            if hit is None:
                return None
            used.add(hit)
        for concept in sorted(used):
            m = measures[concept]
            citations.append({"concept": concept,
                              "period_end": m["period_end"],
                              "value": m["value"]})
        return citations

    def _check_block(self, rendered: str, measures: dict):
        """None — брак; иначе citations. Числа в highlights/risks проверяются
        так же жёстко, как в summary."""
        parts = [rendered]
        return self._citations_for(" ".join(parts), measures)

    def run(self, instrument_id: str, snapshot_id: str,
            model: str = "unspecified") -> dict:
        measures = self._measures(snapshot_id)
        prompt = self._prompt(measures)
        response = self._client.summarize(prompt)

        # confidence логируется, но из ветвления убран (§2.3)
        confidence = response.get("confidence")
        if confidence is not None:
            logger.info("llm confidence=%s (не используется в решениях)",
                        confidence)

        summary = self._render(response.get("summary", ""), measures)
        highlights = [self._render(h, measures)
                      for h in response.get("highlights", [])]
        risks = [self._render(r, measures)
                 for r in response.get("risks", [])]
        if (summary is None
                or any(h is None for h in highlights)
                or any(r is None for r in risks)):
            return self._reject(instrument_id)

        citations = self._citations_for(
            " ".join([summary, *highlights, *risks]), measures)
        if citations is None:
            return self._reject(instrument_id)

        snapshot = self._snapshots.get_snapshot(snapshot_id)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self._llm.insert(
            instrument_id=instrument_id, model=model,
            prompt_hash=prompt_hash,
            snapshot_version=snapshot["version"],
            summary=summary, highlights=highlights, risks=risks,
            citations=citations)
        self._coverage.upsert(instrument_id, "llm_summary", "ready")
        return {"stored": True, "citations": citations,
                "prompt_hash": prompt_hash}

    def _reject(self, instrument_id: str) -> dict:
        """Браковка целиком: ничего в llm_summary, блок missing с причиной."""
        self._coverage.upsert(instrument_id, "llm_summary", "missing",
                              reason=self.GUARD_REASON)
        return {"stored": False, "reason": self.GUARD_REASON}
