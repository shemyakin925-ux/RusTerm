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
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog,
                                   QGroupBox, QHBoxLayout, QHeaderView,
                                   QLabel, QLineEdit, QMainWindow,
                                   QMessageBox, QPushButton, QSplitter,
                                   QTableWidget, QTableWidgetItem,
                                   QTabWidget, QTreeWidget,
                                   QTreeWidgetItem, QVBoxLayout,
                                   QWidget)
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


def _build_window(repos, paths, watchlist_id=None):
    """Собрать окно поверх открытого (возможно пустого) каталога."""
    window = _MainWindow()
    window.setWindowTitle(WINDOW_TITLE)
    central = QWidget()
    window.setCentralWidget(central)
    root_layout = QVBoxLayout(central)

    # ── шапка ──────────────────────────────────────────────────────
    header = QHBoxLayout()
    header.addWidget(QLabel(WINDOW_TITLE))
    header.addStretch(1)
    status = QLabel(objectName="status")
    header.addWidget(status)
    root_layout.addLayout(header)

    body = QSplitter(Qt.Orientation.Horizontal)
    root_layout.addWidget(body, 1)

    # ── левая колонка: списки, поиск и дерево отраслей (C1.1/C5) ───
    left = QGroupBox()
    left_layout = QVBoxLayout(left)
    watchlist_box = QComboBox(objectName="watchlist_box")
    left_layout.addWidget(watchlist_box)
    watchlist_line = QLabel(objectName="watchlist_line")
    left_layout.addWidget(watchlist_line)
    version_row = QHBoxLayout()
    version_box = QComboBox(objectName="version_box")
    version_row.addWidget(version_box, 1)
    rollback_button = QPushButton(objectName="rollback_button")
    rollback_button.setEnabled(False)
    version_row.addWidget(rollback_button)
    left_layout.addLayout(version_row)
    add_row = QHBoxLayout()
    add_ticker = QLineEdit(objectName="add_ticker")
    add_ticker.setPlaceholderText("тикер")
    add_market = QLineEdit(objectName="add_market")
    add_market.setPlaceholderText("рынок")
    add_button = QPushButton(objectName="add_button")
    add_button.setText("Добавить")
    add_row.addWidget(add_ticker, 1)
    add_row.addWidget(add_market)
    add_row.addWidget(add_button)
    left_layout.addLayout(add_row)
    remove_button = QPushButton(objectName="remove_button")
    remove_button.setText("Убрать из списка")
    remove_button.setEnabled(False)
    left_layout.addWidget(remove_button)
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
    body.addWidget(tabs)
    body.setStretchFactor(1, 1)

    # ── низ: разговор (C1.4) ───────────────────────────────────────
    chat_box = QGroupBox()
    chat_layout = QVBoxLayout(chat_box)
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
             "industry": None, "peer": None, "pinned": set(),
             "session": None, "chat_reason": None, "worker": None,
             "watchlist": watchlist_id}

    collect_button.setText("Собрать")
    cancel_button.setText("Отменить")
    rollback_button.setText("Откатить")

    # ── жизнь окна ─────────────────────────────────────────────────
    def repaint_header() -> None:
        if repos is None:
            status.setText("")
            return
        info = data.header_info(repos)
        budget = desktop_actions.budget_view(repos)
        schema = info["schema_version"]
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
        markets_line.setText(
            f"{len(present)} из {len(MARKET_CODES)} рынков")

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
        _repaint_table(table, info)
        _repaint_measures(measure_box, info)
        apply_chart()
        _repaint_industry()
        source_panel.setText("клик по ячейке — панель источника")
        collect_button.setEnabled(state["worker"] is None)
        remove_button.setEnabled(True)
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

    def on_cell_clicked(row: int, _column: int) -> None:
        info = state["table"]
        if info is None or repos is None:
            return
        measure_row = info["measures"][row]
        panel = tui_model.source_panel(repos, measure_row["measure"])
        lines = [f"источник {panel['concept']}"
                 f" ({panel['method_version']})"]
        if measure_row["null_reason"]:
            lines.append(f"причина: {measure_row['null_reason']}")
        for source in panel["sources"]:
            document = str(source["document"])[:40]
            locator = source["locator"]
            kind = (locator.get("kind", "?")
                    if isinstance(locator, dict) else "?")
            lines.append(f"документ {document}… локатор {kind}")
        for stale in panel["stale"]:
            lines.append(f"{stale['marker']} ({stale['source_tag']})")
        source_panel.setText("\n".join(lines))

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
        if result.get("rejected"):
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

    # ── списки наблюдения (TASK-C5) ────────────────────────────────
    def reload_companies() -> None:
        state["companies"] = data.sidebar_companies(repos,
                                                    state["watchlist"])
        repaint_sidebar(search.text())

    def repaint_watchlist_line() -> None:
        overview = desktop_actions.watchlists_overview(repos)
        current = next((o for o in overview
                        if o["watchlist_id"] == state["watchlist"]), None)
        if current is None:
            watchlist_line.setText("списков наблюдения нет: "
                                   "создайте rusterm watchlist create")
            return
        watchlist_line.setText(
            f"версия {current['version']}"
            f" · участников {current['member_count']}")

    def repaint_version_box() -> None:
        version_box.blockSignals(True)
        version_box.clear()
        versions = desktop_actions.watchlist_versions(
            repos, state["watchlist"])
        for v in versions:
            version_box.addItem(f"v{v['version']} ({v['action']})",
                                userData=v["version"])
        version_box.blockSignals(False)
        rollback_button.setEnabled(version_box.count() > 1)

    def on_watchlist_switch(_index: int) -> None:
        state["watchlist"] = watchlist_box.currentData()
        state["selected"] = None
        state["table"] = None
        reload_companies()
        repaint_watchlist_line()
        repaint_version_box()

    def on_add() -> None:
        ticker = add_ticker.text().strip()
        market = add_market.text().strip().upper()
        if not ticker or not market or repos is None:
            return
        candidates = desktop_actions._resolve_ticker(repos, ticker,
                                                     market)
        if not candidates:
            watchlist_line.setText(
                f"тикер {ticker!r} на рынке {market} не найден")
            return
        if len(candidates) > 1:
            watchlist_line.setText(
                f"тикер {ticker!r} неоднозначен: "
                f"{', '.join(candidates)}")
            return
        version = desktop_actions.watchlist_add(repos,
                                                state["watchlist"],
                                                candidates[0])
        add_ticker.clear()
        add_market.clear()
        reload_companies()
        repaint_watchlist_line()
        repaint_version_box()
        watchlist_line.setText(f"{candidates[0]} добавлен,"
                               f" версия {version}")

    def on_remove() -> None:
        selected = state["selected"]
        if selected is None or repos is None:
            return
        version = desktop_actions.watchlist_remove(
            repos, state["watchlist"], selected["instrument_id"])
        state["selected"] = None
        reload_companies()
        repaint_watchlist_line()
        repaint_version_box()
        watchlist_line.setText(f"{selected['ticker']} удалён,"
                               f" версия {version}")

    def _confirm_bulk(text: str) -> bool:
        """Массовая операция требует подтверждения (C5.3) — тот же
        барьер, что подтверждение в CLI."""
        answer = QMessageBox.question(window, "подтверждение", text)
        return answer == QMessageBox.StandardButton.Yes

    def on_rollback() -> None:
        to_version = version_box.currentData()
        if to_version is None or repos is None:
            return
        if not _confirm_bulk(
                f"откатить список к версии {to_version}? "
                "будет создана новая версия с прежним составом"):
            return
        result = desktop_actions.watchlist_rollback(
            repos, state["watchlist"], to_version)
        reload_companies()
        repaint_watchlist_line()
        repaint_version_box()
        watchlist_line.setText(
            f"откат к версии {to_version}: создана версия "
            f"{result['version']}")

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
    watchlist_box.currentIndexChanged.connect(on_watchlist_switch)
    add_button.clicked.connect(on_add)
    remove_button.clicked.connect(on_remove)
    rollback_button.clicked.connect(on_rollback)
    tree.itemSelectionChanged.connect(on_tree_selection)
    kind_box.currentIndexChanged.connect(lambda _i: apply_chart())
    measure_box.currentIndexChanged.connect(lambda _i: apply_chart())
    industry_measure_box.currentIndexChanged.connect(
        lambda _i: apply_industry_chart())
    table.cellClicked.connect(on_cell_clicked)
    question_line.returnPressed.connect(on_ask)
    collect_button.clicked.connect(on_collect)
    cancel_button.clicked.connect(on_collect_cancel)

    # стартовое состояние
    if repos is None:
        message = data.empty_base_message(paths)
        company_header.setText(message)
        answer_label.setText(message)
        repaint_sidebar("")
    else:
        if state["watchlist"] is None:
            overview = desktop_actions.watchlists_overview(repos)
            if overview:
                state["watchlist"] = overview[0]["watchlist_id"]
        watchlist_box.blockSignals(True)
        for o in desktop_actions.watchlists_overview(repos):
            watchlist_box.addItem(f"{o['name']} (v{o['version']})",
                                  userData=o["watchlist_id"])
        if state["watchlist"] is not None:
            index = watchlist_box.findData(state["watchlist"])
            watchlist_box.setCurrentIndex(max(index, 0))
        watchlist_box.blockSignals(False)
        state["companies"] = data.sidebar_companies(repos,
                                                    state["watchlist"])
        if not state["companies"]:
            company_header.setText(data.empty_watchlist_message())
        repaint_sidebar("")
        repaint_watchlist_line()
        repaint_version_box()
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


def run(root, watchlist_id=None) -> int:
    """Точка входа python3 -m rusterm.desktop: только чтение."""
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
    window = _build_window(repos, paths, watchlist_id)
    window.resize(1280, 800)
    window.show()
    code = app.exec()
    if conn is not None:
        conn.close()
    return code
