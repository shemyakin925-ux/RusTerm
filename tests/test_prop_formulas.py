"""ТЗ-82 E1 — чем живёт пункт «профили и зависимость».

E2–E4 дописывают этот файл свойствами; здесь то, что проверяет сам E1:
Hypothesis объявлена в группе `test`, профили регистрирует conftest,
выбор делает переменная HYPOTHESIS_PROFILE, и рантайм библиотеку не
импортирует (ADR-0024). `import hypothesis` здесь без importorskip:
свойство, которое смолчало в прогоне, выглядит зелёным и ничего не
доказывает.
"""
from __future__ import annotations

import inspect
import math
import os
import re
import typing
from pathlib import Path
from typing import Optional, Tuple

import pytest
from hypothesis import given, settings, strategies as st

from rusterm import formulas
from rusterm.reasons import is_known_reason

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


# ── E2: closure property — каждая формула, автоматически ────────────────

# Пара «значение или причина» — единственный контракт формулы
# (rusterm/formulas.py: «Никаких исключений»). Проверка закрытости
# требует входов за границей арифметики: NaN, ±inf, частное, уехавшее
# в inf, степень, упёршаяся в OverflowError.
PAIR = Tuple[Optional[float], Optional[formulas.NullReason]]

FLOAT_OR_NONE = st.one_of(st.floats(allow_nan=True, allow_infinity=True),
                          st.none())
_DATE = st.sampled_from(["2022-12-31", "2023-06-30", "2023-12-31",
                         "2024-06-30", "2024-12-31"])
_PRICE_POINT = st.tuples(_DATE, FLOAT_OR_NONE)


def _census() -> set[str]:
    """Имена публичных формул движка — интроспекцией, не памятью."""
    found = set()
    for name, obj in vars(formulas).items():
        if name.startswith("_") or not inspect.isfunction(obj):
            continue
        if obj.__module__ != "rusterm.formulas":
            continue
        if typing.get_type_hints(obj).get("return") == PAIR:
            found.add(name)
    return found


# Список покрытых формул записан руками: именно он краснеет, когда в
# движок добавляют меру, для которой свойства нет (CENSUS ниже сверяет
# его с интроспекцией в обе стороны).
COVERED = {
    "asset_turnover", "cagr", "dividend_yield", "drawdown",
    "effective_tax_rate", "enterprise_value", "ev_to_ebitda",
    "gross_margin", "hhi", "market_cap_per_class", "market_cap_total",
    "net_margin", "operating_margin", "price_to_book",
    "price_to_earnings", "price_to_sales", "roe", "roe_incl_nci", "roic",
    "total_return", "ttm",
}


def _arg_strategy(annotation):
    """Стратегия по аннотации аргумента: float (и None), bool, список
    float (и None), список пар (дата, float|None)."""
    inner = [a for a in typing.get_args(annotation) if a is not type(None)]
    if typing.get_origin(annotation) is list:
        element = inner[0] if inner else float
        if typing.get_origin(element) is tuple:
            return st.lists(_PRICE_POINT, max_size=6)
        return st.lists(FLOAT_OR_NONE, max_size=6)
    if annotation is bool or bool in inner:
        return st.booleans()
    return FLOAT_OR_NONE


def test_census_covers_every_paired_formula():
    """Новая формула без свойства — красное (ТЗ-82 E2)."""
    found = _census()
    assert found, ("интроспекция не нашла ни одной формулы — страж "
                   "стал пустым и зелёным")
    assert sorted(found - COVERED) == [], (
        "в движке есть пара-формула без свойства: "
        + ", ".join(sorted(found - COVERED)))
    assert sorted(COVERED - found) == [], (
        "свойство названо для функции, которая больше не возвращает "
        "пару: " + ", ".join(sorted(COVERED - found)))
    assert len(COVERED) >= 20, (
        f"покрыто {len(COVERED)} формул — слишком мало, чтобы быть "
        "замыслом")


@pytest.mark.parametrize("name", sorted(COVERED))
@given(data=st.data())
def test_formula_is_closed_on_generated_inputs(name, data):
    """Каждая формула на сгенерированных входах: без исключения, ровно
    одна из пары не None, значение конечно, причина из словаря."""
    function = getattr(formulas, name)
    hints = typing.get_type_hints(function)
    args = [data.draw(_arg_strategy(hints[param]), label=param)
            for param in inspect.signature(function).parameters]
    value, reason = function(*args)
    assert (value is None) != (reason is None), (
        f"{name}({args}) вернул {(value, reason)} — ни значения, ни "
        "отказа (или и то, и другое)")
    if value is not None:
        assert math.isfinite(value), (
            f"{name}({args}) дал нечисловое значение {value!r}")
    assert is_known_reason(reason), (
        f"{name}({args}) сослался на причину вне словаря: {reason!r}")


_ARITHMETIC = {
    "fcf": ("ocf", "capex"),
    "interest_coverage": ("operating_income", "interest_expense"),
    "ebitda": ("operating_income", "d_and_a"),
}


@st.composite
def _arithmetic_payload(draw):
    concept = draw(st.sampled_from(sorted(_ARITHMETIC)))
    return concept, {name: draw(FLOAT_OR_NONE)
                     for name in _ARITHMETIC[concept]}


@given(payload=_arithmetic_payload())
def test_the_calculate_measure_door_is_closed_too(payload):
    """ТЗ-82 E2: у мер, которые считают прямо в calculate_measure
    (ebitda, fcf, interest_coverage), та же закрытость — они идут мимо
    формул-обёрток."""
    concept, kwargs = payload
    measure = formulas.calculate_measure(concept, **kwargs)
    assert (measure.value is None) != (measure.null_reason is None), (
        f"{concept}({kwargs}) → ({measure.value!r}, "
        f"{measure.null_reason!r})")
    if measure.value is not None:
        assert math.isfinite(measure.value), (
            f"{concept}({kwargs}) дал нечисловое значение "
            f"{measure.value!r}")
    assert is_known_reason(measure.null_reason), (
        f"{concept}({kwargs}) — причина вне словаря: "
        f"{measure.null_reason!r}")
