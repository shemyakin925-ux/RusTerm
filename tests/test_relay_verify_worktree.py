"""ТЗ-88 C1: `verify` не наследует мусор прошлого прогона.

Два промаха прежнего `cmd_verify`:

* путь по умолчанию был один на всю машину
  (`tempfile.gettempdir()/rusterm-relay-verify`), а повторный прогон
  делал только `checkout --detach` + `reset --hard` — неотслеживаемое
  они не трогают. Измерено на ветке night-11 (прогон 46): дерево с
  `leftover.py` было принято молча, приёмка вернула «ПРИНЯТО», и файл
  в нём остался;
* молчаливая чистка чужого дерева запрещена и пунктом C4, и смыслом
  проверки: красный `test_i5` от чужого файла — это не поломка
  приёмки, а_signal_ о том, что смотрят не туда.

Репозиторий тестов — локальный «origin» в `tmp_path`, сеть не нужна.
В нём лежит НАСТОЯЩИЙ `agent/relay.py` (вызывается по абсолютному пути)
и заглушка `agent/acceptance.sh`, чтобы не гнать весь набор тестов ради
проверки того, куда и с каким отказом ставится дерево.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RELAY = Path(__file__).resolve().parents[1] / "agent" / "relay.py"
BRANCH = "agent/night-c1"

# Scrub окружения, как в test_j1_hand (ТЗ-46): временный индекс чужого
# репозитория не должен просачиваться в песочницу.
LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
          "RUSTERM_RELAY_VERIFY_DIR")


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, env=env, check=True)


@pytest.fixture()
def shift_repo(tmp_path: Path) -> Path:
    """Голый origin + клон с коммитом: заглушка приёмки и BATON на месте."""
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-q", str(origin)], cwd=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    (work / "agent").mkdir()
    (work / "agent" / "acceptance.sh").write_text(
        "#!/usr/bin/env bash\n"
        "echo ЗАГЛУШКА-ПРИЁМКИ-В-$(basename \"$PWD\")\n", encoding="utf-8")
    (work / "rusterm").mkdir()
    (work / "rusterm" / "__init__.py").write_text("", encoding="utf-8")
    _git(["add", "-A"], cwd=work)
    _git(["commit", "-q", "-m", "round-9: заготовка смены"], cwd=work)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], cwd=work)
    return work


def _head(work: Path) -> str:
    """sha ветки смены: `worktree add` по имени не работает — локальной
    ветки в клоне нет, есть только `origin/<branch>`."""
    return _git(["rev-parse", f"origin/{BRANCH}"], cwd=work).stdout.strip()


def _verify(work: Path, extra: list[str], tmp_home: Path):
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env["HOME"] = str(tmp_home)          # дерево приёмки — тоже в песочнице
    env["TMPDIR"] = str(tmp_home / "tmp")
    (tmp_home / "tmp").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, str(RELAY), "--branch", BRANCH, "verify", *extra],
        cwd=work, capture_output=True, text=True, env=env)


def test_explicit_tree_with_untracked_file_is_refused_by_name(
        tmp_path: Path, shift_repo: Path) -> None:
    """Грязное явное дерево -> отказ, называющий файл; молча не чистим."""
    dirty = tmp_path / "dirty-tree"
    _git(["worktree", "add", "--detach", str(dirty), _head(shift_repo)],
         cwd=shift_repo)
    (dirty / "leftover.py").write_text("# мусор прошлого прогона\n",
                                       encoding="utf-8")

    proc = _verify(shift_repo, ["--worktree", str(dirty)],
                   tmp_path / "home")

    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "leftover.py" in proc.stderr, proc.stderr
    assert "ЗАГЛУШКА-ПРИЁМКИ" not in proc.stdout, (
        f"приёмка всё равно пошла в грязное дерево: {proc.stdout}")
    # C4: чужие файлы не удаляются и не уезжают в никуда.
    assert (dirty / "leftover.py").exists(), "verify стёр чужой файл"
    assert "clean -fd" in proc.stderr, proc.stderr   # команда, которой убрать


def test_clean_explicit_tree_still_runs_the_acceptance(
        tmp_path: Path, shift_repo: Path) -> None:
    """Отказ — только по мусору: чистое явное дерево прогон идёт."""
    clean = tmp_path / "clean-tree"
    _git(["worktree", "add", "--detach", str(clean), _head(shift_repo)],
         cwd=shift_repo)

    proc = _verify(shift_repo, ["--worktree", str(clean)],
                   tmp_path / "home")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ЗАГЛУШКА-ПРИЁМКИ-В-clean-tree" in proc.stdout, proc.stdout


def test_default_worktree_path_differs_between_runs(
        tmp_path: Path, shift_repo: Path) -> None:
    """Путь по умолчанию уникален на прогон: два вызова без `--worktree`
    ставят два разных дерева, и ни одно не наследует мусор другого."""
    first = _verify(shift_repo, [], tmp_path / "home")
    assert first.returncode == 0, first.stdout + first.stderr
    leftover = Path(first.stdout.split("дерево приёмки: ")[1]
                    .splitlines()[0].strip()) / "leftover.py"
    leftover.write_text("# прошлый прогон\n", encoding="utf-8")

    second = _verify(shift_repo, [], tmp_path / "home")

    assert second.returncode == 0, second.stdout + second.stderr
    path_a = first.stdout.split("дерево приёмки: ")[1].splitlines()[0]
    path_b = second.stdout.split("дерево приёмки: ")[1].splitlines()[0]
    assert path_a.strip() != path_b.strip(), (
        f"дерево приёмки переиспользовано: {path_a}")
    listed = _git(["ls-files", "--others", "--exclude-standard"],
                  cwd=leftover.parent).stdout
    assert "leftover.py" in listed, (
        "мусор прошлого прогона пережил checkout+reset — тот же путь")
