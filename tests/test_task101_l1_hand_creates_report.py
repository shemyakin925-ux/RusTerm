"""ТЗ-101 L1: `hand` не называет отчёт, которого нет.

Корень (REPORT-99, Disputed 1): J1 научил `hand` штамповать
`agent/STATE.json` полями `task`/`report`, но сам отчёт создавать он не
научился. Сдача на новый отчёт — `hand --report agent/REPORT-N.md` файла,
которого в дереве нет, — даёт приходящей смене STATE, указывающий в пустоту,
и стражи краснеют ДО первого коммита круга. Замер в scratch-клоне живой
ветки (круг 133, приватный origin): такой `hand` даёт `6 failed, 28 passed`
— `test_state_report_is_tracked_in_this_commit` плюс пять узлов
`test_report_sections.py`, которым `_report_text()` нечего читать.

Правило L1: если `--report` называет файл, которого нет, `hand` пишет
заготовку и кладёт её в ТОТ ЖЕ коммит эстафеты. Существующий отчёт не
трогается ни при каком раскладе.

Зубья:
1. Done-when: заготовка в дереве, в коммите эстафеты и на ветке; коммит
   один, и несёт он ровно BATON + STATE + отчёт.
2. Форма заготовки — по живому списку `REQUIRED_SECTIONS` (сверка с самим
   стражем, а не с пересказом) + `## Runs` + непустой HANDOFF без
   заполнителей; заголовок берётся из ТЗ.
3. Те же пять узлов + узел отслеживаемости зелёные сразу после `hand` на
   скопированных в песочницу настоящих стражах, и краснеют обратно, если
   файл из коммита убрать.
4. Существующий отчёт (закоммиченный и незакоммиченный черновик)
   переживает передачу байт-в-байт и не едет в коммит.
5. Отказ не оставляет заготовки: ни до её создания (красная приёмка), ни
   после (сорванный хуком коммит).
6. Плюмбинг: блоб уезжает, чужое рабочее дерево не получает ни файла; отчёт,
   который на ветке уже есть, плюмбинг не перезаписывает (тот же закон, что
   ТЗ-99 J1 вывел для часов).

Песочница — локальный голый origin в `tmp_path` (сети нет; бюджеты круга —
network 0, LLM 0), `TMPDIR` указан внутрь песочницы, `HOME` намеренно НЕ
подменяется: с другим `HOME` интерпретатор теряет user-site, и запуск
стража падает на `ModuleNotFoundError` ещё до первого утверждения (урок
`tests/test_task99_j1_hand_stamps_state.py`). Стражи копируются в песочницу
байт-в-байт и запускаются там настоящим `pytest`: пересказать их логику
здесь — значит проверять свою фантазию. Приёмка — заглушка: ТЗ-66 L1 делает
её опциональной по наличию `agent/acceptance.sh`, а настоящий набор в
песочнице проверял бы не L1.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RELAY = REPO_ROOT / "agent" / "relay.py"
TRACKED_GUARD = REPO_ROOT / "tests" / "test_state_report_tracked.py"
SECTIONS_GUARD = REPO_ROOT / "tests" / "test_report_sections.py"

BATON = "agent/BATON.json"
STATE = "agent/STATE.json"
BRANCH = "agent/night-l1"
OLD_REPORT = "agent/REPORT-20.md"
NEW_REPORT = "agent/REPORT-21.md"
TASK = "agent/TASK-21.md"
TASK_TITLE = "Заготовка отчёта вместо красной приёмки"
STUB_ACCEPTANCE = "#!/usr/bin/env bash\nexit 0\n"

LEAKED = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")

# Ровно те узлы, которые краснит неназванный отчёт (замер круга 133).
GUARD_NODES = (
    "tests/test_state_report_tracked.py::"
    "test_state_report_is_tracked_in_this_commit",
    "tests/test_report_sections.py::test_report_carries_every_required_section",
    "tests/test_report_sections.py::"
    "test_disputed_lines_live_only_in_disputed_section",
    "tests/test_report_sections.py::"
    "test_handoff_carries_real_values_not_placeholders",
    "tests/test_report_sections.py::"
    "test_last_handoff_does_not_call_committed_items_undone",
    "tests/test_report_sections.py::"
    "test_done_items_have_code_commits_in_round",
)

PREV_STATE = {"task": "agent/TASK-20.md", "report": OLD_REPORT,
              "item": "L0", "step": "последний коммит прежней смены",
              "status": "awaiting_review", "last_commit": "1111111",
              "requests": 39, "net_requests": 39, "llm_calls": 0,
              "model": "Qoder executor (model id not exposed)",
              "updated_at": "2026-09-26T00:00:00Z"}

OLD_TEXT = ("# REPORT-20 — отчёт прежней смены\n\n## Done\n\n## Blocked\n\n"
            "## What not to trust\n\n## Disputed\n\n## Runs\n\n## HANDOFF\n"
            "Status: DONE\n")


def _env(sbx: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                "TMPDIR": str(sbx / "tmp")})
    env.update(extra)
    return env


def _git(sbx: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=str(sbx), capture_output=True,
                          text=True, check=check, env=_env(sbx)).stdout


def _blob(sbx: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=str(sbx), capture_output=True,
                          check=True, env=_env(sbx)).stdout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json(path: Path, body: object) -> None:
    _write(path, json.dumps(body, ensure_ascii=False, indent=1) + "\n")


@pytest.fixture()
def shift(tmp_path: Path) -> Path:
    """Голый origin + клон смены: круг 40, ход у исполнителя, нового
    отчёта ещё нет — это и есть момент сдачи."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-q", str(origin))
    work = tmp_path / "work"
    work.mkdir()
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    (work / "tmp").mkdir()
    # ветка смены обязана быть текущей ДО первого коммита: иначе
    # `push_baton` уходит в плюмбинг, а зубы 1–5 про путь дерева
    _git(work, "checkout", "-q", "-B", BRANCH)
    _write(work / "agent" / "acceptance.sh", STUB_ACCEPTANCE)
    _write(work / OLD_REPORT, OLD_TEXT)
    _write(work / TASK, f"# TASK-21 — {TASK_TITLE}\n\n## L1\n")
    _json(work / STATE, PREV_STATE)
    _json(work / BATON, {"holder": "executor", "round": 40, "branch": BRANCH,
                         "task": "agent/TASK-20.md", "report": OLD_REPORT,
                         "note": ""})
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "круг 40: работа прежней смены")
    _git(work, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}")
    _git(work, "fetch", "-q", "origin")
    _git(work, "branch", "--set-upstream-to", f"origin/{BRANCH}", BRANCH)
    assert not (work / NEW_REPORT).exists(), \
        "заготовку создаёт hand, а не песочница"
    return work


