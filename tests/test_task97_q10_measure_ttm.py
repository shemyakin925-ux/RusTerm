"""ТЗ-97 Q10: TTM для всех потоковых входов — зубы на мерах.

Красные до правки: сегодня потоковый вход меры — последний годовой
(ADR-0021, ТЗ-69 P1) или свежайший общий период (первый проход), а
дивиденды складываются только из четырёх кварталов. Зубы проверяют окно,
величину, lineage-слагаемые и то, что годовой запасной выход НЕ молчит.

Фикстура — декабрьский эмитент на three-факт-наборе: FY2025 + YTD H1
2026 + YTD H1 2025, из которых собирается TTM-окно
2025-07-01…2026-06-30 (100 + 60 − 40 style).
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = "2026-09-24"
# TTM-окно по фикстуре: день после конца вычитаемого YTD и до конца
# прибавляемого
TTM_START, TTM_END = "2025-07-01", "2026-06-30"

# FY2025 / H1-2026 / H1-2025 для потоковых входов
FLOW_FACTS = {
    "revenue": (("2025-01-01", "2025-12-31", "1000"),
                ("2026-01-01", "2026-06-30", "600"),
                ("2025-01-01", "2025-06-30", "400")),
    "net_income": (("2025-01-01", "2025-12-31", "100"),
                   ("2026-01-01", "2026-06-30", "80"),
                   ("2025-01-01", "2025-06-30", "40")),
}
# сток — мгновенная величина: конец окна и начало окна
STOCK_FACTS = {
    "total_assets": (("2026-06-30", "900"), ("2025-06-30", "700"),
                     ("2025-12-31", "800")),
}


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


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


def _instant(conn, issuer_id, concept, end, value):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, 'us-gaap:' || ?, ?, ?, 'instant', ?, 'USD',
           'USD', 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"f-{issuer_id}-{concept}-{end}", issuer_id, concept, end, end,
         value, concept))


def _issuer(conn, repos, instrument_id, issuer_id, with_price=True):
    """Эмитент фикстуры: потоковые входы, сток активов, класс акций и
    цена; `with_price=False` — только первый проход."""
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "US", None, "12-31", "us_gaap",
        "USD"))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    for concept, rows in FLOW_FACTS.items():
        for start, end, value in rows:
            _duration(conn, issuer_id, concept, start, end, value)
    for concept, rows in STOCK_FACTS.items():
        for end, value in rows:
            _instant(conn, issuer_id, concept, end, value)
    if with_price:
        _duration(conn, issuer_id, "shares_outstanding",
                  "2025-01-01", "2025-12-31", "100")
        repos.price.put_rows(instrument_id, "twelvedata",
                             [{"date": AS_OF, "close": 10.0,
                               "currency": "USD"}])


def _build(repos, instrument_id, issuer_id):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build(instrument_id, issuer_id, AS_OF)
    rows = repos.snapshot.get_measures(result.snapshot_id)
    return rows, result


def _measure(rows, concept):
    return next(m for m in rows if m[3] == concept)


def _lineage(repos, measure_id):
    return repos.conn.execute(
        """SELECT role, period_basis FROM measure_lineage
           WHERE measure_id=? ORDER BY role""", (measure_id,)).fetchall()


def test_net_margin_takes_the_ttm_window_not_the_half_year(env):
    """Поток меры — последние 12 месяцев, а не свежий YTD в 6 месяцев:
    сегодня знаменатель и числитель берутся последним общим периодом
    (H1-2026), и «маржа» становится полугодовой."""
    conn, repos = env
    _issuer(conn, repos, "US-TTM", "i1", with_price=False)
    rows, _result = _build(repos, "US-TTM", "i1")
    m = _measure(rows, "net_margin")
    # TTM: (100 + 80 − 40) / (1000 + 600 − 400) = 140 / 1200
    assert float(m[4]) == pytest.approx(140 / 1200), m[4]
    assert (m[6], m[7]) == (TTM_START, TTM_END), (m[6], m[7])


def test_net_margin_lineage_names_every_addend_on_ttm_basis(env):
    """Lineage потоковой меры обязан перечислить слагаемые окна и их
    базу: по трём фактам на вход видно, что знаменатель вычитался."""
    conn, repos = env
    _issuer(conn, repos, "US-TTM", "i1", with_price=False)
    rows, result = _build(repos, "US-TTM", "i1")
    mid = _measure(rows, "net_margin")[0]
    lineage = _lineage(repos, mid)
    assert {b for _r, b in lineage} == {"ttm"}, lineage
    assert len(lineage) == 6, [r for r, _b in lineage]
    roles = " | ".join(r for r, _b in lineage)
    for token in ("fy", "ytd", "ytd_prior"):
        assert token in roles, (token, roles)


def test_pe_denominator_is_ttm_net_income(env):
    """pe = капитализация / TTM-прибыль: сегодня знаменатель — годовой
    net_income (100), и мультипликатор завышен вдвое против
    трейлингового."""
    conn, repos = env
    _issuer(conn, repos, "US-TTM", "i1")
    rows, _result = _build(repos, "US-TTM", "i1")
    m = _measure(rows, "pe")
    assert float(m[4]) == pytest.approx(100 * 10.0 / 140), m[4]
    roles = " | ".join(r for r, _b in _lineage(repos, m[0]))
    assert "fy" in roles and "ytd_prior" in roles, roles


def test_asset_turnover_average_spans_the_same_window_as_the_flow(env):
    """Средний капитал — по запасу на НАЧАЛО и КОНЕЦ окна потока:
    сегодня «начало» — любая предыдущая точка отчётности (квартал перед
    годовым), и средняя берётся по трём месяцам против годовой выручки."""
    conn, repos = env
    _issuer(conn, repos, "US-TTM", "i1", with_price=False)
    rows, _result = _build(repos, "US-TTM", "i1")
    m = _measure(rows, "asset_turnover")
    # revenue TTM 1200 / avg(700 на 2025-06-30, 900 на 2026-06-30)
    assert float(m[4]) == pytest.approx(1200 / 800), m[4]
    assert (m[6], m[7]) == (TTM_START, TTM_END), (m[6], m[7])


def test_missing_addend_takes_the_last_annual_not_the_half_year(env):
    """Нет вычитаемого YTD — вся мера берёт последний годовой, а не
    свежий полугодовой период: смешивать базы нельзя."""
    conn, repos = env
    _issuer(conn, repos, "US-FB", "i2", with_price=False)
    # снимаем H1-2025: TTM не собирается ни для revenue, ни для
    # net_income
    repos.conn.execute(
        "DELETE FROM fact WHERE issuer_id='i2' AND period_end='2025-06-30'")
    rows, _result = _build(repos, "US-FB", "i2")
    m = _measure(rows, "net_margin")
    assert float(m[4]) == pytest.approx(100 / 1000), m[4]
    assert (m[6], m[7]) == ("2025-01-01", "2025-12-31"), (m[6], m[7])


def test_the_fallback_marks_its_lineage_and_names_the_addend(env):
    """Запасной выход не молчит: база периода в lineage —
    annual_fallback, роль называет недостающее слагаемое (концепт и
    период)."""
    conn, repos = env
    _issuer(conn, repos, "US-FB", "i2", with_price=False)
    repos.conn.execute(
        "DELETE FROM fact WHERE issuer_id='i2' AND period_end='2025-06-30'")
    rows, result = _build(repos, "US-FB", "i2")
    mid = _measure(rows, "net_margin")[0]
    lineage = _lineage(repos, mid)
    assert {b for _r, b in lineage} == {"annual_fallback"}, lineage
    roles = " | ".join(r for r, _b in lineage)
    assert "TTM не собран" in roles, roles
    assert "ytd_prior" in roles and "2025-06-30" in roles, roles
    assert any(c == "net_margin" and "2025-06-30" in note
               for c, note in result.annual_fallbacks), result.annual_fallbacks


def test_the_cli_prints_the_annual_instead_of_ttm_mark(env, capsys,
                                                       tmp_path):
    """«в окне и rusterm snapshot — пометка» (ТЗ-97 Q10): пользователь
    видит, что мера считена годовым, а не трейлингом."""
    from rusterm.cli import main
    root = str(tmp_path / "cli")
    assert main(["--root", root, "init"]) == 0
    capsys.readouterr()
    paths = AppPaths.from_root(tmp_path / "cli")
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    repos = RepoRegistry(conn, paths)
    # сидинг идёт через repos, а не ручными INSERT'ами: схему знают они
    repos.instrument.upsert_issuer(Issuer(
        "i3", "Corp i3", "US", "NASDAQ", "12-31", "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-FB3", "i3", "FB3", "common", "active", None))
    for concept, rows in FLOW_FACTS.items():
        for start, end, value in rows:
            if end == "2025-06-30":
                continue  # нет вычитаемого — годовой запасной
            _duration(conn, "i3", concept, start, end, value)
    conn.close()
    assert main(["--root", root, "snapshot", "--instrument",
                 "US-FB3"]) == 0
    out = capsys.readouterr().out
    assert "годовой, TTM не собран" in out, out
    assert "net_margin" in out, out


def test_dividend_yield_takes_the_ttm_window_of_dps(env):
    """Дивиденды — та же функция окна (ТЗ-97 Q10): сегодня TTM складывается
    только из четырёх подряд кварталов, а FY + YTD − YTD пр. не собирается,
    и мера берёт годовой dps там, где есть трейлинг."""
    conn, repos = env
    _issuer(conn, repos, "US-TTM", "i1")
    for start, end, value in (("2025-01-01", "2025-12-31", "4.0"),
                              ("2026-01-01", "2026-06-30", "3.0"),
                              ("2025-01-01", "2025-06-30", "1.0")):
        _duration(conn, "i1", "dps", start, end, value)
    rows, _result = _build(repos, "US-TTM", "i1")
    m = _measure(rows, "div_yield")
    # dps TTM = 4 + 3 − 1 = 6 на цену 10
    assert float(m[4]) == pytest.approx(0.6), m[4]
    assert {b for _r, b in _lineage(repos, m[0])} == {"ttm"}


def test_a_window_without_its_boundary_stock_refuses_rather_than_mixes(env):
    """Сток не лежит на границе окна (у ORCL балансы годовых дат поданы
    в базисе restated и в as_reported-проход не попадают) — мера
    отказывает, а не считается потоком окна и стоком с другой даты:
    «разные окна — period_mismatch» (ТЗ-97 Q10). До правки мера молча
    уезжала на свежий общий период."""
    conn, repos = env
    _issuer(conn, repos, "US-TTM", "i1", with_price=False)
    conn.execute("DELETE FROM fact WHERE canonical_concept='total_assets' "
                 "AND period_end='2026-06-30'")
    rows, _result = _build(repos, "US-TTM", "i1")
    m = _measure(rows, "asset_turnover")
    assert m[4] is None, m[4]
    assert m[10] == "period_mismatch", m[10]


def test_pe_on_a_stale_annual_is_marked_annual_fallback(env):
    """Годовой факт, который проход входов не пустил во вход меры (Y2 —
    старше порога давности), годовым быть не перестаёт: и база периода, и
    пометка обязательны на этом пути тоже (ТЗ-97 Q10)."""
    conn, repos = env
    _issuer(conn, repos, "US-OLD", "i4")
    conn.execute("DELETE FROM fact WHERE issuer_id='i4' "
                 "AND canonical_concept='net_income'")
    # единственный net_income — годовой 2022-й: он старше порога
    # давности, но `_latest_annual_input` его берёт
    _duration(conn, "i4", "net_income", "2022-01-01", "2022-12-31", "100")
    rows, result = _build(repos, "US-OLD", "i4")
    m = _measure(rows, "pe")
    # капитализация 100 * 10.0 / годовой 100
    assert float(m[4]) == pytest.approx(10.0), m[4]
    lineage = _lineage(repos, m[0])
    assert {b for _r, b in lineage} == {"annual_fallback"}, lineage
    assert any(c == "pe" for c, _n in result.annual_fallbacks), \
        result.annual_fallbacks
    # одно написание на все годовые пути: роль называет ту базу, что
    # стоит в period_basis, — иначе поверхности «годовой» не видят
    for role, basis in conn.execute(
            "SELECT role, period_basis FROM measure_lineage "
            "WHERE period_basis IS NOT NULL").fetchall():
        assert role.startswith(f"input:{basis} "), (role, basis)


def test_inputs_sharing_a_span_but_not_a_basis_take_the_annual(env):
    """Одинаковые границы окна — ещё не одна база (ТЗ-97 Q10 пункт 4).
    Форму повторяет живой JPM на копии базы: revenue подан одним годовым
    2025-го, после него ничего нет — по пункту 2 годовой и есть окно,
    basis `ttm`; net_income подаёт кварталы 2026-го без парного YTD
    прошлого года — окно не собирается, и его годовой 2025-го есть
    basis `annual_fallback`. Окна совпадают по датам, базы разные, и
    мера обязана взять одну базу для обоих потоков, а не печатать в
    lineage `ttm` рядом с `annual_fallback`: читатель карточки видит
    одну меру, а не два входа с двумя объяснениями."""
    conn, repos = env
    _issuer(conn, repos, "US-JPM-SHAPE", "i5", with_price=False)
    conn.execute("DELETE FROM fact WHERE issuer_id='i5' "
                 "AND canonical_concept='revenue'")
    _duration(conn, "i5", "revenue", "2025-01-01", "2025-12-31", "1000")
    conn.execute("DELETE FROM fact WHERE issuer_id='i5' "
                 "AND canonical_concept='net_income'")
    for start, end, value in (("2025-01-01", "2025-12-31", "100"),
                              ("2026-01-01", "2026-03-31", "25"),
                              ("2026-01-01", "2026-06-30", "50")):
        _duration(conn, "i5", "net_income", start, end, value)
    rows, result = _build(repos, "US-JPM-SHAPE", "i5")
    m = _measure(rows, "net_margin")
    assert {b for _r, b in _lineage(repos, m[0])} == {"annual_fallback"}, \
        _lineage(repos, m[0])
    assert (m[6], m[7]) == ("2025-01-01", "2025-12-31"), (m[6], m[7])
    # число то же (оба потока одного годового периода), меняется база:
    # смесь баз в lineage одной меры недопустима
    assert float(m[4]) == pytest.approx(100 / 1000), m[4]
    assert any(c == "net_margin" for c, _n in result.annual_fallbacks), \
        result.annual_fallbacks
    # и по всей сборке: у одной меры — одна база периода
    for row in rows:
        bases = {b for _r, b in _lineage(repos, row[0])}
        assert len(bases) <= 1, (row[3], bases)


def test_windows_of_different_spans_take_the_common_annual_and_say_so(env):
    """Окна входов собраны, но разные (у revenue после годового 2025-го
    ничего нет — окно равно году; у net_income собирается алгебра
    2025-07-01…2026-06-30) — смешивать запрещено, и мера берёт последний
    общий годовой период своих входов. Причина обязана назваться и здесь:
    слагаемого не хватает — ни у одного окна список недостающего пуст,
    и единственное честное объяснение состоит в том, что общего окна нет
    (ТЗ-97 Q10 пункт 4)."""
    conn, repos = env
    _issuer(conn, repos, "US-DIFF", "i6", with_price=False)
    conn.execute("DELETE FROM fact WHERE issuer_id='i6' "
                 "AND canonical_concept='revenue' "
                 "AND period_end<>'2025-12-31'")
    rows, result = _build(repos, "US-DIFF", "i6")
    m = _measure(rows, "net_margin")
    # общий годовой: 100 / 1000, а не 140 / 1000 из двух окон
    assert float(m[4]) == pytest.approx(100 / 1000), m[4]
    assert (m[6], m[7]) == ("2025-01-01", "2025-12-31"), (m[6], m[7])
    lineage = _lineage(repos, m[0])
    assert {b for _r, b in lineage} == {"annual_fallback"}, lineage
    roles = " | ".join(r for r, _b in lineage)
    assert "общего TTM-окна нет" in roles, roles
    assert "2025-07-01…2026-06-30" in roles, roles
    assert any(c == "net_margin" and "общего TTM-окна нет" in note
               for c, note in result.annual_fallbacks), result.annual_fallbacks


def test_the_window_panel_says_the_measure_is_annual_not_trailing(env):
    """«в окне … пометка» (ТЗ-97 Q10): панель источника меры, считанной
    годовым вместо трейлинга, называет недостающее слагаемое — иначе в
    окне годовой множитель выглядит последними двенадцатью месяцами."""
    from rusterm.desktop import data as desktop_data
    conn, repos = env
    _issuer(conn, repos, "US-FB", "i2", with_price=False)
    repos.conn.execute(
        "DELETE FROM fact WHERE issuer_id='i2' AND period_end='2025-06-30'")
    rows, _result = _build(repos, "US-FB", "i2")
    m = _measure(rows, "net_margin")
    row = {"measure_id": m[0], "concept": m[3], "value": m[4],
           "unit": m[5], "null_reason": m[10],
           "measure": {"measure_id": m[0], "concept": m[3],
                       "value": m[4], "unit": m[5], "issuer_id": "i2"}}
    text = desktop_data.source_panel_view(repos, repos.paths, row)["text"]
    assert "годовой, TTM не собран" in text, text
    assert "2025-06-30" in text, text
