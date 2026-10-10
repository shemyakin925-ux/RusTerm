"""Живой осмотр окна EquityLab: запускает настоящее окно на реальной базе
офскрин, щёлкает компании и вкладки, снимает PNG и выписывает всё, что
видно пользователю (баннеры, таблицы, «нет данных», ошибки в логе).

python3 .claude/skills/rusterm-check/look.py --root ~/EquityLab/data --out DIR [--companies 3]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# ТЗ-133 R1: осмотр не ходит в сеть и не пишет в базу — без автообновления
os.environ.setdefault("RUSTERM_NO_AUTO_REFRESH", "1")
# какой код смотреть: --code DIR (по умолчанию ~/EquityLab/app — то, что
# реально запускает пользователь), иначе корень этого репозитория
_code = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1])
              if a == "--code"), None)
_default = Path.home() / "EquityLab" / "app"
sys.path.insert(0, str(Path(_code).expanduser() if _code else
                       (_default if _default.exists()
                        else Path(__file__).resolve().parents[3])))

from PySide6.QtWidgets import (QApplication, QLabel, QTableWidget,  # noqa
                               QTabWidget, QTreeWidget, QComboBox)
from PySide6.QtCore import QThread, qInstallMessageHandler  # noqa

from rusterm import env as _env  # noqa
_env.load_env()
from rusterm.desktop import data, window  # noqa

QT_LOG: list[str] = []
qInstallMessageHandler(lambda mode, ctx, msg: QT_LOG.append(msg))


def pump(app, n=5):
    for _ in range(n):
        app.processEvents()


def visible_labels(win):
    # ТЗ-111 U1: панель источника — единственное место, где сырой токен
    # причины живёт по заданию; её текст в проверку шаблонов не ходит
    return [w.text() for w in win.findChildren(QLabel)
            if w.isVisible() and w.text().strip()
            and w.objectName() != "source_panel"]


def dump_tables(win):
    out = []
    for t in win.findChildren(QTableWidget):
        if not t.isVisible():
            continue
        head = [t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c)
                else "" for c in range(t.columnCount())]
        rows = []
        for r in range(t.rowCount()):
            rows.append([t.item(r, c).text() if t.item(r, c) else ""
                         for c in range(t.columnCount())])
        cells = [c for row in rows for c in row[1:]]
        empty = sum(1 for c in cells if c in ("", data.NO_DATA))
        # BACKLOG P3: «—» (честный отказ клетки) отдельно от пустых клеток
        # строк-разделов (вся строка пуста — это заголовок раздела)
        section = [row for row in rows if not any(c.strip() for c in row)]
        dash = sum(1 for row in rows for c in row if c == "—")
        out.append({"header": head, "rows": rows, "cells": len(cells),
                    "empty_or_no_data": empty, "dash": dash,
                    "section_blank": sum(len(row) for row in section)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/EquityLab/data"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--companies", type=int, default=3)
    ap.add_argument("--code", default=None,
                    help="каталог с кодом rusterm (по умолчанию ~/EquityLab/app)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"errors": [], "shots": []}
    app = QApplication.instance() or QApplication([])
    paths, conn = data.open_readonly(a.root)
    repos = None
    if conn is not None:
        from rusterm.store.repos import RepoRegistry
        repos = RepoRegistry(conn, paths)
    try:
        win = window._build_window(repos, paths, None)
    except Exception:
        report["errors"].append("build_window: " + traceback.format_exc())
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 1
    win.resize(1400, 900)
    win.show()
    pump(app, 20)
    report["start_labels"] = visible_labels(win)
    win.grab().save(str(out / "00-start.png"))
    report["shots"].append("00-start.png")

    tree = (win.findChildren(QTreeWidget) or [None])[0]
    leaves = []
    if tree is not None:
        def walk(item):
            if item.childCount() == 0:
                leaves.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))
        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
    report["tree_leaves"] = len(leaves)
    tabs = [t for t in win.findChildren(QTabWidget)]
    report["companies"] = []
    for k, leaf in enumerate(leaves[:a.companies]):
        entry = {"item": leaf.text(0), "tabs": []}
        try:
            tree.setCurrentItem(leaf)
            tree.itemClicked.emit(leaf, 0)
            pump(app, 20)
        except Exception:
            entry["error"] = traceback.format_exc()
        for tw in tabs:
            for ti in range(tw.count()):
                tw.setCurrentIndex(ti)
                pump(app, 10)
                name = f"{k+1:02d}-{ti}-{tw.tabText(ti)}.png".replace("/", "_")
                win.grab().save(str(out / name))
                report["shots"].append(name)
                entry["tabs"].append({"tab": tw.tabText(ti),
                                      "labels": visible_labels(win),
                                      "tables": dump_tables(win),
                                      "combos": [c.currentText() for c in
                                                 win.findChildren(QComboBox)
                                                 if c.isVisible()]})
            tw.setCurrentIndex(0)
        report["companies"].append(entry)
    report["qt_log"] = QT_LOG[-50:]
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False,
                                                indent=1))
    # ТЗ-110 B2: окно запускает фоновый проход при старте — выход без
    # закрытия окон ронял процесс (QThread destroyed while running,
    # exit 134). Закрыть окна и дождаться воркеров перед выходом.
    for w in list(QApplication.allWidgets()):
        try:
            w.close()
        except RuntimeError:
            pass  # C++-объект уже удалён — питонья обёртка пережила его
    deadline = __import__("time").time() + 10
    while __import__("time").time() < deadline:
        try:
            busy = [th for w in QApplication.allWidgets()
                    for th in w.findChildren(QThread) if th.isRunning()]
        except RuntimeError:
            break
        if not busy:
            break
        for th in busy:
            th.wait(100)
    import rusterm
    print(f"code: {Path(rusterm.__file__).parent.parent}")
    print(f"shots: {len(report['shots'])}  dir: {out}")
    print("start banner:", *report["start_labels"][:4], sep="\n  ")
    for c in report["companies"]:
        for t in c["tabs"]:
            for tb in t["tables"]:
                print(f"{c['item'][:30]:30} | {t['tab']:10} | rows "
                      f"{len(tb['rows'])} | empty {tb['empty_or_no_data']}/"
                      f"{tb['cells']} | — {tb['dash']}"
                      f" | section {tb['section_blank']}")
    if QT_LOG:
        print("qt log:", *QT_LOG[-10:], sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
