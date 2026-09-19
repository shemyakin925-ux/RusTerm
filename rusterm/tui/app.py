"""Отрисовка TUI на curses (TASK-8 U11).

curses только красит строки, собранные rusterm.tui.model. Клавиши:
↑/↓ — перемещение, Enter — карточка, s — панель источника, r —
перечитать базу, Esc — назад, q — выход. Изменений состояния нет:
экран только читает базу через репозитории.
"""
from __future__ import annotations

import curses

from rusterm.tui import model

ESC_KEY = 27


def _put(stdscr, row: int, col: int, text: str, attr=None) -> None:
    """Написать строку, не выходя за края окна.

    Дефект, ради которого это заведено (находка координатора
    17.09.2026): карточка инструмента — 44 строки, а обычный терминал
    80x24; `addstr` за краем окна поднимает `_curses.error: addwstr()
    returned ERR`, и она уносила всю программу с кодом 2. Экран,
    который не помещается, обязан обрезаться и прокручиваться.
    """
    height, width = stdscr.getmaxyx()
    if row < 0 or row >= height or col < 0 or col >= width:
        return
    clipped = text[:width - col]
    # Последняя клетка последней строки: curses в неё писать не умеет.
    if row == height - 1 and col + len(clipped) >= width:
        clipped = clipped[:width - col - 1]
    if not clipped:
        return
    stdscr.addstr(row, col, clipped,
                  curses.A_NORMAL if attr is None else attr)


def _viewport(lines: list[str], top: int, room: int) -> tuple[list[str], int]:
    """Кусок списка, влезающий в room строк, и выправленное смещение."""
    if room <= 0 or not lines:
        return [], 0
    top = max(0, min(top, max(len(lines) - room, 0)))
    return lines[top:top + room], top


def _scroll_hint(lines: list[str], top: int, room: int) -> str:
    """Честная подпись «видно столько-то из стольких-то»."""
    if room <= 0 or len(lines) <= room:
        return ""
    last = min(top + room, len(lines))
    return f"  [строки {top + 1}-{last} из {len(lines)}; ↑↓ — прокрутка]"


def _list_screen(stdscr, repos, watchlist_id):
    cursor = 0
    top = 0
    while True:
        rows = model.list_rows(repos, watchlist_id)
        lines = model.render_list(rows)
        stdscr.clear()
        room = max(stdscr.getmaxyx()[0] - 2, 0)
        # курсор всегда в окне: список длиннее экрана — обычное дело
        if cursor < top:
            top = cursor
        elif room and cursor >= top + room:
            top = cursor - room + 1
        visible, top = _viewport(lines, top, room)
        _put(stdscr, 0, 0, "Список (↑↓ — выбор, Enter — карточка, "
                           "r — обновить, q — выход)"
                           + _scroll_hint(lines, top, room))
        for i, line in enumerate(visible):
            _put(stdscr, i + 2, 0, line,
                 curses.A_REVERSE if top + i == cursor else curses.A_NORMAL)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return None
        if key == curses.KEY_DOWN:
            cursor = min(cursor + 1, max(len(rows) - 1, 0))
        elif key == curses.KEY_UP:
            cursor = max(cursor - 1, 0)
        elif key in (curses.KEY_ENTER, 10, 13) and rows:
            return rows[cursor]["instrument_id"]
        elif key == ord("o") and rows:
            # ТЗ-22 J7: третий экран — отрасль выбранного инструмента
            peer = repos.peer_set.peer_set_for_instrument(
                rows[cursor]["instrument_id"])
            if peer:
                _industry_screen(stdscr, repos, peer["peer_set_id"])
        elif key == ord("c"):
            # ТЗ-42 I3/I4, ТЗ-46 N2: разговор — клиент строится одной
            # дверью ВНУТРИ экрана; вторым разом не передаётся
            _chat_screen(stdscr, repos, None)
        # r и прочие клавиши — просто перерисовать из базы заново


def _card_screen(stdscr, repos, instrument_id):
    show_sources = False
    highlighted = 0
    top = 0
    while True:
        card = model.card_rows(repos, instrument_id)
        lines = model.render_card(card)
        stdscr.clear()
        height = stdscr.getmaxyx()[0]
        panel_lines: list[str] = []
        if show_sources and card["measures"]:
            measure = card["measures"][highlighted % len(card["measures"])]
            panel = model.source_panel(repos, measure)
            panel_lines.append(f"Источник {panel['concept']} "
                               f"({panel['method_version']}):")
            for source in panel["sources"]:
                panel_lines.append(
                    f"  документ {source['document'][:16]}… "
                    f"локатор {source['locator'].get('kind', '?')}")
        # панель источника занимает низ окна, карточка — то, что выше
        room = max(height - 2 - (len(panel_lines) + 1 if panel_lines else 0), 0)
        visible, top = _viewport(lines, top, room)
        _put(stdscr, 0, 0, "Карточка (Esc — назад, s — источник "
                           "выделенной меры, q — выход)"
                           + _scroll_hint(lines, top, room))
        for i, line in enumerate(visible):
            _put(stdscr, i + 2, 0, line)
        for j, line in enumerate(panel_lines):
            _put(stdscr, height - len(panel_lines) - 1 + j, 0, line)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key == ESC_KEY:
            return None
        if key == ord("s"):
            show_sources = not show_sources
        if key == curses.KEY_DOWN:
            highlighted += 1
            top += 1
        elif key == curses.KEY_UP:
            highlighted = max(highlighted - 1, 0)
            top = max(top - 1, 0)
        elif key == curses.KEY_NPAGE:
            top += max(room - 1, 1)
        elif key == curses.KEY_PPAGE:
            top = max(top - max(room - 1, 1), 0)


