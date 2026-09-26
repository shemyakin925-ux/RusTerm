"""ТЗ-100 K1: сторож сдачи смотрит не на часы, а на то, во что ляжет штамп.

После ТЗ-99 J1 сам `hand` пишет `updated_at` (`_hand_state_stamp`), поэтому
проверка ТЗ-98 H2 («часы расходятся больше чем на 15 минут — ход не
передан») блокировала ровно ту передачу, которая эти часы и обновляет: на
круге 129 отказ случился на +18.9 мин. Правило K1: отказ там, где вкладывать
штамп некуда — `agent/STATE.json` есть (в дереве смены или блобом на ветке),
но не сливается с объектом штампа. Просроченные, будущие и мусорные часы
больше не мешают: их hand перетирает, а прежние поля остаются.

Отсутствие STATE — не отказ: терять нечего, `hand` положит свой объект
(так же вело себя и старое H2, и на этом держатся песочницы остальных
тестов relay — `tests/test_j1_hand.py`, `tests/test_task89_d2_relay_index.py`).

Часам посвящён соседний модуль `tests/test_task98_h2_hand_clock.py`; здесь
только разбираемость — зубы не дублируются.

Песочница — локальный голый origin в `tmp_path`: сети нет, бюджеты круга
(network 0, LLM 0) соблюдены, git-транспорт только локальный.
`agent/acceptance.sh` — заглушка, оставляющая след: по наличию следа и
решается «отказ ДО приёмки» или после неё. `HOME` не подменяется (иначе
дочерний процесс теряет user-site).
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RELAY = Path(__file__).resolve().parents[1] / "agent" / "relay.py"
BATON = "agent/BATON.json"
STATE = "agent/STATE.json"
BRANCH = "agent/night-k1"
RAN = ".acceptance-ran"

INITIAL_BATON = {"holder": "executor", "round": 31, "branch": BRANCH,
                 "task": "agent/TASK-100.md", "report": "agent/REPORT-100.md",
                 "note": ""}

# поля прежней смены: штамп обязан их сохранить — он двигает четыре, а не
# переписывает файл
PREV = {"task": "agent/TASK-99.md", "report": "agent/REPORT-99.md",
        "item": "J2", "step": "последний коммит прежней смены",
        "status": "awaiting_review", "last_commit": "1111111",
        "requests": 39, "net_requests": 39, "llm_calls": 0,
        "model": "Qoder executor (model id not exposed)"}

STUB_ACCEPTANCE = ('#!/usr/bin/env bash\n'
                   'printf "ran\\n" >> ' + RAN + '\n'
                   'exit 0\n')

LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    env.update(extra)
    return env


def _git(args: list[str], cwd: Path, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=check, env=_env()).stdout


def _utc(minutes_ago: int) -> str:
    """Часы относительно ЭТОГО теста: выражение уровня модуля вычислилось
    бы при импорте и протухло бы до того, как до модуля дойдёт полный
    прогон (урок круга 129, `tests/test_task99_j1_hand_stamps_state.py`)."""
    return (datetime.now(timezone.utc)
            - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _prev_state(**extra: object) -> dict:
    return {**PREV, "updated_at": _utc(3), **extra}


def _write_state(work: Path, body: object) -> None:
    (work / STATE).parent.mkdir(parents=True, exist_ok=True)
    text = body if isinstance(body, str) else json.dumps(
        body, ensure_ascii=False, indent=1) + "\n"
    (work / STATE).write_text(text, encoding="utf-8")


@pytest.fixture()
def shift(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-q", str(origin)], cwd=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    (work / "agent").mkdir(exist_ok=True)
    _write_state(work, _prev_state())
    (work / BATON).write_text(json.dumps(INITIAL_BATON, ensure_ascii=False,
                                         indent=1) + "\n", encoding="utf-8")
    (work / "agent" / "REPORT-100.md").write_text("# REPORT-100\n\n## Done\n",
                                                 encoding="utf-8")
    (work / "agent" / "acceptance.sh").write_text(STUB_ACCEPTANCE,
                                                  encoding="utf-8")
    _git(["checkout", "-q", "-B", BRANCH], cwd=work)
    _git(["add", "-A"], cwd=work)
    _git(["commit", "-q", "-m", "круг 31: заготовка смены"], cwd=work)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], cwd=work)
    _git(["fetch", "-q", "origin"], cwd=work)
    _git(["branch", "--set-upstream-to", f"origin/{BRANCH}", BRANCH],
         cwd=work)
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=work).strip() \
        == BRANCH
    return work


def _hand(work: Path, add_state: bool = True, force: bool = False
          ) -> subprocess.CompletedProcess:
    """Тот же вызов, что делает исполнитель на сдаче, в песочнице."""
    argv = ["python3", str(RELAY), "--branch", BRANCH, "hand", "--to",
            "coordinator", "--task", "agent/TASK-100.md", "--report",
            "agent/REPORT-100.md"]
    if add_state:
        argv += ["--add", STATE]
    if force:
        argv += ["--force"]
    return subprocess.run(argv + ["--note", "сдача K1"], cwd=str(work),
                          capture_output=True, text=True, env=_env())


def _origin_file(work: Path, rel: str) -> str:
    _git(["fetch", "-q", "origin"], cwd=work)
    return _git(["show", f"origin/{BRANCH}:{rel}"], cwd=work)


def _origin_state(work: Path) -> dict:
    return json.loads(_origin_file(work, STATE))


def _origin_baton(work: Path) -> dict:
    return json.loads(_origin_file(work, BATON))


def _ran(work: Path) -> bool:
    return (work / RAN).exists()


def _clock_age_seconds(raw: str) -> float:
    stamp = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    return abs((datetime.now(timezone.utc) - stamp).total_seconds())


# ── зуб 1: STATE есть, но не разбирается — отказ, и приёмка не была ──────


def test_an_unparsable_state_refuses_before_acceptance(shift: Path):
    _write_state(shift, "{ это не json,,,")

    proc = _hand(shift)
    combined = proc.stdout + proc.stderr

    assert proc.returncode != 0, f"hand проглотил мусор вместо STATE: {combined}"
    assert not _ran(shift), "отказ случился ПОСЛЕ запуска приёмки"
    assert "не разбирается" in combined, combined
    assert "починить" in combined, combined
    # ради чего отказа хватает: поля и счётчики прежней смены
    assert "счётчики" in combined, combined
    assert "ход не передан" in combined, combined
    on_origin = _origin_baton(shift)
    assert on_origin["holder"] == "executor" and on_origin["round"] == 31, \
        on_origin
    # и никаких следов вложенной работы: порченый файл остался порченым
    assert (shift / STATE).read_text(encoding="utf-8").startswith("{ это")


# ── зуб 2: валидный JSON, но не объект — тот же отказ ────────────────────


def test_a_json_array_instead_of_an_object_refuses(shift: Path):
    """`hand` сливает штамп в объект; массив — это не то, во что можно
    вложить четыре поля, и прежний код падал на нём с трейсбеком."""
    _write_state(shift, '["task", "report"]')

    proc = _hand(shift)
    combined = proc.stdout + proc.stderr

    assert proc.returncode != 0, f"hand принял массив вместо объекта: {combined}"
    assert not _ran(shift)
    assert "не объект JSON" in combined, combined
    assert "Traceback" not in combined, combined
    assert _origin_baton(shift)["holder"] == "executor"


# ── зуб 3: STATE отсутствует — не отказ, hand кладёт свой объект ─────────


def test_an_absent_state_is_created_by_hand_and_not_refused(shift: Path):
    """Старое H2 молчало там, где STATE нет, и на этом держатся песочницы
    остальных relay-тестов. K1 это молчание сохраняет: нечего терять —
    нечего и запретить."""
    (shift / STATE).unlink()

    proc = _hand(shift, add_state=False)
    combined = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined
    assert _ran(shift), "приёмка не вызвана — hand отказался раньше, чем надо"
    state = _origin_state(shift)
    assert state["status"] == "handed", state
    assert state["task"] == "agent/TASK-100.md", state
    assert state["report"] == "agent/REPORT-100.md", state
    assert _clock_age_seconds(state["updated_at"]) <= 120, state
    assert _origin_baton(shift)["holder"] == "coordinator"


# ── зуб 4: объект остаётся объектом, даже если поля дикие ────────────────


def test_a_valid_object_with_absurd_fields_still_hands_and_keeps_them(shift: Path):
    """Граница сторожа — разбираемость, а не содержание: мусорные значения
    полей переживают сдачу ровно теми, чем лежали."""
    _write_state(shift, {**PREV, "updated_at": None, "item": 42,
                         "requests": "тридцать девять",
                         "notes": ["a", "b"]})

    proc = _hand(shift)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    state = _origin_state(shift)
    assert state["item"] == 42 and state["requests"] == "тридцать девять", state
    assert state["notes"] == ["a", "b"], state
    assert _clock_age_seconds(state["updated_at"]) <= 120, state


# ── зуб 5: --force поверх нештамбуемого STATE — выход, но слышный ────────


def test_force_over_an_unstampable_state_proceeds_out_loud(shift: Path):
    """Разрешение без строки в выводе — дыра (ТЗ-79 Z2 про то же): выход
    обязан быть слышен и называть, чем пришлось пожертвовать."""
    _write_state(shift, "{ это не json,,,")

    proc = _hand(shift, force=True)
    combined = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined
    assert "--force" in combined, combined
    assert "не разбирается" in combined, combined
    assert _ran(shift), "при --force приёмка обязана состояться"
    assert _origin_baton(shift)["holder"] == "coordinator"
    assert _origin_state(shift)["status"] == "handed"


# ── зуб 6: плюмбинг берёт блоб ветки, а не чужое дерево ──────────────────


def test_plumbing_hand_gates_on_the_branch_blob_not_this_worktree(tmp_path: Path,
                                                                  shift: Path):
    """Координатор ведёт параллельную смену в своём дереве: ветка сдачи не
    выкачана, и `push_baton` идёт плюмбингом, строя STATE из блоба самой
    ветки (ТЗ-99 J1). Сторож обязан смотреть в тот же источник — иначе он
    проверяет файл, который в коммит не поедет."""
    other = tmp_path / "coord"
    _git(["clone", "-q", "--branch", BRANCH, str(tmp_path / "origin.git"),
          str(other)], cwd=tmp_path)
    _git(["checkout", "-q", "-B", "coord/parallel"], cwd=other)
    # своё дерево — целое и свежее: по нему отказывать нельзя
    _write_state(other, {"task": "agent/TASK-OTHER.md", "item": "параллельная",
                         "status": "working", "updated_at": _utc(1)})
    _git(["add", "-A"], cwd=other)
    _git(["commit", "-q", "-m", "параллельная смена координатора"], cwd=other)
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=other).strip() \
        == "coord/parallel"

    # на ветке — порченый STATE; его hand и должен увидеть
    _write_state(shift, "{ это не json,,,")
    _git(["add", "-A"], cwd=shift)
    _git(["commit", "-q", "-m", "порченый STATE на ветке"], cwd=shift)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], cwd=shift)

    proc = _hand(other)
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, (
        f"плюмбинг принял нештамбуемый блоб ветки: {combined}")
    assert not (other / RAN).exists(), "отказ случился ПОСЛЕ запуска приёмки"
    assert f"{BRANCH}:{STATE}" in combined, combined
    assert "не разбирается" in combined, combined
    assert _origin_baton(shift)["holder"] == "executor"
    # своё дерево отказ не тронул: ни штампа, ни отката чужими байтами
    assert json.loads((other / STATE).read_text(
        encoding="utf-8"))["item"] == "параллельная"

    # ветка починена — тот же вызов проходит: сторож не запрет плюмбинга
    _git(["checkout", "-q", BRANCH], cwd=shift)
    _write_state(shift, _prev_state())
    _git(["add", "-A"], cwd=shift)
    _git(["commit", "-q", "-m", "STATE на ветке снова объект"], cwd=shift)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], cwd=shift)

    proc = _hand(other)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (other / RAN).exists()
    state = _origin_state(shift)
    assert state["status"] == "handed" and state["item"] == "J2", state
    assert _origin_baton(shift)["holder"] == "coordinator"
