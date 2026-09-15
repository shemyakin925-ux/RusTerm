"""ТЗ-42 J3: сторож P6 не обвиняет коммит эстафеты координатора.

- коммит эстафеты (сообщение «Эстафета: круг N», внутри — только
  BATON.json и файлы координатора) — зелёный;
- тот же текст сообщения, но внутри чужой (исполнительский) файл —
  красный;
- обычный исполнительский коммит — не является коммитом эстафеты и
  оценивается как раньше.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P6_RULE = ROOT / "agent" / "p6_rule.sh"

RELAY_MESSAGE = ("Эстафета: круг 48, ход у executor — agent/TASK-38.md")

COORDINATOR_FILES = {
    "agent/BATON.json": '{"holder": "coordinator", "round": 48}',
    "agent/TASK-38.md": "# TASK-38\n",
    "agent/CONTEXT.md": "# context, updated\n",
    "agent/BACKLOG.md": "# backlog\n",
    "agent/LAUNCH.md": "# launch\n",
}


def _repo(tmp_path: Path, head_files: dict[str, str]):
    """Репозиторий, чей HEAD — коммит с заданным составом и
    сообщением эстафеты."""
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
    # начальный коммит: HEAD~1 обязан существовать (дифф последнего
    # коммита — то, что смотрит сторож)
    (repo / "README.md").write_text("# init\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    for path, text in head_files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", RELAY_MESSAGE)
    return repo, env


def _run_p6(repo: Path, env: dict):
    return subprocess.run(["bash", str(P6_RULE)], cwd=repo, env=env,
                          capture_output=True, text=True)


def test_relay_commit_is_green(tmp_path):
    repo, env = _repo(tmp_path, COORDINATOR_FILES)
    result = _run_p6(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "коммит эстафеты, пропущен" in result.stdout


def test_relay_label_with_executor_file_inside_is_red(tmp_path):
    """Тот же текст сообщения, но внутри — файл исполнителя: красный,
    несмотря на «Эстафета:» в сообщении."""
    files = dict(COORDINATOR_FILES)
    files["agent/p6_rule.sh"] = "# расширенный страж исполнителя\n"
    repo, env = _repo(tmp_path, files)
    result = _run_p6(repo, env)
    assert result.returncode != 0
    assert "agent/p6_rule.sh" in result.stdout


def test_plain_executor_commit_is_not_relay(tmp_path):
    """Обычный коммит исполнителя (его файлы, его сообщение) — не
    коммит эстафеты: сторож смотрит его как раньше."""
    repo, env = _repo(tmp_path, {
        "agent/BATON.json": '{"holder": "executor", "round": 48}',
        "tests/test_x.py": "def test_x():\n    assert True\n",
        "agent/REPORT-38.md": "# отчёт исполнителя\n",
    })
    # HEAD уже с сообщением эстафеты от фикстуры; перепишем сообщение
    # последнего коммита на исполнительский
    subprocess.run(["git", "commit", "-q", "--amend", "-m",
                    "ТЗ-38: работа исполнителя"], cwd=repo, env=env,
                   capture_output=True, text=True, check=True)
    result = _run_p6(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "коммит эстафеты, пропущен" not in result.stdout
