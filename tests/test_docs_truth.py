"""Страж: README не называет чисел о самом себе, которые гниют.

Дефект, ради которого страж заведён (находка координатора 11.09.2026):
ТЗ-19 пунктом F9 переписало §15 «чтобы README говорил правду» — и там
же появилось «тестовый набор — 402 пройдено», которое устарело к концу
той же смены (411). Тем же вечером ADR-0017 сделал ложной фразу
«зафиксирована в тринадцати ADR».

Правило: число о репозитории либо выводится из репозитория, либо не
пишется. Перечень ADR — выводится: страж требует, чтобы каждый файл
docs/adr/ был назван в README, поэтому новый ADR нельзя добавить, не
обновив роадмап.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ADR_DIR = ROOT / "docs" / "adr"

# Рукописные счётчики: «402 пройдено», «2 пропущено», «тринадцати ADR»,
# «13 ADR», «411 тестов». Приёмка «13 из 13» — не счётчик, а контракт
# фиксированного набора проверок, и под запрет не попадает.
_BANNED = (
    re.compile(r"\d+\s+пройдено"),
    re.compile(r"\d+\s+пропущено"),
    re.compile(r"\d+\s+(?:тест|теста|тестов)\b"),
    re.compile(r"\d+\s+ADR\b"),
    re.compile(
        r"\b(?:трёх|четырёх|пяти|шести|семи|восьми|девяти|десяти|"
        r"одиннадцати|двенадцати|тринадцати|четырнадцати|пятнадцати|"
        r"шестнадцати|семнадцати|восемнадцати|девятнадцати|двадцати)\s+ADR\b"
    ),
)


def test_readme_names_no_hand_typed_count():
    text = README.read_text(encoding="utf-8")
    hits = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in _BANNED:
            match = pattern.search(line)
            if match:
                hits.append(f"README.md:{line_no}: {match.group(0)!r}")
    assert not hits, (
        "рукописное число о репозитории в README — оно устареет: "
        + "; ".join(hits))


def test_readme_lists_every_adr():
    """Перечень ADR в README выводится из docs/adr/, а не из памяти."""
    text = README.read_text(encoding="utf-8")
    numbers = sorted(p.name[:4] for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert numbers, "docs/adr/ пуст — страж потерял предмет"
    missing = [n for n in numbers if f"({n})" not in text]
    assert not missing, (
        "ADR есть в docs/adr/, но не назван в README §15: "
        + ", ".join(missing))
