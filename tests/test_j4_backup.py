"""ТЗ-22 J4: данные, которых больше нигде нет — backup/restore.

Ручной факт нельзя скачать заново; копия обязана переживать_round-trip
побайтно (включая locator и lineage), отказываться разворачивать
повреждённый архив, архив с будущей схемой и писать в непустой каталог
без --force.
"""
from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.store.backup import (BackupError, create_backup,
                                   restore_backup)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import DocumentRepo, Instrument, Issuer, \
    RepoRegistry, SnapshotRepo


def _seed(root, with_manual_fact: bool = True):
    """База с эмитентом, снапшотом, мерой с lineage, ручным фактом,
    документом, watchlist'ом — то, что должно пережить round-trip."""
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "cik-1", "Corp", "US", "1", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-C", "cik-1", None, "common", "active", None))
    repos.watchlist.create_watchlist("wl", "Основной", None, None)
    repos.watchlist.new_version("wlv", "wl", 1, "create", None)
    repos.watchlist.add_member("wlv", "US-C", "первый")
    obj = repos.raw.put(b"manual document body bytes",
                        provider="manual-import", block="manual")
    DocumentRepo(conn).put(obj.sha256, "annual.pdf", "pdf", 3,
                           len(b"manual document body bytes"),
                           issuer_id="cik-1")
    if with_manual_fact:
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at, canonical_concept,
               source_kind) VALUES ('f-man', 'cik-1', 'revenue',
               '2024-01-01', '2024-12-31', 'duration', '777', 'USD',
               'USD', 'as_reported', 'manual', ?, ?,
               'manual.v1', 'ok', 0, 'revenue', 'manual')""",
            (obj.sha256,
             json.dumps({"kind": "pdf", "doc_sha256": obj.sha256,
                         "page": 2, "text_snippet": "777"})))
        repos.snapshot.create_snapshot("s-1", "US-C", 1, "2024-12-31",
                                       None, "none", "ready")
        repos.snapshot.add_block("s-1", "fundamentals", "ready", None)
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id="m-man", snapshot_id="s-1", scope="issuer",
                 scope_ref="cik-1", concept="revenue", value="777",
                 unit="USD", period_start="2024-01-01",
                 period_end="2024-12-31", formula_id="revenue",
                 method_version="v1", null_reason=None,
                 peer_set_version=None),
            [{"fact_id": "f-man", "peer_measure_id": None,
              "role": "input"}])
    conn.close()
    return paths


def _db_dump(db_path) -> dict[str, list]:
    """Таблица -> строки, для сравнения баз member by member."""
    conn = sqlite3.connect(str(db_path))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: conn.execute(
            f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tables}
    finally:
        conn.close()


def test_round_trip_is_exact(tmp_path):
    src = _seed(tmp_path / "src")
    archive = tmp_path / "backup.zip"
    summary = create_backup(src, archive)
    assert summary.members >= 3 and summary.schema_version == 40
    target = AppPaths.from_root(tmp_path / "dst")
    result = restore_backup(archive, target)
    assert result["restored"] == summary.members
    before = _db_dump(src.db_path)
    after = _db_dump(target.db_path)
    assert before == after, "базы различаются по членам"
    # ручной факт с locator дошёл до конца
    conn = sqlite3.connect(str(target.db_path))
    try:
        fact = conn.execute(
            """SELECT fact_id, concept, value, currency, source_kind,
               locator FROM fact WHERE fact_id='f-man'""").fetchone()
        lineage = conn.execute(
            """SELECT fact_id, role FROM measure_lineage
               WHERE measure_id='m-man'""").fetchall()
    finally:
        conn.close()
    assert fact[0] == "f-man" and fact[2] == "777" \
        and fact[3] == "USD" and fact[4] == "manual"
    assert json.loads(fact[5])["page"] == 2
    assert lineage == [("f-man", "input")]
    # тела документов переехали побайтно: деревья raw/store равны
    src_files = _raw_tree(src)
    dst_files = _raw_tree(target)
    assert src_files and src_files == dst_files


def _raw_tree(paths) -> dict:
    import os
    out = {}
    for dirpath, _d, files in os.walk(paths.raw_store):
        for f in files:
            full = Path(dirpath) / f
            out[str(full.relative_to(paths.raw_store))] = \
                full.read_bytes()
    return out


def test_restore_refuses_tampered_member(tmp_path):
    src = _seed(tmp_path / "src")
    archive = tmp_path / "backup.zip"
    create_backup(src, archive)
    # вскрыть архив и подменить байты члена
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        contents = {n: zf.read(n) for n in names}
    victim = next(n for n in names if n != "MANIFEST.json"
                  and n != "rusterm.db")
    contents[victim] = contents[victim] + b"tampered"
    with zipfile.ZipFile(archive, "w",
                         compression=zipfile.ZIP_DEFLATED) as zf:
        for n, data in contents.items():
            zf.writestr(n, data)
    target = AppPaths.from_root(tmp_path / "dst2")
    with pytest.raises(BackupError) as e:
        restore_backup(archive, target)
    assert victim in e.value.reason and "не совпал" in e.value.reason
    assert not target.db_path.exists(), "отказ не должен ничего писать"


def test_restore_refuses_future_schema(tmp_path):
    src = _seed(tmp_path / "src", with_manual_fact=False)
    archive = tmp_path / "future.zip"
    create_backup(src, archive)
    with zipfile.ZipFile(archive) as zf:
        contents = {n: zf.read(n) for n in zf.namelist()}
    manifest = json.loads(contents["MANIFEST.json"])
    from rusterm.store.db import _SCHEMA_VERSION
    manifest["schema_version"] = _SCHEMA_VERSION + 1
    contents["MANIFEST.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(archive, "w") as zf:
        for n, data in contents.items():
            zf.writestr(n, data)
    target = AppPaths.from_root(tmp_path / "dst3")
    with pytest.raises(BackupError) as e:
        restore_backup(archive, target)
    assert "новее" in e.value.reason


def test_restore_refuses_nonempty_root_without_force(tmp_path):
    src = _seed(tmp_path / "src")
    archive = tmp_path / "backup.zip"
    create_backup(src, archive)
    target = AppPaths.from_root(tmp_path / "dst4")
    ensure_app_dir(target)
    (target.root / "user-file.txt").write_text("драгоценное")
    with pytest.raises(BackupError) as e:
        restore_backup(archive, target)
    assert "непуст" in e.value.reason and "--force" in e.value.reason
    # с --force — разворачивается
    result = restore_backup(archive, target, force=True)
    assert result["restored"] > 0
    assert (target.root / "user-file.txt").exists(), \
        "force не вытирает чужие файлы, а разворачивает поверх"


def test_doctor_reports_backup_age(tmp_path, capsys):
    import os
    os.environ["RUSTERM_SEC_UA"] = "Synthetic Test j4.invalid"
    os.environ["RUSTERM_ENV_FILE"] = "/nonexistent/rusterm.env"
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "doctor"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["last_backup"] is None
    archive = tmp_path / "b.zip"
    summary = create_backup(AppPaths.from_root(root), archive)
    assert summary.members >= 1  # свежий init: одна база, raw пуст
    assert cli.main(["--root", str(root), "doctor"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["last_backup"] is not None
    assert payload["last_backup"]["age_days"] < 1
    assert payload["last_backup"]["archive"] == str(archive)
