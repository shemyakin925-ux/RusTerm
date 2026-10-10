"""ТЗ-105 R1: `census --rebuild` говорит, что пишет.

Решение координатора (REPORT-103, пункт 9): «`census --rebuild` may
write; say so». Help-текст флага обещал «пересобрать снапшот перед
переписью» — глагол без следа: ни слова о том, что команда трогает базу
пользователя. Докстрока `cmd_census` о пересборке не упоминала вовсе,
хотя лежала под ней строка комментария про ТЗ-58 C3.

Замер, из которого родились зубчики (копия базы пользователя, `mode=ro`
нигде не писала — команда сама решала, писать ли):

| что | было | стало |
|---|---|---|
| `census` без `--rebuild` на каталоге со снапшотом | база байт в байт та же | то же, и это закреплено (Done when) |
| `census --rebuild` | версия снимка растёт, текст этого не обещал | текст обещает: «пишет в базу» |
| у инструмента нет снапшота | `census` строит первый и пишет | так же, но названо в докстроке |
| `apply_migrations` внутри `census` | поднимает схему базы молча | то же; это второй писатель, он в «Спорном» |

Схема правки минимальна: формулировка флага и абзац докстроки. Поведение
не изменено ни на байт — менять его здесь не о чем, а вот не знать о
нём — было можно.
"""
import hashlib
import sqlite3
from pathlib import Path

import pytest

from rusterm.cli import cmd_census, main
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

_IID = "US-R1"


def _seed(tmp_path):
    """Каталог с одним инструментом и одним собранным снапшотом."""
    root = tmp_path / "data"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-r1", "Radish Corp.", "US", "222222", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        _IID, "i-r1", None, "common", "active", None))
    conn.close()
    assert main(["--root", str(root), "snapshot", "--instrument", _IID]) == 0
    return root


def _sha(root):
    return hashlib.sha256((root / "rusterm.db").read_bytes()).hexdigest()


def _cli(root, *extra):
    return main(["--root", str(root), "census", "--instrument", _IID, *extra])


def _versions(root):
    conn = sqlite3.connect(f"file:{root / 'rusterm.db'}?mode=ro", uri=True)
    try:
        return [r[0] for r in conn.execute(
            "SELECT version FROM snapshot WHERE instrument_id=? "
            "ORDER BY version", (_IID,))]
    finally:
        conn.close()


def test_census_without_rebuild_leaves_the_db_byte_identical(tmp_path):
    """Done when: перепись без флага — чтение, а не запись.

    Байт в байт, а не «по количеству строк»: файл базы — то, что
    пользователь теряет, если диагностическая команда всё-таки пишет.
    """
    root = _seed(tmp_path)
    before = _sha(root)
    versions_before = _versions(root)
    assert _cli(root) == 0
    assert _sha(root) == before, "census без --rebuild изменил файл базы"
    assert _versions(root) == versions_before


def test_census_writes_only_the_side_files_a_reader_may_touch(tmp_path):
    """Стоп-кран к предыдущему: `-wal`/`-shm` не должны пережить команду.

    Иначе «байт в байт» следующего прогона зависит от чужого следа:
    незакрытый WAL — это запись в main-файл при следующем открытии.
    """
    root = _seed(tmp_path)
    assert _cli(root) == 0
    side = sorted(p.name for p in Path(root).glob("rusterm.db-*"))
    assert side == [], f"остались служебные файлы базы: {side}"


def test_rebuild_help_says_the_command_writes(tmp_path, capsys):
    """Флаг обязан называть последствие: «пишет в базу».

    `--help` у argparse — это SystemExit(0), не код возврата команды.
    """
    with pytest.raises(SystemExit) as caught:
        main(["--root", str(tmp_path), "census", "--help"])
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert "--rebuild" in help_text, help_text
    line = next(l for l in help_text.splitlines()
                if l.strip().startswith("--rebuild"))
    assert "пишет в базу" in line, f"help флага не говорит о записи: {line}"


def test_census_docstring_names_both_writers(tmp_path):
    """Докстрока `cmd_census` обязана упоминать --rebuild и запись.

    Диагностическая команда читается из исходника чаще, чем из `--help`:
    именно докстрока попадает в отчёты и пересказы.
    """
    doc = cmd_census.__doc__ or ""
    assert "--rebuild" in doc, doc
    assert "пишет" in doc, doc


def test_a_missing_snapshot_is_built_and_that_is_a_write(tmp_path):
    """Исключение из «читает»: без снимка перепись строит первый.

    Зубчик закрепляет НЕ то, что удобно формулировке пункта, а то, что
    команда делает на самом деле: `census` на свежем каталоге пишет.
    Формулировка «без --rebuild остаётся read-only» здесь не держится, и
    поэтому докстрока обязана это называть.
    """
    root = tmp_path / "data"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-r1", "Radish Corp.", "US", "222222", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        _IID, "i-r1", None, "common", "active", None))
    conn.close()
    assert _versions(root) == []
    assert _cli(root) == 0
    assert _versions(root) == [1], "первый снимок не собран — перепись пуста"


def test_rebuild_does_write_a_new_version(tmp_path):
    """Обещание флага проверено: после --rebuild версия растёт."""
    root = _seed(tmp_path)
    before = _versions(root)
    assert _cli(root, "--rebuild") == 0
    after = _versions(root)
    assert len(after) == len(before) + 1, (before, after)
