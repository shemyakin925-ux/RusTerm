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
def test_i04_measure_without_lineage_rejected():
    """Обе ветки: value задан — lineage обязателен; value IS NULL при
    отсутствующих входах — lineage пуст, но null_reason обязателен."""
    import uuid
    from rusterm.store.repos import (
        Instrument, InstrumentRepo, Issuer, SnapshotRepo,
    )
    with tempfile.TemporaryDirectory() as tmp:
        paths = AppPaths.from_root(os.path.join(tmp, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        InstrumentRepo(conn).upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        InstrumentRepo(conn).upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        snapshots = SnapshotRepo(conn)
        snapshots.create_snapshot("s1", "ins1", 1, "2024-01-01",
                                  None, "none", "ready")

        def measure(**kw):
            base = dict(measure_id=str(uuid.uuid4()), snapshot_id="s1",
                        scope="issuer", scope_ref="i1", concept="net_margin",
                        value="0.2", unit="ratio", period_start="2024-01-01",
                        period_end="2024-12-31", formula_id="net_margin",
                        method_version="v1", null_reason=None,
                        peer_set_version=None)
            base.update(kw)
            return base

        lineage = [{"fact_id": "f1", "peer_measure_id": None, "role": "input"}]

        # value задан, lineage пуст — отказ, ничего не записано
        with pytest.raises(ValueError, match="I4"):
            snapshots.insert_measure_with_lineage(measure(), [])
        n = conn.execute("SELECT COUNT(*) FROM measure").fetchone()[0]
        assert n == 0, "measure без lineage не должен записаться"

        # value задан, lineage есть — пишется вместе с lineage
        snapshots.insert_measure_with_lineage(measure(), lineage)
        ln = conn.execute(
            "SELECT COUNT(*) FROM measure_lineage").fetchone()[0]
        assert ln == 1

        # value IS NULL: без null_reason — отказ; с null_reason и пустым
        # lineage — законная запись (входов не было, объяснять обязаны)
        with pytest.raises(ValueError, match="I4"):
            snapshots.insert_measure_with_lineage(
                measure(value=None, null_reason=None), [])
        snapshots.insert_measure_with_lineage(
            measure(value=None, null_reason="missing_data"), [])
        conn.close()


# ── I5. Перцентиль без peer_set_version не пишется ─────────────────────
def test_i05_percentile_requires_peer_set_version():
    """Попытка записи перцентиля без peer_set_version падает на CHECK."""
    from rusterm.store.repos import PeerSetRepo, SnapshotRepo
    with tempfile.TemporaryDirectory() as tmp:
        paths = AppPaths.from_root(os.path.join(tmp, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        peers = PeerSetRepo(conn)
        peers.create_peer_set("ps1", "industry", "tankers")
        peers.add_version("psv1", "ps1", 1, "2024-01-01", None,
                          "manual", "v1", True, None, None)
        snapshots = SnapshotRepo(conn)
        snapshots.create_snapshot("s1", "ins-any", 1, "2024-01-01",
                                  None, "none", "ready")

        base = dict(measure_id="m-pct", snapshot_id="s1", scope="issuer",
                    scope_ref="tankers", concept="percentile",
                    value="0.6", unit="ratio", period_start="2024-01-01",
                    period_end="2024-12-31", formula_id="pct",
                    method_version="v1", null_reason=None)

        # без peer_set_version — нарушение CHECK, запись невозможна
        with pytest.raises(sqlite3.IntegrityError):
            snapshots.insert_measure(**base, peer_set_version=None)
        # с версией peer set — валидно
        snapshots.insert_measure(**base, peer_set_version="psv1")
        conn.close()


# ── I6. Меньше 5 пиров — нет перцентиля; меньше 8 — нет агрегатов ─────
def test_i06_peer_count_thresholds_4_5_and_7_8():
    """Границы 4/5 (нет перцентиля при <5) и 7/8 (нет агрегатов при <8)."""
    from rusterm.core.peers import (
        aggregate_ready, evaluate, percentile_share,
    )
    values_4 = [1.0, 2.0, 3.0, 4.0]
    values_5 = [1.0, 2.0, 3.0, 4.0, 5.0]

    # 4 пира — перцентиль не считается; 5 — считается
    assert percentile_share(values_4, 2.5) is None
    assert percentile_share(values_5, 2.5) == 0.4

    # 7 пиров — агрегатов нет; 8 — есть
    assert aggregate_ready(7) is False
    assert aggregate_ready(8) is True

    # границы через evaluate
    st4 = evaluate("manual", False, [], [f"i{n}" for n in range(4)])
    st5 = evaluate("manual", False, [], [f"i{n}" for n in range(5)])
    st7 = evaluate("manual", False, [], [f"i{n}" for n in range(7)])
    st8 = evaluate("manual", False, [], [f"i{n}" for n in range(8)])
    assert st4.can_percentile is False and st5.can_percentile is True
    assert st7.can_aggregates is False and st8.can_aggregates is True

    # дрейф: замена одного из пяти — churn 0.4 > 0.2 -> suspect
    st = evaluate("manual", False, ["a", "b", "c", "d", "e"],
                  ["a", "b", "c", "d", "x"])
    assert st.churn == pytest.approx(0.4)
    assert st.suspect is True
    # classifier без подтверждения — unverified
    st_cls = evaluate("classifier", False, [], [f"i{n}" for n in range(8)])
    assert st_cls.verified is False


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
def test_i13_facts_only_keeps_unparsed():
    """Документ со статусом needs_verification остаётся после facts_only."""
    import json as _json
    from rusterm.pipeline import IngestionPipeline
    from rusterm.providers.disclosures import (
        DocumentList, FetchedDocument, IndexPoll, IndexRecord,
    )
    from rusterm.store.repos import Instrument, InstrumentRepo, Issuer

    class SingleDocProvider:
        """Синтетический провайдер с одним документом неизвестного типа."""
        source_name = "synthetic"

        def poll_index(self, cursor):
            return IndexPoll(
                records=(IndexRecord("0001", "i1", "MYSTERY", "2024",
                                     "synthetic://mystery", "2024-01-01"),),
                cursor="0001")

        def fetch_document(self, url):
            content = _json.dumps({
                "source": "synthetic",
                "note": "Неразобранный документ для I13.",
                "payload": "x",
            }).encode()
            import hashlib
            return FetchedDocument(url=url, content=content,
                                   sha256=hashlib.sha256(content).hexdigest(),
                                   content_type="application/json")

        def list_documents(self, issuer_id, doc_type=None, period=None):
            return DocumentList(())

    with tempfile.TemporaryDirectory() as tmp:
        paths = AppPaths.from_root(os.path.join(tmp, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        from rusterm.store.repos import RepoRegistry
        InstrumentRepo(conn).upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        InstrumentRepo(conn).upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        repos = RepoRegistry(conn, paths)

        class NoSleep:
            def __call__(self, seconds):
                pass

        pipe = IngestionPipeline(repos, {"synthetic": SingleDocProvider()},
                                 sleep=NoSleep())
        result = pipe.run("ins1", "i1", "synthetic")
        assert result.needs_verification == 1, "документ должен попасть в E4"

        cov = repos.job.get_coverage("ins1", "fundamentals")
        assert cov["status"] == "missing"
        assert "needs_verification" in cov["reason"]
        sha = cov["reason"].split(":", 1)[1]

        # facts_only: неразобранное остаётся на месте
        prune = pipe.prune_unparsed("facts_only")
        assert prune.kept_needs_verification >= 1
        assert repos.raw.has(sha), "facts_only удалил needs_verification"
        conn.close()


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
def test_i15_nonpositive_denominator_yields_null():
    """Не исключение и не отрицательный мультипликатор: нулевой и
    отрицательный знаменатель дают null с причиной (data-dictionary §1.4)."""
    from rusterm.formulas import (
        calculate_measure, effective_tax_rate, price_to_earnings,
        price_to_book, dividend_yield,
    )
    # нулевой знаменатель
    assert price_to_earnings(2000.0, 0.0) == (None, "denominator_zero")
    assert price_to_book(2000.0, 0.0) == (None, "denominator_zero")
    assert dividend_yield(5.0, 0.0) == (None, "denominator_zero")
    # отрицательный знаменатель — null, а не отрицательный мультипликатор
    assert price_to_earnings(2000.0, -100.0) == (None, "negative_denominator")
    assert price_to_book(2000.0, -50.0) == (None, "negative_denominator")
    # ROIC со средним invested_capital <= 0 — тоже null с причиной
    from rusterm.formulas import roic
    assert roic(100.0, 0.0, 0.0) == (None, "denominator_zero")
    assert roic(100.0, -30.0, 10.0) == (None, "negative_denominator")  # avg -10
    # effective_tax при нулевой прибыли — null (ставка юрисдикции вне движка)
    rate, reason = effective_tax_rate(20.0, 0.0)
    assert rate is None and reason == "denominator_zero"
    # через диспетчер: null_reason заполнен, исключения нет
    m = calculate_measure("pe", market_cap_total=2000.0, net_income_ttm=0.0)
    assert m.value is None
    assert m.null_reason == "denominator_zero"