def _hand(work: Path, *extra_args: str, report: str = NEW_REPORT,
          task: str = TASK) -> subprocess.CompletedProcess:
    """Тот же вызов, что делает исполнитель на сдаче нового отчёта."""
    argv = ["python3", str(RELAY), "--branch", BRANCH, "hand", "--to",
            "coordinator", "--task", task, "--report", report,
            "--note", "сдача L1"]
    return subprocess.run(argv + list(extra_args), cwd=str(work),
                          capture_output=True, text=True, env=_env(work))


def _commit_paths(work: Path, ref: str = "HEAD") -> list[str]:
    out = _git(work, "show", "--name-only", "--format=", ref)
    return sorted(line for line in out.splitlines() if line.strip())


def _origin_blob(work: Path, rel: str) -> str:
    _git(work, "fetch", "-q", "origin")
    return _blob(work, "show", f"origin/{BRANCH}:{rel}").decode("utf-8")


def _hand_and_origin_report(work: Path) -> str:
    proc = _hand(work)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return _origin_blob(work, NEW_REPORT)


def _install_guards(work: Path) -> None:
    """Настоящие стражи в песочницу — копиями, одним коммитом."""
    (work / "tests").mkdir(exist_ok=True)
    shutil.copyfile(TRACKED_GUARD,
                    work / "tests" / "test_state_report_tracked.py")
    shutil.copyfile(SECTIONS_GUARD, work / "tests" / "test_report_sections.py")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "стражи отчёта: копия для прогона здесь")


