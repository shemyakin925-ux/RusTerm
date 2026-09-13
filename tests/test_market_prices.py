"""ТЗ-30 (ТЗ-23 K2/K7): котировки перестают быть фикстурами.

B1: вендорский потолок объявлен и в реестре, и в рабочем лимите
модуля; запрос сверх потолка — отказ значением budget_exceeded, без
ожидания. B2: живая серия записывается, повтор — ноль новых строк и
ноль запросов (кеш по каноническому URL без ключа); золотой тест
разбирает записанный обрезанный payload офлайн. B3 (K7): отказ
вендора останавливает ценовой путь с именованной причиной, фундамент
живёт.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import rusterm.providers as providers
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    Listing,
    RepoRegistry,
)
from rusterm.providers import twelvedata as td
from rusterm.providers.base import ProviderError
from rusterm.providers.budget import (
    BudgetExceeded,
    ConfigError,
    NetworkGate,
    RequestGate,
)

FAKE_UA = "Synthetic Test t.invalid"


def _payload_transport(payload: dict, status: int = 200):
    body = json.dumps(payload).encode("utf-8")

    def transport(url, headers):
        return status, body, {}

    return transport


def _no_key_provider():
    return td.TwelveDataProvider(
        gate=RequestGate(gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA})),
        api_key="TESTONLY-key")


def test_twelvedata_declares_vendor_free_ceiling():
    """B1: 800/день и не быстрее 8/мин — и в реестре, и в модуле."""
    limit = providers.host_limit("twelvedata")
    assert limit is not None
    assert limit.host == "api.twelvedata.com"
    assert limit.nightly_max == 800, limit.nightly_max
    assert limit.per_second <= 8.0 / 60.0, limit.per_second
    # модуль и реестр говорят одно и то же — иначе doctor врёт
    assert td._LIMIT.nightly_max == limit.nightly_max
    assert td._LIMIT.per_second == limit.per_second
    assert td._LIMIT.host == limit.host
    assert "twelvedata" in providers.available()


def test_request_past_ceiling_is_refused_by_value_never_a_wait():
    """B1: сверх потолка — budget_exceeded значением; лимитер не
    трогается, ожидания нет."""
    gate = RequestGate(gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))
    provider = td.TwelveDataProvider(gate=gate, api_key="TESTONLY-key")
    budget, limiter, _declared = gate._pool_for(provider.limit)
    budget.max_requests = 0
    outcome = provider.time_series("AAPL")
    assert isinstance(outcome, BudgetExceeded)
    assert outcome.reason == "budget_exceeded"
    assert limiter.rate_limited == 0, "отказ дошёл до ожидания"


def test_no_key_is_config_error_value():
    """K2/N2: ключа нет — ConfigError-значение, сеть не трогается."""
    provider = td.TwelveDataProvider.from_env(
        RequestGate(gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA})),
        environ={"RUSTERM_TWELVEDATA_KEY": ""})
    assert isinstance(provider, ConfigError)
    assert provider.reason == "twelvedata_key_unset"
    assert "TESTONLY" not in repr(provider)


# ── B2: живая серия, записанная и воспроизводимая ──────────────────────

_TRIMMED = (Path(__file__).resolve().parents[1] / "tests" / "data"
            / "twelvedata" / "time_series_AAPL_1day_trimmed.json")


def _seed_instrument(repos, instrument_id="US-X", issuer_id="i-x",
                     ticker="X"):
    repos.instrument.upsert_issuer(
        Issuer(issuer_id, f"Corp {issuer_id}", "US", None, None,
               "us_gaap", "USD"))
    repos.instrument.upsert_instrument(
        Instrument(instrument_id, issuer_id, None, "common", "active",
                   None))
    repos.instrument.upsert_listing(
        Listing(f"l-{instrument_id}", instrument_id, "US", "USD", 1,
                None, None))
    repos.instrument.add_ticker_history(
        f"l-{instrument_id}", ticker, "2020-01-01", None, None, None)


def _price_env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    return conn, repos


def test_second_collection_same_day_is_zero_requests_zero_rows(
        tmp_path, capsys):
    """B2/K2: первый сбор — один запрос, строки записаны; повторный
    сбор того же диапазона — ноль запросов (кеш по каноническому URL
    без ключа) и ноль новых строк (I7)."""
    from rusterm.cli import _ingest_twelvedata_prices

    conn, repos = _price_env(tmp_path)
    _seed_instrument(repos, ticker="AAPL")
    payload = json.loads(_TRIMMED.read_text(encoding="utf-8"))
    calls = []

    def counting_transport(url, headers):
        calls.append(url)
        return 200, json.dumps(payload).encode("utf-8"), {}

    provider = td.TwelveDataProvider(
        gate=RequestGate(gate=NetworkGate(environ={
            "RUSTERM_SEC_UA": FAKE_UA})),
        api_key="TESTONLY-key", transport=counting_transport)

    code = _ingest_twelvedata_prices(repos, "US-X", "2026-09-11",
                                     provider=provider)
    assert code == 0
    assert len(calls) == 1, len(calls)
    n_rows = conn.execute(
        "SELECT COUNT(*) FROM price WHERE instrument_id='US-X'"
    ).fetchone()[0]
    assert n_rows == 200  # обрезанный payload: 100 старых + 100 новых

    code = _ingest_twelvedata_prices(repos, "US-X", "2026-09-11",
                                     provider=provider)
    assert code == 0
    assert len(calls) == 1, "повторный сбор сходил в сеть"
    n_after = conn.execute(
        "SELECT COUNT(*) FROM price WHERE instrument_id='US-X'"
    ).fetchone()[0]
    assert n_after == n_rows, "повторный сбор записал дубли (I7)"
    conn.close()


def test_golden_replay_parses_recorded_payload_offline():
    """B2/K2: золотой тест — записанный обрезанный payload разбирается
    офлайн, названные цены разрешаются в него; вендорский бесплатный
    тариф adjusted_close не отдаёт — это закреплено как факт."""
    from rusterm.providers.twelvedata import TwelveDataProvider

    payload = json.loads(_TRIMMED.read_text(encoding="utf-8"))
    rows = TwelveDataProvider.parse_series(payload)
    assert rows, "payload пуст"
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates), "строки не по возрастанию даты"
    newest = rows[-1]
    assert newest == {"date": "2026-09-11", "close": 332.26999,
                      "currency": "USD", "volume": 50659000}
    oldest = rows[0]
    assert oldest["date"] == "2006-10-25"
    assert oldest["close"] == 2.91714
    assert all("adjusted" not in r for r in rows), \
        "вендор начал отдавать adjusted_close — обнови закрепление"
    assert all(r["currency"] == "USD" for r in rows)


# ── B3 (K7): отказ вендора — именованная причина, фундамент живёт ─────

def test_vendor_failures_stop_price_path_with_named_reasons():
    """K7: 403, 429 и тайм-аут — значения с именованной причиной,
    цена не подделывается, исключение наружу не выходит."""
    gate = RequestGate(gate=NetworkGate(environ={
        "RUSTERM_SEC_UA": FAKE_UA}))

    def _provider(transport):
        return td.TwelveDataProvider(gate=gate, api_key="TESTONLY-key",
                                     transport=transport)

    out403 = _provider(_payload_transport({}, status=403)).time_series(
        "AAPL")
    assert isinstance(out403, ProviderError)
    assert out403.reason == "source_unreachable:http_403", out403.reason

    out429 = _provider(_payload_transport({}, status=429)).time_series(
        "AAPL")
    assert isinstance(out429, ProviderError)
    assert out429.reason == "vendor_rate_limited", out429.reason

    def _timeout(url, headers):
        raise TimeoutError("scratch")

    out_timeout = _provider(_timeout).time_series("AAPL")
    assert isinstance(out_timeout, ProviderError)
    assert out_timeout.reason == "source_unreachable:transport", \
        out_timeout.reason


def test_degraded_snapshot_keeps_fundamentals_names_price_reason(
        tmp_path):
    """K7: вендор недоступен — ценовых строк нет; снапшот строится,
    оценочные меры читают причину (не вчерашнее число), фундаментал
    тех же мер не теряет значений."""
    conn, repos = _price_env(tmp_path)
    _seed_instrument(repos, "US-P", "i-p")
    # фундаментальные значения есть, цен нет — вендор не ответил
    for n, (concept, value) in enumerate(
            (("revenue", "100"), ("net_income", "10"))):
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
               period_end, period_type, value, unit, currency, basis,
               origin, source_ref, locator, parser_version, status,
               ingested_at, canonical_concept, source_kind)
               VALUES (?, 'i-p', ?, '2024-01-01',
               '2024-12-31', 'duration', ?, 'USD', 'USD',
               'as_reported', 'extracted', 's', '{}', 'companyfacts.v1',
               'ok', 0, ?, 'provider')""",
            (f"f-p-{concept}", concept, value, concept))
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build("US-P", "i-p", "2026-09-11")
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-P"))
    margin = next(m for m in rows if m[3] == "net_margin")
    assert margin[4] is not None, "фундаментал потерял значение"
    mcap = next(m for m in rows if m[3] == "market_cap")
    assert mcap[4] is None
    assert mcap[10] == "missing_data: price_close", mcap[10]
    conn.close()


