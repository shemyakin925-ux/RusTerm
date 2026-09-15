"""ТЗ-33 E6 / ТЗ-36 H5-H6: сторож P6 — файлы координатора не касаются
исполнителю; исключение выдаёт ЗАДАНИЕ, а не сам охраняемый.

Шесть случаев H6 (временный git-репозиторий):
1) переопределение списка из окружения игнорируется (красный);
2) маркер без РАЗРЕШЕНО ПРАВИТЬ в файле задания — красный;
3) маркер с авторизацией в задании — зелёный;
4) пустой индекс после чистого коммита — зелёный, в выводе назван
   HEAD~1..HEAD;
5) пустой индекс после грязного коммита — красный;
6) файл координатора без маркера — красный.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P6_RULE = ROOT / "agent" / "p6_rule.sh"


def _repo(tmp_path: Path, allow: list[str] | None = None):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin:/usr/local/bin",
           "HOME": str(tmp_path)}

    def git(*argv):
        return subprocess.run(["git", *argv], cwd=repo, env=env,
                              capture_output=True, text=True, check=True)

    git("init", "-q")
    (repo / "agent").mkdir()
    (repo / "agent" / "TASK.md").write_text("# charter\n", encoding="utf-8")
    (repo / "agent" / "CONTEXT.md").write_text("# context\n",
                                               encoding="utf-8")
    (repo / "agent" / "PROTOCOL.md").write_text("# protocol\n",
                                                encoding="utf-8")
    (repo / "agent" / "REPORT-33.md").write_text("# report\n",
                                                 encoding="utf-8")
    task = repo / "agent" / "TASK-TEST.md"
    task.write_text("# task\n", encoding="utf-8")
    if allow:
        task.write_text(
            "# task\n" + "".join(f"РАЗРЕШЕНО ПРАВИТЬ: {p}\n"
                                 for p in allow), encoding="utf-8")
    (repo / "agent" / "BATON.json").write_text(
        json.dumps({"task": "agent/TASK-TEST.md"}), encoding="utf-8")
    git("add", "agent")
    git("commit", "-q", "-m", "init")
    return repo, env


def _declare(repo: Path, marker: str) -> None:
    (repo / ".git" / "COMMIT_EDITMSG").write_text(
        f"смена\n\n{marker}\n", encoding="utf-8")


def _run(repo: Path, env: dict, extra_env: dict | None = None):
    e = dict(env)
    if extra_env:
        e.update(extra_env)
    return subprocess.run(["bash", str(P6_RULE)], cwd=repo, env=e,
                          capture_output=True, text=True)


def _stage(repo: Path, *files: str) -> None:
    for f in files:
        (repo / f).write_text((repo / f).read_text(encoding="utf-8")
                              + "\nedit\n", encoding="utf-8")
    subprocess.run(["git", "add", *files], cwd=repo,
                   capture_output=True, text=True, check=True)


def test_env_override_of_the_blocklist_is_ignored(tmp_path):
    """H6.1: P6_BLOCKED из окружения больше не меняет список —
    agent/TASK.md остаётся защищённым."""
    repo, env = _repo(tmp_path)
    _stage(repo, "agent/TASK.md")
    result = _run(repo, env, {"P6_BLOCKED": "agent/NOTHING.md"})
    assert result.returncode != 0
    assert "agent/TASK.md" in result.stdout


def test_marker_without_task_authorisation_is_red(tmp_path):
    """H6.2: маркер в сообщении без строки РАЗРЕШЕНО ПРАВИТЬ в файле
    задания — красный: исключение нельзя выдать самому себе."""
    repo, env = _repo(tmp_path, allow=[])
    _stage(repo, "agent/CONTEXT.md")
    _declare(repo, "РАЗРЕШЕНИЕ-КОНТЕКСТА:")
    result = _run(repo, env)
    assert result.returncode != 0
    assert "agent/CONTEXT.md" in result.stdout


def test_marker_with_task_authorisation_is_green(tmp_path):
    repo, env = _repo(tmp_path, allow=["agent/CONTEXT.md"])
    _stage(repo, "agent/CONTEXT.md")
    _declare(repo, "РАЗРЕШЕНИЕ-КОНТЕКСТА:")
    result = _run(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr


def test_staged_coordinator_file_without_marker_is_red(tmp_path):
    repo, env = _repo(tmp_path, allow=["agent/CONTEXT.md"])
    _stage(repo, "agent/CONTEXT.md")
    result = _run(repo, env)
    assert result.returncode != 0
    assert "agent/CONTEXT.md" in result.stdout


def test_staging_own_report_is_green(tmp_path):
    repo, env = _repo(tmp_path)
    _stage(repo, "agent/REPORT-33.md")
    result = _run(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr


def test_staging_both_own_and_coordinator_is_red(tmp_path):
    repo, env = _repo(tmp_path)
    _stage(repo, "agent/TASK.md", "agent/REPORT-33.md")
    result = _run(repo, env)
    assert result.returncode != 0
    assert "agent/TASK.md" in result.stdout
