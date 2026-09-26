"""Окно десктопа EquityLab на PySide6 (TASK-C1, макет пользователя).

Только чтение (ADR-0009): всё содержимое собирает rusterm/desktop/
data.py через модель экранов TUI; здесь — раскладка и реакции.
Ни одной кнопки, которая собирает, обновляет, пишет в базу или зовёт
сеть по своей воле: единственный сетевой путь — вопрос модели в
строке снизу, той же дверью, что `rusterm chat` (make_chat_client +
ChatSession). Модуль импортируется и без PySide6 (приёмка №1).
"""
from __future__ import annotations

try:
    import uuid

    from PySide6.QtCore import QUrl, Qt
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog,
                                   QGroupBox, QHBoxLayout, QHeaderView,
                                   QInputDialog, QLabel, QLineEdit,
                                   QMainWindow, QMessageBox, QPushButton,
                                   QSplitter, QTableWidget,
                                   QTableWidgetItem, QTabWidget,
                                   QTreeWidget, QTreeWidgetItem,
                                   QVBoxLayout, QWidget)
    QT_AVAILABLE = True
except ImportError:  # приёмка №1: ядро и тесты живут без PySide6
    QT_AVAILABLE = False

from pathlib import Path as _Path

from rusterm.desktop import actions as desktop_actions
from rusterm.desktop import data
from rusterm.markets import MARKET_CODES
from rusterm.tui import model as tui_model

if QT_AVAILABLE:  # без PySide6 имя не существует, окно честно откажет
    from rusterm.desktop.charts import ChartArea

    from PySide6.QtCore import QThread
    from PySide6.QtCore import Signal as _QtSignal

    class _MainWindow(QMainWindow):
        """Главное окно с гарантией потока сбора: при закрытии живой
        воркер отменяется и ДОЖИДАЕТСЯ — QThread, уничтоженный под
        работающим потоком, роняет процесс (краш, пойманный прогоном)."""

        def __init__(self):
            super().__init__()
            self._worker = None

        def set_worker(self, worker) -> None:
            self._worker = worker

        def closeEvent(self, event) -> None:
            worker = self._worker
            if worker is not None and worker.isRunning():
                worker.cancel_flag.cancel()
                worker.wait(10000)
            event.accept()

    class _CollectWorker(QThread):
        """Сбор в рабочем потоке (ADR-0004 §3): UI не мёрзнет, стадии
        и итог приходят сигналами, отмена — кооперативная, через флаг.

        Соединение с базой открывается внутри collect_synthetic — в
        ЭТОМ потоке: sqlite-соединение не переезжает между потоками.
        """

        stage = _QtSignal(str)
        finished_run = _QtSignal(object)

        def __init__(self, root, instrument_id, parent=None):
            super().__init__(parent)
            self._root = root
            self._instrument_id = instrument_id
            self.cancel_flag = desktop_actions.CancelFlag()

        def run(self) -> None:
            outcome = desktop_actions.collect_synthetic(
                self._root, self._instrument_id,
                cancel=self.cancel_flag,
                on_stage=self.stage.emit)
            self.finished_run.emit(outcome)

WINDOW_TITLE = "EquityLab"
# ответ модели прижат влево и не шире ~3/4 окна (макет, C1.4)
ANSWER_MAX_WIDTH = 960


