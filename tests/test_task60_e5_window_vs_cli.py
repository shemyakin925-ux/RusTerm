"""ТЗ-60 E5: окно и CLI показывают одно и то же.

Самая дешёвая проверка правдивости десктопа — сравнение с CLI: значения
мер в окне совпадают байт-в-байт с тем, что даёт `rusterm export` для
той же меры и периода; где CLI говорит `missing_data: total_equity`,
окно говорит «нет данных», а панель источника называет тот же концепт.
Расхождение — красный тест с обоими значениями в сообщении; окно не
подгоняется под CLI и наоборот. Прогон по трём рынкам: US, CA, BR.

Правило отображения ячейки (полоса C, format_value) pinned отдельным
тестом: ячейка держит 4 знака, экспорт — полный precision; правило
зафиксировано с обоими значениями, а не спрятано.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,  # noqa: E402
                                 SnapshotRepo)

ROOT = Path(__file__).resolve().parents[1]

# рынок -> (эмитент, инструмент, концепты со значениями, грязное значение)
PLAN = {
    "US": ("i-us5", "US-A5", [("revenues_total", "100", "USD"),
                              ("ebitda_total", "1234.56789", "USD")]),
    "CA": ("i-ca5", "CA-C5", [("equity_total", "0.25", "CAD")]),
    "BR": ("i-br5", "BR-B5", [("gross_debt", "12.5", "BRL")]),
}
REFUSAL = ("CA", "i-ca5", "CA-C5", "total_equity",
           "missing_data: total_equity")


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for market, (issuer_id, iid, measures) in PLAN.items():
        repos.instrument.upsert_issuer(Issuer(
            issuer_id, f"Corp {market}", market, None, None,
            "us-gaap" if market == "US" else "ifrs-full", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer_id, None, "common", "active", None))
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, "2025-01-01",
                                       None, None, "ready")
        for n, (concept, value, unit) in enumerate(measures):
            repos.snapshot.insert_measure(
                f"m-{iid}-{n}", f"s-{iid}", "issuer", issuer_id, concept,
                value, unit, "2024-01-01", "2024-12-31", None,
                "t60-test", None, None)
    market, issuer_id, iid, concept, reason = REFUSAL
    repos.snapshot.insert_measure(
        f"m-{iid}-ref", f"s-{iid}", "issuer", issuer_id, concept,
        None, "CAD", "2024-01-01", "2024-12-31", None, "t60-test",
        reason, None)
    yield repos, paths
    conn.close()


def _export_measures(root: Path, iid: str) -> dict:
    """Настоящий `rusterm export --format json`: {concept: строка
    значения или None}; отказ несёт null_reason как в CLI."""
    env = dict(os.environ,
               RUSTERM_ENV_FILE=str(root / "empty.env"))
    proc = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(root),
         "export", "--instrument", iid, "--format", "json"],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    return {m["concept"]: m for m in payload["measures"]}


def test_window_cells_equal_export_byte_for_byte(catalog):
    """Каждое значение в окне байт-в-байт равно экспорту той же меры
    за тот же период; отказ — «нет данных» и тот же null_reason.
    Расхождение красит тест, назвав оба значения."""
    repos, paths = catalog
    for market, (issuer_id, iid, measures) in PLAN.items():
        table = desktop_data.measure_table_rows(repos, iid)
        window = {row["concept"]: row for row in table["measures"]}
        exported = _export_measures(paths.root, iid)
        assert set(window) == set(exported), (market, sorted(window))
        for concept, exported_row in exported.items():
            row = window[concept]
            row_period = row["measure"].get("period") or ""
            assert row_period == exported_row["period_end"], (
                market, concept, row_period,
                exported_row["period_end"])
            if exported_row["value"] is None:
                assert row["current"] == desktop_data.NO_DATA, (
                    market, concept, row["current"])
                assert row["null_reason"] == exported_row["null_reason"], (
                    market, concept)
            else:
                if row["current"] == exported_row["value"]:
                    continue
                # Правило отображения ячейки (format_value, 4 знака,
                # полоса C): то же число в принятом окне виде. Всё
                # прочее — расхождение, красим, назвав оба значения.
                assert row["current"] == desktop_data.format_value(
                    exported_row["value"]), (
                    f"{market} {concept}: окно {row['current']!r} != "
                    f"экспорт {exported_row['value']!r} и != "
                    f"format_value(экспорта)")


def test_refusal_names_concept_in_source_panel(catalog):
    """Где CLI говорит `missing_data: total_equity`, окно говорит
    «нет данных», а панель источника называет концепт по имени."""
    repos, paths = catalog
    _market, _issuer_id, iid, concept, reason = REFUSAL
    table = desktop_data.measure_table_rows(repos, iid)
    row = next(r for r in table["measures"] if r["concept"] == concept)
    assert row["current"] == desktop_data.NO_DATA
    assert row["null_reason"] == reason
    exported = _export_measures(paths.root, iid)
    assert exported[concept]["null_reason"] == reason
    panel = desktop_data.source_panel_view(
        repos, paths, row)["text"]
    assert f"причина: {reason}" in panel
    assert "не подан: total_equity" in panel


def test_display_rule_is_pinned_not_hidden(catalog):
    """Ячейка держит 4 знака (format_value), экспорт — полный
    precision: правило полосы C зафиксировано с обоими значениями,
    подгонки нет. Изменишь любую сторону — тест красный."""
    repos, paths = catalog
    _issuer_id, iid, measures = PLAN["US"]
    messy = "1234.56789"
    assert messy == dict((c, v) for c, v, _ in measures)["ebitda_total"]
    table = desktop_data.measure_table_rows(repos, iid)
    row = next(r for r in table["measures"]
               if r["concept"] == "ebitda_total")
    exported = _export_measures(paths.root, iid)["ebitda_total"]
    assert row["current"] == "1234.5679", row["current"]
    assert exported["value"] == messy, exported["value"]
