"""BACKLOG B35 (ТЗ-57 A3): команда только-чтения не пачкает дерево.

`markets`, `markets --json` и `--help` из ЧИСТОГО git-дерева обязаны
оставить `git status --porcelain` пустым (дефект B35: markets через
_open создавал в cwd rusterm.db, exports/, logs/ и raw/ — падала
приёмка пунктом 13). Стиль tests/test_b40_readonly_commands.py:
subprocess из временного каталога, изоляция окружения. Позитивный
контроль: init и ingest каталог СОЗДАЮТ — тот же assert видит их
след (пишущим показывают `--root .`: с ТЗ-90 A5 без базы в cwd
молчаливый выбор ушёл бы по правилу 4 в $HOME/.rusterm).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sandbox_home(cwd: Path) -> Path:
    """HOME вне git-дерева — иначе правило 4 из store/paths.resolve_root
    указывает на настоящий каталог разработчика, и тест пишущей команды
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


def test_markets_leaves_clean_tree_clean(tmp_path):
    tree = _fresh_git_tree(tmp_path, "markets-tree")
    for argv in (["markets"], ["markets", "--json"], ["--help"]):
        done = _run(tree, *argv)
        assert done.returncode == 0, (argv, done.stderr)
        status = _git_status(tree)
        assert status == "", (argv, status)


def test_init_creates_catalog_positive_control(tmp_path):
    tree = _fresh_git_tree(tmp_path, "init-tree")
    done = _run(tree, "--root", ".", "init")
    assert done.returncode == 0, done.stderr
    status = _git_status(tree)
    assert status != "", "init обязан создать каталог данных"
    assert (tree / "rusterm.db").exists()


def test_ingest_creates_catalog_positive_control(tmp_path):
    tree = _fresh_git_tree(tmp_path, "ingest-tree")
    done = _run(tree, "--root", ".", "ingest", "--instrument", "US-NOPE")
    status = _git_status(tree)
    assert status != "", "ingest обязан создать каталог данных"
    assert (tree / "rusterm.db").exists()


def test_writer_without_root_goes_to_the_home_rule_not_the_tree(tmp_path):
    """ТЗ-90 A5, правило 4: без базы в cwd пишущая команда создаёт
    каталог в $HOME/.rusterm. HOME здесь — песочница рядом с деревом
    (замерено: без неё тесты писали в настоящий ~/.rusterm)."""
    tree = _fresh_git_tree(tmp_path, "home-rule-tree")
    home = tree.parent / "home-rule-tree-home"
    done = _run(tree, "init")
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert (home / ".rusterm" / "rusterm.db").exists(), done.stdout
    assert _git_status(tree) == "", _git_status(tree)
    assert f"каталог: {home / '.rusterm'}" in done.stdout, done.stdout
