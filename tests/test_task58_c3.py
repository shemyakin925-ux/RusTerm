"""ТЗ-58 C3: расхождения из таблицы A3 закрыты той же механикой, что
`markets` (BACKLOG B35): команды, которые по умолчанию только читают,
не создают absent-каталог данных — он называется по имени. Пишущие
режимы (--record, --fix) поведение не меняют: каталог создаётся
(позитивный контроль).

Команды из REPORT-57 A3: metrics, doctor, census и tui (экран был
задокументирован «только чтение», а каталог создавал молча).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sandbox_home(cwd: Path) -> Path:
    """HOME вне git-дерева — иначе правило 4 из store/paths.resolve_root
    указывает на настоящий каталог разработчика, и тест пишущего режима
    мигрирует его и пишет в него метрики."""
    home = cwd.parent / (cwd.name + "-home")
    home.mkdir(parents=True, exist_ok=True)
    return home


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(ROOT),
               HOME=str(_sandbox_home(cwd)))
    env.pop("RUSTERM_DATA", None)
    env["RUSTERM_ENV_FILE"] = str(cwd / "empty-env")
    return subprocess.run([sys.executable, "-m", "rusterm.cli", *argv],
                          cwd=cwd, capture_output=True, text=True,
                          env=env)


def _git_status(cwd: Path) -> str:
    done = subprocess.run(["git", "status", "--porcelain"],
                          cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _fresh_git_tree(tmp_path: Path, name: str) -> Path:
    tree = tmp_path / name
    tree.mkdir()
    done = subprocess.run(["git", "init", "-q"], cwd=tree,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert _git_status(tree) == "", "дерево не чистое на старте"
    return tree


def test_metrics_readonly_refuses_absent_dir_and_creates_nothing(
        tmp_path):
    tree = _fresh_git_tree(tmp_path, "metrics-tree")
    done = _run(tree, "metrics")
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert "каталога данных нет" in done.stderr, done.stderr
    assert _git_status(tree) == "", _git_status(tree)


def test_doctor_readonly_refuses_absent_dir_and_creates_nothing(
        tmp_path):
    # контракт doctor (test_cli_doctor_detects_schema_gap): отчёт JSON
    # в stdout и код 1; ТЗ-58 C3 добавляет: каталог не создаётся,
    # отсутствие базы — находка отчёта (cadence.reason=no_data_dir)
    tree = _fresh_git_tree(tmp_path, "doctor-tree")
    done = _run(tree, "doctor")
    assert done.returncode == 1, (done.stdout, done.stderr)
    report = json.loads(done.stdout)
    assert report["ok"] is False
    assert any("schema_version" in p for p in report["problems"])
    assert report["cadence"]["reason"] == "no_data_dir"
    assert _git_status(tree) == "", _git_status(tree)


def test_census_refuses_absent_dir_and_creates_nothing(tmp_path):
    tree = _fresh_git_tree(tmp_path, "census-tree")
    done = _run(tree, "census", "--instrument", "US-NOPE")
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert "каталога данных нет" in done.stderr, done.stderr
    assert _git_status(tree) == "", _git_status(tree)


def test_tui_refuses_absent_dir_and_creates_nothing(tmp_path):
    tree = _fresh_git_tree(tmp_path, "tui-tree")
    done = _run(tree, "tui")
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert "каталога данных нет" in done.stdout + done.stderr, \
        (done.stdout, done.stderr)
    assert _git_status(tree) == "", _git_status(tree)


def test_writing_modes_keep_creating(tmp_path):
    """Позитивный контроль: пишущие режимы поведение не меняют —
    metrics --record и doctor --fix создают каталог данных. Каталог
    показан явно (`--root .`): с ТЗ-90 A5 без базы в cwd молчаливый
    выбор ушёл бы по правилу 4 в $HOME/.rusterm — там его проверяет
    tests/test_b35_markets_readonly.py."""
    tree = _fresh_git_tree(tmp_path, "write-tree")
    done = _run(tree, "--root", ".", "metrics", "--record")
    status = _git_status(tree)
    assert status != "", (done.stdout, done.stderr)
    assert (tree / "rusterm.db").exists()
    done = _run(tree, "--root", ".", "doctor", "--fix")
    assert done.returncode == 0, (done.stdout, done.stderr)
