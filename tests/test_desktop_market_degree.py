"""ТЗ-60 E4: степень канала — «сырьё» / «факты» / «меры» — вычисляется
из того, что канал произвёл в этой базе, а не записана рукой: рынок без
единого факта не может показать «факты». Слова одни у `rusterm markets`
(TSV и --json) и строки рынков окна.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3  # noqa: E402

import pytest  # noqa: E402

from rusterm.cli import main as cli_main  # noqa: E402
from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer,  # noqa: E402
                                 Listing, RepoRegistry)


def _company(repos, ticker: str, market_prefix: str, exchange: str):
    repos.instrument.upsert_issuer(Issuer(
        f"i-{ticker}", f"Corp {ticker}", market_prefix, None, None,
        "ifrs-full", "AUD"))
    iid = f"{market_prefix}-{ticker}"
    repos.instrument.upsert_instrument(Instrument(
        iid, f"i-{ticker}", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        f"l-{iid}", iid, exchange, "AUD", 1, None, None))
    repos.instrument.add_ticker_history(
        f"l-{iid}", ticker, "2000-01-01", None, None, None)
    return iid


def _degrees_json(root, capsys) -> dict:
    assert cli_main(["--root", str(root), "markets", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    return {row["code"]: row["degree"] for row in payload["markets"]}


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    yield RepoRegistry(conn, paths), paths
    conn.close()


def test_markets_without_catalog_says_dash_and_creates_nothing(
        tmp_path, capsys):
    """B35: нет каталога — «—» по всем рынкам с каналом; KR без ключа —
    «нет ключа» (ТЗ-61 F4) даже без каталога. Каталог не создан."""
    missing = tmp_path / "nope"
    degrees = _degrees_json(missing, capsys)
    assert degrees["KR"] == "нет ключа"
    del degrees["KR"]
    assert set(degrees.values()) == {"—"}
    assert not missing.exists()


def test_empty_catalog_has_no_degree(catalog, tmp_path, capsys):
    repos, _ = catalog
    assert repos.instrument.channel_degrees() == {}
    degrees = _degrees_json(tmp_path / "app", capsys)
    assert degrees["KR"] == "нет ключа"
    del degrees["KR"]
    assert set(degrees.values()) == {"—"}


def test_degree_climbs_with_channel_production(catalog):
    """AU: канал asx дал сырьё — «сырьё»; появился факт — «факты»;
    построена мера — «меры». US ничего не производил — «—» всё время."""
    repos, _ = catalog
    iid = _company(repos, "BKL", "AU", "ASX")
    degrees = repos.instrument.channel_degrees()
    assert degrees.get("AU", "—") == "—"
    assert degrees.get("US", "—") == "—"

    stored = repos.raw.put(b"announcement index bytes", provider="asx",
                           url="https://asx.example/bkl")
    degrees = repos.instrument.channel_degrees()
    assert degrees.get("AU") == "сырьё"
    assert degrees.get("US", "—") == "—"

    repos.fact.insert_fact(
        "f-au-1", "i-BKL", None, "Revenue", "2024-01-01", "2024-12-31",
        "duration", "100", "AUD", "AUD", "as_reported", "extracted",
        stored.sha256, {"page": 1}, "t60-test")
    degrees = repos.instrument.channel_degrees()
    assert degrees.get("AU") == "факты"

    repos.snapshot.create_snapshot("s-au-1", iid, 1, "2025-01-01",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-au-1", "s-au-1", "issuer", "i-BKL", "revenues_total",
        "100", "AUD", "2024-01-01", "2024-12-31", None, "t60-test",
        None, None)
    degrees = repos.instrument.channel_degrees()
    assert degrees.get("AU") == "меры"


def test_manual_fact_is_not_the_channel_production(catalog):
    """Факт ручного импорта — работа пользователя, не канала: канал
    без своего сырья не поднимается до «фактов»."""
    repos, _ = catalog
    _company(repos, "BKL", "AU", "ASX")
    stored = repos.raw.put(b"typed by hand", provider="manual",
                           url="file://manual")
    repos.fact.insert_fact(
        "f-au-2", "i-BKL", None, "Revenue", "2024-01-01", "2024-12-31",
        "duration", "100", "AUD", "AUD", "as_reported", "manual",
        stored.sha256, {"page": 1}, "t60-test")
    degrees = repos.instrument.channel_degrees()
    assert degrees.get("AU", "—") == "—"


def test_shared_provider_lights_its_markets_with_raw(catalog):
    """US/CA/OTC сидят на одном канале edgar: его сырьё честно
    показывает «сырьё» на всех трёх, хоть инструменты только у US."""
    repos, _ = catalog
    _company(repos, "AAA", "US", "NASDAQ")
    repos.raw.put(b"edgar bytes", provider="edgar",
                  url="https://data.sec.gov/x")
    degrees = repos.instrument.channel_degrees()
    assert degrees["US"] == degrees["CA"] == degrees["OTC"] == "сырьё"
    assert degrees.get("BR", "—") == "—"


def test_cli_and_desktop_show_the_same_words(catalog, tmp_path, capsys):
    repos, _ = catalog
    _company(repos, "BKL", "AU", "ASX")
    repos.raw.put(b"announcement index bytes", provider="asx",
                  url="https://asx.example/bkl")
    filled = _degrees_json(tmp_path / "app", capsys)
    computed = desktop_data.channel_degrees(repos)
    assert filled["AU"] == computed["AU"] == "сырьё"
    for code, degree in filled.items():
        assert degree == computed.get(code, "—")


def test_window_names_degree_in_same_words(catalog):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel
    from rusterm.desktop import window as desktop_window
    repos, paths = catalog
    iid = _company(repos, "BKL", "AU", "ASX")
    repos.raw.put(b"announcement index bytes", provider="asx",
                  url="https://asx.example/bkl")
    repos.watchlist.create_watchlist("wl-main", "main", None, None)
    vid = repos.watchlist.new_version("wlv-1", "wl-main", 1, "seed", None)
    repos.watchlist.add_member(vid, iid, None)

    QApplication.instance() or QApplication([])
    window = desktop_window._build_window(repos, paths, "wl-main")
    label = window.findChild(QLabel, "markets_line")
    assert label is not None
    assert "AU — сырьё" in label.text()
    assert "меры" not in label.text()
    window.close()
