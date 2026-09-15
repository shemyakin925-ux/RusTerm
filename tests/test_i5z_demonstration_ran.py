"""ТЗ-36 I8: приёмка не может пройти молча без демонстрации I5.

Sentinel-тест идёт ПОСЛЕ модуля демонстрации по алфавиту и требует:
либо демонстрация I5 выполнилась в этом процессе (маркер), либо
прогон явно вложенный (I5_NESTED=1 — хук и зелёный случай I5).
Пропуск модуля по любой иной причине красит приёмку с объяснением.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except (TypeError, ValueError):
        return False


def test_i5_demonstration_ran_or_legitimately_nested():
    """Приёмка гоняет весь набор ДВАЖДЫ (check 3 и check 11 без
    zstandard) — двумя разными процессами. Маркер демонстрации свеж:
    его pid жив ИЛИ файл записан не позже 30 минут назад — за это
    время пара прогонов приёмки успевает обновить его. Древний маркер
    мёртвого процесса и его отсутствие — красные с объяснением."""
    if os.environ.get("I5_NESTED") == "1":
        return  # хук и зелёный случай I5: легитимный пропуск
    marker = (Path(tempfile.gettempdir()) / "i5-demo-ran.json")
    assert marker.exists(), (
        "I5 демонстрация не выполнялась в этом прогоне (модуль "
        "пропущен) — приёмка не может пройти без неё (ТЗ-36 I8)")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    pid = payload.get("pid")
    fresh = marker.stat().st_mtime >= (time.time() - 1800)
    assert _pid_alive(pid) or fresh, (
        f"маркер демонстрации протух (pid {pid}, мёртв, файл старый) — "
        "этот прогон приёмки прошёл без демонстрации I5")
