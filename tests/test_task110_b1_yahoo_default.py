"""ТЗ-110 B1: Yahoo — источник котировок по умолчанию.

Решение пользователя (круг 146): ключ Twelve Data отвечает «invalid»,
сплиты и дивиденды там платные (ADR-0018); Yahoo без ключа в коде с
ADR-0029. Без RUSTERM_PRICE_SOURCE путь собирает цены Yahoo-ом, и
`rusterm markets` называет это словами.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.cli import _build_parser, price_source
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing,
                                 RepoRegistry)


def test_without_env_the_price_source_is_yahoo():
    """Окружение изолировано (conftest): не задано — yahoo."""
    assert price_source() == "yahoo"


def test_explicit_source_still_wins():
    monkey_over = pytest.MonkeyPatch()
    with monkey_over.context() as m:
        m.setenv("RUSTERM_PRICE_SOURCE", "twelvedata")
        assert price_source() == "twelvedata"


def test_follow_price_stage_names_yahoo(tmp_path):
    """Аргумент-вектор стадии 5/6 пути зовёт yahoo без всякого env."""
    argv = ["ingest", "--source", cli.price_source(),
            "--instrument", "US-AAPL"]
    parsed = _build_parser().parse_args(
        ["--root", str(tmp_path), *argv])
    assert parsed.command == "ingest" and parsed.source == "yahoo"


def test_markets_names_the_price_source(tmp_path, capsys):
    """`rusterm markets` говорит, откуда котировки: строка «котировки»
    в тексте и поле price_source в --json."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    conn.close()

    args = _build_parser().parse_args(
        ["--root", str(paths.root), "markets"])
    assert cli.cmd_markets(args) == 0
    text = capsys.readouterr().out
    line = [l for l in text.splitlines() if l.startswith("котировки")]
    assert line, text
    assert line[0].split("\t")[1] == "yahoo", line[0]

    args_json = _build_parser().parse_args(
        ["--root", str(paths.root), "markets", "--json"])
    assert cli.cmd_markets(args_json) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["price_source"] == "yahoo", payload.get("price_source")
    assert payload["markets"], "реестр рынков пуст"
