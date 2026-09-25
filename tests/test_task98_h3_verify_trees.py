"""ТЗ-98 H3: verify убирает только свои деревья.

Дерево приёмки ставится под общим /tmp и раньше переживало прогон:
убитый посредине процесс оставлял его там навсегда, и деревьев копилось
сколько угодно (кандидат 3 из REPORT-88, одобрен кругом 126). Теперь
каждое созданное прогоном дерево несёт метку `.relay-verify-owner`
(pid + id прогона), снимается после прогона — и зелёного, и красного, —
а осевшие СВОИ деревья с мёртвым pid выметаются в начале того же
`verify`. Дерево без метки не удаляется ни при каком pid: под общим
/tmp чужая работа отличается от мусора только меткой.

Репозиторий тестов — локальный «origin» в `tmp_path`, приёмка —
заглушка в нём же: настоящий `agent/acceptance.sh` в песочницу не
копируется и не правится. `TMPDIR` указывает на песочницу, поэтому
объезд не трогает настоящий /tmp (и не пишет ничего в `~` — P7).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

RELAY = Path(__file__).resolve().parents[1] / "agent" / "relay.py"
REPO_ROOT = Path(__file__).resolve().parents[1]
BRANCH = "agent/night-h3"
STAMP = ".relay-verify-owner"

# Как в test_relay_verify_worktree (ТЗ-46): чужой временный индекс и
# чужой путь дерева по умолчанию в песочницу не просачиваются.
LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
          "RUSTERM_RELAY_VERIFY_DIR")

# Заглушка приёмки докладывает то, на что смотрит настоящий пункт 13
# (`git status --porcelain`), и наличие метки: метка обязана лежать в
# дереве во время прогона и не быть при этом видимой мусором.
GREEN = ("#!/usr/bin/env bash\n"
         "echo ЗАГЛУШКА-ПРИЁМКИ: зелёная\n"
         "echo \"МЕТКА: $(test -f .relay-verify-owner && echo есть || echo нет)\"\n"
         "echo \"ВНЕ-GIT: $(git status --porcelain | tr '\\n' ';')\"\n"
         "exit 0\n")
RED = ("#!/usr/bin/env bash\n"
       "echo ЗАГЛУШКА-ПРИЁМКИ: красная\n"
       "exit 7\n")


def _env(cwd: Path | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    return env


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, env=_env(), check=True)


def _worktrees(repo: Path) -> set[str]:
    """Что зарегистрировано как рабочие деревья — чтобы отличить снятое
    дерево от каталога, который просто вынули из-под git."""
    out = _git(["worktree", "list", "--porcelain"], cwd=repo).stdout
    return {line.split(" ", 1)[1] for line in out.splitlines()
            if line.startswith("worktree ")}


@pytest.fixture()
def shift_repo(tmp_path: Path, request) -> Path:
    """Голый origin + клон: заглушка приёмки с нужным кодом возврата."""
    stub = RED if "red" in request.node.name else GREEN
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-q", str(origin)], cwd=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    (work / "agent").mkdir()
    (work / "agent" / "acceptance.sh").write_text(stub, encoding="utf-8")
    # НАСТОЯЩИЙ .gitignore репозитория, дословно: метка дерева должна
    # прятаться теми же строками, что и в рабочем дереве смены.
    (work / ".gitignore").write_text(
        (REPO_ROOT / ".gitignore").read_text(encoding="utf-8"),
        encoding="utf-8")
    _git(["add", "-A"], cwd=work)
    _git(["commit", "-q", "-m", "round-127: заготовка смены"], cwd=work)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], cwd=work)
    return work


def _sandbox(tmp_path: Path) -> Path:
    """Дом и /tmp прогона: всё под tmp_path, ничего настоящего."""
    home = tmp_path / "home"
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    return home


def _verify(work: Path, home: Path, extra: list[str] = ()):
    env = _env()
    env["HOME"] = str(home)
    env["TMPDIR"] = str(home / "tmp")
    return subprocess.run(
        [sys.executable, str(RELAY), "--branch", BRANCH, "verify", *extra],
        cwd=work, capture_output=True, text=True, env=env)


def _printed_tree(proc) -> Path:
    line = [l for l in proc.stdout.splitlines() if l.startswith("дерево приёмки: ")]
    assert line, proc.stdout + proc.stderr
    return Path(line[0].split(": ", 1)[1].strip())


def _dead_pid() -> int:
    """Pid заведомо мёртвого процесса: свой ребёнок, дождались ухода."""
    for _ in range(20):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        try:
            os.kill(child.pid, 0)
        except ProcessLookupError:
            return child.pid
        time.sleep(0.05)
    raise AssertionError("не получили мёртвый pid")


def _stale_tree(work: Path, home: Path, name: str, head: str,
                owner: dict | None) -> Path:
    """Осевшее дерево: зарегистрированное `worktree add`, с меткой или без."""
    tree = home / "tmp" / name
    _git(["worktree", "add", "--detach", str(tree), head], cwd=work)
    if owner is not None:
        (tree / STAMP).write_text(json.dumps(owner) + "\n", encoding="utf-8")
    (tree / "notes.txt").write_text("осталось после прогона\n",
                                    encoding="utf-8")
    return tree


def test_green_run_removes_the_tree_it_created(shift_repo: Path,
                                               tmp_path: Path) -> None:
    """Зелёный прогон: дерево стояло под TMPDIR, приёмка прошла, дерева
    нет — ни каталога, ни записи о рабочем дереве."""
    home = _sandbox(tmp_path)
    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    tree = _printed_tree(proc)
    assert tree.parent == home / "tmp"
    assert "ЗАГЛУШКА-ПРИЁМКИ: зелёная" in proc.stdout, proc.stdout
    assert not tree.exists(), f"дерево приёмки осталось: {tree}"
    assert str(tree) not in _worktrees(shift_repo)
    assert "убрано после прогона" in proc.stdout, proc.stdout


def test_red_run_removes_the_tree_too(shift_repo: Path,
                                      tmp_path: Path) -> None:
    """Красный прогон убирается так же: код возврата сохраняем, но
    мусор не оставляем (проверка «зелёное и красное дерево убираются
    одинаково» из пункта H3)."""
    home = _sandbox(tmp_path)
    proc = _verify(shift_repo, home)
    assert proc.returncode == 5, proc.stdout + proc.stderr
    tree = _printed_tree(proc)
    assert "ЗАГЛУШКА-ПРИЁМКИ: красная" in proc.stdout, proc.stdout
    assert not tree.exists(), f"красное дерево оставили: {tree}"
    assert str(tree) not in _worktrees(shift_repo)


def test_stale_stamped_tree_with_dead_pid_is_swept_at_start(
        shift_repo: Path, tmp_path: Path) -> None:
    """Осевшее своё дерево (метка verify, pid мёртв) выметается в начале
    следующего прогона и не переживает его."""
    home = _sandbox(tmp_path)
    head = _git(["rev-parse", f"origin/{BRANCH}"], cwd=shift_repo).stdout.strip()
    stale = _stale_tree(shift_repo, home,
                        f"rusterm-relay-verify-{head[:7]}-OLDDEADPID-1-1",
                        head, {"pid": _dead_pid(), "run": "круг-до-H3"})
    assert stale.exists()

    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not stale.exists(), f"осевшее дерево не убрано: {stale}"
    assert str(stale) in proc.stdout, proc.stdout
    assert str(stale) not in _worktrees(shift_repo)
    # дерево самого прогона убирается тем же путём
    assert not _printed_tree(proc).exists()


def test_tree_without_the_stamp_is_never_touched(shift_repo: Path,
                                                 tmp_path: Path) -> None:
    """Дерево без метки — чужая работа: имя под тем же префиксом ничего
    не меняет. Ни каталог, ни файлы, ни регистрация не трогаются."""
    home = _sandbox(tmp_path)
    head = _git(["rev-parse", f"origin/{BRANCH}"], cwd=shift_repo).stdout.strip()
    foreign = _stale_tree(shift_repo, home,
                          f"rusterm-relay-verify-{head[:7]}-NO-STAMP-1-1",
                          head, None)

    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert foreign.exists(), "verify снёс дерево без метки"
    assert (foreign / "notes.txt").read_text(encoding="utf-8") == \
        "осталось после прогона\n"
    assert str(foreign) not in proc.stdout, proc.stdout


def test_stamped_tree_with_a_live_pid_survives(shift_repo: Path,
                                               tmp_path: Path) -> None:
    """Метка есть, но pid жив (тест-процесс) — дерево занято чужим
    прогоном, и объезд его не трогает: правило «whose pid is dead»."""
    home = _sandbox(tmp_path)
    head = _git(["rev-parse", f"origin/{BRANCH}"], cwd=shift_repo).stdout.strip()
    busy = _stale_tree(shift_repo, home,
                       f"rusterm-relay-verify-{head[:7]}-ALIVEPID-1-1",
                       head, {"pid": os.getpid(), "run": "живой прогон"})

    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert busy.exists(), "убрано дерево с живым pid"
    assert str(busy) not in proc.stdout, proc.stdout


def test_the_stamp_lies_in_the_tree_and_is_not_trash(shift_repo: Path,
                                                     tmp_path: Path) -> None:
    """Метка есть в дереве во время прогона и не видна как мусор.

    Живой прогон (`verify` на настоящей ветке, 2026-09-25T19:18Z) этим
    красным и начался: `?? .relay-verify-owner` давал провал пункта 13
    «нет мусора вне git», а вместе с ним краснели оба случая I5 — их
    вложенный selfcheck видит то же самое дерево. Метка пункту H3
    обязательна, поэтому она спрятана в `.gitignore`; песочница получает
    СТРОКУ репозитория дословно, так что зуб ломается вместе с ней.
    """
    home = _sandbox(tmp_path)
    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "МЕТКА: есть" in proc.stdout, proc.stdout
    listed = [line for line in proc.stdout.splitlines()
              if line.startswith("ВНЕ-GIT:")]
    assert listed, proc.stdout
    assert STAMP not in listed[0], f"метка видна мусором: {listed[0]}"
