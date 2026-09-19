"""Две находки полной проверки 17.09.2026, обе видны только руками.

1. BACKLOG B35: команда, которая только читает реестр рынков,
   создавала в ТЕКУЩЕМ каталоге rusterm.db, exports/, logs/ и raw/.
   Запуск `rusterm markets` из корня репозитория ронял приёмку
   пунктом 13 у того, кто его запустил.
2. Отказ «сектор не найден» не говорил, какие секторы есть, — и
   пользователю оставалось читать исходники.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, "-m", "rusterm.cli", *argv],
                          cwd=cwd, capture_output=True, text=True, env=env)


def test_markets_creates_nothing_in_the_current_directory(tmp_path):
    """B35: реестр рынков читается без создания каталога данных."""
    empty = tmp_path / "чужой-каталог"
    empty.mkdir()
    done = _run(empty, "markets")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "US" in done.stdout, done.stdout
    left = sorted(p.name for p in empty.iterdir())
    assert left == [], f"команда только на чтение оставила: {left}"


def test_markets_json_creates_nothing_either(tmp_path):
    empty = tmp_path / "чужой-каталог-json"
    empty.mkdir()
    done = _run(empty, "markets", "--json")
    assert done.returncode == 0, done.stdout + done.stderr
    assert sorted(p.name for p in empty.iterdir()) == []


def test_unknown_sector_refusal_names_what_exists(tmp_path):
    """Отказ называет причину И следующий шаг: какие секторы есть."""
    root = tmp_path / "data"
    assert _run(tmp_path, "--root", str(root), "init").returncode == 0
    done = _run(tmp_path, "--root", str(root), "industry",
                "--sector", "нет-такого")
    assert done.returncode == 1
    message = done.stdout + done.stderr
    assert "нет-такого" in message
    assert ("известные секторы" in message
            or "нет ни одного сектора" in message), message
