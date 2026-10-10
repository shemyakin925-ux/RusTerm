"""ТЗ-105 R2: сборка `.app` держит свой кэш вне подменённого HOME.

Было (дефект, решение координатора — ТЗ-105, пункт 19 таблицы решений
против item-а REPORT-103 про `Library` в песочном HOME): `_build_app`
звал `python3 -m PyInstaller` с окружением прогона. На macOS PyInstaller
берёт кэш из `PYINSTALLER_CONFIG_DIR`, а без неё — из
`expanduser('~/Library/Application Support')`
(`PyInstaller/configure.py:55-62`). HOME на прогоне набора подменён
песочницей (дверь P7, ТЗ-97 Q11), поэтому первая же сборка оставляла в
песочном HOME каталог `Library`, а `extra_entries` считал его мусором:
`firsthour` внутри защищённого прогона был красен не из-за окна, а из-за
собственного кэша.

Стало: адрес кэша уезжает в рабочую папку теста (`_build_env`),
`HOME_ALLOWED` не расширяется — в нём по-прежнему только `EquityLab`, и
это отдельный пункт ТЗ: «`HOME_ALLOWED` unchanged».

| зуб | было | стало |
|---|---|---|
| окружение сборки | наследовалось целиком | плюс `PYINSTALLER_CONFIG_DIR` под `work` |
| `_get_pyinstaller_cache_dir()` с таким окружением | `…/<HOME>/Library/Application Support/pyinstaller` | `…/work/pyinstaller-config/pyinstaller`, вне HOME |
| песочный HOME после сборки | `Library` сверх списка | `HOME_ALLOWED` остаётся закрытым, и `extra_entries` по-прежнему ловит `Library` |
| остальное окружение | — | то же: `PATH` и `HOME` не переписаны, дочерние процессы не ломаются |

Зубы дешёвые и в обычном наборе: `subprocess.run` подменён, настоящая
сборка здесь не запускается (её делает сам `firsthour`).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests import test_desktop_f2_double_click as f2
from tests.p7_home_isolation import HOME_ALLOWED, extra_entries


@pytest.fixture
def captured(monkeypatch, tmp_path):
    """Запись вызова сборки без настоящей сборки: `subprocess.run`
    подменён, каталог dist создаёт сам, потому что `_build_app`
    проверяет его наличие."""
    calls: list[dict] = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": list(argv), **kwargs})
        work = Path(argv[argv.index("--distpath") + 1])
        (work / "EquityLab.app" / "Contents" / "MacOS").mkdir(parents=True)

        class Done:
            returncode = 0
            stdout = "built"
            stderr = ""
        return Done()

    monkeypatch.setattr(f2.subprocess, "run", fake_run)
    return calls


def _cache_dir_of_the_build(calls) -> Path:
    env = calls[0]["env"]
    return Path(env["PYINSTALLER_CONFIG_DIR"])


def test_the_build_subprocess_is_told_where_to_put_its_config(captured,
                                                              tmp_path):
    """Done-when часть 1: сборка получает адрес кэша, и он — в папке
    этого теста, а не в HOME."""
    work = tmp_path / "f2-build"
    f2._build_app(work)
    assert len(captured) == 1
    cfg = _cache_dir_of_the_build(captured)
    assert cfg == work / "pyinstaller-config"
    assert cfg.is_relative_to(tmp_path)


def test_pyinstaller_itself_chooses_that_directory(captured, monkeypatch,
                                                   tmp_path):
    """Не «мы записали переменную», а «сборка туда и пошла»: тот самый
    резолвер из PyInstaller, вызванный с окружением сборки, отдаёт путь
    вне HOME."""
    from PyInstaller import configure

    work = tmp_path / "f2-build"
    f2._build_app(work)
    cfg = _cache_dir_of_the_build(captured)
    home = Path(os.path.expanduser("~"))
    monkeypatch.setenv("PYINSTALLER_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    chosen = Path(configure._get_pyinstaller_cache_dir())
    assert chosen == cfg / "pyinstaller"
    assert not chosen.is_relative_to(home), (
        f"кэш сборки попал в HOME: {chosen}")


def test_without_the_variable_the_cache_would_land_in_home(monkeypatch,
                                                           tmp_path):
    """Краснота по-честному: то же самое без переменной. Зуб ловит не
    мою веру в PyInstaller, а его поведение на этой машине."""
    from PyInstaller import configure

    home = tmp_path / "home"
    monkeypatch.delenv("PYINSTALLER_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData"))
    chosen = Path(configure._get_pyinstaller_cache_dir())
    assert chosen.is_relative_to(home), (
        f"без переменной кэш уехал из HOME: {chosen}")
    assert "Library" in str(chosen) or "pyinstaller" in str(chosen)


def test_home_allowed_does_not_know_library(tmp_path):
    """`HOME_ALLOWED` не тронут (пункт ТЗ), и `Library` в нём по-прежнему
    мусор: значит лечиться надо адресом кэша, а не списком. Проверка на
    живом песочном HOME — прогон бы на нём и упал."""
    assert HOME_ALLOWED == frozenset({"EquityLab"})
    home = tmp_path / "home"
    (home / "Library" / "Application Support" / "pyinstaller").mkdir(
        parents=True)
    assert extra_entries(home) == ["Library"]
    (home / "EquityLab").mkdir()
    assert extra_entries(home) == ["Library"]


def test_the_rest_of_the_build_environment_is_untouched(captured,
                                                        tmp_path):
    """Сборка не должна лишиться `PATH` и не должна получать другой
    `HOME`: подмена HOME дочерним процессам уже ломала импорт
    (`p7_home_isolation.child_import_paths`)."""
    f2._build_app(tmp_path / "f2-build")
    env = captured[0]["env"]
    assert env["PATH"] == os.environ["PATH"]
    assert env.get("HOME") == os.environ.get("HOME")
    assert env.get("PYTHONPATH") == os.environ.get("PYTHONPATH")
    assert "--distpath" in captured[0]["argv"]
