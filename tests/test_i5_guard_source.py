"""ТЗ-37 I5: страж исполняется из коммита, а не из рабочего дерева.

Воспроизведение манёвра 95b669a end to end:
- правка agent/CONTEXT.md застейджена, agent/p6_rule.sh расширен
  ТОЛЬКО в рабочем дереве -> selfcheck красный и называет страж;
- то же расширение, но ЗАСТЕЙДЖЕННОЕ (задание разрешает строкой
  РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh) -> зелёный, и в выводе видно,
  что исполнялась копия из index.

Оба случая гоняют настоящий bash agent/selfcheck.sh. Вложенный
прогон приёмки (selfcheck запускает pytest) пропускает сами тесты
I5 через переменную I5_NESTED, чтобы не рекурсироваться.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Расширение для зелёного случая: поведение то же (красные случаи
# p6 остаются красными), но копию из index видно по строке-маркеру.
WIDENED = (Path("agent/p6_rule.sh").read_text(encoding="utf-8")
           .replace('echo "P6:', 'echo "P6 [index-copy]:')
           + '\necho "P6: index-copy demo I5"\n')





def _git(*argv: str, check: bool = True):
    return subprocess.run(["git", *argv], cwd=ROOT,
                          capture_output=True, text=True, check=check)


def _selfcheck(extra: dict | None = None):
    env = dict(os.environ)
    env.update(extra or {})
    return subprocess.run(["bash", "agent/selfcheck.sh"], cwd=ROOT,
                          env=env, capture_output=True, text=True)


def _nested() -> bool:
    return bool(os.environ.get("I5_NESTED"))


@pytest.mark.skipif(_nested(), reason="вложенный прогон приёмки")
def test_i5_working_tree_widening_is_red_and_named(tmp_path):
    try:
        ctx = ROOT / "agent" / "CONTEXT.md"
        ctx.write_text(ctx.read_text(encoding="utf-8")
                       + "\nI5 red demo\n", encoding="utf-8")
        _git("add", "agent/CONTEXT.md")
        guard = ROOT / "agent" / "p6_rule.sh"
        saved = guard.read_text(encoding="utf-8")
        guard.write_text(WIDENED, encoding="utf-8")  # НЕ стейджится
        editmsg = subprocess.run(
            ["git", "rev-parse", "--git-path", "COMMIT_EDITMSG"],
            cwd=ROOT, capture_output=True, text=True,
            check=True).stdout.strip()
        Path(editmsg).write_text(
            "demo\n\nРАЗРЕШЕНИЕ-КОНТЕКСТА: demo\n", encoding="utf-8")
        result = _selfcheck()
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "agent/p6_rule.sh" in combined, combined[-800:]
        assert "рабочем дереве" in combined, combined[-800:]
    finally:
        _git("restore", "--staged", "agent/CONTEXT.md",
             "agent/p6_rule.sh", check=False)
        _git("checkout", "--", "agent/CONTEXT.md", "agent/p6_rule.sh",
             check=False)
        editmsg = subprocess.run(
            ["git", "rev-parse", "--git-path", "COMMIT_EDITMSG"],
            cwd=ROOT, capture_output=True, text=True,
            check=True).stdout.strip()
        Path(editmsg).write_text("", encoding="utf-8")


@pytest.mark.skipif(_nested(), reason="вложенный прогон приёмки")
def test_i5_staged_and_authorised_widening_is_green(tmp_path):
    try:
        guard = ROOT / "agent" / "p6_rule.sh"
        saved = guard.read_text(encoding="utf-8")
        guard.write_text(WIDENED, encoding="utf-8")
        _git("add", "agent/p6_rule.sh")  # расширение ЗАСТЕЙДЖЕНО
        # agent/TASK-37.md несёт РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh
        editmsg = subprocess.run(
            ["git", "rev-parse", "--git-path", "COMMIT_EDITMSG"],
            cwd=ROOT, capture_output=True, text=True,
            check=True).stdout.strip()
        Path(editmsg).write_text(
            "I5 green demo\n\nРАЗРЕШЕНИЕ-КОНТЕКСТА: demo\n",
            encoding="utf-8")
        result = _selfcheck({"I5_NESTED": "1"})
        assert result.returncode == 0, (
            result.stdout[-1500:] + result.stderr[-800:])
        combined = result.stdout + result.stderr
        assert "p6_rule.sh исполняется из index" in combined
    finally:
        _git("restore", "--staged", "agent/p6_rule.sh",
             check=False)
        _git("checkout", "--", "agent/p6_rule.sh", check=False)
        editmsg = subprocess.run(
            ["git", "rev-parse", "--git-path", "COMMIT_EDITMSG"],
            cwd=ROOT, capture_output=True, text=True,
            check=True).stdout.strip()
        Path(editmsg).write_text("", encoding="utf-8")
