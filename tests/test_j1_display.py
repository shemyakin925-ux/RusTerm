"""ТЗ-22 J1: валюта доезжает до пользователя — экспорт несёт её на
каждой абсолютной мере, coverage считает currency_mismatch отдельно от
missing_data, карточка TUI показывает валюту рядом с числом.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import rusterm.cli as cli
import rusterm.providers.edgar as edgar_module
from rusterm.tui.model import card_rows, render_card

_TADTAS = {"0": {"cik_str": 320193, "ticker": "AAPL",
                 "title": "Apple Inc."}}
_EXCHANGES = {"fields": ["cik", "name", "ticker", "exchange"],
              "data": [[320193, "Apple Inc.", "AAPL", "NASDAQ"]]}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test j1.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    from pathlib import Path
    data = Path(__file__).resolve().parent / "data"

    def transport(url, headers):
        if "company_tickers.json" in url:
            return 200, json.dumps(_TADTAS).encode(), {}
        if "company_tickers_exchange.json" in url:
            return 200, json.dumps(_EXCHANGES).encode(), {}
        if "CIK0000320193" in url:  # CIK%010d, как в URL companyfacts
            return 200, (data / "edgar"
                         / "companyfacts_m3_AAPL.json").read_bytes(), {}
        return 404, b"{}", {}

    class _Patched(edgar_module.EdgarProvider):
        def __init__(self, *a, **kw):
            kw.setdefault("transport", transport)
            super().__init__(*a, **kw)

    monkeypatch.setattr(edgar_module, "EdgarProvider", _Patched)
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    return root, tmp_path / "app" / "rusterm.db"


def test_export_carries_currency_on_absolute_measures(app, capsys):
    """Done-when J1: export --format json несёт валюту на каждой
    абсолютной мере со значением; ratio-меры валюты не несут."""
    root, db = app
    assert cli.main(["--root", str(root), "add", "--ticker", "AAPL",
                     "--market", "US"]) == 0
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "US-AAPL", "--source", "edgar"]) == 0
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     "US-AAPL"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "export", "--instrument",
                     "US-AAPL", "--format", "json"]) == 0
    export = json.loads(capsys.readouterr().out)
    from rusterm.core.peers import currency_bound
    absolute_valued = [m for m in export["measures"]
                       if m["value"] is not None
                       and currency_bound(m["concept"])]
    assert absolute_valued, "в снапшоте AAPL есть абсолютные меры"
    for m in absolute_valued:
        assert m["currency"] == "USD", (m["concept"], m["currency"])
    ratios = [m for m in export["measures"]
              if not currency_bound(m["concept"])]
    assert all(m.get("currency") is None for m in ratios)


def test_coverage_counts_currency_mismatch_separately(app, capsys):
    """coverage различает причины: currency_mismatch считается отдельно
    от missing_data (разные проблемы — разные починки)."""
    root, db = app
    _build_mixed_snapshot(str(root))
    capsys.readouterr()
    assert cli.main(["--root", str(root), "coverage", "--instrument",
                     "US-A", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    counts = payload["measure_reason_counts"]
    assert counts.get("currency_mismatch", 0) >= 1
    assert counts.get("missing_data", 0) >= 1
    # текстовый режим вывод не менял: различение причин живёт в json
    assert cli.main(["--root", str(root), "coverage", "--instrument",
                     "US-A"]) == 0
    out = capsys.readouterr().out
    assert "причины пустых мер" not in out


def test_tui_card_shows_currency_beside_absolute_measures(app):
    root, db = app
    _build_valued_usd_snapshot(str(root))
    conn = sqlite3.connect(str(db))
    from rusterm.store.repos import RepoRegistry
    from rusterm.store.paths import AppPaths
    repos = RepoRegistry(conn, AppPaths.from_root(root))
    card = card_rows(repos, "US-V")
    conn.close()
    ebitda = next(m for m in card["measures"]
                  if m["concept"] == "ebitda" and m["value"] is not None)
    assert ebitda["currency"] == "USD"
    lines = render_card(card)
    assert any("ebitda" in line and "[USD]" in line for line in lines)


# ── карманные сборки снапшотов (факты и меры — руками, сети нет) ────

def _build_mixed_snapshot(root: str) -> None:
    """Шесть эмитентов (3 USD + 3 KRW), смешанный peer set, сборка
    снапшота US-A: перцентиль revenue получает currency_mismatch,
    недосчитанные меры — missing_data. Паттерн ТЗ-21 H3."""
    from rusterm.core.snapshot import SnapshotBuilder
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                     RepoRegistry)

    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    currencies = ["USD"] * 3 + ["KRW"] * 3
    ids = [f"{('US' if c == 'USD' else 'KR')}-{chr(ord('A') + i)}"
           for i, c in enumerate(currencies)]
    peer_measures = []
    for i, (iid, cur) in enumerate(zip(ids, currencies)):
        repos.instrument.upsert_issuer(Issuer(
            f"i{i}", f"Corp {i}", "US", None, None, "us_gaap", cur))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i{i}", None, "common", "active", None))
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at, canonical_concept,
               source_kind) VALUES (?, ?, 'revenue', '2024-01-01',
               '2024-12-31', 'duration', ?, 'USD', ?, 'as_reported',
               'extracted', 's', '{}', 'companyfacts.v1', 'ok', 0,
               'revenue', 'provider')""",
            (f"f{i}", f"i{i}", str(100 + 10 * i), cur))
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at, canonical_concept,
               source_kind) VALUES (?, ?, 'net_income', '2024-01-01',
               '2024-12-31', 'duration', ?, 'USD', ?, 'as_reported',
               'extracted', 's', '{}', 'companyfacts.v1', 'ok', 0,
               'net_income', 'provider')""",
            (f"n{i}", f"i{i}", str(20 + i), cur))
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, "2024-12-31",
                                       None, "none", "ready")
        repos.snapshot.add_block(f"s-{iid}", "fundamentals", "ready",
                                 None)
        for mid, concept, value, fc in (
                (f"m{i}r", "revenue", str(100 + 10 * i), "revenue"),
                (f"m{i}n", "net_margin", f"0.{2 + i}", "net_income")):
            repos.snapshot.insert_measure_with_lineage(
                dict(measure_id=mid, snapshot_id=f"s-{iid}",
                     scope="issuer", scope_ref=f"i{i}", concept=concept,
                     value=value, unit="USD",
                     period_start="2024-01-01", period_end="2024-12-31",
                     formula_id=concept, method_version="v1",
                     null_reason=None, peer_set_version=None),
                [{"fact_id": f"f{i}" if fc == "revenue" else f"n{i}",
                  "peer_measure_id": None, "role": "input"}])
        peer_measures.append((iid, f"m{i}r", "revenue",
                              str(100 + 10 * i), True))
        peer_measures.append((iid, f"m{i}n", "net_margin",
                              f"0.{2 + i}", True))
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ps", "industry", "mixed")
    peers.add_version("psv1", "ps", 1, "2024-01-01", None, "manual",
                      "v1", True, None, None)
    for iid in ids:
        peers.add_member("psv1", iid, None)
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage)
    builder.build(ids[0], "i0", "2024-12-31", peer_set_version="psv1",
                  peer_measures=peer_measures,
                  peer_members_previous=[], peer_members_current=ids)
    conn.close()


def _build_valued_usd_snapshot(root: str) -> None:
    """Один USD-эмитент с посчитанной ebitda: входы operating_income и
    d_and_a записаны, мера имеет значение и валюту USD."""
    from rusterm.core.snapshot import SnapshotBuilder
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths
    from rusterm.store.repos import Instrument, Issuer, RepoRegistry

    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "iv", "Valued Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-V", "iv", None, "common", "active", None))
    for fact_id, concept, value in (
            ("fv1", "operating_income", "30"),
            ("fv2", "d_and_a", "5"),
            ("fv3", "revenue", "100"),
            ("fv4", "net_income", "20")):
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at, canonical_concept,
               source_kind) VALUES (?, ?, ?, '2024-01-01',
               '2024-12-31', 'duration', ?, 'USD', 'USD',
               'as_reported', 'extracted', 's', '{}',
               'companyfacts.v1', 'ok', 0, ?, 'provider')""",
            (fact_id, "iv", concept, value, concept))
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    builder.build("US-V", "iv", "2024-12-31")
    conn.close()
