"""Отраслевые наборы аналогов обычным путём (ТЗ-73 T2, ADR-0002).

До этого модуля набор аналогов нельзя было завести ни одной командой:
в базе пользователя peer_set — 0 строк, и вкладка «Отрасль» не могла
наполниться ни при каких данных. Здесь — одна дверь записи.

Правила ADR-0002, которые дверь держит:
- набор — версионируемая сущность: новый состав — новая версия, старая
  закрывается датой, а не переписывается; две версии на одну дату
  невозможны (version_at на этом падает);
- происхождение обязательно: manual | catalog | classifier |
  llm_suggested;
- ``llm_suggested`` никогда не подтверждается сам — подтверждение
  пользователя записывается как ``manual``;
- тот же состав с тем же происхождением — не новая версия: перцентиль
  не должен «измениться», потому что кто-то повторил команду.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional

ORIGINS = ("manual", "catalog", "classifier", "llm_suggested")
METHOD_VERSION = "peers.v1"


@dataclass
class PeerSetResult:
    peer_set_id: str
    version: int
    created: bool          # False — состав не изменился, версии не прибавилось
    members: int
    closed_version: Optional[int] = None


class PeerSetRefused(ValueError):
    """Отказ словами: команда печатает его как есть."""


def set_industry_peers(repos, sector: str, instrument_ids: list[str],
                       origin: str, approved: bool, today: str,
                       criteria: Optional[dict] = None) -> PeerSetResult:
    if origin not in ORIGINS:
        raise PeerSetRefused(
            f"происхождение {origin!r} вне словаря ADR-0002: "
            f"{', '.join(ORIGINS)}")
    if origin == "llm_suggested" and approved:
        raise PeerSetRefused(
            "предложение модели не подтверждается само (ADR-0002): "
            "подтверждённый пользователем набор записывается с "
            "--origin manual")
    members = sorted(set(instrument_ids))
    if not members:
        raise PeerSetRefused("пустой набор аналогов не записывается")

    repos.peer_set.create_peer_set(sector, "industry", sector)
    current = repos.peer_set.open_version(sector)
    if current is not None and current["members"] == set(members) \
            and current["origin"] == origin \
            and current["approved"] == approved:
        return PeerSetResult(sector, current["version"], False, len(members))

    closed = None
    if current is not None:
        repos.peer_set.close_version(current["peer_set_version_id"], today)
        closed = current["version"]
    version = repos.peer_set.max_version_of(sector) + 1
    version_id = str(uuid.uuid4())
    repos.peer_set.add_version(
        version_id, sector, version, today, None, origin, METHOD_VERSION,
        approved, time.time() if approved else None, criteria)
    for iid in members:
        repos.peer_set.add_member(version_id, iid, f"origin:{origin}")
    return PeerSetResult(sector, version, True, len(members), closed)


def peer_inputs(repos, instrument_id: str,
                as_of: str) -> tuple[Optional[str], Optional[list]]:
    """Вход второго прохода снапшота (ТЗ-94 E2): версия набора аналогов
    бумаги на дату и величины участников из их последних снапшотов.

    До этого ни один рабочий вызов (snapshot, refresh, окно) не передавал
    набор построителю, и перцентили ADR-0002 считались только в тестах —
    на базе пользователя 0 строк. Возвращает (peer_set_version_id,
    [(peer_id, measure_id, concept, value, fresh)]) или (None, None),
    если бумага ни в одном наборе или у набора нет версии на дату.
    Сама бумага и чужие перцентили в величины аналогов не входят."""
    ps = repos.peer_set.peer_set_for_instrument(instrument_id)
    if ps is None:
        return None, None
    version = repos.peer_set.version_at(ps["peer_set_id"], as_of)
    if version is None:
        return None, None
    measures: list = []
    snapshots = repos.peer_set.member_snapshots_at(
        version["peer_set_version_id"], as_of)
    for peer_id, snapshot_id in snapshots.items():
        if peer_id == instrument_id or snapshot_id is None:
            continue
        for row in repos.snapshot.get_measures(snapshot_id):
            measure_id, concept, value = row[0], row[3], row[4]
            if concept == "percentile":
                continue
            measures.append((peer_id, measure_id, concept, value, True))
    return version["peer_set_version_id"], measures
