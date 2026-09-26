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
    calls: list[tuple[object, object, int]] = []
    monkeypatch.setattr(
        desktop_window, "run",
        lambda root, watchlist_id=None, rule=1:
        calls.append((root, watchlist_id, rule)) or 0)
    return calls


def test_desktop_listed_in_cli_help(capsys):
    with pytest.raises(SystemExit) as exited:
        cli_main(["--help"])
    assert exited.value.code == 0
    assert "desktop" in capsys.readouterr().out


def test_both_doors_call_the_same_run(tmp_path, run_recorder):
    from pathlib import Path

    from rusterm.desktop.__main__ import main as desktop_main
    root = Path(tmp_path / "catalog")
    assert cli_main(["--root", str(root), "desktop"]) == 0
    assert desktop_main(["--root", str(root)]) == 0
    # ТЗ-90 A5: явный корень — правило 1, и обе двери доносят его окну
    # одинаково (путь и номер правила)
    assert run_recorder == [(root, None, 1), (root, None, 1)]
    # --watchlist проходит в ту же дверь без переписывания
    assert cli_main(["--root", str(root), "desktop",
                     "--watchlist", "demo-list"]) == 0
    assert run_recorder[-1] == (root, "demo-list", 1)


def test_door_without_root_shares_the_cli_default(monkeypatch, run_recorder,
                                                  tmp_path):
    """ТЗ-90 A5: у двери нет своего значения по умолчанию. Без --root
    окно открывается там же, где CLI ($RUSTERM_DATA — правило 2), а не
    «на своём»; явный «--root .» — правило 1, то есть текущий каталог
    по слову пользователя, а не подменённый дефолт. Прежняя проверка
    доказывала обратное: что «.» ведёт себя как окно."""
    from pathlib import Path

    data = tmp_path / "catalog"
    monkeypatch.setenv("RUSTERM_DATA", str(data))
    assert cli_main(["desktop"]) == 0
    assert run_recorder == [(data, None, 2)]
    run_recorder.clear()
    here = Path(".")
    assert cli_main(["--root", ".", "desktop"]) == 0
    assert run_recorder == [(here, None, 1)]


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
    assert run_recorder == [(missing, None, 1)]
