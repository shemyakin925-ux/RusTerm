"""Правила изоляции HOME для прогона набора (ТЗ-97 Q11, дверь P7).

Модуль-помощник, как `tests/i5_guard_residue.py`: pytest здесь не
импортируется — фикстура в `conftest.py` только вызывает эти функции, а
тесты проверяют само правило, не копию решения.

Зачем это нужно: с круга 135 каталог данных по умолчанию (ступень 4) —
`~/EquityLab/data`, то есть рабочая база пользователя. Тест, который
выбрал путь по умолчанию и не подменён, писал бы туда.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Что имеет право остаться в подменённом HOME после прогона всего набора.
# `EquityLab` — каталог, который создаёт само приложение по правилу 4.
# Замер полного прогона (REPORT-97, Run Q11-2): в песочном HOME не
# появилось ничего — ни каталога данных (каждый тест правила 4 подменяет
# HOME сам), ни следов Qt или CLI. Поэтому список не расширен заранее:
# всё, чего здесь нет, роняет прогон на teardown сессии.
HOME_ALLOWED = frozenset({"EquityLab"})


def live_run_selected(markexpr: str) -> bool:
    """Зовёт ли селектор маркеров живые тесты. Обычный прогон — пустой
    селектор и дефолтный `not live` (addopts): в нём подмена HOME
    обязательна. `live`, `live and not slow` — живой прогон: ему нужен
    настоящий `~/.rusterm.env` с ключами пользователя."""
    expr = " ".join((markexpr or "").lower().split())
    if not expr or expr == "not live":
        return False
    if re.search(r"\bnot\s+live\b", expr):
        return False
    return bool(re.search(r"\blive\b", expr))


def extra_entries(home: Path) -> list[str]:
    """Что лежит в HOME сверх закрытого списка. Немигающая проверка:
    каталог отсутствует — пусто, недоступен — имя самого сбоя."""
    try:
        names = sorted(p.name for p in home.iterdir())
    except OSError as exc:
        return [f"<OSError {exc}>"]
    return [name for name in names if name not in HOME_ALLOWED]


def child_import_paths(real_home: str) -> list[str]:
    """Записи `sys.path` этого процесса, лежащие под настоящим HOME.

    Нужны потому, что подмена HOME ломает дочерние процессы: путь
    пользовательских пакетов интерпретатор считает один раз при старте,
    а `python3 -m pytest` с новым HOME находит по нему пустой каталог и
    падает на `ModuleNotFoundError: pygments` ещё до импорта pytest — об
    этом прямо написано в докстринге
    tests/test_task99_j1_hand_stamps_state.py («HOME здесь НАМЕРЕННО не
    подменяется»). Отдаём детям ровно те пути, с которых живёт этот
    процесс, и ничего сверх них: в вenv под HOME ничего не лежит, и
    список пуст — чужие каталоги в PYTHONPATH не лезут."""
    if not real_home:
        return []
    base = Path(real_home).resolve()
    out = []
    for entry in sys.path:
        if not entry:
            continue
        path = Path(entry)
        try:
            if path.is_relative_to(base) and path.is_dir():
                out.append(str(path))
        except OSError:  # путь не читается — не отдаём дальше
            continue
    return out
