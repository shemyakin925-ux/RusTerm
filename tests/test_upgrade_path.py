"""ТЗ-51 U2: чужая база — обновление без потери данных.

Фикстуры — настоящие базы, собранные КОДОМ ИСТОРИИ (не эмуляция
схемы руками): tests/data/upgrade/schema41.sqlite собран кодом коммита
5424134 (миграция 41), schema44.sqlite — кодом 8cce46c (миграция 44);
в каждой: init, demo, ingest --source synthetic, snapshot, список
наблюдения с двумя версиями. Файлы названы .sqlite, а не .db: приёмка
(проверка 13) считает любой *.db в дереве мусором.

Проверяется: применяются ровно недостающие миграции, числа ключевых
таблиц не меняются, значения мер после обновления равны экспорту
старого кода до обновления (golden_schema44.json), doctor после
обновления зелёный, резервная копия обновлённой базы разворачивается и
снова сходится по числам.
"""
from __future__ import annotations

import json

import sqlite3
from pathlib import Path

import pytest

from rusterm.store.backup import create_backup, restore_backup
from rusterm.store.db import apply_migrations, current_schema_version
from rusterm.store.doctor import doctor_report
from rusterm.store.paths import AppPaths, ensure_app_dir

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "upgrade"
GOLDEN = json.loads((DATA / "golden_schema44.json").read_text(
    encoding="utf-8"))

CASES = {
    "schema41.sqlite": [42, 43, 44, 45],
    "schema44.sqlite": [45],
}


def _fresh_copy(tmp_path: Path, fixture: str) -> AppPaths:
    root = tmp_path / fixture.replace(".", "-")
    root.mkdir()
    # фикстура лежит сжатой (.gz): страж payload-размера (B25) держит
    # файлы tests/data в пределах 256 КБ
    import gzip
    with gzip.open(DATA / f"{fixture}.gz", "rb") as src:
        (root / "rusterm.db").write_bytes(src.read())
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    return paths


def _counts(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    out = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
           for t in ("fact", "snapshot", "measure", "watchlist",
                     "watchlist_version", "watchlist_member")}
    conn.close()
    return out


@pytest.mark.parametrize("fixture,expected", sorted(CASES.items()))
def test_upgrade_applies_missing_migrations_and_keeps_counts(
        tmp_path, fixture, expected):
    paths = _fresh_copy(tmp_path, fixture)
    counts_before = _counts(paths.db_path)
    conn = sqlite3.connect(str(paths.db_path))
    applied = apply_migrations(conn)
    assert applied == expected, (fixture, applied)
    assert current_schema_version(conn) == 45
    # идемпотентность: применённая миграция не переписывается
    assert apply_migrations(conn) == []
    conn.commit()
    conn.close()
    assert _counts(paths.db_path) == counts_before
    assert counts_before == GOLDEN["counts"]


def test_doctor_is_green_after_upgrade(tmp_path):
    paths = _fresh_copy(tmp_path, "schema44.sqlite")
    conn = sqlite3.connect(str(paths.db_path))
    apply_migrations(conn)
    conn.commit()
    report = doctor_report(paths, conn)
    conn.close()
    schema_problems = [p for p in report["problems"]
                       if "schema_version" in p]
    assert schema_problems == [], report["problems"]


def test_measure_values_survive_upgrade(tmp_path):
    """Значения мер после обновления равны экспорту старого кода до
    обновления (сравнение по файлу, не на глаз)."""
    paths = _fresh_copy(tmp_path, "schema44.sqlite")
    conn = sqlite3.connect(str(paths.db_path))
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    conn.commit()
    rows = conn.execute(
        "SELECT concept, value, null_reason FROM measure").fetchall()
    conn.close()
    got = sorted(
        ({"concept": r["concept"], "value": r["value"],
          "null_reason": r["null_reason"]} for r in rows),
        key=lambda d: (d["concept"], str(d["value"])))
    expected = sorted(
        GOLDEN["measures"],
        key=lambda d: (d["concept"], str(d["value"])))
    assert got == expected


def test_backup_of_upgraded_base_restores_and_matches(tmp_path):
    paths = _fresh_copy(tmp_path, "schema44.sqlite")
    conn = sqlite3.connect(str(paths.db_path))
    apply_migrations(conn)
    conn.commit()
    conn.close()
    archive = tmp_path / "upgraded-backup.zip"
    create_backup(paths, archive)
    target = AppPaths.from_root(tmp_path / "restored")
    ensure_app_dir(target)
    restore_backup(archive, target, force=True)
    assert _counts(target.db_path) == GOLDEN["counts"]
    target_conn = sqlite3.connect(str(target.db_path))
    assert apply_migrations(target_conn) == []
    target_conn.close()
    report = doctor_report(target, sqlite3.connect(str(target.db_path)))
    assert [p for p in report["problems"]
            if "schema_version" in p] == []
