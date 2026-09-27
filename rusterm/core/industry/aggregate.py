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

ТЗ-97 Q8 (решение пользователя 24.09): окно разрыва концов периодов
участников — 2 года (INDUSTRY_PERIOD_WINDOW_DAYS), прежний порог ТЗ-22
J3 в 100 дней отменял агрегат всего сектора из-за одного другого
финансового года. Теперь участник вне окна исключается с пометкой
(excluded + счётчик причин), а остальные считаются; строка агрегата
несёт диапазон периодов включённых («периоды от … до …»).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field, replace

from rusterm.core.peers import (AGGREGATE_MIN_PEERS, currency_bound,
                                currency_guard, period_window)

METHOD_VERSION = "industry.v1"

_VERIFIED_ORIGINS = ("manual", "catalog")


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
    # валюта, в которой заявлены квартили; None — мера безразмерна
    # (ratio) или набор легаси-легаси без записанной валюты (ТЗ-21 H3)
    currency: str | None = None
    # причины, по которым участники не внесли вклад: причина -> счётчик
    reason_counts: dict = field(default_factory=dict)
    # ТЗ-97 Q8: диапазон концов периодов включённых участников и кто
    # остался вне окна (instrument_id -> period_end)
    period_from: str | None = None
    period_to: str | None = None
    excluded: dict = field(default_factory=dict)
    # ТЗ-102 M4: сколько участников дошло до расчёта этой меры и у
    # скольких из них значение есть. Без этих двух чисел отказ
    # `peer_set_too_small` неотличим от тощего набора, а `n` на отказе
    # всегда нуль.
    members_seen: int = 0
    with_value: int = 0


def _with_window(agg: AggregateMeasure, window) -> AggregateMeasure:
    """Окно периодов — часть строки, а не только расчёта: отказ тоже
    обязан называть диапазон и исключённых, иначе «почему тут пусто»
    приходится угадывать по составу набора."""
    counts = dict(agg.reason_counts)
    if window.excluded:
        counts["period_out_of_window"] = len(window.excluded)
    return replace(agg, period_from=window.period_from,
                   period_to=window.period_to,
                   excluded=dict(window.excluded), reason_counts=counts)


def period_note(agg: AggregateMeasure) -> str:
    """«периоды от … до …» и кто вне окна — одной формулировкой для
    `rusterm industry`, экрана «Отрасль» и вкладки Qt: пользователь не
    должен выбирать, где ему поверят (ТЗ-97 Q8)."""
    parts = []
    if agg.period_from and agg.period_to:
        parts.append(f"периоды от {agg.period_from} до {agg.period_to}")
    if agg.excluded:
        parts.append("вне окна: " + ", ".join(
            f"{iid} ({end})" for iid, end in sorted(agg.excluded.items())))
    return "; ".join(parts)


def shortfall_note(agg: AggregateMeasure) -> str:
    """Чем именно «мало участников»: составом набор или пустыми значениями.

    Нехватка состава (участников меньше порога) фразы не получает — там
    отказ честный и другой текст был бы оправданием. Фраза звучит только
    когда участников столько, сколько нужно, а мера доехала не до всех
    (ТЗ-102 M4)."""
    if agg.null_reason != "peer_set_too_small":
        return ""
    if agg.members_seen < AGGREGATE_MIN_PEERS:
        return ""
    return (f"участников {agg.members_seen}, значение меры есть у "
            f"{agg.with_value}")


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
            reason_counts=reason_counts,
            members_seen=len(values), with_value=len(contributing))

    q1, q2, q3 = statistics.quantiles(contributing, n=4, method="inclusive")
    return AggregateMeasure(
        concept=concept,
        p25=repr(q1), median=repr(q2), p75=repr(q3),
        n=len(contributing),
        reason_counts=reason_counts)


