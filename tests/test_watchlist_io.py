"""Тесты импорта/экспорта watchlist (TASK-7 T11).

Контрольный случай ТЗ: импорт четырёх строк (1 хорошая, 1 неизвестная,
1 неоднозначная, 1 уже в списке) добавляет ровно одного участника,
остальные три попадают в отчёт по своим категориям. Молчаливых
пропусков нет.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile

from rusterm.core.watchlist_io import (
    EXPORT_COLUMNS,
    export_csv,
    export_json,
    import_rows,
    parse_import,
)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    WatchlistRepo,
)

AS_OF = "2026-09-08"


def _setup():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    instruments = InstrumentRepo(conn)
    watchlist = WatchlistRepo(conn)
    instruments.upsert_issuer(Issuer(
        "i1", "N", "US", None, None, "us_gaap", "USD"))

    def add_instrument(instrument_id, isin=None):
        instruments.upsert_instrument(Instrument(
            instrument_id, "i1", isin, "common", "active", None))

    def add_listing(instrument_id, listing_id, exchange, ticker):
        instruments.upsert_listing(type(
            "L", (), {"listing_id": listing_id,
                      "instrument_id": instrument_id,
                      "exchange": exchange, "currency": "USD",
                      "is_primary": 1, "first_trade_date": None,
                      "last_trade_date": None})())
        instruments.add_ticker_history(listing_id, ticker, "2020-01-01",
                                       None, None, None)

    add_instrument("ins_aapl", "US0378331005")
    add_listing("ins_aapl", "l1", "US", "AAPL")
    add_instrument("ins_msft", "US5949181045")
    add_listing("ins_msft", "l2", "US", "MSFT")
    add_instrument("ins_dup1")
    add_listing("ins_dup1", "l3", "US", "DUPL")
    add_instrument("ins_dup2")
    add_listing("ins_dup2", "l4", "US", "DUPL")

    watchlist.create_watchlist("w1", "Наблюдение", None, None)
    watchlist.new_version("wv1", "w1", 1, "create", None)
    watchlist.add_member("wv1", "ins_aapl", None)   # уже в списке
    return tmpdir, conn, instruments, watchlist


def _four_rows():
    """1 хорошая (MSFT), 1 неизвестная (NOPE), 1 неоднозначная (DUPL),
    1 уже в списке (AAPL)."""
    return [
        {"ticker": "MSFT", "market": "US", "note": "новая"},
        {"ticker": "NOPE", "market": "US", "note": ""},
        {"ticker": "DUPL", "market": "US", "note": ""},
        {"ticker": "AAPL", "market": "US", "note": ""},
    ]


def test_four_row_import_adds_exactly_one_and_reports_rest():
    tmpdir, conn, instruments, watchlist = _setup()
    try:
        report = import_rows(watchlist, instruments, "w1", _four_rows(),
                             AS_OF)
        assert [a["ticker"] for a in report["added"]] == ["MSFT"]
        assert [r["ticker"] for r in report["not_found"]] == ["NOPE"]
        assert report["not_found"][0]["reason"]
        assert [a["ticker"] for a in report["ambiguous"]] == ["DUPL"]
        assert sorted(report["ambiguous"][0]["candidates"]) == \
            ["ins_dup1", "ins_dup2"]
        assert [a["ticker"] for a in report["already_present"]] == ["AAPL"]

        # добавлен ровно один участник; состав менялся новой версией
        current = watchlist.current_version("w1")
        assert current["version"] == 2
        assert current["action"] == "import"
        members = sorted(m["instrument_id"]
                         for m in watchlist.members("w1"))
        assert members == ["ins_aapl", "ins_msft"]
        # версия 1 не переписана
        assert [m["instrument_id"]
                for m in watchlist.members("w1", version=1)] == ["ins_aapl"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_import_without_additions_creates_no_version():
    tmpdir, conn, instruments, watchlist = _setup()
    try:
        report = import_rows(watchlist, instruments, "w1", _four_rows(),
                             AS_OF)
        report2 = import_rows(watchlist, instruments, "w1", _four_rows(),
                              AS_OF)
        # второй импорт: MSFT уже в списке — добавлять нечего, версии нет
        assert report2["added"] == []
        assert [a["ticker"] for a in report2["already_present"]] == \
            ["MSFT", "AAPL"]
        assert watchlist.current_version("w1")["version"] == 2
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_export_is_ticker_addressed_with_exact_columns():
    tmpdir, conn, instruments, watchlist = _setup()
    try:
        import_rows(watchlist, instruments, "w1", _four_rows(), AS_OF)
        csv_text, note = export_csv(watchlist, instruments, "w1", AS_OF)
        assert "industry пуст" in note
        header = csv_text.splitlines()[0]
        assert header == ",".join(EXPORT_COLUMNS)
        rows = parse_import(csv_text, "csv")
        by_ticker = {r["ticker"]: r for r in rows}
        assert by_ticker["AAPL"]["isin"] == "US0378331005"
        assert by_ticker["AAPL"]["market"] == "US"
        assert by_ticker["MSFT"]["note"] == "новая"
        assert all(r["industry"] == "" for r in rows)

        # JSON-экспорт — те же данные плюс явная заметка о пустой колонке
        payload = json.loads(
            export_json(watchlist, instruments, "w1", AS_OF)[0])
        assert {r["ticker"] for r in payload["rows"]} == \
            {r["ticker"] for r in rows}
        assert "industry пуст" in payload["note"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
