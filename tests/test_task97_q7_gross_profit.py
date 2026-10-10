"""ТЗ-97 Q7: валовая прибыль — формула словаря, а не только тег.

Буква пункта (agent/TASK-97.md, Q7): «софт и телеком не подают
GrossProfit, но подают выручку и себестоимость» — значит мера обязана
считаться из поданных фактов: объявлена формулой в словаре мер,
происхождение обоих слагаемых в lineage, тот же период. Расчёт, а не
подстановка: общего периода нет — отказ, а не число из другого года.

| где | было | стало |
|---|---|---|
| словарь мер | `gross_profit` — только вход `gross_margin`; строки меры не было ни у кого | формула первого прохода `{revenue, cogs}`, unit kind `money` (валюта входов) |
| эмитент без тега GrossProfit, с Revenues и CostOfRevenue | `gross_margin: missing_data: gross_profit`, валовой прибыли в выводе нет | мера посчитана, в lineage оба слагаемых своими fact_id. ТЗ-104 P4: рядом стоит и `gross_margin` — он читает посчитанную меру |
| слагаемые из разных периодов | — | `period_mismatch` (одно окно на всю меру, ТЗ-97 Q10) |
| тег GrossProfit подан | меры нет | значение = поданная величина: словарь §2 определяет концепт как «= revenue − cogs, **если не раскрыт**», раскрытое приоритетнее вычитания |
| GrossProfit без себестоимости | меры нет (факт лежал невостребованным) | мера со значением, в lineage один факт |

Приоритет раскрытой величины — не поблажка: на копии базы пользователя
262 последних issuer-периода, где поданы все три тега, расходятся в
двух, и оба — Wells Fargo (cik-106040): `revenue − cogs` даёт
−1 457 000 000 против раскрытых +244 000 000, потому что у банка в
себестоимость попадает процентный расход. Показать отрицательную
валовую прибыль там, где эмитент раскрыл положительную, — число,
которое врёт.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import SnapshotBuilder, measure_inputs
from rusterm.formulas import calculate_measure, measure_unit
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = "2026-09-24"
# годовой период фикстуры: он и окно меры, когда после него ничего нет
FY = ("2025-01-01", "2025-12-31")
REVENUE = 1000.0
COGS = 620.0
GROSS = REVENUE - COGS           # 380
# предыдущий год — для зуба про разные периоды
PRIOR_FY = ("2024-01-01", "2024-12-31")
# квартальная фикстура: FY + H1 после + H1 до → окно 2025-07-01…2026-06-30
TTM = ("2025-07-01", "2026-06-30")


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, iid="US-Q7", issuer="i1"):
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))


def _flow(conn, issuer, concept, value, period=FY):
    """Потоковый факт: тег us-gaap:<concept>, каноникал тот же концепт —
    ровно как после разбора companyfacts."""
    start, end = period
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, 'us-gaap:' || ?, ?, ?, 'duration', ?, 'USD',
           'USD', 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"f-{issuer}-{concept}-{start}-{end}", issuer, concept, start, end,
         repr(value), concept))


def _build(repos, iid="US-Q7", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build(iid, issuer, AS_OF)
    rows = {m[3]: m for m in repos.snapshot.get_measures(
        result.snapshot_id)}
    return rows, result


def _lineage(repos, measure_id):
    return repos.conn.execute(
        "SELECT fact_id, role, period_basis FROM measure_lineage "
        "WHERE measure_id=? ORDER BY fact_id", (measure_id,)).fetchall()


# ── словарь мер ──

def test_dictionary_declares_the_formula_and_its_unit():
    """Q7: «объявить формулой в словаре мер» — формула, входы и единица.
    Зуб краснеет, пока gross_profit остаётся только входом
    gross_margin."""
    assert measure_inputs("gross_profit") == ("cogs", "revenue")
    # валюта входов, а не «ratio»: валовая прибыль — деньги
    assert measure_unit("gross_profit", "USD") == "USD"
    assert measure_unit("gross_profit", "BRL") == "BRL"


def test_components_are_subtracted_and_absence_is_named_by_name():
    """Движок: revenue − cogs; нехватка названа концептом, как требует
    ТЗ-91 B2 («причина не врёт»)."""
    m = calculate_measure("gross_profit", revenue=REVENUE, cogs=COGS)
    assert (m.value, m.null_reason) == (GROSS, None)

    only_revenue = calculate_measure("gross_profit", revenue=REVENUE)
    assert only_revenue.value is None
    assert only_revenue.null_reason == "missing_data: cogs"
    assert is_known_reason(only_revenue.null_reason.split(":")[0])

    only_cogs = calculate_measure("gross_profit", cogs=COGS)
    assert only_cogs.value is None
    assert only_cogs.null_reason == "missing_data: revenue"


# ── путь «тега нет — считаем» ──

def test_measure_without_the_tag_computes_and_carries_both_sources(env):
    """Done-when Q7: без тега GrossProfit, с Revenues и CostOfRevenue —
    мера считается, и оба слагаемых стоят в lineage своими id."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)
    _flow(conn, "i1", "cogs", COGS)

    rows, _ = _build(repos)

    row = rows["gross_profit"]
    assert float(row[4]) == pytest.approx(GROSS)
    assert row[5] == "USD"
    assert row[10] is None
    assert (row[6], row[7]) == FY
    assert row[8] == "gross_profit" and row[9] == "v1"

    lineage = _lineage(repos, row[0])
    assert {r[0] for r in lineage} == {"f-i1-cogs-2025-01-01-2025-12-31",
                                       "f-i1-revenue-2025-01-01-2025-12-31"}
    assert all(r[1].startswith("input:") for r in lineage)

    # ТЗ-104 P4 дописывает сюжет: ряд маржи стоит на ПОСЧИТАННОЙ мере, а
    # не на поданном теге. Булавка Q7 «gross_margin остался на подаваемом
    # теге» здесь заменена более сильной: тот же вход без тега даёт и
    # валовую прибыль, и маржу (вопрос был в Disputed отчёта TASK-97,
    # решение координатора — строка «8, 21 | chain gross_margin | P4»).
    margin = rows["gross_margin"]
    assert float(margin[4]) == pytest.approx(GROSS / REVENUE), margin
    assert margin[10] is None, margin[10]


