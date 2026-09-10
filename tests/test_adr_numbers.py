"""BACKLOG B31: номера ADR распределяются заданиями (0013 — ТЗ-20 L10,
0015 — ТЗ-24 N10, 0016 — ТЗ-26 Q11); страж не даёт двум файлам
претендовать на один номер. Документация заморожена — страж читает
docs/adr/, не пишет.
"""
from __future__ import annotations

import re
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parents[1] / "docs" / "adr"
_NUMBER_RE = re.compile(r"^(\d{4})-")


def test_adr_numbers_are_unique():
    numbers: dict[str, str] = {}
    for path in sorted(ADR_DIR.glob("*.md")):
        match = _NUMBER_RE.match(path.name)
        assert match, f"в имени ADR нет номера: {path.name}"
        number = match.group(1)
        assert number not in numbers, (
            f"номер {number} у двух ADR: {numbers[number]} и {path.name}")
        numbers[number] = path.name
    assert len(numbers) >= 13  # 0001–0012 и 0014 на текущую ночь
