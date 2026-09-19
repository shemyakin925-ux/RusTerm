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
    from PySide6.QtWidgets import (QApplication, QComboBox, QGroupBox,
                                   QHBoxLayout, QHeaderView, QLabel,
                                   QLineEdit, QMainWindow, QSplitter,
                                   QTableWidget, QTableWidgetItem,
                                   QTreeWidget, QTreeWidgetItem,
                                   QVBoxLayout, QWidget)
    QT_AVAILABLE = True
except ImportError:  # приёмка №1: ядро и тесты живут без PySide6
    QT_AVAILABLE = False

from rusterm.desktop import data
from rusterm.markets import MARKET_CODES
from rusterm.tui import model as tui_model

if QT_AVAILABLE:  # без PySide6 имя не существует, окно честно откажет
    from rusterm.desktop.charts import ChartArea

WINDOW_TITLE = "EquityLab"
# ответ модели прижат влево и не шире ~3/4 окна (макет, C1.4)
ANSWER_MAX_WIDTH = 960


def _build_window(repos, paths, watchlist_id=None):
    """Собрать окно поверх открытого (возможно пустого) каталога."""
    window = QMainWindow()
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

    # ── левая колонка: поиск и дерево отраслей (C1.1) ──────────────
    left = QGroupBox()
    left_layout = QVBoxLayout(left)
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

    # ── центр: карточка, диаграмма, таблица (C1.2/C1.3) ────────────
    center = QWidget()
    center_layout = QVBoxLayout(center)
    company_header = QLabel(objectName="company_header")
    center_layout.addWidget(company_header)
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
    body.addWidget(center)
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
             "industry": None, "pinned": set(), "session": None,
             "chat_reason": None}

    # ── жизнь окна ─────────────────────────────────────────────────
    def repaint_header() -> None:
        if repos is None:
            status.setText("")
            return
        info = data.header_info(repos)
        schema = info["schema_version"]
        status.setText(f"схема {schema if schema is not None else '—'}"
                       f" · запросов сегодня {info['requests_today']}")

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
        _repaint_table(table, info)
        _repaint_measures(measure_box, info)
        apply_chart()
        source_panel.setText("клик по ячейке — панель источника")

    def apply_chart() -> None:
        if state["table"] is None:
            return
        kind = kind_box.currentData() or "line"
        spec = data.chart_spec(kind, state["table"], state["industry"],
                               measure_box.currentData())
        chart_area.set_spec(spec)

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

    # соединения
    search.textChanged.connect(on_search)
    tree.itemExpanded.connect(on_item_expanded)
    tree.itemCollapsed.connect(on_item_collapsed)
    tree.itemSelectionChanged.connect(on_tree_selection)
    kind_box.currentIndexChanged.connect(lambda _i: apply_chart())
    measure_box.currentIndexChanged.connect(lambda _i: apply_chart())
    table.cellClicked.connect(on_cell_clicked)
    question_line.returnPressed.connect(on_ask)

    # стартовое состояние
    if repos is None:
        message = data.empty_base_message(paths)
        company_header.setText(message)
        answer_label.setText(message)
        repaint_sidebar("")
    else:
        state["companies"] = data.sidebar_companies(repos, watchlist_id)
        if not state["companies"]:
            company_header.setText(data.empty_watchlist_message())
        repaint_sidebar("")
    repaint_header()
    setup_chat()
    if state["chat_reason"]:
        question_line.setPlaceholderText(
            f"модель недоступна: {state['chat_reason']}")
    return window


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
