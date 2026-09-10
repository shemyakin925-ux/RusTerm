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


@dataclass(frozen=True)
class HostLimit:
    """Объявление сетевого провайдера (TASK-19 F5): какой хост, каким
    темпом и с каким ночным потолком. Реестр не выдаёт сетевого
    провайдера без объявления — та же дверь, что U5, петля шире; темпы
    взяты из живых замеров agent/REPORT-MARKETS.md."""
    host: str
    per_second: float
    nightly_max: int


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

    Бюджет и темп ведутся ПО ХОСТУ (TASK-19 F5): 5/с SEC не перетекает
    на opendart.fss.or.kr и наоборот. Пул по хосту создаётся лениво из
    HostLimit провайдера; request(send) без limit — прежний единый пул
    (edgar, 5/с, 5000/ночь), его поведение не менялось.

    Счётчики для metric_sample (T12): сделано, отказано, задержано —
    суммарно по всем пулам.
    """

    def __init__(self, budget: Budget | None = None,
                 limiter: RateLimiter | None = None,
                 gate: NetworkGate | None = None) -> None:
        self.gate = gate or NetworkGate()
        self.budget = budget or Budget()
        self.limiter = limiter or RateLimiter()
        self._made = 0
        self.config_refusals = 0
        self._host_pools: dict[str, tuple[Budget, RateLimiter, HostLimit]] = {}

    def _pool_for(self, limit: HostLimit) -> tuple[Budget, RateLimiter]:
        key = limit.host.lower()
        pool = self._host_pools.get(key)
        if pool is None:
            pool = (Budget(max_requests=limit.nightly_max),
                    RateLimiter(per_second=limit.per_second), limit)
            self._host_pools[key] = pool
        return pool

    @property
    def calls_made(self) -> int:
        per_host = sum(b.used for b, _, _ in self._host_pools.values())
        return self._made + per_host

    @property
    def refused(self) -> int:
        per_host = sum(b.refused for b, _, _ in self._host_pools.values())
        return self.budget.refused + self.config_refusals + per_host

    @property
    def rate_limited(self) -> int:
        return self.limiter.rate_limited + sum(
            rl.rate_limited for _, rl, _ in self._host_pools.values())

    def host_usage(self) -> dict[str, dict]:
        """Счётчики по хостам (BACKLOG B24): used/отказы/потолок/темп
        каждого тронутого пула. Незатронутые хосты не показываются."""
        return {host: {"used": b.used, "refused": b.refused,
                       "rate_limited": rl.rate_limited,
                       "ceiling": limit.nightly_max,
                       "per_second": limit.per_second}
                for host, (b, rl, limit) in self._host_pools.items()}

    def request(self, send: Callable[[dict[str, str]], T],
                limit: HostLimit | None = None) -> T | ConfigError | BudgetExceeded:
        """Один сетевой вызов: send получает заголовки с User-Agent.

        limit задан — пул по хосту из объявления провайдера; None —
        прежний единый пул (edgar).
        """
        headers = self.gate.headers()
        if isinstance(headers, ConfigError):
            self.config_refusals += 1
            return headers
        if limit is None:
            budget, limiter = self.budget, self.limiter
        else:
            budget, limiter, _declared = self._pool_for(limit)
        exceeded = budget.charge()
        if exceeded is not None:
            return exceeded
        limiter.acquire()
        if limit is None:
            self._made += 1
        return send(headers)
