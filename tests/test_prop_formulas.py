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
# Двоичный масштаб домножает float ДОЧНО: лишней цифры не появляется,
# поэтому там сравнение строгое, до бита. Десятичный (×1000 — «деньги в
# тысячах», ровно та единица измерения, о которой говорит ТЗ) округляется
# сам, и погрешность входа усиливается там, где знаменатель — разность
# близких чисел. Граница для него — не выдуманное число, а измеренный шум
# последнего бита (_ulp_noise).
_BINARY_SCALE = st.sampled_from([2.0 ** -30, 2.0, 2.0 ** 30])

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
@given(data=st.data(), scale=_BINARY_SCALE)
def test_a_binary_scale_of_two_leaves_the_same_bits(name, arity, data, scale):
    """×2**k точен, значит и ответ обязан сойтись до бита: допуск здесь
    не нужен вовсе, и любая разница — настоящая зависимость меры от
    единицы измерения. 30000 случайных наборов на каждую из двенадцати
    формул × три масштаба расхождения не дали (строка 22 отчёта)."""
    function = getattr(formulas, name)
    params = list(inspect.signature(function).parameters)
    args = [data.draw(_NONZERO, label=param) for param in params]
    value, reason = function(*args)
    scaled, scaled_reason = function(*[a * scale for a in args])
    assert _reason_token(reason) == _reason_token(scaled_reason), (
        f"{name}{args} → {reason!r}, а с ×{scale:g} → {scaled_reason!r}")
    assert value == scaled, (
        f"{name}{args} = {value!r}, ×{scale:g} → {scaled!r}: двоичный "
        "масштаб точен, так что расхождение даже до последнего бита — "
        "это уже не округление")


def _ulp_noise(function, args) -> float:
    """На сколько шевелится ответ, если каждый аргумент сдвинуть на один
    последний бит (в обе стороны); складывается по аргументам. Умножение
    на десятичный масштаб двигает вход не больше чем на пол-ulp, поэтому
    эта величина — граница, до которой «значение не зависит от единицы
    измерения» вообще выполнимо в float: за её пределами остаётся только
    настоящая зависимость. Измерено на контрпримере deep-профиля
    (roic(1e12, 999999999215.0, −999999962869.0), ×1e-3): знаменатель —
    половина суммы 999999999215.0 и −999999962869.0, то есть вычитание
    близких чисел; шум последнего бита 0.185, расхождение 0.066 — внутри
    шума, а относительная разница 1.2e-9 ровно на грани прежнего
    фиксированного допуска.

    Считается только когда строгая проверка не сошлась — обычный путь
    (хорошо обусловленные входы) остаётся с допуском 1e-9.
    """
    base = function(*args)[0]
    if base is None:
        return 0.0
    noise = 0.0
    for index, value in enumerate(args):
        step = 0.0
        for direction in (math.inf, -math.inf):
            moved = math.nextafter(value, direction)
            other = function(*args[:index], moved, *args[index + 1:])[0]
            if other is not None:
                step = max(step, abs(other - base))
        noise += step
    return noise


@pytest.mark.parametrize("name,arity", sorted(_RATIO_FORMULAS.items()))
@given(data=st.data(), scale=_SCALE)
def test_money_scale_does_not_move_a_ratio(name, arity, data, scale):
    function = getattr(formulas, name)
    params = list(inspect.signature(function).parameters)
    args = [data.draw(_NONZERO, label=param) for param in params]
    value, reason = function(*args)
    scaled_args = [a * scale for a in args]
    scaled, scaled_reason = function(*scaled_args)
    assert _reason_token(reason) == _reason_token(scaled_reason), (
        f"{name}{args} → {reason!r}, а с масштабом ×{scale:g} → "
        f"{scaled_reason!r}: отказ зависит от единицы измерения")
    if value is not None:
        assert scaled is not None, (
            f"{name}{args} = {value!r}, а с масштабом ×{scale:g} → "
            f"{scaled!r}: отказ там, где ответа нет")
        if not _same_number(value, scaled):
            noise = (_ulp_noise(function, args)
                     + _ulp_noise(function, scaled_args))
            assert abs(value - scaled) <= noise, (
                f"{name}{args} = {value!r}, ×{scale:g} → {scaled!r}: "
                f"разница {abs(value - scaled)!r} больше шума последнего "
                f"бита ({noise!r}) — масштаб меняет ответ сам")


_ROIC_CANCELLATION = (1000000000000.0, 999999999215.0, -999999962869.0)


