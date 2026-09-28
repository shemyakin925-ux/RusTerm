"""ТЗ-91 B4: входы оценочных мер проходят те же двери, что и первый проход.

Буква пункта (agent/TASK-91.md, B4) и что здесь проверяется:

| где | было | стало |
|---|---|---|
| `_latest_canonical` | свежайший факт по концепту без привязки к as_of и без правила давности: сборка на 2025-06-30 оценивала бумагу балансом 2026 года, а брошенный девять лет назад тег долга входил в сегодняшний EV | период позже as_of отсекается (ТЗ-22 J3), сток старше `_STALE_LOOKBACK_DAYS` от anchor эмитента — `stale_data: <концепт>: last <дата>` (форма ТЗ-55 Y1) |
| `latest_annual_fact` (repos) | «годовой» = окно >= 300 дней: двухлетний кумулятив проходил как годовой | коридор 350..380 — тот же, что у `_annual_common_period` и `is_annual_window` |
| `_latest_annual_input` | знаменатель запасного годового пути брался и из периода, закрытого после as_of | дверь as_of |
| `_annual_common_period` | общий годовой период выбирался и среди ещё не закрытых | та же дверь |
| `shares_outstanding` | — | дверь as_of стоит, дверь давности — нет: для акций есть своё, более строгое правило давности ТЗ-102 M1 (550 дней от as_of, токен `stale_input`), и оно всегда срабатывает раньше общей |

Причина отказа по вычищенному давностью входу — `stale_data`, а не
`missing_data`: тег подавался и перестал, а назвать его отсутствующим —
ровно та ложь, которую запретил B2. Цепочка (`net_debt_ebitda`) повторяет
чужой `stale_data` своим токеном, как повторяет `currency_mismatch` после
B3.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.snapshot import _STALE_LOOKBACK_DAYS, SnapshotBuilder
from rusterm.core.ttm import is_annual_window
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

# Дата сборки постоянная и в прошлом всех периодов фикстуры: двери
# меряются от неё, а не от сегодняшнего дня, иначе тест краснел бы со
# временем.
AS_OF = "2025-06-30"
PRICE_DATE = "2025-06-27"          # 3 дня: порог _PRICE_STALE_DAYS = 7
SHARES_DATE = "2025-03-31"         # 91 день: свежее порога M1 (550)
FY_END = "2024-12-31"              # годовой период, закрытый до as_of
FY_START = (date.fromisoformat(FY_END) - timedelta(days=364)).isoformat()
FUTURE = "2026-12-31"              # период, закрытый ПОСЛЕ as_of
ABANDONED = "2015-12-31"           # сток, отстающий от anchor на годы


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, iid="US-B4", issuer="i1"):
    """Бумага с ценой на `PRICE_DATE`; число акций — на `SHARES_DATE`."""
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))
    repos.price.put_rows(iid, "twelvedata",
                         [{"date": PRICE_DATE, "close": 10.0,
                           "currency": "USD"}])


def _fact(conn, issuer_id, concept, value, start, end, period_type):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-' || ? || '-' || ? || '-' || ?, ?, ?, ?, ?, ?, ?,
           'USD', 'USD', 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (issuer_id, concept, end, issuer_id, concept, start, end,
         period_type, str(value), concept))


def _stock(conn, issuer_id, concept, value, end=FY_END):
    _fact(conn, issuer_id, concept, value, end, end, "instant")


def _flow(conn, issuer_id, concept, value, start=FY_START, end=FY_END):
    _fact(conn, issuer_id, concept, value, start, end, "duration")


def _drop(conn, concept):
    conn.execute("DELETE FROM fact WHERE canonical_concept=?", (concept,))


def _balance(conn, issuer_id="i1", end=FY_END, shares=SHARES_DATE):
    """Число акций + долг 5, деньги 2 и 1, капитал 35 → net_debt 2,
    invested_capital 37; при цене 10.0 и 7 акциях капитализация 70.
    `shares` — отдельная дата: их свежость меряется своим порогом M1, а
    `end` задаёт anchor двери давности."""
    _fact(conn, issuer_id, "shares_outstanding", 7.0, shares,
          shares, "instant")
    _stock(conn, issuer_id, "total_debt", 5.0, end)
    _stock(conn, issuer_id, "cash", 2.0, end)
    _stock(conn, issuer_id, "st_investments", 1.0, end)
    _stock(conn, issuer_id, "total_equity", 35.0, end)


def _flows(conn, issuer_id="i1"):
    _flow(conn, issuer_id, "revenue", 100.0)
    _flow(conn, issuer_id, "net_income", 10.0)
    _flow(conn, issuer_id, "operating_income", 6.0)
    _flow(conn, issuer_id, "d_and_a", 1.0)
    _flow(conn, issuer_id, "tax_expense", 1.0)
    _flow(conn, issuer_id, "pretax_income", 5.0)


def _build(repos, iid="US-B4", issuer="i1", as_of=AS_OF):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(iid, issuer, as_of)
    return {m[3]: m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(iid))}


# ── дверь 1: период, закрытый после as_of, во вход не годится ──────────

def test_a_balance_closing_after_as_of_is_not_an_input(env):
    """ТЗ-91 B4, зуб «будущий факт»: долг на 2026-12-31 — отчёт ещё не
    закрыт на дату сборки 2025-06-30, и в net_debt / invested_capital / ev
    ему не место (первый проход режет так же, ТЗ-22 J3)."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "total_debt")
    _stock(conn, "i1", "total_debt", 5.0, FUTURE)
    rows = _build(repos)
    assert rows["net_debt"][4] is None, rows["net_debt"]
    assert rows["net_debt"][10] == "missing_data: total_debt", \
        rows["net_debt"][10]
    assert rows["invested_capital"][10] == "missing_data: total_debt", \
        rows["invested_capital"][10]
    assert rows["ev"][4] is None, rows["ev"]
    # капитализация — не балансовая мера: цена и акции закрыты до as_of,
    # поэтому она считается, а не отказывает заодно с долгом
    assert float(rows["market_cap"][4]) == pytest.approx(70.0), \
        rows["market_cap"]