def test_components_from_different_periods_refuse(env):
    """Done-when Q7: «с разными периодами — period_mismatch». Выручка
    2025-го и себестоимость 2024-го — не валовая прибыль одного года, а
    смесь баз: числа в строке не будет."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)
    _flow(conn, "i1", "cogs", COGS, period=PRIOR_FY)

    rows, _ = _build(repos)

    row = rows["gross_profit"]
    assert row[4] is None
    assert row[10] == "period_mismatch"
    assert is_known_reason(row[10])
    assert _lineage(repos, row[0]) == []


def test_missing_component_is_named_not_silent(env):
    """Выручка есть, себестоимости не было никогда — отказ зовёт `cogs`
    по имени (ТЗ-91 B2), а не голое missing_data."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)

    rows, _ = _build(repos)

    row = rows["gross_profit"]
    assert row[4] is None
    assert row[10] == "missing_data: cogs"


# ── путь «тег подан — берём его» ──

def test_filed_aggregate_wins_over_the_subtraction(env):
    """Словарь §2: «= revenue − cogs, если не раскрыт». Раскрытая
    величина приоритетнее вычитания, и в lineage стоит её fact_id, а не
    слагаемые.

    Числа взяты с копии базы пользователя (Wells Fargo, cik-106040):
    вычитание даёт отрицательную валовую прибыль, эмитент раскрывает
    положительную."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", 803_000_000.0)
    _flow(conn, "i1", "cogs", 804_457_000_000.0)   # −1 457 000 000
    _flow(conn, "i1", "gross_profit", 244_000_000.0)

    rows, _ = _build(repos)

    row = rows["gross_profit"]
    assert float(row[4]) == pytest.approx(244_000_000.0)
    assert float(row[4]) > 0
    lineage = _lineage(repos, row[0])
    assert {r[0] for r in lineage} == {"f-i1-gross_profit-2025-01-01-2025-12-31"}


def test_filed_aggregate_without_cogs_still_gives_the_measure(env):
    """Часть эмитентов базы подаёт GrossProfit без тега себестоимости.
    До Q7 их валовая прибыль не появлялась в выводе вообще, хотя факт
    лежал в базе."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)
    _flow(conn, "i1", "gross_profit", GROSS)

    rows, _ = _build(repos)

    row = rows["gross_profit"]
    assert float(row[4]) == pytest.approx(GROSS)
    assert row[10] is None
    assert {r[0] for r in _lineage(repos, row[0])} == {
        "f-i1-gross_profit-2025-01-01-2025-12-31"}


# ── окно: те же двери, что у остальных потоковых мер ──

def test_ttm_window_feeds_both_components(env):
    """Q10 распространяется и на новую меру: оба слагаемых берутся из
    одного TTM-окна, а не из последнего годового. 1000+600−400 и
    600+360−240 → 1200 − 720 = 480 за 2025-07-01…2026-06-30."""
    conn, repos = env
    _paper(repos)
    for concept, values in (("revenue", (1000.0, 600.0, 400.0)),
                            ("cogs", (600.0, 360.0, 240.0))):
        fy, h1_new, h1_old = values
        _flow(conn, "i1", concept, fy, period=FY)
        _flow(conn, "i1", concept, h1_new,
              period=("2026-01-01", "2026-06-30"))
        _flow(conn, "i1", concept, h1_old,
              period=("2025-01-01", "2025-06-30"))

    rows, _ = _build(repos)

    row = rows["gross_profit"]
    assert float(row[4]) == pytest.approx(480.0)
    assert (row[6], row[7]) == TTM
    assert row[10] is None
    # шесть слагаемых одного окна: три у выручки, три у себестоимости
    assert len(_lineage(repos, row[0])) == 6
