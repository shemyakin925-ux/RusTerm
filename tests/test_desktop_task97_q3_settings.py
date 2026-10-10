"""ТЗ-97 Q3 (ТЗ-73 T4): вкладка «Настройки» — закреплена тестом.

Done-when пункта требует, чтобы тест держал то, что уже работает, и
назвал словами то, что работало только наполовину:

1. ключи показаны происхождением без значений — страж на утечку: в
   окружение кладутся sentinel-значения всех ENV_NAMES, и ни одно не
   обязано встретиться ни в одной надписи, таблице или дереве окна;
2. у каждого имени есть назначение, иначе строка «нет — …» пуста;
3. лимиты совпадают с реестром провайдеров (состав и числа), а колонка
   «правка» читается из двери конфигурации, а не из воздуха;
4. каталог называет размер и дату; каталога нет — причина словом и
   команда, которой она закрывается (правило P8);
5. кнопка «сменить каталог данных» проверена нажатием (ТЗ-72 S1) в обеих
   ветках: пустого каталога окно спрашивает, битый — не спрашивает, а
   отказывает словами и называет команду закрытия. Ветка отказа до этого
   пункта не существовала: `catalog_switch_decision` знал только
   «файл есть / файла нет», и каталог с мусором вместо базы открывался
   новым окном.
"""
from __future__ import annotations

import datetime
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rusterm import env as env_module
from rusterm.desktop import data as desktop_data
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

# Значения, которые не должны никуда утечь: форма умышленно не похожа
# ни на путь, ни на число, ни на имя провайдера.
SENTINELS = {name: f"СЕКРЕТ-{idx}-4f9a-ЗНАЧЕНИЕ"
             for idx, name in enumerate(env_module.ENV_NAMES)}