def test_a_share_count_from_an_open_period_is_not_a_multiplier(env):
    """Дверь as_of стоит и на акциях, хотя дверь давности для них снимает-
    ся (M1): число акций на период, который ещё не закрыт, — не факт."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "shares_outstanding")
    _fact(conn, "i1", "shares_outstanding", 7.0, FUTURE, FUTURE, "instant")
    rows = _build(repos)
    assert rows["market_cap"][4] is None, rows["market_cap"]
    assert rows["market_cap"][10] == "missing_data: shares_outstanding", \
        rows["market_cap"][10]


def test_the_door_leaves_a_closed_balance_alone(env):
    """Случай «золотых» AAPL: всё закрыто до as_of — те же числа, ни
    одной новой отказной строки."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    rows = _build(repos)
    assert float(rows["net_debt"][4]) == pytest.approx(2.0), rows["net_debt"]
    assert float(rows["invested_capital"][4]) == pytest.approx(37.0)
    assert float(rows["pb"][4]) == pytest.approx(70.0 / 35.0), rows["pb"]
    assert float(rows["pe"][4]) == pytest.approx(70.0 / 10.0), rows["pe"]
    for concept in ("net_debt", "invested_capital", "pb", "pe", "ev",
                    "market_cap"):
        assert rows[concept][10] is None, (concept, rows[concept][10])


