"""ТЗ-37 I7: авторизация P6 работает в linked worktree.

Временный `git worktree add --detach` (там .git — файл): его
agent/BATON.json указывает на одноразовый файл задания с
`РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md`; agent/CONTEXT.md стейджится,
декларация РАЗРЕШЕНИЕ-КОНТЕКСТА пишется в путь, который называет
`git rev-parse --git-path COMMIT_EDITMSG`.

- I7_BASE=HEAD (по умолчанию): P6 зелёный — декларация видна;
- I7_BASE=1459cbb: P6 красный и называет agent/CONTEXT.md — на
  сегодняшнем коде декларация в worktree невидима (буквальный
  .git/COMMIT_EDITMSG).

Страж вызывается напрямую (bash agent/p6_rule.sh) — без вложенной
приёмки.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _base() -> str:
    """База worktree: I7_BASE, если задан; иначе дерево индекса, когда
    p6_rule.sh застейджен с изменениями (тест проверяет то, что
    коммится), иначе HEAD."""
    override = os.environ.get("I7_BASE")
    if override:
        return override
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--",
         "agent/p6_rule.sh"], cwd=ROOT, capture_output=True, text=True,
        env=_hermetic_env())
    if staged.stdout.strip():
        # worktree требует коммит: дерево индекса заворачивается во
        # временный висячий коммит — ссылки не двигаются
        tree = subprocess.run(["git", "write-tree"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True,
                              env=_hermetic_env()).stdout.strip()
        return subprocess.run(
            ["git", "commit-tree", tree, "-p", "HEAD", "-m",
             "i7 temporary base"], cwd=ROOT, capture_output=True,
            text=True, check=True, env=_hermetic_env()).stdout.strip()
    return "HEAD"


pytestmark = pytest.mark.skipif(
    bool(os.environ.get("I5_NESTED")),
    reason="вложенная приёмка пропускает демонстрации I5/I7")


# Протечки хука: pre-commit в линкованном worktree держит в окружении
# АБСОЛЮТНЫЙ GIT_DIR настоящего репозитория, и голый `git add` во
# временном worktree уезжал в настоящий индекс — agent/CONTEXT.md,
# agent/BATON.json и scratch-task.md оказывались застейджены в рабочей
# копии координатора (находка 17.09.2026, та же порода, что закрыта в
# ТЗ-46 для песочниц j1 и e6).
_LEAKED_GIT_ENV = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
                   "GIT_OBJECT_DIRECTORY",
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES")


def _hermetic_env() -> dict:
    env = dict(os.environ)
    for leaked in _LEAKED_GIT_ENV:
        env.pop(leaked, None)
    return env


def _git(*argv: str, cwd: Path, check: bool = True):
    return subprocess.run(["git", *argv], cwd=cwd, capture_output=True,
                          text=True, check=check, env=_hermetic_env())


@pytest.fixture()
def worktree(tmp_path: Path):
    base = _base()
    wt = tmp_path / "i7-worktree"
    _git("worktree", "add", "--detach", str(wt), base, cwd=ROOT)
    yield wt, base
    subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                   cwd=ROOT, capture_output=True, text=True,
                   env=_hermetic_env())


def _authorise_and_stage(wt: Path) -> None:
    """Одноразовые BATON + файл задания с авторизацией; CONTEXT.md
    стейджится; декларация — в git-path COMMIT_EDITMSG."""
    # одноразовый файл задания — вне agent/, чтобы шаблон
    # agent/TASK-*.md его не блокировал
    (wt / "scratch-task.md").write_text(
        "scratch\nРАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md\n",
        encoding="utf-8")
    (wt / "agent" / "BATON.json").write_text(
        json.dumps({"task": "scratch-task.md"}), encoding="utf-8")
    ctx = wt / "agent" / "CONTEXT.md"
    ctx.write_text(ctx.read_text(encoding="utf-8") + "\nI7 demo\n",
                   encoding="utf-8")
    _git("add", "agent/CONTEXT.md", "agent/BATON.json",
         "scratch-task.md", cwd=wt)
    editmsg = _git("rev-parse", "--git-path", "COMMIT_EDITMSG",
                   cwd=wt).stdout.strip()
    Path(editmsg).write_text(
        "I7 demo\n\nРАЗРЕШЕНИЕ-КОНТЕКСТА: демонстрация авторизации\n",
        encoding="utf-8")


def test_p6_sees_the_declaration_in_a_worktree(worktree):
    """На исправленном коде (I7_BASE=HEAD) декларация видна в
    worktree: P6 зелёный. На 1459cbb — красный с именем файла."""
    wt, base = worktree
    _authorise_and_stage(wt)
    result = subprocess.run(["bash", "agent/p6_rule.sh"], cwd=wt,
                            capture_output=True, text=True)
    if base == "HEAD":
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert "agent/CONTEXT.md" in result.stdout