def _run_guards(work: Path) -> str:
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", *GUARD_NODES],
                          cwd=str(work), capture_output=True, text=True,
                          env=_env(work))
    return proc.stdout + proc.stderr


def _headers(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines()
            if line.startswith("## ")]


# ── зуб 1: Done-when — отчёт едет коммитом эстафеты ──────────────────────


def test_the_missing_report_rides_the_baton_commit(shift: Path) -> None:
    """`hand --report` несуществующего файла: заготовка появляется в
    дереве, в коммите эстафеты и на ветке — отдельного коммита не нужно."""
    proc = _hand(shift)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    created = shift / NEW_REPORT
    assert created.is_file(), "отчёт так и не появился в дереве смены"
    assert NEW_REPORT in _commit_paths(shift), (
        f"коммит эстафеты не несёт отчёт: {_commit_paths(shift)}")
    assert _origin_blob(shift, NEW_REPORT) == created.read_text(
        encoding="utf-8"), "в дереве и на ветке — разные байты заготовки"
    assert json.loads(_origin_blob(shift, STATE))["report"] == NEW_REPORT, \
        "STATE назвал отчёт, которого коммит не принёс"


def test_the_skeleton_is_announced_not_silent(shift: Path) -> None:
    """Молча созданного файла мало: `hand` говорит, что положил заготовку
    (тот же закон громкости, что у ТЗ-78 Z2 и ТЗ-99 J2)."""
    proc = _hand(shift)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert NEW_REPORT in proc.stdout, proc.stdout
    assert "заготовк" in proc.stdout, proc.stdout


def test_the_baton_commit_carries_baton_state_and_report_only(shift: Path) -> None:
    """Один коммит на сдачу, и несёт он ровно три файла: BATON, штамп J1 и
    заготовку. Окно «STATE уже назвал, git ещё не хранит» закрыто."""
    _hand(shift)
    assert _commit_paths(shift) == sorted([BATON, STATE, NEW_REPORT]), \
        _commit_paths(shift)
    assert _git(shift, "rev-list", "--count", "HEAD~1..HEAD").strip() == "1"


# ── зуб 2: форма заготовки — то, что требуют стражи ──────────────────────


