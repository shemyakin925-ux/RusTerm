"""ТЗ-102 M3: баланс на границе окна может прийти из restated-подачи.

Почему это нужно (ADR-0025, пункт 5; координатор, вариант (a) решения 5).
Годовой баланс эмитент подаёт в СЛЕДУЮЩЕМ отчёте сравнительной колонкой,
и разборщик ставит такому факту basis='restated' (determine_basis: период
документа позже периода факта). Проход входов берёт только as_reported —
значит на границе TTM-окна годовой даты нет, и `roe`/`asset_turnover`
отказывают `period_mismatch` именно у тех бумаг, где окно кончается
годовым балансом (замер 27.09 на копии базы: AAPL 2023-09-30, 2024-09-28,
2025-09-27 и ORCL 2024-05-31, 2025-05-31, 2026-05-31 — все restated).

Правило: сток ищется СТРОГО на дату границы; если на этой дате нет
as_reported — берётся restated того же числа и помечается в lineage
(база `restated` + названа подача-источник). Другая дата не подставляется
никогда, приоритет as_reported не понижается.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = "2026-09-24"
TTM_START, TTM_END = "2025-07-01", "2026-06-30"

# потоки: FY2025 + H1-2026 − H1-2025 → окно 1200 (revenue) и 140
# (net_income)
FLOW_FACTS = {
    "revenue": (("2025-01-01", "2025-12-31", "1000"),
                ("2026-01-01", "2026-06-30", "600"),
                ("2025-01-01", "2025-06-30", "400")),
    "net_income": (("2025-01-01", "2025-12-31", "100"),
                   ("2026-01-01", "2026-06-30", "80"),
                   ("2025-01-01", "2025-06-30", "40")),
}

FILING_URL = ("https://data.sec.gov/api/xbrl/companyfacts/"
              "CIK0000042425.json")


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _raw_object(conn, sha="r1", url=FILING_URL):
    """Подача-источник: строка raw_object, по которой lineage и называет
    файл. Без неё fact живёт (FK в фикстурах не включён), но имя подачи
    взять неоткуда."""
    conn.execute(
        """INSERT INTO raw_object(sha256, provider, url, fetched_at, bytes,
           content_type, compression)
           VALUES (?, 'edgar', ?, 0, 10, 'application/json', 'none')""",
        (sha, url))


def _duration(conn, issuer_id, concept, start, end, value):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, 'us-gaap:' || ?, ?, ?, 'duration', ?, 'USD',
           'USD', 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"f-{issuer_id}-{concept}-{start}-{end}", issuer_id, concept,
         start, end, value, concept))


def _stock(conn, issuer_id, concept, end, value, basis="as_reported",
           sha="s"):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, 'us-gaap:' || ?, ?, ?, 'instant', ?, 'USD',
           'USD', ?, 'extracted', ?, '{}', 'companyfacts.v1', 'ok',
           0, ?, 'provider')""",
        (f"f-{issuer_id}-{concept}-{end}-{basis}", issuer_id, concept,
         end, end, value, basis, sha, concept))


def _issuer(conn, repos, instrument_id, issuer_id, stocks=()):
    """Эмитент фикстуры: потоки окна + перечень стоков
    (concept, end, value, basis)."""
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "US", None, "12-31", "us_gaap",
        "USD"))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    for concept, rows in FLOW_FACTS.items():
        for start, end, value in rows:
            _duration(conn, issuer_id, concept, start, end, value)
    for concept, end, value, basis in stocks:
        _stock(conn, issuer_id, concept, end, value, basis)


def _build(repos, instrument_id, issuer_id):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build(instrument_id, issuer_id, AS_OF)
    return repos.snapshot.get_measures(result.snapshot_id), result


def _measure(rows, concept):
    return next(m for m in rows if m[3] == concept)


def _stock_roles(repos, measure_id):
    """Роли стоковых входов меры — только они, чтобы не цеплять слагаемые
    окна."""
    return [r for r, in repos.conn.execute(
        """SELECT role FROM measure_lineage WHERE measure_id=?
           AND role LIKE '%stock%'""", (measure_id,)).fetchall()]


def test_border_stock_may_come_from_restated_filing(env):
    """Годовая дата конца окна есть только в restated — мера считается,
    а не отказывает: сегодня это `period_mismatch` (красный зуб M3)."""
    conn, repos = env
    _issuer(conn, repos, "US-R1", "i1", stocks=(
        ("total_assets", "2025-06-30", "700", "as_reported"),
        ("total_assets", "2026-06-30", "900", "restated"),
    ))
    rows, _result = _build(repos, "US-R1", "i1")
    m = _measure(rows, "asset_turnover")
    # 1200 / avg(700, 900) = 1.5
    assert m[4] is not None, m[10]
    assert float(m[4]) == pytest.approx(1.5), m[4]
    assert (m[6], m[7]) == (TTM_START, TTM_END), (m[6], m[7])


