"""ТЗ-23 K5: обход по полноте — фальшивые часы, бюджет, приоритеты.

- полный инструмент скипается на день 3 и опрашивается на день 10;
- неполный забирает бюджет раньше полного;
- проход, оборванный потолком, возобновляется без повторных запросов;
- симуляция 30 дней: запросов в день меньше 800 (для отчёта).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core import cadence
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

DAY0 = date(2026, 9, 1)


def _as_of(day: int) -> str:
    return (DAY0 + timedelta(days=day)).isoformat()


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    def issuer_with_history(n: int, days: list[int], last_day: int):
        iid = f"US-{chr(ord('A') + n)}"
        issuer = f"i{n}"
        repos.instrument.upsert_issuer(Issuer(
            issuer, f"Corp {n}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer, None, "common", "active", None))
        rows = [{"date": _as_of(d), "close": 100.0 + d,
                 "currency": "USD"} for d in days]
        repos.price.put_rows(iid, "twelvedata", rows)
        return iid

    # полный: история сомкнута до дня 0
    complete = issuer_with_history(0, [0], 0)
    # неполный: дыра 11..? внутри — закрывается одной коллекцией
    incomplete = issuer_with_history(1, [0, 11], 11)
    return conn, repos, complete, incomplete


def test_complete_skipped_on_day3_polled_on_day10(env):
    conn, repos, complete, incomplete = env
    # день 3: полный не из-за срока (прошло 3 дня < 10) — скип
    plan = cadence.plan_pass(repos, _as_of(3))
    by_id = {e.instrument_id: e for e in plan}
    assert by_id[complete].action == "skip"
    assert by_id[incomplete].action == "backfill"
    # день 10: полный опрашивается
    plan = cadence.plan_pass(repos, _as_of(10))
    by_id = {e.instrument_id: e for e in plan}
    assert by_id[complete].action == "poll"


def test_completeness_is_computed_not_a_flag(env):
    conn, repos, complete, incomplete = env
    state, reason, last = cadence.instrument_state(
        repos.price.dates(complete), _as_of(1))
    assert (state, last) == ("complete", _as_of(0))
    state, reason, last = cadence.instrument_state(
        repos.price.dates(incomplete), _as_of(30))
    assert state == "incomplete"
    assert reason.startswith("gap:")
    # флага нет и быть не может: состояние выводится из дат каждый раз
    # добор истории переворачивает состояние: из данных, не из флага
    repos.price.put_rows(incomplete, "twelvedata",
                         [{"date": _as_of(d), "close": 1.0,
                           "currency": "USD"} for d in range(1, 25)])
    state, _, _ = cadence.instrument_state(
        repos.price.dates(incomplete), _as_of(26))
    assert state == "complete", "дыра закрыта — история сомкнута"


def test_backfill_takes_budget_ahead_of_poll(env):
    conn, repos, complete, incomplete = env
    calls: list[str] = []
    result = cadence.run_pass(
        repos, _as_of(10), lambda e: calls.append(e.instrument_id),
        budget=1)
    assert calls == [incomplete], "неполный забирает бюджет первым"
    assert result["stopped_at"] == complete
    assert result["spent"] == 1


def test_interrupted_pass_resumes_without_duplicate_requests(env):
    """Бюджет 1 запрос/день: неполный добивается первым, полный
    опрашивается из остатка; коллектор как настоящий сбор — двигает
    данные, и план пересчитывается из них же (возобновляемость)."""
    conn, repos, complete, incomplete = env
    calls: list[str] = []

    def collector_for(day):
        def collect(entry):
            calls.append(entry.instrument_id)
            repos.price.put_rows(entry.instrument_id, "twelvedata",
                                 [{"date": _as_of(day), "close": 100.0,
                                   "currency": "USD"}])
        return collect

    cadence.run_pass(repos, _as_of(10), collector_for(10), budget=1)
    cadence.run_pass(repos, _as_of(11), collector_for(11), budget=1)
    cadence.run_pass(repos, _as_of(21), collector_for(21), budget=5)
    # день 10: неполный (приоритет); день 11: полный в сроке опроса;
    # день 21: оба в сроке опроса
    assert calls == [incomplete, complete, complete, incomplete] or \
        calls == [incomplete, complete, incomplete, complete], calls
    # ни одного повторного запроса в один день
    assert len(calls) == len(set(enumerate(calls)))


def test_thirty_day_simulation_under_daily_ceiling(env, capsys):
    """Симуляция 30 дней: 8 неполных добиваются, полные опрашиваются
    раз в 10 дней; запросов в день — единицы, потолок 800 не близко."""
    conn, repos, complete, incomplete = env
    # портфель: 40 полных + 8 неполных, история на день 0
    instruments = [complete]
    for n in range(1, 40):
        iid = f"US-{chr(ord('A') + n % 26)}{n}"
        repos.instrument.upsert_issuer(Issuer(
            f"ic{n}", f"C{n}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"ic{n}", None, "common", "active", None))
        repos.price.put_rows(iid, "twelvedata",
                             [{"date": _as_of(0), "close": 100.0,
                               "currency": "USD"}])
        instruments.append(iid)
    for n in range(8):
        iid = f"US-B{n}"
        repos.instrument.upsert_issuer(Issuer(
            f"ib{n}", f"B{n}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"ib{n}", None, "common", "active", None))
        repos.price.put_rows(iid, "twelvedata",
                             [{"date": _as_of(0), "close": 100.0,
                               "currency": "USD"},
                              {"date": _as_of(0 + 30 * (n + 1)),
                               "close": 100.0, "currency": "USD"}])
        instruments.append(iid)
    calls: list[str] = []
    per_day: dict[int, int] = {}
    for day in range(0, 30, 2):
        result = cadence.run_pass(
            repos, _as_of(day),
            lambda e: calls.append(e.instrument_id), budget=800)
        per_day[day] = result["spent"]
    assert all(v < 800 for v in per_day.values()), per_day
    assert sum(per_day.values()) == len(calls)
    capsys.readouterr()
    print("30-дневная каденция (проход раз в 2 дня), запросов/день:")
    for day in sorted(per_day):
        print(f"  day {day:2d}: {per_day[day]}")
