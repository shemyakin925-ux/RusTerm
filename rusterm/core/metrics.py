"""Системные метрики — девять, из базы (TASK-7 T12,
docs/quality-and-observability.md §3).

Жёсткое правило: метрика не выдумывает значение. Нет входных строк —
метрика не записывается вовсе: отсутствие пробы и нуль — разные факты,
и второй врёт. Счётчики провайдера — реальные из RequestGate (T3),
не заглушки.
"""
from __future__ import annotations

import time
from typing import Optional

METRIC_NAMES = (
    "provider_success_rate",
    "provider_rate_limited",
    "data_lag",
    "suspect_share",
    "unparsed_share",
    "verification_queue",
    "peer_set_coverage",
    "peer_set_churn",
    "locator_resolve_failures",
)


class SystemMetrics:
    """Считает девять метрик; записывает только те, у кого есть данные."""

    def __init__(self, metrics_repo, request_gate=None):
        self._repo = metrics_repo
        # RequestGate из rusterm/providers/budget.py; None — провайдерских
        # метрик tonight нет и выдумывать их нельзя
        self._gate = request_gate

    def compute(self, now: Optional[float] = None) -> dict:
        now = time.time() if now is None else now
        values: dict[str, Optional[float]] = {name: None
                                              for name in METRIC_NAMES}

        # Провайдер: реальные счётчики гейта
        if self._gate is not None:
            made = self._gate.calls_made
            refused = self._gate.refused
            if made + refused > 0:
                values["provider_success_rate"] = made / (made + refused)
            if self._gate.rate_limited > 0 or made > 0:
                values["provider_rate_limited"] = float(
                    self._gate.rate_limited)

        # Запаздывание данных: сейчас минус свежайшее сырье
        last_fetch = self._repo.last_fetch_ts()
        if last_fetch is not None:
            values["data_lag"] = now - last_fetch

        # Доля suspect среди фактов
        statuses = self._repo.fact_status_counts()
        total_facts = sum(statuses.values())
        if total_facts:
            values["suspect_share"] = statuses.get("suspect", 0) / total_facts

        # Доля неразобранного сырья
        raw = self._repo.raw_counts()
        if raw["total"]:
            values["unparsed_share"] = raw["unparsed"] / raw["total"]

        # Очередь верификации: неподтверждённые в golden расхождения
        open_verifications = self._repo.verification_open_count()
        if open_verifications:
            values["verification_queue"] = float(open_verifications)

        # Покрытие peer set: доля инструментов в хоть каком peer set
        instruments = self._repo.instrument_counts()
        if instruments["total"]:
            values["peer_set_coverage"] = (
                instruments["with_peers"] / instruments["total"])

        # Churn peer set: симметрическая разность двух последних версий
        peer_sets = self._repo.last_two_peer_member_sets()
        if peer_sets is not None:
            prev, cur = peer_sets
            denom = max(len(prev), len(cur))
            if denom:
                changed = len(set(prev) ^ set(cur))
                values["peer_set_churn"] = changed / denom

        # Не разрешаемые локаторы
        locators = self._repo.locator_failures_and_total()
        if locators["total"]:
            values["locator_resolve_failures"] = (
                locators["failures"] / locators["total"])

        return values

    def record(self, values: dict, provider: str = "synthetic",
               ts: Optional[float] = None) -> int:
        """Записать пробы в metric_sample; None не пишется никогда.
        Возвращает число записанных проб."""
        ts = time.time() if ts is None else ts
        written = 0
        for name, value in values.items():
            if value is None:
                continue
            self._repo.record_sample(ts, name, provider, float(value))
            written += 1
        return written


def record_host_usage(repo, gate, ts: Optional[float] = None) -> int:
    """Счётчики RequestGate по хостам — в metric_sample (BACKLOG B24).
    Имя пробы provider_used_<хост>, колонка provider = хост; пишутся
    только тронутые пулы. Возвращает число записанных проб."""
    ts = time.time() if ts is None else ts
    written = 0
    for host, usage in sorted(gate.host_usage().items()):
        if usage["used"] == 0 and usage["refused"] == 0:
            continue
        repo.record_sample(ts, f"provider_used_{host}", host,
                           float(usage["used"]))
        written += 1
    return written
