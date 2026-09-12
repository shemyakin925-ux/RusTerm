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
