"""ТЗ-22 J7: третий экран TUI — отрасль. Строки собирают чистые
функции model.industry_rows/render_industry; тесты гоняются без
импорта curses. Смешение валют рендерится отказом, а не числом;
валюта одновалютной меры стоит рядом с квартилями (J1).
"""
from __future__ import annotations

import sqlite3
import sys

import pytest

from rusterm.tui import model
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)


def test_model_source_does_not_use_curses():
    """Модель собирает экраны чистыми функциями; curses упоминается
    только в app.py (проверка исходника, не процесса)."""
    import inspect
    assert "import curses" not in inspect.getsource(model)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    def member(iid, issuer, cur, revenue):
        repos.instrument.upsert_issuer(Issuer(
            issuer, f"Corp {issuer}", "US", None, None, "us_gaap", cur))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer, None, "common", "active", None))
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, "2024-12-31",
                                       None, "none", "ready")
        fact_id = f"f-{iid}"
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at, canonical_concept,
               source_kind) VALUES (?, ?, 'revenue', '2024-01-01',
               '2024-12-31', 'duration', ?, ?, ?, 'as_reported',
               'extracted', 's', '{}', 'companyfacts.v1', 'ok', 0,
               'revenue', 'provider')""",
            (fact_id, issuer, str(revenue), cur, cur))
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id=f"m-{iid}", snapshot_id=f"s-{iid}",
                 scope="issuer", scope_ref=issuer, concept="revenue",
                 value=str(revenue), unit=cur,
                 period_start="2024-01-01", period_end="2024-12-31",
                 formula_id="revenue", method_version="v1",
                 null_reason=None, peer_set_version=None),
            [{"fact_id": fact_id, "peer_measure_id": None,
              "role": "input"}])

    peers = PeerSetRepo(conn)
    # одновалютный сектор от восьми участников: квартили с валютой
    peers.create_peer_set("tankers", "industry", "tankers")
    peers.add_version("tv1", "tankers", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    for i in range(8):
        iid = f"US-{chr(ord('A') + i)}"
        peers.add_member("tv1", iid, None)
        member(iid, f"i{i}", "USD", 100 + i)

    # смешанный сектор: 4 USD + 4 KRW
    peers.create_peer_set("mixed", "industry", "mixed")
    peers.add_version("mv1", "mixed", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    for i in range(4):
        iid = f"KR-{chr(ord('A') + i)}"
        peers.add_member("mv1", iid, None)
        member(iid, f"k{i}", "KRW", 9000 + i)
    for i in range(4):
        iid = f"US-M{i}"  # без коллизий с участниками tankers
        peers.add_member("mv1", iid, None)
        member(iid, f"u{i}", "USD", 100 + i)
    yield conn, repos
    conn.close()


def test_single_currency_sector_shows_quartiles_with_currency(env):
    conn, repos = env
    screen = model.industry_rows(repos, "tankers", "2025-01-01")
    assert screen["version"] == 1
    assert len(screen["members"]) == 8
    revenue = next(r for r in screen["rows"]
                   if r["concept"] == "revenue")
    assert revenue["null_reason"] is None
    assert revenue["currency"] == "USD"
    assert revenue["n"] == 8 and revenue["median"] is not None
    lines = model.render_industry(screen)
    assert any("revenue" in line and "USD" in line for line in lines)


def test_mixed_currency_sector_renders_mismatch_not_number(env):
    conn, repos = env
    screen = model.industry_rows(repos, "mixed", "2025-01-01")
    revenue = next(r for r in screen["rows"]
                   if r["concept"] == "revenue")
    assert revenue["null_reason"] and \
        revenue["null_reason"].startswith("currency_mismatch")
    assert revenue["p25"] is None and revenue["median"] is None
    lines = model.render_industry(screen)
    mismatch_lines = [line for line in lines if "currency_mismatch" in line]
    assert mismatch_lines, lines
    # в строке отказа нет выдуманных квартилей
    assert "/ " not in mismatch_lines[0]
    # ratio-меры (net_margin не собран — фактов нет) показывают причину
    net = next(r for r in screen["rows"] if r["concept"] == "net_margin")
    assert net["null_reason"]


def test_sector_without_version_at_date_renders_refusal(env):
    conn, repos = env
    screen = model.industry_rows(repos, "tankers", "2020-01-01")
    assert screen["version"] is None
    assert model.render_industry(screen) == [
        "Сектор tankers: нет версии на 2020-01-01"]
