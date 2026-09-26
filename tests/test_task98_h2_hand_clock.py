"""ТЗ-98 H2 в переборе ТЗ-100 K1: часы больше не сторож сдачи.

Прежнее правило H2: `updated_at` в `agent/STATE.json` расходится с
настоящим временем больше чем на 15 минут (допуск O0) — `hand` отказывает
до приёмки. Работало ровно до ТЗ-99 J1, который сам `hand` и научил эти
часы писать: проверка начала блокировать ту передачу, которая её и
чинит. Круг 129 это показал живьём: отказ на +18.9 мин при честных часах
предыдущей смены — STATE писали за 19 минут до сдачи.

Новое правило (K1): расхождение часов — не отказ, любые прежние значения
`updated_at` штамп перетирает. Отказывает только нештамбуемый STATE — это
в соседнем модуле `tests/test_task100_k1_stampable_state.py`, и зубы тут с
ним не дублируются: здесь часы, там разбираемость.

O0 в `agent/selfcheck.sh` не тронут (запрет ТЗ-100), и
`tests/test_state_clock.py` тоже: его аргумент — про разбор и форму
сообщения на синтетических часах.

Песочница — локальный голый «origin» в `tmp_path` (сети нет, бюджеты
круга соблюдены). `agent/acceptance.sh` — заглушка, которая пишет себе в
лог-файл: именно её наличие/отсутствие и есть доказательство «отказ ДО
приёмки» — а теперь доказательство того, что отказа не было.
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
BRANCH = "agent/night-h2"
RAN = ".acceptance-ran"

INITIAL_BATON = {"holder": "executor", "round": 12,
                 "task": "agent/TASK-98.md", "report": "agent/REPORT-98.md",
                 "note": ""}

# поля прежней смены — их штамп обязан перевезти нетронутыми
PREV = {"task": "agent/TASK-97.md", "report": "agent/REPORT-97.md",
        "item": "H2", "status": "awaiting_review", "requests": 21,
        "net_requests": 20, "llm_calls": 1,
        "model": "Qoder executor (model id not exposed)"}

# заглушка приёмки: зелёная, но оставляет след — по нему и видно,
# запускалась она или нет
STUB_ACCEPTANCE = ('#!/usr/bin/env bash\n'
                   'printf "ran\\n" >> ' + RAN + '\n'
                   'exit 0\n')

LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")

# текст отказа прежнего H2 — теперь он обязан НЕ появляться ни в одном
# выводе: возврат к сверке часов красит эти зубы, а не прячет их
DRIFT_WORDS = ("расходится с реальным", "допуск 15", "не ISO-8601",
               "без часового пояса", "нет updated_at")


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    env.update(extra)
    return env


def _git(args: list[str], cwd: Path, **extra: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True, env=_env(**extra)).stdout


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _minutes_ago(minutes: int) -> str:
    """Часы относительно ЭТОГО теста, а не момента импорта модуля
    (выражение уровня модуля протухло бы до полного прогона)."""
    return _stamp(datetime.now(timezone.utc) - timedelta(minutes=minutes))


def _write_state(work: Path, updated_at: object, **extra: object) -> None:
    body: dict = {**PREV, **extra}
    if updated_at is not _NO_CLOCK:
        body["updated_at"] = updated_at
    (work / STATE).write_text(json.dumps(body, ensure_ascii=False, indent=1)
                              + "\n", encoding="utf-8")


class _NoClock:
    pass


_NO_CLOCK = _NoClock()


def _hand(work: Path, force: bool = False) -> subprocess.CompletedProcess:
    """Тот же вызов, что делает исполнитель на сдаче, в песочнице."""
    argv = ["python3", str(RELAY), "--branch", BRANCH, "hand",
            "--to", "coordinator", "--report", "agent/REPORT-98.md",
            "--add", STATE]
    if force:
        argv += ["--force"]
    return subprocess.run(argv + ["--note", "сдача H2"], cwd=str(work),
                          capture_output=True, text=True, env=_env())


def _baton_on_origin(work: Path) -> dict:
    _git(["fetch", "-q", "origin"], cwd=work)
    return json.loads(_git(["show", f"origin/{BRANCH}:{BATON}"], cwd=work))


def _state_on_origin(work: Path) -> dict:
    _git(["fetch", "-q", "origin"], cwd=work)
    return json.loads(_git(["show", f"origin/{BRANCH}:{STATE}"], cwd=work))


def _acceptance_ran(work: Path) -> bool:
    return (work / RAN).exists()


def _clock_is_live(raw: str) -> bool:
    return abs((datetime.now(timezone.utc)
                - datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)).total_seconds()) <= 120


def _assert_handed(work: Path, proc: subprocess.CompletedProcess) -> dict:
    """Общая для всех часов проверка: отказа не было, приёмка состоялась,
    ход уехал, а в коммите лежат живые часы и прежние поля смены."""
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"hand отказал из-за часов: {combined}"
    for word in DRIFT_WORDS:
        assert word not in combined, f"{word!r} в выводе — сверка часов вернулась"
    assert "поверх просроченных часов" not in combined, (
        "вывод зовёт --force там, где обходить больше нечего")
    assert _acceptance_ran(work), "заглушка приёмки не вызвана"
    on_origin = _baton_on_origin(work)
    assert on_origin["holder"] == "coordinator", on_origin
    assert on_origin["round"] == 13, on_origin
    state = _state_on_origin(work)
    assert _clock_is_live(state["updated_at"]), state["updated_at"]
    assert state["status"] == "handed", state
    for key in PREV:
        if key not in ("task", "report", "status", "updated_at"):
            assert state[key] == PREV[key], (key, state)
    return state


# ── зуб 1: 44 минуты просрочки — больше не отказ ─────────────────────────


def test_a_state_44_minutes_old_hands_and_gets_a_live_clock(shift: Path):
    """Бывший красный случай H2: прежний код отвечал «ход не передан,
    приёмка не запускалась» и требовал --force."""
    _write_state(shift, _minutes_ago(44))

    _assert_handed(shift, _hand(shift))
    # штамп живёт не только в коммите: то, на что смотрит приходящая
    # сторона в этом же дереве, — файл дерева
    tree = json.loads((shift / STATE).read_text(encoding="utf-8"))
    assert _clock_is_live(tree["updated_at"]), tree["updated_at"]
    assert tree["status"] == "handed", tree


# ── зуб 2: часы в будущем — тоже не отказ ────────────────────────────────


def test_a_clock_44_minutes_ahead_hands_too(shift: Path):
    """Прежний H2 брал |drift|, поэтому метка на 44 минуты вперёд красила
    сдачу так же. K1 на часы не смотрит: он их перетирает."""
    ahead = _stamp(datetime.now(timezone.utc) + timedelta(minutes=44))
    _write_state(shift, ahead)

    state = _assert_handed(shift, _hand(shift))
    assert state["updated_at"] != ahead, "в коммит уехали чужие часы"
    # J1: STATE зеркалит BATON этой сдачи — часы для этого не сторож
    assert state["task"] == "agent/TASK-98.md", state
    assert state["report"] == "agent/REPORT-98.md", state


# ── зуб 3: 500 минут — число из Done-when ТЗ-100 K1 ──────────────────────


def test_a_state_500_minutes_old_hands_without_force(shift: Path):
    """Буквально Done-when K1: обычный `hand` без `--force` проходит, и в
    коммите — свежий `updated_at`."""
    _write_state(shift, _minutes_ago(500))

    _assert_handed(shift, _hand(shift))


# ── зуб 4: неразбираемое значение часов — не отказ, а чистый лист ────────


def test_an_unparsable_clock_value_is_stamped_over(shift: Path):
    """Прежний H2 красил этот случай («не ISO-8601»). Теперь это просто
    значение поля: объект валиден, значит штамп ложится."""
    _write_state(shift, "вчера после обеда")

    state = _assert_handed(shift, _hand(shift))
    assert state["updated_at"] != "вчера после обеда", state
    assert "вчера после обеда" not in json.dumps(state, ensure_ascii=False), state


# ── зуб 5: часов нет вовсе — штамп их заводит ────────────────────────────


def test_a_state_without_a_clock_gets_one(shift: Path):
    """Прежний отказ «в agent/STATE.json нет updated_at» снимается: поле
    появляется коммитом эстафеты, а не требованием к исполнителю."""
    _write_state(shift, _NO_CLOCK)
    assert "updated_at" not in json.loads((shift / STATE).read_text(
        encoding="utf-8"))

    state = _assert_handed(shift, _hand(shift))
    assert _clock_is_live(state["updated_at"]), state


# ── зуб 6: свежие часы — путь цел, и он не изменился ─────────────────────


def test_a_fresh_state_reaches_acceptance_and_hands(shift: Path):
    """Единственный зуб прежнего модуля, переживший перебор: при честных
    часах hand шёл и раньше — здесь он обязан идти и теперь."""
    _write_state(shift, _minutes_ago(1))

    _assert_handed(shift, _hand(shift))


# ── зуб 7: --force больше не нужен для часов, но и не молчит по делу ─────


def test_force_is_not_required_for_a_stale_clock_and_stays_silent(shift: Path):
    """Раньше `--force` был штатным выходом поверх просроченных часов.
    Теперь у часов нет чего обходить — значит и строки об этом в выводе
    быть не должно: разрешённый путь не притворяется исключением (зуб 1
    доказывает, что без `--force` тот же результат)."""
    _write_state(shift, _minutes_ago(44))

    proc = _hand(shift, force=True)
    state = _assert_handed(shift, proc)
    combined = proc.stdout + proc.stderr
    assert "force" not in combined.lower(), combined
    assert state["status"] == "handed", state


# ── песочница ────────────────────────────────────────────────────────────


@pytest.fixture()
def shift(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-q", str(origin)], cwd=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    (work / "agent").mkdir(exist_ok=True)
    (work / BATON).write_text(json.dumps(INITIAL_BATON, ensure_ascii=False,
                                         indent=1) + "\n", encoding="utf-8")
    (work / "agent" / "REPORT-98.md").write_text("# REPORT-98\n\n## Done\n",
                                                 encoding="utf-8")
    (work / "agent" / "acceptance.sh").write_text(STUB_ACCEPTANCE,
                                                  encoding="utf-8")
    _git(["checkout", "-q", "-B", BRANCH], cwd=work)
    _git(["add", "-A"], cwd=work)
    _git(["commit", "-q", "-m", "круг 12: заготовка смены"], cwd=work)
    _git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], cwd=work)
    _git(["fetch", "-q", "origin"], cwd=work)
    _git(["branch", "--set-upstream-to", f"origin/{BRANCH}", BRANCH],
         cwd=work)
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=work).strip() \
        == BRANCH
    return work
