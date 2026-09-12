"""ТЗ-21 H7: повторяющийся дефект «замаскированного кода выхода»
невозможен структурно.

Три утверждения:
1. agent/selfcheck.sh читает статус приёмки ИЗ ФАЙЛА (перенаправление
   до всякого пайпа), а не из пайпа;
2. selfcheck не может выйти 0 при грязном дереве — поведенчески:
   неотслеживаемый файл даёт ненулевой выход с именем проверки;
3. agent/acceptance.sh байт-в-байт совпадает с origin/main — та же
   проверка, что и пункт 12 приёмки, но видимая из обычного pytest.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELFCHECK = ROOT / "agent" / "selfcheck.sh"


def test_selfcheck_captures_acceptance_status_before_piping():
    text = SELFCHECK.read_text(encoding="utf-8")
    # приёмка пишется в файл, статус читается отдельно
    assert "acceptance.sh > \"$ACC\" 2>&1" in text
    assert "ACC_STATUS=$?" in text
    assert "[ \"$ACC_STATUS\" -eq 0 ]" in text
    # статус решает выход: провал гасит скрипт
    assert "fail \"acceptance\" \"exit status $ACC_STATUS\"" in text
    # строки печатаются только после того, как статус известен
    tail_pos = text.index('tail -4 "$ACC"')
    status_pos = text.index("ACC_STATUS=$?")
    assert status_pos < tail_pos


def test_selfcheck_cannot_exit_zero_with_dirty_tree():
    """Поведенчески: неотслеживаемый файл — ненулевой выход и имя
    проверки, БЕЗ полного прогона приёмки (страж P3 срабатывает
    раньше)."""
    junk = ROOT / "h7-deliberate-junk.txt"
    junk.write_text("deliberate untracked file for H7\n",
                    encoding="utf-8")
    try:
        result = subprocess.run(
            ["bash", str(SELFCHECK)], capture_output=True, text=True,
            cwd=ROOT)
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "P3/P4" in combined
        assert "h7-deliberate-junk.txt" in combined
    finally:
        junk.unlink(missing_ok=True)


def test_acceptance_script_byte_identical_to_origin_main():
    origin = subprocess.run(
        ["git", "show", "origin/main:agent/acceptance.sh"],
        capture_output=True, text=True, cwd=ROOT)
    assert origin.returncode == 0
    local = (ROOT / "agent" / "acceptance.sh").read_text(
        encoding="utf-8")
    assert local == origin.stdout, (
        "agent/acceptance.sh отличается от origin/main — правка "
        "приёмки запрещена (проверка 12)")
