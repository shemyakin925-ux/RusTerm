"""История мер по финансовым годам (ТЗ-107 V1).

Окно показывает колонку года только там, где есть снапшот с мерами за
этот год. Обычная сборка строит снапшот «на сегодня», поэтому у бумаги
была одна колонка — год запуска. Здесь — пересборка: по одному снапшоту
на конец каждого финансового года из уже лежащих в базе фактов, без
сети. Дата сборки — конец года: дверь `as_of` построителя не пускает
периоды, закончившиеся позже, так что год видит только свои данные.

Правила:
- уже построенный год не строится заново (повтор ничего не добавляет);
- если построен хоть один год, последним пересобирается текущий
  снапшот: «сейчас» в окне — последняя версия, и она не должна
  оказаться прошлогодней.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_YEARS = 10


@dataclass
class HistoryResult:
    instrument_id: str
    built: list = field(default_factory=list)     # концы лет, собранные сейчас
    skipped: list = field(default_factory=list)   # уже были
    current_rebuilt: bool = False


def build_history(repos, instrument_id: str, issuer_id: str,
                  years: int = DEFAULT_YEARS,
                  today: Optional[str] = None,
                  rebuild: bool = False,
                  rebuild_current: bool = True) -> HistoryResult:
    from rusterm.core.snapshot import make_snapshot_builder

    today = today or _dt.date.today().isoformat()
    result = HistoryResult(instrument_id)
    have = {s["as_of"] for s in
            repos.snapshot.snapshots_of_instrument(instrument_id)}
    ends = [e for e in repos.snapshot.annual_period_ends(issuer_id)
            if e <= today][:max(years, 0)]
    for end in sorted(ends):
        # PRODUCT.md С2: rebuild пересобирает год текущим кодом — новая
        # версия снапшота побеждает старую в истории (старшая версия
        # года), снапшоты, собранные прежними правилами, не держат дыры
        if end in have and not rebuild:
            result.skipped.append(end)
            continue
        make_snapshot_builder(repos, end).build(instrument_id, issuer_id,
                                                end)
        result.built.append(end)
    # rebuild_current=False — вызывающий сам строит текущий снапшот следом
    # (follow: стадия «снапшот» идёт после истории, иначе два снапшота
    # на одну дату и две датированные оценки governance)
    if result.built and rebuild_current:
        make_snapshot_builder(repos, today).build(instrument_id, issuer_id,
                                                  today)
        result.current_rebuilt = True
    return result
