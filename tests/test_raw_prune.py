"""BACKLOG B28: чистка raw store удаляет только объекты без ссылок.

Ссылки — факт (fact.source_ref) и импортированный документ
(document.sha256). Оба направления: строка+файл без ссылок удаляется,
файл без строки удаляется; всё, на что есть ссылка, переживает чистку
вместе с .zst/.gz вариантами. Манифест append-only не правится.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.raw_store import has_object, prune_raw_store, \
    put_with_manifest
from rusterm.store.repos import RepoRegistry


def _setup():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    return tmpdir, paths, conn, repos


def test_prune_removes_only_unreferenced_in_both_directions():
    tmpdir, paths, conn, repos = _setup()
    try:
        sha_a = repos.raw.put(b"referenced by a fact", provider="edgar",
                              block="fundamentals").sha256
        sha_b = repos.raw.put(b"referenced by a document",
                              provider="edgar", block="fundamentals").sha256
        sha_c = repos.raw.put(b"unreferenced object", provider="edgar",
                              block="fundamentals").sha256

        # факт на A и документ на B — оба выживают
        conn.execute(
            "INSERT INTO fact(fact_id, issuer_id, concept, period_start,"
            " period_end, period_type, unit, basis, origin, source_ref,"
            " locator, parser_version, status, ingested_at)"
            " VALUES ('f1','i1','Revenues','2024-01-01','2024-12-31',"
            " 'duration','USD','as_reported','extracted',?, 'l','p.v1',"
            " 'ok',0)", (sha_a,))
        repos.document.put(sha_b, "annual.txt", "txt", 3, 40)

        # осиротевший файл без строки в базе
        orphan_dir = paths.raw_store / "dd"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        (orphan_dir / ("d" * 64)).write_bytes(b"orphan bytes")

        report = prune_raw_store(paths, conn)

        assert report["removed_objects"] == 1   # только C
        assert report["removed_files"] == 1     # только осиротевший файл
        assert report["kept_objects"] == 2      # A и B
        assert has_object(paths.raw_store, sha_a)
        assert has_object(paths.raw_store, sha_b)
        assert not has_object(paths.raw_store, sha_c)
        assert not (orphan_dir / ("d" * 64)).exists()
        # строка C ушла из базы, строки A и B на месте
        n = conn.execute("SELECT COUNT(*) FROM raw_object").fetchone()[0]
        assert n == 2
    finally:
        conn.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_prune_is_idempotent_and_second_pass_removes_nothing():
    tmpdir, paths, conn, repos = _setup()
    try:
        sha = repos.raw.put(b"kept payload", provider="edgar",
                            block="fundamentals").sha256
        conn.execute(
            "INSERT INTO fact(fact_id, issuer_id, concept, period_start,"
            " period_end, period_type, unit, basis, origin, source_ref,"
            " locator, parser_version, status, ingested_at)"
            " VALUES ('f1','i1','Revenues','2024-01-01','2024-12-31',"
            " 'duration','USD','as_reported','extracted',?, 'l','p.v1',"
            " 'ok',0)", (sha,))
        first = prune_raw_store(paths, conn)
        assert first["removed_objects"] == 0
        second = prune_raw_store(paths, conn)
        assert second == {"removed_objects": 0, "removed_files": 0,
                          "kept_objects": 1}
        assert has_object(paths.raw_store, sha)
    finally:
        conn.close()
        shutil.rmtree(tmpdir, ignore_errors=True)
