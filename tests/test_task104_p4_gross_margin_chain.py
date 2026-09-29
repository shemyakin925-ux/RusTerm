"""ТЗ-104 P4: `gross_margin` считает по готовой мере `gross_profit`.

Буква пункта (agent/TASK-104.md, P4): «Wire through `_CHAIN_MEASURES` like
`nopat ← effective_tax`». До пункта `gross_margin` стояла формулой первого
прохода с входами `{gross_profit, revenue}` — то есть требовала **факт**
валовой прибыли. ТЗ-97 Q7 выпустил меру `gross_profit`, которая считается
из поданных `revenue − cogs` там, где своего тега нет, но ряд маржи её не
увидел: на копии базы пользователя у CLF, FCX, LUMN и STX валовая прибыль
есть, а маржи нет.

| где | было | стало |
|---|---|---|
| словарь | `gross_margin` — формула первого прохода, вход = тег GrossProfit | член `_CHAIN_MEASURES`, числитель подставляется из посчитанной меры того же прохода |
| эмитент без тега, с Revenues и CostOfRevenue | `missing_data: gross_profit` | маря = GROSS / REVENUE, в lineage факт выручки + ссылка на меру |
| тег GrossProfit подан | значение по факту | то же значение: приоритет раскрытой величины живёт в мере, ряд получает её ответ |
| валовой прибыли нет (нет `cogs`) | `missing_data: gross_profit` | та же причина: цепочка зовёт отвалившееся ЗВЕНО (ТЗ-58 C4) |

`base_concepts` обязана продолжать просить `gross_profit` как концепт:
раскрытый тег — приоритетный вход меры (ТЗ-97 Q7, Wells Fargo), и если
ряд перестанет называть его входом формулы первого прохода, факт просто
перестанет попадать в выборку.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import (
    _CHAIN_MEASURES,
    _MEASURE_FORMULAS,
    SnapshotBuilder,
    base_concepts,
    measure_inputs,
)
from rusterm.formulas import calculate_measure, measure_unit
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = "2026-09-24"
FY = ("2025-01-01", "2025-12-31")
PRIOR_FY = ("2024-01-01", "2024-12-31")
TTM = ("2025-07-01", "2026-06-30")
REVENUE = 1000.0
COGS = 620.0
GROSS = REVENUE - COGS               # 380
MARGIN = GROSS / REVENUE             # 0.38
# скелет для зуба «тег подан»: валовая прибыль раскрыта, слагаемые
# против неё (банк, у которого в себестоимость попал процентный расход)
DISCLOSED = 244_000_000.0
DISCLOSED_REVENUE = 803_000_000.0
DISCLOSED_COGS = 804_457_000_000.0


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, iid="US-P4", issuer="i1"):
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))


def _flow(conn, issuer, concept, value, period=FY, unit="USD"):
    start, end = period
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, 'us-gaap:' || ?, ?, ?, 'duration', ?, ?, ?,
           'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"f-{issuer}-{concept}-{start}-{end}", issuer, concept, start, end,
         repr(value), unit, unit, concept))


def _build(repos, iid="US-P4", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build(iid, issuer, AS_OF)
    return {m[3]: m for m in repos.snapshot.get_measures(result.snapshot_id)}


def _lineage(repos, measure_id):
    return repos.conn.execute(
        "SELECT fact_id, peer_measure_id, role FROM measure_lineage "
        "WHERE measure_id=? ORDER BY fact_id, role", (measure_id,)).fetchall()


# ── словарь: ряд стоит в цепочке, а не в первом проходе ────────────────

def test_the_row_is_a_chain_member_now():
    """Зуб структуры: `gross_margin` больше не формула первого прохода и
    стоит в `_CHAIN_MEASURES` с числителем-мерой — как `nopat` со
    ставкой. Иначе порядок групп в build() не имеет для неё смысла."""
    assert "gross_margin" not in _MEASURE_FORMULAS
    assert _CHAIN_MEASURES["gross_margin"] == {
        "gross_profit": "gross_profit", "revenue": "revenue"}
    assert measure_inputs("gross_margin") == ("gross_profit", "revenue")


def test_the_disclosed_tag_is_still_a_fetch_target():
    """Ловушка пункта: входы формул первого прохода задают, какие концепты
    вообще запрашиваются. Если `gross_profit` выпадет из base_concepts
    вместе с рядом, раскрытый тег перестанет попадать в выборку, и
    приоритет ТЗ-97 Q7 умрёт молча — на пустом `by_concept`."""
    assert "gross_profit" in base_concepts


def test_the_dictionary_formula_and_unit_are_unchanged():
    """Формула и единица ряда те же: маржа — отношение, а не деньги."""
    assert calculate_measure("gross_margin", gross_profit=GROSS,
                             revenue=REVENUE).value == pytest.approx(MARGIN)
    assert measure_unit("gross_margin", "USD") == "ratio"


# ── Done-when: тега нет, слагаемые есть — маржа со значением ────────────

def test_margin_has_a_value_without_the_gross_profit_fact(env):
    """Зуб Done-when: у эмитента нет факта GrossProfit, есть Revenues и
    CostOfRevenue. Ряд обязан получить 380/1000 из посчитанной меры, а не
    `missing_data: gross_profit`."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)
    _flow(conn, "i1", "cogs", COGS)

    rows = _build(repos)

    margin = rows["gross_margin"]
    assert float(margin[4]) == pytest.approx(MARGIN), margin
    assert margin[10] is None, margin[10]
    assert margin[5] == "ratio", margin[5]
    # период ряда = период числителя, а не «as_of, as_of»
    assert (margin[6], margin[7]) == FY, margin
    assert float(rows["gross_profit"][4]) == pytest.approx(GROSS), \
        rows["gross_profit"]


