"""ТЗ-143 F0a: один отказ фида не роняет «Обновить».

REPORT-142 Q1: ProviderError от EDGAR submissions раньше проскакивал в
сравнение дат refresh_one и падал TypeError-ом — весь проход окна
обрывался на середине. Теперь отказ одной бумаги — результат с
причиной (считается в «отказов: N» итоговой строки), проход идёт
дальше. Фикстура офлайновая (P7): три бумаги, у средней submissions
отказывает (ProviderError значением, как живой 403/обрыв), две другие
приезжают по записанным ответам.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.cli import _build_parser
from rusterm.core.refresh import SUMMARY_LINE_PREFIX
from rusterm.providers.base import ProviderError
from rusterm.providers.yahoo import YahooProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Issuer, Instrument, Listing,
                                 RepoRegistry)
from tests.test_task96_r2_follow import YAHOO_CHART

REPO = Path(__file__).resolve().parents[1]
FACTS = REPO / "tests/data/edgar/companyfacts_m3_AAPL.json"

SUBMISSIONS_10Q = {
    "filings": {"recent": {
        "filingDate": ["2026-09-15", "2026-08-01"],
        "form": ["10-Q", "10-K"],
    }},
}

REFUSER_CIK = 222222


class _FakeProvider:
    """Провайдер по контракту refresh_one: submissions -> дата/форма,
    companyfacts -> записанный payload. CIK-отказнику submissions
    недоступен — ProviderError значением, как живой 403/обрыв
    (ТЗ-109 R2)."""

    def __init__(self):
        self.cik = None

    def latest_filing_date(self):
        if self.cik == REFUSER_CIK:
            return ProviderError("source_unreachable:http_403")
        dates = SUBMISSIONS_10Q["filings"]["recent"]["filingDate"]
        return max(dates)

    def latest_filing_form(self):
        if self.cik == REFUSER_CIK:
            return None
        dates = SUBMISSIONS_10Q["filings"]["recent"]["filingDate"]
        forms = SUBMISSIONS_10Q["filings"]["recent"]["form"]
        return forms[dates.index(max(dates))]

    def fetch_companyfacts_conditional(self, validators=None):
        # payload с cik эмитента: у SEC поле и правда его несёт, а тут
        # оно ещё разводит sha256 ответов трёх бумаг (сырое хранилище
        # content-addressed — одинаковые байты дедуплицировались бы в
        # «unchanged» второй бумаге)
        doc = json.loads(FACTS.read_bytes().decode("utf-8"))
        doc["cik"] = self.cik
        return doc, {"etag": '"fake"', "last_modified": "fake"}


@pytest.fixture
def offline_providers(monkeypatch):
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return _FakeProvider()
        if name == "yahoo":
            return YahooProvider(
                gate=gate,
                transport=lambda url, headers:
                    (200, YAHOO_CHART.read_bytes(), {}))
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_PRICE_SOURCE", raising=False)


def _catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for issuer_id, instrument_id, ticker, cik in (
            ("cik-111111", "US-AAA", "AAA", 111111),
            ("cik-222222", "US-BBB", "BBB", REFUSER_CIK),
            ("cik-333333", "US-CCC", "CCC", 333333)):
        repos.instrument.upsert_issuer(Issuer(
            issuer_id, f"Issuer {ticker}", "US", str(cik), None,
            "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            instrument_id, issuer_id, None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{instrument_id}", instrument_id, "XNAS", "USD", 1,
            None, None))
        repos.instrument.add_ticker_history(
            f"l-{instrument_id}", ticker, "2015-01-01", None, "sandbox",
            None)
    conn.close()
    return paths


def test_one_submissions_refusal_does_not_abort_the_pass(
        tmp_path, offline_providers, capsys):
    """Средняя из трёх бумаг отказывает на submissions: проход
    завершается, бумаги 1 и 3 обновлены, строка называет «отказов: 1»."""
    paths = _catalog(tmp_path)

    args = _build_parser().parse_args(
        ["--root", str(paths.root), "refresh", "--all"])
    rc = cli.cmd_refresh(args)
    out = capsys.readouterr().out

    assert rc == 1, "один отказ — код 1, но проход завершён"
    conn = sqlite3.connect(f"file:{paths.db_path}?mode=ro", uri=True)
    try:
        for issuer in ("cik-111111", "cik-333333"):
            facts = conn.execute(
                "SELECT COUNT(*) FROM fact WHERE issuer_id=?",
                (issuer,)).fetchone()[0]
            assert facts > 0, f"{issuer} не обновлён"
        refused = conn.execute(
            "SELECT COUNT(*) FROM fact WHERE issuer_id='cik-222222'"
        ).fetchone()[0]
        assert refused == 0, "отказавшая бумага не должна привезти факты"
    finally:
        conn.close()
    summary = out.strip().splitlines()[-1]
    assert summary.startswith(SUMMARY_LINE_PREFIX), out
    assert "новые отчёты: 2" in summary, summary
    assert "отказов: 1" in summary, summary
