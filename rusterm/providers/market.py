"""MarketDataProvider — протокол котировок и профилей.

Строгие запреты: только стандартная библиотека, HTTP только внутри rusterm/providers/.
Никаких ORM, асинхронных фреймворков, внешних зависимостей.
"""
from __future__ import annotations

from typing import Literal, Optional


InstrumentId = str
Market = Literal["MOEX", "NYSE", "NASDAQ", "ICE"]
Profile = dict[str, any]


class MarketDataProvider:
    """Протокол MarketDataProvider (module-contracts.md §2).

    Все методы возвращают либо валидные данные, либо явные маркеры ошибок
    (not_found, not_modified), никогда исключения.
    """

    def resolve(self, instrument_id: InstrumentId,
                market: Optional[Market] = None,
                date: Optional[str] = None) -> _listdict:
        """Разрешение тикера к instrument_id.

        Возвращает dict с полями:
        - instrument_id: str
        - ambiguous: list[str]  (варианты совпадения)
        - not_found: bool
        """
        raise NotImplementedError

    def profile(self, instrument_id: InstrumentId) -> _listdict:
        """Профиль эмитента.

        Возвращает dict с raw-объектом и метаданными.
        Не возвращает факты — только сырьё для парсера.
        """
        raise NotImplementedError

    def prices(self, listing_id: InstrumentId,
               start: str, end: str) -> _listdict:
        """Цены за диапазон дат.

        Обязан отдавать и close, и adjusted.
        Diff строится по close.
        """
        raise NotImplementedError

    def industry_members(self, industry: str,
                        filters: _listdict | None = None) -> _listdict:
        """Члены отрасли.

        Результат — кандидаты, не члены peer set.
        """
        raise NotImplementedError

    def index_members(self, index: str) -> _listdict:
        """Члены индекса/ETF.

        Результат — кандидаты.
        """
        raise NotImplementedError


class FakeMarketDataProvider(MarketDataProvider):
    """Фейковый MarketDataProvider на синтетических данных.

    Явно помечен как synthetic для отличия от реальных источников.
    Отдаёт poll_index и документы для тестирования инкрементов I6-I7.
    """

    # Индекс изменений для инкрементального poll_index
    _cursor: str = "0"
    # Кэш данных
    _cache: _listdict = {}

    def _set_cache(self, data: _listdict) -> None:
        """Установка кэша данных (для тестирования)."""
        self._cache = data

    # -- MarketDataProvider implementation --

    def resolve(self, instrument_id: InstrumentId,
                market: Optional[Market] = None,
                date: Optional[str] = None) -> _listdict:
        """Простое разрешение: возвращаем данные из кэша или not_found."""
        result = self._cache.get(instrument_id)
        if result is None:
            return {
                "instrument_id": instrument_id,
                "not_found": True,
                "ambiguous": [],
            }
        # Убеждаемся, что в результате есть instrument_id
        if "instrument_id" not in result:
            result["instrument_id"] = instrument_id
        return result

    def profile(self, instrument_id: InstrumentId) -> _listdict:
        """Возвращает профиль из кэша или базовый пустой."""
        result = self._cache.get(instrument_id, {})
        if not result:
            result = {
                "instrument_id": instrument_id,
                "ticker": instrument_id,
                "exchange": "MOEX",
                "sector": "unknown",
                "industry": "unknown",
            }
        if "instrument_id" not in result:
            result["instrument_id"] = instrument_id
        return result

    def prices(self, listing_id: InstrumentId,
               start: str, end: str) -> _listdict:
        """Возвращает цены из кэша."""
        result = self._cache.get(listing_id, {})
        if not result:
            # Возвращаем базовые цены по умолчанию
            result = {
                "listing_id": listing_id,
                "close": 0.0,
                "adjusted": 0.0,
                "start": start,
                "end": end,
            }
        if "listing_id" not in result:
            result["listing_id"] = listing_id
        return result

    def industry_members(self, industry: str,
                         filters: _listdict | None = None) -> _listdict:
        """Возвращает кандидатов отрасли."""
        result = self._cache.get(f"industry_{industry}", [])
        if not result:
            result = []
        if "instrument_id" not in str(result):
            # Гарантируем структуру
            if isinstance(result, list):
                result = [{"instrument_id": r} if isinstance(r, str) else r for r in result]
        return {"candidates": result}

    def index_members(self, index: str) -> _listdict:
        """Возвращает кандидатов индекса."""
        result = self._cache.get(f"index_{index}", [])
        if not result:
            result = []
        return {"candidates": result}