def test_the_deep_scale_failure_is_retold_without_a_generator():
    """ADR-0024: провал, найденный на deep, надо пересказать default-
    прогоном, прежде чем чинить, — а deep-сиды не воспроизводимы
    (derandomize=False, database=None). Здесь пересказ примером: тест
    запускается в любом профиле и покраснеет, если расхождение пропадёт
    (тогда Disputed 5 закрывают, а не оставляют висеть).

    Измерено: 55026687.943652675 против 55026688.01006897 при ×1e-3 —
    1.2e-9 относительно, ровно за допуском 1e-9 и внутри шума последнего
    бита (0.185 абсолютных на каждой из двух сторон сравнения).
    """
    value, reason = formulas.roic(*_ROIC_CANCELLATION)
    scaled_args = tuple(a * 1e-3 for a in _ROIC_CANCELLATION)
    scaled, scaled_reason = formulas.roic(*scaled_args)
    assert (reason, scaled_reason) == (None, None), (
        f"roic({_ROIC_CANCELLATION}) → {reason!r}, ×1e-3 → "
        f"{scaled_reason!r}: отказ там, где пример его не даёт")
    assert not _same_number(value, scaled), (
        f"roic{_ROIC_CANCELLATION} = {value!r} и ×1e-3 → {scaled!r} "
        "сошлись в пределах 1e-9: расхождение из Disputed 5 исчезло — "
        "закрывай его, а не тест")
    noise = (_ulp_noise(formulas.roic, _ROIC_CANCELLATION)
             + _ulp_noise(formulas.roic, scaled_args))
    assert abs(value - scaled) <= noise, (
        f"разница {abs(value - scaled)!r} вне измеренного шума последнего "
        f"бита ({noise!r}): масштаб двигает ответ сильнее, чем округление")


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


# Верхняя граница hhi — не 1.0, а квадрат того самого допуска, который
# код объявляет сам: доли обязаны суммироваться в 1.0 с допуском 1e-6
# (formulas.hhi), и монопольный участник с долей 1.0000009 даёт
# hhi = 1.0000018 (измерено — строка 21 отчёта). Строка «диапазон 0..1»
# из того же docstring этим же числом не выполняется; расхождение
# унесёт решение координатора (Disputed 4), а пока его держат две
# проверки ниже: граница свойства поbranch-но и капкан на сам факт.
_HHI_TOLERANCE = 1e-6


@given(shares=st.lists(st.floats(min_value=0.0, max_value=1.0,
                                 allow_nan=False, allow_infinity=False),
                       min_size=1, max_size=6))
def test_hhi_ignores_order_and_stays_in_its_documented_bounds(shares):
    value, reason = formulas.hhi(shares)
    assert formulas.hhi(sorted(shares, reverse=True)) == (value, reason)
    assert formulas.hhi(list(reversed(shares))) == (value, reason)
    if value is not None:
        total = sum(float(s) for s in shares)
        bound = 1.0 if total == 1.0 else (1.0 + _HHI_TOLERANCE) ** 2
        assert 0.0 <= value <= bound, (
            f"hhi({shares}) = {value!r} при sum = {total!r} вне границы "
            f"{bound!r}, которую выводят правила самого hhi")


def test_hhi_still_outruns_its_own_documented_range():
    """Капкан на Disputed 4: краснеет в тот день, когда hhi перестанет
    выходить за 1.0. Тогда правят не этот тест, а docstring формулы и
    запись в «Спорном» — расхождение не должно пережить решение молча."""
    value, reason = formulas.hhi([1.0, 1.192092896e-07])
    assert reason is None, (
        f"hhi([1.0, 1.192092896e-07]) → {reason!r}: допуск 1e-6 по сумме "
        "больше не принимает эту долю — Disputed 4 закрыт иначе")
    assert value is not None and value > 1.0, (
        f"hhi([1.0, 1.192092896e-07]) = {value!r}: выход за границу 0..1 "
        "исчез — закрой Disputed 4 и обнови границу в docstring")


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


# ── E4: ноль — не пропуск ───────────────────────────────────────────────

# Пара «ноль в числителе» и «числителя нет» дают разные ответы, и путать
# их — значит считать меру там, где факта нет (ТЗ-82 E4). Список
# двухместных отношений выводится интроспекцией: новая такая формула
# попадает под проверку сама, без правки теста.
_ARITY2_PAIRS = sorted(
    name for name, obj in vars(formulas).items()
    if not name.startswith("_") and inspect.isfunction(obj)
    and obj.__module__ == "rusterm.formulas"
    and typing.get_type_hints(obj).get("return") == PAIR
    and len(inspect.signature(obj).parameters) == 2
)


def test_arity_two_pairs_are_not_an_empty_list():
    """Список построен интроспекцией: если она сломалась (аннотация
    возврата или число аргументов уехало), свойство стало бы зелёным без
    единого случая — этот тест говорит об этом вслух."""
    assert len(_ARITY2_PAIRS) >= 9, (
        f"двухместных пар найдено {len(_ARITY2_PAIRS)} — "
        "интроспекция больше не видит формулы")


@pytest.mark.parametrize("name", _ARITY2_PAIRS)
@given(denominator=st.floats(min_value=1e-6, max_value=1e12,
                             allow_nan=False, allow_infinity=False))
def test_absent_numerator_is_refused_zero_numerator_is_a_number(
        name, denominator):
    """Знаменатель — положительное конечное число: правила нулевого и
    отрицательного знаменателя здесь ни при чём, вопрос только в
    числителе."""
    function = getattr(formulas, name)
    missing, missing_reason = function(None, denominator)
    assert (missing, missing_reason) == (None, "missing_data"), (
        f"{name}(None, {denominator}) → {(missing, missing_reason)}: "
        "пропущенный факт обязан быть отказом, а не 0.0")
    zero, zero_reason = function(0.0, denominator)
    assert (zero, zero_reason) == (0.0, None), (
        f"{name}(0.0, {denominator}) → {(zero, zero_reason)}: ноль при "
        "годном знаменателе — настоящее значение, а не отказ")
