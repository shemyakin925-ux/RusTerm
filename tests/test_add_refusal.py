"""TASK-19 F3 (ADR-0010 §3): `rusterm add` спрашивает провайдера рынка
«забирается ли эмитент автоматически» ДО создания. Три исхода ровно:
ingest (создание) / manual_import_required (отказ по имени, ноль строк,
код 0) / unknown_issuer (код 1). Всё через подставного провайдера —
сети нет.
"""
from __future__ import annotations

import sqlite3

import pytest

import rusterm.cli as cli
from rusterm.providers.base import ProviderError
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir


class FakeProvider:
    """Детерминированная подстава: resolve всегда успешен,
    can_auto_ingest возвращает сценарное значение исхода."""

    scenario: bool | ProviderError = True

    def resolve(self, ticker, market, as_of):
        return {"ticker": ticker.upper(), "cik": 1234567,
                "title": f"{ticker.upper()} Fake Corp"}

    def ticker_venues(self):
        return {"FAKE": "NASDAQ"}

    def can_auto_ingest(self, identifier):
        return self.scenario


@pytest.fixture()
def app_root(monkeypatch, tmp_path):
    # синтетический контакт: уже заданная переменная сильнее env-файла
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test f3.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       str(tmp_path / "no-such-rusterm.env"))
    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    conn.close()
    return root, paths


def _issuer_count(paths) -> int:
    conn = sqlite3.connect(str(paths.db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM issuer").fetchone()[0]
    finally:
        conn.close()


def _run_add(root, monkeypatch, scenario) -> int:
    fake = FakeProvider()
    fake.scenario = scenario
    monkeypatch.setattr(cli, "get_provider", lambda name, gate=None: fake)
    return cli.main(["--root", str(root), "add", "--ticker", "FAKE",
                     "--market", "US"])


def test_ingest_outcome_creates_issuer(app_root, monkeypatch):
    root, paths = app_root
    assert _run_add(root, monkeypatch, True) == 0
    assert _issuer_count(paths) == 1


def test_manual_import_required_refuses_leaves_zero_rows_exits_0(
        app_root, monkeypatch, capsys):
    root, paths = app_root
    assert _run_add(root, monkeypatch, False) == 0
    # отказ по имени: ноль строк в issuer, счётом, не на глаз
    assert _issuer_count(paths) == 0
    out = capsys.readouterr().out
    assert "manual_import_required" in out
    # совет действия назван командой с подставленным тикером
    assert "rusterm import" in out and "FAKE" in out


def test_unknown_issuer_exits_1_and_creates_nothing(
        app_root, monkeypatch, capsys):
    root, paths = app_root
    assert _run_add(root, monkeypatch,
                    ProviderError("unknown_issuer")) == 1
    assert _issuer_count(paths) == 0
    assert "unknown_issuer" in capsys.readouterr().err


def test_unresolved_market_provider_is_config_error_value(
        app_root, monkeypatch, capsys):
    """Строка реестра KR указывает на провайдера, которого ещё нет:
    get_provider обязан ответить значением provider_not_implemented (F5
    сажает место), add не создаёт эмитента и объясняет причину."""
    from rusterm.providers import UnknownProvider

    root, paths = app_root
    monkeypatch.setattr(
        cli, "get_provider",
        lambda name, gate=None: UnknownProvider(name))
    code = cli.main(["--root", str(root), "add", "--ticker", "SAMSUNG",
                     "--market", "KR"])
    assert code == 1
    assert _issuer_count(paths) == 0
    assert "provider_not_implemented:dart" in capsys.readouterr().err
