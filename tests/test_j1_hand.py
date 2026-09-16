"""ТЗ-42 J1: `hand` не имеет права закончиться, не переложив эстафету.

Временный репозиторий с голым «origin» (локальный каталог, сеть не
нужна):
- чужой файл в индексе -> hand отказывается: код ненулевой, в выводе
  "ход не передан", BATON на origin не изменился;
- чистый индекс -> hand проходит, и BATON читается именно с origin.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

RELAY = Path(__file__).resolve().parents[1] / "agent" / "relay.py"

BATON_EXECUTOR = {
    "holder": "executor", "round": 1, "branch": "agent/night-test",
    "task": "agent/TASK-X.md", "report": "agent/REPORT-X.md",
    "note": "", "handed_by": "coordinator",
    "handed_at": "2026-09-16T00:00:00Z", "paused": False,
    "finished": False,
}


def _run(args: list[str], cwd: Path, env_extra: dict | None = None):
    import os
    env = dict(os.environ)
    # ТЗ-46: хук «git commit --only» (эстафетный коммит) оставляет в
    # окружении GIT_INDEX_FILE временного индекса ДРУГОГО репозитория;
    # песочница обязана быть герметичной — без чужого индекса и
    # указателей на чужое хранилище объектов.
    for leaked in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
                   "GIT_OBJECT_DIRECTORY",
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(leaked, None)
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "t"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "t@t"
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys_executable(), str(RELAY), *args],
                          cwd=cwd, capture_output=True, text=True,
                          env=env)


def sys_executable() -> str:
    import sys
    return sys.executable


@pytest.fixture()
def relay_repo(tmp_path: Path):
    """Рабочий репозиторий + голый origin и ветка agent/night-test с
    BATON.json, где ход у executor."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    work.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "HOME": str(tmp_path)}

    def git(*argv: str, check: bool = True):
        return subprocess.run(["git", *argv], cwd=work, env=env,
                              capture_output=True, text=True, check=check)

    git("init", "-q", "-b", "agent/night-test")
    git("remote", "add", "origin", str(origin))
    (work / "agent").mkdir()
    baton = work / "agent" / "BATON.json"
    baton.write_text(json.dumps(BATON_EXECUTOR, indent=1) + "\n",
                     encoding="utf-8")
    (work / "agent" / "REPORT-X.md").write_text("# отчёт\n",
                                                encoding="utf-8")
    git("add", "agent")
    git("commit", "-q", "-m", "init")
    git("push", "-q", "origin", "agent/night-test:agent/night-test")
    return work, origin, env, baton


def _origin_baton(origin: Path, branch: str) -> dict | None:
    out = subprocess.run(
        ["git", "--git-dir", str(origin), "show",
         f"{branch}:agent/BATON.json"], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


def test_hand_refuses_dirty_index_and_origin_unchanged(relay_repo):
    """Чужой файл в индексе -> hand отказывается: код ненулевой,
    "ход не передан" в выводе, BATON на origin не изменился."""
    work, origin, env, _baton = relay_repo
    (work / "stranger.txt").write_text("чужое\n", encoding="utf-8")
    subprocess.run(["git", "add", "stranger.txt"], cwd=work, env=env,
                   capture_output=True, text=True, check=True)
    result = _run(["--remote", "origin", "--branch",
                   "agent/night-test", "hand", "--to", "coordinator",
                   "--report", "agent/REPORT-X.md",
                   "--note", "попытка из грязного индекса"], cwd=work)
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "ход не передан" in combined
    assert "stranger.txt" in combined
    on_origin = _origin_baton(origin, "agent/night-test")
    assert on_origin is not None
    assert on_origin["holder"] == "executor", \
        "эстафета уехала из грязного индекса"
    assert on_origin["round"] == 1


def test_clean_hand_passes_and_reads_origin(relay_repo):
    """Чистый индекс -> hand проходит; BATON читается с origin:
    ход у coordinator, round увеличился."""
    work, origin, env, _baton = relay_repo
    result = _run(["--remote", "origin", "--branch",
                   "agent/night-test", "hand", "--to", "coordinator",
                   "--report", "agent/REPORT-X.md",
                   "--note", "сдача I5+I6"], cwd=work)
    assert result.returncode == 0, result.stdout + result.stderr
    on_origin = _origin_baton(origin, "agent/night-test")
    assert on_origin is not None
    assert on_origin["holder"] == "coordinator"
    assert on_origin["round"] == 2
    assert on_origin["note"] == "сдача I5+I6"
    # строка подтверждения — про origin, не про рабочее дерево
    assert "передано коммитом" in result.stdout


def test_assert_holder_both_outcomes(relay_repo):
    """J2: --assert-holder — ненулевой код, если на origin держатель не
    эта роль; ноль — если эта."""
    work, origin, env, _baton = relay_repo
    # после hand ход у coordinator
    _run(["--remote", "origin", "--branch", "agent/night-test", "hand",
          "--to", "coordinator", "--report", "agent/REPORT-X.md",
          "--note", ""], cwd=work)
    ok = _run(["--remote", "origin", "--branch", "agent/night-test",
               "status", "--assert-holder", "coordinator"], cwd=work)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = _run(["--remote", "origin", "--branch", "agent/night-test",
                "status", "--assert-holder", "executor"], cwd=work)
    assert bad.returncode != 0
    assert "ход НЕ передан" in bad.stdout + bad.stderr
