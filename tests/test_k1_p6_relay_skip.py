"""ТЗ-43 K1: пропуск коммита эстафеты опирается на проверяемое.

- коммит с сообщением «Эстафета: круг 99», правящий agent/CONTEXT.md
  без изменения BATON.json, — КРАСНЫЙ (обход 95b669a закрыт);
- настоящий коммит эстафеты (BATON.json изменился + файлы
  координатора) — зелёный;
- неменяющийся BATON с сообщением эстафеты — красный.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
P6_RULE = ROOT / "agent" / "p6_rule.sh"

RELAY_PREFIX = "Эстафета: круг 99, ход у executor — agent/TASK-42.md"

COORDINATOR_SET = {
    "agent/BATON.json": '{"holder": "coordinator", "round": 99}',
    "agent/TASK-42.md": "# TASK-42\n",
    "agent/CONTEXT.md": "# context, обновлён координатором\n",
    "agent/BACKLOG.md": "# backlog\n",
    "agent/LAUNCH.md": "# launch\n",
}


def _repo(tmp_path: Path, files: dict[str, str],
          message: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "HOME": str(tmp_path)}

    def git(*argv: str, check: bool = True):
        return subprocess.run(["git", *argv], cwd=repo, env=env,
                              capture_output=True, text=True,
                              check=check)

    git("init", "-q", "-b", "agent/night-test")
    (repo / "agent").mkdir()
    (repo / "README.md").write_text("# init\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    for path, text in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", message)
    return repo, env


def _run_p6(repo: Path, env: dict):
    return subprocess.run(["bash", str(P6_RULE)], cwd=repo, env=env,
                          capture_output=True, text=True)


def test_forged_relay_message_editing_context_is_red(tmp_path):
    """Дословное воспроизведение обхода координатора: сообщение
    «Эстафета: круг 99», правит agent/CONTEXT.md, BATON не тронут —
    красный."""
    files = dict(COORDINATOR_SET)
    files.pop("agent/BATON.json")  # BATON в коммите НЕ менялся
    files["agent/CONTEXT.md"] = "# context, несанкционированная правка\n"
    repo, env = _repo(tmp_path, files, RELAY_PREFIX)
    result = _run_p6(repo, env)
    assert result.returncode != 0
    # красный называет проверяемую причину: BATON не менялся
    assert "BATON.json не менялся" in result.stdout


def test_real_relay_commit_still_skipped(tmp_path):
    """Настоящий коммит эстафеты: BATON изменился, состав — только
    файлы координатора: пропускается."""
    repo, env = _repo(tmp_path, COORDINATOR_SET, RELAY_PREFIX)
    result = _run_p6(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "коммит эстафеты, пропущен" in result.stdout


def test_relay_commit_carrying_executor_file_is_red(tmp_path):
    """«Эстафета» с BATON, но с файлом исполнителя внутри — красный."""
    files = dict(COORDINATOR_SET)
    files["agent/p6_rule.sh"] = "# расширенный страж исполнителя\n"
    repo, env = _repo(tmp_path, files, RELAY_PREFIX)
    result = _run_p6(repo, env)
    assert result.returncode != 0
    assert "agent/p6_rule.sh" in result.stdout