def _build_window(repos, paths, watchlist_id=None, rule=1):
    """Собрать окно поверх открытого (возможно пустого) каталога.

    `rule` — номер правила из `store.paths.resolve_root`, по которому
    выбран этот каталог (1 — явно назван). Шапка печатает ту же строку,
    что и `rusterm status`: «открылась не та база» и «в этой базе нет
    данных» должны различаться словами, а не догадкой (ТЗ-90 A5).
    """
    window = _MainWindow()
    window.setWindowTitle(WINDOW_TITLE)
    central = QWidget()
    window.setCentralWidget(central)
    root_layout = QVBoxLayout(central)

    # ── шапка ──────────────────────────────────────────────────────
    header = QHBoxLayout()
    header.addWidget(QLabel(WINDOW_TITLE))
    root_rule_label = QLabel(objectName="root_rule")
    root_rule_label.setText(f"каталог данных: {paths.root} "
                            f"(правило: {rule})")
    header.addWidget(root_rule_label)
    header.addStretch(1)
    status = QLabel(objectName="status")
    header.addWidget(status)
    root_layout.addLayout(header)
    # ТЗ-95 F1: отставшая от кода база — не падение окна, а одна строка
    # под шапкой: какие схемы сошлись и какой командой поднять базу.
    # Окно по-прежнему только читает (ADR-0023).
    schema_notice = QLabel(objectName="schema_notice")
    schema_notice.setWordWrap(True)
    schema_notice.setVisible(False)
    root_layout.addWidget(schema_notice)

    body = QSplitter(Qt.Orientation.Horizontal)
    root_layout.addWidget(body, 1)

    # ── левая колонка: списки, поиск и дерево отраслей (C1.1/C5.1) ─
    left = QGroupBox()
    left_layout = QVBoxLayout(left)
    watchlist_row = QHBoxLayout()
    watchlist_box = QComboBox(objectName="watchlist_box")
    watchlist_row.addWidget(watchlist_box, 1)
    watchlist_label = QLabel(objectName="watchlist_label")
    watchlist_row.addWidget(watchlist_label)
    left_layout.addLayout(watchlist_row)
    # ── кнопки списка наблюдения (C5.2/C5.3) ───────────────────────
    watchlist_buttons = QHBoxLayout()
    watchlist_add_button = QPushButton(
        objectName="watchlist_add_button")
    watchlist_add_button.setText("+ бумага")
    watchlist_remove_button = QPushButton(
        objectName="watchlist_remove_button")
    watchlist_remove_button.setText("− выбранное")
    watchlist_clear_button = QPushButton(
        objectName="watchlist_clear_button")
    watchlist_clear_button.setText("очистить список")
    for button in (watchlist_add_button, watchlist_remove_button,
                   watchlist_clear_button):
        watchlist_buttons.addWidget(button)
    left_layout.addLayout(watchlist_buttons)
    if repos is not None:
        for button in (watchlist_add_button, watchlist_remove_button,
                       watchlist_clear_button):
            button.setEnabled(True)

    search = QLineEdit(objectName="search")
    search.setPlaceholderText("поиск: тикер или название")
    left_layout.addWidget(search)
    match_count = QLabel(objectName="match_count")
    left_layout.addWidget(match_count)
    tree = QTreeWidget(objectName="tree")
    tree.setHeaderHidden(True)
    left_layout.addWidget(tree, 1)
    markets_line = QLabel(objectName="markets_line")
    left_layout.addWidget(markets_line)
    body.addWidget(left)

    # ── центр: вкладки «Компания» и «Отрасль» (C1.2/C1.3/C3) ───────
    tabs = QTabWidget(objectName="tabs")
    center = QWidget()
    center_layout = QVBoxLayout(center)
    company_header = QLabel(objectName="company_header")
    center_layout.addWidget(company_header)
    collect_row = QHBoxLayout()
    collect_button = QPushButton(objectName="collect_button")
    collect_button.setEnabled(False)
    cancel_button = QPushButton(objectName="cancel_button")
    cancel_button.setEnabled(False)
    collect_row.addWidget(collect_button)
    collect_row.addWidget(cancel_button)
    collect_status = QLabel(objectName="collect_status")
    collect_row.addWidget(collect_status, 1)
    center_layout.addLayout(collect_row)
    export_row = QHBoxLayout()
    export_csv_button = QPushButton(objectName="export_csv_button")
    export_csv_button.setText("экспорт csv")
    export_md_button = QPushButton(objectName="export_md_button")
    export_md_button.setText("экспорт md")
    save_png_button = QPushButton(objectName="save_png_button")
    save_png_button.setText("график в png")
    for button in (export_csv_button, export_md_button, save_png_button):
        button.setEnabled(False)
        export_row.addWidget(button)
    export_row.addStretch(1)
    center_layout.addLayout(export_row)
    controls = QHBoxLayout()
    kind_box = QComboBox(objectName="kind_box")
    for kind in data.CHART_KINDS:
        kind_box.addItem(data.CHART_KIND_LABELS[kind], userData=kind)
    controls.addWidget(kind_box)
    measure_box = QComboBox(objectName="measure_box")
    controls.addWidget(measure_box, 1)
    center_layout.addLayout(controls)
    chart_area = ChartArea()
    chart_area.setObjectName("chart_area")
    center_layout.addWidget(chart_area, 2)
    table = QTableWidget(objectName="table")
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    center_layout.addWidget(table, 3)
    source_panel = QLabel(objectName="source_panel")
    source_panel.setWordWrap(True)
    center_layout.addWidget(source_panel)
    stale_button = QPushButton(objectName="stale_button")
    stale_button.setText("показать устаревшие входы")
    stale_button.setVisible(False)
    center_layout.addWidget(stale_button)
    open_raw_button = QPushButton(objectName="open_raw_button")
    open_raw_button.setText("открыть сохранённый ответ")
    open_raw_button.setEnabled(False)
    center_layout.addWidget(open_raw_button)
    tabs.addTab(center, "Компания")

    # ── вкладка «Отрасль» (TASK-C3) ────────────────────────────────
    industry = QWidget()
    industry_layout = QVBoxLayout(industry)
    peer_line = QLabel(objectName="peer_line")
    peer_line.setWordWrap(True)
    industry_layout.addWidget(peer_line)
    members_line = QLabel(objectName="members_line")
    members_line.setWordWrap(True)
    industry_layout.addWidget(members_line)
    industry_table = QTableWidget(objectName="industry_table")
    industry_table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows)
    industry_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch)
    industry_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    industry_table.setSortingEnabled(True)  # сортировка по любой мере
    industry_layout.addWidget(industry_table, 3)
    industry_controls = QHBoxLayout()
    industry_controls.addWidget(QLabel("мера:"))
    industry_measure_box = QComboBox(
        objectName="industry_measure_box")
    industry_controls.addWidget(industry_measure_box, 1)
    industry_layout.addLayout(industry_controls)
    industry_chart = ChartArea()
    industry_chart.setObjectName("industry_chart")
    industry_layout.addWidget(industry_chart, 2)
    radar_chart = ChartArea()
    radar_chart.setObjectName("radar_chart")
    industry_layout.addWidget(radar_chart, 2)
    excluded_label = QLabel(objectName="excluded_label")
    excluded_label.setWordWrap(True)
    industry_layout.addWidget(excluded_label)
    tabs.addTab(industry, "Отрасль")

    # ── вкладка «Качество» (TASK-C8) ───────────────────────────────
    quality = QWidget()
    quality_layout = QVBoxLayout(quality)
    coverage_label = QLabel(objectName="coverage_label")
    coverage_label.setWordWrap(True)
    quality_layout.addWidget(coverage_label)
    governance_table = QTableWidget(objectName="governance_table")
    governance_table.setColumnCount(3)
    governance_table.setHorizontalHeaderLabels(
        ["показатель", "цвет", "расшифровка"])
    governance_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch)
    governance_table.setEditTriggers(QTableWidget.EditTrigger
                                     .NoEditTriggers)
    quality_layout.addWidget(governance_table, 1)
    tabs.addTab(quality, "Качество")

    # ── вкладка «Настройки» (TASK-C9) ──────────────────────────────
    settings = QWidget()
    settings_layout = QVBoxLayout(settings)
    keys_label = QLabel(objectName="keys_label")
    keys_label.setWordWrap(True)
    settings_layout.addWidget(keys_label)
    limits_table = QTableWidget(objectName="limits_table")
    limits_table.setColumnCount(4)
    limits_table.setHorizontalHeaderLabels(
        ["хост", "потолок за ночь", "запросов/сек", "правка"])
    limits_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch)
    limits_table.setEditTriggers(QTableWidget.EditTrigger
                                 .NoEditTriggers)
    settings_layout.addWidget(limits_table, 1)
    catalog_label = QLabel(objectName="catalog_label")
    catalog_label.setWordWrap(True)
    settings_layout.addWidget(catalog_label)
    switch_root_button = QPushButton(objectName="switch_root_button")
    switch_root_button.setText("сменить каталог данных")
    settings_layout.addWidget(switch_root_button)
    tabs.addTab(settings, "Настройки")
    body.addWidget(tabs)
    body.setStretchFactor(1, 1)

    # ── низ: разговор (C1.4/C7) ────────────────────────────────────
    chat_box = QGroupBox()
    chat_layout = QVBoxLayout(chat_box)
    chat_header = QHBoxLayout()
    llm_usage_label = QLabel(objectName="llm_usage_label")
    chat_header.addWidget(llm_usage_label, 1)
    chat_sessions_box = QComboBox(objectName="chat_sessions_box")
    chat_sessions_box.addItem("прошлые разговоры", userData=None)
    chat_header.addWidget(chat_sessions_box, 1)
    chat_layout.addLayout(chat_header)
    answer_label = QLabel(objectName="answer_label")
    answer_label.setWordWrap(True)
    answer_label.setMaximumWidth(ANSWER_MAX_WIDTH)
    answer_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    chat_layout.addWidget(answer_label)
    question_line = QLineEdit(objectName="question_line")
    question_line.setPlaceholderText("спросить о том, что на экране…")
    chat_layout.addWidget(question_line)
    root_layout.addWidget(chat_box)

    state = {"companies": [], "selected": None, "table": None,
             "watchlist": watchlist_id, "open_raw_target": None,
             "industry": None, "peer": None, "pinned": set(),
             "session": None, "chat_reason": None, "worker": None,
             "source_measure_row": None, "stale_detail": False}

    collect_button.setText("Собрать")
    cancel_button.setText("Отменить")

    # ── жизнь окна ─────────────────────────────────────────────────
    def repaint_header() -> None:
        if repos is None:
            status.setText("")
            schema_notice.setText("")
            schema_notice.setVisible(False)
            return
        info = data.header_info(repos)
        budget = desktop_actions.budget_view(repos)
        schema = info["schema_version"]
        notice = info["schema_notice"]
        schema_notice.setText(notice or "")
        schema_notice.setVisible(bool(notice))
        status.setText(
            f"схема {schema if schema is not None else '—'}"
            f" · запросов сегодня {budget['used_today']}"
            f" · потолок {budget['ceiling_per_night']}")

    def repaint_sidebar(query: str = "") -> None:
        tree.clear()
        if repos is None:
            match_count.setText("")
            markets_line.setText("")
            return
        tree_data = data.sector_tree(state["companies"], query)
        expanded = data.expanded_sectors(tree_data, query,
                                         state["pinned"])
        matches = sum(len(node["companies"]) for node in tree_data)
        query_text = (query or "").strip()
        match_count.setText(
            f"совпадений: {matches}" if query_text
            else f"компаний: {len(state['companies'])}")
        for node in tree_data:
            sector_item = QTreeWidgetItem(
                [f"▾ {node['sector']} · {len(node['companies'])}"])
            sector_item.setData(0, Qt.ItemDataRole.UserRole,
                                ("sector", node["sector"]))
            tree.addTopLevelItem(sector_item)
            for company in node["companies"]:
                label = company["ticker"]
                if company.get("name"):
                    label = f"{label} · {company['name']}"
                item = QTreeWidgetItem([label])
                item.setData(0, Qt.ItemDataRole.UserRole,
                             ("company", company))
                sector_item.addChild(item)
            sector_item.setExpanded(node["sector"] in expanded)
        present = {c["market"] for c in state["companies"]
                   if c["market"] != "—"}
        # ТЗ-60 E4: степень канала теми же словами, что `rusterm markets`
        degrees = data.channel_degrees(repos)
        with_degree = sorted(
            c for c in present if degrees.get(c, "—") != "—")
        line = f"{len(present)} из {len(MARKET_CODES)} рынков"
        if with_degree:
            line += " · " + ", ".join(
                f"{c} — {degrees[c]}" for c in with_degree)
        markets_line.setText(line)

    def repaint_watchlists() -> None:
        """C5.1: списки в переключателе, версия и состав видны."""
        if repos is None:
            watchlist_box.clear()
            watchlist_label.setText("")
            return
        choices = data.watchlist_choices(repos)
        watchlist_box.blockSignals(True)
        watchlist_box.clear()
        for choice in choices:
            watchlist_box.addItem(
                f"{choice['name']} ({choice['watchlist_id']})",
                userData=choice["watchlist_id"])
        index = watchlist_box.findData(state.get("watchlist"))
        if index < 0 and choices:
            # ТЗ-72 Д2: выбранного нет в перечне (не передан или устарел)
            # — показан первый список, и подпись говорит про него же,
            # а не «списков нет» при видимом выборе
            index = 0
        if index >= 0:
            watchlist_box.setCurrentIndex(index)
            state["watchlist"] = choices[index]["watchlist_id"]
        watchlist_box.blockSignals(False)
        current = next((c for c in choices
                        if c["watchlist_id"] == state.get("watchlist")),
                       None)
        watchlist_label.setText(
            f"v{current['version']} · {current['member_count']} бумаг"
            if current else "списков нет")

    def on_watchlist_switch(index: int) -> None:
        state["watchlist"] = watchlist_box.itemData(index)
        state["selected"] = None
        state["companies"] = (data.sidebar_companies(
            repos, state["watchlist"]) if repos else [])
        repaint_sidebar("")
        repaint_watchlists()

    def on_watchlist_add() -> None:
        """C5.2: добавление через те же двери ядра, что CLI add.
"""
        watchlist_id = state.get("watchlist")
        if repos is None or not watchlist_id:
            QMessageBox.warning(window, "список",
                                "списков нет; " + data.NO_WATCHLISTS_HINT)
            return
        text, ok = QInputDialog.getText(
            window, "добавить бумагу",
            "тикер и рынок (например: CNQ TSX):")
        if not ok or not text.strip():
            return
        parts = text.split()
        outcome = data.add_instrument(repos, watchlist_id,
                                      parts[0],
                                      parts[1] if len(parts) > 1 else "")
        if not outcome["ok"]:
            QMessageBox.warning(window, "добавление", outcome["message"])
            return
        state["companies"] = data.sidebar_companies(repos, watchlist_id)
        repaint_sidebar("")
        repaint_watchlists()

    def on_watchlist_remove() -> None:
        """C5.2: удаление выбранной бумаги; версия новая, старая
        доступна."""
        watchlist_id = state.get("watchlist")
        selected = state.get("selected")
        if repos is None or not watchlist_id:
            QMessageBox.warning(window, "список",
                                "списков нет; " + data.NO_WATCHLISTS_HINT)
            return
        if not selected:
            QMessageBox.warning(window, "удаление",
                                "выберите бумагу в дереве слева")
            return
        outcome = data.remove_instruments(repos, watchlist_id,
                                          [selected["instrument_id"]])
        if not outcome["ok"]:
            QMessageBox.warning(window, "удаление", outcome["message"])
            return
        state["companies"] = data.sidebar_companies(repos, watchlist_id)
        state["selected"] = None
        repaint_sidebar("")
        repaint_watchlists()

    def on_watchlist_clear() -> None:
        """C5.3: массовая операция — подтверждение и одна строка
        аудита; без подтверждения слой данных откажет словами."""
        watchlist_id = state.get("watchlist")
        if repos is None or not watchlist_id:
            QMessageBox.warning(window, "список",
                                "списков нет; " + data.NO_WATCHLISTS_HINT)
            return
        ids = [c["instrument_id"] for c in state["companies"]]
        outcome = data.remove_instruments(repos, watchlist_id, ids)
        if outcome.get("needs_confirm"):
            answer = QMessageBox.question(
                window, "очистить список",
                outcome["message"] + " — продолжить?")
            if answer != QMessageBox.StandardButton.Yes:
                return
            outcome = data.remove_instruments(repos, watchlist_id, ids,
                                              confirmed=True)
        if not outcome["ok"]:
            QMessageBox.warning(window, "очистка", outcome["message"])
            return
        state["companies"] = data.sidebar_companies(repos, watchlist_id)
        state["selected"] = None
        repaint_sidebar("")
        repaint_watchlists()

    def load_company(company: dict) -> None:
        state["selected"] = company
        width_years = max(4, table.width() // 90)
        state["table"] = data.measure_table_rows(
            repos, company["instrument_id"], width_years)
        info = state["table"]
        company_header.setText(
            f"{info['ticker']} · {info['name'] or '—'}"
            f" · {company['market']}")
        sector = company.get("sector")
        state["industry"] = (tui_model.industry_rows(repos, sector)
                             if sector else None)
        state["peer"] = data.peer_screen(repos,
                                         company["instrument_id"])
        state["card"] = info["card"]
        _repaint_table(table, info)
        _repaint_measures(measure_box, info)
        apply_chart()
        _repaint_industry()
        repaint_quality()
        repaint_settings()
        # ТЗ-75 V1: истории нет — под таблицей исполнимая строка
        # «посчитать ряд одним действием», а не стена пустых колонок;
        # ТЗ-72 S5: тонкий источник — слова вместо стены прочерков;
        # ТЗ-81 B2: колонок меньше запрошенных — словами почему
        source_panel.setText(info.get("suggestion")
                             or " · ".join(x for x in
                                           (info.get("history_note"),
                                            info.get("summary_line")) if x)
                             or "клик по ячейке — панель источника")
        # ТЗ-72 Д4: панель источника новой бумаги — свёрнутая
        state["source_measure_row"] = None
        state["stale_detail"] = False
        stale_button.setVisible(False)
        collect_button.setEnabled(state["worker"] is None)
        for button in (export_csv_button, export_md_button,
                       save_png_button):
            button.setEnabled(True)

    def apply_chart() -> None:
        if state["table"] is None:
            return
        kind = kind_box.currentData() or "line"
        spec = data.chart_spec(kind, state["table"], state["industry"],
                               measure_box.currentData())
        chart_area.set_spec(spec)

    def apply_industry_chart() -> None:
        screen = state["industry"]
        if screen is None:
            industry_chart.set_spec({
                "kind": "message",
                "text": "нет данных: у компании нет peer set"})
            return
        spec = data.industry_chart_spec(
            screen, industry_measure_box.currentData())
        industry_chart.set_spec(spec)

    def _repaint_industry() -> None:
        """Вкладка «Отрасль» (TASK-C3): peer set словами, таблица с
        пометками отказов, box-plot и радар против медианы группы."""
        peer = state["peer"]
        screen = state["industry"]
        if peer is None or not peer["has_peer_set"]:
            peer_line.setText(peer["message"] if peer else
                              "у компании нет peer set")
            members_line.setText("")
        else:
            peer_line.setText(
                f"peer set {peer['peer_set_id']} v{peer['version']}"
                f" · {peer['scope']}"
                f" ({', '.join(peer['markets']) or '—'})"
                f" · {peer['rule']}")
            members = ", ".join(
                m["ticker"] + (" ← вы" if m["is_self"] else "")
                for m in peer["members"])
            members_line.setText(f"участники ({len(peer['members'])}):"
                                 f" {members}")
        rows = data.industry_table_rows(screen) if screen else []
        industry_table.setSortingEnabled(False)  # на время заполнения
        industry_table.setColumnCount(6)
        industry_table.setHorizontalHeaderLabels(
            ["мера", "p25", "медиана", "p75", "n", "отказ"])
        industry_table.setRowCount(len(rows))
        for row, r in enumerate(rows):
            industry_table.setItem(row, 0, _sort_item(r["concept"],
                                                      r["concept"]))
            for column, key in ((1, "p25"), (2, "median"), (3, "p75")):
                industry_table.setItem(
                    row, column,
                    _number_item(r[key], r["refused"]))
            industry_table.setItem(row, 4,
                                   _number_item(r["n"], r["refused"]))
            industry_table.setItem(row, 5, _sort_item(r["mark"],
                                                      r["mark"]))
        industry_table.setSortingEnabled(True)
        industry_measure_box.blockSignals(True)
        industry_measure_box.clear()
        if screen is not None:
            for r in screen.get("rows", []):
                mark = "" if not r.get("null_reason") \
                    else " · отказ"
                industry_measure_box.addItem(r["concept"] + mark,
                                             userData=r["concept"])
        industry_measure_box.blockSignals(False)
        apply_industry_chart()
        # радар «компания против группы» + исключённые счётчиком
        if screen is not None and state["table"] is not None:
            rspec = data.radar_vs_group_spec(state["table"], screen)
            radar_chart.set_spec(rspec)
            if rspec["kind"] == "radar_vs":
                excluded_label.setText(
                    "радар: компания (сплошная) против медианы группы"
                    " (пунктир); исключены — без данных компании: "
                    f"{rspec['excluded_company']},"
                    " без данных группы: "
                    f"{rspec['excluded_group']}")
            else:
                excluded_label.setText(rspec["text"])
        else:
            radar_chart.set_spec({
                "kind": "message", "text": "нет данных"})
            excluded_label.setText("")

    def on_search(text: str) -> None:
        repaint_sidebar(text)

    def sector_of(item) -> str | None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        return payload[1] if payload and payload[0] == "sector" else None

    def on_item_expanded(item) -> None:
        name = sector_of(item)
        if name and not (search.text() or "").strip():
            state["pinned"].add(name)

    def on_item_collapsed(item) -> None:
        name = sector_of(item)
        if name and not (search.text() or "").strip():
            state["pinned"].discard(name)

    def on_tree_selection() -> None:
        item = tree.currentItem()
        if item is None or repos is None:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if payload and payload[0] == "company":
            load_company(payload[1])

    def repaint_quality() -> None:
        """C8: покрытие мер (те же строки, что rusterm coverage),
        пометки устаревания и governance пятью цветами с расшифровкой
        из ядра; цвет в окне не вычисляется."""
        if repos is None or state["table"] is None:
            coverage_label.setText("качества нет — базы нет")
            governance_table.setRowCount(0)
            return
        instrument_id = state["selected"]["instrument_id"]
        coverage = data.measure_coverage(repos, instrument_id)
        if not coverage["has_snapshot"]:
            coverage_label.setText("снапшота нет — качество мер не "
                                   "измерить; сначала rusterm ingest")
        else:
            reasons = ", ".join(f"{token}: {count}" for token, count
                                in sorted(coverage["reasons"].items()))
            tail = f"; отказы — {reasons}" if reasons else ""
            coverage_label.setText(
                f"покрытие мер: {coverage['green']} из "
                f"{coverage['total']}{tail}")
        governance = data.governance_view(state["card"])
        governance_table.setRowCount(len(governance["rows"]))
        for row, g in enumerate(governance["rows"]):
            note = g["note"] or (f"причина: {g['reason']}"
                                 if g["reason"] else "")
            for column, text in enumerate((g["indicator"], g["color"],
                                           note)):
                governance_table.setItem(
                    row, column, QTableWidgetItem(text))

    def repaint_settings() -> None:
        """C9: ключи без значений (откуда и зачем), лимиты из
        реестра с оверрайдами из конфигурации ядра, каталог данных."""
        if repos is None:
            keys_label.setText("настроек нет — базы нет")
            limits_table.setRowCount(0)
            catalog_label.setText("")
            return
        keys = data.keys_view()
        lines = [f"ключи (файл: {keys['file']}):"]
        for row in keys["rows"]:
            state_word = f"найден, {row['origin']}" if row["found"] \
                else f"нет — {row['purpose']}"
            lines.append(f"  {row['name']}: {state_word}")
        keys_label.setText("\n".join(lines))
        limits = data.host_limits_view(paths)
        limits_table.setRowCount(len(limits["rows"]))
        for row, entry in enumerate(limits["rows"]):
            override = (f"{entry['override']}/сек"
                        if entry["override"] is not None else "—")
            for column, text in enumerate(
                    (entry["host"], str(entry["nightly_max"]),
                     str(entry["per_second"]), override)):
                limits_table.setItem(row, column,
                                     QTableWidgetItem(text))
        catalog = data.catalog_view(paths)
        if catalog["exists"]:
            catalog_label.setText(
                f"каталог: {catalog['root']}\nбаза: "
                f"{catalog['db_path']} ({catalog['size_bytes']} байт,"
                f" обновлялась {catalog['updated_at']})")
        else:
            catalog_label.setText(
                f"каталог: {catalog['root']} — базы нет; "
                "начните с rusterm init")

    def on_switch_root() -> None:
        """C9.3: смена каталога. Молчаливого создания нет: каталога
        данных нет — вопрос, и только подтверждение запускает новое
        окно поверх выбранного корня."""
        chosen = QFileDialog.getExistingDirectory(
            window, "каталог данных", paths.root)
        if not chosen:
            return
        decision = data.catalog_switch_decision(chosen)
        if not decision["exists"]:
            answer = QMessageBox.question(
                window, "сменить каталог",
                "в выбранном каталоге данных нет — создать и открыть "
                "его? (сбор запускается отдельно)")
            if answer != QMessageBox.StandardButton.Yes:
                status.setText("смена каталога отменена — "
                               "ничего не создано")
                return
        import sys as _sys
        _sys.argv = [_sys.argv[0], "--root", chosen]
        window.close()
        from rusterm.desktop.__main__ import main as desktop_main
        raise SystemExit(desktop_main(["--root", chosen]))

    def on_limit_edit(row: int, _column: int) -> None:
        limits = data.host_limits_view(paths)
        if row >= len(limits["rows"]):
            return
        entry = limits["rows"][row]
        text, ok = QInputDialog.getText(
            window, "лимит хоста",
            f"запросов/сек для {entry['host']} "
            f"(реестр: {entry['per_second']}):",
            text=str(entry["override"]
                     if entry["override"] is not None
                     else entry["per_second"]))
        if not ok or not text.strip():
            return
        try:
            value = float(text)
        except ValueError:
            QMessageBox.warning(window, "лимит хоста",
                                "нужно число, например 0.5")
            return
        outcome = data.set_host_rate_limit(paths, entry["host"], value)
        if not outcome["ok"]:
            QMessageBox.warning(window, "лимит хоста",
                                "дверь конфигурации не приняла правку")
        repaint_settings()

    limits_table.cellDoubleClicked.connect(on_limit_edit)
    switch_root_button.clicked.connect(on_switch_root)

    def on_open_raw() -> None:
        """C6.2: сохранённый ответ открывают средства системы; файла
        нет — кнопка неактивна, слова в панели."""
        target = state.get("open_raw_target")
        if target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    def show_source_panel(detail: bool) -> None:
        """ТЗ-72 Д4: панель источника перерисовывается с тем же рядом
        мер — свёрнуто или с полным перечнем устаревших входов."""
        info = state["table"]
        measure_row = state.get("source_measure_row")
        if info is None or repos is None or measure_row is None:
            return
        view = data.source_panel_view(repos, paths, measure_row,
                                      instrument_id=info["instrument_id"],
                                      stale_detail=detail)
        source_panel.setText(view["text"])
        state["open_raw_target"] = view["open_target"]
        open_raw_button.setEnabled(view["open_target"] is not None)
        count = view["stale_count"]
        stale_button.setVisible(count > 0)
        stale_button.setText(
            f"скрыть устаревшие входы: {count}" if detail
            else f"показать устаревшие входы: {count}")

    def on_cell_clicked(row: int, _column: int) -> None:
        info = state["table"]
        if info is None or repos is None:
            return
        state["source_measure_row"] = info["measures"][row]
        state["stale_detail"] = False
        show_source_panel(False)

    def on_toggle_stale() -> None:
        state["stale_detail"] = not state.get("stale_detail")
        show_source_panel(state["stale_detail"])

    def setup_chat() -> None:
        if repos is None:
            state["chat_reason"] = "нет базы — спросить не о чем"
            return
        from rusterm.core.chat import ChatSession
        from rusterm.core.llm import make_chat_client
        client = make_chat_client()
        reason = data.chat_unavailable_reason(client)
        state["chat_reason"] = reason
        state["session"] = None if reason else ChatSession(repos, client)
        state["chat_session_id"] = (None if reason
                                    else str(uuid.uuid4()))

    def repaint_chat_usage() -> None:
        """C7.2: вызовы из calls_totals — то же место, что
        rusterm status; ключ не показывается никогда."""
        llm_usage_label.setText(
            data.llm_usage_line(repos) if repos else "вызовы: —")

    def repaint_chat_sessions() -> None:
        """C7.1: прошлые разговоры в переключателе, свежие сверху;
        переживают перезапуск окна — читаются из базы."""
        chat_sessions_box.blockSignals(True)
        chat_sessions_box.clear()
        chat_sessions_box.addItem("прошлые разговоры", userData=None)
        if repos is not None:
            for session in data.chat_sessions(repos):
                chat_sessions_box.addItem(
                    f"{session['session_id'][:8]}… · "
                    f"{session['calls']} вызов.",
                    userData=session["session_id"])
        chat_sessions_box.blockSignals(False)

    def on_session_open(index: int) -> None:
        session_id = chat_sessions_box.itemData(index)
        if repos is None or not session_id:
            return
        answer_label.setText(
            "\n".join(data.chat_transcript_lines(repos, session_id)))

    def on_ask() -> None:
        question = question_line.text().strip()
        if not question:
            return
        if state["session"] is None:
            reason = state["chat_reason"] or "модель недоступна"
            answer_label.setText(f"модель недоступна: {reason}")
            return
        # вопрос модели синхронный: соединение sqlite не переезжает в
        # другой поток; вынос в QThreadPool — вопрос ТЗ-C7
        result = state["session"].ask(question)
        # C7.1: расшифровка переживает перезапуск — та же дверь, что
        # у CLI chat (save_transcript в chat_transcript/chat_turn)
        from rusterm.core.chat import save_transcript
        save_transcript(repos, state["session"],
                        state["chat_session_id"])
        repaint_chat_usage()
        repaint_chat_sessions()
        if result.get("rejected"):
            # C7.3: ответ без цитаты — не ответ: в панели отказ с
            # причиной, сам бракованный текст не показывается
            answer_label.setText(f"отказ: {result.get('reason')}")
            return
        citations = "\n".join(f"цитата: {c}"
                             for c in result.get("citations") or [])
        text = result.get("answer") or ""
        answer_label.setText(text + ("\n" + citations if citations else ""))
        question_line.clear()

    def on_collect() -> None:
        """Кнопка «Собрать»: демо-конвейер в рабочем потоке; для
        остальных инструментов — слова с командой CLI, без копии тела
        cmd_ingest (C2.1)."""
        if state["worker"] is not None or repos is None:
            return
        company = state["selected"]
        if company is None:
            return
        instrument_id = company["instrument_id"]
        if instrument_id != desktop_actions.demo_instrument_id():
            # отказ синтетического сбора возвращается до всякого ввода-
            # вывода — безопасно позвать прямо в UI-потоке
            outcome = desktop_actions.collect_synthetic(
                paths.root, instrument_id)
            collect_status.setText(f"сбор не удался: {outcome.detail}")
            return
        worker = _CollectWorker(paths.root, instrument_id,
                                parent=window)
        window.set_worker(worker)
        state["worker"] = worker
        collect_button.setEnabled(False)
        cancel_button.setEnabled(True)
        worker.stage.connect(collect_status.setText)
        worker.finished_run.connect(on_collect_done)
        collect_status.setText("сбор запущен")
        worker.start()

    def on_collect_cancel() -> None:
        worker = state["worker"]
        if worker is not None:
            worker.cancel_flag.cancel()
            collect_status.setText("отмена…")

    def on_collect_done(outcome) -> None:
        state["worker"] = None
        window.set_worker(None)
        collect_button.setEnabled(state["selected"] is not None)
        cancel_button.setEnabled(False)
        if outcome.cancelled:
            collect_status.setText(f"отменено: {outcome.detail}")
        elif outcome.ok:
            collect_status.setText(f"готово: {outcome.detail}")
        else:
            collect_status.setText(
                f"сбор не удался: {outcome.reason} — {outcome.detail}")
        # карточка и бюджет перечитываются из базы теми же дверями
        if state["selected"] is not None:
            load_company(state["selected"])
        repaint_header()

    # соединения
    search.textChanged.connect(on_search)
    tree.itemExpanded.connect(on_item_expanded)
    tree.itemCollapsed.connect(on_item_collapsed)
    def _export_table(fmt: str) -> None:
        """C4.1+C4.3: видимая таблица уходит в файл тем же кодом ядра,
        что rusterm export (значения и слова отказа не пересобираются);
        адрес спрашивает диалог, каталог по умолчанию — exports/."""
        selected = state.get("selected")
        if not selected:
            return
        text = (data.export_table_csv(repos, selected["instrument_id"])
                if fmt == "csv" else
                data.export_table_md(repos, selected["instrument_id"]))
        if text is None:
            return
        target, _filter = QFileDialog.getSaveFileName(
            window, f"экспорт {fmt}", str(paths.root / "exports"),
            f"*.{fmt}")
        if not target:
            return
        _Path(target).write_text(text, encoding="utf-8")

    def on_save_png() -> None:
        """C4.2: текущий график в png с подписью (эмитент, мера,
        период, дата выгрузки)."""
        if not state.get("table"):
            return
        concept = measure_box.currentData() or ""
        period = ""
        for row in state["table"]["measures"]:
            if row["concept"] == concept:
                period = row["measure"].get("period") or ""
                break
        caption = data.chart_caption(state["table"], concept, period)
        target, _filter = QFileDialog.getSaveFileName(
            window, "сохранить график", str(paths.root / "exports"),
            "*.png")
        if not target:
            return
        chart_area.save_png(target, caption)

    export_csv_button.clicked.connect(lambda: _export_table("csv"))
    export_md_button.clicked.connect(lambda: _export_table("md"))
    save_png_button.clicked.connect(on_save_png)
    tree.itemSelectionChanged.connect(on_tree_selection)
    watchlist_add_button.clicked.connect(on_watchlist_add)
    watchlist_remove_button.clicked.connect(on_watchlist_remove)
    watchlist_clear_button.clicked.connect(on_watchlist_clear)
    watchlist_box.currentIndexChanged.connect(on_watchlist_switch)
    kind_box.currentIndexChanged.connect(lambda _i: apply_chart())
    measure_box.currentIndexChanged.connect(lambda _i: apply_chart())
    industry_measure_box.currentIndexChanged.connect(
        lambda _i: apply_industry_chart())
    table.cellClicked.connect(on_cell_clicked)
    stale_button.clicked.connect(on_toggle_stale)
    open_raw_button.clicked.connect(on_open_raw)
    question_line.returnPressed.connect(on_ask)
    chat_sessions_box.currentIndexChanged.connect(on_session_open)
    collect_button.clicked.connect(on_collect)
    cancel_button.clicked.connect(on_collect_cancel)

    # стартовое состояние
    if repos is None:
        message = data.empty_base_message(paths)
        company_header.setText(message)
        answer_label.setText(message)
        repaint_sidebar("")
    else:
        # ТЗ-72 Д2: переключатель синхронизируется до боковой панели,
        # чтобы видимый список и состав слева были про одно и то же
        repaint_watchlists()
        if data.watchlist_choices(repos):
            state["companies"] = data.sidebar_companies(
                repos, state["watchlist"])
        else:
            # ТЗ-72 S4: списков нет, инструменты есть — окно показывает
            # инструменты и предлагает собрать список одной командой
            state["companies"] = data.all_instruments(repos)
            if state["companies"]:
                company_header.setText(
                    f"списков нет; показаны все инструменты базы — "
                    f"{data.NO_WATCHLISTS_HINT}")
        if not state["companies"]:
            company_header.setText(data.empty_base_instruments_message())
        repaint_sidebar("")
    repaint_watchlists()
    repaint_settings()
    repaint_chat_usage()
    repaint_chat_sessions()
    repaint_header()
    setup_chat()
    if state["chat_reason"]:
        question_line.setPlaceholderText(
            f"модель недоступна: {state['chat_reason']}")
    return window


def _sort_item(text: str, sort_key: str):
    """Ячейка-строка: сортируется по своему тексту."""
    item = QTableWidgetItem(text)
    item.setData(Qt.ItemDataRole.DisplayRole, sort_key)
    return item


def _number_item(value, refused: bool):
    """Ячейка числа: сортируется как число, показывается текстом;
    отказ — «нет данных», при сортировке уходит по алфавиту и виден
    по колонке «отказ», не молча."""
    if refused:
        return QTableWidgetItem(data.NO_DATA)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return QTableWidgetItem(str(value or data.NO_DATA))
    item = QTableWidgetItem()
    item.setData(Qt.ItemDataRole.DisplayRole, number)
    return item


def _repaint_table(table, info: dict) -> None:
    years = info["years"]
    table.setColumnCount(2 + len(years))
    table.setHorizontalHeaderLabels(["мера", "сейчас", *years])
    table.setRowCount(len(info["measures"]))
    for row, measure in enumerate(info["measures"]):
        table.setItem(row, 0, QTableWidgetItem(measure["concept"]))
        table.setItem(row, 1, QTableWidgetItem(measure["current"]))
        for column, year in enumerate(years):
            table.setItem(row, 2 + column,
                          QTableWidgetItem(measure["years"][year]))


def _repaint_measures(box, info: dict) -> None:
    box.blockSignals(True)
    box.clear()
    for measure in info["measures"]:
        mark = "" if measure["has_value"] else " · нет данных"
        box.addItem(measure["concept"] + mark,
                    userData=measure["concept"])
    box.blockSignals(False)


def run(root, watchlist_id=None, rule=1) -> int:
    """Точка входа python3 -m rusterm.desktop: только чтение.

    `rule` — номер правила поиска каталога (см. `_build_window`);
    корень, который назвал сам пользователь, — правило 1.
    """
    import os as _os
    if not QT_AVAILABLE:
        print("PySide6 не установлен: pip install 'rusterm[desktop]'",
              flush=True)
        return 1
    paths, conn = data.open_readonly(root)
    repos = None
    if conn is not None:
        from rusterm.store.repos import RepoRegistry
        repos = RepoRegistry(conn, paths)
    app = QApplication.instance() or QApplication([])
    window = _build_window(repos, paths, watchlist_id, rule)
    window.resize(1280, 800)
    window.show()
    if _os.environ.get("RUSTERM_APP_SMOKE"):
        # C10.4: smoke-прогон сборки — окно стартовало и закрывается
        # само; в обычной работе переменной нет и окно живёт
        # ТЗ-81 B3: строка о том, какой каталог открыт, — чтобы прогон
        # собранного бинарника доказывал правило поиска, а не только
        # «запустилось и не упало». С круга 111 номер правила в той же
        # строке: .app из Finder обязан показать, что взял его из
        # ~/.rusterm.env, а не из ~/.rusterm.
        print(f"rusterm-app root={paths.root} (правило: {rule})",
              flush=True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1200, window.close)
    code = app.exec()
    if conn is not None:
        conn.close()
    return code
