"""ТЗ-22 J1.0: парсер EDGAR записывает валюту из ключа units; правило
пустых валют вступает в силу ровно с этим изменением.

- companyfacts: ключ units — валюта для денежных концептов (USD, CAD);
  shares и USD/shares валютой не являются — currency остаётся None.
- Стоп-кран: набор из записанной валюты и пустот — currency_mismatch,
  а не молчаливое «та одна валюта»; набор из одних пустот (легаси) —
  как раньше.
"""
from __future__ import annotations

import json
import os
import sqlite3

import pytest

import rusterm.cli as cli
import rusterm.providers.edgar as edgar_module
from rusterm.core.peers import currency_guard
from rusterm.parsers import CompanyFactsParser, currency_of_unit

# ── правило формы ключа ──────────────────────────────────────────────


def test_currency_of_unit_rule():
    assert currency_of_unit("USD") == "USD"
    assert currency_of_unit("CAD") == "CAD"
    assert currency_of_unit("KRW") == "KRW"
    assert currency_of_unit("shares") is None
    assert currency_of_unit("pure") is None
    assert currency_of_unit("USD/shares") is None
    assert currency_of_unit("") is None


def test_companyfacts_parser_records_currency_from_units_key():
    raw = json.dumps({"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            {"start": "2024-01-01", "end": "2024-12-31", "val": 100,
             "accn": "a1", "fy": 2024, "fp": "FY", "form": "10-K",
             "filed": "2025-01-01"}]},
        },
        "WeightedAverageNumberOfSharesOutstanding": {"units": {"shares": [
            {"end": "2024-12-31", "val": 50,
             "accn": "a1", "form": "10-K", "filed": "2025-01-01"}]},
        },
    }}}).encode()
    result = CompanyFactsParser().parse(raw, {"source_ref": "h" * 64})
    by_unit = {f["unit"]: f for f in result.facts}
    assert by_unit["USD"]["currency"] == "USD"
    assert by_unit["shares"]["currency"] is None


# ── записанные payload'ы: ингест в свежую базу ───────────────────────

_TADTAS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1000275, "ticker": "RY",
          "title": "ROYAL BANK OF CANADA"},
}
_EXCHANGES = {"fields": ["cik", "name", "ticker", "exchange"],
              "data": [[320193, "Apple Inc.", "AAPL", "NASDAQ"],
                       [1000275, "Royal Bank of Canada", "RY", "NYSE"]]}
_FACTS = {"companyfacts_m3_AAPL.json": 320193,
          "companyfacts_m6_RY.json": 1000275}


def _ingest(root, ticker: str, market: str) -> None:
    assert cli.main(["--root", str(root), "add", "--ticker", ticker,
                     "--market", market]) == 0
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     f"{market}-{ticker}", "--source", "edgar"]) == 0


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test j10.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    from pathlib import Path
    data = Path(__file__).resolve().parent / "data"

    def transport(url, headers):
        if "company_tickers.json" in url:
            return 200, json.dumps(_TADTAS).encode(), {}
        if "company_tickers_exchange.json" in url:
            return 200, json.dumps(_EXCHANGES).encode(), {}
        for name, cik in _FACTS.items():
            if f"CIK{cik:010d}" in url:
                return 200, (data / "edgar" / name).read_bytes(), {}
        return 404, b"{}", {}

    class _Patched(edgar_module.EdgarProvider):
        def __init__(self, *a, **kw):
            kw.setdefault("transport", transport)
            super().__init__(*a, **kw)

    monkeypatch.setattr(edgar_module, "EdgarProvider", _Patched)
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    return root, tmp_path / "app" / "rusterm.db"


