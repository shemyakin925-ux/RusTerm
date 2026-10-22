"""ТЗ-144 G2: кнопка «Добавить аналоги…» на вкладке «Аналоги».

У бумаги без группы кнопка видна; нажатие — подсказка в рабочем
потоке, выбор — `QInputDialog.getText` (подменён), сбор группы —
вторым потоком. Двери ядра подменены: сети нет.
"""
from __future__ import annotations

import os
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_window_button_suggests_and_builds_a_group(tmp_path, monkeypatch):
    from PySide6.QtWidgets import (QApplication, QInputDialog, QPushButton,
                                   QTreeWidget)
    from rusterm.desktop import actions
    from rusterm.desktop import window as desktop_window
    from tests.test_desktop_task110_b2_refresh import _catalog, _widget

    app = QApplication.instance() or QApplication([])
    repos, paths, conn = _catalog(tmp_path)
    calls = {}
    monkeypatch.setattr(actions, "suggest_peers", lambda root, iid: {
        "ok": True, "sic": 3571, "description": "ELECTRONIC COMPUTERS",
        "year": 2025, "candidates": [
            {"cik": 2, "ticker": "DELL", "name": "Dell", "revenue": 9e10},
            {"cik": 3, "ticker": "HPQ", "name": "HP", "revenue": 5e10}]})

    def build(root, iid, tickers, sic, description, cancel=None,
              on_stage=None):
        calls["build"] = (iid, list(tickers), sic)
        return actions.CollectOutcome(ok=True, detail="группа sic-3571")

    monkeypatch.setattr(actions, "build_peer_group", build)
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (k.get("text"), True)))
    win = desktop_window._build_window(repos, paths, "wl-1")
    try:
        tree = _widget(win, QTreeWidget, "tree")
        top = tree.topLevelItem(0)
        tree.setCurrentItem(top.child(0) if top.childCount() else top)
        app.processEvents()
        button = _widget(win, QPushButton, "peer_suggest_button")
        assert not button.isHidden(), "у бумаги без группы кнопка видна"
        button.click()
        deadline = time.time() + 10
        while "build" not in calls and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        while win._worker is not None and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        assert calls.get("build") == ("US-AAPL", ["DELL", "HPQ"], 3571)
    finally:
        win.close()
        conn.close()
