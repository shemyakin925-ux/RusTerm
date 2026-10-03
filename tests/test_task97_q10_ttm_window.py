"""ТЗ-97 Q10: TTM для всех потоковых входов (решение пользователя 24.09).

Здесь — чистая функция окна: `rusterm.core.ttm.ttm_window`. Меры зовут её,
а не каждая пересобирает арифметику по-своему (иначе d_and_a сложится по
одному окну, а operating_income — по другому, и «мера» станет смесью).

Форма входов — кортежи (value, period_start, period_end, fact_id) в том
же порядке, что даёт `SnapshotRepo.as_reported_facts` после фильтра
`as_of` и правила давности: ядро не делает второго запроса и не заводит
свою дверь в дату.
"""
from __future__ import annotations

from rusterm.core.ttm import (TtmWindow, is_annual_window, ttm_window)

ANNUAL_TTM = "ttm"
FALLBACK = "annual_fallback"


def _rows(specs):
    """Список кортежей по коротким строкам-спекам: (value, start, end, id).
    Один аргумент-список: `_rows([a], [b])` развалился бы на unpacking в
    ядре, и три зуба на `is None` стали бы зелёными без единой строки
    входа."""
    return [tuple(spec) for spec in specs]


# ── алгебра «год + YTD − YTD прошлого года» ─────────────────────────────


