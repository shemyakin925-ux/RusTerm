"""ТЗ-21 H4: end to end по каждому севшему рынку — add → ingest →
snapshot → export, всё на записанных payload'ах, сети нет.

Полные пути (данные до мер): US-AAPL, CA-RY, OTC-CPTP — EDGAR
companyfacts из tests/data/edgar, транспорт подменяется на уровне
класса провайдера (та же дверь, что sitecustomize у X1/G9, но
в-process). Экспорт несёт код рынка буквально: instrument_id — это
"<код рынка>-<тикер>" (cmd_add), он же в метаданных экспорта.

Честные отказы: KR без ключа — провайдер не строится, ноль строк,
код 1 (причина dart_key_unset, H8: значение не печатается никогда);
BR/AU — эмитент создаётся (кадастровый индекс / header+announcements
отвечают), но канала сбора фундаментала у CLI ещё нет, поэтому
snapshot честно пуст: все десять мер первого прохода — null с
причиной, экспорт работает и несёт код рынка.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import rusterm.cli as cli
import rusterm.providers.edgar as edgar_module
from rusterm.providers.asx import AsxProvider
from rusterm.providers.base import ProviderError
from rusterm.providers.budget import RequestGate
from rusterm.providers.cvm import CAD_URL, CvmProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir

# десять мер первого прохода (formulas §3, snapshot.py V4)
_TEN = ("asset_turnover", "ebitda", "effective_tax", "fcf",
        "gross_margin", "interest_coverage", "net_margin", "nopat",
        "operating_margin", "roe")

_DATA = None  # заполнится в константе ниже


def _data(path):
    from pathlib import Path
    return Path(__file__).resolve().parent / "data" / path


def _issuer_count(paths) -> int:
    conn = sqlite3.connect(str(paths.db_path))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM issuer").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture()
def app(monkeypatch, tmp_path):
    """Инициализированный корень приложения с чистым окружением:
    контакт задан, ключей нет, env-файл отсутствует."""
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test h4.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    monkeypatch.delenv("RUSTERM_DART_KEY", raising=False)
    monkeypatch.delenv("RUSTERM_LLM_API_KEY", raising=False)
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    return root, AppPaths.from_root(root)


@pytest.fixture()
def edgar_stub(monkeypatch):
    """Подменный EDGAR на записанных файлах: карта тикеров с AAPL/RY/
    CPTP, файл площадок, companyfacts по CIK из tests/data/edgar."""
    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL",
                     "title": "Apple Inc."},
               "1": {"cik_str": 1000275, "ticker": "RY",
                     "title": "ROYAL BANK OF CANADA"},
               "2": {"cik_str": 202947, "ticker": "CPTP",
                     "title": "Capital Properties Inc"}}
    exchanges = {"fields": ["cik", "name", "ticker", "exchange"],
                 "data": [
        [320193, "Apple Inc.", "AAPL", "NASDAQ"],
        [1000275, "Royal Bank of Canada", "RY", "NYSE"],
        [202947, "Capital Properties Inc", "CPTP", "OTC"]]}
    facts = {"companyfacts_m3_AAPL.json": 320193,
             "companyfacts_m6_RY.json": 1000275,
             "companyfacts_m6_CPTP.json": 202947}

    def transport(url, headers):
        if "company_tickers.json" in url:
            return 200, json.dumps(tickers).encode(), {}
        if "company_tickers_exchange.json" in url:
            return 200, json.dumps(exchanges).encode(), {}
        for name, cik in facts.items():
            if f"CIK{cik:010d}" in url:
                return 200, _data(f"edgar/{name}").read_bytes(), {}
        return 404, b"{}", {}

    class _Patched(edgar_module.EdgarProvider):
        def __init__(self, *a, **kw):
            kw.setdefault("transport", transport)
            super().__init__(*a, **kw)

    monkeypatch.setattr(edgar_module, "EdgarProvider", _Patched)


def _full_path(root, capsys, ticker: str, market: str, min_values: int,
               exact_values: int | None = None):
    """add → ingest → snapshot → export; экспорт несёт код рынка."""
    assert cli.main(["--root", str(root), "add", "--ticker", ticker,
                     "--market", market]) == 0
    capsys.readouterr()
    instrument = f"{market}-{ticker}"
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     instrument, "--source", "edgar"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     instrument]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "export", "--instrument",
                     instrument, "--format", "json"]) == 0
    export = json.loads(capsys.readouterr().out)
    # код рынка в экспорте — буквально, в идентификаторе инструмента
    assert export["snapshot"]["instrument_id"] == instrument
    rows = [m for m in export["measures"]
            if m["concept"] in _TEN]
    values = [m for m in rows if m["value"] is not None]
    assert len(rows) == 10, "десять мер первого прохода в экспорте"
    assert len(values) >= min_values
    if exact_values is not None:
        assert len(values) == exact_values, (
            f"{instrument}: {len(values)} из 10")
    # у пустых мер причина названа, не тишина
    for m in rows:
        if m["value"] is None:
            assert m["null_reason"], (instrument, m["concept"])
    return len(values)


def test_h4_us_end_to_end(app, edgar_stub, capsys):
    root, paths = app
    assert _full_path(root, capsys, "AAPL", "US", min_values=8) >= 8
    assert _issuer_count(paths) == 1


def test_h4_ca_end_to_end(app, edgar_stub, capsys):
    root, paths = app
    assert _full_path(root, capsys, "RY", "CA", min_values=1) >= 1
    assert _issuer_count(paths) == 1


def test_h4_otc_end_to_end(app, edgar_stub, capsys):
    root, paths = app
    assert _full_path(root, capsys, "CPTP", "OTC", min_values=1) >= 1
    assert _issuer_count(paths) == 1


def test_h4_kr_honest_refusal_without_key(app, capsys):
    """KR сегодня честно отказывает: ключа нет — провайдер не строится,
    ноль строк, имя причины без всяких значений (H8)."""
    root, paths = app
    assert cli.main(["--root", str(root), "add", "--ticker", "005930",
                     "--market", "KR"]) == 1
    err = capsys.readouterr().err
    assert "KR" in err and "dart_key_unset" in err
    assert "SENTINEL" not in err and "sk-" not in err
    assert _issuer_count(paths) == 0


def test_h4_br_issuer_created_snapshot_honestly_empty(app, monkeypatch,
                                                      capsys):
    """BR: кадастровый индекс (записанный срез) отвечает — эмитент
    создаётся; канала сбора фундаментала в CLI ещё нет, snapshot
    пуст, но честен: десять мер — null с причиной; экспорт несёт BR."""
    root, paths = app
    cad = _data("cvm/cad_slice.csv").read_bytes()

    def transport(url, headers, method):
        if url == CAD_URL and method == "HEAD":
            return 200, b"", {"Last-Modified": "recorded-cad"}
        if url == CAD_URL and method == "GET":
            return 200, cad, {}
        return 404, b"", {}

    class _BR:
        """Адаптер resolve/venues (cmd_add EDGAR-центричен), вопрос о
        доступности отвечает настоящий CvmProvider.can_auto_ingest."""

        def __init__(self):
            self.cvm = CvmProvider(gate=RequestGate(),
                                   transport=transport)

        def resolve(self, ticker, market, as_of):
            return {"ticker": ticker.upper(), "cik": 23264,
                    "title": "AMBEV S.A."}

        def can_auto_ingest(self, identifier):
            return self.cvm.can_auto_ingest(identifier)

        def ticker_venues(self):
            return {}

    monkeypatch.setattr(cli, "get_provider", lambda name, gate=None:
                        _BR())
    assert cli.main(["--root", str(root), "add", "--ticker", "AMBEV",
                     "--market", "BR"]) == 0
    assert _issuer_count(paths) == 1
    capsys.readouterr()
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     "BR-AMBEV"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "export", "--instrument",
                     "BR-AMBEV", "--format", "json"]) == 0
    export = json.loads(capsys.readouterr().out)
    assert export["snapshot"]["instrument_id"] == "BR-AMBEV"
    rows = [m for m in export["measures"] if m["concept"] in _TEN]
    assert len(rows) == 10
    assert all(m["value"] is None for m in rows)
    assert all(m["null_reason"] for m in rows)


def test_h4_au_issuer_created_snapshot_honestly_empty(app, monkeypatch,
                                                      capsys):
    """AU: записанные header+announcements отвечают — эмитент
    создаётся; раскрытия ASX машинно недоступны (без договора,
    ADR-0010 §5), snapshot честно пуст, экспорт несёт AU."""
    root, paths = app
    header = _data("asx/header_BHP.json").read_bytes()
    announcements = _data("asx/announcements_BHP.json").read_bytes()

    def transport(url, headers):
        if url.endswith("/BHP/header"):
            return 200, header, {}
        if url.endswith("/BHP/announcements"):
            return 200, announcements, {}
        return 404, b"{}", {}

    class _AU:
        def __init__(self):
            self.asx = AsxProvider(gate=RequestGate(),
                                   transport=transport)

        def resolve(self, ticker, market, as_of):
            got = self.asx._get(ticker.upper(), "header")
            if isinstance(got, ProviderError):
                return got
            return {"ticker": ticker.upper(), "cik": 0,
                    "title": (got.get("data") or {}).get(
                        "displayName", ticker.upper())}

        def can_auto_ingest(self, identifier):
            return self.asx.can_auto_ingest(identifier)

        def ticker_venues(self):
            return {}

    monkeypatch.setattr(cli, "get_provider", lambda name, gate=None:
                        _AU())
    assert cli.main(["--root", str(root), "add", "--ticker", "BHP",
                     "--market", "AU"]) == 0
    assert _issuer_count(paths) == 1
    capsys.readouterr()
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     "AU-BHP"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "export", "--instrument",
                     "AU-BHP", "--format", "json"]) == 0
    export = json.loads(capsys.readouterr().out)
    assert export["snapshot"]["instrument_id"] == "AU-BHP"
    rows = [m for m in export["measures"] if m["concept"] in _TEN]
    assert len(rows) == 10
    assert all(m["value"] is None for m in rows)
    assert all(m["null_reason"] for m in rows)
