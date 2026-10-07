"""ТЗ-111 U3: кнопка «Обновить базу» — базу обновляет щелчок, а не
команда в терминале.

На отставшей схеме окно показывает кнопку «Обновить базу»: бэкап, затем
миграции той же дверью, что rusterm init (ADR-0023 не нарушается —
миграция только по явному щелчку). После щелчка: схема актуальна,
бэкап-файл существует, кнопка скрыта. До щелчка база не мигрирует
(страж test_desktop_f1_stale_schema остаётся зелёным).
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (QApplication, QLabel,  # noqa: E402
                               QPushButton)

from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.store.db import current_schema_version  # noqa: E402
from rusterm.store.paths import AppPaths  # noqa: E402

FIXTURE = (Path(__file__).resolve().parents[1] / "tests" / "data" /
           "upgrade" / "schema44.sqlite.gz")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _stale_catalog(tmp_path, monkeypatch):
    """Копия отставшей базы schema-44 в песочный каталог."""
    import gzip
    import shutil

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       str(tmp_path / "empty.env"))
    (tmp_path / "empty.env").write_text("", encoding="utf-8")
    root = tmp_path / "data"
    root.mkdir()
    paths = AppPaths.from_root(root)
    paths.db_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(FIXTURE, "rb") as src:
        paths.db_path.write_bytes(src.read())
    return paths


def _open(paths):
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _widget(window, cls, name):
    widget = window.findChild(cls, name)
    assert widget is not None, f"{name} не найдено в окне"
    return widget


def test_upgrade_button_migrates_with_backup(qapp, tmp_path, monkeypatch):
    paths = _stale_catalog(tmp_path, monkeypatch)
    conn = _open(paths)
    assert current_schema_version(conn) == 44
    conn.close()

    repos_conn = _open(paths)
    from rusterm.store.repos import RepoRegistry
    repos = RepoRegistry(repos_conn, paths)
    window = desktop_window._build_window(repos, paths, "wl1", 1)
    window.show()

    button = _widget(window, QPushButton, "upgrade_base_button")
    notice = _widget(window, QLabel, "schema_notice")
    assert button.isVisible(), "кнопки обновления нет на отставшей схеме"
    assert "схема 44" in notice.text(), notice.text()

    backups = list((Path(paths.root) / "backups").glob("*.zip")) \
        if (Path(paths.root) / "backups").exists() else []
    assert not backups, "бэкап до щелчка — рано"

    button.click()
    deadline = __import__("time").time() + 15
    while __import__("time").time() < deadline:
        QApplication.processEvents()
        if "обновление базы" not in notice.text():
            break
        __import__("time").sleep(0.05)

    conn2 = _open(paths)
    assert current_schema_version(conn2) == 48
    conn2.close()
    backups = list((Path(paths.root) / "backups").glob("*.zip"))
    assert backups, "бэкапа нет — обновление без страховки"
    assert "схема 44 → 48" in notice.text(), notice.text()
    assert not button.isVisible(), "кнопка осталась после обновления"
    window.close()


def test_the_window_still_does_not_migrate_without_the_click(
        qapp, tmp_path, monkeypatch):
    """Щелчок — единственная дверь миграции: постройка окна на отставшей
    базе схему не меняет (страж F1 — на той же фикстуре)."""
    paths = _stale_catalog(tmp_path, monkeypatch)
    conn = _open(paths)
    from rusterm.store.repos import RepoRegistry
    repos = RepoRegistry(conn, paths)
    window = desktop_window._build_window(repos, paths, "wl1", 1)
    window.close()
    conn2 = _open(paths)
    assert current_schema_version(conn2) == 44
    conn2.close()