def test_fy_plus_ytd_minus_ytd_prior_is_the_window():
    """Три поданных факта вместо четырёх кварталов: Q4 эмитент не подаёт
    никогда (ADR-0021), поэтому основной способ — алгебра."""
    w = ttm_window(_rows([
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
        (40.0, "2025-01-01", "2025-06-30", "ytd25h1"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    assert w.basis == ANNUAL_TTM
    assert w.value == 120.0          # 100 + 60 − 40
    # окно — настоящие 12 месяцев: день после вычитаемого YTD и до конца
    # прибавляемого, а не полтора года от начала годового факта
    assert (w.start, w.end) == ("2025-07-01", "2026-06-30")


def test_the_three_addends_are_recorded_with_their_signs():
    """Lineage обязан называть слагаемые: читатель мерой не проверит, что
    знаменатель вычитался, а не сложился."""
    w = ttm_window(_rows([
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
        (40.0, "2025-01-01", "2025-06-30", "ytd25h1"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    signs = {c.fact_id: c.sign for c in w.components}
    assert signs == {"fy25": 1, "ytd26h1": 1, "ytd25h1": -1}
    assert {c.role for c in w.components} == {"fy", "ytd", "ytd_prior"}


def test_a_non_contiguous_annual_is_not_an_addend():
    """Год, не стыкующийся с началом YTD, — не «предыдущий год этого
    же финкалендаря»: алгебра с ним даёт смесь двух годов."""
    w = ttm_window(_rows([
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2023-01-01", "2023-12-31", "fy23"),
        (40.0, "2025-01-01", "2025-06-30", "ytd25h1"),
    ]), as_of="2026-09-24", concept="revenue")
    # годового, стыкующегося с 2026-01-01, нет → TTM не собран; fy23 —
    # слишком старый годовой, он годится только запасным значением
    assert w is not None
    assert w.basis == FALLBACK
    assert any("fy" in m for m in w.missing), w.missing


def test_the_prior_ytd_must_be_the_same_fiscal_offset():
    """Девять месяцев против шести — не пара: вычитание должно снимать
    ровно тот же кусок года, что прибавился."""
    w = ttm_window(_rows([
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
        (90.0, "2025-01-01", "2025-09-30", "ytd25nine"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    assert w.basis == FALLBACK
    assert any("ytd_prior" in m for m in w.missing), w.missing


# ── сумма четырёх подряд идущих кварталов ───────────────────────────────


def test_four_consecutive_quarters_sum_to_the_window():
    w = ttm_window(_rows([
        (15.0, "2026-04-01", "2026-06-30", "q2_26"),
        (12.0, "2026-01-01", "2026-03-31", "q1_26"),
        (11.0, "2025-10-01", "2025-12-31", "q4_25"),
        (10.0, "2025-07-01", "2025-09-30", "q3_25"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    assert w.basis == ANNUAL_TTM
    assert w.value == 48.0
    assert (w.start, w.end) == ("2025-07-01", "2026-06-30")
    assert {c.sign for c in w.components} == {1}


def test_a_broken_chain_is_not_a_sum_of_three():
    """Три квартала и пропущенный четвёртый — 9 месяцев под видом 12.
    Сумма трёх красная; значение — годовой факт с пометкой."""
    w = ttm_window(_rows([
        (15.0, "2026-04-01", "2026-06-30", "q2_26"),
        (12.0, "2026-01-01", "2026-03-31", "q1_26"),
        (10.0, "2025-07-01", "2025-09-30", "q3_25"),
        (44.0, "2025-01-01", "2025-12-31", "fy25"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    assert w.basis == FALLBACK
    assert w.value == 44.0
    assert any("2025-10-01" in m or "2025-12-31" in m
               for m in w.missing), w.missing


# ── годовой сам как окно и отказ ─────────────────────────────────────────


def test_annual_with_nothing_newer_is_itself_the_window():
    """Правило вердикта: после последнего годового ничего не подано —
    годовой И ЕСТЬ TTM, а не «запасной» (окно = год)."""
    w = ttm_window(_rows([
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
    ]), as_of="2026-02-01", concept="revenue")
    assert w is not None
    assert w.basis == ANNUAL_TTM
    assert w.value == 100.0
    assert (w.start, w.end) == ("2025-01-01", "2025-12-31")


def test_no_window_and_no_annual_is_none():
    """Ни TTM, ни годового — прежний отказ `missing_data`, а не ноль и не
    последнее известное quarterly × 4."""
    w = ttm_window(_rows([
        (15.0, "2026-04-01", "2026-06-30", "q2_26"),
        (12.0, "2026-01-01", "2026-03-31", "q1_26"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is None


def test_missing_prior_year_falls_back_to_the_annual_and_names_it():
    """Нет вычитаемого — берём последний годовой, но не тихо: в `missing`
    — концепт и период того, чего не хватило."""
    w = ttm_window(_rows([
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
    ]), as_of="2026-09-24", concept="net_income")
    assert w is not None
    assert w.basis == FALLBACK
    assert w.value == 100.0
    assert len(w.missing) == 1
    assert "net_income" in w.missing[0]
    assert "2025-01-01" in w.missing[0] and "2025-06-30" in w.missing[0], \
        w.missing


# ── двери и шум входных данных ──────────────────────────────────────────


def test_a_period_ending_after_as_of_is_not_a_fact_yet():
    """ТЗ-22 J3: период, кончившийся позже даты снапшота, ещё закрыт не
    был — окно не имеет права на него заканчиваться, какой календарь у
    эмитента ни был."""
    w = ttm_window(_rows([
        (70.0, "2026-01-01", "2026-09-30", "ytd26nine"),   # после as_of
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
        (40.0, "2025-01-01", "2025-06-30", "ytd25h1"),
    ]), as_of="2026-08-01", concept="revenue")
    assert w is not None
    assert w.end == "2026-06-30"
    assert w.value == 120.0     # 70-й факт в окне быть не должно


def test_a_restated_duplicate_of_a_period_is_counted_once():
    """Тот же период, поданный дважды (пересоставленный факт), удваивает
    слагаемое — и TTM удваивается молча."""
    w = ttm_window(_rows([
        (15.0, "2026-04-01", "2026-06-30", "q2_26"),
        (15.0, "2026-04-01", "2026-06-30", "q2_26_restated"),
        (12.0, "2026-01-01", "2026-03-31", "q1_26"),
        (11.0, "2025-10-01", "2025-12-31", "q4_25"),
        (10.0, "2025-07-01", "2025-09-30", "q3_25"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    assert w.value == 48.0, "дубль периода сложился дважды"


def test_an_empty_or_unparsable_input_is_none_not_a_crash():
    """Ядро вызывается на 44 бумагах сразу: кривой факт не должен
    ронять сборку снапшота."""
    assert ttm_window([], as_of="2026-09-24", concept="revenue") is None
    assert ttm_window(_rows([
        ("не число", "2025-01-01", "2025-12-31", "x"),
        (10.0, None, "2025-12-31", "y"),
    ]), as_of="2026-09-24", concept="revenue") is None


def test_the_window_never_claims_twelve_months_it_does_not_have():
    """Длина окна — величина, которую читатель меры не проверит:
    12-месячной называется только правда-12-месячная (350..380 дней с
    люфтом на сдвиг фингода и 52/53-недельные годы)."""
    w = ttm_window(_rows([
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
        (40.0, "2025-01-01", "2025-06-30", "ytd25h1"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    assert w.basis == ANNUAL_TTM
    assert 350 <= _days(w.start, w.end) <= 380, (w.start, w.end)


def _days(start: str, end: str) -> int:
    from datetime import date
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def test_the_fallback_keeps_the_annual_window_for_the_reader():
    """Запасное значение несёт окно годового факта, а не выдуманное
    «последние 12 месяцев»: пользователь видит, каким периодом он
    пользуется."""
    w = ttm_window(_rows([
        (60.0, "2026-01-01", "2026-06-30", "ytd26h1"),
        (100.0, "2025-01-01", "2025-12-31", "fy25"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None
    assert (w.start, w.end) == ("2025-01-01", "2025-12-31")
    assert [c.fact_id for c in w.components] == ["fy25"]


def test_400_days_is_not_twelve_months_however_it_was_submitted():
    """Дверь 350..380 дней — не придирка: факт за 13 месяцев (исправленная
    подача, сдвинутый фингод) не имеет права называться TTM. Ни годового,
    ни TTM здесь нет → отказа, а не «годовой с хвостом»."""
    w = ttm_window(_rows([
        (100.0, "2025-01-01", "2026-02-05", "long400"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is None


def test_four_quarters_that_span_thirteen_months_are_not_a_ttm():
    """Четыре формальных квартала (95 дней, соседство 1 день) могут дать
    окно 383 дня — это не 12 месяцев, и сумма их не становится TTM."""
    w = ttm_window(_rows([
        (15.0, "2026-04-15", "2026-07-19", "q4"),
        (12.0, "2026-01-09", "2026-04-14", "q3"),
        (11.0, "2025-10-05", "2026-01-08", "q2"),
        (10.0, "2025-07-01", "2025-10-04", "q1"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is None, "окно из четырёх кварталов вышло длиннее 12 месяцев"


def test_a_five_week_gap_between_quarters_is_not_consecutive():
    """Люфт соседства — 5 дней (как в d_and_a-цепочке TЗ-31): разрыв в 20
    дней между кварталами — это пропущенный период, а не «подряд».
    Годового факта здесь нет, поэтому ответа нет вовсе — а не сумма трёх
    кварталов (и не сумма четырёх с дыркой) под видом годовой."""
    w = ttm_window(_rows([
        (15.0, "2026-04-20", "2026-07-19", "q2_26"),   # 90 дней, квартал
        (12.0, "2026-01-01", "2026-03-31", "q1_26"),   # до него — 20 дней
        (11.0, "2025-10-01", "2025-12-31", "q4_25"),
        (10.0, "2025-07-01", "2025-09-30", "q3_25"),
    ]), as_of="2026-09-24", concept="revenue")
    assert w is None, ("разрыв в 20 дней собрал «TTM» из трёх кварталов "
                       "или придумал четвёртый")


# ── публичный предикат годового окна (им им пользуется сборка снапшота) ─

def test_the_public_predicate_keeps_the_same_corridor_as_the_kernel():
    """`is_annual_window` — тот же коридор 350…380 дней, что у годового
    слагаемого, и то же безразличие к мусору: окно меры и слагаемое ядра
    обязаны называться «годом» по одному определению, иначе два
    представления о годе разъедутся на пограничных календарях."""
    assert is_annual_window("2025-01-01", "2025-12-31") is True
    assert is_annual_window("2025-01-01", "2026-02-15") is False  # 410
    assert is_annual_window("2025-06-01", "2026-05-01") is False  # 334
    # перевёрнутый период и мусор — False, а не исключение: сборка
    # вызывает предикат на всём наборе бумаг сразу
    assert is_annual_window("2025-12-31", "2025-01-01") is False
    assert is_annual_window(None, "2025-12-31") is False
    assert is_annual_window("годовой", "2025-12-31") is False


def test_the_annual_fallback_window_is_annual_by_the_same_predicate():
    """Окно, которое ядро отдало годовым запасным, предикат сборки
    тоже признаёт годовым: запасной выход описан дважды, и описания
    не имеют права расходиться."""
    w = ttm_window(_rows([
        (100.0, "2025-01-01", "2025-12-31", "fy25"),   # FY2025
        (60.0, "2026-01-01", "2026-06-30", "ytd26"),   # YTD H1 2026
    ]), as_of="2026-09-24", concept="revenue")
    assert w is not None and w.basis == FALLBACK, w
    assert is_annual_window(w.start, w.end) is True, (w.start, w.end)


def test_the_missing_piece_is_named_by_the_calendar_shift_not_365_days():
    """Вычитаемое ищут календарным сдвигом (коридор 358–372 дня), и
    назвать его обязаны тем же сдвигом: сдвиг на 365 дня через 29.02.2024
    показал бы «нет факта 2024-01-02…2024-06-30» там, где эмитент подаёт
    2024-01-01…2024-06-30 — пометка врала бы о периоде, которого никто и
    не искал."""
    w = ttm_window(_rows([
        (60.0, "2025-01-01", "2025-06-30", "ytd25h1"),   # через 29.02.2024
        (100.0, "2024-01-01", "2024-12-31", "fy24"),
    ]), as_of="2025-09-24", concept="revenue")
    assert w is not None and w.basis == FALLBACK, w
    assert "2024-01-01…2024-06-30" in w.missing[0], w.missing
    assert "2024-01-02" not in w.missing[0], w.missing
