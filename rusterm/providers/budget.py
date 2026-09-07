"""Бюджет и темп сетевых запросов (TASK-7 T3, module-contracts.md §2).

Границы: файл живёт в providers и не импортирует store/sqlite3 (I10);
ошибки — значения, не исключения (§7): без User-Agent сеть запрещена
(N2), сверх потолка запрос отклоняется, а не ждёт (N3 — спящий агент в
четыре часа ночи сжигает ночь молча).

Реальные (сетевые) провайдеры ходят в сеть только через
RequestGate.request — мимо этой двери запрос не проходит. Синтетические
провайдеры нулевой стоимости и лимитера не касаются.
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

SEC_UA_ENV = "RUSTERM_SEC_UA"

T = TypeVar("T")


@dataclass(frozen=True)
class BudgetExceeded:
    """Исчерпан бюджет запросов: значение, не исключение (N3, §7)."""
    used: int
    max_requests: int
    reason: str = "budget_exceeded"


@dataclass(frozen=True)
class ConfigError:
    """Нет обязательной конфигурации для выхода в сеть (N2, §7)."""
    reason: str


class RateLimiter:
    """Держит не более per_second запросов в секунду.

    Монотонные часы (не настенные), сон через инъекцию sleeper — тесты
    спят подставным сном, а не настоящим.
    """

    def __init__(self, per_second: float = 5.0,
                 clock: Callable[[], float] | None = None,
                 sleeper: Callable[[float], None] | None = None) -> None:
        self.min_interval = 1.0 / per_second
        self.clock = clock or time.monotonic
        self.sleeper = sleeper or time.sleep
        self._next_allowed = self.clock()
        self.rate_limited = 0  # сколько вызовов пришлось задержать

    def acquire(self) -> None:
        now = self.clock()
        if now < self._next_allowed:
            self.rate_limited += 1
            self.sleeper(self._next_allowed - now)
            now = self.clock()
        self._next_allowed = max(now, self._next_allowed) + self.min_interval


class Budget:
    """Счётчик запросов с жёстким потолком; сверх — отказ значением."""

    def __init__(self, max_requests: int = 5000) -> None:
        self.max_requests = max_requests
        self.used = 0
        self.refused = 0

    def charge(self) -> BudgetExceeded | None:
        """Списать один запрос. None — можно; BudgetExceeded — потолок."""
        if self.used >= self.max_requests:
            self.refused += 1
            return BudgetExceeded(used=self.used,
                                  max_requests=self.max_requests)
        self.used += 1
        return None


class NetworkGate:
    """Правило идентификации (N2): нет RUSTERM_SEC_UA — сети нет."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self.environ = os.environ if environ is None else environ

    @property
    def user_agent(self) -> str | None:
        ua = self.environ.get(SEC_UA_ENV, "")
        return ua or None

    def headers(self) -> dict[str, str] | ConfigError:
        ua = self.user_agent
        if ua is None:
            return ConfigError("sec_ua_unset")
        return {"User-Agent": ua}


class RequestGate:
    """Единая дверь сетевого провайдера: UA-гейт -> бюджет -> темп.

    Счётчики для metric_sample (T12): сделано, отказано, задержано.
    """

    def __init__(self, budget: Budget | None = None,
                 limiter: RateLimiter | None = None,
                 gate: NetworkGate | None = None) -> None:
        self.gate = gate or NetworkGate()
        self.budget = budget or Budget()
        self.limiter = limiter or RateLimiter()
        self._made = 0
        self.config_refusals = 0

    @property
    def calls_made(self) -> int:
        return self._made

    @property
    def refused(self) -> int:
        return self.budget.refused + self.config_refusals

    @property
    def rate_limited(self) -> int:
        return self.limiter.rate_limited

    def request(self, send: Callable[[dict[str, str]], T]) -> T | ConfigError | BudgetExceeded:
        """Один сетевой вызов: send получает заголовки с User-Agent."""
        headers = self.gate.headers()
        if isinstance(headers, ConfigError):
            self.config_refusals += 1
            return headers
        exceeded = self.budget.charge()
        if exceeded is not None:
            return exceeded
        self.limiter.acquire()
        self._made += 1
        return send(headers)
