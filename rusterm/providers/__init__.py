"""Провайдеры: MarketDataProvider, DisclosuresProvider. Не пишут в базу (I10).

Реестр провайдеров: имена -> фабрики. Провайдер получает имя и возвращает
экземпляр; ошибка неизвестного имени возвращается значением, как и все
ошибки провайдеров.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .disclosures import DisclosuresProvider, SyntheticDisclosuresProvider
from .market import MarketDataProvider, SyntheticMarketProvider


@dataclass(frozen=True)
class UnknownProvider:
    """Неизвестное имя провайдера — ошибка значением, не исключение."""
    name: str


# Фабрики, а не экземпляры: у провайдера может быть своё состояние.
_FACTORIES: dict[str, Callable[[], object]] = {
    "synthetic-market": SyntheticMarketProvider,
    "synthetic-disclosures": SyntheticDisclosuresProvider,
}


def register(name: str, factory: Callable[[], object]) -> None:
    """Добавить провайдера в реестр. Повторная регистрация заменяет фабрику."""
    _FACTORIES[name] = factory


def get_provider(name: str):
    """Экземпляр провайдера по имени; UnknownProvider, если имени нет."""
    factory = _FACTORIES.get(name)
    if factory is None:
        return UnknownProvider(name)
    return factory()


def available() -> list[str]:
    """Имена зарегистрированных провайдеров, по алфавиту."""
    return sorted(_FACTORIES)


__all__ = [
    "DisclosuresProvider", "SyntheticDisclosuresProvider",
    "MarketDataProvider", "SyntheticMarketProvider",
    "UnknownProvider", "register", "get_provider", "available",
]
