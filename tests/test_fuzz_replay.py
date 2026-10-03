"""ТЗ-83 F4: реплей папки tests/data/fuzz.

Ф1 и Ф2 обещали: каждый найденный дефект остаётся файлом в
tests/data/fuzz/<точка входа>/<sha8>.bin. Этот файл проверяет обещание
по машинной проверке: по одному тесту на файл, контракт — из той же таблицы ТЗ,
что и у свойств Ф1 (используются публичные check_* из
tests/test_fuzz_parsers.py, чтобы реплей и свойство не разошлись).

Пустая папка при объявленных дефектах — красный тест, а не skip:
молчаливое «нечего проверять» было бы способом убрать доказательства,
не трогая отчёт.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_fuzz_parsers import (
    check_companyfacts_contract,
    check_cvm_contract,
    check_extract_contract,
    check_form4_contract,
    check_parse_auto_contract,
)

_ROOT = Path(__file__).resolve().parents[1]
_FUZZ = _ROOT / "tests" / "data" / "fuzz"

# Точки входа, для которых Ф1/Ф2/Ф3 нашли хотя бы один дефект. Новый
# каталог без записи здесь — красный тест ниже, а не невидимый пропуск.
KNOWN_ENTRIES = {
    "form4": "строка 1: OwnershipFiling или ValueError",
    "companyfacts": "строка 2: ParseResult на любом входе",
    "cvm": "строка 3: (facts, unparsed), факт конечен",
    "parse_auto": "строка 4: ParseResult или None",
    "parse_auto_xbrl": "строка 4: тот же контракт, таксономия xbrl",
    "parse_auto_table": "строка 4: тот же контракт, раздел tables",
    "extract": "строка 5: Document или ProviderError, не бросает",
}

# metadata для parse_auto: папка названа по разделу payload, который в
# нём действительно есть (замер Ф1 — см. agent/REPORT-83.md).
_AUTO_META = {
    "parse_auto": {"doc_kind": "companyfacts", "doc_type": "10-K"},
    "parse_auto_xbrl": {"doc_kind": "xbrl", "doc_type": "10-K"},
    "parse_auto_table": {"doc_kind": "table", "doc_type": "PRICES"},
}
# statement для CvmDfpParser.parse_rows: срез, из которого собраны
# файлы-репро (Ф1), а не выдуманный DRE.
_CVM_STATEMENT = "DRE"


def _folders() -> list[Path]:
    return sorted(p for p in _FUZZ.iterdir() if p.is_dir()) \
        if _FUZZ.is_dir() else []


def _files() -> list[tuple[str, Path]]:
    return [(folder.name, path)
            for folder in _folders()
            for path in sorted(folder.glob("*.bin"))]


def _params() -> list[tuple[str, Path]]:
    """Пустой корпус не должен превращать тест в skip: вместо
    пустого параметра подставляется страж, и он же красный."""
    return _files() or [("<пусто>", _FUZZ)]


def _replay(entry: str, path: Path, tmp_path: Path) -> None:
    blob = path.read_bytes()
    if entry == "form4":
        check_form4_contract(blob)
    elif entry == "companyfacts":
        check_companyfacts_contract(blob)
    elif entry in _AUTO_META:
        check_parse_auto_contract(blob, _AUTO_META[entry])
    elif entry == "cvm":
        rows = json.loads(blob.decode("utf-8"))
        check_cvm_contract(rows, _CVM_STATEMENT)
    elif entry == "extract":
        # строка 5 принимает путь, а не байты: файл пишется в tmp_path,
        # корпус репозитория не трогается
        probe = tmp_path / path.name
        probe.write_bytes(blob)
        check_extract_contract(probe)
    else:  # pragma: no cover - закрыто тестом ниже
        raise AssertionError(f"нет контракта для точки входа {entry!r}")


@pytest.mark.parametrize("entry,path", _params(),
                         ids=lambda p: p.name if isinstance(p, Path) else p)
def test_replay_file_respects_its_declared_contract(entry, path, tmp_path):
    """Каждый записанный репро проходит по своей строке таблицы ТЗ."""
    if entry == "<пусто>":
        raise AssertionError(
            f"{_FUZZ} не содержит ни одного .bin — воспроизводить "
            f"нечего, а Ф1/Ф2/Ф3 объявили дефекты")
    _replay(entry, path, tmp_path)


def test_fuzz_folder_exists_and_is_not_empty():
    """Пустая папка при том, что Ф1 объявил 19 семейств дефектов, — это
    потерянные доказательства, а не «нечего воспроизводить»."""
    assert _FUZZ.is_dir(), f"нет папки корпуса {_FUZZ}"
    files = _files()
    assert files, (
        f"{_FUZZ} существует, но пуста: Ф1 записал 19 файлов-репро, "
        f"их нет — тест обязан быть красным, а не skip")


def test_every_known_entry_has_files():
    """Ни одна точка входа не «исчезает» молча: пустой каталог при
    объявленных дефектах красен сам по себе."""
    for entry, contract in sorted(KNOWN_ENTRIES.items()):
        folder = _FUZZ / entry
        assert folder.is_dir(), (
            f"нет каталога {folder} — {contract} (Ф1/Ф2/Ф3 обещали "
            f"репро там)")
        files = list(folder.glob("*.bin"))
        assert files, f"{folder} пуст, хотя {contract} имел дефекты"


def test_no_unmapped_entry_folders():
    """Новая папка в корпусе обязана принести и контракт: иначе её
    файлы не проверяются ничем."""
    unknown = [folder.name for folder in _folders()
               if folder.name not in KNOWN_ENTRIES]
    assert not unknown, (
        f"каталоги без записи о контракте: {unknown} — добавь их в "
        f"KNOWN_ENTRIES вместе с проверкой")


@pytest.mark.parametrize("entry,path", _params(),
                         ids=lambda p: p.name if isinstance(p, Path) else p)
def test_replay_file_name_is_the_sha8_of_its_bytes(entry, path):
    """Имя файла — это sha256(...)[:8] его содержимого (правило Ф1):
    иначе переименованный или испорченный артефакт перестаёт быть
    воспроизводимым доказательством."""
    if entry == "<пусто>":
        pytest.fail("пустой корпус: имени нет")
    name = path.stem
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    assert name == digest, (
        f"{entry}/{path.name}: содержимое не совпадает с именем — "
        f"sha8 байтов {digest}")


def test_replay_corpus_covers_the_reported_entries():
    """Счётчик как зуб: у каждой точки входа есть пол, равный числу
    записанных репро (Ф1 — 19 файлов на четырёх JSON-точках и CVM, Ф2 —
    billion laughs в form4, Ф3 — 11 контейнеров в extract). Общий пол без
    персональных был бы дырой: удалить половину папки extract и остаться
    зелёным — не проверка."""
    floors = {"companyfacts": 3, "cvm": 5, "extract": 11, "form4": 2,
              "parse_auto": 4, "parse_auto_table": 3, "parse_auto_xbrl": 3}
    assert set(floors) == set(KNOWN_ENTRIES), (
        "полы по корпусу и список точек входа разошлись")
    missing = []
    for entry, floor in sorted(floors.items()):
        have = len(list((_FUZZ / entry).glob("*.bin")))
        if have < floor:
            missing.append(f"{entry}: {have} вместо {floor}")
    assert not missing, (
        "корпус похудел относительно записанного в отчёте: "
        + "; ".join(missing))
