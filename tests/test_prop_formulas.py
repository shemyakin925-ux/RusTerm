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
# ── E3: метаморфные свойства ──────────────────────────────────────────────

# Входы E3 — конечные числа вне границы домена (1e-6 ≤ |x| ≤ 1e12);
# закрытость на NaN/±inf — дело E2, здесь проверяется другое: мера не
# должна зависеть от единицы измерения и от порядка слагаемых.
_NONZERO = (st.floats(min_value=1e-6, max_value=1e12, allow_nan=False,
                      allow_infinity=False)
            | st.floats(min_value=-1e12, max_value=-1e-6, allow_nan=False,
                        allow_infinity=False))
_SCALE = st.sampled_from([1e-3, 1e3, 1e6])

# Формулы «деньги / деньги»: все аргументы — деньги, масштаб входит и в
# числитель, и в знаменатель.
_RATIO_FORMULAS = {
    "gross_margin": 2,
    "operating_margin": 2,
    "net_margin": 2,
    "roe": 3,
    "roic": 3,
    "asset_turnover": 3,
    "effective_tax_rate": 2,
    "price_to_earnings": 2,
    "price_to_book": 2,
    "price_to_sales": 2,
    "ev_to_ebitda": 2,
    "dividend_yield": 2,
}


def _same_number(a, b) -> bool:
    return abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1.0)


def _reason_token(reason):
    """Причина без продолжения: 'jurisdiction_rate: rate=…' и
    'missing_data: shares_sum:…' несут в продолжении ЧИСЛО, а
    (a·k)/(b·k) воспроизводит его с относительной погрешностью ~1e-16 —
    не масштаб меняет отказ, а округление floats. Сравнение по первому
    токену — то же, чем пользуется is_known_reason. Замеренный пример:
    effective_tax_rate(28143926709.0, 1e-06) → rate=28143926709000000.0000,
    ×1e-3 → rate=28143926708999996.0000."""
    return None if reason is None else reason.split(":", 1)[0]


def test_the_ratio_list_matches_the_signatures():
    """Арность в списке выше — не память: аргументов у формулы столько,
    сколько масштабируется денег, иначе свойство молчит по части входов."""
    for name, arity in _RATIO_FORMULAS.items():
        params = list(inspect.signature(getattr(formulas, name)).parameters)
        assert len(params) == arity, (
            f"{name} вызывается с {arity} аргументами, а в сигнатуре "
            f"{params}")


@pytest.mark.parametrize("name,arity", sorted(_RATIO_FORMULAS.items()))
@given(data=st.data(), scale=_SCALE)
def test_money_scale_does_not_move_a_ratio(name, arity, data, scale):
    function = getattr(formulas, name)
    params = list(inspect.signature(function).parameters)
    args = [data.draw(_NONZERO, label=param) for param in params]
    value, reason = function(*args)
    scaled, scaled_reason = function(*[a * scale for a in args])
    assert _reason_token(reason) == _reason_token(scaled_reason), (
        f"{name}{args} → {reason!r}, а с масштабом ×{scale:g} → "
        f"{scaled_reason!r}: отказ зависит от единицы измерения")
    if value is not None:
        assert scaled is not None and _same_number(value, scaled), (
            f"{name}{args} = {value!r}, ×{scale:g} → {scaled!r}")


@given(quarters=st.lists(_NONZERO, min_size=4, max_size=8))
def test_ttm_does_not_care_about_the_order_of_its_window(quarters):
    value, reason = formulas.ttm(quarters)
    window = quarters[-4:]
    assert reason is None and _same_number(value, sum(window))
    for permuted in (list(reversed(window)),
                     window[1:] + window[:1],
                     sorted(window)):
        assert formulas.ttm([*quarters[:-4], *permuted]) == (value, reason)


@given(quarters=st.lists(st.one_of(_NONZERO, st.none()),
                         min_size=0, max_size=8))
def test_ttm_refuses_a_short_or_gapped_window(quarters):
    value, reason = formulas.ttm(quarters)
    if len(quarters) < 4 or any(v is None for v in quarters[-4:]):
        assert (value, reason) == (None, "missing_data"), (
            f"ttm({quarters}) → {(value, reason)}; неполное окно не "
            "смешивается с полным")
    else:
        assert reason is None and _same_number(value, sum(quarters[-4:]))


@given(caps=st.lists(st.one_of(_NONZERO, st.none()), min_size=1, max_size=4))
def test_market_cap_total_is_never_a_partial_sum(caps):
    value, reason = formulas.market_cap_total(caps)
    if any(c is None for c in caps):
        assert (value, reason) == (None, "missing_data"), (
            f"market_cap_total({caps}) → {(value, reason)}: частичная "
            "капитализация выглядит как настоящая")
    else:
        assert reason is None and _same_number(value, sum(caps))


@given(v_start=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False,
                         allow_infinity=False),
       growth=st.floats(min_value=-0.985, max_value=9.9, allow_nan=False,
                        allow_infinity=False),
       periods=st.integers(min_value=1, max_value=30))
def test_cagr_reads_back_the_growth_it_was_hand(v_start, growth, periods):
    v_end = v_start * (1.0 + growth) ** periods
    value, reason = formulas.cagr(v_start, v_end, periods)
    assert reason is None, f"cagr({v_start}, {v_end}, {periods}) → {reason!r}"
    assert abs(value - growth) <= 1e-6 * max(1.0, abs(growth))


@given(v=st.floats(min_value=1e-6, max_value=1e12, allow_nan=False,
                   allow_infinity=False),
       n=st.integers(min_value=1, max_value=30))
def test_cagr_refuses_a_nonpositive_start(v, n):
    for start in (-v, 0.0):
        value, reason = formulas.cagr(start, v, n)
        assert value is None and reason == "negative_denominator", (
            f"cagr({start}, {v}, {n}) → {(value, reason)}: рост от убытка "
            "не определён")


@given(shares=st.lists(st.floats(min_value=0.0, max_value=1.0,
                                 allow_nan=False, allow_infinity=False),
                       min_size=1, max_size=6))
def test_hhi_ignores_order_and_stays_in_its_documented_bounds(shares):
    value, reason = formulas.hhi(shares)
    assert formulas.hhi(sorted(shares, reverse=True)) == (value, reason)
    assert formulas.hhi(list(reversed(shares))) == (value, reason)
    if value is not None:
        assert 0.0 <= value <= 1.0, f"hhi({shares}) = {value!r}"


@given(price=st.floats(min_value=1e-6, max_value=1e12, allow_nan=False,
                       allow_infinity=False),
       months=st.integers(min_value=2, max_value=12))
def test_a_flat_series_has_no_return_and_no_drawdown(price, months):
    series = [(f"2024-{month:02d}-28", price) for month in range(1, months + 1)]
    assert formulas.total_return(series) == (0.0, None)
    assert formulas.drawdown(series) == (0.0, None)


@given(series=st.lists(st.tuples(
    st.sampled_from(["2023-12-29", "2024-03-28", "2024-06-28", "2024-09-27",
                     "2024-12-31"]),
    st.floats(min_value=1e-6, max_value=1e12, allow_nan=False,
              allow_infinity=False)), min_size=2, max_size=8))
def test_drawdown_lives_between_minus_one_and_zero(series):
    value, reason = formulas.drawdown(sorted(series))
    assert reason is None, f"drawdown({series}) → {reason!r}"
    assert -1.0 <= value <= 0.0, f"drawdown({series}) = {value!r}"
