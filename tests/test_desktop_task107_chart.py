"""ТЗ-107 V2: ось графика подписана целыми годами (скриншот 30.09:
2026.088608 … 2026.088616 на одной точке)."""
from __future__ import annotations

import pytest


def test_chart_axis_is_labelled_with_whole_years():
    pytest.importorskip("PySide6")
    from rusterm.desktop import charts
    if not charts.PYQTGRAPH_AVAILABLE:
        pytest.skip("pyqtgraph не установлен")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    for years, values in (([2023, 2024, 2025], [0.1, 0.2, 0.3]),
                          ([2026], [0.009])):
        view = charts._PyqtgraphView(
            {"kind": "line", "years": years, "values": values})
        ticks = view.getAxis("bottom")._tickLevels[0]
        labels = [label for _, label in ticks]
        assert labels == [str(y) for y in years], labels
        assert all("." not in label for label in labels)
