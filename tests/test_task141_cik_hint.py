"""ТЗ-141 D4: подсказка CIK вручную (вердикт на REPORT-139 Q1).

Фид говорит CIK A (строка XOM указывает на CIK 2115436), пользователь
даёт --cik B (34088) — резолвер фида не вызывается, регистрант B, имя —
от самого регистранта (submissions), аудит несёт происхождение manual.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.cli import _build_parser
from rusterm.store.paths import AppPaths
from rusterm.store.repos import RepoRegistry


class _FakeFeedProvider:
    """Фид говорит CIK A; submissions отвечают только для CIK B."""

    reason = None

    def __init__(self, gate=None):
        self.cik = None
        self.calls: list[str] = []

    def resolve(self, ticker, market, as_of):
        self.calls.append("resolve")
        return {"ticker": ticker.upper(), "cik": 2115436,
                "title": "ExxonMobil Holdings Corp"}

    def registrant_name(self):
        self.calls.append("registrant_name")
        if self.cik != 34088:
            from rusterm.providers.base import ProviderError
            return ProviderError("unknown_issuer")
        return "EXXON MOBIL CORP"

    def ticker_venues(self):
        self.calls.append("venues")
        return {"T": "NYSE"}

    def can_auto_ingest(self, ticker):
        return True


def test_cik_hint_beats_the_feed_row(tmp_path, monkeypatch):
    import rusterm.cli as cli

    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test d4.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    fake = _FakeFeedProvider()
    monkeypatch.setattr(cli, "get_provider", lambda name, gate=None: fake)

    root = str(tmp_path / "cik-base")
    assert cli.main(["--root", root, "init"]) == 0
    args = _build_parser().parse_args(
        ["--root", root, "add", "--ticker", "T", "--market", "US",
         "--cik", "34088"])
    assert cli.cmd_add(args) == 0

    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(f"file:{paths.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        issuer = dict(conn.execute(
            "SELECT issuer_id, name, registry_id FROM issuer").fetchone())
        assert issuer["registry_id"] == "34088", issuer
        assert issuer["name"] == "EXXON MOBIL CORP", issuer
        payload = json_of(conn)
    finally:
        conn.close()
    # фид не вызывался: строка фида отвечает другой сущности
    assert "resolve" not in fake.calls, fake.calls
    assert payload.get("cik_origin") == "manual", payload


def json_of(conn):
    """Payload последней записи add — происхождение CIK там."""
    row = conn.execute(
        "SELECT payload FROM audit_log WHERE action='add'"
        " ORDER BY ts DESC LIMIT 1").fetchone()
    import json
    return json.loads(row[0]) if row and row[0] else {}


def test_without_hint_the_feed_row_decides(tmp_path, monkeypatch):
    import rusterm.cli as cli

    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test d4.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    fake = _FakeFeedProvider()
    monkeypatch.setattr(cli, "get_provider", lambda name, gate=None: fake)

    root = str(tmp_path / "feed-base")
    assert cli.main(["--root", root, "init"]) == 0
    args = _build_parser().parse_args(
        ["--root", root, "add", "--ticker", "T", "--market", "US"])
    assert cli.cmd_add(args) == 0

    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(f"file:{paths.db_path}?mode=ro", uri=True)
    try:
        registry_id = conn.execute(
            "SELECT registry_id FROM issuer").fetchone()[0]
        assert registry_id == "2115436", registry_id
        payload = json_of(conn)
        assert payload.get("cik_origin") is None, payload
    finally:
        conn.close()