def test_recorded_ingest_carries_currency(app):
    """Done-when J1.0: ингест записанного payload'а пишет валюту факта;
    выборка DISTINCT больше не [None]."""
    root, db = app
    _ingest(root, "AAPL", "US")
    _ingest(root, "RY", "CA")
    conn = sqlite3.connect(str(db))
    try:
        for market, ccy in (("US", "USD"), ("CA", "CAD")):
            rows = conn.execute(
                """SELECT DISTINCT f.currency FROM fact f
                   JOIN instrument i ON i.issuer_id = f.issuer_id
                   WHERE i.instrument_id LIKE ? AND f.currency IS NOT NULL""",
                (f"{market}-%",)).fetchall()
            assert {r[0] for r in rows} == {ccy}, (market, rows)
        # денежные факты без валюты после J1.0 не существуют
        blanks = conn.execute(
            """SELECT COUNT(*) FROM fact f
               JOIN instrument i ON i.issuer_id = f.issuer_id
               WHERE i.instrument_id LIKE '%-%'
                 AND f.currency IS NULL AND f.unit IN
                 ('USD', 'CAD', 'KRW', 'BRL')""").fetchone()[0]
        assert blanks == 0
        # shares и USD/shares валютой не были — None честен
        non_currency = conn.execute(
            """SELECT DISTINCT currency FROM fact
               WHERE unit IN ('shares', 'USD/shares')""").fetchall()
        assert {r[0] for r in non_currency} == {None}
    finally:
        conn.close()


# ── правило пустот в стоп-кране ──────────────────────────────────────


def test_guard_counts_blank_as_party():
    # записанная + пустота = отказ с перечнем, не «та одна валюта»
    assert currency_guard("revenue", {"USD", ""}) == \
        "currency_mismatch: (blank), USD"
    assert currency_guard("ebitda", {"", "", "KRW"}) == \
        "currency_mismatch: (blank), KRW"
    # одни пустоты — легаси, поведение прежнее
    assert currency_guard("revenue", {"", ""}) is None
    assert currency_guard("revenue", set()) is None
    # одна записанная без пустот — как раньше
    assert currency_guard("revenue", {"USD"}) is None
    assert currency_guard("revenue", {"USD", "KRW"}) == \
        "currency_mismatch: KRW, USD"


def test_firewall_sees_blank_via_lineage():
    """currencies_for_measure отдаёт пустоты: мера с входами
    «USD-факт + пустой факт» получает отказ с перечнем."""
    from rusterm.core.peers import currency_bound
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import RepoRegistry
    import tempfile
    from pathlib import Path

    paths = AppPaths.from_root(Path(tempfile.mkdtemp()) / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-usd', 'i1', 'revenue', '2024-01-01', '2024-12-31',
           'duration', '100', 'USD', 'USD', 'as_reported', 'extracted',
           's1', '{}', 'companyfacts.v1', 'ok', 0, 'revenue', 'provider')""")
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-blank', 'i2', 'revenue', '2024-01-01', '2024-12-31',
           'duration', '200', 'USD', NULL, 'as_reported', 'extracted',
           's2', '{}', 'synthetic.v1', 'ok', 0, 'revenue', 'provider')""")
    from rusterm.store.repos import SnapshotRepo
    snap = SnapshotRepo(conn)
    for mid, fact_id in (("m1", "f-usd"), ("m2", "f-blank"),
                         ("m3", "f-usd")):
        snap.insert_measure_with_lineage(
            dict(measure_id=mid, snapshot_id="s-x", scope="issuer",
                 scope_ref="i1", concept="revenue", value="1",
                 unit="USD", period_start="2024-01-01",
                 period_end="2024-12-31", formula_id="revenue",
                 method_version="v1", null_reason=None,
                 peer_set_version=None),
            [{"fact_id": fact_id, "peer_measure_id": None,
              "role": "input"}])
    assert currency_bound("revenue")
    assert repos.snapshot.currencies_for_measure("m1") == {"USD"}
    # m2: факт без валюты даёт пустую строку, а unit меры несёт валюту
    # (ТЗ-23 K4/K6: unit денежной меры — её валюта)
    assert repos.snapshot.currencies_for_measure("m2") == {"", "USD"}
    # смешение записанной и пустой через lineage — отказ с перечнем
    mixed = repos.snapshot.currencies_for_measure("m1") | \
        repos.snapshot.currencies_for_measure("m2")
    assert currency_guard("revenue", mixed) == \
        "currency_mismatch: (blank), USD"
    # легаси «одни пустоты» (пустая валюта и у фактов, и в unit)
    # покрыт юнит-тестом currency_guard выше: {"", ""} -> None
    conn.close()
