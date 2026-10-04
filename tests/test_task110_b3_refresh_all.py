"""ТЗ-110 B3: `rusterm refresh --all` — проход окна без окна.

Тот же проход, что у фонового воркера (ТЗ-110 B2): цены инкрементально
(только недостающие дни; свежая лента — ноль запросов), отчётность —
только изменившаяся, снапшот — у бумаги, у которой что-то приехало.
Отмена читается на границе бумаги (код 130, как у follow).

Офлайн: провайдеры подменены в двери `cli.get_provider` (edgar и yahoo —
записанные ответы), счётчик запросов настоящий, каталог `tmp_path` (P7).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.cli import _build_parser
from rusterm.providers.edgar import EdgarProvider
from rusterm.providers.yahoo import YahooProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing,
                                 RepoRegistry)
from tests.edgar_fixtures import ownership_body
from tests.test_task96_r2_follow import _edgar_transport, YAHOO_CHART

REPO = Path(__file__).resolve().parents[1]


def _yahoo_ok(url, headers):
    return 200, YAHOO_CHART.read_bytes(), {}


@pytest.fixture
def offline_providers(monkeypatch):
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_transport)
        if name == "yahoo":
            return YahooProvider(gate=gate, transport=_yahoo_ok)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_PRICE_SOURCE", raising=False)


def _catalog(tmp_path):
    """Песочный каталог с одной бумагой (CIK из записанной карты)."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-US-AAPL", "Apple Inc.", "US", "320193", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAPL", "i-US-AAPL", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-US-AAPL", "US-AAPL", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history("l-US-AAPL", "AAPL", "2015-01-01",
                                        None, "sandbox", None)
    conn.close()
    return paths


def _prices(root):
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        return db.execute(
            "SELECT COUNT(*) FROM price WHERE instrument_id='US-AAPL'"
        ).fetchone()[0]
    finally:
        db.close()


def _snapshots(root):
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        return db.execute(
            "SELECT COUNT(*) FROM snapshot WHERE instrument_id='US-AAPL'"
        ).fetchone()[0]
    finally:
        db.close()


def test_refresh_all_updates_prices_and_snapshot(
        tmp_path, offline_providers, capsys):
    """Один проход --all: цены записаны, снапшот построен, итоговая
    строка называет бумаги и запросы. Повтор — ноль новых строк цен
    (дедупликация I7) при тех же записанных ответах."""
    paths = _catalog(tmp_path)

    args = _build_parser().parse_args(
        ["--root", str(paths.root), "refresh", "--all"])
    assert cli.cmd_refresh(args) == 0
    out = capsys.readouterr().out

    assert _prices(paths.root) > 0, "цены не записаны"
    assert _snapshots(paths.root) > 0, "снапшот не построен"
    summary = [l for l in out.splitlines()
               if l.startswith("обновлено: ")]
    assert summary, out
    assert "1 бумаг" in summary[0], summary[0]
    assert "запросов: " in summary[0], summary[0]

    before = _prices(paths.root)
    args = _build_parser().parse_args(
        ["--root", str(paths.root), "refresh", "--all"])
    assert cli.cmd_refresh(args) == 0
    capsys.readouterr()
    assert _prices(paths.root) == before, "повтор записал дубли (I7)"


def test_refresh_all_stops_on_cancel_at_a_paper_boundary(
        tmp_path, offline_providers, capsys):
    """Отмена на границе бумаги: код 130, как у follow; сколько-то
    сделано — и это честно в базе."""
    paths = _catalog(tmp_path)
    cancel = cli.desktop_actions.CancelFlag() \
        if hasattr(cli, "desktop_actions") else None
    from rusterm.desktop.actions import CancelFlag
    cancel = CancelFlag()
    cancel.cancel()

    args = _build_parser().parse_args(
        ["--root", str(paths.root), "refresh", "--all"])
    rc = cli.cmd_refresh(args, cancel=cancel)
    capsys.readouterr()

    assert rc == cli.FOLLOW_CANCELLED, rc


def test_refresh_all_without_watchlist_flag_does_not_need_it(
        tmp_path, offline_providers, capsys):
    """--all не требует --watchlist: список бумаг — сама база."""
    paths = _catalog(tmp_path)
    args = _build_parser().parse_args(
        ["--root", str(paths.root), "refresh", "--all"])
    assert cli.cmd_refresh(args) == 0
    out = capsys.readouterr().out
    assert "не найден" not in out, out


# ── schedule install/remove: plist в tmp_path ───────────────────────────

def test_schedule_install_writes_plist_with_daily_seven(tmp_path,
                                                        monkeypatch):
    """Done-when B3: содержимое plist (путь базы, аргументы прохода,
    ежедневный запуск в 07:00) сгенерировано в tmp_path; launchctl
    позван с путём файла; remove убирает."""
    import subprocess

    import rusterm.core.schedule as schedule

    calls = []
    monkeypatch.setattr(subprocess, "run",
                        lambda argv, **kw: calls.append(argv) or
                        subprocess.CompletedProcess(argv, 0))
    root = tmp_path / "app"
    root.mkdir()
    agents = tmp_path / "agents"

    args = _build_parser().parse_args(
        ["--root", str(root), "schedule", "install", "--dir", str(agents)])
    assert cli.cmd_schedule(args) == 0
    plist = agents / "com.equitylab.refresh.plist"
    content = plist.read_text(encoding="utf-8")

    assert str(root) in content, content
    assert "refresh" in content and "--all" in content, content
    assert "<key>Hour</key><integer>7</integer>" in content, content
    assert "<key>Minute</key><integer>0</integer>" in content, content
    assert calls and calls[0][:2] == ["launchctl", "load"], calls

    args = _build_parser().parse_args(
        ["schedule", "remove", "--dir", str(agents)])
    assert cli.cmd_schedule(args) == 0
    assert not plist.exists()
    assert calls[-1][:2] == ["launchctl", "unload"], calls


def test_schedule_remove_without_install_is_a_named_refusal(tmp_path,
                                                            capsys):
    args = _build_parser().parse_args(
        ["schedule", "remove", "--dir", str(tmp_path / "agents")])
    assert cli.cmd_schedule(args) == 1
    err = capsys.readouterr().err
    assert "агента нет" in err, err
