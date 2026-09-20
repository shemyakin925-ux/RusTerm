"""Отрисовка диаграмм десктопа (TASK-C1.3): pyqtgraph или QtCharts.

Данные приходят спецификациями из rusterm/desktop/data.py — здесь
только рисование. pyqtgraph установлен — рисует он; нет — те же типы
рисует QtCharts, окно о подмене молчит (деградация без отказа,
ADR-0023). Оба бэкенда верны одному закону: годы без значения —
разрыв линии, а не ноль; псевдо-OHLC из close не рисуется никогда.

Модуль импортируется и без PySide6 (приёмка №1): Qt-импорты под
охраной, чистые помощники работают без Qt.
"""
from __future__ import annotations

import math

try:
    from PySide6.QtCore import Qt, QRect
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QLabel, QWidget
    QT_AVAILABLE = True
except ImportError:  # приёмка №1: модуль обязан импортироваться без Qt
    QT_AVAILABLE = False

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    pg = None
    PYQTGRAPH_AVAILABLE = False


def available_backend() -> str:
    """Каким бэкендом будут рисоваться диаграммы в этом процессе."""
    if QT_AVAILABLE and PYQTGRAPH_AVAILABLE:
        return "pyqtgraph"
    if QT_AVAILABLE:
        return "qtcharts"
    return "none"


def split_segments(years: list, values: list) -> list[list[tuple]]:
    """Разбить ряд на непрерывные отрезки по пропускам (без Qt).

    Год со значением None — разрыв: отрезок кончается, следующий
    начинается. Ноль никогда не подставляется на место пропуска.
    """
    segments: list[list[tuple]] = []
    current: list[tuple] = []
    for year, value in zip(years, values):
        if value is None:
            if current:
                segments.append(current)
                current = []
            continue
        current.append((year, value))
    if current:
        segments.append(current)
    return segments


