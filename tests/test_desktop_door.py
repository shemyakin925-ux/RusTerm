"""ТЗ-60 E3: дверь десктопа из CLI — rusterm desktop.

Обе точки входа (python3 -m rusterm.desktop и rusterm desktop) ведут
в один код rusterm.desktop.__main__.main; отказ без PySide6 словами
даёт window.run ещё в нём, поэтому у обеих дверей слова одинаковые.
Дверь сама каталог данных не создаёт (B35).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys  # noqa: E402

import pytest  # noqa: E402

from rusterm.cli import main as cli_main  # noqa: E402


@pytest.fixture()
def run_recorder(monkeypatch):
    from rusterm.desktop import window as desktop_window
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        desktop_window, "run",
        lambda root, watchlist_id=None:
        calls.append((root, watchlist_id)) or 0)
    return calls


def test_desktop_listed_in_cli_help(capsys):
    with pytest.raises(SystemExit) as exited:
        cli_main(["--help"])
    assert exited.value.code == 0
    assert "desktop" in capsys.readouterr().out


def test_both_doors_call_the_same_run(tmp_path, run_recorder):
    from rusterm.desktop.__main__ import main as desktop_main
    root = str(tmp_path / "catalog")
    assert cli_main(["--root", root, "desktop"]) == 0
    assert desktop_main(["--root", root]) == 0
    assert run_recorder == [(root, None), (root, None)]
    # --watchlist проходит в ту же дверь без переписывания
    assert cli_main(["--root", root, "desktop",
                     "--watchlist", "demo-list"]) == 0
    assert run_recorder[-1] == (root, "demo-list")


def test_door_without_root_uses_the_window_default(monkeypatch, run_recorder):
    """Без --root окно открывается на своём каталоге по умолчанию
    ($RUSTERM_DATA / ~/.rusterm), а не на «.» из общего дефолта CLI;
    явный «--root .» — тот же путь к умолчанию окна."""
    import rusterm.store.paths as paths_module
    fake = paths_module.Path("/fake/default")
    monkeypatch.setattr(paths_module, "default_root", lambda: fake)
    assert cli_main(["desktop"]) == 0
    assert cli_main(["--root", ".", "desktop"]) == 0
    assert run_recorder == [(fake, None), (fake, None)]


def test_door_without_pyside6_speaks_words_not_traceback(
        tmp_path, monkeypatch, capsys, run_recorder):
    """Без PySide6 команда не падает трассировкой: словами, что
    поставить и какой группой зависимостей (слова window.run — те же,
    что у python3 -m rusterm.desktop). from-импорт берёт атрибут
    пакета, не заглядывая в sys.modules, поэтому у пакета атрибут
    window стирается вместе с записью в sys.modules; стираются и все
    записи PySide6* — иначе повторный импорт возьмёт модули из кэша
    и окно откроется настоящее."""
    import rusterm.desktop
    for name in [k for k in sys.modules
                 if k == "PySide6" or k.startswith("PySide6.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "PySide6", None)
    monkeypatch.delattr(rusterm.desktop, "window", raising=False)
    monkeypatch.delitem(sys.modules, "rusterm.desktop.window",
                        raising=False)
    code = cli_main(["--root", str(tmp_path), "desktop"])
    out = capsys.readouterr().out
    assert code != 0
    assert "PySide6 не установлен" in out
    assert "rusterm[desktop]" in out
    assert "Traceback" not in out
    assert run_recorder == []


def test_door_creates_no_data_dir(tmp_path, run_recorder):
    """Правило B35: сама команда каталог не создаёт — даже до окна."""
    missing = tmp_path / "nope"
    assert cli_main(["--root", str(missing), "desktop"]) == 0
    assert not missing.exists()
    assert run_recorder == [(str(missing), None)]
