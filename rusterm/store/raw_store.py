"""Content-addressed raw store + JSONL-манифест по ADR-0003.

Контракт:
- Запись: хеш -> байты. Сжатие zstd выше 64 КБ, иначе plain.
- Адресация: raw/store/<2>/<sha256>, где <2> — первые два hex-символа.
- Манифест: только на добавление, формат JSONL.
- Чтение: либо по пути, либо восстановление индекса из манифеста.
- Дубль sha256: запись — no-op, манифест не пишется.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .paths import AppPaths


COMPRESS_THRESHOLD = 64 * 1024  # 64 КБ
ZSTD_EXTENSION = ".zst"


@dataclass(frozen=True)
class StoredObject:
    sha256: str
    bytes_written: int  # фактический объём в store (после возможного сжатия)
    content_type: str
    compression: str  # none | zstd
    fetched_at: float  # unix ts
    provider: str
    url: str | None
    instrument_id: str | None
    block: str | None
    http_status: int | None
    etag: str | None

    def to_manifest_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class RawIndexEntry:
    sha256: str
    provider: str
    url: str | None
    fetched_at: float
    bytes: int
    content_type: str
    compression: str
    instrument_id: str | None
    block: str | None
    http_status: int | None
    etag: str | None

    @property
    def path(self) -> str:
        return f"raw/store/{self.sha256[:2]}/{self.sha256}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_path(store_dir: Path, sha256: str) -> Path:
    return store_dir / sha256[:2] / sha256


def manifest_path_for(root: Path, ts: float | None = None) -> Path:
    """Имя файла манифеста привязано к дате — один файл на сутки."""
    if ts is None:
        ts = time.time()
    import datetime as _dt
    day = _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).strftime("%Y-%m-%d")
    return root / f"manifest-{day}.jsonl"


def put_object(
    raw_store_dir: Path,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
    provider: str,
    url: str | None = None,
    instrument_id: str | None = None,
    block: str | None = None,
    http_status: int | None = None,
    etag: str | None = None,
) -> StoredObject:
    """Записать байты в content-addressed store.

    Возвращает StoredObject. Если объект уже существует — запись no-op,
    нового StoredObject не создаётся (читаем существующие метаданные).
    """
    sha = sha256_bytes(data)
    target = object_path(raw_store_dir, sha)
    target.parent.mkdir(parents=True, exist_ok=True)

    compress = len(data) >= COMPRESS_THRESHOLD
    if compress:
        import zstandard as zstd
        compressed = zstd.ZstdCompressor().compress(data)
        target_path = target.with_suffix(target.suffix + ZSTD_EXTENSION)
        if not target_path.exists():
            target_path.write_bytes(compressed)
        bytes_written = len(compressed)
        compression_label = "zstd"
    else:
        if not target.exists():
            target.write_bytes(data)
        target_path = target
        bytes_written = len(data)
        compression_label = "none"

    return StoredObject(
        sha256=sha,
        bytes_written=bytes_written,
        content_type=content_type,
        compression=compression_label,
        fetched_at=time.time(),
        provider=provider,
        url=url,
        instrument_id=instrument_id,
        block=block,
        http_status=http_status,
        etag=etag,
    )


def append_manifest_line(manifests_dir: Path, obj: StoredObject) -> Path:
    """Дописать строку в манифест. Возвращает путь к файлу манифеста.

    Запись — append, на существующий файл. Никогда не переписываем.
    """
    manifests_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_path_for(manifests_dir, obj.fetched_at)
    # Атомарная запись одной строки: открыть на append, записать, закрыть.
    with path.open("a", encoding="utf-8") as f:
        f.write(obj.to_manifest_line() + "\n")
    return path


def read_object(raw_store_dir: Path, sha256: str) -> bytes:
    """Прочитать байты. Ищет plain и zstd вариант. Не декомпрессирует —
    возвращает то, что лежит на диске."""
    target = object_path(raw_store_dir, sha256)
    if not target.exists():
        zstd_path = target.with_suffix(target.suffix + ZSTD_EXTENSION)
        if zstd_path.exists():
            return zstd_path.read_bytes()
        raise FileNotFoundError(f"raw object {sha256} not in store")
    return target.read_bytes()


def decompress_object(raw_store_dir: Path, sha256: str) -> bytes:
    """Прочитать и декомпрессировать при необходимости."""
    raw = read_object(raw_store_dir, sha256)
    if raw.endswith(ZSTD_EXTENSION.encode()) or _is_zstd_magic(raw):
        import zstandard as zstd
        return zstd.ZstdDecompressor().decompress(raw)
    return raw


def _is_zstd_magic(data: bytes) -> bool:
    # zstd magic: 0x28 0xB5 0x2F 0xFD
    return len(data) >= 4 and data[:4] == b"\x28\xb5\x2f\xfd"


def iter_manifest_entries(manifests_dir: Path) -> Iterator[RawIndexEntry]:
    """Потоковое чтение манифестов. Дедупликация по sha256 — последняя
    запись побеждает (на случай ре-импорта того же объекта)."""
    seen: dict[str, RawIndexEntry] = {}
    files = sorted(manifests_dir.glob("manifest-*.jsonl"))
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            entry = RawIndexEntry(
                sha256=data["sha256"],
                provider=data.get("provider", ""),
                url=data.get("url"),
                fetched_at=data.get("fetched_at", 0.0),
                bytes=data.get("bytes_written", data.get("bytes", 0)),
                content_type=data.get("content_type", "application/octet-stream"),
                compression=data.get("compression", "none"),
                instrument_id=data.get("instrument_id"),
                block=data.get("block"),
                http_status=data.get("http_status"),
                etag=data.get("etag"),
            )
            seen[entry.sha256] = entry
    yield from seen.values()


def rebuild_index(manifests_dir: Path) -> dict[str, RawIndexEntry]:
    """Полное восстановление индекса из манифестов."""
    return {e.sha256: e for e in iter_manifest_entries(manifests_dir)}


def has_object(raw_store_dir: Path, sha256: str) -> bool:
    target = object_path(raw_store_dir, sha256)
    if target.exists():
        return True
    return target.with_suffix(target.suffix + ZSTD_EXTENSION).exists()


def put_with_manifest(
    paths: AppPaths,
    data: bytes,
    **kwargs,
) -> StoredObject:
    """Удобный композиционный вызов: записать в store + дописать манифест."""
    obj = put_object(paths.raw_store, data, **kwargs)
    append_manifest_line(paths.raw_manifests, obj)
    return obj
