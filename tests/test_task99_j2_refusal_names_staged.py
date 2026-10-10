"""ТЗ-99 J2: отказ `hand` называет работу, которую он оставил в индексе.

Корень (ТЗ-89 D2, Disputed 2 → решение круга 129 «keep as is»): при
отказе `hand` откатывает `agent/BATON.json` к HEAD, а файлы, вложенные
через `--add`, остаются в индексе — работа не откатывается. Раньше об
этом можно было только догадываться: сообщение говорило про BATON и про
«чужое», но не перечисляло, что именно остаётся в индексе после отказа.

Правило J2: строка «в индексе остались: <files> — это твоя работа, не
откатана». Имена берутся из индекса в момент отказа, а не из аргументов,
поэтому путь отклонённого push (там `reset --mixed` снимает файлы с
индекса) врать про них не будет.

Штамп J1 — второй файл, который `hand` пишет сам, поэтому тот же отказ
возвращает и `agent/STATE.json` (зубья 2–3). Оставлять в индексе вызывающего
`status: "handed"` про несостоявшуюся передачу — та же беда, от которой D2
запрещает держать смену круга: её уносит следующий же коммит.

Зубья:
1. Done-when: отвергающий pre-commit-хук — оба файла `--add` названы,
   BATON в индексе не лежит.
2. Отказ hand снимает и собственный штамп J1: `agent/STATE.json`
   возвращается своими байтами и своим блобом индекса, в строке «остались»
   его нет.
3. Своя правка STATE, положенная в индекс до `hand`, переживает отказ без
   изменений (откат касается только файлов самого `hand`).
4. Отказ из-за чужого в индексе называет свой `--add` и не трогает чужое
   (утверждения D2 остаются в силе).
5. Ранний отказ (стоп-файл, до всякого `git add`) тоже называет то, что
   вызывающий успел положить в индекс.
6. Отказ без `--add` — строки нет.
7. `--add` файл лежит в дереве, но не в индексе — строки нет: она
   обещает только то, что проверяемо по `git diff --cached`.
8. Успешный `hand` не печатает ничего про остатки: строка живёт в отказе,
   а не в конце каждой команды.

Песочница — локальный голый «origin» в `tmp_path` (сети нет, бюджеты
круга соблюдены), окружение вычищено от leaks git-переменных; `TMPDIR`
внутри песочницы, `HOME` не подменяется (тот же замер, что в
`tests/test_task99_j1_hand_stamps_state.py`: с другим `HOME` интерпретатор
теряет user-site). `agent/acceptance.sh` — заглушка: ТЗ-66 L1 делает
живую приёмку опциональной по наличию скрипта.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RELAY = REPO_ROOT / "agent" / "relay.py"

BATON = "agent/BATON.json"
STATE = "agent/STATE.json"
BRANCH = "agent/night-j2"
PHRASE = " — это твоя работа, не откатана"

LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")

STUB_ACCEPTANCE = "#!/usr/bin/env bash\nexit 0\n"
REJECTING_HOOK = "#!/bin/sh\necho 'нет' >&2\nexit 1\n"


def _minutes_ago(minutes: int) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _env(sbx: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                "TMPDIR": str(sbx / "tmp")})
    env.update(extra)
    return env


def _git(sbx: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(sbx), capture_output=True,
                          text=True, check=True, env=_env(sbx)).stdout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json(path: Path, body: dict) -> None:
    _write(path, json.dumps(body, ensure_ascii=False, indent=1) + "\n")


def _commit(sbx: Path, subject: str) -> str:
    _git(sbx, "add", "-A")
    _git(sbx, "commit", "-q", "-m", subject)
    return _git(sbx, "rev-parse", "HEAD").strip()


@pytest.fixture()
def shift(tmp_path: Path) -> Path:
    """Голый origin + клон смены, круг 21, ход у исполнителя.

    Ветка текущая ДО первого коммита — иначе `push_baton` уходит в
    плюмбинг и зубы про путь дерева не состоятся.
    """
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-q", str(origin))
    work = tmp_path / "work"
    work.mkdir()
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    (work / "tmp").mkdir()
    _git(work, "checkout", "-q", "-B", BRANCH)

    _write(work / "agent" / "acceptance.sh", STUB_ACCEPTANCE)
    _write(work / "agent" / "REPORT-98.md", "# REPORT-98\n")
    _json(work / STATE, {"task": "agent/TASK-99.md",
                         "report": "agent/REPORT-99.md",
                         "status": "working",
                         "updated_at": _minutes_ago(3)})
    _json(work / BATON, {"holder": "executor", "round": 21, "branch": BRANCH,
                         "task": "agent/TASK-99.md",
                         "report": "agent/REPORT-99.md", "note": ""})
    _commit(work, "Эстафета: круг 21, ход у executor — agent/TASK-99.md")
    _git(work, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}")
    _git(work, "fetch", "-q", "origin")
    _git(work, "branch", "--set-upstream-to", f"origin/{BRANCH}", BRANCH)
    assert _git(work, "rev-parse", "--abbrev-ref", "HEAD").strip() == BRANCH
    return work


def _hand(work: Path, *extra_args: str) -> subprocess.CompletedProcess:
    argv = ["python3", str(RELAY), "--branch", BRANCH, "hand",
            "--to", "coordinator", "--note", "сдача J2"]
    return subprocess.run(argv + list(extra_args), cwd=str(work),
                          capture_output=True, text=True, env=_env(work))


def _staged(work: Path) -> list[str]:
    return [f for f in _git(work, "diff", "--cached",
                            "--name-only").splitlines() if f.strip()]


def _named_left(text: str) -> list[str]:
    """Имена из строки «в индексе остались: …». Пусто — если строки нет."""
    for line in text.splitlines():
        if line.startswith("relay: в индексе остались: "):
            assert line.endswith(PHRASE), line
            body = line[len("relay: в индексе остались: "):-len(PHRASE)]
            return [f.strip() for f in body.split(",") if f.strip()]
    return []


def _stage_two(work: Path) -> None:
    _write(work / "docs" / "a.md", "a\n")
    _write(work / "docs" / "b.md", "b\n")
    _git(work, "add", "docs/a.md", "docs/b.md")


# ── зуб 1 (Done-when): отвергающий pre-commit ────────────────────────────


def test_rejecting_hook_names_both_add_files_and_baton_is_not_staged(shift):
    """Ровно форма гейта: хук не пустил коммит эстафеты — названы ОБА
    вложенных файла, а BATON в индексе отсутствует."""
    hook = shift / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(REJECTING_HOOK, encoding="utf-8")
    hook.chmod(0o755)
    _stage_two(shift)
    assert _staged(shift) == ["docs/a.md", "docs/b.md"]

    proc = _hand(shift, "--add", "docs/a.md", "--add", "docs/b.md")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "коммит эстафеты не прошёл" in out, out
    assert _named_left(out) == ["docs/a.md", "docs/b.md"], out
    # BATON откатан (ТЗ-89 D2) — его в индексе нет
    assert BATON not in _staged(shift), _staged(shift)
    assert _git(shift, "diff", "--cached", BATON).strip() == ""
    # …а работа осталась: строка не блефует
    assert _staged(shift) == ["docs/a.md", "docs/b.md"]
    # ход не передан: на origin по-прежнему исполнитель круга 21
    on_origin = json.loads(_git(shift, "show", f"origin/{BRANCH}:{BATON}"))
    assert on_origin["holder"] == "executor" and on_origin["round"] == 21


# ── зуб 2: отказ снимает собственный штамп J1 ────────────────────────────


def test_refused_hand_rolls_back_its_own_state_stamp(shift):
    """Штамп J1 — второй файл, который `hand` пишет сам. Отказ обязан
    снять и его: иначе у вызывающего в индексе лежит `status: "handed"`
    про передачу, которой не было, и следующий его коммит уносит её на
    ветку (тот же класс беды, что круг 107 у D2)."""
    hook = shift / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(REJECTING_HOOK, encoding="utf-8")
    hook.chmod(0o755)
    before = (shift / STATE).read_bytes()
    _stage_two(shift)

    proc = _hand(shift, "--add", "docs/a.md", "--add", "docs/b.md")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert (shift / STATE).read_bytes() == before, out
    assert _git(shift, "show", f":{STATE}").encode("utf-8") \
        == before.rstrip(b"\n") + b"\n", _git(shift, "show", f":{STATE}")
    assert STATE not in _staged(shift), _staged(shift)
    assert _named_left(out) == ["docs/a.md", "docs/b.md"], out
    # чужая работа осталась нетронутой — откат касается только файлов hand
    assert _staged(shift) == ["docs/a.md", "docs/b.md"]


# ── зуб 3: своя правка STATE переживает отказ ───────────────────────────


def test_callers_own_staged_state_edit_survives_the_refusal(shift):
    """Откат штампа не имеет права съесть свою правку STATE: вызывающий
    кладёт её в индекс сам, и после отказа в индексе лежит ЕГО версии,
    а не HEAD и не штамп `hand`."""
    hook = shift / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(REJECTING_HOOK, encoding="utf-8")
    hook.chmod(0o755)
    mine = json.dumps({"task": "agent/TASK-99.md", "report": "agent/REPORT-99.md",
                       "item": "моя правка", "status": "working",
                       "updated_at": _minutes_ago(3)},
                      ensure_ascii=False, indent=1) + "\n"
    _write(shift / STATE, mine)
    _git(shift, "add", STATE)
    _stage_two(shift)

    proc = _hand(shift, "--add", "docs/a.md", "--add", "docs/b.md")
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert (shift / STATE).read_text(encoding="utf-8") == mine
    assert _git(shift, "show", f":{STATE}") == mine
    staged = _staged(shift)
    assert STATE in staged and "docs/a.md" in staged, staged


# ── зуб 4: отказ из-за чужого в индексе ──────────────────────────────────


def test_foreign_index_refusal_names_own_add_and_leaves_foreign(shift):
    before = (shift / STATE).read_bytes()
    _stage_two(shift)
    _write(shift / "tools" / "foreign.py", "foreign = 1\n")
    _git(shift, "add", "tools/foreign.py")

    proc = _hand(shift, "--add", "docs/a.md", "--add", "docs/b.md")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "в индексе лежит чужое: tools/foreign.py" in out, out
    assert _named_left(out) == ["docs/a.md", "docs/b.md"], out
    staged = _staged(shift)
    assert BATON not in staged, staged
    # чужое не тронуто — то же утверждение, что у D2
    assert "tools/foreign.py" in staged, staged
    # штамп наносится ПОСЛЕ проверки чужого: отказ, не дошедший до `git
    # add`, не имеет права касаться дерева
    assert (shift / STATE).read_bytes() == before, out


# ── зуб 5: ранний отказ тоже называет ────────────────────────────────────


def test_early_refusal_before_any_add_names_staged_work(shift):
    """Отказ до `git add` (стоп-файл) — файлы в индексе положил сам
    вызывающий; «не откатана» относится и к нему."""
    _stage_two(shift)
    _git(shift, "rm", "--cached", "-q", "docs/b.md")
    (shift / ".git" / "relay-stop").write_text("стоп\n", encoding="utf-8")

    proc = _hand(shift, "--add", "docs/a.md")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "пауза:" in out, out
    assert _named_left(out) == ["docs/a.md"], out


# ── зуб 6: без --add строки нет ──────────────────────────────────────────


def test_refusal_without_add_prints_no_leftovers_line(shift):
    (shift / ".git" / "relay-stop").write_text("стоп\n", encoding="utf-8")
    proc = _hand(shift)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "в индексе остались" not in out, out


# ── зуб 7: файл в дереве, но не в индексе — не «остался» ─────────────────


def test_unstaged_add_file_is_not_claimed_as_leftover(shift):
    """Строка обязана описывать индекс, а не аргументы командной строки:
    иначе она обещает возврат того, что и не уходило."""
    _write(shift / "docs" / "a.md", "a\n")
    (shift / ".git" / "relay-stop").write_text("стоп\n", encoding="utf-8")

    proc = _hand(shift, "--add", "docs/a.md")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert _named_left(out) == [], out
    assert _staged(shift) == []


# ── зуб 8: успешный hand молчит про остатки ──────────────────────────────


def test_successful_hand_prints_no_leftovers_line(shift):
    _stage_two(shift)
    proc = _hand(shift, "--add", "docs/a.md", "--add", "docs/b.md")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "в индексе остались" not in out, out
    assert _staged(shift) == [], _staged(shift)
    committed = _git(shift, "show", "--name-only", "--format=", "HEAD")
    assert "docs/a.md" in committed and "docs/b.md" in committed, committed
