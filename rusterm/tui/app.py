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


def _list_screen(stdscr, repos, watchlist_id):
    cursor = 0
    while True:
        rows = model.list_rows(repos, watchlist_id)
        lines = model.render_list(rows)
        stdscr.clear()
        stdscr.addstr(0, 0, "Список (↑↓ — выбор, Enter — карточка, "
                            "r — обновить, q — выход)")
        for i, line in enumerate(lines):
            stdscr.addstr(i + 2, 0, line,
                          curses.A_REVERSE if i == cursor else curses.A_NORMAL)
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
    while True:
        card = model.card_rows(repos, instrument_id)
        lines = model.render_card(card)
        stdscr.clear()
        stdscr.addstr(0, 0, "Карточка (Esc — назад, s — источник "
                            "выделенной меры, q — выход)")
        for i, line in enumerate(lines):
            stdscr.addstr(i + 2, 0, line)
        if show_sources and card["measures"]:
            measure = card["measures"][highlighted % len(card["measures"])]
            panel = model.source_panel(repos, measure)
            stdscr.addstr(len(lines) + 3, 0,
                          f"Источник {panel['concept']} "
                          f"({panel['method_version']}):")
            for j, source in enumerate(panel["sources"]):
                stdscr.addstr(len(lines) + 4 + j, 2,
                              f"документ {source['document'][:16]}… "
                              f"локатор {source['locator'].get('kind', '?')}")
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


def _industry_screen(stdscr, repos, sector):
    while True:
        screen = model.industry_rows(repos, sector)
        lines = model.render_industry(screen)
        stdscr.clear()
        stdscr.addstr(0, 0, "Отрасль (Esc — назад, q — выход)")
        for i, line in enumerate(lines):
            stdscr.addstr(i + 2, 0, line)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key == ESC_KEY:
            return None


def _chat_screen(stdscr, repos, session_id: str | None):
    """Экран «Разговор» (ТЗ-42 I3, Q10): вопрос -> ответ через ТОТ ЖЕ
    ChatSession, что и CLI. Клиент строится единственной дверью
    make_intent_client (ТЗ-42 I4) — экран свой клиент не создаёт.
    Вопрос, Enter — отправить, ESC — выход."""
    import curses

    from rusterm.core.chat import ChatSession
    from rusterm.core.llm import make_intent_client

    client = make_intent_client()
    session = ChatSession(repos, client)
    rows = []
    stdscr.addstr(0, 0, "Разговор (вопрос, Enter — отправить, ESC — выход):")
    stdscr.addstr(1, 0, "> ")
    stdscr.refresh()
    question = ""
    while True:
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            if question.strip():
                result = session.ask(question)
                rows.append((question, result.get("answer"),
                             result.get("citations") or [],
                             session.calls_made))
            question = ""
            stdscr.erase()
            stdscr.addstr(0, 0, "Разговор (вопрос, Enter — отправить, ESC — выход):")
            for i, (q, a, cit, _calls) in enumerate(rows, start=1):
                stdscr.addstr(i, 0, f"вы: {q}")
                if a:
                    stdscr.addstr(i + 1, 2, f"модель: {a}")
                for j, citation in enumerate(cit):
                    stdscr.addstr(i + 2 + j, 4, f"цитата: {citation}")
            row = 1 + sum(3 for _ in rows)
            stdscr.addstr(row, 0,
                          f"вызовов: {session.calls_made}")
            stdscr.addstr(row + 1, 0, "> ")
            stdscr.refresh()
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            question = question[:-1]
        elif 32 <= key < 127 or key > 127:
            question += chr(key)
        if key == ESC_KEY:
            return None


def run(root: str, watchlist_id: str | None = None) -> int:
    from rusterm.store.db import apply_migrations, open_connection
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import RepoRegistry

    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
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
