"""TASK-C10.4: smoke-тест сборки — собранное .app стартует и
закрывается с кодом 0.

В ОБЫЧНОМ ПРОГОНЕ ТЕСТ ПРОПУСКАЕТСЯ: он живёт только при двух
условиях сразу — сборка dist/EquityLab.app существует и переменная
RUSTERM_APP_SMOKE=1 выставлена рукой запускающего (маркер прогона
сборки). Сеть на тест не тратится; каталог данных — tmp_path.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_BINARY = ROOT / "dist" / "EquityLab.app" / "Contents" / "MacOS" \
    / "EquityLab"

pytestmark = pytest.mark.skipif(
    not APP_BINARY.exists() or os.environ.get("RUSTERM_APP_SMOKE") != "1",
    reason="smoke сборки: нужен собранный dist/EquityLab.app и "
           "RUSTERM_APP_SMOKE=1 (маркер прогона сборки); в обычном "
           "прогоне пропускается")


def test_built_app_starts_and_exits_zero(tmp_path):
    empty_root = tmp_path / "data"
    empty_root.mkdir()
    result = subprocess.run(
        [str(APP_BINARY), "--root", str(empty_root)],
        env=dict(os.environ, RUSTERM_APP_SMOKE="1",
                 QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-800:]
    # каталога не было — окно сказало словами и ничего не создало
    assert not (empty_root / "rusterm.db").exists()


def test_built_app_finds_the_catalog_from_the_environment(tmp_path):
    """ТЗ-81 B3: запуск двойным щелчком — аргументов нет; каталог данных
    обязан найтись из окружения (тот же канал, что у ключей), иначе
    собранное окно молча читает не ту базу."""
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    result = subprocess.run(
        [str(APP_BINARY)],
        env=dict(os.environ, RUSTERM_APP_SMOKE="1",
                 QT_QPA_PLATFORM="offscreen",
                 RUSTERM_DATA=str(catalog),
                 # чужой env-файл машины не должен решать за тест
                 RUSTERM_ENV_FILE=str(tmp_path / "absent.env")),
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-800:]
    assert f"root={catalog}" in result.stdout, result.stdout[-400:]
    assert not (catalog / "rusterm.db").exists()


def test_built_app_reads_the_catalog_from_the_env_file(tmp_path):
    """ТЗ-81 B3: двойной щелчок — это ещё и отсутствие шелла: переменную
    пользователь записывает в файл, и собранный бинарник обязан его
    прочесть сам (тот же канал, что у ключей)."""
    catalog = tmp_path / "from-file"
    catalog.mkdir()
    env_file = tmp_path / "rusterm.env"
    env_file.write_text(f"RUSTERM_DATA={catalog}\n", encoding="utf-8")
    env_file.chmod(0o600)
    env = dict(os.environ, RUSTERM_APP_SMOKE="1",
               QT_QPA_PLATFORM="offscreen")
    env.pop("RUSTERM_DATA", None)
    result = subprocess.run(
        [str(APP_BINARY)],
        env=dict(env, RUSTERM_ENV_FILE=str(env_file)),
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-800:]
    assert f"root={catalog}" in result.stdout, result.stdout[-400:]


def test_qt_is_linked_dynamically_not_embedded():
    """ТЗ-81 B3 / ADR-0004 §6: LGPL требует, чтобы Qt можно было заменить,
    — это так только если библиотеки лежат отдельными Mach-O файлами с
    `@rpath`-идентичностями. Проверка идёт по файлам фреймворков: у главного
    бинарника `otool -L … | grep Qt` пуст (окно к Qt не прилинковано, PySide6
    грузится в рантайме), и отсутствие там Qt — не признак статической
    линковки."""
    frameworks = APP_BINARY.parents[1] / "Frameworks"
    qt = sorted(p.name for p in frameworks.iterdir()
                if p.name.startswith("Qt"))
    assert len(qt) >= 3, f"отдельных Qt-библиотек в сборке нет: {qt}"
    for name in qt:
        out = subprocess.run(["otool", "-D", str(frameworks / name)],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-300:]
        identity = out.stdout.strip().splitlines()[-1]
        assert identity == f"@rpath/{name}", (name, identity)
    abi3 = frameworks / "PySide6" / "QtCore.abi3.so"
    refs = subprocess.run(["otool", "-L", str(abi3)],
                          capture_output=True, text=True).stdout
    assert "@rpath/QtCore" in refs, \
        "модуль PySide6 не ссылается на отдельную библиотеку Qt"
