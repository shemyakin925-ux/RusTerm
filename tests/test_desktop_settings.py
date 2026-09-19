"""TASK-C9: настройки, ключи и лимиты — ключи без значений, лимиты из
реестра с оверрайдами в том же config.toml, каталог данных со сменой
через вопрос (молчаливого создания нет).

Слой данных без Qt; оконные тесты — offscreen с заглушками диалогов.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3

import pytest

from rusterm.desktop import data as desktop_data
from rusterm.store.repos import Instrument, Issuer
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import RepoRegistry
from rusterm.store import config as config_module


@pytest.fixture()
def paths_env(tmp_path, monkeypatch):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    # ни одного «найденного» ключа из машины теста
    for name in ("RUSTERM_SEC_UA", "RUSTERM_LLM_PROVIDER",
                 "RUSTERM_LLM_API_KEY", "RUSTERM_LLM_MODEL",
                 "RUSTERM_TWELVEDATA_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       str(tmp_path / "empty.env"))
    yield paths
    # бутстрап мог запомнить происхождения чужого окружения — сброс
    from rusterm import env as env_module
    env_module._LAST_ORIGINS = None


# ── C9.1: ключи — откуда, без значений ──────────────────────────────────

def test_keys_view_names_origin_without_values(paths_env, monkeypatch):
    for name in ("RUSTERM_SEC_UA", "RUSTERM_LLM_PROVIDER",
                 "RUSTERM_LLM_API_KEY", "RUSTERM_LLM_MODEL",
                 "RUSTERM_TWELVEDATA_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RUSTERM_LLM_API_KEY", "sk-secret-value-xyz")
    view = desktop_data.keys_view()
    rows = {r["name"]: r for r in view["rows"]}
    assert set(rows) == {"RUSTERM_SEC_UA", "RUSTERM_LLM_PROVIDER",
                         "RUSTERM_LLM_API_KEY", "RUSTERM_LLM_MODEL",
                         "RUSTERM_TWELVEDATA_KEY"}
    assert rows["RUSTERM_LLM_API_KEY"]["found"] is True
    assert rows["RUSTERM_LLM_API_KEY"]["origin"] == "окружение"
    assert "sk-secret-value-xyz" not in str(view)
    missing = rows["RUSTERM_TWELVEDATA_KEY"]
    assert missing["found"] is False
    assert "twelvedata" in missing["purpose"]
    assert "котировки" in missing["purpose"]


# ── C9.2: лимиты хостов — реестр + правка в config.toml ядра ────────────

def test_host_limits_match_registry_and_roundtrip(paths_env):
    from rusterm.providers import all_host_limits
    paths = paths_env
    view = desktop_data.host_limits_view(paths)
    registry = all_host_limits()
    assert len(view["rows"]) == len(registry)
    by_host = {limit.host: limit for limit in registry.values()}
    for row in view["rows"]:
        limit = by_host[row["host"]]
        assert row["nightly_max"] == limit.nightly_max
        assert row["per_second"] == limit.per_second
        assert row["override"] is None
    outcome = desktop_data.set_host_rate_limit(paths, "data.sec.gov", 0.5)
    assert outcome["ok"] and outcome["applied"] == 0.5
    # правка читается тем же ядром
    reread = config_module.load_config(paths.config_path)
    assert reread.provider_rate_limit["data.sec.gov"] == 0.5
    # и видна в виде оверрайда
    view = desktop_data.host_limits_view(paths)
    sec = next(r for r in view["rows"] if r["host"] == "data.sec.gov")
    assert sec["override"] == 0.5


def test_rate_limit_edit_replaces_same_host(paths_env):
    paths = paths_env
    desktop_data.set_host_rate_limit(paths, "data.sec.gov", 0.5)
    desktop_data.set_host_rate_limit(paths, "data.sec.gov", 0.25)
    text = paths.config_path.read_text(encoding="utf-8")
    assert text.count("data.sec.gov") == 1
    reread = config_module.load_config(paths.config_path)
    assert reread.provider_rate_limit["data.sec.gov"] == 0.25


# ── C9.3: каталог данных ─────────────────────────────────────────────────

def test_catalog_view_reports_size_and_update(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    conn.close()
    view = desktop_data.catalog_view(paths)
    assert view["exists"] is True
    assert view["size_bytes"] > 0
    assert "updated_at" in view
    empty = desktop_data.catalog_view(
        AppPaths.from_root(tmp_path / "nowhere"))
    assert empty["exists"] is False


def test_catalog_switch_decision_asks_when_missing(tmp_path):
    empty = desktop_data.catalog_switch_decision(tmp_path / "new-root")
    assert empty["exists"] is False
    populated = tmp_path / "filled"
    populated.mkdir()
    (populated / "rusterm.db").write_bytes(b"")
    existing = desktop_data.catalog_switch_decision(populated)
    assert existing["exists"] is True


def test_window_settings_tab_shows_keys_and_asks_for_root(
        tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import (QApplication, QLabel, QMessageBox,
                                   QPushButton, QTabWidget,
                                   QTableWidget, QTreeWidget)
    from rusterm.desktop import window as desktop_window

    for name in ("RUSTERM_LLM_API_KEY", "RUSTERM_SEC_UA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(tmp_path / "empty.env"))
    QApplication.instance() or QApplication([])
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-X", "X", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-X", "i-X", None, "common", "active", None))
    window = desktop_window._build_window(repos, paths, None)
    tabs = window.findChild(QTabWidget, "tabs")
    assert tabs.count() == 4
    keys_label = window.findChild(QLabel, "keys_label")
    assert "нет —" in keys_label.text()
    assert "sk-" not in keys_label.text()

    asked = {}
    monkeypatch.setattr(
        desktop_window.QFileDialog, "getExistingDirectory",
        staticmethod(lambda *a, **k: str(tmp_path / "nowhere")))
    monkeypatch.setattr(
        desktop_window.QMessageBox, "question",
        staticmethod(lambda *a, **k:
                     asked.setdefault("asked",
                                      QMessageBox.StandardButton.No)))
    from PySide6.QtWidgets import QPushButton
    switch_button = window.findChild(QPushButton,
                                     "switch_root_button")
    switch_button.click()
    assert asked.get("asked"), "молчаливого создания нет — спросили"
    assert not (tmp_path / "nowhere" / "rusterm.db").exists()
    window.close()
