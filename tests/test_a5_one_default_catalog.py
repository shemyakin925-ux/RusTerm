"""ТЗ-90 A5: один каталог данных по умолчанию у CLI и у окна.

Прежний порядок расходился молча: `--root` в CLI по умолчанию был «.»,
а окно и собранный `.app` смотрели только в `$RUSTERM_DATA` /
`~/.rusterm`. Замер на дереве 4d0c4d2 (каталог с базой, HOME и
env-файл — песочные):

    $ cd /tmp/a5-probe/work && python3 -m rusterm.cli status
    каталог данных: /private/tmp/a5-probe/work
    $ python3 -c "from rusterm.store.paths import default_root;
                  print(default_root())"
    /tmp/a5-probe/home/.rusterm

одна и та же директория — две разные базы. Теперь порядок выбирает одна
функция (`store/paths.resolve_root`), и номер правила печатается
наружу: «открылась не та база» отличается от «здесь нет данных»
строкой, а не догадкой. Шапка окна проверяется в
tests/test_desktop_window.py — Qt сюда не пускает приёмка (пункт 6).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rusterm import env as env_module
from rusterm.cli import main as cli_main
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, resolve_root

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def catalog(tmp_path, monkeypatch):
    """Каталог с настоящей (мигрированной) базой + песочные HOME и
    env-файл: ни одно правило не зависит от машины теста."""
    home = tmp_path / "home"
    home.mkdir()
    data = tmp_path / "project"
    data.mkdir()
    conn = sqlite3.connect(str(data / "rusterm.db"), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    conn.close()
    (tmp_path / "empty.env").write_text("", encoding="utf-8")
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(tmp_path / "empty.env"))
    monkeypatch.setenv("HOME", str(home))
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    return {"data": data, "home": home, "tmp": tmp_path}


# ── 1. таблица из четырёх строк ──────────────────────────────────────────

def test_the_four_row_table(catalog, monkeypatch):
    """Каждое правило проверяется там, где оно ПРОТИВОРЕЧИТ следующему:
    явный корень — против окружения и каталога, окружение — против
    каталога, каталог — против дома."""
    explicit = catalog["tmp"] / "explicit"
    env_dir = catalog["tmp"] / "from_env"
    rows = [
        # (случай, ожидаемый путь, номер правила)
        ("explicit", explicit, 1),
        ("RUSTERM_DATA", env_dir, 2),
        ("./rusterm.db", Path("."), 3),
        ("home", catalog["home"] / ".rusterm", 4),
    ]
    assert [r[2] for r in rows] == [1, 2, 3, 4]
    for case, want, rule in rows:
        # условия всех нижних правил стоят и здесь: рядом лежит база,
        # HOME песочный — выбор должен сделать вид ВЕРХНЕЙ строки
        monkeypatch.setenv("RUSTERM_DATA", str(env_dir))
        monkeypatch.chdir(catalog["data"])
        if case == "explicit":
            got, got_rule = resolve_root(explicit)
        elif case == "RUSTERM_DATA":
            got, got_rule = resolve_root()
        else:
            monkeypatch.delenv("RUSTERM_DATA")
            if case == "./rusterm.db":
                got, got_rule = resolve_root()
            else:
                monkeypatch.chdir(catalog["tmp"])   # рядом базы нет
                got, got_rule = resolve_root()
        assert got == want, case
        assert got_rule == rule, case


def test_rule_3_only_when_the_base_actually_lies_there(catalog,
                                                       monkeypatch):
    """Правило 3 — не «текущий каталог всегда», а «рядом лежит
    rusterm.db»: в пустой директории программа не открывает базу,
    которой нет."""
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    empty = catalog["tmp"] / "empty-dir"
    empty.mkdir()
    monkeypatch.chdir(empty)
    assert resolve_root() == (catalog["home"] / ".rusterm", 4)


def test_the_env_file_line_is_rule_2_for_a_finder_launch(catalog,
                                                         monkeypatch):
    """Двойной щелчок — запуск без шелла: каталог приходит из
    `~/.rusterm.env`, и это то же правило 2, что у окружения."""
    data = catalog["data"]
    env_file = catalog["tmp"] / "rusterm.env"
    env_file.write_text(f"RUSTERM_DATA={data}\n", encoding="utf-8")
    env_file.chmod(0o600)
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(env_file))
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    env_module.load_env()
    assert resolve_root() == (data, 2)


# ── 2. номер правила виден наружу: его печатает status ───────────────────

def test_status_names_the_rule_it_used(catalog, monkeypatch, capsys):
    root = str(catalog["data"])
    assert cli_main(["--root", root, "status"]) == 0
    out = capsys.readouterr().out
    assert f"каталог данных: {AppPaths.from_root(root).root} " \
        "(правило: 1)" in out

    # тот же каталог без --root: рядом лежит rusterm.db → правило 3,
    # и путь остаётся тем же (это и есть починка расхождения)
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    monkeypatch.chdir(catalog["data"])
    assert cli_main(["status"]) == 0
    out = capsys.readouterr().out
    assert f"каталог данных: {AppPaths.from_root(root).root} " \
        "(правило: 3)" in out
    assert "правило: 1" not in out


# ── 3. страж: второго значения по умолчанию не осталось ──────────────────

def test_guard_no_second_default_for_the_data_root():
    """ТЗ-90 A5: `default="."` уходит из парсера, `RUSTERM_DATA` из
    окружения читает ровно один модуль, и домашний запасной путь тоже
    один. Иначе правило 2 снова распадётся на два мнения — CLI про «.»,
    окно про дом."""
    sources = {path: path.read_text(encoding="utf-8")
               for path in (ROOT / "rusterm").rglob("*.py")}
    assert len(sources) > 40, "страж почти ничего не прочитал"
    parser = sources[ROOT / "rusterm" / "cli" / "__init__.py"]
    assert 'default="."' not in parser
    assert "default_root" not in "".join(sources.values()), \
        "у старого имени по умолчанию остались читатели"
    readers = sorted(str(p.relative_to(ROOT))
                     for p, text in sources.items()
                     if 'environ.get("RUSTERM_DATA")' in text)
    assert readers == ["rusterm/store/paths.py"], readers
    fallbacks = sorted(str(p.relative_to(ROOT))
                       for p, text in sources.items()
                       if 'home() / ".rusterm"' in text)
    assert fallbacks == ["rusterm/store/paths.py"], fallbacks
