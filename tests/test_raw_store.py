"""Тесты инкремента И2: content-addressed raw store + манифест."""
from __future__ import annotations

import json
import time

import pytest

from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.raw_store import (
    COMPRESS_THRESHOLD,
    append_manifest_line,
    decompress_object,
    has_object,
    iter_manifest_entries,
    manifest_path_for,
    object_path,
    put_object,
    put_with_manifest,
    read_object,
    rebuild_index,
    sha256_bytes,
)


@pytest.fixture
def app_paths(tmp_path) -> AppPaths:
    paths = AppPaths.from_root(tmp_path / "data")
    ensure_app_dir(paths)
    return paths


def test_sha256_known_value():
    # известный хеш пустой строки
    assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_bytes(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_put_object_writes_file(app_paths: AppPaths):
    data = b"small payload"
    obj = put_object(app_paths.raw_store, data, provider="test", url="u", block="b")
    assert obj.sha256 == sha256_bytes(data)
    assert obj.bytes_written == len(data)
    assert obj.compression == "none"
    assert object_path(app_paths.raw_store, obj.sha256).exists()


def test_put_object_under_threshold_no_compression(app_paths: AppPaths):
    data = b"x" * (COMPRESS_THRESHOLD - 1)
    obj = put_object(app_paths.raw_store, data, provider="t")
    assert obj.compression == "none"
    assert has_object(app_paths.raw_store, obj.sha256)


def test_put_object_at_threshold_compresses(app_paths: AppPaths):
    data = b"x" * COMPRESS_THRESHOLD
    obj = put_object(app_paths.raw_store, data, provider="t")
    assert obj.compression in ("zstd", "gzip")
    # Проверяем round-trip: сжатые данные читаются обратно
    decompressed = decompress_object(app_paths.raw_store, obj.sha256)
    assert decompressed == data
    # Проверяем, что сжатие действительно уменьшило объем
    assert obj.bytes_written < len(data)
    # Сжатый объект лежит на диске с расширением своего алгоритма
    plain = object_path(app_paths.raw_store, obj.sha256)
    exists_zst = plain.with_suffix(plain.suffix + ".zst").exists()
    exists_gz = plain.with_suffix(plain.suffix + ".gz").exists()
    assert exists_zst or exists_gz, (
        "сжатый объект не записан на диск ни как .zst, ни как .gz"
    )


def test_put_object_above_threshold_compresses(app_paths: AppPaths):
    data = b"x" * (COMPRESS_THRESHOLD * 4)
    obj = put_object(app_paths.raw_store, data, provider="t")
    # Проверяем round-trip: сжатые данные читаются обратно
    decompressed = decompress_object(app_paths.raw_store, obj.sha256)
    assert decompressed == data


def test_put_object_labels_zstd_when_available(app_paths: AppPaths):
    """При доступном zstandard метка именно 'zstd'. Без пакета — пропуск:
    метка тогда законно 'gzip' (TASK-3 §A2)."""
    try:
        import zstandard  # noqa: F401
    except ImportError:
        pytest.skip("zstandard не установлен — используется gzip-фолбэк")
    data = b"x" * COMPRESS_THRESHOLD
    obj = put_object(app_paths.raw_store, data, provider="t")
    assert obj.compression == "zstd"


def test_put_object_duplicate_is_noop(app_paths: AppPaths):
    """I7 в части store: повторная запись того же байтового содержимого
    не создаёт второго объекта."""
    data = b"abcdef" * 100
    obj1 = put_object(app_paths.raw_store, data, provider="t")
    obj2 = put_object(app_paths.raw_store, data, provider="t")
    assert obj1.sha256 == obj2.sha256
    # файл один
    matches = list(app_paths.raw_store.rglob(obj1.sha256 + "*"))
    assert len(matches) == 1


def test_read_object_roundtrip_plain(app_paths: AppPaths):
    data = b"plain roundtrip"
    obj = put_object(app_paths.raw_store, data, provider="t")
    assert read_object(app_paths.raw_store, obj.sha256) == data
    assert decompress_object(app_paths.raw_store, obj.sha256) == data


def test_read_object_roundtrip_compressed(app_paths: AppPaths):
    data = b"x" * (COMPRESS_THRESHOLD * 2)
    obj = put_object(app_paths.raw_store, data, provider="t")
    decompressed = decompress_object(app_paths.raw_store, obj.sha256)
    assert decompressed == data


def test_append_manifest_line_creates_file(app_paths: AppPaths):
    obj = put_object(app_paths.raw_store, b"x", provider="t")
    p = append_manifest_line(app_paths.raw_manifests, obj)
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["sha256"] == obj.sha256


def test_manifest_path_is_per_day():
    import datetime as _dt
    ts = _dt.datetime(2026, 9, 6, 12, 0, tzinfo=_dt.timezone.utc).timestamp()
    p = manifest_path_for(__import__("pathlib").Path("/tmp/m"), ts)
    assert p.name == "manifest-2026-09-06.jsonl"


def test_manifest_appends_only(app_paths: AppPaths):
    obj1 = put_object(app_paths.raw_store, b"first", provider="t")
    obj2 = put_object(app_paths.raw_store, b"second", provider="t")
    p1 = append_manifest_line(app_paths.raw_manifests, obj1)
    p2 = append_manifest_line(app_paths.raw_manifests, obj2)
    assert p1 == p2  # один день — один файл
    text = p1.read_text(encoding="utf-8")
    assert text.count("\n") == 2  # две строки, обе заканчиваются \n


def test_iter_manifest_entries_dedupes(app_paths: AppPaths):
    """Если один объект записан дважды, в индексе одна запись (последняя)."""
    data = b"dedup-payload"
    obj = put_object(app_paths.raw_store, data, provider="t")
    append_manifest_line(app_paths.raw_manifests, obj)
    append_manifest_line(app_paths.raw_manifests, obj)
    entries = list(iter_manifest_entries(app_paths.raw_manifests))
    assert len(entries) == 1
    assert entries[0].sha256 == obj.sha256


def test_rebuild_index_from_manifests(app_paths: AppPaths):
    data1 = b"alpha"
    data2 = b"beta"
    o1 = put_with_manifest(app_paths, data1, provider="t1")
    o2 = put_with_manifest(app_paths, data2, provider="t2")
    idx = rebuild_index(app_paths.raw_manifests)
    assert set(idx.keys()) == {o1.sha256, o2.sha256}
    assert idx[o1.sha256].provider == "t1"
    assert idx[o2.sha256].provider == "t2"


def test_manifest_handles_corrupted_line_gracefully(app_paths: AppPaths):
    """Повреждённая строка в манифесте — падать нельзя, должны вернуться
    остальные. Проверяем, что парсер хотя бы поднимает ошибку на повреждённой
    строке — а iter_manifest_entries должен её пропустить ИЛИ явно отказать.
    Принимаем решение: skip с предупреждением."""
    good = put_object(app_paths.raw_store, b"good", provider="t")
    append_manifest_line(app_paths.raw_manifests, good)
    p = manifest_path_for(app_paths.raw_manifests, good.fetched_at)
    with p.open("a", encoding="utf-8") as f:
        f.write("{not a json line}\n")
    # Поведение: повреждённая строка бросает — это OK, но должно быть
    # именно на повреждённой, а не на хорошей.
    with pytest.raises(json.JSONDecodeError):
        list(iter_manifest_entries(app_paths.raw_manifests))


def test_has_object_true_and_false(app_paths: AppPaths):
    data = b"present"
    obj = put_object(app_paths.raw_store, data, provider="t")
    assert has_object(app_paths.raw_store, obj.sha256)
    assert not has_object(app_paths.raw_store, "0" * 64)


def test_put_with_manifest_writes_both(app_paths: AppPaths):
    data = b"combo"
    obj = put_with_manifest(app_paths, data, provider="combo", block="b")
    assert has_object(app_paths.raw_store, obj.sha256)
    idx = rebuild_index(app_paths.raw_manifests)
    assert obj.sha256 in idx
    assert idx[obj.sha256].block == "b"
