"""Peer set: пороги, статусы, дрейф (ADR-0002, data-model.md §5).

Инварианты, которые здесь живут:
- членов меньше пяти — перцентили по версии не рассчитываются (I6);
- меньше восьми — отраслевые агрегаты не считаются (I6);
- origin=classifier без подтверждения — набор unverified;
- peer_set_churn за проход больше 20% состава — снапшот suspect.
"""
from __future__ import annotations

from dataclasses import dataclass

PERCENTILE_MIN_PEERS = 5
AGGREGATE_MIN_PEERS = 8
DRIFT_SUSPECT_THRESHOLD = 0.20

# Происхождения по приоритету (ADR-0002): manual побеждает всегда;
# llm_suggested автоматически не применяется.
_VERIFIED_ORIGINS = ("manual", "catalog")


@dataclass(frozen=True)
class PeerSetStatus:
    size: int
    origin: str
    verified: bool
    can_percentile: bool
    can_aggregates: bool
    churn: float
    suspect: bool


def evaluate(origin: str, approved_by_user: bool,
             previous_members: list[str],
             current_members: list[str]) -> PeerSetStatus:
    """Статус версии набора: пороги, верифицированность, дрейф за проход.

    previous_members/current_members — списки instrument_id состава
    предыдущей и текущей версий.
    """
    size = len(current_members)
    verified = origin in _VERIFIED_ORIGINS or bool(approved_by_user)

    prev, cur = set(previous_members), set(current_members)
    added = len(cur - prev)
    removed = len(prev - cur)
    churn = ((added + removed) / size) if size else 0.0

    return PeerSetStatus(
        size=size,
        origin=origin,
        verified=verified,
        can_percentile=size >= PERCENTILE_MIN_PEERS,
        can_aggregates=size >= AGGREGATE_MIN_PEERS,
        churn=churn,
        suspect=churn > DRIFT_SUSPECT_THRESHOLD,
    )


def percentile_share(peer_values: list[float], own_value: float) -> float | None:
    """Доля пиров со значением строго меньше значения компании.

    Меньше PERCENTILE_MIN_PEERS пиров — перцентиль не считается (None),
    по общему правилу порога 5.
    """
    if len(peer_values) < PERCENTILE_MIN_PEERS:
        return None
    below = sum(1 for v in peer_values if v < own_value)
    return below / len(peer_values)


def aggregate_ready(peer_count: int) -> bool:
    """Отраслевые агрегаты считаются только от восьми пиров и больше."""
    return peer_count >= AGGREGATE_MIN_PEERS


# Валютно-связанные виды мер (formulas.MEASURE_UNIT_KINDS): смешение
# валют портит сравнение; ratio, count и index нейтральны.
_CURRENCY_BOUND_KINDS = frozenset({"money", "per_share"})


def currency_bound(concept: str) -> bool:
    """Абсолютна ли мера, то есть сравнима только внутри одной валюты.

    money и per_share из карты единиц — да. Концепта нет в карте —
    это вход as-reported (revenue, total_equity и прочие денежные
    факты карты V0): он тоже валютно-связан. Входных концептов вне
    денег карта V0 не знает, так что «неизвестен» здесь означает
    «денежный», а не «неизвестно» (ТЗ-21 H3).
    """
    from rusterm.formulas import MEASURE_UNIT_KINDS
    return MEASURE_UNIT_KINDS.get(concept) in _CURRENCY_BOUND_KINDS \
        or concept not in MEASURE_UNIT_KINDS


def currency_guard(concept: str, currencies: set[str]) -> str | None:
    """Валютный стоп-кран (ТЗ-21 H3; пустоты по правилу ТЗ-22 J1.0):
    причина для меры или None.

    Две и более различных НЕПУСТЫХ валют у входов абсолютной меры —
    currency_mismatch с перечнем валют в продолжении (тот же стиль,
    что missing_data у X3). С того коммита, где провайдеры начали
    записывать валюту (J1.0), пустая валюта — сторона смешения:
    набор из записанной валюты и пустот — currency_mismatch, а не
    молчаливое «та одна валюта»; набор из одних пустот (легаси) ведёт
    себя как раньше и никогда не подменяется USD. Ratio и count
    нейтральны.
    """
    if not currency_bound(concept):
        return None
    present = sorted({c.strip().upper() for c in currencies
                      if c and c.strip()})
    blanks = any(not (c and c.strip()) for c in currencies)
    if len(present) > 1 or (present and blanks):
        return "currency_mismatch: " + ", ".join(
            sorted(present + (["(blank)"] if blanks else [])))
    return None
