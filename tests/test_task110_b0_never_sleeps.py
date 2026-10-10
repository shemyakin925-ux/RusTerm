"""ТЗ-110 B0 «приёмка не спит»: зубы на автозамену из conftest.

Замер (круг 145): hand ТЗ-109 шёл ~4 ч — pytest парковался в
`time.sleep` на живых Yahoo-429, а верификация пала на переходе
полуночи внутри одного теста. Здесь закреплено:
- сокет в обычном тесте запрещён, тест назван по имени в ошибке;
- путь ретрая (ТЗ-109 R2) укладывается в секунду: паузы 1/4/15
  запрошены (писарь), но не проспаны;
- дата дверей программы заморожена на тест и совпадает с
  `frozen_today`, каким бы ни был реальный час.
"""
from __future__ import annotations

import socket
import time
import urllib.error

import pytest

import datetime

from rusterm.providers.budget import retry_transport
from rusterm.cli import args_as_of_default

import tests.conftest as _conftest


def test_a_socket_opening_test_fails_with_its_name():
    """Сокет в обычном тесте запрещён; в сообщении — имя теста."""
    sock = socket.socket()
    try:
        with pytest.raises(AssertionError) as excinfo:
            sock.connect(("93.184.216.34", 80))
    finally:
        sock.close()
    message = str(excinfo.value)
    assert "ТЗ-110 B0" in message, message
    assert "test_a_socket_opening_test_fails_with_its_name" in message, \
        message


def test_create_connection_is_blocked_too():
    with pytest.raises(AssertionError) as excinfo:
        socket.create_connection(("example.com", 80))
    assert "test_create_connection_is_blocked_too" in str(excinfo.value)


def test_the_retry_path_finishes_under_a_second():
    """Три транзиентных отказа — четыре попытки, меньше секунды на
    стенке; паузы 1/4/15 записаны писарем, но не проспаны."""
    attempts = {"n": 0}

    def op():
        attempts["n"] += 1
        if attempts["n"] < 4:
            raise urllib.error.URLError("down")
        return "ok"

    started = time.perf_counter()
    outcome = retry_transport(op)
    took = time.perf_counter() - started

    assert outcome == "ok"
    assert attempts["n"] == 4
    assert took < 1.0, took
    assert _conftest._budget.RETRY_SLEEPS[-3:] == [1.0, 4.0, 15.0], \
        _conftest._budget.RETRY_SLEEPS[-3:]


def test_program_date_doors_agree_with_frozen_today(frozen_today):
    """Двери программы читают замороженную дату теста: край окна,
    посчитанный тестом, и сборка согласованы при любом часе."""
    assert args_as_of_default() == frozen_today.isoformat()
    assert isinstance(frozen_today, datetime.date)


def test_live_test_is_skipped_without_rusterm_live(tmp_path):
    """Живой тест без RUSTERM_LIVE=1 скипается, с ней — идёт.
    Демонстрация на настоящем прогоне: проба кладётся в tests/ (чтобы
    загрузился conftest с автозаменой B0) и гоняется подпроцессом с
    селектором `-m live`; проба самоуничтожается в finally."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    probe = repo / "tests" / "test_b0_live_probe_tmp.py"
    probe.write_text(
        "import pytest\n"
        "@pytest.mark.live\n"
        "def test_live_probe_runs_when_allowed():\n"
        "    assert True\n",
        encoding="utf-8")
    try:
        def run(live: str | None) -> str:
            env = dict(os.environ)
            env.pop("RUSTERM_LIVE", None)
            if live is not None:
                env["RUSTERM_LIVE"] = live
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-m", "live",
                 "tests/test_b0_live_probe_tmp.py"],
                capture_output=True, text=True, env=env, timeout=180,
                cwd=repo)
            return proc.stdout + proc.stderr

        without = run(None)
        assert "1 skipped" in without, without
        assert "1 passed" not in without, without

        with_env = run("1")
        assert "1 passed" in with_env, with_env
        assert "1 skipped" not in with_env, with_env
    finally:
        probe.unlink(missing_ok=True)
