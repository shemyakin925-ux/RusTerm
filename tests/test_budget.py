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


# ── TASK-19 F5: бюджет и темп по хостам ────────────────────────────────

from rusterm.providers.budget import HostLimit

_A = HostLimit(host="host-a.example", per_second=1000.0, nightly_max=2)
_B = HostLimit(host="host-b.example", per_second=1000.0, nightly_max=2)


def _ua_gate() -> RequestGate:
    return RequestGate(gate=NetworkGate(
        environ={"RUSTERM_SEC_UA": "Synthetic Test f5.invalid"}))


def test_two_hosts_exhaust_independently():
    """F5: хост A у своего потолка (2) не запирает хост B — пулы
    раздельные, счётчики по хостам."""
    gate = _ua_gate()
    send = lambda headers: "ok"
    assert gate.request(send, limit=_A) == "ok"
    assert gate.request(send, limit=_A) == "ok"
    assert isinstance(gate.request(send, limit=_A), BudgetExceeded)
    # чужой хост проходит: SECовский потолок не перетекает на соседа
    assert gate.request(send, limit=_B) == "ok"
    assert gate.calls_made == 3
    assert gate.refused == 1


def test_per_host_pools_do_not_share_legacy_budget():
    """F5: запросы по HostLimit не трогают легаси-пул и наоборот —
    5/с SEC не наследуется чужим хостом и не съедается им."""
    gate = _ua_gate()
    send = lambda headers: "ok"
    legacy = HostLimit(host="data.sec.gov", per_second=5.0,
                       nightly_max=5000)
    assert gate.request(send) == "ok"           # легаси-пул (edgar)
    assert gate.request(send, limit=_A) == "ok"  # свой пул по хосту
    assert gate.budget.used == 1                 # легаси потратил один
    assert gate.calls_made == 2


def test_seat_returns_config_error_value_not_import_error():
    """F5: get_provider('dart') до появления модуля — значение
    provider_not_implemented, не ImportError (место уже занято)."""
    from rusterm.providers import get_provider
    result = get_provider("dart", gate=_ua_gate())
    assert isinstance(result, ConfigError)
    assert result.reason == "provider_not_implemented:dart"
    # без гейта — прежняя дверь U5, тоже значением
    no_gate = get_provider("dart", gate=None)
    assert isinstance(no_gate, ConfigError)
    assert no_gate.reason == "network_provider_requires_gate:dart"


def test_available_lists_all_eight_names():
    """F5: пять сетевых мест (edgar, dart, cvm, asx, otcmarkets) +
    llm-api + две синтетики — ровно восемь имён."""
    from rusterm.providers import available
    names = available()
    assert len(names) == 8
    for expected in ("edgar", "dart", "cvm", "asx", "otcmarkets",
                     "llm-api", "synthetic-market",
                     "synthetic-disclosures"):
        assert expected in names, expected


def test_every_network_provider_declares_host_limit():
    """F5: у каждого сетевого провайдера есть HostLimit; темпы — из
    замеров REPORT-MARKETS (SEC 5/с, DART 2/с, CVM/ASX/OTC 1/с)."""
    from rusterm.providers import _HOST_LIMITS, _NETWORK_PROVIDERS
    assert set(_HOST_LIMITS) == set(_NETWORK_PROVIDERS)
    rates = {"edgar": 5.0, "dart": 2.0, "cvm": 1.0, "asx": 1.0,
             "otcmarkets": 1.0, "llm-api": 1.0}
    for name, limit in _HOST_LIMITS.items():
        assert limit.host, name
        assert limit.per_second == rates[name], name
        assert limit.nightly_max > 0, name
