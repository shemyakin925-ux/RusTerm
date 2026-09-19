"""ТЗ-36 I8: приёмка не может пройти молча без демонстрации I5.

Sentinel-тест идёт ПОСЛЕ модуля демонстрации по алфавиту и требует:
либо демонстрация I5 выполнилась в этом процессе (маркер), либо
прогон явно вложенный (I5_NESTED=1 — хук и зелёный случай I5).
Пропуск модуля по любой иной причине красит приёмку с объяснением.

ТЗ-45 M2: маркер сверяется по session id ЭТОГО прогона. Прежняя
проверка «pid жив ИЛИ файл свежий» пропускала маркер чужого прогона;
теперь свежесть и живость не помогают — session чужой, приёмка красная.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_i5_guard_source import DEMO_SESSION_ID, _marker_path

ROOT = Path(__file__).resolve().parents[1]
MARKER = _marker_path()


def test_i5_demonstration_ran_or_legitimately_nested():
    """Приёмка гоняет весь набор ДВАЖДЫ (check 3 и check 11 без
    zstandard) — двумя разными процессами. Каждый процесс пишет СВОЙ
    session id в маркер (фикстура модуля демонстрации при импорте),
    поэтому маркер чужого прогона совпасть не может: ни отсутствие
    маркера, ни чужой session зелёной приёмку не делают."""
    if os.environ.get("I5_NESTED") == "1":
        return  # хук и зелёный случай I5: легитимный пропуск
    assert MARKER.exists(), (
        "I5 демонстрация не выполнялась в этом прогоне (модуль "
        "пропущен) — приёмка не может пройти без неё (ТЗ-36 I8)")
    payload = json.loads(MARKER.read_text(encoding="utf-8"))
    session = payload.get("session")
    assert session == DEMO_SESSION_ID, (
        f"маркер демонстрации ЧУЖОГО прогона (его session {session!r}, "
        f"его pid {payload.get('pid')!r}; этот прогон "
        f"{DEMO_SESSION_ID!r}) — приёмка прошла без демонстрации I5 "
        "(ТЗ-45 M2)")


@pytest.mark.skipif(
    os.environ.get("I5_NESTED") == "1",
    reason="вложенный прогон приёмки: sentinel там легитимно "
           "молчит, чужой маркер нечему красить")
def test_foreign_session_marker_does_not_green_the_run():
    """ТЗ-45 M2: маркер с чужим session — свежий, от живого процесса —
    приёмку зелёной не делает: sentinel в отдельном процессе красный
    с объяснением. Маркер этого прогона возвращается в finally."""
    saved = MARKER.read_bytes() if MARKER.exists() else None
    try:
        foreign = {"pid": os.getpid(),  # живой процесс
                   "session": "foreign-session-not-this-run"}
        MARKER.write_text(json.dumps(foreign), encoding="utf-8")
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "-q",
             "tests/test_i5z_demonstration_ran.py::"
             "test_i5_demonstration_ran_or_legitimately_nested"],
            cwd=ROOT, capture_output=True, text=True)
        assert out.returncode != 0, out.stdout[-800:]
        combined = out.stdout + out.stderr
        assert "ЧУЖОГО прогона" in combined, combined[-800:]
    finally:
        if saved is None:
            MARKER.unlink(missing_ok=True)
        else:
            MARKER.write_bytes(saved)