def test_a_fallback_denominator_cannot_come_from_the_future(env):
    """Запасной годовой знаменатель `ps` брался из годового периода,
    кончившегося позже as_of: сборка на 2025-06-30 делила капитализацию на
    выручку 2025 года, которой на эту дату ещё нет."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "revenue")
    _flow(conn, "i1", "revenue", 200.0, "2025-01-01", "2025-12-31")
    rows = _build(repos)
    assert rows["ps"][4] is None, rows["ps"]
    assert rows["ps"][10] == "missing_data: revenue_ttm", rows["ps"][10]
    # знаменатель `pe` закрыт до as_of — мера остаётся с числом
    assert float(rows["pe"][4]) == pytest.approx(7.0), rows["pe"]


def test_the_common_annual_period_of_a_chain_also_respects_as_of(env):
    """ТЗ-31 C2 (`_annual_common_period`) выбирает последний общий годовой
    период входов; без двери там же оказывался период, закрытый после
    as_of, и EBITDA из него умножала знаменатель в несколько раз.

    Форма фикстуры — реальный разнобой: операционная прибыль подаётся
    кварталами (окно TTM собирается), амортизация — только годовыми, и у
    обеих есть ещё не закрытый год. Общего окна нет, поэтому мера садится
    на годовой общий период — и обязана взять закрытый (2023), а не
    будущий (2026)."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    # roic в этой фикстуре остаётся на последнем NOPAT первого прохода, а
    # его знаменатель — моментный капитал; как отдельный факт он подан
    # здесь только затем, чтобы строка мерала свой lineage (иначе I4
    # снимает исключение до того, как тест увидит число)
    _stock(conn, "i1", "invested_capital", 40.0)
    _drop(conn, "operating_income")
    _drop(conn, "d_and_a")
    quarters = [("2024-07-01", "2024-09-30"), ("2024-10-01", "2024-12-31"),
                ("2025-01-01", "2025-03-31"), ("2025-04-01", "2025-06-30")]
    for i, (start, end) in enumerate(quarters):
        _flow(conn, "i1", "operating_income", 25.0 + i, start, end)
    _flow(conn, "i1", "operating_income", 100.0, "2023-01-01", "2023-12-31")
    _flow(conn, "i1", "operating_income", 999.0, "2026-01-01", FUTURE)
    _flow(conn, "i1", "d_and_a", 5.0, "2023-01-01", "2023-12-31")
    _flow(conn, "i1", "d_and_a", 999.0, "2026-01-01", FUTURE)
    rows = _build(repos)
    ev = float(rows["ev"][4])
    assert ev == pytest.approx(70.0 + 5.0 - 2.0 - 1.0), rows["ev"]
    # 72 / (100 + 5), а не 72 / (999 + 999): закрытый год, не будущий
    assert float(rows["ev_ebitda"][4]) == pytest.approx(ev / 105.0), \
        rows["ev_ebitda"]


# ── дверь 2: брошенный тег ────────────────────────────────────────────

def test_an_abandoned_debt_tag_refuses_with_stale_data(env):
    """ТЗ-91 B4, зуб «брошенный тег»: долг эмитент перестал подавать девять
    лет назад, и в сегодняшний EV он больше не входит. Причина —
    `stale_data` с последним известным периодом (форма ТЗ-55 Y1): факт
    был, `missing_data` соврал бы, что его не подавали никогда."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "total_debt")
    _stock(conn, "i1", "total_debt", 5.0, ABANDONED)
    rows = _build(repos)
    expected = f"stale_data: total_debt: last {ABANDONED}"
    assert rows["net_debt"][4] is None, rows["net_debt"]
    assert rows["net_debt"][10] == expected, rows["net_debt"][10]
    assert rows["invested_capital"][10] == expected, rows["invested_capital"]
    assert rows["ev"][10] == expected, rows["ev"]
    # B2: ни одна строка не называет отсутствующим то, что подавался
    named = [c for c, r in rows.items()
             if "missing_data: total_debt" in (r[10] or "")
             or ", total_debt" in (r[10] or "")]
    assert not named, f"total_debt назван отсутствующим в {named}"


def test_the_stale_refusal_is_a_dictionary_reason(env):
    """Каждая причина прохода — из словаря §1.4 (страж B15 стоит и на
    новых токенах)."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "total_debt")
    _stock(conn, "i1", "total_debt", 5.0, ABANDONED)
    rows = _build(repos)
    for row in rows.values():
        assert is_known_reason(row[10]), (row[3], row[10])


def test_a_stale_tag_does_not_refuse_the_measures_that_do_not_need_it(env):
    """Дверь касается своего концепта: капитал на месте, поэтому `pb`
    считается, хотя долга в наборе годных входов нет."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "total_debt")
    _stock(conn, "i1", "total_debt", 5.0, ABANDONED)
    rows = _build(repos)
    assert float(rows["pb"][4]) == pytest.approx(2.0), rows["pb"]
    assert rows["pb"][10] is None, rows["pb"]
    assert float(rows["market_cap"][4]) == pytest.approx(70.0)
    assert float(rows["pe"][4]) == pytest.approx(7.0), rows["pe"]


def test_the_chain_repeats_the_stale_refusal_instead_of_calling_net_debt_missing(env):
    """net_debt_ebitda без net_debt по давности: `missing_data: net_debt`
    соврал бы про меру, у которой причина названа, — тот же порядок, что
    B3 установил для currency_mismatch."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "total_debt")
    _stock(conn, "i1", "total_debt", 5.0, ABANDONED)
    rows = _build(repos)
    assert rows["net_debt_ebitda"][4] is None, rows["net_debt_ebitda"]
    assert rows["net_debt_ebitda"][10] == \
        f"stale_data: total_debt: last {ABANDONED}", \
        rows["net_debt_ebitda"][10]
    # знаменатель roic — отказавшийся по той же причине
    # invested_capital: цепочка повторяет его строку, а не объявляет
    # капитал отсутствующим (тот же порядок, что у net_debt_ebitda)
    assert rows["roic"][4] is None, rows["roic"]
    assert rows["roic"][10] == f"stale_data: total_debt: last {ABANDONED}", \
        rows["roic"][10]


