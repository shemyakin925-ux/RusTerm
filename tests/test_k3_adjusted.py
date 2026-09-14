"""ТЗ-23 K3: корректировка — наша функция (price_adj), вендорский
adjusted — сверка.

- золотой ряд со сплитом и дивидендом: наша серия совпадает с
  ожидаемой ТОЧНО;
- намеренное расхождение с вендором — оба числа в находке, при этом
  ни наш ряд, ни вендорская колонка в хранилище не меняются.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.core.prices import our_adjusted_series, build_events
from rusterm.formulas import dividend_factor, split_factor


def _rows():
    return [
        {"date": "2024-06-03", "close": 100.0, "adjusted": None,
         "currency": "USD"},
        {"date": "2024-06-04", "close": 50.0, "adjusted": None,
         "currency": "USD"},
        {"date": "2024-06-05", "close": 50.0, "adjusted": None,
         "currency": "USD"},
    ]


def _actions():
    return [
        {"ex_date": "2024-06-04", "kind": "split", "factor": 2.0,
         "amount": None, "currency": None, "source": "twelvedata"},
        {"ex_date": "2024-06-05", "kind": "dividend", "factor": None,
         "amount": 1.0, "currency": "USD", "source": "twelvedata"},
    ]


def test_golden_series_with_split_and_dividend_exact():
    """Сплит 1:2 на 06-04 (f=0.5) и дивиденд 1 на 06-05
    (f = 1 - 1/50 = 0.98): наша серия точна до последнего знака."""
    ours, disagreements = our_adjusted_series(_rows(), _actions())
    f_div = dividend_factor(1.0, 50.0)
    expected = [
        ("2024-06-03", 100.0 * split_factor(2.0) * f_div),
        ("2024-06-04", 50.0 * f_div),
        ("2024-06-05", 50.0),
    ]
    assert ours == pytest.approx(expected)
    # вендорский adjusted в этом ряду не записан — расхождений нет
    assert disagreements == []


def test_events_use_close_before_ex_date():
    """Дивидендный коэффициент считается по close последнего дня
    ПЕРЕД ex-date; без цены перед ex-date событие не применяется."""
    events = build_events(_rows(), _actions())
    assert ("2024-06-04", split_factor(2.0)) in events
    assert events[-1] == ("2024-06-05", pytest.approx(0.98))
    lone = [{"date": "2024-06-05", "close": 50.0, "adjusted": None}]
    assert build_events(lone, [_actions()[1]]) == []


def test_deliberate_vendor_mismatch_is_reported_not_resolved(env_stub=None):
    rows = _rows()
    # вендор утверждает adjusted=60 на 06-04 — наша формула даёт 49
    rows[1]["adjusted"] = 60.0
    ours, disagreements = our_adjusted_series(rows, _actions())
    assert len(disagreements) == 1
    date, ours_value, vendor_value = disagreements[0]
    assert date == "2024-06-04"
    assert ours_value == pytest.approx(49.0)
    assert vendor_value == 60.0
    # ничто не переписано: наши close и вендорский adjusted на месте
    assert rows[1]["close"] == 50.0
    assert rows[1]["adjusted"] == 60.0
    assert ours[1] == ("2024-06-04", pytest.approx(49.0))


def test_agreements_and_disagreements_counted(env=None):
    rows = _rows()
    rows[0]["adjusted"] = 49.0   # совпадает с нашей
    rows[1]["adjusted"] = 60.0   # расходится
    ours, disagreements = our_adjusted_series(rows, _actions())
    total_days = len(ours)
    assert total_days == 3
    assert len(disagreements) == 1
    agreed = total_days - len(disagreements)
    assert agreed == 2


# ── ТЗ-31 C1: доказательство изнутри на реальных событиях ──────────────

_DATA = (Path(__file__).resolve().parents[1] / "tests" / "data"
         / "twelvedata")


def _payload(name: str) -> dict:
    return json.loads((_DATA / name).read_text(encoding="utf-8"))


def test_real_split_event_digit_for_digit_against_vendor():
    """Сплит AAPL 4:1 (ex-date 2020-08-31): 499.23 * split_factor(4) =
    124.8075 — число нашей функции совпало с сохранённой вендорской
    close на 2020-08-28 ЦИФРА В ЦИФРУ. Тем самым доказано и что
    формула верна, и что вендорский бесплатный close уже несёт
    сплит-коррекцию (ADR-0020): 2020-08-31 — уже сырой 129.039993."""
    from rusterm.formulas import price_adj
    from rusterm.providers.twelvedata import TwelveDataProvider

    ours = price_adj([("2020-08-28", 499.23)],
                     [("2020-08-31", split_factor(4.0))])
    assert ours == [("2020-08-28", 124.8075)]

    window = TwelveDataProvider.parse_series(
        _payload("time_series_AAPL_split_window.json"))
    closes = {r["date"]: r["close"] for r in window}
    assert closes["2020-08-28"] == 124.8075, \
        "вендор изменил базу ряда? ADR-0020 п.4"
    assert closes["2020-08-31"] == 129.039993


def test_real_dividend_series_digit_for_digit():
    """Вендорский ряд корректируется ТОЛЬКО дивидендами (ADR-0020):
    на 2026-05-08 вручную 293.32001 * (1-0.26/293.32001) *
    (1-0.27/313.32999) — тот же порядок умножения, что в price_adj;
    совпадение цифра в цифру. Вендорский adjusted в строках остаётся
    None (ADR-0019), расхождений нет."""
    from rusterm.providers.twelvedata import TwelveDataProvider
    from rusterm.core.prices import vendor_adjusted_series

    rows = TwelveDataProvider.parse_series(
        _payload("time_series_AAPL_div_window.json"))
    actions, currency, _skipped = TwelveDataProvider.parse_dividends(
        _payload("dividends_AAPL_full.json"))
    assert currency == "USD"
    series, disagreements = vendor_adjusted_series(rows, actions)
    assert disagreements == [], \
        "вендор начал отдавать adjusted — сверка ADR-0014 §4 вернулась"
    by_date = dict(series)
    # оба дивиденда 2026 года — 0.27 (майское повышение 2026, payload);
    # тот же порядок умножения, что в price_adj: факторы, затем close
    hand = 293.32001 * ((1.0 - 0.27 / 293.32001)
                        * (1.0 - 0.27 / 313.32999))
    assert by_date["2026-05-08"] == hand
    # последний день ПЕРЕД ex-date 2026-08-10 несёт его фактор;
    # сам день ex-date уже торгуется по новой базе — своего фактора нет
    hand_last = 313.32999 * (1.0 - 0.27 / 313.32999)
    assert by_date["2026-08-07"] == hand_last
    assert by_date["2026-08-10"] == 308.26001
    # сырой close не тронут: корректировка сообщается рядом, не правкой
    raw = {r["date"]: r["close"] for r in rows}
    assert raw["2026-05-08"] == 293.32001


def test_real_price_rows_keep_adjusted_null_in_store(tmp_path):
    """Булавка на уровне хранилища: строки записанного payload ложатся
    в price с adjusted IS NULL на ВСЕХ строках. Вендор начнёт
    присылать поле — булавка встанет красным, и сверка ADR-0014 §4
    вернётся вместе со входом."""
    import sqlite3

    from rusterm.providers.twelvedata import TwelveDataProvider
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import (Instrument, Issuer, RepoRegistry)

    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-r", "Corp r", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-R", "i-r", None, "common", "active", None))
    rows = TwelveDataProvider.parse_series(
        _payload("time_series_AAPL_1day_trimmed.json"))
    assert len(rows) == 200
    repos.price.put_rows("US-R", "twelvedata", rows)
    nulls, filled = conn.execute(
        """SELECT SUM(adjusted IS NULL), SUM(adjusted IS NOT NULL)
           FROM price WHERE instrument_id='US-R'""").fetchone()
    assert (nulls, filled) == (200, 0), (nulls, filled)
    conn.close()
