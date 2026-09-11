"""Фикстуры — только синтетические (BACKLOG B2, TASK-2 §2).

Каждый файл в fixtures/ несёт synthetic в имени и в теле. Придуманное
число, не помеченное как выдуманное, рано или поздно уезжает в отчёт
под видом данных эмитента — дисциплина проверяется машиной, а не
на честном слове.
"""
from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_fixtures_are_synthetic():
    files = sorted(p for p in FIXTURES.rglob("*") if p.is_file())
    assert files, "в fixtures/ не осталось ни одного файла"
    for path in files:
        assert "synthetic" in path.name.lower(), (
            f"{path}: в имени файла нет пометки synthetic")
        body = path.read_text(encoding="utf-8", errors="replace").lower()
        assert "synthetic" in body or "синтетическ" in body, (
            f"{path}: в теле файла нет пометки synthetic/синтетическ")
