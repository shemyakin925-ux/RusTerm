"""Провайдеры: MarketDataProvider, DisclosuresProvider. Не пишут в базу (I10).

Реестр провайдеров: имена -> фабрики. Провайдер получает имя и возвращает
экземпляр; ошибка неизвестного имени возвращается значением, как и все
ошибки провайдеров.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .base import ProviderError
from .budget import ConfigError, HostLimit, RequestGate
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

# Объявления сетевых провайдеров (TASK-19 F5, ADR-0010 §4). Темп — из
# живых замеров agent/REPORT-MARKETS.md: SEC 5/с (действует с ТЗ-7),
# DART 2/с, CVM 1/с (объёмные файлы), ASX 1/с, OTC 1/с (канал без
# договора — вежливый темп), LLM API 1/с. Ночной потолок — проектные
# 5000/хост до замера настоящих потолков: полоса TASK-20, строя модуль
# источника, уточняет число у себя. Реестр не выдаёт сетевого
# провайдера без объявления — та же дверь, что U5 (TASK-8), петля шире.
_HOST_LIMITS: dict[str, HostLimit] = {
    "edgar": HostLimit(host="data.sec.gov", per_second=5.0,
                       nightly_max=5000),
    "dart": HostLimit(host="opendart.fss.or.kr", per_second=2.0,
                      nightly_max=5000),
    "cvm": HostLimit(host="dados.cvm.gov.br", per_second=1.0,
                     nightly_max=5000),
    "asx": HostLimit(host="asx.api.markitdigital.com", per_second=1.0,
                     nightly_max=5000),
    "otcmarkets": HostLimit(host="backend.otcmarkets.com", per_second=1.0,
                            nightly_max=5000),
    "llm-api": HostLimit(host="openrouter.ai", per_second=1.0,
                         nightly_max=5000),
}

# Сетевые провайдеры: выдаются только с RequestGate (TASK-8 U5 —
# реестр делает обход лимитера невозможным, а не «на совести» автора).
# Места импортируют свой модуль ВНУТРИ вызова (ADR-0012 §2): после этой
# ночи ни одна полоса этот файл не трогает — полоса создаёт только свой
# модуль rusterm/providers/<имя>.py с build(gate), место уже здесь.
_NETWORK_PROVIDERS: dict[str, Callable[[RequestGate], object]] = {
    "edgar": lambda gate: _edgar_provider(gate),
    "dart": lambda gate: _seat_provider("dart", gate),
    "cvm": lambda gate: _seat_provider("cvm", gate),
    "asx": lambda gate: _seat_provider("asx", gate),
    "otcmarkets": lambda gate: _seat_provider("otcmarkets", gate),
    "llm-api": lambda gate: _seat_provider("llm_api", gate),
}


def _edgar_provider(gate: RequestGate):
    from .edgar import EdgarProvider
    return EdgarProvider(gate=gate)


def _seat_provider(module_name: str, gate: RequestGate):
    """Место провайдера: модуль импортируется только внутри вызова.
    Модуля нет — ConfigError-значение, а не ImportError (TASK-19 F5).
    Маскируется только отсутствие самого модуля: отсутствие его
    зависимости честно всплывает. Контракт модуля: build(gate)."""
    import importlib
    full = f"rusterm.providers.{module_name}"
    try:
        module = importlib.import_module(full)
    except ModuleNotFoundError as e:
        if e.name in (module_name, full):
            return ConfigError(
                reason=f"provider_not_implemented:{module_name}")
        raise
    build = getattr(module, "build", None)
    if build is None:
        raise TypeError(f"{full}.build(gate) обязателен (TASK-19 F5)")
    return build(gate)


def register(name: str, factory: Callable[[], object]) -> None:
    """Добавить провайдера в реестр. Повторная регистрация заменяет фабрику."""
    _FACTORIES[name] = factory


def get_provider(name: str, gate: RequestGate | None = None):
    """Экземпляр провайдера по имени.

    Неизвестное имя — UnknownProvider; сетевой провайдер без гейта —
    ConfigError-значение: обойти бюджет и лимитер нельзя ни одному
    сетевому провайдеру (TASK-7 T3, TASK-8 U5). Сетевой провайдер без
    объявления хоста не выдаётся вовсе (TASK-19 F5).
    """
    if name in _NETWORK_PROVIDERS:
        if name not in _HOST_LIMITS:
            return ConfigError(reason=f"provider_declares_no_host:{name}")
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


def host_limit(name: str) -> HostLimit | None:
    """Объявление хоста по имени провайдера; None — не сетевой."""
    return _HOST_LIMITS.get(name)


def all_host_limits() -> dict[str, HostLimit]:
    """Все объявления: имя провайдера -> HostLimit (BACKLOG B24 —
    потолок хоста для doctor и status)."""
    return dict(_HOST_LIMITS)


__all__ = [
    "DisclosuresProvider", "SyntheticDisclosuresProvider",
    "MarketDataProvider", "SyntheticMarketProvider",
    "UnknownProvider", "ProviderError", "ConfigError", "HostLimit",
    "RequestGate", "register", "get_provider", "available", "host_limit",
    "all_host_limits",
]
