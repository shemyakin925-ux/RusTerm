"""ТЗ-65 K5: два счёта бюджета названы, а не спрятаны. Всего за жизнь
каталога против последней пробы гейта: при трёх пробах числа
расходятся и подписи/ключи не путаются."""
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
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    yield RepoRegistry(conn, paths), tmp_path / "app"
    conn.close()


def test_three_probes_diverge_and_labels_hold(catalog, capsys):
    repos, root = catalog
    import time
    for n, spent in enumerate((5, 3, 0)):
        repos.metrics.record_sample(
            time.time() + n, "provider_requests_used", "edgar",
            float(spent))
    assert cli_main(["--root", str(root), "budget"]) == 0
    out = capsys.readouterr().out
    assert "использовано запросов за жизнь каталога: 8" in out
    assert "последняя проба гейта: provider_requests_used = 0" in out
    assert cli_main(["--root", str(root), "budget", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["used_total"] == 8
    assert payload["last_probe"] == 0.0
    assert payload["used"] == 8  # обратная совместимость