def build_sector_aggregates(repos, peer_set_id: str, as_of: str,
                            concepts: tuple[str, ...]) -> dict:
    """Сборка агрегатов сектора на дату (TASK-17 E2): версия набора и
    снапшоты участников выбираются ПО ДАТЕ, не фильтрацией после.
    Возвращает исход значением; SQL остаётся в репозиториях."""
    version = repos.peer_set.version_at(peer_set_id, as_of)
    if version is None:
        return {"outcome": "not_found", "peer_set_id": peer_set_id,
                "as_of": as_of}
    verified = version["origin"] in _VERIFIED_ORIGINS or version["approved"]
    members = repos.peer_set.member_snapshots_at(
        version["peer_set_version_id"], as_of)

    aggregates: list[AggregateMeasure] = []
    no_snapshot = sum(1 for sid in members.values() if sid is None)
    for concept in concepts:
        values: list[tuple[str, float | None]] = []
        member_measures: dict[str, str] = {}
        period_ends: dict[str, str] = {}
        for iid in sorted(members):
            sid = members[iid]
            if sid is None:
                values.append((iid, None))
                continue
            row = next(
                (m for m in repos.snapshot.get_measures(sid)
                 if m[3] == concept), None)
            value = None if row is None or row[4] is None \
                else float(row[4])
            if row is not None:
                member_measures[iid] = row[0]
                if row[7]:
                    period_ends[iid] = row[7]
            values.append((iid, value))
        # ТЗ-97 Q8: окно периодов — 2 года; участник старше самого
        # свежего вне окна исключается с пометкой и в расчёт не входит
        # (ни значением, ни валютой, ни причиной no_value)
        window = period_window(period_ends)
        if window.excluded:
            values = [pair for pair in values
                      if pair[0] not in window.excluded]
        # ТЗ-21 H3: агрегат несёт валюту, в которой заявлен; смешение
        # валют абсолютной меры — currency_mismatch с перечнем.
        # ТЗ-103 N2: валюта приходит только от участников СО ЗНАЧЕНИЕМ:
        # отказная строка меры не вносит в сравнение ни числа, ни
        # валюты, иначе набор из одних отказов отказывался по валютам,
        # которых в сравнении не было вовсе (отчётная причина —
        # `peer_set_too_small`, ТЗ-102 M4).
        currencies: set[str] = set()
        for iid, v in values:
            mid = member_measures.get(iid) if v is not None else None
            if mid:
                currencies |= repos.snapshot.currencies_for_measure(mid)
        guard = currency_guard(concept, currencies)
        if guard is not None:
            aggregates.append(_with_window(AggregateMeasure(
                concept=concept, p25=None, median=None, p75=None,
                n=len([v for _, v in values if v is not None]),
                null_reason=guard), window))
            continue
        agg = sector_aggregate(concept, values, verified=verified)
        # одновалютный абсолютный агрегат заявляет свою валюту
        present = sorted(c.strip().upper() for c in currencies if c)
        if currency_bound(concept) and len(present) == 1:
            agg = AggregateMeasure(
                concept=agg.concept, p25=agg.p25, median=agg.median,
                p75=agg.p75, n=agg.n, null_reason=agg.null_reason,
                method_version=agg.method_version, currency=present[0],
                reason_counts=agg.reason_counts,
                members_seen=agg.members_seen, with_value=agg.with_value)
        if no_snapshot:
            reason_counts = dict(agg.reason_counts)
            reason_counts["no_snapshot_at_date"] = no_snapshot
            agg = AggregateMeasure(
                concept=agg.concept, p25=agg.p25, median=agg.median,
                p75=agg.p75, n=agg.n, null_reason=agg.null_reason,
                method_version=agg.method_version,
                reason_counts=reason_counts,
                members_seen=agg.members_seen, with_value=agg.with_value)
        aggregates.append(_with_window(agg, window))
    return {"outcome": "resolved",
            "peer_set_id": peer_set_id,
            "peer_set_version_id": version["peer_set_version_id"],
            "version": version["version"],
            "verified": verified,
            "as_of": as_of,
            "members": members,
            "aggregates": aggregates}


def sector_concentration(repos, sector: str, as_of: str,
                         concept: str = "revenue") -> dict:
    """Концентрация сектора (ТЗ-24 N7): hhi по долям выручки участников
    на дату — та же машина версий, что у M7: peer set и снапшоты
    выбираются ПО ДАТЕ, поэтому новый сбор не переписывает прошлое.

    Валютная дисциплина H3: доли суммы, смешивающей воны и доллары,
    бессмысленны — смешанный сектор даёт currency_mismatch, никакого
    пересчёта курсов (ADR-0014 §4). Возвращаемое несёт валюту, в
    которой считало, число участников и отказ по имени.
    """
    from rusterm.formulas import hhi
    version = repos.peer_set.version_at(sector, as_of)
    if version is None:
        return {"value": None, "reason": "no_version_at_date",
                "currency": None, "n": 0, "members": []}
    members = repos.peer_set.member_snapshots_at(
        version["peer_set_version_id"], as_of)
    values: list[tuple[str, float]] = []
    currencies: set[str] = set()
    for iid in sorted(members):
        sid = members[iid]
        if sid is None:
            continue
        row = next((m for m in repos.snapshot.get_measures(sid)
                    if m[3] == concept), None)
        if row is None or row[4] is None:
            continue
        try:
            values.append((iid, float(row[4])))
        except (TypeError, ValueError):
            continue
        if row[5]:
            currencies.add(row[5].strip().upper())
    if not values:
        return {"value": None, "reason": "no_contributors",
                "currency": None, "n": 0,
                "members": sorted(members)}
    if len(currencies) > 1:
        pair = sorted(currencies)
        return {"value": None,
                "reason": f"currency_mismatch: {pair[0]}, {pair[1]}",
                "currency": None, "n": len(values),
                "members": [iid for iid, _ in values]}
    total = sum(v for _, v in values)
    shares = [v / total for _, v in values]
    value, reason = hhi(shares)
    currency = next(iter(currencies)) if len(currencies) == 1 else None
    return {"value": value, "reason": reason, "currency": currency,
            "n": len(values), "members": [iid for iid, _ in values]}