# Момент, который каталог обязан назвать в подписи (локальное время
# машины теста, та же размерность, что у `stat().st_mtime`).
PINNED_EPOCH = 1_759_000_000.0


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """Каталог с одной бумагой и окружением без чужих ключей."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-X", "X", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-X", "i-X", None, "common", "active", None))
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(tmp_path / "empty.env"))
    yield repos, paths, tmp_path
    conn.close()
    env_module._LAST_ORIGINS = None


def _window(repos, paths, watchlist_id=None):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from rusterm.desktop import window as desktop_window
    # offscreen-сборка живёт в процессе теста: без приложения Qt
    # бьёт фаталом в paintEngine, а не в assert
    QApplication.instance() or QApplication([])
    return desktop_window._build_window(repos, paths, watchlist_id)


def _label(window, name):
    from PySide6.QtWidgets import QLabel
    return window.findChild(QLabel, name)


def _settings_tab(window):
    from PySide6.QtWidgets import QTabWidget
    tabs = window.findChild(QTabWidget, "tabs")
    for i in range(tabs.count()):
        if tabs.tabText(i) == "Настройки":
            return tabs.widget(i)
    raise AssertionError("вкладки «Настройки» нет")


def _all_text(window) -> str:
    """Весь текст окна: надписи, поля, ячейки таблиц и дерева, заголовок.
    Страж на утечку ищет значение ключа здесь, а не только на вкладке."""
    from PySide6.QtWidgets import QLabel, QLineEdit, QTableWidget, QTreeWidget
    chunks = [window.windowTitle()]
    for label in window.findChildren(QLabel):
        chunks.append(label.text())
    for line in window.findChildren(QLineEdit):
        chunks.append(line.text())
        chunks.append(line.placeholderText())
    for table in window.findChildren(QTableWidget):
        for column in range(table.columnCount()):
            header = table.horizontalHeaderItem(column)
            chunks.append(header.text() if header else "")
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                chunks.append(item.text() if item else "")
    for tree in window.findChildren(QTreeWidget):
        stack = [tree.topLevelItem(i)
                 for i in range(tree.topLevelItemCount())]
        while stack:
            node = stack.pop()
            for column in range(tree.columnCount()):
                chunks.append(node.text(column))
            stack.extend(node.child(i)
                         for i in range(node.childCount()))
    return "\n".join(chunks)


# ── 1-2: ключи — имя, происхождение, назначение; никогда значение ────────

def test_panel_names_a_purpose_for_every_loaded_name():
    """Словарь назначений покрывает список загружаемых имён: строка
    «ключа нет» обязана говорить, что из-за этого недоступно."""
    missing = sorted(set(env_module.ENV_NAMES)
                     - set(desktop_data.KEY_PURPOSE))
    assert not missing, f"ключи без назначения в панели: {missing}"


def test_settings_tab_shows_origin_and_never_a_value(app_env, monkeypatch):
    for name, value in SENTINELS.items():
        monkeypatch.setenv(name, value)
    repos, paths, _ = app_env
    window = _window(repos, paths)
    try:
        text = _label(window, "keys_label").text()
        for name in env_module.ENV_NAMES:
            assert name in text, f"имя {name} не названо на вкладке"
        assert "найден, окружение" in text
        assert "—" not in text.splitlines()[0], (
            "строка ключей началась с прочерка вместо заголовка")
        every = _all_text(window)
        for name, value in SENTINELS.items():
            assert value not in every, (
                f"значение ключа {name} утекло в окно: {value}")
    finally:
        window.close()


def test_absent_key_is_named_with_what_it_blocks(app_env):
    """Ключа нет — ряд называет, что из-за этого недоступно (P8), а не
    оставляет читателя со словом «нет»."""
    repos, paths, _ = app_env
    monkey = os.environ  # conftest уже вычистил ENV_NAMES
    assert not any(monkey.get(n) for n in env_module.ENV_NAMES)
    window = _window(repos, paths)
    try:
        text = _label(window, "keys_label").text()
        assert "нет —" in text
        for row in desktop_data.keys_view()["rows"]:
            assert not row["found"]
            assert row["purpose"], f"{row['name']}: отсутствие без причины"
            assert row["purpose"] in text, (
                f"назначение {row['name']} не доехало до вкладки")
    finally:
        window.close()


# ── 3: лимиты = реестр провайдеров, правка = дверь конфигурации ──────────

def test_limits_table_equals_the_provider_registry(app_env):
    from PySide6.QtWidgets import QTableWidget
    from rusterm.providers import all_host_limits
    repos, paths, _ = app_env
    window = _window(repos, paths)
    try:
        table = window.findChild(QTableWidget, "limits_table")
        registry = all_host_limits()
        assert table.rowCount() == len(registry), (
            f"таблица называет {table.rowCount()} хостов, реестр — "
            f"{len(registry)}")
        shown = {}
        for row in range(table.rowCount()):
            cells = [table.item(row, column).text()
                     for column in range(table.columnCount())]
            shown[cells[0]] = cells
        assert set(shown) == {limit.host for limit in registry.values()}, (
            "состав хостов разошёлся с реестром")
        for limit in registry.values():
            cells = shown[limit.host]
            assert cells[1] == str(limit.nightly_max)
            assert cells[2] == str(limit.per_second)
            assert cells[3] == "—", "без правки в конфиге — прочерк"
    finally:
        window.close()


def test_override_column_reads_the_configuration_door(app_env):
    """Колонка «правка» — не украшение: оверрайд, записанный дверью
    `set_provider_rate_limit`, должен быть в ней виден."""
    from PySide6.QtWidgets import QTableWidget
    from rusterm.providers import all_host_limits
    repos, paths, _ = app_env
    host = all_host_limits()["llm-api"].host
    outcome = desktop_data.set_host_rate_limit(paths, host, 0.5)
    assert outcome["ok"] is True, outcome
    window = _window(repos, paths)
    try:
        table = window.findChild(QTableWidget, "limits_table")
        rows = {table.item(row, 0).text(): table.item(row, 3).text()
                for row in range(table.rowCount())}
        assert rows[host] == "0.5/сек", rows
    finally:
        window.close()


# ── 4: каталог называет размер и дату; без базы — причина и дверь ────────

def test_catalog_label_names_size_and_date(app_env):
    """Размер и дата каталога — названные, а не намалёванные: момент
    закрепляется `os.utime`, затем вкладка перерисовывается выбором
    бумаги (ТЗ-72 S1 — нажатием), и подпись обязана вернуть ровно эти
    два числа."""
    from PySide6.QtWidgets import QTreeWidget
    repos, paths, _ = app_env
    window = _window(repos, paths)
    try:
        tree = window.findChild(QTreeWidget, "tree")
        node = tree.topLevelItem(0).child(0)
        assert node is not None, "в дереве нет ни одной бумаги"
        os.utime(paths.db_path, (PINNED_EPOCH, PINNED_EPOCH))
        tree.setCurrentItem(node)
        text = _label(window, "catalog_label").text()
        expected = datetime.datetime.fromtimestamp(
            PINNED_EPOCH).isoformat(timespec="seconds")
        assert str(paths.root) in text, text
        assert paths.db_path.name in text, text
        assert f"обновлялась {expected}" in text, (
            f"дата не закреплённый момент ({expected}): {text}")
        assert f"{paths.db_path.stat().st_size} байт" in text, text
    finally:
        window.close()


def test_missing_catalogue_is_a_reason_with_a_door(app_env, tmp_path):
    """База есть в одном каталоге, окно открыто над другим: подпись
    обязана назвать причину и команду, которой она закрывается."""
    repos, _, _ = app_env
    other = AppPaths.from_root(tmp_path / "empty-root")
    window = _window(repos, other)
    try:
        text = _label(window, "catalog_label").text()
        assert "базы нет" in text, text
        assert "rusterm init" in text, f"двери нет: {text}"
        assert other.db_path.name not in text or "базы нет" in text
    finally:
        window.close()


# ── 5: смена каталога нажатием — вопрос для пустого, отказ для битого ───

def test_switch_button_asks_before_creating(app_env, tmp_path):
    """Ветка «каталога нет»: окно спрашивает, отказа создать нет —
    ничего не создаётся (B35/B40)."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QMessageBox, QPushButton
    from rusterm.desktop import window as desktop_window
    repos, paths, _ = app_env
    window = _window(repos, paths)
    asked = {}
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            desktop_window.QFileDialog, "getExistingDirectory",
            staticmethod(lambda *a, **k: str(tmp_path / "nowhere")))
        monkeypatch.setattr(
            desktop_window.QMessageBox, "question",
            staticmethod(lambda *a, **k: asked.setdefault(
                "asked", QMessageBox.StandardButton.No)))
        window.findChild(QPushButton, "switch_root_button").click()
        assert asked.get("asked"), "молчаливого создания нет — спросили"
        assert not (tmp_path / "nowhere" / "rusterm.db").exists()
        assert "отменена" in _label(window, "status").text()
    finally:
        monkeypatch.undo()
        window.close()


