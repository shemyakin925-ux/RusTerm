"""ТЗ-98 H2: просроченный `updated_at` нельзя сдать.

O0 в `agent/selfcheck.sh` сверяет часы STATE.json с настоящими, но
только `[ -z "${I5_NESTED:-}" ]`, а `agent/githooks/pre-commit` зовёт
selfcheck именно с `I5_NESTED=1` — то есть ни один коммит-путь часы не
проверяет (замер круга 124, upheld в TASK-98 как H2). `relay.py hand`
берёт проверку на себя: отказ до запуска приёмки, rc≠0, words + команда
починки. Допуск тот же, что у O0 — 15 минут.

O0 здесь НЕ трогается (запрет ТЗ-98), и `tests/test_state_clock.py`
тоже: его аргумент — про разбор и форму сообщения, а живые часы в нём
сравнены быть не могут. Здесь живое сравнение законно: `hand` идёт там
же и тогда же, где писали STATE, а не часами позже в свежем дереве
координатора.

Песочница — локальный голый «origin» в `tmp_path` (сети нет, бюджеты
круга соблюдены). `agent/acceptance.sh` — заглушка, которая пишет себе
в лог-файл: именно её наличие/отсутствие и есть доказательство «отказ
ДО приёмки».
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

# заглушка приёмки: зелёная, но оставляет след — по нему и видно,
# запускалась она или нет
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


def _git(args: list[str], cwd: Path, **extra: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True, env=_env(**extra)).stdout


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_state(work: Path, updated_at: str | None) -> None:
    body: dict = {"task": "agent/TASK-98.md", "report": "agent/REPORT-98.md",
                  "item": "H2", "status": "awaiting_review"}
    if updated_at is not None:
        body["updated_at"] = updated_at
    (work / STATE).write_text(json.dumps(body, ensure_ascii=False, indent=1)
                              + "\n", encoding="utf-8")


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


def _hand(work: Path, add_state: bool = True,
         force: bool = False) -> subprocess.CompletedProcess:
    """Тот же вызов, что делает исполнитель на сдаче, в песочнице."""
    argv = ["python3", str(RELAY), "--branch", BRANCH, "hand",
            "--to", "coordinator", "--report", "agent/REPORT-98.md"]
    if add_state:
        argv += ["--add", STATE]
    if force:
        argv += ["--force"]
    return subprocess.run(argv + ["--note", "сдача H2"], cwd=str(work),
                          capture_output=True, text=True, env=_env())


def _baton_on_origin(work: Path) -> dict:
    _git(["fetch", "-q", "origin"], cwd=work)
    return json.loads(_git(["show", f"origin/{BRANCH}:{BATON}"], cwd=work))


def _acceptance_ran(work: Path) -> bool:
    return (work / RAN).exists()


# ── зуб 1: 44 минуты просрочки — отказ, и приёмка не запускалась ─────────


def test_a_state_44_minutes_old_refuses_hand_before_acceptance(shift: Path):
    stale = _stamp(datetime.now(timezone.utc) - timedelta(minutes=44))
    _write_state(shift, stale)

    proc = _hand(shift)
    combined = proc.stdout + proc.stderr

    assert proc.returncode != 0, f"hand не отказал: {combined}"
    assert not _acceptance_ran(shift), (
        "отказ по часам случился ПОСЛЕ запуска приёмки — порядок нарушен")
    assert f"updated_at={stale}" in combined, combined
    assert "расходится с реальным" in combined, combined
    assert "допуск 15" in combined, combined
    # и слова, и команда починки
    assert "починить" in combined and "python3 - <<" in combined, combined
    # ход не передан
    on_origin = _baton_on_origin(shift)
    assert on_origin["holder"] == "executor"
    assert on_origin["round"] == 12


# ── зуб 2: свежие часы — hand идёт дальше и доходит до приёмки ───────────


def test_a_fresh_state_reaches_acceptance_and_hands(shift: Path):
    _write_state(shift, _stamp(datetime.now(timezone.utc)))

    proc = _hand(shift)
    combined = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined
    assert _acceptance_ran(shift), "заглушка приёмки не вызвана при свежих часах"
    on_origin = _baton_on_origin(shift)
    assert on_origin["holder"] == "coordinator"
    assert on_origin["round"] == 13


# ── зуб 3: метка вне допуска и в будущем — тот же отказ ──────────────────


def test_a_clock_ahead_of_reality_refuses_too(shift: Path):
    """O0 берёт |drift|, а не «опоздание»: метка на 44 минуты вперёд —
    это ручная правка часов, и она так же не доказательство жизни."""
    ahead = _stamp(datetime.now(timezone.utc) + timedelta(minutes=44))
    _write_state(shift, ahead)

    proc = _hand(shift)
    combined = proc.stdout + proc.stderr

    assert proc.returncode != 0, combined
    assert not _acceptance_ran(shift)
    assert f"updated_at={ahead}" in combined, combined
    assert "приёмка не запускалась" in combined, combined


# ── зуб 4: разбирается с мусором и молчит там, где STATE нет ─────────────


def test_an_unparsable_stamp_refuses_and_a_missing_state_does_not(shift: Path):
    _write_state(shift, "вчера после обеда")
    proc = _hand(shift)
    assert proc.returncode != 0, "hand принял неразбираемый updated_at"
    assert not _acceptance_ran(shift)
    assert "не ISO-8601" in proc.stdout + proc.stderr

    # без STATE.json в дереве — это песочница, а не сдача: проверка не
    # мешает (иначе каждый unit-тест relay обязан был бы писать часы)
    (shift / STATE).unlink()
    (shift / RAN).unlink(missing_ok=True)
    proc = _hand(shift, add_state=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _acceptance_ran(shift)


# ── зуб 5: --force — выход, но не молчание ───────────────────────────────


def test_force_overrides_a_stale_clock_out_loud(shift: Path):
    """Координатор сдаёт ход часами позже, чем исполнитель писал STATE,
    и идёт тем же `cmd_hand`: без выхода у H2 был бы сломан его путь.
    Выход — `--force`, и он обязан быть слышен, а не молчать (ТЗ-79 Z2
    про то же: разрешение без строки в выводе — это дыра)."""
    stale = _stamp(datetime.now(timezone.utc) - timedelta(minutes=44))
    _write_state(shift, stale)

    proc = _hand(shift, force=True)
    combined = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined
    assert "--force поверх просроченных часов" in combined, combined
    assert f"updated_at={stale}" in combined, combined
    assert _acceptance_ran(shift)
    assert _baton_on_origin(shift)["holder"] == "coordinator"
