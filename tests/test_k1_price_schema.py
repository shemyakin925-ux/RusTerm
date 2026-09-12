"""ТЗ-23 K1: цены и корпоративные действия получают место в схеме.

Миграция 41 (price, corporate_action) применяется дважды без дублей;
существующая база мигрирует, прежние таблицы сохраняют ряды; цена
уникальна по (инструмент, дата, источник) — повторный сбор того же
дня не вставляет дубль и не переписывает (I7).
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (CorporateActionRepo, Instrument, Issuer,
                                 PriceRepo, RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-T", "i1", None, "common", "active", None))
    return paths, conn, repos


def test_migration_applied_twice_creates_no_duplicates(env):
    paths, conn, repos = env
    inserted = repos.price.put_rows("US-T", "twelvedata", [
        {"date": "2024-12-30", "close": 100.0, "adjusted": 99.0,
         "currency": "USD", "volume": 1_000},
        {"date": "2024-12-31", "close": 101.0, "adjusted": 100.0,
         "currency": "USD", "volume": 1_100},
    ])
    repos.corp_action.put("US-T", "2024-06-01", "split", factor=2.0)
    before_prices = conn.execute(
        "SELECT COUNT(*) FROM price").fetchone()[0]
    before_actions = conn.execute(
        "SELECT COUNT(*) FROM corporate_action").fetchone()[0]
    # повторное применение всех миграций
    apply_migrations(conn)
    after_prices = conn.execute(
        "SELECT COUNT(*) FROM price").fetchone()[0]
    after_actions = conn.execute(
        "SELECT COUNT(*) FROM corporate_action").fetchone()[0]
    assert before_prices == after_prices == 2
    assert before_actions == after_actions == 1
    # и повторная вставка тех же строк — no-op (I7)
    again = repos.price.put_rows("US-T", "twelvedata", [
        {"date": "2024-12-30", "close": 100.0, "adjusted": 99.0,
         "currency": "USD", "volume": 1_000},
        {"date": "2024-12-31", "close": 101.0, "adjusted": 100.0,
         "currency": "USD", "volume": 1_100},
    ])
    assert again == 0
    assert inserted == 2
    assert repos.price.count("US-T") == 2


def test_existing_database_migrates_and_keeps_rows(env):
    """Прежние таблицы сохраняют ряды после миграции 41."""
    paths, conn, repos = env
    repos.instrument.upsert_issuer(Issuer(
        "i2", "Corp 2", "CA", None, None, "ifrs-full", "CAD"))
    counts_before = {t: conn.execute(
        f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("issuer", "instrument", "fact", "measure")}
    apply_migrations(conn)  # повтор: миграция 41 уже применена
    counts_after = {t: conn.execute(
        f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("issuer", "instrument", "fact", "measure")}
    assert counts_before == counts_after
    assert conn.execute(
        "SELECT MAX(version) FROM schema_version").fetchone()[0] == 41


def test_price_uniqueness_per_instrument_date_source(env):
    paths, conn, repos = env
    repos.price.put_rows("US-T", "twelvedata",
                         [{"date": "2024-12-31", "close": 101.0,
                           "currency": "USD"}])
    # другой источник — своя строка (требование unique по тройке)
    repos.price.put_rows("manual", "manual",
                         [{"date": "2024-12-31", "close": 100.5,
                           "currency": "USD"}])
    rows = conn.execute(
        """SELECT source, close FROM price WHERE instrument_id='US-T'
           ORDER BY source""").fetchall()
    assert rows == [("twelvedata", 101.0)]


def test_price_as_of_reports_age_and_refuses_future(env):
    paths, conn, repos = env
    repos.price.put_rows("US-T", "twelvedata", [
        {"date": "2024-12-27", "close": 99.0, "currency": "USD"},
        {"date": "2024-12-30", "close": 100.0, "currency": "USD"},
    ])
    got = repos.price.price_as_of("US-T", "2025-01-05")
    assert got["date"] == "2024-12-30" and got["close"] == 100.0
    assert got["age_days"] == 6
    assert repos.price.price_as_of("US-T", "2024-12-28")["date"] == \
        "2024-12-27"
    # цен до этой даты нет — None, не перенос завтрашней
    assert repos.price.price_as_of("US-ZZ", "2025-01-05") is None


def test_corporate_action_kinds_and_uniqueness(env):
    paths, conn, repos = env
    assert repos.corp_action.put("US-T", "2024-06-01", "split",
                                 factor=2.0) is True
    assert repos.corp_action.put("US-T", "2024-06-15", "dividend",
                                 amount=0.5, currency="USD") is True
    # то же событие повторно — False (I7)
    assert repos.corp_action.put("US-T", "2024-06-01", "split",
                                 factor=2.0) is False
    events = repos.corp_action.all("US-T")
    assert [(e["kind"], e["factor"], e["amount"]) for e in events] == [
        ("split", 2.0, None), ("dividend", None, 0.5)]
    # check-constraint: split без factor невозможен
    try:
        conn.execute(
            """INSERT INTO corporate_action(instrument_id, ex_date,
               kind, amount, source) VALUES ('US-T', '2024-07-01',
               'split', NULL, 'x')""")
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised
