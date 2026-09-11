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