if QT_AVAILABLE:

    class ChartArea(QWidget):
        """Полотно диаграммы: сменяет спецификации без пересоздания."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._backend = available_backend()
            self._view = None
            self._label = QLabel("нет данных", self)
            self._label.setWordWrap(True)
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def backend(self) -> str:
            return self._backend

        def current_text(self) -> str:
            """Текст сообщения на полотне («нет данных» и причины);
            на живой диаграмме — пустая строка. Видимость не участвует:
            offscreen-прогон ничего не показывает."""
            return self._label.text() if self._view is None else ""

        def set_spec(self, spec: dict) -> None:
            """Применить спецификацию: применение без перезапуска окна."""
            if spec.get("kind") == "message":
                self._show_message(spec.get("text", "нет данных"))
                return
            self._label.hide()
            self._drop_view()
            self._view = (_PyqtgraphView(spec, self)
                          if self._backend == "pyqtgraph"
                          else _QtChartsView(spec, self))
            self._view.setGeometry(self.rect())
            self._view.show()

        def resizeEvent(self, event) -> None:
            super().resizeEvent(event)
            if self._view is not None:
                self._view.setGeometry(self.rect())
            self._label.setGeometry(self.rect())

        def save_png(self, path: str, caption: str = "") -> bool:
            """C4.2: текущий график в png; подпись припечатана снизу
            к снимку виджета. Сообщению-заглушке тоже можно сохранить
            png — подпись честно скажет, что на экране было."""
            image = self.grab().toImage()
            if not caption:
                return image.save(path)
            margin = 8
            probe = QPainter(image)
            font = probe.font()
            font.setPointSize(10)
            probe.setFont(font)
            text_rect = probe.boundingRect(
                QRect(0, 0, image.width() - 2 * margin, 60),
                Qt.TextWordWrap, caption)
            probe.end()
            canvas = QImage(
                image.width(),
                image.height() + text_rect.height() + 2 * margin,
                QImage.Format_ARGB32_Premultiplied)
            canvas.fill(QColor("white"))
            painter = QPainter(canvas)
            painter.drawImage(0, 0, image)
            painter.setPen(QColor("black"))
            painter.setFont(font)
            painter.drawText(
                QRect(margin, image.height() + margin,
                      canvas.width() - 2 * margin,
                      text_rect.height() + margin),
                Qt.TextWordWrap, caption)
            painter.end()
            return canvas.save(path)

        def _drop_view(self) -> None:
            if self._view is not None:
                self._view.setParent(None)
                self._view.deleteLater()
                self._view = None

        def _show_message(self, text: str) -> None:
            self._drop_view()
            self._label.setText(text)
            self._label.show()

    # ── pyqtgraph ───────────────────────────────────────────────────
    # класс существует только когда бэкенд есть: без pyqtgraph модуль
    # всё равно импортируется (приёмка №1), а вид строит QtCharts

    if PYQTGRAPH_AVAILABLE:

        class _PyqtgraphView(pg.PlotWidget):
            def __init__(self, spec: dict, parent=None):
                super().__init__(parent)
                self.setAntialiasing(True)
                kind = spec["kind"]
                if kind in ("line", "bars"):
                    years = [int(y) for y in spec["years"]]
                    values = [float(v) if v is not None else None
                              for v in spec["values"]]
                    if kind == "line":
                        # разрыв — NaN + connect="finite": None pyqtgraph
                        # не понимает (object-массив роняет isfinite)
                        nan_values = [v if v is not None else float("nan")
                                      for v in values]
                        self.plot(years, nan_values, connect="finite",
                                  symbol="o", symbolSize=5)
                    else:
                        present = [(y, v) for y, v in zip(years, values)
                                   if v is not None]
                        if present:
                            self.addItem(pg.BarGraphItem(
                                x=[p[0] for p in present],
                                height=[p[1] for p in present],
                                width=0.6, brush="w"))
                    self.setLabel("bottom", "год")
                elif kind == "box":
                    box = pg.BarGraphItem(x=[0], height=[spec["p75"]
                                                        - spec["p25"]],
                                          y0=[spec["p25"]], width=0.5,
                                          brush="w")
                    self.addItem(box)
                    self.addItem(pg.InfiniteLine(
                        pos=spec["median"], angle=0,
                        pen=pg.mkPen("w", width=2)))
                    self.getAxis("bottom").setTicks([[
                        (0.0, f"{spec['concept']}\nn={spec['n']}")]])
                    self.setLabel("left", spec["concept"])
                elif kind == "radar":
                    axes = spec["axes"]
                    count = len(axes)
                    xs, ys = [], []
                    for i, axis in enumerate(axes + axes[:1]):
                        angle = 2 * math.pi * i / count
                        xs.append(axis["value"] * math.cos(angle))
                        ys.append(axis["value"] * math.sin(angle))
                    self.plot(xs, ys, symbol="o", symbolSize=4)
                    self.setAspectLocked(True)
                elif kind == "radar_vs":
                    axes = spec["axes"]
                    count = len(axes)
                    scale = max(
                        [a["value"] for a in axes]
                        + [a["median"] for a in axes]) or 1.0

                    def polygon(pick):
                        xs, ys = [], []
                        for i in range(count + 1):
                            axis = axes[i % count]
                            r = pick(axis) / scale
                            angle = 2 * math.pi * i / count
                            xs.append(r * math.cos(angle))
                            ys.append(r * math.sin(angle))
                        return xs, ys

                    xs, ys = polygon(lambda a: a["value"])
                    self.plot(xs, ys, symbol="o", symbolSize=5,
                              pen=pg.mkPen("w", width=2))
                    mxs, mys = polygon(lambda a: a["median"])
                    self.plot(mxs, mys,
                              pen=pg.mkPen("y", width=2, style=
                                           Qt.PenStyle.DashLine))
                    for i, axis in enumerate(axes):
                        angle = 2 * math.pi * i / count
                        r = axis["value"] / scale
                        item = pg.TextItem(axis["concept"])
                        item.setPos(r * math.cos(angle),
                                    r * math.sin(angle))
                        self.addItem(item)
                    self.setAspectLocked(True)

    # ── QtCharts ────────────────────────────────────────────────────

    class _QtChartsView(QWidget):
        def __init__(self, spec: dict, parent=None):
            super().__init__(parent)
            from PySide6.QtCharts import (QBarCategoryAxis, QBarSeries,
                                          QBarSet, QBoxPlotSeries,
                                          QBoxSet, QChart, QChartView,
                                          QLineSeries, QPolarChart,
                                          QValueAxis)
            from PySide6.QtGui import QPainter
            from PySide6.QtWidgets import QVBoxLayout

            kind = spec["kind"]
            chart = QChart()
            if kind == "line":
                for segment in split_segments(spec["years"],
                                              spec["values"]):
                    # отрезок = своя серия: разрыв остаётся разрывом
                    part = QLineSeries()
                    for year, value in segment:
                        part.append(float(year), float(value))
                    chart.addSeries(part)
                axis_x = QValueAxis()
                axis_x.setLabelFormat("%d")
                axis_x.setTitleText("год")
                chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
                axis_y = QValueAxis()
                chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
                for series in chart.series():
                    series.attachAxis(axis_x)
                    series.attachAxis(axis_y)
            elif kind == "bars":
                series = QBarSeries()
                bar = QBarSet(spec.get("concept", ""))
                categories = []
                for year, value in zip(spec["years"], spec["values"]):
                    if value is None:
                        # год без значения выпадает из набора и из оси:
                        # нулевой столбик изображал бы нулевую меру
                        continue
                    bar.append(float(value))
                    categories.append(str(year))
                series.append(bar)
                chart.addSeries(series)
                axis_x = QBarCategoryAxis()
                axis_x.append(categories)
                chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
                axis_y = QValueAxis()
                chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
                series.attachAxis(axis_x)
                series.attachAxis(axis_y)
            elif kind == "box":
                series = QBoxPlotSeries()
                # усы схлопнуты в квартили: известных чисел три, край
                # не выдумывается (QBoxSet требует все пять позиций)
                series.append(QBoxSet(spec["p25"], spec["p25"],
                                      spec["median"], spec["p75"],
                                      spec["p75"]))
                chart.addSeries(series)
                chart.createDefaultAxes()
            else:  # radar и radar_vs — полярные
                from PySide6.QtGui import QPen
                if kind == "radar_vs":
                    series_company = QLineSeries()
                    series_group = QLineSeries()
                    axes = spec["axes"]
                    count = len(axes)
                    for i in range(count + 1):
                        axis = axes[i % count]
                        angle = 360.0 * i / count
                        series_company.append(angle, axis["value"])
                        series_group.append(angle, axis["median"])
                    chart = QPolarChart()
                    chart.addSeries(series_company)
                    chart.addSeries(series_group)
                    angular = QValueAxis()
                    angular.setRange(0, 360)
                    chart.addAxis(
                        angular,
                        QPolarChart.PolarOrientation
                        .PolarOrientationAngular)
                    radial = QValueAxis()
                    chart.addAxis(
                        radial,
                        QPolarChart.PolarOrientation
                        .PolarOrientationRadial)
                    for s in chart.series():
                        s.attachAxis(angular)
                        s.attachAxis(radial)
                    # QtCharts не подписывает вершины — состав осей
                    # виден в таблице и в подписи исключённых
                    pen = QPen()
                    pen.setStyle(Qt.PenStyle.DashLine)
                    series_group.setPen(pen)
                else:
                    series = QLineSeries()
                    axes = spec["axes"]
                    count = len(axes)
                    for i, axis in enumerate(axes + axes[:1]):
                        series.append(360.0 * i / count, axis["value"])
                    chart = QPolarChart()
                    chart.addSeries(series)
                    angular = QValueAxis()
                    angular.setRange(0, 360)
                    chart.addAxis(
                        angular,
                        QPolarChart.PolarOrientation
                        .PolarOrientationAngular)
                    radial = QValueAxis()
                    chart.addAxis(
                        radial,
                        QPolarChart.PolarOrientation
                        .PolarOrientationRadial)
                    series.attachAxis(angular)
                    series.attachAxis(radial)

            view = QChartView(chart)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(view)