def _industry_screen(stdscr, repos, sector):
    top = 0
    while True:
        screen = model.industry_rows(repos, sector)
        lines = model.render_industry(screen)
        stdscr.clear()
        room = max(stdscr.getmaxyx()[0] - 2, 0)
        visible, top = _viewport(lines, top, room)
        _put(stdscr, 0, 0, "Отрасль (Esc — назад, q — выход)"
                           + _scroll_hint(lines, top, room))
        for i, line in enumerate(visible):
            _put(stdscr, i + 2, 0, line)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key == ESC_KEY:
            return None
        if key == curses.KEY_DOWN:
            top += 1
        elif key == curses.KEY_UP:
            top = max(top - 1, 0)


def _chat_screen(stdscr, repos, session_id: str | None):
    """Экран «Разговор» (ТЗ-42 I3, Q10): вопрос -> ответ через ТОТ ЖЕ
    ChatSession, что и CLI. Клиент строится единственной дверью
    make_chat_client — той же, что у команды `rusterm chat`, и умеющей
    ровно то, что зовёт ChatSession.ask (находка координатора
    17.09.2026: прежняя дверь отдавала клиента без метода chat, и
    первый же вопрос ронял программу).

    Вопрос, Enter — отправить, ESC — выход. Отказ модели показывается
    строкой, а не падением."""
    import curses

    from rusterm.core.chat import ChatSession
    from rusterm.core.llm import make_chat_client

    session = ChatSession(repos, make_chat_client())
    rows: list[tuple[str, str | None, list, str | None]] = []
    question = ""

    def repaint() -> None:
        stdscr.erase()
        _put(stdscr, 0, 0,
             "Разговор (вопрос, Enter — отправить, ESC — выход):")
        lines: list[str] = []
        for asked, answer, citations, refusal in rows:
            lines.append(f"вы: {asked}")
            if answer:
                lines.append(f"  модель: {answer}")
            if refusal:
                lines.append(f"  отказ: {refusal}")
            for citation in citations:
                lines.append(f"    цитата: {citation}")
        room = max(stdscr.getmaxyx()[0] - 4, 0)
        visible, _top = _viewport(lines, max(len(lines) - room, 0), room)
        for i, line in enumerate(visible):
            _put(stdscr, i + 1, 0, line)
        bottom = stdscr.getmaxyx()[0]
        _put(stdscr, bottom - 2, 0, f"вызовов: {session.calls_made}")
        _put(stdscr, bottom - 1, 0, f"> {question}")
        stdscr.refresh()

    repaint()
    while True:
        key = stdscr.getch()
        if key == ESC_KEY:
            return None
        if key in (curses.KEY_ENTER, 10, 13):
            if question.strip():
                result = session.ask(question)
                rows.append((question, result.get("answer"),
                             list(result.get("citations") or []),
                             result.get("reason")
                             if result.get("rejected") else None))
            question = ""
            repaint()
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            question = question[:-1]
            repaint()
        elif 32 <= key < 127 or key > 127:
            question += chr(key)
            repaint()


def run(root: str, watchlist_id: str | None = None) -> int:
    from rusterm.store.db import apply_migrations, open_connection
    from rusterm.store.paths import AppPaths
    from rusterm.store.repos import RepoRegistry

    paths = AppPaths.from_root(root)
    # ТЗ-58 C3 (расхождение A3): экран задокументирован «только
    # чтение» — отсутствующий каталог данных называется по имени, а
    # не создаётся молча
    if not paths.db_path.exists():
        print(f"каталога данных нет: {root}; выполните rusterm init")
        return 1
    conn = open_connection(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    def loop(stdscr):
        selection = None
        while True:
            if selection is None:
                selection = _list_screen(stdscr, repos, watchlist_id)
                if selection is None:
                    return 0
            else:
                outcome = _card_screen(stdscr, repos, selection)
                if outcome == "quit":
                    return 0
                selection = None

    try:
        return curses.wrapper(loop)
    finally:
        conn.close()
