"""ТЗ-96 R3: отказанный вендором запрос не должен исчезать из счётчика.

Живой прогон показал обратное: стадия «цены» сделала два вызова
(/time_series 200 и /splits 403), а `rusterm budget` и строка стадии
назвали один. Починка R2 поставила запись расхода на успех; этот тест
закрывает выход по отказу — и для котировок, и для корпоративных
событий, и для случая «сплиты пришли, дивиденды отказали» (гейт
накапливает вызовы, поэтому второй записи в той же стадии быть не
может: сумма сэмплов обязана остаться равным числом вызовов).

Офлайн: транспорт — словарь ответов, сеть не трогается; каталог в
`tmp_path`, окружение пользователя не читается (страж P7).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.cli import _build_parser
from rusterm.providers.twelvedata import TwelveDataProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths
from rusterm.store.repos import RepoRegistry

REPO = Path(__file__).resolve().parents[1]
TIMES = REPO / "tests/data/twelvedata/time_series_r3_AAPL_1000d.json"


def _transport(fail_on: str, calls: list):
    def send(url, headers):
        for kind in ("time_series", "/splits", "/dividends"):
            if kind in url:
                calls.append(kind)
                if kind == fail_on:
                    return 403, json.dumps(
                        {"code": "403", "status": "error"}).encode(), {}
                if kind == "time_series":
                    return 200, TIMES.read_bytes(), {}
                return 200, b'{"meta": {}, "splits": [], "dividends": []}', {}
        calls.append("unknown")
        return 404, b'{"status": "error"}', {}
    return send


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    # контакт SEC нужен самому гейту (заголовки), а не тесту: провайдера
    # тест подменяет, но гейт настоящий
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    assert cli.main(["--root", str(root), "add", "--ticker", "AAPL",
                     "--market", "US", "--cik", "320193",
                     "--name", "Apple Inc."]) == 0
    assert cli._requests_used(str(root)) == 0, "add с --cik/--name тянет сеть"
    return root


def _wire(monkeypatch, root, fail_on, calls):
    def fake(name, gate=None):
        if name == "twelvedata":
            return TwelveDataProvider(api_key="TESTONLY", gate=gate,
                                      transport=_transport(fail_on, calls))
        raise AssertionError(f"чужой провайдер не нужен: {name}")
    monkeypatch.setattr(cli, "get_provider", fake)


def _ingest(root):
    args = _build_parser().parse_args(
        ["--root", str(root), "ingest", "--source", "twelvedata",
         "--instrument", "US-AAPL"])
    return cli.cmd_ingest(args)


def test_refused_splits_are_still_counted(catalog, monkeypatch):
    root = catalog
    calls: list = []
    _wire(monkeypatch, root, "/splits", calls)
    assert _ingest(root) == 1
    assert calls == ["time_series", "/splits"], calls
    assert cli._requests_used(str(root)) == len(calls)


def test_refused_dividends_after_successful_splits_are_counted_once(
        catalog, monkeypatch):
    """Сплиты прошли, дивиденды отказали: гейт к этому моменту пропустил
    три вызова, и сумма сэмплов обязана остаться тремя — а не удвоиться
    из-за записи на успехе и на отказе."""
    root = catalog
    calls: list = []
    _wire(monkeypatch, root, "/dividends", calls)
    assert _ingest(root) == 1
    assert calls == ["time_series", "/splits", "/dividends"], calls
    assert cli._requests_used(str(root)) == len(calls)


def test_refused_quotes_are_counted(catalog, monkeypatch):
    """Только котировочная дверь: отказ /time_series — один пропущенный
    гейтом запрос, и он обязан быть в счётчике."""
    root = catalog
    calls: list = []
    _wire(monkeypatch, root, "time_series", calls)
    conn = sqlite3.connect(str(Path(root) / "rusterm.db"),
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, AppPaths.from_root(root))
    try:
        rc = cli._ingest_twelvedata_prices(repos, "US-AAPL",
                                           cli.args_as_of_default())
    finally:
        conn.close()
    assert rc == 1
    assert calls == ["time_series"], calls
    assert cli._requests_used(str(root)) == 1
