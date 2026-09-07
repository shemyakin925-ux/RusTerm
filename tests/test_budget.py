"""Тесты бюджета и лимитера запросов (TASK-7 T3). Настоящей сети нет:
send — подставной, сон — подставной; любой настоящий вызов — провал теста.
"""
from __future__ import annotations

import time

import pytest

from rusterm.providers.budget import (
    Budget,
    BudgetExceeded,
    ConfigError,
    NetworkGate,
    RateLimiter,
    RequestGate,
)


class FakeClock:
    """Подставные монотонные часы: sleeper двигает время, не спит."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleep_requests: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleep_requests.append(seconds)
        self.now += seconds


def _fail_send(headers):
    raise AssertionError("сетевой вызов вопреки гейту: send был вызван")


def test_budget_5001st_charge_returns_value_not_exception():
    budget = Budget(max_requests=5000)
    for _ in range(5000):
        assert budget.charge() is None
    outcome = budget.charge()  # 5001-й: значение, не исключение, не сон
    assert isinstance(outcome, BudgetExceeded)
    assert outcome.used == 5000
    assert budget.used == 5000
    assert budget.refused == 1


def test_limiter_holds_five_per_second_on_fake_clock():
    fc = FakeClock()
    limiter = RateLimiter(per_second=5, clock=fc, sleeper=fc.sleep)
    times = []
    for _ in range(20):
        limiter.acquire()
        times.append(fc.now)

    # Гарантия fixed-interval лимитера: соседние вызовы разнесены не меньше
    # чем на интервал; серия из 20 вызовов идёт ровно 19 интервалов,
    # то есть 5.0 вызовов/с в среднем по серии.
    for earlier, later in zip(times, times[1:]):
        assert later - earlier >= 0.2 - 1e-9
    assert times[-1] == pytest.approx(19 * 0.2)
    assert (len(times) - 1) / times[-1] == pytest.approx(5.0)

    # от начала серии в первую секунду проходят ровно 5 вызовов
    assert sum(1 for t in times if t < times[0] + 1.0) == 5

    # весь сон ушёл подставному sleeper (19 задержек), не time.sleep
    assert len(fc.sleep_requests) == 19

    # часы по умолчанию — монотонные, не настенные
    assert RateLimiter().clock is time.monotonic


def test_request_gate_refuses_without_ua_and_makes_no_call():
    rg = RequestGate(
        budget=Budget(max_requests=10),
        limiter=RateLimiter(per_second=5, clock=FakeClock(),
                            sleeper=lambda s: None),
        gate=NetworkGate(environ={}),  # RUSTERM_SEC_UA нет
    )
    outcome = rg.request(_fail_send)
    assert isinstance(outcome, ConfigError)
    assert outcome.reason == "sec_ua_unset"
    assert rg.calls_made == 0
    assert rg.budget.used == 0
    assert rg.refused == 1


def test_request_gate_passes_ua_charges_budget_and_counts():
    # Подставной контакт только для теста; настоящие запросы не делаются.
    rg = RequestGate(
        budget=Budget(max_requests=2),
        limiter=RateLimiter(per_second=5, clock=FakeClock(),
                            sleeper=lambda s: None),
        gate=NetworkGate(
            environ={"RUSTERM_SEC_UA": "Synthetic Test synthetic.invalid"}),
    )
    seen = []

    def send(headers):
        seen.append(headers)
        return "payload"

    assert rg.request(send) == "payload"
    assert rg.request(send) == "payload"
    assert seen and all(
        h["User-Agent"] == "Synthetic Test synthetic.invalid" for h in seen)

    # потолок 2: третий вызов отклонён значением, send не звался
    outcome = rg.request(send)
    assert isinstance(outcome, BudgetExceeded)
    assert len(seen) == 2

    assert rg.calls_made == 2
    assert rg.refused == 1
    # подставной sleeper время не двигает: третья задержка не нужна —
    # третий вызов отклонён бюджетом до лимитера
    assert rg.rate_limited == 1
