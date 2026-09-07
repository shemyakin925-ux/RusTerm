"""Тесты инкремента И1: пути и конфигурация."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from rusterm.store.config import load_config, write_default_config
from rusterm.store.paths import AppPaths, default_root, ensure_app_dir


def test_paths_from_root_creates_all_dirs(tmp_path: Path):
    paths = AppPaths.from_root(tmp_path / "data")
    assert not paths.root.exists()
    ensure_app_dir(paths)
    assert paths.root.is_dir()
    assert paths.raw_store.is_dir()
    assert paths.raw_manifests.is_dir()
    assert paths.exports.is_dir()
    assert paths.logs.is_dir()
    assert paths.db_path.parent == paths.root


def test_ensure_app_dir_is_idempotent(tmp_path: Path):
    """Повторный вызов не ломает существующий каталог и не удаляет файлы."""
    paths = AppPaths.from_root(tmp_path / "data")
    ensure_app_dir(paths)
    (paths.logs / "audit.jsonl").write_text("test\n", encoding="utf-8")
    ensure_app_dir(paths)
    assert (paths.logs / "audit.jsonl").read_text(encoding="utf-8") == "test\n"
    # второй раз поверх — должно быть тихо
    ensure_app_dir(paths)
    assert paths.root.is_dir()


def test_paths_db_path_points_to_root():
    paths = AppPaths.from_root("/tmp/rusterm-test")
    assert paths.db_path.resolve() == Path("/tmp/rusterm-test/rusterm.db").resolve()


def test_default_root_uses_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RUSTERM_DATA", str(tmp_path))
    assert default_root() == tmp_path


def test_default_root_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_root() == tmp_path / ".rusterm"


def test_load_config_missing_returns_defaults(tmp_path: Path):
    cfg = load_config(tmp_path / "absent.toml")
    assert cfg.raw_retention == "facts_only"
    assert cfg.log_level == "INFO"
    assert cfg.providers_enabled == []


def test_load_config_reads_values(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text(
        'raw_retention = "full"\n'
        'log_level = "DEBUG"\n'
        "providers_enabled = [\"sec_edgar\"]\n"
        "[provider_rate_limit]\n"
        'sec_edgar = 8.0\n',
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.raw_retention == "full"
    assert cfg.log_level == "DEBUG"
    assert cfg.providers_enabled == ["sec_edgar"]
    assert cfg.provider_rate_limit["sec_edgar"] == 8.0


def test_load_config_corrupted_falls_back(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text("raw_retention = \"full\"\n" "log_level = \"DEBUG\"\n", encoding="utf-8")
    # Удалим кавычку — будет невалидный TOML
    p.write_text("raw_retention = ", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.raw_retention == "facts_only"  # default


def test_load_config_unreadable_falls_back(tmp_path: Path):
    # Каталог вместо файла — OSError
    p = tmp_path / "config.toml"
    p.mkdir()
    cfg = load_config(p)
    assert cfg.raw_retention == "facts_only"


def test_write_default_config_creates_file(tmp_path: Path):
    p = tmp_path / "config.toml"
    write_default_config(p)
    assert p.exists()
    # Должен парситься как валидный TOML
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    assert data["raw_retention"] == "facts_only"
    assert "log_level" in data


def test_write_default_config_does_not_overwrite(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text('raw_retention = "full"\n', encoding="utf-8")
    write_default_config(p)
    assert p.read_text(encoding="utf-8") == 'raw_retention = "full"\n'


def test_config_contains_no_secret_keys(tmp_path: Path):
    """ADR-0003: ключ LLM не в config.toml."""
    p = tmp_path / "config.toml"
    write_default_config(p)
    text = p.read_text(encoding="utf-8").lower()
    for forbidden in ("api_key", "apikey", "password", "secret", "token"):
        assert forbidden not in text, f"config.toml содержит {forbidden!r}"


def test_paths_resolve_handles_spaces_and_unicode(tmp_path: Path):
    root = tmp_path / "каталог с пробелами"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    assert paths.root.is_dir()
    assert paths.db_path == root / "rusterm.db"
