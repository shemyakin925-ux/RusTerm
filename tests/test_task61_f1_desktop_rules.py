"""ТЗ-61 F1: десктоп под общими правилами ядра.

1. Ни одной новой причины мимо словаря: обход по коду rusterm/desktop/
   тем же сканером, что у ТЗ-B1 (позиции причин: keyword/имена/ключи
   *reason*, пары-возвраты) — токен вне словаря мер и вне allowlist
   чужих областей красит тест. Не список из пяти — обход.
2. Округление и форматирование ячейки не меняют значения: ячейка
   держит ровно 4 знака (format_value) и совпадает с экспортом в
   этих пределах; полный precision живёт в экспорте байт-в-байт.
   Мера, где третий знак важен: 0.0012345.
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

from rusterm.cli import main as cli_main  # noqa: E402
from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.reasons import NULL_REASONS  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,  # noqa: E402
                                 SnapshotRepo)

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "rusterm" / "desktop"

from tests.test_b1_reasons import ALLOWED_NON_MEASURE, _collect  # noqa: E402


def test_desktop_refusal_tokens_stay_in_the_vocabulary():
    """Обход по коду: каждая строка в позиции причины где-либо в
    rusterm/desktop/ — в словаре мер или в allowlist чужих областей.
    Новый канал с новой причиной красит этот тест."""
    unknown: dict[str, list[str]] = {}
    for path in sorted(PKG.rglob("*.py")):
        for lineno, token in _collect(path):
            if token not in NULL_REASONS \
                    and token not in ALLOWED_NON_MEASURE:
                unknown.setdefault(token, []).append(
                    f"{path.name}:{lineno}")
    assert not unknown, (
        "десктоп вернул причину мимо словаря (заведи в reasons.py или "
        f"обоснуй область в тесте B1): {unknown}")


def test_walker_catches_a_made_up_desktop_reason(tmp_path):
    """Красная демонстрация: выдуманная причина в CollectOutcome
    позиция обязательна попадает в обход (механика, не память)."""
    fake = tmp_path / "fake_desktop.py"
    fake.write_text(
        "def act():\n"
        "    return CollectOutcome(ok=False,\n"
        "                          reason='desktop_made_up_reason')\n",
        encoding="utf-8")
    tokens = {token for _, token in _collect(fake)}
    assert "desktop_made_up_reason" in tokens
    assert "desktop_made_up_reason" not in NULL_REASONS
    assert "desktop_made_up_reason" not in ALLOWED_NON_MEASURE


# ── округление ячейки не меняет значения ─────────────────────────────────

VALUES = ("1.23456789", "0.0012345")


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-us9", "Corp US", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-N9", "i-us9", None, "common", "active", None))
    repos.snapshot.create_snapshot("s-us9", "US-N9", 1, "2025-01-01",
                                   None, None, "ready")
    for n, value in enumerate(VALUES):
        repos.snapshot.insert_measure(
            f"m-us9-{n}", "s-us9", "issuer", "i-us9",
            f"measure_{n}", value, "ratio", "2024-01-01", "2024-12-31",
            None, "t61-test", None, None)
    yield repos, paths
    conn.close()


def _export_values(root: Path, iid: str) -> dict:
    env = dict(os.environ, RUSTERM_ENV_FILE=str(root / "empty.env"))
    proc = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(root),
         "export", "--instrument", iid, "--format", "json"],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return {m["concept"]: m["value"]
            for m in json.loads(proc.stdout)["measures"]}


def test_cell_rounding_keeps_the_value(catalog, tmp_path):
    """Ячейка = format_value значения (ровно 4 знака) и не меняет
    значение в этих пределах; третий знак у малой меры совпадает с
    экспортом; полный precision живёт в экспорте байт-в-байт."""
    repos, paths = catalog
    table = desktop_data.measure_table_rows(repos, "US-N9")
    exported = _export_values(tmp_path / "app", "US-N9")
    for n, value in enumerate(VALUES):
        concept = f"measure_{n}"
        row = next(r for r in table["measures"]
                   if r["concept"] == concept)
        cell = row["current"]
        # правило отображения: ровно format_value значения
        assert cell == desktop_data.format_value(value), (
            concept, cell, value)
        # округление, не искажение: ячейка = значение, сжатое до 4
        # знаков, без дрейфа двоичной арифметики
        assert float(cell) == round(float(value), 4), (concept, cell)
        # полный precision живёт в экспорте, не в ячейке
        assert exported[concept] == value, (concept, exported[concept])
    # мера, где третий знак важен: 0.0012345 -> ячейка 0.0012
    small = next(r for r in table["measures"]
                 if r["concept"] == "measure_1")
    assert small["current"] == "0.0012", small["current"]
    assert small["current"].split(".")[1][2] \
        == VALUES[1].split(".")[1][2] == "1"
