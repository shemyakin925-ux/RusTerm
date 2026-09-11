"""MarketDataProvider — протокол котировок и профилей (module-contracts.md §2).

Границы слоя: HTTP может жить только здесь; слой хранилища провайдеру
запрещён (I10); ни одна операция не бросает исключение наружу — ошибка
возвращается значением (ProviderError).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .base import ProviderError

# Рынок — строка спецификации (data-model.md §1: listing.exchange — строка).
# Рынок РФ исключён из проекта коммитом b1125ba; MOEX не используется.
Market = str

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@dataclass(frozen=True)
class ResolveMatch:
    instrument_id: str


@dataclass(frozen=True)
class ResolveAmbiguous:
    """Несколько кандидатов — выбор наугад запрещён (ADR-0005)."""
    candidates: tuple


@dataclass(frozen=True)
class ResolveNotFound:
    ticker: str
    market: str
    as_of: str


ResolveOutcome = ResolveMatch | ResolveAmbiguous | ResolveNotFound | ProviderError


@dataclass(frozen=True)
class ProfileResult:
    instrument_id: str
    data: dict


@dataclass(frozen=True)
class PriceRow:
    date: str
    close: float
    adjusted: float


@dataclass(frozen=True)
class PriceSeries:
    listing_id: str
    rows: tuple  # tuple[PriceRow, ...]


@dataclass(frozen=True)
class Candidates:
    """Кандидаты отрасли/индекса: это кандидаты, не члены peer set."""
    items: tuple


class MarketDataProvider(Protocol):
    """Протокол по module-contracts.md §2. Реализации не наследуются:
    достаточно совпадения методов (typing.Protocol)."""

    def resolve(self, ticker: str, market: Market, as_of: str) -> ResolveOutcome:
        """Разрешение тикера к instrument_id. Без даты запрещено (ADR-0005)."""
        ...

    def profile(self, instrument_id: str) -> ProfileResult | ProviderError:
        """Сырой профиль: сырьё для парсера, не факты."""
        ...

    def prices(self, listing_id: str, start: str, end: str) -> PriceSeries | ProviderError:
        """Цены за диапазон. Обязан отдавать и close, и adjusted."""
        ...

    def industry_members(self, industry: str,
                         filters: dict | None = None) -> Candidates | ProviderError:
        """Кандидаты отрасли."""
        ...

    def index_members(self, index: str) -> Candidates | ProviderError:
        """Кандидаты индекса либо ETF."""
        ...


class SyntheticMarketProvider:
    """Фейковый провайдер на синтетических фикстурах
    fixtures/synthetic_market_profile.json. Все данные выдуманы;
    только для тестов И6-И8."""

    source_name = "synthetic"

    def __init__(self, fixture_path: Path | None = None):
        path = fixture_path or (_FIXTURES / "synthetic_market_profile.json")
        with open(path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    def resolve(self, ticker: str, market: Market, as_of: str) -> ResolveOutcome:
        # Разрешение без даты запрещено (ADR-0005); пустая дата — ошибка значением.
        if not as_of:
            return ProviderError("resolve_without_date")
        ambiguous = self._data.get("ambiguous", {})
        if ticker in ambiguous:
            return ResolveAmbiguous(tuple(ambiguous[ticker]))
        inst = self._data.get("instruments", {}).get(ticker)
        if inst is None:
            return ResolveNotFound(ticker=ticker, market=market, as_of=as_of)
        return ResolveMatch(inst["instrument_id"])

    def profile(self, instrument_id: str) -> ProfileResult | ProviderError:
        data = self._data.get("profiles", {}).get(instrument_id)
        if data is None:
            return ProviderError(f"profile_not_found:{instrument_id}")
        return ProfileResult(instrument_id=instrument_id, data=dict(data))

    def prices(self, listing_id: str, start: str, end: str) -> PriceSeries | ProviderError:
        rows = self._data.get("prices", {}).get(listing_id)
        if rows is None:
            return ProviderError(f"listing_not_found:{listing_id}")
        selected = tuple(
            PriceRow(date=r["date"], close=float(r["close"]),
                     adjusted=float(r["adjusted"]))
            for r in rows
            if start <= r["date"] <= end
        )
        return PriceSeries(listing_id=listing_id, rows=selected)

    def industry_members(self, industry: str,
                         filters: dict | None = None) -> Candidates | ProviderError:
        items = [
            {"instrument_id": iid, "data": dict(p)}
            for iid, p in self._data.get("profiles", {}).items()
            if p.get("industry") == industry
        ]
        return Candidates(tuple(items))

    def index_members(self, index: str) -> Candidates | ProviderError:
        members = self._data.get("index_members", {}).get(index)
        if members is None:
            return ProviderError(f"index_not_found:{index}")
        return Candidates(tuple(members))
