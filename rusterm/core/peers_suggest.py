"""ТЗ-144 G1: кандидаты в аналоги для компании из новой отрасли.

Компания, добавленная в базу, где нет никого с её SIC (REPORT-142 E3:
NVDA, KO, XOM, PFE, WMT), получала на «Аналогах» отказ. Здесь — кого
предложить: компании той же отрасли SIC из EDGAR, торгуемые на бирже США,
по убыванию выручки последнего собранного календарного года (frames).

Правило детерминировано: те же входы — тот же список. Выручка берётся
по тегу `Revenues`, при его отсутствии — по ASC-606; первый тег сильнее
(у Tigo Energy в ASC-606 подано в 1000 раз больше, чем в Revenues —
замер координатора 22.10). Сеть — только через провайдер (I9).
"""
from __future__ import annotations

from typing import Iterable, Optional

from rusterm.providers.base import ProviderError

REVENUE_TAGS = ("Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax")
US_VENUES = frozenset({"Nasdaq", "NYSE"})
LIMIT = 5


def rank_candidates(sic_ciks: Iterable[int], frames: list[dict],
                    listed: dict, exclude: Iterable[int] = (),
                    limit: int = LIMIT) -> list[dict]:
    """[{cik, ticker, name, revenue}] — до `limit` компаний отрасли.

    `frames` — словари {CIK: выручка} в порядке силы тегов (первый,
    у кого есть значение, побеждает); `listed` — {CIK: (тикер, имя,
    биржа)}. Компания без тикера на бирже США, без выручки или из
    `exclude` пропускается. Порядок — выручка по убыванию, затем тикер."""
    excluded = set(exclude)
    revenue: dict[int, float] = {}
    for frame in frames:
        for cik, value in frame.items():
            revenue.setdefault(int(cik), value)
    out = []
    for cik in dict.fromkeys(int(c) for c in sic_ciks):
        if cik in excluded or cik not in listed:
            continue
        ticker, name, venue = listed[cik]
        value = revenue.get(cik)
        if venue not in US_VENUES or not value or value <= 0:
            continue
        out.append({"cik": cik, "ticker": ticker, "name": name,
                    "revenue": value})
    out.sort(key=lambda c: (-c["revenue"], c["ticker"]))
    return out[:limit]


def suggest(provider, exclude_ciks: Iterable[int], year: int,
            limit: int = LIMIT) -> dict | ProviderError:
    """Подсказка для эмитента провайдера (`provider.cik` задан):
    {sic, description, year, candidates}. Кадр года пуст — год назад.
    Отказ провайдера — значение (ProviderError/ConfigError)."""
    code = provider.sic_code()
    if not isinstance(code, tuple):
        return code
    sic, description = code
    ciks = provider.sic_ciks(sic)
    if not isinstance(ciks, list):
        return ciks
    listed = provider.listed_companies()
    if not isinstance(listed, dict):
        return listed
    frames: list[dict] = []
    used_year: Optional[int] = None
    for candidate_year in (year, year - 1):
        frames = []
        for tag in REVENUE_TAGS:
            frame = provider.revenue_frame(tag, candidate_year)
            if not isinstance(frame, dict):
                return frame
            frames.append(frame)
        if any(frames):
            used_year = candidate_year
            break
    return {"sic": sic, "description": description, "year": used_year,
            "candidates": rank_candidates(ciks, frames, listed,
                                          exclude=exclude_ciks,
                                          limit=limit)}
