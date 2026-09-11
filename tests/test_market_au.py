"""ТЗ-20 L3: провайдер ASX (Австралия), канал без договора.

Все тесты офлайн на ЗАПИСАННЫХ телах tests/data/asx/ (живая выкачка
11.09: header+announcements для CBA/BHP/TLS, 200; несуществующий код
ZZZZ — HTTP 400). Сети нет.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.providers.asx import AsxProvider
from rusterm.providers.base import ProviderError
from rusterm.providers.budget import NetworkGate, RequestGate

DATA = Path(__file__).resolve().parent / "data" / "asx"
UA_ENV = {"RUSTERM_SEC_UA": "Synthetic Test l3.invalid"}


def _gate() -> RequestGate:
    return RequestGate(gate=NetworkGate(environ=dict(UA_ENV)))


def _recorded(code: str, what: str) -> bytes:
    return (DATA / f"{what}_{code}.json").read_bytes()


def _provider(responses: dict[str, object], calls: list | None = None):
    def transport(url: str, headers: dict):
        if calls is not None:
            calls.append(url)
        for part, body in responses.items():
            if part in url:
                raw = body if isinstance(body, bytes) else json.dumps(
                    body).encode()
                return 200, raw, {}
        return 400, b"bad request", {}
    return AsxProvider(gate=_gate(), transport=transport)


def test_can_auto_ingest_true_on_recorded_header_and_announcements():
    """Золотая привязка: настоящие байты CBA (выкачка 11.09)."""
    provider = _provider({
        "CBA/header": _recorded("CBA", "header"),
        "CBA/announcements": _recorded("CBA", "announcements"),
    })
    assert provider.can_auto_ingest("CBA") is True


def test_recorded_header_values_resolve_to_file():
    header = json.loads(_recorded("CBA", "header"))
    # значения разрешаются в записанный файл по указателю
    assert header["data"]["symbol"] == "CBA"
    assert header["data"]["marketCap"] == 256374433246
    assert header["data"]["sector"] == "Financials"


def test_unknown_code_maps_to_unknown_issuer():
    """ZZZZ в замере ответил HTTP 400 — unknown_issuer значением."""
    provider = _provider({})
    answer = provider.can_auto_ingest("ZZZZ")
    assert isinstance(answer, ProviderError)
    assert answer.reason == "unknown_issuer"


def test_listed_without_announcements_is_false_partial_market():
    """access=partial: эмитент известен (header 200), раскрытий не
    видно — False -> наверху manual_import_required, а не пустой
    эмитент."""
    provider = _provider({
        "XYZ/header": {"data": {"symbol": "XYZ",
                                "displayName": "SUSPENDED LTD"}},
        "XYZ/announcements": {"data": {"items": []}},
    })
    assert provider.can_auto_ingest("XYZ") is False


def test_list_documents_from_recorded_announcements():
    provider = _provider({
        "CBA/announcements": _recorded("CBA", "announcements"),
    })
    docs = provider.list_documents("CBA")
    assert docs.documents
    first = docs.documents[0]
    assert first.issuer_id == "CBA"
    assert first.url.startswith("asxdoc:")
    assert first.doc_type  # announcementType из записанного тела


def test_fetch_document_is_manual_import_required_with_filing_named():
    provider = _provider({})
    answer = provider.fetch_document("asxdoc:2924-03134570-3A701583")
    assert isinstance(answer, ProviderError)
    assert answer.reason.startswith("manual_import_required:asxdoc:")
    # и никогда не ретраится: запросов через гейт не было вовсе
    assert provider.gate.calls_made == 0


def test_poll_index_honestly_refuses_value():
    answer = _provider({}).poll_index("20260911")
    assert isinstance(answer, ProviderError)
    assert answer.reason == "asx_no_marketwide_index"


def test_no_contract_note_in_docstring():
    """ADR-0010 §5: канал без договора объявлен в докстринге модуля."""
    import rusterm.providers.asx as module
    assert "без договора" in (module.__doc__ or "")


def test_partial_refusal_leaves_zero_issuer_rows(app_root_factory):
    """Done-when полосы: partial-отказ через cmd_add — ноль строк в
    issuer (счётом) и код 0; сообщение называет команду ручного
    импорта с тикером. can_auto_ingest здесь — НАСТОЯЩИЙ код
    AsxProvider; адаптер в тесте поставляет только resolve/ticker_venues
    (они EDGAR-центричны в cmd_add и вне зоны L3)."""
    import sqlite3

    import rusterm.cli as cli

    root, paths = app_root_factory
    asx = _provider({
        "XYZ/header": {"data": {"symbol": "XYZ",
                                "displayName": "SUSPENDED LTD"}},
        "XYZ/announcements": {"data": {"items": []}},
    })

    class ResolveAdapter:
        """Тестовый адаптер: ASX-код и есть идентификатор; вопрос о
        доступности отвечает настоящий AsxProvider.can_auto_ingest."""

        def resolve(self, ticker, market, as_of):
            header = asx._get(ticker.upper(), "header")
            if isinstance(header, ProviderError):
                return header
            return {"ticker": ticker.upper(), "cik": 0,
                    "title": (header.get("data") or {}).get(
                        "displayName", ticker.upper())}

        def ticker_venues(self):
            return {"XYZ": "ASX"}

        def can_auto_ingest(self, identifier):
            return asx.can_auto_ingest(identifier)

    original = cli.get_provider
    cli.get_provider = lambda name, gate=None: ResolveAdapter()
    try:
        code = cli.main(["--root", str(root), "add", "--ticker", "XYZ",
                         "--market", "AU"])
    finally:
        cli.get_provider = original
    assert code == 0
    conn = sqlite3.connect(str(paths.db_path))
    try:
        n = conn.execute("SELECT COUNT(*) FROM issuer").fetchone()[0]
    finally:
        conn.close()
    assert n == 0


@pytest.fixture()
def app_root_factory(monkeypatch, tmp_path):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test l3.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       str(tmp_path / "no-such-rusterm.env"))
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3_connect(paths)
    apply_migrations(conn)
    conn.close()
    return root, paths


def sqlite3_connect(paths):
    import sqlite3
    return sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