def test_the_skeleton_carries_every_section_the_guard_requires(shift: Path) -> None:
    """Секции заготовки — список живого стража (`REQUIRED_SECTIONS`) плюс
    `## Runs`, HANDOFF непустой и без заполнителей. Сверка с модулем, а не
    с его пересказом: иначе заготовка «проходит» мой тест и валит приёмку."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    try:
        import test_report_sections as guard
        required = list(guard.REQUIRED_SECTIONS)
    finally:
        sys.path.pop(0)
    assert required, "страж не отдал REQUIRED_SECTIONS — зуб пустой"

    text = _hand_and_origin_report(shift)
    have = _headers(text)
    for name in required:
        assert name in have, f"в заготовке нет секции {name!r}: {have}"
    assert "Runs" in have, have
    handoff = text.split("## HANDOFF", 1)[1]
    assert handoff.strip(), "## HANDOFF пуст — страж краснеет на нём"
    for placeholder in ("N passed", "M skipped", "<"):
        assert placeholder not in handoff, \
            f"заготовка содержит заполнитель {placeholder!r}"


def test_the_title_line_is_taken_from_the_task(shift: Path) -> None:
    """`# REPORT-21 — <заголовок ТЗ>`: заготовка говорит, о каком круге
    отчёт, а не просто номер файла."""
    text = _hand_and_origin_report(shift)
    assert text.splitlines()[0] == f"# REPORT-21 — {TASK_TITLE}", \
        text.splitlines()[0]


# ── зуб 3: узлы, которые краснит неназванный отчёт ───────────────────────


def test_the_guards_an_unborn_report_reddens_are_green_after_the_hand(
        shift: Path) -> None:
    """Ядро Done-when на настоящих стражах: зелёные сразу после `hand`, без
    единого дополнительного коммита, и краснеют обратно, если файл из
    коммита убрать — то есть зелёность делает заготовка, а не порядок
    истории."""
    _install_guards(shift)
    before = _run_guards(shift)
    assert "failed" not in before, (
        f"песочница красна ещё до hand — зуб проверяет не L1: {before}")

    proc = _hand(shift)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    after = _run_guards(shift)
    assert "failed" not in after, (
        "после hand стражи обязаны зелёнеть без единого дополнительного "
        f"коммита: {after}")

    (shift / NEW_REPORT).unlink()
    _git(shift, "rm", "-q", "--cached", NEW_REPORT)
    reverted = _run_guards(shift)
    assert "failed" in reverted, (
        "без файла стражи всё равно зелёные — значит про него они и не "
        f"спрашивают: {reverted}")


# ── зуб 4: существующий отчёт не трогается ───────────────────────────────


def test_an_existing_report_survives_a_hand_that_names_it(shift: Path) -> None:
    """Закоммиченный отчёт переживает передачу байт-в-байт и НЕ едет в
    коммит эстафеты: у `hand` нет права на работу смены."""
    existing = OLD_TEXT.replace("REPORT-20", "REPORT-21")
    _write(shift / NEW_REPORT, existing)
    _git(shift, "add", "-A")
    _git(shift, "commit", "-q", "-m", "смена написала отчёт")

    proc = _hand(shift)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (shift / NEW_REPORT).read_text(encoding="utf-8") == existing, \
        "существующий отчёт перезаписан заготовкой"
    assert _origin_blob(shift, NEW_REPORT) == existing
    assert NEW_REPORT not in _commit_paths(shift), (
        f"рука hand потянула в коммит чужую работу: {_commit_paths(shift)}")


def test_an_uncommitted_draft_is_not_clobbered_either(shift: Path) -> None:
    """Черновик отчёта, ещё не закоммиченный, — тоже существующий файл:
    проверка идёт по дереву, а не по блобу ветки, иначе `hand` стёр бы
    незакоммиченную работу смены."""
    draft = "# REPORT-21 — черновик, который ещё не уехал в git\n"
    _write(shift / NEW_REPORT, draft)

    _hand(shift)
    assert (shift / NEW_REPORT).read_text(encoding="utf-8") == draft


# ── зуб 5: отказ не оставляет заготовки ──────────────────────────────────


def test_a_refusal_before_the_commit_leaves_no_skeleton(shift: Path) -> None:
    """Красная приёмка — отказ ДО всякой записи: ни файла, ни следа в
    индексе (ТЗ-66 L1, ТЗ-99 J2)."""
    _write(shift / "agent" / "acceptance.sh", "#!/usr/bin/env bash\nexit 7\n")
    _git(shift, "add", "-A")
    _git(shift, "commit", "-q", "-m", "заглушка приёмки: красная")

    proc = _hand(shift)
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, "красная приёмка не остановила передачу"
    assert not (shift / NEW_REPORT).exists(), \
        "отказ оставил заготовку сдачи, которая не состоялась"
    assert NEW_REPORT not in _git(shift, "ls-files").splitlines()
    assert "ход не передан" in combined or "красная" in combined, combined


def test_a_refusal_after_the_skeleton_rolls_it_back(shift: Path) -> None:
    """Сорванный коммит — отказ ПОСЛЕ того, как заготовка уже написана
    (хук не пустил `git commit`): созданный `hand` файл обязан уйти вместе
    с передачей, а не остаться в дереве и индексе."""
    hook = shift / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    proc = _hand(shift)
    assert proc.returncode != 0, f"хук не остановил передачу: {proc.stdout}"
    assert not (shift / NEW_REPORT).exists(), \
        "после сорванного коммита заготовка осталась в дереве"
    assert NEW_REPORT not in _git(shift, "ls-files").splitlines(), \
        "после сорванного коммита заготовка осталась в индексе"
    assert _git(shift, "rev-parse", "HEAD").strip() == _git(
        shift, "rev-parse", "origin/agent/night-l1").strip(), \
        "сорванная передача всё равно уехала в историю"


def test_a_report_path_outside_the_repository_is_refused(shift: Path) -> None:
    """`hand` теперь пишет файл, и путь обязан остаться в репозитории:
    выход за его пределы — отказ, а не запись по соседству со сменой."""
    proc = _hand(shift, report="../вне-репозитория.md")
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, (
        f"путь за пределами репозитория принят без отказа: {combined}")
    assert not (shift.parent / "вне-репозитория.md").exists(), \
        "заготовка написана вне репозитория"
    assert "вне репозитория" in combined, combined


# ── зуб 6: плюмбинг — блоб в коммит, чужое дерево не трогать ─────────────


@pytest.fixture()
def coord_tree(shift: Path) -> Path:
    """Тот же голый origin, выкачанный НЕ в ветку смены: параллельная смена
    координатора, где `hand` идёт плюмбингом."""
    other = shift.parent / "coord"
    _git(shift.parent, "clone", "-q", "-b", BRANCH,
         str(shift.parent / "origin.git"), str(other))
    _git(other, "checkout", "-q", "-B", "coord/parallel-shift")
    assert _git(other, "rev-parse", "--abbrev-ref", "HEAD").strip() != BRANCH
    return other


def _hand_from(tree: Path) -> subprocess.CompletedProcess:
    return _hand(tree)


def test_plumbing_adds_the_blob_without_writing_into_a_foreign_tree(
        coord_tree: Path) -> None:
    """Ветке отчёта нет — заготовка уезжает блобом; рабочее дерево, где эта
    ветка не выкачана, не получает ни одного файла."""
    before = sorted(p.name for p in (coord_tree / "agent").iterdir())

    proc = _hand_from(coord_tree)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _origin_blob(coord_tree, NEW_REPORT).startswith("# REPORT-21 — "), \
        "в коммите эстафеты нет заготовки"
    assert not (coord_tree / NEW_REPORT).exists(), \
        "плюмбинг написал в чужое рабочее дерево"
    assert sorted(p.name for p in (coord_tree / "agent").iterdir()) == before


def test_plumbing_never_rewrites_a_report_the_branch_already_has(
        coord_tree: Path) -> None:
    """Отчёт на ветке ЕСТЬ — значит это работа смены, и плюмбинг обязан
    пройти мимо: ни заготовки, ни нового блоба. Именно так и теряется
    написанный отчёт, если проверять наличие по чужому дереву."""
    written = "# REPORT-21 — уже написан сменой\n"
    _git(coord_tree, "checkout", "-q", "-B", BRANCH)
    _write(coord_tree / NEW_REPORT, written)
    _git(coord_tree, "add", "-A")
    _git(coord_tree, "commit", "-q", "-m", "смена пишет отчёт")
    _git(coord_tree, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}")
    _git(coord_tree, "checkout", "-q", "-B", "coord/parallel-shift")
    assert _origin_blob(coord_tree, NEW_REPORT) == written

    proc = _hand_from(coord_tree)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _origin_blob(coord_tree, NEW_REPORT) == written, \
        "плюмбинг перезаписал отчёт ветки заготовкой"
    assert NEW_REPORT not in _commit_paths(coord_tree, f"origin/{BRANCH}"), \
        _commit_paths(coord_tree, f"origin/{BRANCH}")
