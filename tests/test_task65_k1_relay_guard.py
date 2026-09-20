"""ТЗ-65 K1: эстафетный коммит перестаёт быть щелью. Аудит-режим
красит настоящие коммиты круга 82 (8923c31, b3b55ef несли работу),
чистая передача 5e9ee84 зелёная; ребейз, тащащий работу, красится
пре-коммитом; обычный рабочий коммит зелёный."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _p7(*argv, cwd=REPO):
    guard = REPO / "agent" / "p7_relay_rule.sh"
    return subprocess.run(["bash", str(guard), *argv],
                          cwd=cwd, capture_output=True, text=True)


def test_round82_work_carrying_relays_are_red():
    for sha in ("8923c31", "b3b55ef"):
        r = _p7(f"check:{sha}")
        assert r.returncode == 1, (sha, r.stdout, r.stderr)
        assert "несёт работу" in r.stderr


def test_pure_hand_is_green():
    r = _p7("check:5e9ee84")
    assert r.returncode == 0, r.stdout
    assert "чистая передача" in r.stdout


def test_normal_commit_is_green():
    r = _p7("check:2865299")  # ТЗ-63: обычный рабочий коммит
    assert r.returncode == 0, r.stdout


def test_rebase_arm_reds_in_scratch_clone(tmp_path):
    """Ребейз, переносящий эстафетный коммит с работой, красится
    пре-коммитом (EDITMSG = subject перенесённого коммита)."""
    scratch = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(REPO), str(scratch)],
                   check=True, capture_output=True)
    env_git = ["git", "-C", str(scratch)]
    subprocess.run(env_git + ["config", "user.email", "t@t"],
                   check=True, capture_output=True)
    subprocess.run(env_git + ["config", "user.name", "t"],
                   check=True, capture_output=True)
    # эстафетный коммит с работой (как круг 82)
    (scratch / "work.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(env_git + ["add", "work.py"], check=True)
    subprocess.run(env_git + ["commit", "-q", "-m",
                              "Эстафета: круг 9, ход у executor"], check=True)
    # ребейз: правим родителя — перезапись потребует перенос коммита
    git_dir = scratch.resolve().joinpath(".git")
    rebase_dir = git_dir / "rebase-merge"
    rebase_dir.mkdir()
    (rebase_dir / "head-name").write_text("refs/heads/main",
                                          encoding="utf-8")
    editmsg = scratch.resolve().joinpath(".git", "COMMIT_EDITMSG")
    editmsg.write_text("Эстафета: круг 9, ход у executor\n",
                       encoding="utf-8")
    (scratch / "work2.py").write_text("x = 2\n", encoding="utf-8")
    subprocess.run(env_git + ["add", "work2.py"], check=True)
    r = _p7("precommit", cwd=scratch)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "тащит работу" in r.stderr


def test_round84_relay_with_work_is_red():
    """8ea2e0d — эстафетный заголовок круга 84, нёсший работу J-круга:
    красный (ТЗ-66 L1)."""
    r = _p7("check:8ea2e0d")
    assert r.returncode == 1
    assert "несёт работу" in r.stderr
