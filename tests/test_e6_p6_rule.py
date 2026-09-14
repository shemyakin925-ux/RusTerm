"""ТЗ-33 E6: сторож P6 — файлы координатора не касаются исполнителю.

Три случая (временный git-репозиторий, staged-diff):
1) staging agent/TASK.md — красный с именем файла;
2) staging agent/REPORT-33.md — зелёный;
3) staging оба — красный.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P6_RULE = ROOT / "agent" / "p6_rule.sh"


def _repo(tmp_path: Path):
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
    (repo / "agent" / "REPORT-33.md").write_text("# report\n",
                                                 encoding="utf-8")
    git("add", "agent")
    git("commit", "-q", "-m", "init")
    return repo, env


def _stage(repo: Path, *files: str) -> subprocess.CompletedProcess:
    for f in files:
        (repo / f).write_text((repo / f).read_text(encoding="utf-8")
                              + "\nedit\n", encoding="utf-8")
    subprocess.run(["git", "add", *files], cwd=repo,
                   capture_output=True, text=True, check=True)
    return subprocess.run(["bash", str(P6_RULE)], cwd=repo,
                          capture_output=True, text=True)


def test_staging_task_md_is_red_with_file_named(tmp_path):
    repo, env = _repo(tmp_path)
    result = _stage(repo, "agent/TASK.md")
    assert result.returncode != 0
    assert "agent/TASK.md" in result.stdout
    assert "git restore --staged" in result.stdout


def test_staging_own_report_is_green(tmp_path):
    repo, env = _repo(tmp_path)
    result = _stage(repo, "agent/REPORT-33.md")
    assert result.returncode == 0, result.stdout + result.stderr


def test_staging_both_is_red(tmp_path):
    repo, env = _repo(tmp_path)
    result = _stage(repo, "agent/TASK.md", "agent/REPORT-33.md")
    assert result.returncode != 0
    assert "agent/TASK.md" in result.stdout
