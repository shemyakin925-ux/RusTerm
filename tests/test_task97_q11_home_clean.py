"""ТЗ-97 Q11: ничего нового в домашней папке пользователя.

Пользователь 24.09 собрал всё в один каталог: `~/EquityLab/` — `app/`
(код, из которого запускают окно), `data/` (база), `backups/`,
`archive/`. Ярлык на рабочем столе уже смотрит туда. Значит каталог
данных по умолчанию — `~/EquityLab/data`, а не `~/.rusterm`: прежний
выбор писал в соседний, второй по счёту домашний каталог, и в домашней
папке пользователя живёт осколок круга 100 (`~/.rusterm` с 44 бумагами
мимо его воли).

Что закреплено здесь (пункт 4 правил ТЗ-90 A5 остаётся в силе — меняется
ТОЛЬКО значение):
- правило 4 = `Path.home()/"EquityLab"/"data"`, номер правила тот же,
  верхние правила не тронуты;
- пишущая дверь без `--root` создаёт в HOME ровно `EquityLab/` — ничего
  больше (файл ключей `~/.rusterm.env` не в счёт: прогон его не пишет);
- копия базы, для которой пользователь не назвал путь, живёт в
  `EquityLab/backups/<дата>[-метка].zip` — рядом с `data/`, а не внутри
  него и не в `~`;
- `~/.rusterm` как каталог данных не назван больше ни в одном совете, ни
  в `--help` (`.rusterm.env` — имя файла ключей, оно остаётся);
- изоляция: HOME подменён у всех тестов default-прогона, поэтому прогон
  набора не может написать в настоящую домашнюю папку (P7).

Офлайн: сеть не нужна (страж `_no_network_in_default_run`), каталог —
`tmp_path`, настоящего каталога пользователя тесты не касают.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from rusterm import cli
from rusterm.store.paths import AppPaths, resolve_root

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Песочный HOME, рядом с которым нет базы: тогда каталог выбирается
    именно по правилу 4, а не по 2 или 3."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    monkeypatch.chdir(tmp_path)
    return h


# ── 1. правило 4 ──────────────────────────────────────────────────────────

def test_rule_4_is_the_users_data_folder(home):
    assert resolve_root() == (home / "EquityLab" / "data", 4)


def test_the_upper_rules_still_win(home, monkeypatch, tmp_path):
    """Перенос значения не трогает порядок: явный `--root`, окружение и
    лежащая рядом база по-прежнему сильнее дома."""
    env_dir = tmp_path / "from_env"
    monkeypatch.setenv("RUSTERM_DATA", str(env_dir))
    assert resolve_root() == (env_dir, 2)
    monkeypatch.delenv("RUSTERM_DATA")
    nearby = tmp_path / "nearby"
    nearby.mkdir()
    (nearby / "rusterm.db").write_text("", encoding="utf-8")
    monkeypatch.chdir(nearby)
    assert resolve_root() == (Path("."), 3)


# ── 2. пишущая дверь не оставляет в HOME ничего лишнего ──────────────────

def test_a_writing_door_creates_only_equitylab_in_home(home, capsys):
    assert cli.main(["init"]) == 0
    capsys.readouterr()
    assert sorted(p.name for p in home.iterdir()) == ["EquityLab"]
    assert (home / "EquityLab" / "data" / "rusterm.db").exists()
    assert resolve_root()[0] == home / "EquityLab" / "data"


# ── 3. копии базы ─────────────────────────────────────────────────────────

def test_backup_without_a_path_lands_in_the_backups_folder(home, capsys):
    cli.main(["init"])
    capsys.readouterr()
    assert cli.main(["backup"]) == 0
    backups = home / "EquityLab" / "backups"
    names = sorted(p.name for p in backups.iterdir())
    assert names == [f"{dt.date.today().isoformat()}.zip"], names
    assert sorted(p.name for p in home.iterdir()) == ["EquityLab"]


def test_a_backup_label_goes_into_the_name(home, capsys):
    cli.main(["init"])
    capsys.readouterr()
    assert cli.main(["backup", "--label", "before-demo"]) == 0
    assert (home / "EquityLab" / "backups" /
            f"{dt.date.today().isoformat()}-before-demo.zip").exists()


def test_a_backup_label_cannot_be_a_path(home, capsys):
    """Метка попадает в имя файла, поэтому она не путь: `--label
    ../../escape` не должен вынести копию из `backups/` наружу."""
    cli.main(["init"])
    capsys.readouterr()
    assert cli.main(["backup", "--label", "../../escape"]) == 1
    assert sorted(p.name for p in home.iterdir()) == ["EquityLab"]
    assert not list(home.rglob("escape.zip"))


def test_the_backup_folder_is_a_sibling_of_the_data_root(tmp_path):
    """Каталог копий выводится из корня, а не из HOME: у
    `--root /tmp/x/data` копия обязана лечь в `/tmp/x/backups`, иначе
    «копия рядом с базой» снова стала бы новой папкой в домашнем
    каталоге пользователя, который открыл чужую базу."""
    want = (tmp_path / "EquityLab" / "backups").resolve()
    paths = AppPaths.from_root(tmp_path / "EquityLab" / "data")
    assert paths.backups == want
    assert not paths.backups.exists(), "свойство не создаёт каталог"


# ── 4. советы и код не называют прежний каталог ──────────────────────────

def test_help_names_the_new_default_and_not_the_old_one(capsys):
    """И `--help` whole, и `rusterm desktop --help`: пользователь читает
    совет, а не код."""
    text = ""
    for argv in (["--help"], ["desktop", "--help"]):
        with pytest.raises(SystemExit) as exit_info:
            cli.main(argv)
        assert exit_info.value.code == 0
        text += capsys.readouterr().out
    assert text.count("~/EquityLab/data") >= 2, text
    assert "~/.rusterm" not in text.replace("~/.rusterm.env", "")


def test_no_stale_data_directory_in_the_package():
    """Городовой заставки ТЗ-97 Q11: «git grep -n '~/.rusterm\\b' rusterm
    пуст, кроме имени файла ключей». Одна строка остаться не могла, а
    снять её нельзя: страж P2 (`agent/selfcheck.sh`) считает снятой любую
    снятую строку `db.py` кроме подъёма `_SCHEMA_VERSION`, а подъёма схемы
    в этом пункте нет. Поэтому зуб исключает не файл, а называет строку
    целиком: новая строка с прежним путём красная, и красен любой, кто
    тихо перепишет названную — иначе исключение переживёт свою причину.
    Развилка записана в отчёт (REPORT-97, Disputed 4)."""
    assert _stale_data_directory_lines() == [
        "rusterm/store/db.py: (ТЗ-95 F1: у пользователя `~/.rusterm` — "
        "схема 44, таблицы разговоров",
    ]


def _stale_data_directory_lines() -> list[str]:
    """Каждая строка пакета, где прежний каталог назван как путь."""
    offenders = []
    for path in sorted((ROOT / "rusterm").rglob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            for at in _occurrences(line, "~/.rusterm"):
                if line.startswith("~/.rusterm.env", at):
                    continue
                offenders.append(
                    f"{path.relative_to(ROOT)}: {line.strip()}")
    return offenders


def _occurrences(line: str, needle: str) -> list[int]:
    hits, at = [], line.find(needle)
    while at >= 0:
        hits.append(at)
        at = line.find(needle, at + 1)
    return hits


# ── 5. изоляция HOME для всего default-прогона ────────────────────────────

def test_home_is_patched_for_every_ordinary_test(tmp_path_factory):
    """Сам факт подмены — не вежливость, а дверь P7: с новым значением
    правила 4 тест без изоляции писал бы в настоящую базу пользователя
    (`~/EquityLab/data`), а не в песочницу."""
    sandbox = tmp_path_factory.getbasetemp()
    assert Path.home().is_relative_to(sandbox), \
        f"conftest не подменил HOME: {Path.home()} вне песочницы {sandbox}, " \
        "прогон набора может написать в домашний каталог пользователя"


def test_the_live_run_is_the_one_exception():
    """Живому прогону нужен настоящий `~/.rusterm.env` с ключами, поэтому
    подмена HOME его не трогает. Правило выбора обязана различать
    `not live` (дефолт, подмена обязательна) и `live` (подмены нет):
    перепутанные стороны молча либо лишат живой прогон ключей, либо
    вернут P7-риск в default-прогон."""
    from tests.p7_home_isolation import live_run_selected

    picks = [("", False), ("not live", False), ("live", True),
             ("live and not slow", True), ("not live and x", False),
             ("mark x", False)]
    for expr, want_live in picks:
        assert live_run_selected(expr) is want_live, \
            f"селектор {expr!r}: живой прогон ожидается {want_live}"


def test_the_home_allow_list_is_closed(tmp_path):
    """Страж сессии сверяет подменённый HOME с закрытым списком. Пустой
    каталог — чисто; `EquityLab` — чисто; любая другая папка — сигнал,
    и она же называется в сообщении (иначе прогон краснеет молча)."""
    from tests.p7_home_isolation import extra_entries

    home = tmp_path / "sandbox-home"
    home.mkdir()
    assert extra_entries(home) == []
    (home / "EquityLab" / "data").mkdir(parents=True)
    assert extra_entries(home) == []
    (home / ".rusterm").mkdir()
    assert extra_entries(home) == [".rusterm"]
