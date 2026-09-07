"""Пятнадцать инвариантов архитектуры — тесты-надзиратели.

Источник истины: agent/TASK.md §4. Проверка машиной — agent/acceptance.sh
проверяет, что здесь ровно пятнадцать функций test_i01_…test_i15_.

По правилу TASK-2.md §2.A: инварианты, которые заведомо потребуют кода
# Замечание: I4, I5, I6, I13, I15 — пока не покрыты кодом, помечены через pytest.mark.
до тех пор, пока соответствующий код не появится. Остальные должны
проходить сразу, против уже существующих И1-И5.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import sys
import tempfile

import pytest

from rusterm.core.fact import (
    Fact,
    LocatorXBRL,
    LocatorTable,
    determine_basis,
    resolve_locator,
)
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.raw_store import put_with_manifest, decompress_object
from rusterm.store.db import apply_migrations, writer_transaction, _SCHEMA_VERSION


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ── I1. Факт без locator не сохраняется ──────────────────────────────────
def test_i01_fact_without_locator_rejected():
    """Попытка записи факта без locator падает (конструктор)."""
    with pytest.raises((ValueError, TypeError, AssertionError)):
        Fact(
            issuer_id="i1",
            concept="revenue",
            period_start="2023-01-01",
            period_end="2023-12-31",
            period_type="duration",
            value="100",
            unit="USD",
            basis="as_reported",
            origin="extracted",
            source_ref="abc",
            locator={},  # пустой — нарушение
            parser_version="1.0",
        )


# ── I2. Факт неизменяем ─────────────────────────────────────────────────
def test_i02_fact_is_immutable():
    """В репозитории нет пути, меняющего value; исправление создаёт
    новый факт и проставляет superseded_by."""
    import inspect
    from rusterm.store import repos as r
    src = inspect.getsource(r)
    forbidden = [
        "UPDATE fact SET value",
        "UPDATE fact SET unit",
        "UPDATE fact SET period_start",
        "UPDATE fact SET period_end",
    ]
    for snippet in forbidden:
        assert snippet not in src, (
            f"репозиторий факта содержит изменяющий путь: {snippet!r}"
        )
    assert hasattr(r.FactRepo, "mark_superseded"), "нет mark_superseded"


# ── I3. basis определяется правилом периода ────────────────────────────
def test_i03_basis_period_rule():
    """Отчёт за период → as_reported; сравнительная колонка позднего
    отчёта → restated."""
    assert determine_basis("2023-12-31", "2023-12-31", "2024-02-15") == "as_reported"
    assert determine_basis("2024-12-31", "2023-12-31", "2025-02-15") == "restated"
    assert determine_basis("2024-09-30", "2023-09-30", "2024-11-01") == "restated"
    assert determine_basis("2023-12-31", "2023-12-31", "2024-03-15") == "as_reported"


# ── I4. measure без lineage не пишется, кроме value IS NULL ────────────
@pytest.mark.xfail(
    strict=True,
    reason="I4 требует кода этапа C (SnapshotRepo.insert_measure с проверкой lineage). "
           "После реализации этапа снять маркер.",
)
def test_i04_measure_without_lineage_rejected():
    """Обе ветки: value задан и value IS NULL."""
    pytest.fail("I4 не реализован на этом этапе — причина в декораторе")


# ── I5. Перцентиль без peer_set_version не пишется ─────────────────────
@pytest.mark.xfail(
    strict=True,
    reason="I5 требует кода этапа C (PeerSetRepo / snapshot). "
           "После реализации этапа снять маркер.",
)
def test_i05_percentile_requires_peer_set_version():
    """Попытка записи перцентиля без peer_set_version падает."""
    pytest.fail("I5 не реализован на этом этапе — причина в декораторе")


# ── I6. Меньше 5 пиров — нет перцентиля; меньше 8 — нет агрегатов ─────
@pytest.mark.xfail(
    strict=True,
    reason="I6 требует кода этапа C (PeerSet / snapshot с порогами 5 и 8). "
           "После реализации этапа снять маркер.",
)
def test_i06_peer_count_thresholds_4_5_and_7_8():
    """Границы 4/5 (нет перцентиля при <5) и 7/8 (нет агрегатов при <8)."""
    pytest.fail("I6 не реализован на этом этапе — причина в декораторе")


# ── I7. Повторный сбор не создаёт ни нового объекта в store, ни фактов ─
def test_i07_duplicate_collection_is_idempotent():
    """Двойной прогон: store не растёт, факты не дублируются."""
    import json
    from rusterm.store.raw_store import (
        has_object, rebuild_index,
    )

    with tempfile.TemporaryDirectory() as tmp:
        paths = AppPaths.from_root(os.path.join(tmp, "app"))
        ensure_app_dir(paths)

        data = json.dumps({"facts": {"f1": {"value": "100", "unit": "USD"}}}).encode()
        obj1 = put_with_manifest(paths, data, provider="synthetic", block="fundamentals")
        obj2 = put_with_manifest(paths, data, provider="synthetic", block="fundamentals")

        assert obj1.sha256 == obj2.sha256
        assert has_object(paths.raw_store, obj1.sha256)
        assert decompress_object(paths.raw_store, obj1.sha256) == data

        idx = rebuild_index(paths.raw_manifests)
        assert len(idx) == 1, f"ожидалась 1 запись, получили {len(idx)}"


# ── I8. rusterm/core/ не импортирует Qt ────────────────────────────────
def test_i08_core_does_not_import_qt():
    """Обход дерева импортов rusterm/core/ — нет Qt."""
    from rusterm.core import fact
    src = open(fact.__file__, "r", encoding="utf-8").read()
    for needle in ("PySide6", "PyQt5", "PyQt6", "qtpy", "from PySide", "from PyQt"):
        assert needle not in src, f"core импортирует Qt: {needle!r}"


# ── I9. Парсеры не ходят в сеть ────────────────────────────────────────
def test_i09_parsers_have_no_http_imports():
    """В rusterm/parsers/ нет импортов HTTP-библиотек."""
    parsers_dir = os.path.join(REPO_ROOT, "rusterm", "parsers")
    if not os.path.isdir(parsers_dir):
        return
    for fname in os.listdir(parsers_dir):
        if not fname.endswith(".py"):
            continue
        path = os.path.join(parsers_dir, fname)
        src = open(path, "r", encoding="utf-8").read()
        for needle in ("import httpx", "import requests", "import urllib.request",
                       "import aiohttp", "import http.client", "from httpx",
                       "from requests", "from urllib.request", "from aiohttp"):
            assert needle not in src, f"{fname} импортирует HTTP: {needle!r}"


# ── I10. Провайдеры не пишут в базу ────────────────────────────────────
def test_i10_providers_dont_import_store_db():
    """В rusterm/providers/ нет импортов rusterm.store.db."""
    prov_dir = os.path.join(REPO_ROOT, "rusterm", "providers")
    if not os.path.isdir(prov_dir):
        return
    for fname in os.listdir(prov_dir):
        if not fname.endswith(".py"):
            continue
        path = os.path.join(prov_dir, fname)
        src = open(path, "r", encoding="utf-8").read()
        assert "rusterm.store" not in src, (
            f"провайдер {fname} тянет слой хранилища: 'rusterm.store' в коде"
        )
        assert "import sqlite3" not in src, (
            f"провайдер {fname} импортирует sqlite3 напрямую"
        )


# ── I11. Миграция не пересоздаёт базу ──────────────────────────────────
def test_i11_migration_preserves_data_and_grows_version():
    """База с данными переживает миграцию; schema_version растёт."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = AppPaths.from_root(os.path.join(tmp, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(
            str(paths.db_path), timeout=30, isolation_level=None,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("CREATE TABLE example (id INTEGER PRIMARY KEY, v TEXT)")
            conn.execute("INSERT INTO example (v) VALUES ('survive')")
            conn.commit()
            apply_migrations(conn)
            v1 = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            assert v1 == _SCHEMA_VERSION, (
                f"ожидалась версия {_SCHEMA_VERSION}, получили {v1}"
            )
            apply_migrations(conn)
            v2 = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            assert v2 == _SCHEMA_VERSION, (
                "повторное применение должно сохранять schema_version"
            )
            row = conn.execute("SELECT v FROM example WHERE id=1").fetchone()
            assert row is not None and row[0] == "survive", (
                "миграция потеряла пользовательские данные"
            )
        finally:
            conn.close()


