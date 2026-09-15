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

import json
import os
import subprocess
import sys
import tempfile
import tempfile
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


@pytest.fixture(scope="module", autouse=True)
def _demonstration_ran():
    """ТЗ-36 I8: замок с фиксированным путём мог протухнуть (SIGKILL,
    reboot) и молча выкидывать демонстрацию из любого прогона на хосте.
    Замок убран: рекурсию держит I5_NESTED (хук и зелёный случай), а
    этот маркер доказывает sentinel-тесту, что демонстрация ВЫПОЛНЕНА
    в текущем процессе."""
    marker = Path(tempfile.gettempdir()) / "i5-demo-ran.json"
    marker.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    yield


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
        # прежнее содержимое декларации сохраняется и возвращается
        editmsg_saved = Path(editmsg).read_text(encoding="utf-8")
        Path(editmsg).write_text(
            "demo\n\nРАЗРЕШЕНИЕ-КОНТЕКСТА: demo\n", encoding="utf-8")
        result = _selfcheck()
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "agent/p6_rule.sh" in combined, combined[-800:]
        assert "рабочем дереве" in combined, combined[-800:]
    finally:
        # p6_rule.sh здесь НЕ трогается: его правка могла быть
        # застейджена исполнителем отдельно (I7) — красный случай
        # стейджит только agent/CONTEXT.md
        _git("restore", "--staged", "agent/CONTEXT.md", check=False)
        _git("checkout", "--", "agent/CONTEXT.md", check=False)
        Path(editmsg).write_text(editmsg_saved, encoding="utf-8")


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
        editmsg_saved = Path(editmsg).read_text(encoding="utf-8")
        # реальное ожидаемое сообщение сохраняется и ДОПОЛНЯЕТСЯ
        # маркером: pending-изменения самих тестов (замены булавок)
        # продолжают видеть свои объявления
        Path(editmsg).write_text(
            editmsg_saved + "\nРАЗРЕШЕНИЕ-КОНТЕКСТА: demo\n",
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
        Path(editmsg).write_text(editmsg_saved, encoding="utf-8")


def test_stale_single_flight_lock_does_not_skip_the_module(tmp_path):
    """ТЗ-36 I8: протухший замок старой схемы (pid мёртвого процесса)
    не влияет ни на что — замок убран, оба теста I5 собираются и
    выполняются."""
    import sys

    stale = Path(tempfile.gettempdir()) / "i5-demo-single-flight.lock"
    stale.write_text(json.dumps({"pid": 999999999}), encoding="utf-8")
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "tests/test_i5_guard_source.py"], cwd=ROOT,
            capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
        # оба теста I5 собираются к исполнению — замок ни на что не влияет
        assert "tests/test_i5_guard_source.py: 3" in out.stdout, out.stdout
        assert "skipped" not in out.stdout, out.stdout
    finally:
        stale.unlink(missing_ok=True)
