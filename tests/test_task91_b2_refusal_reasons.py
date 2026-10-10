"""ТЗ-91 B2: причины отказа в проходе оценки не врут.

Правило словаря §1.4: у входа, который на месте, нет права называться
отсутствующим. Шесть строк пункта:

| где | было | стало |
|---|---|---|
| pe, net_income ≤ 0 | `missing_data: net_income` | `negative_denominator` / `denominator_zero` |
| net_debt_ebitda, ebitda ≤ 0 | `missing_data: ebitda` | то же |
| нет цены | early return писал `price_close` во все 13 строк | net_debt, net_debt_ebitda, invested_capital считаются без цены |
| net_debt | отказывал `missing_data: market_cap_total` | капитализация в формуле не участвует |
| effective_tax, pretax < 0 | `jurisdiction_rate` | `negative_denominator` |
| `calculate_measure` на неизвестный концепт | `missing_data` | `concept_not_mapped` |
| nopat при отказе ставки | `missing_data: effective_tax, operating_income` | `missing_data: effective_tax` |

Граница, оставленная как есть сознательно: `roic` в отказе по цене
остаётся — его крепит чужой тест
`tests/test_k4_k6_valuation.py::test_missing_price_yields_reason_on_all_six`
(строка ТЗ-23 K4 «все шесть ценовых мер»), а пункт B2 про net_debt,
invested_capital и net_debt_ebitda.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.snapshot import (
    _STALE_LOOKBACK_DAYS, SnapshotBuilder)
from rusterm.formulas import calculate_measure, effective_tax_rate
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = date.today().isoformat()
FRESH_SHARES = date.fromordinal(date.today().toordinal() - 90).isoformat()
FY_END = "2025-12-31"      # годовой период, закрытый до as_of
FY_START = "2025-01-01"    # 364 дня — годовой для окна TTM (350..380)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, conn, iid="US-B2", issuer="i1", price=True):
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))
    if price:
        repos.price.put_rows(iid, "twelvedata",
                             [{"date": AS_OF, "close": 10.0,
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


def _stock(conn, issuer_id, concept, value, end):
    _fact(conn, issuer_id, concept, value, end, end, "instant")


def _flow(conn, issuer_id, concept, value, end=FY_END, days=364):
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    _fact(conn, issuer_id, concept, value, start, end, "duration")


def _base(conn, issuer_id="i1"):
    """Эмитент со всеми входами прохода оценки. Долг 5, деньги 2 и 1,
    капитал 35 → net_debt = 2, invested_capital = 37; flows — годовые,
    закрытые до as_of. ebitda = 6 + 1 = 7, net_income = 10,
    revenue = 100, pretax_income = 5."""
    _stock(conn, issuer_id, "shares_outstanding", 7.0, FRESH_SHARES)
    _flow(conn, issuer_id, "revenue", 100.0)
    _flow(conn, issuer_id, "net_income", 10.0)
    _flow(conn, issuer_id, "operating_income", 6.0)
    _flow(conn, issuer_id, "d_and_a", 1.0)
    _flow(conn, issuer_id, "tax_expense", 1.0)
    _flow(conn, issuer_id, "pretax_income", 5.0)
    _stock(conn, issuer_id, "total_debt", 5.0, FY_END)
    _stock(conn, issuer_id, "cash", 2.0, FY_END)
    _stock(conn, issuer_id, "st_investments", 1.0, FY_END)
    _stock(conn, issuer_id, "total_equity", 35.0, FY_END)


def _set(conn, issuer_id, concept, value):
    """Значение входа меняётся на месте: строка остаётся на месте,
    и отказ не может сослаться на «нет факта»."""
    conn.execute("UPDATE fact SET value=? WHERE issuer_id=?"
                 " AND canonical_concept=?",
                 (str(value), issuer_id, concept))


def _build(repos, iid="US-B2", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build(iid, issuer, AS_OF)
    rows = {m[3]: m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(iid))}
    return rows, result


def _valued_inputs(conn, rows):
    """Имена входов, у которых ЕСТЬ число: концепты мер со значением и
    канонические концепты фактов. Для стража B2."""
    names = {m[3] for m in rows.values() if m[4] is not None}
    names |= {r[0] for r in conn.execute(
        """SELECT DISTINCT canonical_concept FROM fact
           WHERE value IS NOT NULL AND status='ok'
             AND canonical_concept IS NOT NULL""")}
    return names


# ── строки 1 и 2: знак знаменателя, у которого есть число ──────────────

NONPOSITIVE = [
    ("pe", "net_income", -50.0, "negative_denominator"),
    ("pe", "net_income", 0.0, "denominator_zero"),
    ("ps", "revenue", -100.0, "negative_denominator"),
    ("net_debt_ebitda", "operating_income", -5.0, "negative_denominator"),
    ("net_debt_ebitda", "operating_income", -1.0, "denominator_zero"),
]


@pytest.mark.parametrize("measure,input,value,reason", NONPOSITIVE)
def test_denominator_with_a_number_is_not_missing_data(
        env, measure, input, value, reason):
    conn, repos = env
    _paper(repos, conn)
    _base(conn)
    _set(conn, "i1", input, value)
    rows, _result = _build(repos)
    m = rows[measure]
    assert m[4] is None, (measure, m[4])
    assert m[10] == reason, (measure, m[10])
    assert is_known_reason(m[10])
    # тот же вход не называется отсутствующим ни в одной другой мере
    named = [c for c, r in rows.items()
             if (r[10] or "").startswith(f"missing_data: {input}")
             or f", {input}" in (r[10] or "")]
    assert not named, f"{input} с числом назван отсутствующим в {named}"


def test_pe_on_the_annual_fallback_says_the_same(env):
    """Запасной годовой вход pe (окна TTM нет) — тот же честный токен.

    Отказ пишется раньше пометки годового основания, поэтому ветку
    отличает контрольный прогон: то же окно с положительным числом
    обязано дать пометку `pe` — иначе строка читалась бы из окна TTM, а
    не с `_latest_annual_input`, и тест проверял бы не ту ветку.

    Фикстура переписана ТЗ-91 B4: раньше ветку отличал 320-дневный период
    (для окна TTM не годовой, для `_latest_annual_input` — да с порогом
    300 дней). После B4 «годовой» — один коридор 350..380 на оба места, и
    такой период не год ни туда, ни туда: мера отказала бы по
    `missing_data`, а не по знаменателю. Годный способ оставить ту же
    ветку — годовой вход, вычищенный из входов правилом давности: окна
    меры нет, а `_latest_annual_input` его берёт (так же, как это держит
    тест ТЗ-97 Q10 `test_pe_on_a_stale_annual_is_marked_annual_fallback`).
    """
    conn, repos = env
    _paper(repos, conn)
    _base(conn)
    # единственный net_income — годовой 2022-го: от anchor эмитента
    # (2025-12-31) он отстаёт больше чем на _STALE_LOOKBACK_DAYS, поэтому
    # окна TTM у меры нет, а запасным годовым входом она его берёт
    stale_end = (date.fromisoformat(FY_END)
                 - timedelta(days=_STALE_LOOKBACK_DAYS + 20)).isoformat()
    conn.execute("DELETE FROM fact WHERE issuer_id='i1'"
                 " AND canonical_concept='net_income'")
    _flow(conn, "i1", "net_income", 50.0, end=stale_end)
    _rows, control = _build(repos)
    assert "pe" in {c for c, _why in control.annual_fallbacks}, \
        f"ветка не та: {control.annual_fallbacks}"
    _set(conn, "i1", "net_income", -50.0)
    rows, _result = _build(repos)
    assert rows["pe"][4] is None
    assert rows["pe"][10] == "negative_denominator", rows["pe"][10]


# ── строка 3: нет цены — считается то, чему цена не нужна ──────────────

def test_price_free_measures_compute_without_a_price(env):
    conn, repos = env
    _paper(repos, conn, price=False)
    _base(conn)
    rows, _result = _build(repos)
    assert float(rows["net_debt"][4]) == pytest.approx(2.0), rows["net_debt"]
    assert float(rows["invested_capital"][4]) == pytest.approx(37.0)
    assert float(rows["net_debt_ebitda"][4]) == pytest.approx(2.0 / 7.0)
    for concept in ("net_debt", "invested_capital", "net_debt_ebitda"):
        assert rows[concept][10] is None, (concept, rows[concept][10])
    # ценовые меры остаются при своём честном отказе
    assert rows["market_cap"][10] == "missing_data: price_close"
    assert rows["roic"][10] == "missing_data: price_close", \
        "roic крепит тест K4 — см. докстринг модуля"


# ── строка 4: net_debt не зависит от капитализации ─────────────────────

def test_net_debt_survives_a_failed_market_cap(env):
    """Акций нет → market_cap и всё, что из неё растёт, отказаны; долг
    и деньги в фактах — net_debt, net_debt_ebitda и invested_capital
    считаются."""
    conn, repos = env
    _paper(repos, conn)
    _base(conn)
    conn.execute("DELETE FROM fact WHERE canonical_concept"
                 "='shares_outstanding'")
    rows, _result = _build(repos)
    assert rows["market_cap"][10] == "missing_data: shares_outstanding"
    assert rows["net_debt"][10] is None, rows["net_debt"][10]
    assert float(rows["net_debt"][4]) == pytest.approx(2.0)
    assert float(rows["invested_capital"][4]) == pytest.approx(37.0)
    assert float(rows["net_debt_ebitda"][4]) == pytest.approx(2.0 / 7.0)
    for concept in ("pe", "ev", "pb"):
        assert rows[concept][4] is None
        assert rows[concept][10] == "missing_data: market_cap_total", \
            (concept, rows[concept][10])


# ── строка 5: отрицательный знаменатель, а не полоса юрисдикции ────────

def test_negative_pretax_is_a_negative_denominator(env):
    conn, repos = env
    _paper(repos, conn)
    _base(conn)
    _set(conn, "i1", "pretax_income", -5.0)
    rows, _result = _build(repos)
    assert rows["effective_tax"][4] is None
    assert rows["effective_tax"][10] == "negative_denominator", \
        rows["effective_tax"][10]
    assert effective_tax_rate(1.0, -4000.0) == (None,
                                               "negative_denominator")
    # ставка вне полосы с положительным знаменателем — по-прежнему она
    assert effective_tax_rate(-4640375000.0, 19487327000.0) == (
        None, "jurisdiction_rate: rate=-0.2381")


# ── строка 6: неизвестный концепт ──────────────────────────────────────

def test_unknown_concept_is_not_reported_as_missing_data():
    m = calculate_measure("no_such_measure", revenue=100.0)
    assert m.value is None
    assert m.null_reason == "concept_not_mapped", m.null_reason
    assert is_known_reason(m.null_reason)


# ── строка 7: цепочка называет отвалившееся звено, а не весь вход ──────

def test_chain_names_only_the_link_that_fell_out(env):
    """nopat = operating_income * (1 − ставка). Ставка отказала —
    `missing_data` обязан назвать её одну: operating_income — исходный
    вход, у него есть число, и мерой он не был, так что в computed его
    нет по устройству, а не по нехватке."""
    conn, repos = env
    _paper(repos, conn)
    _base(conn)
    _set(conn, "i1", "pretax_income", -5.0)
    rows, _result = _build(repos)
    assert rows["nopat"][10] == "missing_data: effective_tax", \
        rows["nopat"][10]
    assert rows["operating_margin"][4] is not None, \
        "operating_income на месте — иначе проверка пуста"


# ── страж пункта: ни один отказ не называет вход, у которого есть число ─

def test_no_refusal_names_an_input_that_has_a_value(env):
    conn, repos = env
    _paper(repos, conn)
    _base(conn)
    # все спорные входы — present-but-nonpositive
    _set(conn, "i1", "net_income", -50.0)
    _set(conn, "i1", "revenue", 0.0)
    _set(conn, "i1", "operating_income", -5.0)
    _set(conn, "i1", "pretax_income", -5.0)
    rows, _result = _build(repos)
    names = _valued_inputs(conn, rows)
    assert {"net_income", "revenue", "operating_income",
            "pretax_income"} <= names, "фикстура потеряла вход"
    offenders = []
    for concept, m in rows.items():
        reason = m[10] or ""
        if not reason.startswith("missing_data:"):
            continue
        for part in reason[len("missing_data:"):].split(","):
            token = part.strip().split(":")[0]
            if token and token in names:
                offenders.append((concept, reason))
    assert not offenders, (
        f"отказ называет отсутствующим вход с числом: {offenders}")