def test_restated_border_is_marked_in_lineage(env):
    """Отметка обязательна: база входа — restated, и названа подача, из
    которой он взят (иначе меру нельзя прочесть заново)."""
    conn, repos = env
    _raw_object(conn)
    _issuer(conn, repos, "US-R1", "i1", stocks=(
        ("total_assets", "2025-06-30", "700", "as_reported"),
        ("total_assets", "2026-06-30", "900", "restated"),
    ))
    # restated-факт фикстуры ссылается на подачу r1
    conn.execute("UPDATE fact SET source_ref='r1' WHERE basis='restated'")
    rows, _result = _build(repos, "US-R1", "i1")
    m = _measure(rows, "asset_turnover")
    roles = _stock_roles(repos, m[0])
    assert len(roles) == 2, roles
    marked = [r for r in roles if "restated" in r]
    assert len(marked) == 1, roles
    assert "2026-06-30" in marked[0], marked[0]
    assert "CIK0000042425.json" in marked[0], marked[0]
    # база ПЕРИОДА при этом остаётся базой окна — restated не перекраивает
    # period_basis в 'annual'
    assert {b for (b,) in repos.conn.execute(
        """SELECT DISTINCT period_basis FROM measure_lineage
           WHERE measure_id=?""", (m[0],)).fetchall()} == {"ttm"}


def test_as_reported_on_the_same_date_still_wins(env):
    """Приоритет не понижается: на дате границы есть as_reported — он и
    идёт в вход, restated того же числа не участвует и не помечается."""
    conn, repos = env
    _issuer(conn, repos, "US-R2", "i2", stocks=(
        ("total_assets", "2025-06-30", "700", "as_reported"),
        ("total_assets", "2026-06-30", "900", "as_reported"),
        ("total_assets", "2026-06-30", "9999", "restated"),
    ))
    rows, _result = _build(repos, "US-R2", "i2")
    m = _measure(rows, "asset_turnover")
    assert float(m[4]) == pytest.approx(1.5), m[4]
    assert not [r for r in _stock_roles(repos, m[0]) if "restated" in r], \
        _stock_roles(repos, m[0])


def test_restated_on_another_date_is_never_substituted(env):
    """На границе даты нет — и restated с ДРУГОЙ даты не спасает: отказ
    остаётся `period_mismatch` (М3 запрещает подстановку даты)."""
    conn, repos = env
    _issuer(conn, repos, "US-R3", "i3", stocks=(
        ("total_assets", "2025-06-30", "700", "as_reported"),
        ("total_assets", "2026-03-31", "900", "restated"),
    ))
    rows, _result = _build(repos, "US-R3", "i3")
    m = _measure(rows, "asset_turnover")
    assert m[4] is None, m[4]
    assert m[10] == "period_mismatch", m[10]


def test_begin_border_takes_the_restated_year_end(env):
    """Начало окна — та же граница: как ближайшая дата НЕ ПОЗЖЕ начала.
    Квартальный as_reported 2025-03-31 ближе, чем ничего, но годовой
    restated 2025-06-30 — ровно граница, и он приоритетнее более ранней
    даты: мера берёт 700, а не 600."""
    conn, repos = env
    _issuer(conn, repos, "US-R4", "i4", stocks=(
        ("total_assets", "2025-03-31", "600", "as_reported"),
        ("total_assets", "2025-06-30", "700", "restated"),
        ("total_assets", "2026-06-30", "900", "as_reported"),
    ))
    rows, _result = _build(repos, "US-R4", "i4")
    m = _measure(rows, "asset_turnover")
    assert float(m[4]) == pytest.approx(1200 / ((700 + 900) / 2)), m[4]


def test_restated_beyond_the_freshness_lookback_is_not_a_border(env):
    """Древняя сравнительная колонка не имеет права стать границей:
    правило давности входов (Y2) действует и на restated-путь. Концепт
    при этом_present_ в as_reported (квартальный баланс 2026-03-31), чтобы
    отказ был про границу, а не про отсутствующий вход."""
    conn, repos = env
    _issuer(conn, repos, "US-R5", "i5", stocks=(
        ("total_assets", "2026-03-31", "850", "as_reported"),
        ("total_assets", "2023-01-01", "500", "restated"),
        ("total_assets", "2026-06-30", "900", "restated"),
    ))
    rows, _result = _build(repos, "US-R5", "i5")
    m = _measure(rows, "asset_turnover")
    assert m[4] is None, m[4]
    assert m[10] == "period_mismatch", m[10]


def test_roe_uses_the_restated_equity_at_the_border(env):
    """То же на второй паре: `roe` = 140 / avg(700, 900)."""
    conn, repos = env
    _issuer(conn, repos, "US-R6", "i6", stocks=(
        ("total_equity", "2025-06-30", "700", "as_reported"),
        ("total_equity", "2026-06-30", "900", "restated"),
    ))
    rows, _result = _build(repos, "US-R6", "i6")
    m = _measure(rows, "roe")
    assert float(m[4]) == pytest.approx(140 / ((700 + 900) / 2)), m[4]


def test_a_border_with_neither_basis_refuses(env):
    """Ни as_reported, ни restated на дате границы — прежний отказ,
    слово в слово (М3 не отменяет решение Q10 о смеси окон)."""
    conn, repos = env
    _issuer(conn, repos, "US-R7", "i7", stocks=(
        ("total_assets", "2025-06-30", "700", "as_reported"),
    ))
    rows, _result = _build(repos, "US-R7", "i7")
    m = _measure(rows, "asset_turnover")
    assert m[4] is None, m[4]
    assert m[10] == "period_mismatch", m[10]
