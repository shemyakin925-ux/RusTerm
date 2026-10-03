"""ТЗ-91 B5: `roic` делит на СРЕДНЕЕ капитала на начало и конец окна.

Буква пункта (agent/TASK-91.md, B5): прежний код пропускал одно и то же
значение капитала и как `invested_capital_begin`, и как
`invested_capital_end`, хотя словарь определяет знаменатель как среднее
двух дат. Правило: начало — капитал из моментных фактов на начало окна
NOPAT (±10 дней); нет его ⇒ `missing_prior_period`.

| где | было | стало |
|---|---|---|
| `calculate_measure("roic", …)` | begin == end (фактически nopat / IC_сегодня) | begin — капитал на границу начала окна |
| нет капитала на границе | число всё равно считалось | `missing_prior_period` (токен из словаря ТЗ-9, как у двухпериодных мер первого прохода) |
| производный капитал (нет поданного `invested_capital`) | знаменатель шёл в lineage пустым списком, и на последнем пути I4 снимал меру до теста | строки lineage несут id всех слагаемых обеих границ |
| граница в календаре эмитента | — | допуск ±10 дней: 52/53-недельные календари сдвигают закрытие периода; дырка в пару недель — другой период, а не та же граница |
| сток на границе | — | ищется по обеим базам (ТЗ-102 M3): годовой баланс, приехавший сравнительной колонкой, — тот же конец периода |
| якорь давности границы | отсчитывался и от периода, закрытого после as_of | только закрытые к дате сборки — ровно как в `_latest_canonical` (B4) |

Меньшинство: NCI берётся с той же границы. Правило D7 (отсутствие NCI —
ноль, если блок капитала подавался) — свойство раскрытия эмитента, а не
даты, поэтому ноль на границе ставят только те, кто NCI не отчитывал
никогда; остальным без NCI на границе капитал не строится (зуб ниже).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

# Дата сборки постоянная и в прошлом всех периодов фикстуры: границы
# меряются от неё, иначе тест краснел бы со временем.
AS_OF = "2025-06-30"
PRICE_DATE = "2025-06-27"          # 3 дня: порог _PRICE_STALE_DAYS = 7
SHARES_DATE = "2025-03-31"         # 91 день: свежее порога M1 (550)
FY_END = "2024-12-31"              # годовой поток: он и есть окно NOPAT
FY_START = (date.fromisoformat(FY_END) - timedelta(days=364)).isoformat()
PRIOR_END = "2023-12-31"           # капитал на начало окна (граница +2 дня)

NOPAT = 4.8                        # 6 * (1 - 1/5)
IC_END = 37.0                      # 35 + 0 + 5 - 2 - 1
IC_BEGIN = 29.0                    # 25 + 0 + 8 - 3 - 1


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths), paths


def _paper(repos, iid="US-B5", issuer="i1"):
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))
    repos.price.put_rows(iid, "twelvedata",
                         [{"date": PRICE_DATE, "close": 10.0,
                           "currency": "USD"}])


def _fact(conn, issuer_id, concept, value, start, end, period_type,
          basis="as_reported", source_ref="s", currency="USD"):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-' || ? || '-' || ? || '-' || ? || '-' || ?, ?, ?,
           ?, ?, ?, ?, ?, ?, ?, 'extracted', ?, '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (issuer_id, concept, basis, end, issuer_id, concept, start, end,
         period_type, str(value), currency, currency, basis, source_ref,
         concept))


def _stock(conn, issuer_id, concept, value, end=FY_END,
           basis="as_reported", source_ref="s", currency="USD"):
    _fact(conn, issuer_id, concept, value, end, end, "instant", basis,
          source_ref, currency)


def _flow(conn, issuer_id, concept, value, start=FY_START, end=FY_END):
    _fact(conn, issuer_id, concept, value, start, end, "duration")


def _balance(conn, issuer_id="i1", end=FY_END, equity=35.0, debt=5.0,
             cash=2.0, stinv=1.0, shares=SHARES_DATE):
    """Капитал на `end`: 35 + 0 + 5 - 2 - 1 = 37 (NCI ни разу не отчитан,
    поэтому ноль производен по правилу D7)."""
    _fact(conn, issuer_id, "shares_outstanding", 7.0, shares, shares,
          "instant")
    _stock(conn, issuer_id, "total_debt", debt, end)
    _stock(conn, issuer_id, "cash", cash, end)
    _stock(conn, issuer_id, "st_investments", stinv, end)
    _stock(conn, issuer_id, "total_equity", equity, end)


def _prior_balance(conn, issuer_id="i1", end=PRIOR_END, equity=25.0,
                   debt=8.0, cash=3.0, stinv=1.0, **kwargs):
    """Капитал на начало окна потока: 25 + 0 + 8 - 3 - 1 = 29. Числа
    акций здесь нет — множитель цены подаётся один раз (`_balance`)."""
    _stock(conn, issuer_id, "total_debt", debt, end, **kwargs)
    _stock(conn, issuer_id, "cash", cash, end, **kwargs)
    _stock(conn, issuer_id, "st_investments", stinv, end, **kwargs)
    _stock(conn, issuer_id, "total_equity", equity, end, **kwargs)


def _flows(conn, issuer_id="i1"):
    _flow(conn, issuer_id, "revenue", 100.0)
    _flow(conn, issuer_id, "net_income", 10.0)
    _flow(conn, issuer_id, "operating_income", 6.0)
    _flow(conn, issuer_id, "d_and_a", 1.0)
    _flow(conn, issuer_id, "tax_expense", 1.0)
    _flow(conn, issuer_id, "pretax_income", 5.0)


def _base(conn, repos, iid="US-B5", issuer="i1"):
    """Бумага с двумя годовыми границами баланса и годовым потоком."""
    _paper(repos, iid, issuer)
    _balance(conn, issuer)
    _prior_balance(conn, issuer)
    _flows(conn, issuer)


def _build(repos, iid="US-B5", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(iid, issuer, AS_OF)
    return {m[3]: m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(iid))}


def _lineage_roles(conn, rows, concept):
    return [r[0] for r in conn.execute(
        "SELECT role FROM measure_lineage WHERE measure_id=?",
        (rows[concept][0],))]


def _lineage_facts(conn, rows, concept):
    return {r[0] for r in conn.execute(
        "SELECT fact_id FROM measure_lineage WHERE measure_id=?",
        (rows[concept][0],))}


# ── среднее двух границ ────────────────────────────────────────────────

def test_roic_divides_by_the_average_of_two_year_ends(env):
    """Зуб Done-when («test with two year-ends»): капитал 37 на конец окна
    и 29 на его начало дают знаменатель 33, а не 37."""
    conn, repos, _paths = env
    _base(conn, repos)
    rows = _build(repos)
    assert float(rows["roic"][4]) == pytest.approx(
        NOPAT / ((IC_BEGIN + IC_END) / 2.0)), rows["roic"]
    assert rows["roic"][10] is None, rows["roic"][10]
    # прежняя ошибка: nopat / капитала одного дня
    assert float(rows["roic"][4]) != pytest.approx(NOPAT / IC_END)
    # сама строка капитала не двигается: две даты нужны только roic
    assert float(rows["invested_capital"][4]) == pytest.approx(IC_END), \
        rows["invested_capital"]


def test_no_capital_at_the_border_is_a_refusal_not_a_carry_forward(env):
    """Без капитала на начало окна среднее выдумано: `missing_prior_period`
    из словаря причин, а не перенос сегодняшнего числа на вчерашнюю дату.
    Отказ касается только roic — его числитель и моментный капитал на
    месте."""
    conn, repos, _paths = env
    _base(conn, repos)
    conn.execute("DELETE FROM fact WHERE period_end=?", (PRIOR_END,))
    rows = _build(repos)
    assert rows["roic"][4] is None, rows["roic"]
    assert rows["roic"][10] == "missing_prior_period", rows["roic"][10]
    assert float(rows["nopat"][4]) == pytest.approx(NOPAT), rows["nopat"]
    assert float(rows["invested_capital"][4]) == pytest.approx(IC_END)


def test_the_first_pass_keeps_naming_its_own_refusal(env):
    """B5 не трогает двухпериодные меры первого прохода: у них граница
    ищется строго по датам окна (ТЗ-102 M3), и без стока на начале окна
    `roe` говорит `period_mismatch`. Два разных отказа за одно и то же
    отсутствие — осознанные: этот пункт добавляет токен проходу оценки, а
    не переписывает первый."""
    conn, repos, _paths = env
    _base(conn, repos)
    conn.execute("DELETE FROM fact WHERE period_end=?", (PRIOR_END,))
    rows = _build(repos)
    assert rows["roe"][10] == "period_mismatch", rows["roe"]
    assert rows["roic"][10] == "missing_prior_period", rows["roic"]


# ── допуск границы ─────────────────────────────────────────────────────

def test_a_border_shifted_by_the_fiscal_calendar_still_counts(env):
    """52/53-недельный календарь: баланс закрыт 2023-12-28 вместо
    2024-01-02 — те же 4.8/33, дырки в два дня знаменатель не видит."""
    conn, repos, _paths = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _prior_balance(conn, end="2023-12-28")
    rows = _build(repos)
    assert float(rows["roic"][4]) == pytest.approx(
        NOPAT / ((IC_BEGIN + IC_END) / 2.0)), rows["roic"]


def test_a_balance_three_weeks_off_the_border_is_another_period(env):
    """Допуск — не разрешение подставить «похожую» дату: баланс
    2023-12-12 — предыдущий квартал, а не начало окна, и среднее из него
    не строится."""
    conn, repos, _paths = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _prior_balance(conn, end="2023-12-12")
    rows = _build(repos)
    assert rows["roic"][4] is None, rows["roic"]
    assert rows["roic"][10] == "missing_prior_period", rows["roic"][10]


# ── двери B4 на границе ────────────────────────────────────────────────

def test_a_period_after_as_of_does_not_move_the_staleness_anchor(env):
    """Давность границы меряется от якоря — самого свежего ЗАКРЫТОГО к дате
    сборки периода, как в `_latest_canonical`. Тег, закрытый после as_of,
    якорем быть не может (ТЗ-22 J3): иначе сборка на 2025-06-30 отвергла бы
    капитал 2023-12-31 как устаревший, отсчитав 1826 дней от баланса 2029
    года, — и отказ был бы про дату сборки, а не про данные."""
    conn, repos, _paths = env
    _base(conn, repos)
    _stock(conn, "i1", "total_debt", 6.0, "2029-12-31")
    rows = _build(repos)
    assert float(rows["roic"][4]) == pytest.approx(
        NOPAT / ((IC_BEGIN + IC_END) / 2.0)), rows["roic"]
    # и сам ещё не закрытый период знаменателем не становится
    assert float(rows["invested_capital"][4]) == pytest.approx(IC_END), \
        rows["invested_capital"]


# ── откуда берётся граница ─────────────────────────────────────────────

def test_the_comparative_column_supplies_the_border(env):
    """ТЗ-102 M3: годовой баланс, приехавший сравнительной колонкой
    следующего 10-K, — тот же конец периода. В базе пользователя так
    лежит весь FY2024 Apple, и без этой ветки roic терял бы знаменатель
    на каждой бумаге, у которой ранняя подача вычищена дедупом."""
    conn, repos, paths = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    obj = repos.raw.put(b'{"comparative": 1}', provider="sec",
                        block="companyfacts",
                        url="https://data.sec.gov/us-gaap/aapl-2025-10k.json")
    for concept, value in (("total_debt", 8.0), ("cash", 3.0),
                           ("st_investments", 1.0), ("total_equity", 25.0)):
        _stock(conn, "i1", concept, value, PRIOR_END, basis="restated",
               source_ref=obj.sha256)
    rows = _build(repos)
    assert float(rows["roic"][4]) == pytest.approx(
        NOPAT / ((IC_BEGIN + IC_END) / 2.0)), rows["roic"]
    roles = _lineage_roles(conn, rows, "roic")
    assert any("capital at 2023-12-31 basis: restated (aapl-2025-10k.json)"
               in role for role in roles), roles


def test_reported_capital_at_the_border_is_taken_whole(env):
    """Эмитент подал `invested_capital` итогом: знаменатель roic берёт его
    и на границе, и на конце окна — то же правило приоритета источника,
    что до B5 действовало для одной даты. Строка `invested_capital` при
    этом остаётся суммой слагаемых (прежнее поведение, пункт его не
    трогает): 4.8/35.5, а не 4.8/33, бывает только у roic."""
    conn, repos, _paths = env
    _base(conn, repos)
    _stock(conn, "i1", "invested_capital", 40.0, FY_END)
    _stock(conn, "i1", "invested_capital", 31.0, PRIOR_END)
    rows = _build(repos)
    assert float(rows["roic"][4]) == pytest.approx(NOPAT / 35.5), \
        rows["roic"]                       # (31 + 40) / 2, а не (29 + 37)
    facts = _lineage_facts(conn, rows, "roic")
    assert "f-i1-invested_capital-as_reported-2023-12-31" in facts, facts


def test_minority_interest_is_taken_from_the_same_border(env):
    """Капитал на дату — капитал вместе с её же NCI: 25 + 6 + 8 - 3 - 1
    на начало и 35 + 4 + 5 - 2 - 1 на конец."""
    conn, repos, _paths = env
    _base(conn, repos)
    _stock(conn, "i1", "minority_interest", 4.0, FY_END)
    _stock(conn, "i1", "minority_interest", 6.0, PRIOR_END)
    rows = _build(repos)
    ic_end = 35.0 + 4.0 + 5.0 - 2.0 - 1.0
    ic_begin = 25.0 + 6.0 + 8.0 - 3.0 - 1.0
    assert float(rows["roic"][4]) == pytest.approx(
        NOPAT / ((ic_begin + ic_end) / 2.0)), rows["roic"]


def test_nci_reported_but_absent_at_the_border_refuses(env):
    """D7 разрешает ноль только тем, кто NCI не отчитывал НИ РАЗУ. Эмитент
    её отчитывает, но на границе строки нет — значит, меньшинство там
    другое, и выдумывать сегодняшнее число на вчерашнюю дату нельзя."""
    conn, repos, _paths = env
    _base(conn, repos)
    _stock(conn, "i1", "minority_interest", 4.0, FY_END)
    rows = _build(repos)
    assert rows["roic"][4] is None, rows["roic"]
    assert rows["roic"][10] == "missing_prior_period", rows["roic"][10]


# ── lineage: обе даты знаменателя ──────────────────────────────────────

def test_both_denominator_dates_appear_in_lineage(env):
    """Мера обязана быть прочитана по своим входам (I4 + ТЗ-32 D6): в
    lineage roic лежат id всех слагаемых капитала обеих границ, и обе даты
    видны — начало окна названо ещё и в роли строки. До B5 производный
    капитал шёл в lineage пустым списком, и на пути «последний NOPAT
    первого прохода» I4 снимал меру до того, как тест успевал её
    увидеть."""
    conn, repos, _paths = env
    _base(conn, repos)
    rows = _build(repos)
    facts = _lineage_facts(conn, rows, "roic")
    for concept, end in (("total_equity", FY_END), ("total_debt", FY_END),
                         ("cash", FY_END), ("st_investments", FY_END),
                         ("total_equity", PRIOR_END),
                         ("total_debt", PRIOR_END),
                         ("cash", PRIOR_END),
                         ("st_investments", PRIOR_END)):
        assert f"f-i1-{concept}-as_reported-{end}" in facts, (concept, end)
    # обе даты знаменателя читаются из lineage: конец окна — под стоком
    # с ролью `input`, начало — с ролью, которая называет границу
    ends = {r[0] for r in conn.execute(
        """SELECT f.period_end FROM measure_lineage l
           JOIN fact f ON f.fact_id = l.fact_id
           WHERE l.measure_id=?""", (rows["roic"][0],))}
    assert {FY_END, PRIOR_END} <= ends, ends
    roles = _lineage_roles(conn, rows, "roic")
    assert any(f"capital at {PRIOR_END}" in role for role in roles), roles


def test_a_border_side_in_another_currency_is_a_k6_refusal(env):
    """ТЗ-91 B3 со второй датой: капитал начала окна в другой валюте —
    стороны расходятся, и частного не бывает. С B5 в спор валют входит
    вторая моментная граница, а не только сегодняшний баланс."""
    conn, repos, _paths = env
    _base(conn, repos)
    conn.execute("DELETE FROM fact WHERE period_end=?", (PRIOR_END,))
    _prior_balance(conn, "i1", currency="GBP")
    rows = _build(repos)
    assert rows["roic"][4] is None, rows["roic"]
    assert rows["roic"][10] == "currency_mismatch: GBP, USD", \
        rows["roic"][10]
