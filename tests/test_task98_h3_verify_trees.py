"""ТЗ-98 H3: verify убирает только свои деревья.

Дерево приёмки ставится под общим /tmp и раньше переживало прогон:
убитый посредине процесс оставлял его там навсегда, и деревьев копилось
сколько угодно (кандидат 3 из REPORT-88, одобрен кругом 126). Каждое
созданное прогоном дерево помечено, снимается после зелёного прогона,
красное остаётся для разбора и уходит в начале следующего (`verify`,
ТЗ-100 K2), а осевшие СВОИ деревья с мёртвым pid выметаются тем же
объездом. Дерево без метки не удаляется ни при каком pid: под общим /tmp
чужая работа отличается от мусора только меткой.

ТЗ-100 K3: метка — сосед дерева (`<дерево>.owner`), а не файл внутри
него. Внучатый selfcheck пункта 13 приёмки («нет мусора вне git») видит
дерево целиком, и прятавшаяся в `.gitignore` метка красила его, стоило
строке исчезнуть; дерево, в которое verify ничего не пишет, такому
красному не бывает.

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
# К3 (ТЗ-100): метка владельца — сосед дерева, `<дерево>.owner`; внутрь
# дерева verify не пишет ничего, и прежней метки там быть не должно.
OWNER_SUFFIX = ".owner"
STAMP_IN_TREE = ".relay-verify-owner"

# Как в test_relay_verify_worktree (ТЗ-46): чужой временный индекс и
# чужой путь дерева по умолчанию в песочницу не просачиваются.
LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
          "RUSTERM_RELAY_VERIFY_DIR")

# Заглушка приёмки докладывает то, на что смотрит настоящий пункт 13
# (`git status --porcelain`), соседнюю метку дерева и любой файл метки
# внутри дерева: метка обязана быть рядом с деревом во время прогона и
# не быть внутри него — тогда и `git status` пуст без всякой строки в
# .gitignore.
GREEN = ("#!/usr/bin/env bash\n"
         "echo ЗАГЛУШКА-ПРИЁМКИ: зелёная\n"
         "name=$(basename \"$PWD\")\n"
         "test -f \"../$name.owner\" && echo МЕТКА: есть || echo МЕТКА: нет\n"
         f"test -e {STAMP_IN_TREE} && echo ВНУТРИ: есть || echo ВНУТРИ: нет\n"
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
    # НАСТОЯЩИЙ .gitignore репозитория, дословно: пустота дерева
    # доказывается теми же строками, что и в рабочем дереве смены, —
    # после К3 среди них нет исключений для метки.
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


def _owner_file(tree: Path) -> Path:
    """Сосед дерева по К3: `<дерево>.owner` в том же каталоге-родителе."""
    return tree.parent / (tree.name + OWNER_SUFFIX)


def _stale_tree(work: Path, home: Path, name: str, head: str,
                owner: dict | None) -> Path:
    """Осевшее дерево: зарегистрированное `worktree add`, с соседней
    меткой или без неё."""
    tree = home / "tmp" / name
    _git(["worktree", "add", "--detach", str(tree), head], cwd=work)
    if owner is not None:
        _owner_file(tree).write_text(json.dumps(owner) + "\n",
                                     encoding="utf-8")
    (tree / "notes.txt").write_text("осталось после прогона\n",
                                    encoding="utf-8")
    return tree


def test_green_run_removes_the_tree_it_created(shift_repo: Path,
                                               tmp_path: Path) -> None:
    """Зелёный прогон: дерево стояло под TMPDIR, приёмка прошла, дерева
    нет — ни каталога, ни записи о рабочем дереве, ни соседней метки."""
    home = _sandbox(tmp_path)
    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    tree = _printed_tree(proc)
    assert tree.parent == home / "tmp"
    assert "ЗАГЛУШКА-ПРИЁМКИ: зелёная" in proc.stdout, proc.stdout
    assert not tree.exists(), f"дерево приёмки осталось: {tree}"
    assert str(tree) not in _worktrees(shift_repo)
    assert "убрано после прогона" in proc.stdout, proc.stdout
    assert "дерево оставлено" not in proc.stdout, proc.stdout
    assert not _owner_file(tree).exists(), \
        f"соседняя метка пережила зелёный прогон: {_owner_file(tree)}"


def test_red_run_keeps_its_tree_and_names_it_last(shift_repo: Path,
                                                  tmp_path: Path) -> None:
    """Красный прогон дерево НЕ убирает: на нём разбираются, и путь к
    нему — последняя строка вывода (ТЗ-100 K2). Регистрация рабочего
    дерева остаётся вместе с каталогом: следующий прогон снимает и то,
    и другое тем же объездом Х3."""
    home = _sandbox(tmp_path)
    proc = _verify(shift_repo, home)
    assert proc.returncode == 5, proc.stdout + proc.stderr
    tree = _printed_tree(proc)
    assert "ЗАГЛУШКА-ПРИЁМКИ: красная" in proc.stdout, proc.stdout
    assert tree.exists(), f"красное дерево убрано: {tree}"
    assert str(tree) in _worktrees(shift_repo)
    assert proc.stdout.rstrip().endswith(
        f"дерево оставлено для разбора: {tree} — удалит следующий verify"), \
        proc.stdout
    assert "убрано после прогона" not in proc.stdout, proc.stdout
    owner = _owner_file(tree)
    assert owner.exists(), f"красное дерево осталось без соседней метки: {owner}"
    assert json.loads(owner.read_text(encoding="utf-8"))["run"] == tree.name


def test_the_next_run_removes_a_tree_left_by_a_red_one(shift_repo: Path,
                                                       tmp_path: Path) -> None:
    """Обещание последней строки держит следующий прогон: осевшее дерево
    первого прогона снято (метка verify, pid мёртв — объезд Х3 в начале
    `verify`), а своё красное дерево этого прогона ещё занято разбором."""
    home = _sandbox(tmp_path)
    first = _verify(shift_repo, home)
    assert first.returncode == 5, first.stdout + first.stderr
    kept = _printed_tree(first)
    assert kept.exists(), f"первый прогон не оставил дерево: {kept}"

    second = _verify(shift_repo, home)
    assert second.returncode == 5, second.stdout + second.stderr
    assert not kept.exists(), f"осевшее красное дерево не убрано: {kept}"
    assert str(kept) in second.stdout, second.stdout
    assert str(kept) not in _worktrees(shift_repo)
    assert not _owner_file(kept).exists(), \
        f"метка убранного дерева осталась: {_owner_file(kept)}"
    assert _printed_tree(second).exists(), "своё красное дерево убрано"


def test_a_red_run_in_a_foreign_tree_promises_nothing(shift_repo: Path,
                                                      tmp_path: Path) -> None:
    """Явно данное чужое дерево красным прогоном остаётся на месте, и
    `verify` не обещает, что его удалит следующий прогон: убирать чужое
    дерево у объезда Х3 нет ни права, ни метки."""
    home = _sandbox(tmp_path)
    head = _git(["rev-parse", f"origin/{BRANCH}"], cwd=shift_repo).stdout.strip()
    foreign = home / "own-tree"
    _git(["worktree", "add", "--detach", str(foreign), head], cwd=shift_repo)

    proc = _verify(shift_repo, home, ["--worktree", str(foreign)])
    assert proc.returncode == 5, proc.stdout + proc.stderr
    assert foreign.exists(), f"чужое дерево убрано: {foreign}"
    assert str(foreign) in _worktrees(shift_repo)
    assert "дерево оставлено" not in proc.stdout, proc.stdout
    assert "убрано после прогона" not in proc.stdout, proc.stdout
    # К3: чужое дерево — ничего не написано ни в него, ни рядом
    assert not (foreign / STAMP_IN_TREE).exists(), "метка внутри чужого дерева"
    assert not _owner_file(foreign).exists(), "метка рядом с чужим деревом"


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
    assert not _owner_file(stale).exists(), \
        f"метка убранного дерева не снята: {_owner_file(stale)}"
    # дерево самого прогона убирается тем же путём
    assert not _printed_tree(proc).exists()


def test_an_orphan_owner_stamp_is_swept_too(shift_repo: Path,
                                            tmp_path: Path) -> None:
    """Метка без дерева — то же осевшее своё: каталог сняли, а соседний
    файл остался (или его бросил убитый между `worktree add` и штампом
    процесс). Следующий прогон убирает и его, чужие файлы и метки живого
    прогона не трогая."""
    home = _sandbox(tmp_path)
    head = _git(["rev-parse", f"origin/{BRANCH}"], cwd=shift_repo).stdout.strip()
    gone = home / "tmp" / f"rusterm-relay-verify-{head[:7]}-ORPHAN-1-1"
    orphan = _owner_file(gone)
    orphan.write_text(json.dumps({"pid": _dead_pid(), "run": gone.name}) + "\n",
                      encoding="utf-8")
    other = home / "tmp" / "kakaya-to-sveshaya.owner"
    other.write_text("не наше\n", encoding="utf-8")
    busy = _owner_file(home / "tmp"
                       / f"rusterm-relay-verify-{head[:7]}-ORPHANALIVE-2-2")
    busy.write_text(json.dumps({"pid": os.getpid(), "run": busy.name}) + "\n",
                    encoding="utf-8")

    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not orphan.exists(), f"осевшая метка не убрана: {orphan}"
    assert other.exists(), "verify прибрал чужой файл с расширением .owner"
    assert busy.exists(), "убрана метка orphan с живым pid"


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
    assert _owner_file(busy).exists(), "метка живого прогона убрана"
    assert str(busy) not in proc.stdout, proc.stdout


def test_the_stamp_is_a_sibling_and_nothing_lands_in_the_tree(
        shift_repo: Path, tmp_path: Path) -> None:
    """Метка стоит РЯДОМ с деревом, внутри дерева её нет, и `git status
    --porcelain` в дереве пуст без всякого исключения в `.gitignore`.

    Живой прогон (`verify` на настоящей ветке, 2026-09-25T19:18Z) начался
    красным ровно наоборот: `?? .relay-verify-owner` в дереве давал
    провал пункта 13 «нет мусора вне git», а вместе с ним краснели оба
    случая I5 — их вложенный selfcheck видит то же самое дерево. Метку
    тогда спрятали в `.gitignore`, и зуб ловил её возвращение только
    пока строка там жила. К3 убирает и строку, и сам файл: пустое дерево
    нечего прятать.
    """
    home = _sandbox(tmp_path)
    proc = _verify(shift_repo, home)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "МЕТКА: есть" in proc.stdout, proc.stdout
    assert "ВНУТРИ: нет" in proc.stdout, proc.stdout
    listed = [line for line in proc.stdout.splitlines()
              if line.startswith("ВНЕ-GIT:")]
    assert listed, proc.stdout
    assert listed[0].strip() == "ВНЕ-GIT:", f"в дереве мусор: {listed[0]}"
    leftovers = sorted(p.name for p in (home / "tmp").iterdir())
    assert leftovers == [], f"в песочнице /tmp что-то осталось: {leftovers}"


def test_the_repo_gitignore_no_longer_hides_an_in_tree_stamp(
        tmp_path: Path) -> None:
    """Строка `.relay-verify-owner` из `.gitignore` вынута вместе с
    файлом: оставить её — значит заранее разрешить писать в дерево
    приёмки мусор, который никто не проверяет."""
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert STAMP_IN_TREE not in text, "в .gitignore вернулась метка дерева"
    assert "relay-verify-owner" not in text
