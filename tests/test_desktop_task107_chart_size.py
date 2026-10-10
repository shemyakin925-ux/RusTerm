"""ТЗ-107 (просьба пользователя 01.10): график крупнее таблицы, граница
между ними перетаскивается."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QSplitter  # noqa: E402

from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.desktop.charts import ChartArea  # noqa: E402
from rusterm.store.paths import AppPaths  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_chart_and_table_share_a_draggable_split(qapp, tmp_path):
    paths = AppPaths.from_root(tmp_path / "nowhere")
    window = desktop_window._build_window(None, paths, None)
    split = window.findChild(QSplitter, "chart_split")
    assert split is not None
    chart = window.findChild(ChartArea, "chart_area")
    assert split.indexOf(chart) == 0
    assert chart.minimumHeight() >= 320
    window.resize(1600, 1000)
    window.show()
    qapp.processEvents()
    sizes = split.sizes()
    assert sizes[0] >= sizes[1], sizes
    window.close()
