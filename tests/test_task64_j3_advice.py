"""ТЗ-64 J3: отказ подсказывает, что делать.

`missing_data: price_close` несёт строку-совет с подставленной
командой (инструмент, источник — из констант ядра); строка разбирается
парсером CLI, не исполняется; совет одинаков в CLI и в окне;
concept_not_mapped совета не получает — выдуманного нет.
"""
from __future__ import annotations

import os
import shlex
import sqlite3
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from rusterm.cli import _build_parser, main as cli_main  # noqa: E402
from rusterm.core.export import refusal_advice  # noqa: E402
from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import Instrument, Issuer, RepoRegistry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-j3", "Corp J", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-J3", "i-j3", None, "common", "active", None))
    repos.snapshot.create_snapshot("s-j3", "US-J3", 1, "2025-01-01",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-j3-price", "s-j3", "issuer", "i-j3", "div_yield",
        None, "ratio", "2024-01-01", "2024-12-31", None, "t64-test",
        "missing_data: price_close", None)
    repos.snapshot.insert_measure(
        "m-j3-map", "s-j3", "issuer", "i-j3", "drawdown",
        None, "ratio", "2024-01-01", "2024-12-31", None, "t64-test",
        "concept_not_mapped", None)
    yield repos, paths
    conn.close()


def test_advice_substitutes_instrument_and_parses(catalog, tmp_path,
                                                  capsys):
    """Совет md-экспорта подставляет инструмент и разбирается
    парсером CLI (как в B26): разбор без исполнения, без сети."""
    assert cli_main(["--root", str(tmp_path / "app"), "export",
                     "--instrument", "US-J3", "--format", "md"]) == 0
    out = capsys.readouterr().out
    match = next((line for line in out.splitlines()
                  if "rusterm ingest" in line), None)
    assert match, out
    tokens = shlex.split(match[match.index("rusterm"):])[1:]  # без rusterm
    parser = _build_parser()
    args = parser.parse_args(["--root", str(tmp_path / "app")] + tokens)
    assert args.source == "twelvedata"
    assert args.instrument == "US-J3"


def test_advice_only_where_action_is_obvious():
    """concept_not_mapped совета не получает — выдуманного нет."""
    assert refusal_advice("price_close", "US-J3") is not None
    assert refusal_advice("concept_not_mapped", "US-J3") is None


def test_window_advice_same_words(catalog, tmp_path):
    """Окно и CLI — одними словами: «что делать: цены: rusterm ingest
    --source twelvedata --instrument US-J3»."""
    repos, paths = catalog
    table = desktop_data.measure_table_rows(repos, "US-J3")
    row = next(r for r in table["measures"]
               if r["concept"] == "div_yield")
    panel = desktop_data.source_panel_view(
        repos, paths, row,
        instrument_id=table["instrument_id"])["text"]
    advice = ("что делать: цены: rusterm ingest --source twelvedata "
              "--instrument US-J3")
    assert advice in panel

    env = dict(os.environ, RUSTERM_ENV_FILE=str(paths.root / "empty.env"))
    proc = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(paths.root),
         "export", "--instrument", "US-J3", "--format", "md"],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert advice in proc.stdout