def test_margin_lineage_links_the_profit_measure(env):
    """Числитель — чужая мера, и это видно: в ряду ссылка на её
    measure_id, как у `nopat` со ставкой. Факт меньшинства здесь ни при
    чём — фактов валовой прибыли в фикстуре нет."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)
    _flow(conn, "i1", "cogs", COGS)

    rows = _build(repos)
    links = _lineage(repos, rows["gross_margin"][0])
    assert rows["gross_profit"][0] in {r[1] for r in links}, links
    assert {r[0] for r in links if r[0]} == {
        "f-i1-revenue-2025-01-01-2025-12-31"}, links


def test_margin_shares_the_window_of_its_numerator(env):
    """Q10 распространяется на ряд через числитель: оба слагаемых собирают
    TTM-окно 2025-07-01…2026-06-30 (1200 − 720 = 480), ряд того же окна и
    равен 480/1200."""
    conn, repos = env
    _paper(repos)
    for concept, values in (("revenue", (1000.0, 600.0, 400.0)),
                            ("cogs", (600.0, 360.0, 240.0))):
        fy, h1_new, h1_old = values
        _flow(conn, "i1", concept, fy, period=FY)
        _flow(conn, "i1", concept, h1_new, period=("2026-01-01", "2026-06-30"))
        _flow(conn, "i1", concept, h1_old, period=("2025-01-01", "2025-06-30"))

    rows = _build(repos)

    assert float(rows["gross_profit"][4]) == pytest.approx(480.0)
    margin = rows["gross_margin"]
    assert float(margin[4]) == pytest.approx(0.4), margin
    assert (margin[6], margin[7]) == TTM, margin
    assert margin[10] is None, margin[10]


# ── чего пункт не должен сломать ────────────────────────────────────────

def test_disclosed_aggregate_still_drives_the_margin(env):
    """Тег GrossProfit подан — ряд считает по нему, а не по вычитанию:
    мера выбирает раскрытую величину (Уэллс Фарго: вычитание даёт
    −1 457 000 000 против раскрытых +244 000 000). Поведение было верным
    и обязано остаться."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", DISCLOSED_REVENUE)
    _flow(conn, "i1", "cogs", DISCLOSED_COGS)
    _flow(conn, "i1", "gross_profit", DISCLOSED)

    rows = _build(repos)

    margin = rows["gross_margin"]
    assert float(margin[4]) == pytest.approx(
        DISCLOSED / DISCLOSED_REVENUE), margin
    assert margin[10] is None, margin[10]


def test_absent_component_is_still_named_by_the_link(env):
    """Себестоимости не было никогда: валовая прибыль не считается, ряд
    зовёт отвалившееся звено `gross_profit` (ТЗ-58 C4), а не голое
    missing_data. Причина была верной — пусть и остаётся."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)

    rows = _build(repos)

    margin = rows["gross_margin"]
    assert margin[4] is None, margin
    assert margin[10] == "missing_data: gross_profit", margin[10]
    assert is_known_reason(margin[10].split(":")[0])


def test_components_of_different_years_do_not_make_a_margin(env):
    """Выручка 2025, себестоимость 2024: валовая прибыль не считается
    (`period_mismatch`), ряд не имеет права брать знаменатель из одного
    года, а числитель — «ниоткуда»."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)
    _flow(conn, "i1", "cogs", COGS, period=PRIOR_FY)

    rows = _build(repos)

    assert rows["gross_profit"][10] == "period_mismatch"
    margin = rows["gross_margin"]
    assert margin[4] is None, margin
    assert is_known_reason(margin[10].split(":")[0].split(";")[0]), margin[10]


def test_disclosed_profit_in_another_currency_refuses_the_margin(env):
    """K6: раскрытая валовая прибыль в GBP под выручкой в USD — не
    частное, а две валюты. До пункта ряд брал оба факта одним общим
    ключом `(unit, start, end)`, и такая пара не сходилась вовсе; через
    цепочку общий ключ исчезает — отказ обязан быть явным, а не числом."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", DISCLOSED_REVENUE)
    _flow(conn, "i1", "cogs", COGS)
    _flow(conn, "i1", "gross_profit", DISCLOSED, unit="GBP")

    rows = _build(repos)

    margin = rows["gross_margin"]
    assert margin[4] is None, margin
    assert margin[10] == "currency_mismatch: GBP, USD", margin[10]


def test_nopat_chain_link_is_untouched(env):
    """Страховка на обобщение места, где цепочка дописывает lineage:
    `nopat` обязана остаться ссылкой на `effective_tax` — одна ссылка,
    та же роль."""
    conn, repos = env
    _paper(repos)
    _flow(conn, "i1", "revenue", REVENUE)
    _flow(conn, "i1", "cogs", COGS)
    _flow(conn, "i1", "operating_income", 200.0)
    _flow(conn, "i1", "tax_expense", 60.0)
    _flow(conn, "i1", "pretax_income", 240.0)

    rows = _build(repos)

    links = _lineage(repos, rows["nopat"][0])
    assert rows["effective_tax"][0] in {r[1] for r in links}, links
    assert rows["gross_profit"][0] not in {r[1] for r in links}, links
    assert float(rows["nopat"][4]) == pytest.approx(
        200.0 * (1 - 0.25)), rows["nopat"]
