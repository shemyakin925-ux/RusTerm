"""ТЗ-99 J1: `hand` сам ставит метку в `agent/STATE.json`.

Корень (ТЗ-89 D0, Disputed 1): `hand` двигал только `agent/BATON.json`, а
`agent/STATE.json` оставался с именами и часами предыдущей смены.
`tests/test_report_sections.py` берёт отчёт из STATE, а окно круга — из
BATON, поэтому на всём промежутке между коммитом эстафеты и первым
коммитом новой смены `test_done_items_have_code_commits_in_round` красна:
в круге 129 приезжающий исполнитель получил ровно это (замер — строка
«Arrival baseline» в REPORT-99). Единственный доступный ответ был —
переписать STATE приходящей стороной, то есть доказывать чужую смену
своей рукой.

Правило J1: те же четыре поля (`task`, `report` — из аргументов `hand`,
`status: "handed"`, свежий `updated_at`) едут коммитом эстафеты,
остальное содержимое STATE не трогается.

Зубья:
1. Done-when: после `hand` настоящий страж
   `test_done_items_have_code_commits_in_round` зелёный БЕЗ дополнительных
   коммитов; на тех же коммитах он краснеет обратно, если вернуть STATE
   в вид до `hand` — то есть зелёность делает штамп, а не случайность
   истории.
2. Коммит эстафеты несёт `agent/STATE.json` рядом с `agent/BATON.json`,
   ровно по одному разу; `STATE.task == BATON.task`; `status=handed`;
   `updated_at` — живые часы; поля прежней смены (`requests`, `model`,
   `item`, `step`) уцелели.
3. Без `--task`/`--report` STATE всё равно зеркалит BATON (поля берутся
   из получившегося BATON, а не из воздуха).
4. `--add agent/STATE.json` (обходной путь кругов 119+) не удваивает
   файл в коммите.
5. Свой STATE, уже лежащий в индексе, не считается «чужим» и не рвёт
   передачу; его правка доживает до коммита.
6. Плюмбинг (смена выкачана НЕ в этом дереве): штамп собирается из блоба
   STATE самой ветки, а рабочее дерево — например, параллельная смена
   координатора — не тронуто ни байтом.

Песочница — локальный голый «origin» в `tmp_path` (сети нет, бюджеты
круга соблюдены), из окружения вычищен только leaks git-переменных
(тот же приём, что у ТЗ-89 D2 и ТЗ-98 H2). `HOME` здесь НАМЕРЕННО не
подменяется: с другим `HOME` интерпретатор теряет user-site, и запуск
стража падает на `ModuleNotFoundError: pygments` (измерено на второй
попытке этого модуля). Страж копируется в песочницу байт-в-байт и
запускается там настоящим `pytest`: переписать его логику здесь
значило бы проверять не его, а свою фантазию.
`agent/acceptance.sh` — заглушка: ТЗ-66 L1 делает живую приёмку
опциональной по наличию скрипта, иначе каждый прогон тянул бы весь набор
тестов.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RELAY = REPO_ROOT / "agent" / "relay.py"
GUARD_SOURCE = REPO_ROOT / "tests" / "test_report_sections.py"
L3_NODE = ("tests/test_report_sections.py::"
           "test_done_items_have_code_commits_in_round")

BATON = "agent/BATON.json"
STATE = "agent/STATE.json"
BRANCH = "agent/night-j1"
OLD_REPORT = "agent/REPORT-98.md"
NEW_REPORT = "agent/REPORT-99.md"
STUB_ACCEPTANCE = "#!/usr/bin/env bash\nexit 0\n"

LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")

def _minutes_ago(minutes: int) -> str:
    """Часы внутри допуска H2 (15 мин): `hand` здесь отказал бы ДО
    всякого штампа, и зубы проверяли бы не J1. Сам спор «затирать часы
    до проверки или после» — ТЗ-100 K1, не этот пункт."""
    return (datetime.now(timezone.utc)
            - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


# прежнее состояние дел: имена отчёта ещё прошлой смены. `updated_at`
# сюда НЕ кладётся: выражение уровня модуля вычисляется при импорте, а
# до этого модуля полный прогон приёмки доходит через ~19 минут после
# сборки — `hand` отказывает по проверке часов H2, и зубы 4–6 краснеют
# не потому, что штамп сломан, а потому, что песочница притворялась
# свежей, когда таковой уже не была (измерено на круге 129: в
# подмножестве модулей зелёные, в полном прогоне — красные).
OLD_STATE = {"task": "agent/TASK-98.md", "report": OLD_REPORT,
             "item": "H1", "step": "последний коммит прежней смены",
             "status": "awaiting_review", "last_commit": "1111111",
             "requests": 39, "net_requests": 39, "llm_calls": 0,
             "model": "Qoder executor (model id not exposed)"}


def _pre_hand_state(**extra: str) -> dict:
    """STATE прежней смены с часами, честными ОТНОСИТЕЛЬНО этого теста:
    `hand` обязан увидеть «писали три минуты назад», а не «писали на
    сборке песочниц»."""
    return {**OLD_STATE, "updated_at": _minutes_ago(3), **extra}


OLD_HANDOFF = ("# REPORT-98\n\n## Done\n\n## HANDOFF\n"
               "Status: DONE\nItems done: H1 — приём прежней смены\n")
NEW_HANDOFF = ("# REPORT-99\n\n## Done\n\n## HANDOFF\n"
               "Status: WORKING\nItems done: J1 — штамп STATE коммитом "
               "эстафеты\n")


def _env(sbx: Path, **extra: str) -> dict[str, str]:
    """`TMPDIR` — внутрь песочницы: временный индекс плюмбинга и лог
    приёмки не должны оставаться в `tempfile.gettempdir()` — это красит
    `tests/test_no_shared_tmp.py`.

    `HOME` намеренно НЕ подменяется: с другим `HOME` интерпретатор
    перестаёт видеть user-site, и запуск стража падает на
    `ModuleNotFoundError: pygments` ещё до первого утверждения
    (измерено на второй попытке этого модуля). Ничего из песочницы в
    домашний каталог не пишет — все пути здесь внутри `tmp_path`.
    """
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                "TMPDIR": str(sbx / "tmp")})
    env.update(extra)
    return env


def _git(sbx: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(sbx), capture_output=True,
                          text=True, check=True, env=_env(sbx)).stdout


def _blob(sbx: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=str(sbx), capture_output=True,
                          check=True, env=_env(sbx)).stdout


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
    """Голый origin + клон смены; история — круг 20, ход у исполнителя.

    «Х1: реализация» — работа ПРЕДЫДУЩЕЙ смены: ниже границы круга, то
    есть для стража её нет;
    «Эстафета: круг 20, …» — нижняя граница окна;
    «ТЗ-99 J1: реализация» — нетестовый файл и пункт в теме, отчёт новой
        смены уже здесь, но STATE о нём ещё не знает.
    """
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-q", str(origin))
    work = tmp_path / "work"
    work.mkdir()
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    (work / "tmp").mkdir()  # сюда указывает TMPDIR песочницы
    # ветка смены обязана быть текущей ДО первого коммита: `push_baton`
    # идёт плюмбингом, если смена выкачана не здесь, а зубья 1–5 про
    # путь дерева
    _git(work, "checkout", "-q", "-B", BRANCH)

    _write(work / "agent" / "acceptance.sh", STUB_ACCEPTANCE)
    _write(work / OLD_REPORT, OLD_HANDOFF)
    (work / "agent" / "old_impl.py").write_text("old = 1\n", encoding="utf-8")
    _json(work / STATE, _pre_hand_state())
    _json(work / BATON, {"holder": "executor", "round": 19, "branch": BRANCH,
                         "task": "agent/TASK-98.md", "report": OLD_REPORT,
                         "note": ""})
    _commit(work, "Х1: реализация прежней смены")

    _json(work / BATON, {"holder": "executor", "round": 20, "branch": BRANCH,
                         "task": "agent/TASK-99.md", "report": NEW_REPORT,
                         "note": ""})
    _commit(work, "Эстафета: круг 20, ход у executor — agent/TASK-99.md")

    (work / "agent" / "impl.py").write_text("hand = 'stamp'\n",
                                            encoding="utf-8")
    _write(work / NEW_REPORT, NEW_HANDOFF)
    _commit(work, "ТЗ-99 J1: реализация — штамп STATE")

    _git(work, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}")
    _git(work, "fetch", "-q", "origin")
    _git(work, "branch", "--set-upstream-to", f"origin/{BRANCH}", BRANCH)
    assert _git(work, "rev-parse", "--abbrev-ref", "HEAD").strip() == BRANCH
    return work


def _install_guard(sbx: Path) -> None:
    """Страж — копия настоящего файла; коммитится до `hand`, чтобы
    песочница проверяла его, а не пересказ."""
    (sbx / "tests").mkdir(exist_ok=True)
    shutil.copyfile(GUARD_SOURCE, sbx / "tests" / "test_report_sections.py")
    _commit(sbx, "страж секций отчёта: копия для прогона в песочнице")


def _run_l3(sbx: Path) -> str:
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", L3_NODE],
                          cwd=str(sbx), capture_output=True, text=True,
                          env=_env(sbx))
    return proc.stdout + proc.stderr


def _hand(work: Path, *extra_args: str) -> subprocess.CompletedProcess:
    argv = ["python3", str(RELAY), "--branch", BRANCH, "hand",
            "--to", "coordinator", "--note", "сдача J1"]
    return subprocess.run(argv + list(extra_args), cwd=str(work),
                          capture_output=True, text=True, env=_env(work))


def _state(work: Path, ref: str = "HEAD") -> dict:
    return json.loads(_git(work, "show", f"{ref}:{STATE}"))


def _baton(work: Path, ref: str = "HEAD") -> dict:
    return json.loads(_git(work, "show", f"{ref}:{BATON}"))


def _committed_paths(work: Path, ref: str = "HEAD") -> list[str]:
    out = _git(work, "show", "--name-only", "--format=", ref)
    return [line for line in out.splitlines() if line.strip()]


# ── зуб 1 (Done-when): страж зелёный без дополнительного коммита ─────────


def test_l3_guard_is_green_right_after_hand_and_red_without_the_stamp(shift):
    """То, ради чего писался пункт: приехавшая смена не обязана своим
    коммитом доказывать, что чужая смена закрыла свои пункты."""
    _install_guard(shift)

    before = _run_l3(shift)
    assert "1 failed" in before, (
        "без штампа страж обязан краснеть на отчёте прошлой смены — "
        f"иначе зуб пустой: {before}")

    proc = _hand(shift, "--report", NEW_REPORT)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    after = _run_l3(shift)
    assert "1 passed" in after, (
        "после hand страж обязан быть зелёным без единого дополнительного "
        f"коммита: {after}")

    # тем же движком: возвращаем STATE в вид до hand — краснеть должен
    # ровно этот же зуб, а не другой.
    stamped = (shift / STATE).read_bytes()
    (shift / STATE).write_bytes(_blob(shift, "show", f"HEAD~1:{STATE}"))
    reverted = _run_l3(shift)
    (shift / STATE).write_bytes(stamped)
    assert "1 failed" in reverted, (
        "зелёность делает штамп STATE, а не порядок коммитов: "
        f"без него {reverted}")
    assert "1 passed" in _run_l3(shift)


# ── зуб 2: что именно и чем едет коммит эстафеты ─────────────────────────


def test_the_baton_commit_carries_state_once_and_keeps_other_fields(shift):
    proc = _hand(shift, "--task", "agent/TASK-99.md", "--report", NEW_REPORT)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    paths = _committed_paths(shift)
    assert paths.count(BATON) == 1, paths
    assert paths.count(STATE) == 1, paths

    state, baton = _state(shift), _baton(shift)
    # «как было до `hand`» читается из ветки, а не из постоянной модуля:
    # счётчики и проза прежней смены не теряются, а часы — меняются
    pre = _state(shift, "HEAD~1")
    assert state["task"] == baton["task"] == "agent/TASK-99.md", state
    assert state["report"] == baton["report"] == NEW_REPORT, state
    assert state["status"] == "handed", state
    # счётчики и проза прежней смены не теряются: J1 называет четыре
    # поля, остальное для relay — не его
    for key in ("requests", "net_requests", "llm_calls", "model", "item",
                "step"):
        assert state[key] == pre[key] == OLD_STATE[key], (key, state)
    # часы — живые: не прежняя метка и не «круглая» минута
    stamp = datetime.strptime(state["updated_at"],
                              "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    drift = abs((datetime.now(timezone.utc) - stamp).total_seconds())
    assert drift <= 120, f"updated_at не только что: {state['updated_at']}"
    assert state["updated_at"] != pre["updated_at"]


# ── зуб 3: аргументов нет — STATE всё равно зеркалит BATON ───────────────


def test_state_mirrors_the_baton_even_without_task_and_report_args(shift):
    """BATON после hand несёт task/report прошлой передачи; штамп берёт
    их оттуда же, поэтому расхождения между двумя файлами после пункта
    просто нет."""
    proc = _hand(shift)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    state, baton = _state(shift), _baton(shift)
    assert baton["task"] == "agent/TASK-99.md" and baton["report"] == NEW_REPORT
    assert state["task"] == baton["task"], state
    assert state["report"] == baton["report"], state
    assert state["status"] == "handed", state


# ── зуб 4: обходной путь кругов 119+ не удваивает файл ───────────────────


def test_explicit_add_of_state_does_not_list_it_twice(shift):
    proc = _hand(shift, "--report", NEW_REPORT, "--add", STATE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    paths = _committed_paths(shift)
    assert paths.count(STATE) == 1, paths
    assert _state(shift)["status"] == "handed"


# ── зуб 5: свой STATE в индексе — не «чужое» ─────────────────────────────


def test_own_state_already_staged_is_not_foreign(shift):
    """Прежний `hand` умер бы на «в индексе лежит чужое»: исполнитель
    коммитит STATE в том же изменении, что и отчёт. Теперь правка
    доживает до коммита эстафеты вместе со штампом."""
    mine = _pre_hand_state(item="J1 — ждёт передачи")
    _json(shift / STATE, mine)
    _git(shift, "add", "--", STATE)

    proc = _hand(shift, "--report", NEW_REPORT)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    state = _state(shift)
    assert state["item"] == "J1 — ждёт передачи", state
    assert state["status"] == "handed" and state["task"] == "agent/TASK-99.md"


# ── зуб 6: плюмбинг не трогает чужое рабочее дерево ──────────────────────


def test_plumbing_path_stamps_the_branch_not_this_worktree(shift, tmp_path):
    """Координатор ведёт параллельные смены в своих `coord/*` и сдаёт
    ход плюмбингом. Его рабочие часы — не данные ветки смены, поэтому
    база штампа берётся из блоба STATE самой ветки."""
    other = _pre_hand_state(task="agent/TASK-OTHER.md",
                            item="параллельная смена координатора")
    _json(shift / STATE, other)
    _commit(shift, "параллельная смена в другом дереве (не ветка смены)")
    before = (shift / STATE).read_bytes()

    _git(shift, "checkout", "-q", "-B", "main")
    assert _git(shift, "rev-parse", "--abbrev-ref", "HEAD").strip() != BRANCH

    proc = _hand(shift, "--report", NEW_REPORT)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    _git(shift, "fetch", "-q", "origin")
    on_branch = json.loads(_git(shift, "show", f"origin/{BRANCH}:{STATE}"))
    assert on_branch["task"] == "agent/TASK-99.md", on_branch
    assert on_branch["status"] == "handed", on_branch
    assert on_branch["item"] == OLD_STATE["item"], (
        "штамп обязан собираться из блоба ветки, а не из чужого дерева: "
        f"{on_branch}")
    assert (shift / STATE).read_bytes() == before, (
        "рабочее дерево плюмбинга не должно меняться ни байтом")
