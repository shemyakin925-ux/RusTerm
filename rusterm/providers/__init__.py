"""Провайдеры: MarketDataProvider, DisclosuresProvider. Не пишут в базу (I10).

Реестр провайдеров: имена -> фабрики. Провайдер получает имя и возвращает
экземпляр; ошибка неизвестного имени возвращается значением, как и все
ошибки провайдеров.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .base import ProviderError
from .budget import ConfigError, RequestGate
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

# Сетевые провайдеры: выдаются только с RequestGate (TASK-8 U5 —
# реестр делает обход лимитера невозможным, а не «на совести» автора).
_NETWORK_PROVIDERS: dict[str, Callable[[RequestGate], object]] = {
    "edgar": lambda gate: _edgar_provider(gate),
}


def _edgar_provider(gate: RequestGate):
    from .edgar import EdgarProvider
    return EdgarProvider(gate=gate)


def register(name: str, factory: Callable[[], object]) -> None:
    """Добавить провайдера в реестр. Повторная регистрация заменяет фабрику."""
    _FACTORIES[name] = factory


def get_provider(name: str, gate: RequestGate | None = None):
    """Экземпляр провайдера по имени.

    Неизвестное имя — UnknownProvider; сетевой провайдер без гейта —
    ConfigError-значение: обойти бюджет и лимитер нельзя ни одному
    сетевому провайдеру (TASK-7 T3, TASK-8 U5).
    """
    if name in _NETWORK_PROVIDERS:
        if gate is None:
            return ConfigError(
                reason=f"network_provider_requires_gate:{name}")
        return _NETWORK_PROVIDERS[name](gate)
    factory = _FACTORIES.get(name)
    if factory is None:
        return UnknownProvider(name)
    return factory()


def available() -> list[str]:
    """Имена зарегистрированных провайдеров, по алфавиту."""
    return sorted(set(_FACTORIES) | set(_NETWORK_PROVIDERS))


__all__ = [
    "DisclosuresProvider", "SyntheticDisclosuresProvider",
    "MarketDataProvider", "SyntheticMarketProvider",
    "UnknownProvider", "ProviderError", "ConfigError", "RequestGate",
    "register", "get_provider", "available",
]
