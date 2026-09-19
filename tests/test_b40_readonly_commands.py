"""BACKLOG B40: команды «только на чтение» не создают каталог данных.

Реестр B35-стиля по четырём командам, которые открывали absent-каталог
через _open (создать + ensure_app_dir) и оставляли после себя
rusterm.db, exports/, logs/ и raw/:

- budget     — печатает потолки и счётчики; создавать нечего;
               на отсутствующей базе теперь потолки + «нет данных»;
- cadence    — планирует проход по существующим инструментам;
               absent-каталог = «нечего планировать», rc 0;
- status     — «что у меня есть»; absent-каталог = отказ по имени
               («каталога данных нет»), rc 1, ничего не создано;
- coverage   — читает покрытие инструмента; absent-каталог = отказ
               по имени, rc 1, ничего не создано.

Verdict-таблица в agent/REPORT-50.md. markets уже закрыт тестами B35.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    env.setdefault("RUSTERM_ENV_FILE", str(cwd / "empty-env"))
    return subprocess.run([sys.executable, "-m", "rusterm.cli", *argv],
                          cwd=cwd, capture_output=True, text=True,
                          env=env)


def _assert_creates_nothing(tmp_path: Path, name: str, *argv: str,
                            expect_rc: int):
    empty = tmp_path / name
    empty.mkdir()
    data_dir = empty / "данные"
    done = _run(empty, "--root", str(data_dir), *argv)
    assert done.returncode == expect_rc, (name, done.stdout, done.stderr)
    left = sorted(p.name for p in empty.iterdir())
    assert left == [], f"{name}: команда только на чтение оставила: {left}"


def test_budget_creates_nothing_and_says_no_data(tmp_path):
    _assert_creates_nothing(tmp_path, "budget-dir", "budget", expect_rc=0)
    done = _run(tmp_path / "budget-dir", "--root",
                str(tmp_path / "budget-dir" / "данные"), "budget")
    assert "5000" in done.stdout


def test_cadence_creates_nothing_and_says_nothing_to_plan(tmp_path):
    _assert_creates_nothing(tmp_path, "cadence-dir", "cadence",
                            expect_rc=0)
    done = _run(tmp_path / "cadence-dir", "--root",
                str(tmp_path / "cadence-dir" / "данные"), "cadence")
    assert "нечего планировать" in done.stdout + done.stderr


def test_status_refuses_by_name_on_absent_data_dir(tmp_path):
    _assert_creates_nothing(tmp_path, "status-dir", "status", expect_rc=1)
    done = _run(tmp_path / "status-dir", "--root",
                str(tmp_path / "status-dir" / "данные"), "status")
    assert "каталога данных нет" in done.stderr


def test_coverage_refuses_by_name_on_absent_data_dir(tmp_path):
    _assert_creates_nothing(tmp_path, "coverage-dir", "coverage",
                            "--instrument", "US-NOPE", expect_rc=1)
    done = _run(tmp_path / "coverage-dir", "--root",
                str(tmp_path / "coverage-dir" / "данные"),
                "coverage", "--instrument", "US-NOPE")
    assert "каталога данных нет" in done.stderr