def test_switch_button_refuses_a_broken_catalogue_in_words(app_env,
                                                          tmp_path):
    """Ветка «путь битый»: файл базы есть, но это не база. Спрашивать
    «создать?» здесь нельзя, и открывать окно над мусором нельзя —
    окно отказывает словами и называет команду закрытия."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QMessageBox, QPushButton
    from rusterm.desktop import window as desktop_window
    repos, paths, _ = app_env
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "rusterm.db").write_bytes("это не база данных"
                                        .encode("utf-8"))
    window = _window(repos, paths)
    asked = []
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            desktop_window.QFileDialog, "getExistingDirectory",
            staticmethod(lambda *a, **k: str(broken)))
        monkeypatch.setattr(
            desktop_window.QMessageBox, "question",
            staticmethod(lambda *a, **k: asked.append(a) or
                         QMessageBox.StandardButton.Yes))
        window.findChild(QPushButton, "switch_root_button").click()
        text = _label(window, "status").text()
        assert not asked, f"битый путь asked как пустой: {text}"
        assert "каталог не сменён" in text, text
        assert "не база данных" in text, f"отказ без слов о причине: {text}"
        assert f"rusterm --root {broken} init" in text, (
            f"отказ без команды закрытия: {text}")
        assert (broken / "rusterm.db").read_bytes(
        ) == "это не база данных".encode("utf-8"), "отказ тронул чужой файл"
    finally:
        monkeypatch.undo()
        window.close()


def test_the_refusal_returns_before_any_second_window_is_raised():
    """AST-зуб: ветка отказа стоит до запуска нового окна. Нажатием это
    проверять нельзя: на старом коде битый путь доходил до
    `raise SystemExit` внутри Qt-слота, и красный тест убивал весь
    прогон вместо того, чтобы отчитаться отказом словом."""
    import ast
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "rusterm" / "desktop" / "window.py")
                     .read_text(encoding="utf-8"))
    host = next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "on_switch_root")
    guards = [node for node in ast.walk(host)
              if isinstance(node, ast.If) and "usable" in ast.dump(node.test)]
    assert guards, "окно не различает битый каталог (`usable`)"
    refusal = guards[0]
    assert [node for node in ast.walk(refusal)
            if isinstance(node, ast.Return)], "ветка отказа не возвращается"
    assert not [node for node in ast.walk(refusal)
                if isinstance(node, ast.Raise)], (
        "ветка отказа поднимает SystemExit вместо слова")
    raises = [node for node in ast.walk(host) if isinstance(node, ast.Raise)]
    assert raises, "окно вообще не перезапускается"
    assert all(node.lineno > refusal.lineno for node in raises), (
        "отказ стоит после перезапуска — битый путь успеет открыть окно")


# ── слой данных: три формы пути, без Qt ────────────────────────────────

def test_decision_covers_the_three_shapes_of_a_path(tmp_path):
    missing = desktop_data.catalog_switch_decision(tmp_path / "none")
    assert missing == {"candidate_root": str(tmp_path / "none"),
                       "exists": False, "usable": False, "reason": None,
                       "closing": None}

    fresh = tmp_path / "fresh"
    (fresh / "rusterm.db").parent.mkdir()
    (fresh / "rusterm.db").write_bytes(b"")   # пустой файл = новая база
    ok = desktop_data.catalog_switch_decision(fresh)
    assert ok["exists"] is True and ok["usable"] is True, ok

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "rusterm.db").write_bytes(b"SQLite format 3 X" + b"\x00" * 8)
    bad = desktop_data.catalog_switch_decision(broken)
    assert bad["exists"] is True and bad["usable"] is False, bad
    assert "не база данных" in bad["reason"]
    assert bad["closing"] == f"rusterm --root {broken} init"


def test_a_real_database_is_usable(tmp_path):
    paths = AppPaths.from_root(tmp_path / "real")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    conn.close()
    decision = desktop_data.catalog_switch_decision(paths.root)
    assert decision["exists"] is True and decision["usable"] is True, \
        decision


def test_the_refusal_command_is_the_one_the_cli_accepts(tmp_path):
    """Отказ словом бесполезен, если названная команда не разбирается:
    та же проверка, что держит двери вкладок (ТЗ-97 Q1)."""
    from rusterm import cli
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "rusterm.db").write_bytes(b"not sqlite")
    decision = desktop_data.catalog_switch_decision(broken)
    argv = decision["closing"].split()[1:]
    parsed = cli._build_parser().parse_args(argv)
    assert parsed.command == "init"
    assert parsed.root == str(broken)
