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
from pathlib import Path


def test_i5_demonstration_ran_or_legitimately_nested():
    if os.environ.get("I5_NESTED") == "1":
        return  # хук и зелёный случай I5: легитимный пропуск
    marker = (Path(tempfile.gettempdir()) / "i5-demo-ran.json")
    assert marker.exists(), (
        "I5 демонстрация не выполнялась в этом прогоне (модуль "
        "пропущен) — приёмка не может пройти без неё (ТЗ-36 I8)")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload.get("pid") == os.getpid(), (
        "маркер демонстрации от другого процесса — этот прогон "
        "демонстрацию не выполнял")