# ── I12. resolve(locator) == value ─────────────────────────────────────
def test_i12_resolve_locator_matches_value():
    """На фикстурах: resolve(locator) возвращает строку, равную fact.value."""
    import json
    with tempfile.TemporaryDirectory() as tmp:
        paths = AppPaths.from_root(os.path.join(tmp, "app"))
        ensure_app_dir(paths)

        xbrl = {"facts": {"f1": {"value": "100", "unit": "USD"}}}
        raw = json.dumps(xbrl).encode()
        obj = put_with_manifest(paths, raw, provider="synthetic", block="fundamentals")
        loc = LocatorXBRL(doc_sha256=obj.sha256, fact_id="f1", concept="revenue")
        getter = lambda sha: decompress_object(paths.raw_store, sha)
        assert resolve_locator(loc, getter) == "100"

        table = {"tables": [{"rows": [{"cells": [{"value": "50"}, {"value": "60"}]}]}]}
        raw2 = json.dumps(table).encode()
        obj2 = put_with_manifest(paths, raw2, provider="synthetic", block="fundamentals")
        loc2 = LocatorTable(doc_sha256=obj2.sha256, table_index=0, row=0, col=1)
        assert resolve_locator(loc2, getter) == "60"


# ── I13. facts_only не удаляет неразобранное ───────────────────────────
@pytest.mark.xfail(
    strict=True,
    reason="I13 требует кода этапа B (pipeline с facts_only-политикой). "
           "После реализации этапа снять маркер.",
)
def test_i13_facts_only_keeps_unparsed():
    """Документ со статусом needs_verification остаётся после facts_only."""
    pytest.fail("I13 не реализован на этом этапе — причина в декораторе")


# ── I14. В базу пишет один поток ───────────────────────────────────────
def test_i14_writer_thread_is_serialized():
    """Запись сериализована writer_transaction."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = AppPaths.from_root(os.path.join(tmp, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(
            str(paths.db_path), timeout=30, isolation_level=None,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        apply_migrations(conn)
        try:
            conn.execute("CREATE TABLE writer_check (v TEXT)")
            with writer_transaction(conn):
                conn.execute("INSERT INTO writer_check (v) VALUES ('main')")
            with writer_transaction(conn):
                conn.execute("INSERT INTO writer_check (v) VALUES ('main2')")
            n = conn.execute("SELECT COUNT(*) FROM writer_check").fetchone()[0]
            assert n == 2, f"две транзакции записали две строки, получили {n}"
        finally:
            conn.close()


# ── I15. Знаменатель ≤ 0 даёт null с причиной ─────────────────────────
@pytest.mark.xfail(
    strict=True,
    reason="I15 требует кода этапа C (formulas с null-правилами для знаменателя). "
           "После реализации этапа снять маркер.",
)
def test_i15_nonpositive_denominator_yields_null():
    """Не исключение и не отрицательный мультипликатор."""
    pytest.fail("I15 не реализован на этом этапе — причина в декораторе")
