# -*- mode: python ; coding: utf-8 -*-
# EquityLab.app — сборка десктопного окна PyInstaller (ТЗ-81 B3).
#
# Одна команда, из корня клона:
#
#     python3 -m PyInstaller EquityLab.spec --noconfirm
#
# На выходе — dist/EquityLab.app, который открывается двойным щелчком.
# Эквивалент ключа `--windowed` в этом спеке назван явно: `console=False`
# в EXE ниже. Именно его отсутствие заставляло рядом с окном жить окно
# терминала (жалоба пользователя, круг 109).
#
# Почему spec лежит в репозитории: TASK-C10 собрал .app однажды и спрятал
# spec в .gitignore — из клона он не собирался никогда. Строка, которая его
# прятала, снята; build/ и dist/ игнорируемыми остались, иначе мусор сборки
# красил бы приёмку неотслеживаемыми файлами (проверка 13).
#
# Линковка Qt остаётся ДИНАМИЧЕСКОЙ (ADR-0004 §6, LGPL): PyInstaller
# переносит библиотеки PySide6 отдельными dylib в Contents/Frameworks с
# @rpath-идентичностями, ничего не встраивая статически и не сжимая бинари
# (upx=False — сжатый бинарь нельзя ни перелинковать, ни подписать).
# Проверяется так:
#
#     otool -L dist/EquityLab.app/Contents/MacOS/EquityLab | grep -c Qt
#
# nonfat-аргументы Analysis'у не передаются; rusterm берётся из ЭТОГО клона
# (pathex=SPECPATH), потому что на машине разработчика пакет ещё и
# установлен как editable из другой директории — молча собрать не тот код
# было бы худшим исходом для сборки, которая «воспроизводится».

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Точка входа — обычный импортируемый модуль (TASK-C10): внутри бандла
# `python3 -m rusterm.desktop` не работает.
entry = os.path.join(SPECPATH, "rusterm", "desktop", "app_entry.py")

# Реестр провайдеров и doctor грузят модули по имени через importlib
# (rusterm/providers/__init__.py::_seat_provider, rusterm/store/doctor.py) —
# статический анализ их не видит.
provider_modules = [
    "rusterm.providers.asx",
    "rusterm.providers.cvm",
    "rusterm.providers.dart",
    "rusterm.providers.edgar",
    "rusterm.providers.llm_api",
    "rusterm.providers.otcmarkets",
    "rusterm.providers.twelvedata",
]

hiddenimports = (provider_modules
                 + collect_submodules("rusterm")
                 + collect_submodules("pyqtgraph"))

a = Analysis(
    [entry],
    pathex=[SPECPATH],
    binaries=[],
    datas=collect_data_files("pyqtgraph"),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # tkinter и тесты в приложение не едут: окно — Qt, а tests/ тянет за
    # собой pytest и сеть по импорту фикстур. torch/setuptools-копию
    # приложение не использует; без явного excludes анализ утаскивает в
    # бандл многотагонные тулчейны машины (замерено на этой же машине:
    # сборка без excludes доходит до hook-torch и собирает torch целиком).
    excludes=["tkinter", "tests", "pytest", "torch", "setuptools",
              "pkg_resources", "wheel", "IPython", "matplotlib",
              "scipy", "pandas"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# onedir, не onefile: в onefile Qt-библиотеки прячутся в архив внутри
# бинаря и разворачиваются во временный каталог на каждый запуск, и тогда
# требование ADR-0004 §6 («динамическая линковка Qt видна в бандле»)
# нечем не проверяемо, ни проверяемо. Onedir кладёт их в
# Contents/Frameworks отдельными dylib с @rpath — их видно `otool -L`.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EquityLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # ← эквивалент --windowed: терминала рядом нет
    disable_stderr_logging=False,
    team_explicit_id=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EquityLab",
)

app = BUNDLE(
    coll,
    name="EquityLab.app",
    icon=None,
    bundle_identifier=None,
)
