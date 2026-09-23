"""ТЗ-82 E1 — чем живёт пункт «профили и зависимость».

E2–E4 дописывают этот файл свойствами; здесь то, что проверяет сам E1:
Hypothesis объявлена в группе `test`, профили регистрирует conftest,
выбор делает переменная HYPOTHESIS_PROFILE, и рантайм библиотеку не
импортирует (ADR-0024). `import hypothesis` здесь без importorskip:
свойство, которое смолчало в прогоне, выглядит зелёным и ничего не
доказывает.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from hypothesis import given, settings, strategies as st

from rusterm import formulas

REPO = Path(__file__).resolve().parents[1]


def test_profile_comes_from_the_environment():
    """Один рычаг — HYPOTHESIS_PROFILE; без него прогон идёт default."""
    assert settings.get_current_profile_name() == os.environ.get(
        "HYPOTHESIS_PROFILE", "default")


def test_default_profile_pins_are_the_ones_the_task_named():
    current = settings.get_profile("default")
    assert current.max_examples == 200
    assert current.derandomize is True
    assert current.database is None
    assert current.deadline is None


def test_deep_profile_is_heavier_but_writes_nothing():
    deep = settings.get_profile("deep")
    assert deep.max_examples == 5000
    assert deep.derandomize is False
    assert deep.database is None
    assert deep.deadline is None


def test_hypothesis_is_declared_in_the_test_extra_only():
    """pyproject: группа test — единственная, где живёт генератор;
    зависимости ядра остаются пустыми."""
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^test = \[[^\]]*"hypothesis[^"]*"', text, re.M), (
        "hypothesis не объявлена в [project.optional-dependencies] test")
    assert re.search(r"^dependencies = \[\]$", text, re.M), (
        "ядро перестало собираться без сторонних пакетов")


def test_runtime_never_imports_hypothesis():
    """ADR-0024 ③: `grep -rn hypothesis rusterm/` — пусто, и это
    проверяет машина, а не отчёт. Число, попавшее в базу, не может
    зависеть от генератора."""
    hits = []
    for path in sorted((REPO / "rusterm").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if re.search(r"hypothesis", line, re.IGNORECASE):
                hits.append(f"{path.relative_to(REPO)}:{number}")
    assert hits == [], "генератор протёк в рантайм: " + ", ".join(hits)


@given(st.floats(min_value=-1e12, max_value=1e12,
                 allow_nan=False, allow_infinity=False))
def test_generated_equal_amounts_give_one_or_an_honest_refusal(amount):
    """Счётчик прогона видно в --hypothesis-show-statistics: генератор
    действительно перебирает входы, а не пропускает тест. Отношение
    числа к самому себе — 1.0; правила знаменателя при этом остаются
    правилами: ноль — denominator_zero, отрицательная выручка —
    negative_denominator, а не перевёрнутый знак."""
    value, reason = formulas.gross_margin(amount, amount)
    if amount == 0.0:
        assert (value, reason) == (None, "denominator_zero")
    elif amount < 0.0:
        assert (value, reason) == (None, "negative_denominator")
    else:
        assert (value, reason) == (1.0, None)