# ── B4: кадентность на живых данных ────────────────────────────────────

def test_cadence_incomplete_backfills_then_complete_polls(tmp_path):
    """B4 (ADR-0014 §2): дыра в истории — backfill (бюджет первым);
    после записи реальных дат из живого payload инструмент complete и
    опрашивается раз в ~10 дней: симулированный месяц — один опрос."""
    from datetime import date, timedelta

    from rusterm.core.cadence import plan_pass, run_pass

    conn, repos = _price_env(tmp_path)
    _seed_instrument(repos, "US-AAPL", "i-aapl", "AAPL")
    payload = json.loads(_TRIMMED.read_text(encoding="utf-8"))
    rows = td.TwelveDataProvider.parse_series(payload)
    # свежий непрерывный кусок живого ряда: последние 100 дней
    fresh = rows[-100:]

    # 1) история с дырой (20 торговых дней вынуты из середины) —
    #    план ведёт backfill
    middle = len(fresh) // 2
    holed = fresh[:middle] + fresh[middle + 20:]
    repos.price.put_rows("US-AAPL", "twelvedata", holed)
    plan = plan_pass(repos, "2026-09-13")
    entry = next(e for e in plan if e.instrument_id == "US-AAPL")
    assert entry.state == "incomplete", (entry.state, entry.reason)
    assert entry.action == "backfill"
    assert entry.reason.startswith("gap:"), entry.reason

    # 2) backfill вставляет только недостающее (I7: дубли не пишутся)
    inserted = repos.price.put_rows("US-AAPL", "twelvedata", fresh)
    assert inserted == 20, inserted

    # 3) теперь complete, опрос не из-за чего — данные свежи
    plan = plan_pass(repos, "2026-09-13")
    entry = next(e for e in plan if e.instrument_id == "US-AAPL")
    assert entry.state == "complete", (entry.state, entry.reason)
    assert entry.action == "skip" and entry.reason.startswith("polled:")

    # 4) симулированный месяц в окне сомкнутости (по 09-24: дальше
    #    живая история 09-11 честно протухает и ряд идёт в backfill):
    #    полный опрашивается по расписанию — один опрос за месяц
    polls = []
    day = date(2026, 9, 1)
    while day <= date(2026, 9, 24):
        as_of = day.isoformat()
        result = run_pass(repos, as_of,
                          lambda e: polls.append((as_of, e.instrument_id)))
        day += timedelta(days=1)
    assert polls == [("2026-09-21", "US-AAPL")], polls
    conn.close()