def test_the_staleness_door_measures_the_issuers_anchor_not_the_calendar(env):
    """Порог меряется от anchor эмитента (самого свежего закрытого периода
    входов), как в первом проходе (TASK-12 Y2): весь набор старых, но
    согласованных балансов — не «давность», а просто старый эмитент, и
    меры считаются. Просрочка ровно одного входа — отказ по нему."""
    conn, repos = env
    _paper(repos)
    # весь набор годов на 2020-12-31: anchor = 2020-12-31, ages = 0
    _balance(conn, end="2020-12-31", shares="2020-12-31")
    _flows(conn)
    # revenue — тоже канонический вход оценочных мер (pe/ps), и в этом
    # эмитенте он подан на свежий год; чтобы anchor остался «2020-12-31»,
    # вход убирается совсем: мера без него откажет, а давность не изменится
    _drop(conn, "revenue")
    rows = _build(repos)
    assert float(rows["net_debt"][4]) == pytest.approx(2.0), rows["net_debt"]
    assert rows["net_debt"][10] is None, rows["net_debt"][10]
    # долг отстал от anchor (2020-12-31) на порог + 1 день
    _drop(conn, "total_debt")
    _stock(conn, "i1", "total_debt", 5.0,
           (date.fromisoformat("2020-12-31")
            - timedelta(days=_STALE_LOOKBACK_DAYS + 1)).isoformat())
    rows = _build(repos)
    assert (rows["net_debt"][10] or "").startswith(
        "stale_data: total_debt: last "), rows["net_debt"][10]


# ── дверь 3: «годовой» — коридор, а не «любое окно >= 300 дней» ───────

def test_a_two_year_cumulative_is_not_annual(env):
    """ТЗ-91 B4, зуб «730-дневное окно»: знаменатель pe из двух лет при
    капитализации за один — частное не про меру. Порог 300 дней пропускал
    его, коридор 350..380 (ТЗ-31 C2) — нет."""
    conn, repos = env
    _paper(repos)
    _balance(conn)
    _flows(conn)
    _drop(conn, "net_income")
    _flow(conn, "i1", "net_income", 20.0,
          (date.fromisoformat(FY_END) - timedelta(days=730)).isoformat(),
          FY_END)
    rows = _build(repos)
    assert rows["pe"][4] is None, rows["pe"]
    assert rows["pe"][10] == "missing_data: net_income_ttm", rows["pe"][10]


def test_the_store_corridor_agrees_with_the_kernel(env):
    """Одно определение года у слоя хранилища и у ядра: коридор
    `latest_annual_fact` обязан совпасть с `is_annual_window` на всех
    границах — иначе два «года» разъедутся, как разъехались до ТЗ-97 Q10
    в первом проходе."""
    conn, repos = env
    for days in (334, 349, 350, 364, 380, 381, 410, 730, 1095):
        issuer = f"i-{days}"
        repos.instrument.upsert_issuer(Issuer(
            issuer, "Corp", "US", None, None, "us-gaap", "USD"))
        start = (date.fromisoformat(FY_END)
                 - timedelta(days=days)).isoformat()
        _flow(conn, issuer, "net_income", 10.0, start, FY_END)
        annual = is_annual_window(start, FY_END)
        got = repos.snapshot.latest_annual_fact(issuer, "net_income",
                                              as_of=AS_OF)
        assert (got is not None) is annual, (days, annual, got)


def test_the_store_door_hides_an_open_period(env):
    """Без as_of фильтр не ставится — то же соглашение, что у первого
    прохода (`_issuer_inputs`, ТЗ-22 J3): дверь открыта только когда
    дата сборки известна."""
    conn, repos = env
    repos.instrument.upsert_issuer(Issuer(
        "i-door", "Corp", "US", None, None, "us-gaap", "USD"))
    _flow(conn, "i-door", "net_income", 10.0, "2025-01-01", "2025-12-31")
    assert repos.snapshot.latest_annual_fact("i-door", "net_income") \
        is not None, "годовой 2025-го без двери as_of не взят"
    assert repos.snapshot.latest_annual_fact(
        "i-door", "net_income", as_of=AS_OF) is None
