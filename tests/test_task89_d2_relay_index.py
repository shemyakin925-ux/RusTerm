"""ТЗ-89 D2: отказ `hand` не оставляет смену круга в индексе.

Корень пропавшего маркера «Эстафета: круг 107» (ТЗ-89 D0, пункт 2):
первая попытка `hand` в круге 106 упала на хуке, а изменённый
`BATON.json` к тому моменту уже лежал в индексе — и следующим обычным
коммитом (`f8534a4`, «Координатор: …») уехал под чужим заголовком.
Круг остался без маркера, граница окна — без нижней границы.

Правило D2: после ЛЮБОГО отказа `hand` индекс и рабочее дерево для
`agent/BATON.json` совпадают с `HEAD`. Либо смена круга уехала маркером
«Эстафета: …», либо её нет — третьего не бывает.

Песочница — локальный голый «origin» в `tmp_path` (сети нет, бюджеты
круга соблюдены). `agent/acceptance.sh` в песочнице НЕ кладётся: ТЗ-66 L1
делает её опциональной по наличию скрипта, иначе каждый прогон тянул бы
весь набор тестов. Хуки, отвергающие коммит и пуш — настоящие `.git/
hooks`, потому что именно на них круг 106 и споткнулся.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

RELAY = Path(__file__).resolve().parents[1] / "agent" / "relay.py"
BATON = "agent/BATON.json"
BRANCH = "agent/night-d2"

LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")

# средние координаты: круг 9, ход у исполнителя
INITIAL_BATON = {"holder": "executor", "round": 9,
                 "task": "agent/TASK-89.md", "report": "agent/REPORT-89.md",
                 "note": ""}


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    env.update(extra)
    return env


def _git(args: list[str], cwd: Path, **extra: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True, env=_env(**extra)).stdout


@pytest.fixture()
def shift(tmp_path: Path) -> Path:
    """Голый origin с веткой смены + клон, в котором эта ветка checkout'а.

    Ветка должна быть текущей: `push_baton` идёт плюмбингом, если смена
    выкачана НЕ в этом дереве, а дыра D2 — в ветке рабочего дерева.
    """
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-q", str(origin)], cwd=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    (work / "agent").mkdir(exist_ok=True)
    (work / BATON).write_text(json.dumps(INITIAL_BATON, ensure_ascii=False,
                                         indent=1) + "\n", encoding="utf-8")
    (work / "agent" / "REPORT-89.md").write_text("# REPORT-89\n\n## Done\n",
                                                 encoding="utf-8")
    _git(["checkout", "-q", "-B", BRANCH], cwd=work)
    _git(["add", "-A"], cwd=work)
    _git(["commit", "-q", "-m", "круг 9: заготовка смены"], cwd=work)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], cwd=work)
    _git(["fetch", "-q", "origin"], cwd=work)
    _git(["branch", "--set-upstream-to", f"origin/{BRANCH}", BRANCH], cwd=work)
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=work).strip() == BRANCH
    return work


def _hook(work: Path, name: str, body: str) -> None:
    path = work / ".git" / "hooks" / name
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)


def _hand(work: Path) -> subprocess.CompletedProcess:
    """Тот же вызов, что делает исполнитель на сдаче, только в песочнице."""
    return subprocess.run(
        ["python3", str(RELAY), "--branch", BRANCH, "hand",
         "--to", "coordinator", "--report", "agent/REPORT-89.md",
         "--add", "agent/REPORT-89.md", "--note", "сдача D2"],
        cwd=str(work), capture_output=True, text=True, env=_env())


def _staged_baton(work: Path) -> str:
    return _git(["diff", "--cached", "--name-only", "--", BATON], cwd=work)


def _vs_head_baton(work: Path) -> str:
    """И индекс, и рабочее дерево против HEAD — что требует D2."""
    return _git(["diff", "HEAD", "--name-only", "--", BATON], cwd=work)


def _baton_on_origin(work: Path) -> dict:
    _git(["fetch", "-q", "origin"], cwd=work)
    return json.loads(_git(["show", f"origin/{BRANCH}:{BATON}"], cwd=work))


# ── зуб 1: хук отверг коммит (это и есть круг 106) ───────────────────────


def test_a_rejected_commit_leaves_no_baton_change_in_the_index(shift: Path):
    """Отказ коммита обязан откатить `agent/BATON.json` к HEAD: и в
    индексе, и в дереве. До правки здесь оставалась смена круга
    (round 9 -> 10, holder executor -> coordinator) — ровно то, что в
    круге 107 уехало под коммитом координатора."""
    _hook(shift, "pre-commit", 'echo "хук отверг коммит" >&2\nexit 1\n')

    proc = _hand(shift)

    assert proc.returncode != 0, f"hand не отказал: {proc.stdout}"
    assert _staged_baton(shift) == "", (
        "отказ hand оставил смену круга в индексе: "
        f"{_staged_baton(shift)!r}")
    assert _vs_head_baton(shift) == "", (
        "отказ hand оставил BATON.json изменённым против HEAD: "
        f"{_vs_head_baton(shift)!r}")
    assert json.loads((shift / BATON).read_text(encoding="utf-8")) \
        == INITIAL_BATON, "рабочее дерево BATON.json разошлось с HEAD"
    # и главное: ход НЕ передан
    assert _baton_on_origin(shift)["holder"] == "executor"


# ── зуб 2: чужое в индексе — отказ до всякого add ────────────────────────


def test_a_foreign_staged_path_refuses_hand_without_leaving_the_round(shift: Path):
    """Вторая щель: `die("в индексе лежит чужое")` случается ПОСЛЕ того,
    как relay записал новый BATON в рабочее дерево. Отказ обязан убрать
    и это — иначе следующий обычный коммит забирает смену круга."""
    (shift / "agent" / "other.py").write_text("x = 1\n", encoding="utf-8")
    _git(["add", "--", "agent/other.py"], cwd=shift)

    proc = _hand(shift)

    assert proc.returncode != 0, "hand не отказал на чужом индексе"
    assert "чужое" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr
    assert _vs_head_baton(shift) == "", (
        "BATON.json остался изменённым после отказа про чужой индекс: "
        f"{_vs_head_baton(shift)!r}")


# ── зуб 3: гонка пуша — origin ушёл вперёд во время коммита ──────────────


def test_a_rejected_push_leaves_no_baton_change_against_head(shift: Path,
                                                             tmp_path: Path):
    """Третья щель (тот самый круг 108): коммит состоялся, пуш отбит,
    потому что ветка ушла вперёд. Прежний код снимал коммит
    `reset --mixed HEAD~1` и затем делал `checkout origin/<branch> --
    BATON` — а это кладёт ЧУЖОЙ BATON уже в индекс против нового HEAD.
    Здесь гонка воспроизводится честно: хук двигает ref origin ровно
    между коммитом и пушем."""
    competitor = tmp_path / "competitor"
    competitor.mkdir()
    _git(["clone", "-q", str(tmp_path / "origin.git"), str(competitor),
          "--branch", BRANCH], cwd=tmp_path)
    rival = json.loads((competitor / BATON).read_text(encoding="utf-8"))
    rival.update({"holder": "coordinator", "round": 42})
    (competitor / BATON).write_text(json.dumps(rival, ensure_ascii=False,
                                               indent=1) + "\n",
                                    encoding="utf-8")
    _git(["add", "-A"], cwd=competitor)
    _git(["commit", "-q", "-m", "чужая передача хода (круг 42)"],
         cwd=competitor)
    rival_sha = _git(["rev-parse", "HEAD"], cwd=competitor).strip()
    # объекты соперника обязаны оказаться в origin заранее (под чужим
    # именем), иначе update-ref в хуке падает: «trying to write ref …
    # with nonexistent object» — измерено на второй попытке.
    _git(["push", "-q", "origin", f"{rival_sha}:refs/heads/rival-branch"],
         cwd=competitor)

    # хук пропускает коммит и двигает origin — пуш становится не-фаст-форвардом.
    # GIT_* из хука-родителя обязательны: без unset `git` ниже говорил бы с
    # индексом проверяемого репозитория (измерено: update-ref молча падал,
    # пуш проходил, и тест терял смысл).
    _hook(shift, "pre-commit",
          'unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX '
          'GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n'
          'git --git-dir="%s" update-ref refs/heads/%s %s || exit 1\nexit 0\n'
          % (tmp_path / "origin.git", BRANCH, rival_sha))

    proc = _hand(shift)

    assert proc.returncode != 0, f"hand не отказал на отбитом пуше: {proc.stdout}"
    assert "push отклонён" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr
    assert _staged_baton(shift) == "", (
        "после отбитого пуша в индексе лежит BATON: "
        f"{_staged_baton(shift)!r}")
    assert _vs_head_baton(shift) == "", (
        "после отбитого пуша BATON.json не равен HEAD: "
        f"{_vs_head_baton(shift)!r}")
    # снятый коммит не должен лежать и в истории
    assert "круг 42" not in _git(["log", "--format=%s", "-3"], cwd=shift)


# ── контроль: успешная сдача по-прежнему уезжает ─────────────────────────


def test_the_plumbing_path_refuses_without_leaving_anything(shift: Path):
    """Четвёртый путь отказа — координаторский (`push_baton` плюмбингом,
    когда смена выкачана НЕ в этом дереве). Он собирается во временном
    индексе и по построению не может оставить смену круга, но D2 говорит
    «после ЛЮБОГО отказа» — значит это надо показать, а не подразумевать.
    Отказ здесь: `--add` называет файл, которого нет в дереве."""
    _git(["checkout", "-q", "-B", "main"], cwd=shift)
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=shift).strip() \
        != BRANCH

    proc = subprocess.run(
        ["python3", str(RELAY), "--branch", BRANCH, "hand",
         "--to", "coordinator", "--add", "agent/REPORT-нет-такого.md",
         "--note", "координаторская попытка"],
        cwd=str(shift), capture_output=True, text=True, env=_env())

    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "нечего добавить" in (proc.stdout + proc.stderr)
    assert _staged_baton(shift) == "" and _vs_head_baton(shift) == ""
    assert _baton_on_origin(shift)["holder"] == "executor"


def test_a_successful_hand_still_moves_the_baton(shift: Path):
    """Откат работает только на отказе: удачный `hand` обязан поставить
    маркер и перенести ход — иначе починка D2 запирает эстафету."""
    proc = _hand(shift)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    on_origin = _baton_on_origin(shift)
    assert on_origin["holder"] == "coordinator" and on_origin["round"] == 10, \
        on_origin
    assert _staged_baton(shift) == "" and _vs_head_baton(shift) == ""
