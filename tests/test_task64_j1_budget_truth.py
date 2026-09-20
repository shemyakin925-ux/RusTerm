"""ТЗ-64 J1: счётчик запросов перестаёт врать.

Сколько RequestGate пропустил — столько и показано: запись расхода
идёт из гейта (_record_gate_usage), budget/status читают сумму сэмплов.
Равенство проверяется на подставных запросах через настоящий гейт,
без сети.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from rusterm.cli import _record_gate_usage, main as cli_main
from rusterm.providers.budget import RequestGate
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import RepoRegistry


@pytest.fixture()
def catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("RUSTERM_SEC_UA", "test contact t64")
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    yield RepoRegistry(conn, paths), tmp_path / "app"
    conn.close()


def _gate_makes(gate: RequestGate, n: int) -> None:
    for _ in range(n):
        outcome = gate.request(lambda headers: "ok")
        assert outcome == "ok"


def test_display_equals_gate_calls(catalog):
    """Равенство: сколько гейт пропустил — столько и в budget, по
    хостам и в сумме."""
    repos, _ = catalog
    edgar_gate = RequestGate()
    _gate_makes(edgar_gate, 3)
    _record_gate_usage(repos, "edgar", edgar_gate)
    tw_gate = RequestGate()
    _gate_makes(tw_gate, 2)
    _record_gate_usage(repos, "twelvedata", tw_gate)

    assert edgar_gate.calls_made == 3
    assert tw_gate.calls_made == 2
    rows = {s[2]: float(s[3]) for s in repos.metrics.samples()
            if s[1] == "provider_requests_used"}
    assert rows == {"edgar": 3.0, "twelvedata": 2.0}


def test_budget_json_carries_real_used(catalog, capsys):
    repos, root = catalog
    gate = RequestGate()
    _gate_makes(gate, 3)
    _record_gate_usage(repos, "edgar", gate)
    assert cli_main(["--root", str(root), "budget", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["used"] == gate.calls_made == 3
    assert payload["samples"]["provider_requests_used"] == 3.0


def test_status_json_carries_used(catalog, capsys):
    repos, root = catalog
    gate = RequestGate()
    _gate_makes(gate, 2)
    _record_gate_usage(repos, "edgar", gate)
    assert cli_main(["--root", str(root), "status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["budget"]["used"] == 2


def test_no_gate_no_lie(catalog, capsys):
    """Без запросов used = 0 и не выдумывается."""
    repos, root = catalog
    assert cli_main(["--root", str(root), "budget", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["used"] == 0
    assert payload["samples"] == {}
