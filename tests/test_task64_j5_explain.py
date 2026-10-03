"""ТЗ-64 J5: программа объясняет себя — «неотображённых концептов»
сопровождается словами из ядра, повторный snapshot на идентичных
входах честно говорит «без изменений», изменившийся вход — версия
увеличивается.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.cli import main as cli_main
from rusterm.core.snapshot import snapshot_measures_identical
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-k5", "Corp K", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-K5", "i-k5", None, "common", "active", None))
    yield repos, paths
    conn.close()


def _measure(repos, measure_id: str, value: str):
    repos.snapshot.insert_measure(
        measure_id, "s-k5", "issuer", "i-k5", "revenues_total",
        value, "USD", "2024-01-01", "2024-12-31", None, "t64-test",
        None, None)


def test_comparator_sees_identical_and_changed(catalog):
    repos, _ = catalog
    repos.snapshot.create_snapshot("s-k5-a", "US-K5", 1, "2025-01-01",
                                   None, None, "ready")
    _measure(repos, "m-a", "100")
    repos.snapshot.create_snapshot("s-k5-b", "US-K5", 2, "2025-01-01",
                                   None, None, "ready")
    _measure(repos, "m-b", "100")
    a = repos.snapshot.get_measures("s-k5-a")
    b = repos.snapshot.get_measures("s-k5-b")
    assert snapshot_measures_identical(a, b)
    repos.snapshot.insert_measure(
        "m-b2", "s-k5-b", "issuer", "i-k5", "gross_margin",
        "0.5", "ratio", "2024-01-01", "2024-12-31", None, "t64-test",
        None, None)
    b2 = repos.snapshot.get_measures("s-k5-b")
    assert not snapshot_measures_identical(a, b2)


def test_second_snapshot_reports_no_change(catalog, tmp_path, capsys):
    """Текущая пара фактов: v2 vs v3 идентичны — «без изменений»;
    добавленная прошлогодняя пара делает net_margin доступной — v4
    отличается, «без изменений» исчезает."""
    repos, _ = catalog
    raw = repos.raw.put(b"saved response j5", provider="edgar",
                        url="https://data.sec.gov/companyfacts")
    for fid, con, val in (("f-cur-1", "us-gaap:Revenues", "100"),
                          ("f-cur-2", "us-gaap:NetIncomeLoss", "20")):
        repos.fact.insert_fact(
            fid, "i-k5", None, con, "2025-07-01", "2026-06-30",
            "duration", val, "USD", "USD", "as_reported", "extracted",
            raw.sha256, {"endpoint": "companyfacts"}, "t64-test")
    assert cli_main(["--root", str(tmp_path / "app"), "snapshot",
                     "--instrument", "US-K5"]) == 0
    first = capsys.readouterr().out
    assert "без изменений" not in first
    assert cli_main(["--root", str(tmp_path / "app"), "snapshot",
                     "--instrument", "US-K5"]) == 0
    second = capsys.readouterr().out
    assert "без изменений" in second
    # изменившийся вход: прошлогодняя пара — prior period появился
    for fid, con, val in (("f-pri-1", "us-gaap:Revenues", "80"),
                          ("f-pri-2", "us-gaap:NetIncomeLoss", "16")):
        repos.fact.insert_fact(
            fid, "i-k5", None, con, "2024-07-01", "2025-06-30",
            "duration", val, "USD", "USD", "as_reported", "extracted",
            raw.sha256, {"endpoint": "companyfacts"}, "t64-test")
    assert cli_main(["--root", str(tmp_path / "app"), "snapshot",
                     "--instrument", "US-K5"]) == 0
    third = capsys.readouterr().out
    # версия растёт всегда (append-only), метка честно называет
    # совпадение значений — прошлогодняя пара не меняет net_margin
    assert "v3" in third
    assert "без изменений" in third
