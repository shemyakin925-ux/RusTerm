"""Резервная копия и восстановление (ТЗ-22 J4).

Ручной импортированный факт — первые данные проекта, которые нельзя
скачать заново: пользователь отдал файл модели, заплатил за вызов и
сверил цитату. Архив один: база (вместе со watchlist'ами и lineage),
манифесты raw-хранилища и сами объекты (тела импортированных
документов). Каждый член архива несёт sha256 в MANIFEST.json; там же
версия схемы.

Восстановление честно отказывает: архив с версией схемы НОВЕЕ
работающего кода, член с несовпавшим хешем, и никогда не пишет в
непустой каталог без явного --force.

SQL здесь не нужен — кроме VACUUM INTO для согласованного снимка базы;
файл лежит в слое хранилища, CLI только показывает исход.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .db import current_schema_version
from .paths import AppPaths

ARCHIVE_DB_MEMBER = "rusterm.db"
MANIFEST_MEMBER = "MANIFEST.json"
BACKUP_STATE_FILE = "backup.json"


class BackupError(Exception):
    """Отказ со именем причины; CLI печатает её, код возврата 1."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class BackupSummary:
    archive: str
    members: int
    bytes_total: int
    schema_version: int | None
    created_at: float


def create_backup(paths: AppPaths, archive_path: str | Path) -> BackupSummary:
    """Собрать архив из каталога данных. Снимок базы — согласованный
    (VACUUM INTO во временный файл), WAL не тащим."""
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    conn_path = str(paths.db_path)
    if not os.path.exists(conn_path):
        raise BackupError(f"базы нет: {conn_path} (сначала rusterm init)")

    import sqlite3
    snapshot_db = archive_path.with_suffix(archive_path.suffix + ".dbtmp")
    if snapshot_db.exists():
        snapshot_db.unlink()
    src = sqlite3.connect(conn_path)
    try:
        schema_version = current_schema_version(src)
        src.execute("VACUUM INTO ?", (str(snapshot_db),))
    finally:
        src.close()

    members: list[dict] = []
    try:
        members.append(_member_from_file(ARCHIVE_DB_MEMBER, snapshot_db))
        manifests = sorted(paths.raw_manifests.glob("manifest-*.jsonl"))
        for m in manifests:
            # пути членов — относительно корня каталога данных, как на диске
            members.append(_member_from_file(
                f"raw/manifests/{m.name}", m))
        if paths.raw_store.is_dir():
            for dirpath, _dirs, files in os.walk(paths.raw_store):
                for fname in sorted(files):
                    full = Path(dirpath) / fname
                    rel = full.relative_to(paths.root)
                    members.append(_member_from_file(str(rel), full))
        manifest = {
            "schema_version": schema_version,
            "created_at": time.time(),
            "members": members,
        }
        with zipfile.ZipFile(archive_path, "w",
                             compression=zipfile.ZIP_DEFLATED) as zf:
            for member in members:
                zf.write(member["_source"], member["path"])
            zf.writestr(MANIFEST_MEMBER,
                        json.dumps(manifest, ensure_ascii=False,
                                   indent=1))
    finally:
        if snapshot_db.exists():
            snapshot_db.unlink()

    # отметка о копии в каталоге данных — doctor читает возраст
    state = {"archive": str(archive_path),
             "created_at": manifest["created_at"],
             "members": len(members)}
    paths.root.joinpath(BACKUP_STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")

    return BackupSummary(
        archive=str(archive_path), members=len(members),
        bytes_total=sum(m["bytes"] for m in members),
        schema_version=schema_version,
        created_at=manifest["created_at"])


def _member_from_file(member_path: str, source: Path) -> dict:
    data = source.read_bytes()
    return {"path": member_path, "sha256": _sha256(data),
            "bytes": len(data), "_source": str(source)}


def restore_backup(archive_path: str | Path, target: AppPaths,
                   force: bool = False) -> dict:
    """Развернуть архив в каталог target. Отказы — BackupError:
    MANIFEST нет, схема новее кода, хеш члена не сошёлся, каталог
    непуст и force не задан."""
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise BackupError(f"архива нет: {archive_path}")
    try:
        zf = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile:
        raise BackupError("это не zip-архив")
    with zf:
        names = zf.namelist()
        if MANIFEST_MEMBER not in names:
            raise BackupError(f"в архиве нет {MANIFEST_MEMBER}")
        manifest = json.loads(zf.read(MANIFEST_MEMBER))
        members = manifest.get("members", [])
        if not any(m.get("path") == ARCHIVE_DB_MEMBER for m in members):
            raise BackupError(f"в архиве нет {ARCHIVE_DB_MEMBER}")
        schema_version = manifest.get("schema_version")
        from .db import _SCHEMA_VERSION
        if schema_version is None or schema_version > _SCHEMA_VERSION:
            raise BackupError(
                f"схема архива {schema_version} новее работающей "
                f"{_SCHEMA_VERSION}; обновите rusterm")
        listed = {m["path"] for m in members}
        if target.root.exists() and any(target.root.iterdir()):
            if not force:
                raise BackupError(
                    f"каталог {target.root} непуст; перезапись без "
                    f"--force запрещена")
        # проверяем хеши ДО всякой записи
        for member in members:
            data = zf.read(member["path"])
            if _sha256(data) != member.get("sha256"):
                raise BackupError(
                    f"хеш члена {member['path']} не совпал — архив "
                    f"повреждён")
            if member["path"] not in {MANIFEST_MEMBER} and \
                    member["path"] not in listed:
                raise BackupError(f"внелистовый член {member['path']}")
        target.root.mkdir(parents=True, exist_ok=True)
        restored = 0
        for member in members:
            data = zf.read(member["path"])
            dest = _safe_target(target.root, member["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            restored += 1
    return {"restored": restored,
            "schema_version": schema_version,
            "created_at": manifest.get("created_at"),
            "target": str(target.root)}


def _safe_target(root: Path, member_path: str) -> Path:
    """Член архива разворачивается только внутрь каталога данных;
    выход за корень (../) — отказ."""
    dest = (root / member_path).resolve()
    if not str(dest).startswith(str(root.resolve()) + os.sep):
        raise BackupError(f"член {member_path} выходит за каталог данных")
    return dest


def last_backup_info(paths: AppPaths) -> dict | None:
    """Отметка о последней копии; None — копий не было."""
    state_path = paths.root / BACKUP_STATE_FILE
    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    age_seconds = max(0.0, time.time() - float(state.get("created_at", 0)))
    return {"archive": state.get("archive"),
            "created_at": state.get("created_at"),
            "age_days": round(age_seconds / 86400, 2)}
