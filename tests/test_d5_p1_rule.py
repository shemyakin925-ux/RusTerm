"""ТЗ-32 D5: сторож P1 перестаёт мешать законной замене булавки.

Три случая из пункта (временный git-репозиторий, staged-diff):
1) снятие assert без блока ЗАМЕНА-БУЛАВКИ — красный;
2) снятие с блоком, но добавлено меньше assert, чем снято — красный;
3) объявленная замена с равным или большим числом добавленных —
   зелёный. Плюс: без снятых assert сторож зелёный всегда.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P1_RULE = ROOT / "agent" / "p1_rule.sh"

BASE = '''def check(x):
    assert x > 0
    assert x < 10
    return x
'''


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin:/usr/local/bin",
           "HOME": str(tmp_path)}
    src = repo / "pkg_pin.py"
    src.write_text(BASE, encoding="utf-8")
    def git(*argv):
        return subprocess.run(["git", *argv], cwd=repo, env=env,
                              capture_output=True, text=True, check=True)
    git("init", "-q")
    git("add", "pkg_pin.py")
    git("commit", "-q", "-m", "init")
    return repo, env, git


def _stage_edit(repo: Path, removed: int, added_block: str) -> None:
    """Снять `removed` assert-строк и добавить `added_block` новых."""
    body = BASE
    for _ in range(removed):
        body = body.replace("    assert x > 0\n", "", 1)
    body += added_block
    (repo / "pkg_pin.py").write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", "pkg_pin.py"], cwd=repo,
                   capture_output=True, text=True, check=True)


def _declare(repo: Path) -> None:
    """Записать декларацию замены в COMMIT_EDITMSG (так же, как это
    делает предстоящий git commit -m перед сторожем)."""
    block = ("ЗАМЕНА-БУЛАВКИ: pkg_pin.py::test_old -> "
             "pkg_pin.py::test_new\n"
             "ПОЧЕМУ СИЛЬНЕЕ: пин накрывает и старое, и границу\n")
    (repo / ".git" / "COMMIT_EDITMSG").write_text(
        "смена: булавка\n\n" + block, encoding="utf-8")


def _run(repo: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(P1_RULE)], cwd=repo, env=env,
                          capture_output=True, text=True)


def test_p1_removal_without_declaration_is_red(tmp_path):
    repo, env, git = _repo(tmp_path)
    _stage_edit(repo, removed=1, added_block="")
    result = _run(repo, env)
    assert result.returncode != 0
    assert "pkg_pin.py" in result.stdout + result.stderr


def test_p1_declared_but_fewer_asserts_added_is_red(tmp_path):
    repo, env, git = _repo(tmp_path)
    _stage_edit(repo, removed=1, added_block="def extra():\n    return 1\n")
    _declare(repo)
    result = _run(repo, env)
    assert result.returncode != 0
    assert "добавлено assert: 0, снято: 1" in result.stdout


def test_p1_declared_replacement_with_enough_asserts_is_green(tmp_path):
    repo, env, git = _repo(tmp_path)
    _stage_edit(repo, removed=1, added_block="assert True\n")
    _declare(repo)
    result = _run(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr


def test_p1_no_removals_is_always_green(tmp_path):
    repo, env, git = _repo(tmp_path)
    (repo / "pkg_pin.py").write_text(BASE + "# comment change\n",
                                     encoding="utf-8")
    subprocess.run(["git", "add", "pkg_pin.py"], cwd=repo,
                   capture_output=True, text=True, check=True)
    result = _run(repo, env)
    assert result.returncode == 0


# ── ТЗ-36 H6.3: пустой индекс — не зелёный свет ────────────────────────

def _commit_current(repo: Path, env: dict, message: str):
    subprocess.run(["git", "commit", "-q", "-a", "-m", message],
                   cwd=repo, env=env, capture_output=True, text=True)


def test_p1_empty_index_after_clean_commit_is_green_named(tmp_path):
    repo, env, git = _repo(tmp_path)
    (repo / "pkg_pin.py").write_text(BASE + "\n# tidy\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-a", "-m", "tidy"],
                   cwd=repo, env=env, capture_output=True, text=True)
    result = _run(repo, env)
    assert result.returncode == 0
    assert "HEAD~1..HEAD" in result.stdout, result.stdout


def test_p1_empty_index_after_dirty_commit_is_red_named(tmp_path):
    repo, env, git = _repo(tmp_path)
    body = BASE.replace("    assert x > 0\n", "")
    (repo / "pkg_pin.py").write_text(body, encoding="utf-8")
    _commit_current(repo, env, "удалил assert без объявления")
    result = _run(repo, env)
    assert result.returncode != 0
    assert "HEAD~1..HEAD" in result.stdout, result.stdout


def test_p1_empty_index_declared_replacement_is_green(tmp_path):
    repo, env, git = _repo(tmp_path)
    body = BASE.replace("    assert x > 0\n", "") + "    assert x >= 0\n"
    (repo / "pkg_pin.py").write_text(body, encoding="utf-8")
    message = ("замена\n\n"
               "ЗАМЕНА-БУЛАВКИ: pkg_pin.py::a -> pkg_pin.py::b\n"
               "ПОЧЕМУ СИЛЬНЕЕ: накрывает границу")
    _commit_current(repo, env, message)
    result = _run(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HEAD~1..HEAD" in result.stdout
