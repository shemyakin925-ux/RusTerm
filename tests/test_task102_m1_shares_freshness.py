"""ТЗ-102 M1: цена умножается только на свежее число акций.

Решение координатора по пункту 1 из спорных REPORT-97: капитализация по
цене сегодня и числу акций 14-летней давности хуже честного отказа.

Правило: для мер, где цена умножается на акции (market_cap и всё, что
построено на market_cap_total — ev, pe, ps, pb, fcf_yield), вход
shares_outstanding годен, пока его период кончился не раньше as_of −
_SHARES_FRESH_DAYS (то же число дней, что у порога годового dps:
_DPS_ANNUAL_STALE_DAYS). Якорь — as_of, а не самый свежий факт эмитента:
у бумаги с десятком свежих отчётов и одним забытым тегом акций
капитализация всё равно считается по тому тегу. Отказ называет дату:
`stale_input: shares_outstanding (<дата>)`.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.snapshot import SnapshotBuilder, _SHARES_FRESH_DAYS
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = date.today().isoformat()


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, conn, instrument_id, issuer_id):
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "US", None, None, "us_gaap",
        "USD"))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    repos.price.put_rows(instrument_id, "twelvedata",
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
    """Мгновенный факт: период — одна дата, как у тегов
    CommonStockSharesOutstanding."""
    _fact(conn, issuer_id, concept, value, end, end, "instant")


def _flow(conn, issuer_id, concept, value, end):
    start = (date.fromisoformat(end) - timedelta(days=360)).isoformat()
    _fact(conn, issuer_id, concept, value, start, end, "duration")


def _vale_shape(conn, issuer_id, shares_end):
    """Фикстура формы VALE: цена сегодняшняя, акции давным-давно,
    свежие потоки и капитал вокруг."""
    _stock(conn, issuer_id, "shares_outstanding", 270_927_828.0,
           shares_end)
    _flow(conn, issuer_id, "revenue", 100.0, "2025-12-31")
    _flow(conn, issuer_id, "net_income", 10.0, "2025-12-31")
    _stock(conn, issuer_id, "total_equity", 50.0, "2025-12-31")


def _build(repos, instrument_id, issuer_id, as_of=AS_OF):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(instrument_id, issuer_id, as_of)
    return repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(instrument_id))


def _measure(rows, concept):
    return next(m for m in rows if m[3] == concept)


STALE_REFUSAL = "stale_input: shares_outstanding (2012-12-31)"


def test_stale_share_count_refuses_market_cap(env):
    """Акций 2012 года, цена сегодняшняя — отказ с датой, не число."""
    conn, repos = env
    _paper(repos, conn, "US-V", "i1")
    _vale_shape(conn, "i1", "2012-12-31")
    mcap = _measure(_build(repos, "US-V", "i1"), "market_cap")
    assert mcap[4] is None, "капитализация по 14-летнему числу акций"
    assert mcap[10] == STALE_REFUSAL, mcap[10]


def test_refusal_propagates_to_market_cap_total(env):
    """market_cap_total наследует названную причину: у производных мер
    в отказе читается настоящее имя входа, а не выдуманная цена."""
    conn, repos = env
    _paper(repos, conn, "US-V", "i1")
    _vale_shape(conn, "i1", "2012-12-31")
    total = _measure(_build(repos, "US-V", "i1"), "market_cap_total")
    assert total[4] is None
    assert total[10] == STALE_REFUSAL, total[10]


def test_fresh_share_count_computes_market_cap(env):
    conn, repos = env
    # ТЗ-110 B0.4: край считается от ТОГО ЖЕ as_of, что идёт в сборку,
    # — переход полуночи посреди прогона не разъезжает тест и сборку
    fresh = (date.fromisoformat(AS_OF) - timedelta(days=90)).isoformat()
    _paper(repos, conn, "US-V", "i1")
    _vale_shape(conn, "i1", fresh)
    mcap = _measure(_build(repos, "US-V", "i1"), "market_cap")
    assert mcap[4] is not None, mcap[10]
    assert mcap[10] is None
    assert float(mcap[4]) == pytest.approx(10.0 * 270_927_828.0)


def test_boundary_of_freshness_window_is_inclusive(env):
    """Ровно _SHARES_FRESH_DAYS — ещё годен; на день старше — отказ."""
    edge = (date.fromisoformat(AS_OF)
            - timedelta(days=_SHARES_FRESH_DAYS)).isoformat()
    over = (date.fromisoformat(AS_OF)
            - timedelta(days=_SHARES_FRESH_DAYS + 1)).isoformat()
    conn, repos = env
    _paper(repos, conn, "US-E", "i1")
    _vale_shape(conn, "i1", edge)
    mcap = _measure(_build(repos, "US-E", "i1"), "market_cap")
    assert mcap[4] is not None, f"граница окна ({edge}) отсечена зря"

    _paper(repos, conn, "US-O", "i2")
    _vale_shape(conn, "i2", over)
    mcap2 = _measure(_build(repos, "US-O", "i2"), "market_cap")
    assert mcap2[4] is None, f"просрок на день ({over}) принят свежим"
    assert mcap2[10] == f"stale_input: shares_outstanding ({over})"


def test_anchor_is_as_of_not_the_newest_fact(env):
    """Якорь — as_of, а не самый свежий факт эмитента. Различающий
    случай: весь отчётный ряд давний, и тег акций в нём — самый свежий.
    По прежнему соглашению (`_eligible_input` считает возраст от
    самого свежего факта) акции здесь «нулевой давности» и капитализация
    строится; по M1 она отказана, потому что отсчёт идёт от as_of."""
    conn, repos = env
    _paper(repos, conn, "US-LATE", "i1")
    _stock(conn, "i1", "shares_outstanding", 270_927_828.0, "2012-12-31")
    _flow(conn, "i1", "revenue", 100.0, "2012-06-30")
    _flow(conn, "i1", "net_income", 10.0, "2012-06-30")
    _stock(conn, "i1", "total_equity", 50.0, "2012-06-30")
    mcap = _measure(_build(repos, "US-LATE", "i1"), "market_cap")
    assert mcap[4] is None, "акции — самый свежий факт, и это не спасает"
    assert mcap[10] == STALE_REFUSAL, mcap[10]


def test_absent_share_count_keeps_its_own_reason(env):
    """Акций нет вовсе — прежний отказ missing_data: shares_outstanding:
    правило давности не имеет права подменять отсутствие просроком."""
    conn, repos = env
    _paper(repos, conn, "US-N", "i1")
    _flow(conn, "i1", "revenue", 100.0, "2025-12-31")
    mcap = _measure(_build(repos, "US-N", "i1"), "market_cap")
    assert mcap[4] is None
    assert mcap[10] == "missing_data: shares_outstanding", mcap[10]


def test_unparseable_share_date_pinned_to_current_behaviour(env):
    """Неразбираемая дата входа — случай, которого в схеме быть не
    должно; `_eligible_input` трактует её как «не отбрасывать». Строка
    крепит это решение, а не оставляет его случайным: менять его можно
    только осознанно."""
    conn, repos = env
    _paper(repos, conn, "US-V", "i1")
    _vale_shape(conn, "i1", "2025-12-31")
    conn.execute("UPDATE fact SET period_end='не дата' WHERE "
                 "canonical_concept='shares_outstanding'")
    mcap = _measure(_build(repos, "US-V", "i1"), "market_cap")
    assert mcap[10] != STALE_REFUSAL
    assert (mcap[4] is not None) == (mcap[10] is None), (mcap[4], mcap[10])


def test_stale_beats_currency_mismatch(env):
    """Просроченные акции ещё и в другой валюте: отказ называет давность,
    а не валюту — у входа, отвергнутого по возрасту, нет права на
    частное, и «смешай валюты» было бы отговоркой. Строка крепит
    порядок проверок в `_valuation_pass`."""
    conn, repos = env
    _paper(repos, conn, "US-BR", "i1")
    _stock(conn, "i1", "shares_outstanding", 270_927_828.0, "2012-12-31")
    conn.execute("UPDATE fact SET currency='BRL' WHERE "
                 "canonical_concept='shares_outstanding'")
    mcap = _measure(_build(repos, "US-BR", "i1"), "market_cap")
    assert mcap[4] is None
    assert mcap[10] == STALE_REFUSAL, mcap[10]


def test_div_yield_is_not_built_on_shares(env):
    """div_yield = dps / price: акций в формуле нет, и правило M1 её не
    задевает — проверка, что отказ не расползается на весь §3."""
    conn, repos = env
    _paper(repos, conn, "US-V", "i1")
    _vale_shape(conn, "i1", "2012-12-31")
    _flow(conn, "i1", "dps_ttm", 0.5, "2025-12-31")
    dy = _measure(_build(repos, "US-V", "i1"), "div_yield")
    assert dy[10] != STALE_REFUSAL, dy[10]
