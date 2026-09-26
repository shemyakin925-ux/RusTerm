"""ТЗ-62 G1: лимит хоста правится через слой конфигурации.

Дверь одна — store.config.set_provider_rate_limit: она одна знает
формат config.toml; десктоп зовёт её и про имя файла не знает (grep
по rusterm/desktop/ пуст). Битый существующий файл — отказ причиной
config_broken, молчаливой перезаписи нет, байты файла не тронуты.
Запись проверяется обратным чтением load_config.
"""
from __future__ import annotations

from pathlib import Path

from rusterm.desktop import data as desktop_data
from rusterm.store.config import set_provider_rate_limit

BROKEN = '[provider_rate_limit]\n"data.sec.gov" = oops\n'


def test_setter_creates_and_replaces(tmp_path):
    path = tmp_path / "config.toml"
    first = set_provider_rate_limit(path, "data.sec.gov", 0.5)
    assert first["ok"] and first["applied"] == 0.5
    second = set_provider_rate_limit(path, "data.sec.gov", 0.25)
    assert second["ok"] and second["applied"] == 0.25
    text = path.read_text(encoding="utf-8")
    assert text.count("data.sec.gov") == 1


def test_broken_config_refused_not_overwritten(tmp_path):
    """Битый файл: отказ причиной config_broken; байты не тронуты —
    чинит пользователь, а не молчаливая перезапись."""
    path = tmp_path / "config.toml"
    path.write_text(BROKEN, encoding="utf-8")
    outcome = set_provider_rate_limit(path, "data.sec.gov", 0.5)
    assert outcome["ok"] is False
    assert outcome["reason"].startswith("config_broken:")
    assert path.read_text(encoding="utf-8") == BROKEN


def test_desktop_does_not_know_the_config_filename():
    """Окно зовёт дверь слоя конфигурации; имени config.toml в
    rusterm/desktop/ нет ни в коде, ни в docstrings."""
    desktop = Path(desktop_data.__file__).resolve().parent
    offenders = [p.name for p in sorted(desktop.rglob("*.py"))
                 if "config.toml" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders


def test_desktop_setter_delegates_to_the_store_door(tmp_path):
    """Окнешный set_host_rate_limit — та же дверь: итог читается
    load_config, файл пишется слоем конфигурации."""
    paths = type("P", (), {"config_path": tmp_path / "config.toml"})()
    outcome = desktop_data.set_host_rate_limit(paths, "data.sec.gov", 0.5)
    assert outcome["ok"] and outcome["applied"] == 0.5
