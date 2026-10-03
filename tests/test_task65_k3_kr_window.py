"""ТЗ-65 K3 (BACKLOG B47): попытка сбора по KR-инструменту из окна —
та же причина и та же строка-инструкция, что у CLI. Текст сверяется
на равенство, не на похожесть."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from rusterm.cli import main as cli_main  # noqa: E402
from rusterm.desktop import actions as desktop_actions  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import Instrument, Issuer, RepoRegistry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def kr_catalog(tmp_path, monkeypatch):
    monkeypatch.delenv("RUSTERM_DART_KEY", raising=False)
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-krt", "Corp KR", "KR", None, None, "ifrs-full", "KRW"))
    repos.instrument.upsert_instrument(Instrument(
        "KR-KRT", "i-krt", None, "common", "active", None))
    yield repos, paths, tmp_path / "app"
    conn.close()


def test_window_kr_refusal_equals_cli(kr_catalog, tmp_path, capsys,
                                      monkeypatch):
    repos, _paths, root = kr_catalog
    outcome = desktop_actions.collect_synthetic(str(root), "KR-KRT")
    assert outcome.ok is False
    assert outcome.reason == "dart_key_unset"
    cli = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(root),
         "ingest", "--instrument", "KR-KRT"],
        capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert "dart_key_unset" in cli.stderr
    # строка-инструкция в обоих лицах байт-в-байт
    cli_line = cli.stderr.strip()
    win_line = outcome.detail
    assert win_line in cli_line, (cli_line, win_line)
    assert outcome.reason == "dart_key_unset"
    # инструкция (после « — ») совпадает байт-в-байт
    assert cli_line.split(" — ", 1)[1] == win_line.split(" — ", 1)[1], (
        cli_line, win_line)
