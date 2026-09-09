"""Агрегат по сектору — чистая функция (TASK-17 E1, веха M7,
docs/quality-and-observability.md §5, data-model.md §5).

На вход: имя меры и список (instrument_id, value | None). На выход:
p25 / median / p75 / n — и ничего больше. Среднее, взвешивание и
составной счёт запрещены документом: медиана не даёт одному выбросу
говорить за весь сектор.

Метод квартилей: statistics.quantiles(method="inclusive") — линейная
интерполяция между порядковыми статистиками. Метод назван здесь,
потому что перцентиль без названного метода не воспроизводим между
двумя читателями, тем более между двумя версиями.

Null исключается и считается (ruling 2): участник с пустым значением
не вносит вклад никуда, кроме счётчика причин. Меньше
AGGREGATE_MIN_PEERS вкладчиков — агрегата нет: null с причиной
peer_set_too_small (I6). Не подтверждённый набор —
peer_set_not_confirmed: решение о верифицированности принимает
вызывающая сторона, эта функция знает только значения.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from rusterm.core.peers import AGGREGATE_MIN_PEERS

METHOD_VERSION = "industry.v1"


@dataclass(frozen=True)
class AggregateMeasure:
    """Результат по одной мере: три квартиля и n — либо null с причиной
    (I4: null обязан причиной)."""
    concept: str
    p25: str | None = None
    median: str | None = None
    p75: str | None = None
    n: int = 0
    null_reason: str | None = None
    method_version: str = METHOD_VERSION
    # причины, по которым участники не внесли вклад: причина -> счётчик
    reason_counts: dict = field(default_factory=dict)


def sector_aggregate(concept: str, values: list[tuple[str, float | None]],
                     verified: bool = True) -> AggregateMeasure:
    """Медиана и два квартиля по вкладчикам, n — число вкладчиков.

    values — (instrument_id, value | None); None не превращается в ноль
    и не участвует ни в чём, кроме счётчика причин no_value.
    """
    reason_counts: dict[str, int] = {}
    contributing: list[float] = []
    for _instrument_id, value in values:
        if value is None:
            reason_counts["no_value"] = reason_counts.get("no_value", 0) + 1
            continue
        contributing.append(float(value))

    if not verified:
        return AggregateMeasure(
            concept=concept, n=0,
            null_reason="peer_set_not_confirmed",
            reason_counts=reason_counts)
    if len(contributing) < AGGREGATE_MIN_PEERS:
        return AggregateMeasure(
            concept=concept, n=0,
            null_reason="peer_set_too_small",
            reason_counts=reason_counts)

    q1, q2, q3 = statistics.quantiles(contributing, n=4, method="inclusive")
    return AggregateMeasure(
        concept=concept,
        p25=repr(q1), median=repr(q2), p75=repr(q3),
        n=len(contributing),
        reason_counts=reason_counts)
