"""ТЗ-83 F3: враждебные контейнеры ручного импорта.

Входы из ТЗ на одном проводе `extract_text`: zip-бомба (объявлено
>= 1 GiB, на диске — сотня байт), zip с элементом `../` (и его вариант с
обратным слешем), магия PDF + мусор, docx без `word/document.xml`,
пустой файл и «магия, а после неё ноль байт». От каждого — отказ
значением, причиной из уже существующего семейства, быстрее чем за
`DEADLINE_SECONDS + 1`, и ни одного файла вне `tmp_path`.

Статичные контейнеры лежат в tests/data/fuzz/extract/ и воспроизводятся
оттуда же в Ф4; соответствие файлов генератору проверяется отдельным
тестом, чтобы папка не протухла молча.
"""
from __future__ import annotations

import hashlib
import io
import re
import struct
import time
import zipfile
from pathlib import Path

import pytest

from rusterm.manual import extract as _extract
from rusterm.manual.extract import DEADLINE_SECONDS, extract_text
from rusterm.providers.base import ProviderError

_ROOT = Path(__file__).resolve().parents[1]
_CORPUS = _ROOT / "tests" / "data" / "fuzz" / "extract"

# 1 GiB «после распаковки» при 125 байтах на диске: потолок
# MAX_ZIP_UNCOMPRESSED (512 MiB) заведомо превышен.
_BOMB_1GIB = 1024 ** 3
_ESCAPE = "RT83-ESCAPED"


_STAMP = (1980, 1, 1, 0, 0, 0)


def _zip(members: dict[str, bytes]) -> bytes:
    """Метки времени в архиве закреплены (_STAMP): иначе байты генератора
    меняются вместе с часами, и тест «корпус = генератор» краснеет на
    следующий день после коммита."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members.items():
            info = zipfile.ZipInfo(name, date_time=_STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, payload)
    return buf.getvalue()


def _zip_bomb(declared: int = _BOMB_1GIB, field: int = 24) -> bytes:
    """Настоящий zip, у которого размер задан в центральном каталоге:
    поле uncompressed size лежит по смещению 24 от сигнатуры
    PK\\x01\\x02 (compressed — 20; в локальном заголовке наоборот —
    замер Ф3). Guard читает infolist(), то есть именно каталог, и
    отказывает до всякой распаковки. field=20 — это бомба наоборот:
    огромный заявленный СЖАТЫЙ размер, который guard не читает."""
    raw = bytearray(_zip({"payload.txt": b"x" * 16}))
    cd = raw.find(b"PK\x01\x02")
    assert cd >= 0, "не найден центральный каталог"
    struct.pack_into("<I", raw, cd + field, declared)
    return bytes(raw)


# Валидный ПУСТЫЙ архив: только End Of Central Directory (PK\\x05\\x06).
# Магическая строка extract.py — PK\\x03\\x04, поэтому такой вход в
# ветку контейнеров не попадает и отказывается как бинарный мусор
# (замер Ф3, записано в Disputed 5 — отказ верный, имя причины спорное).
_EMPTY_ZIP = b"PK\x05\x06" + b"\x00" * 18


def _zip_lying_size(declared: int = 16, real: int = 2 * 1024 * 1024) -> bytes:
    """Архив, который врёт в МЕНЬШУЮ сторону: объявлено 16 байт, а после
    распаковки их `real`. Потолок `_zip_guard` суммирует объявленные
    размеры, поэтому такую бомбу он пропускает — останавливает только
    проверка CRC внутри `zipfile` (замер Ф3). Правим оба места:
    uncompressed size в центральном каталоге (+24 от PK\\x01\\x02) и в
    локальном заголовке (+22 от PK\\x03\\x04); сжатый размер и CRC не
    трогаем — иначе архив перестаёт быть «архивом с честным CRC»."""
    body = b"<w:document>" + b"x" * real + b"</w:document>"
    raw = bytearray(_zip({"word/document.xml": body}))
    struct.pack_into("<I", raw, raw.find(b"PK\x01\x02") + 24, declared)
    struct.pack_into("<I", raw, raw.find(b"PK\x03\x04") + 22, declared)
    return bytes(raw)


_ZIP_LIES = _zip_lying_size()


_CASES: dict[str, bytes] = {
    "zip-bomb-1gib": _zip_bomb(),
    "zip-bomb-compressed-field": _zip_bomb(field=20),
    "zip-lies-declares-16": _ZIP_LIES,
    "zip-empty-archive": _EMPTY_ZIP,
    "zip-traversal-slash": _zip({f"../{_ESCAPE}-slash.txt": b"escape"}),
    "zip-traversal-backslash": _zip({f"..\\{_ESCAPE}-back.txt": b"escape"}),
    "zip-traversal-in-docx": _zip({"word/document.xml": b"<w:document/>",
                                   f"../{_ESCAPE}-docx.txt": b"escape"}),
    "docx-without-document-xml": _zip({"[Content_Types].xml": b"<Types/>"}),
    "pdf-magic-junk": b"%PDF-1.7\n" + b"\x00\x01 junk " * 8,
    "pdf-magic-only": b"%PDF-",
    "zip-magic-only": b"PK\x03\x04",
    "empty-file": b"",
}


def _known_reasons() -> set[str]:
    """Семейство причин, которые extract.py произносит сам. Собирается
    из исходника, а не сочиняется: тест не может «разрешить» причину,
    которой в модуле нет."""
    source = Path(_extract.__file__).read_text(encoding="utf-8")
    return set(re.findall(r'reason=f?"([a-z_]+)', source))


def _call(tmp_path: Path, name: str, payload: bytes):
    """extract_text по файлу в tmp_path: (результат, секунды). Проверяет
    два требования Ф3 — время и что рядом ничего не появилось.

    Снимок берётся ПОСЛЕ записи файла и ПОСЛЕ autouse-фикстуры
    `tests/conftest.py:35`, которая сама кладёт в tmp_path
    `empty-rusterm.env` (изоляция окружения, P7): наивная проверка
    «в tmp_path не появилось файлов» краснеет на ней, а не на импорте
    (замер Ф3)."""
    path = tmp_path / name
    path.write_bytes(payload)
    outer_before = {p.name for p in tmp_path.parent.iterdir()}
    inner_before = {p.name for p in tmp_path.iterdir()}
    start = time.monotonic()
    try:
        out = extract_text(path)
    finally:
        took = time.monotonic() - start
    assert took <= DEADLINE_SECONDS + 1, (
        f"{name}: extract_text молчал {took:.1f}s при потолке "
        f"{DEADLINE_SECONDS + 1:.0f}s")
    outer = {p.name for p in tmp_path.parent.iterdir()} - outer_before
    assert not outer, f"{name}: импорт оставил {sorted(outer)} вне tmp_path"
    inner = {p.name for p in tmp_path.iterdir()} - inner_before
    assert not inner, f"{name}: внутри tmp_path добавилось {sorted(inner)}"
    return out, took


@pytest.mark.parametrize("case", sorted(_CASES))
def test_hostile_container_refuses_as_value(tmp_path, case):
    out, _took = _call(tmp_path, case, _CASES[case])
    assert isinstance(out, ProviderError), (
        f"{case}: враждебный контейнер вернулся как Document: "
        f"{repr(out)[:200]}")
    reason = out.reason or ""
    assert reason, f"{case}: отказ без именованной причины"
    assert reason.split(":")[0] in _known_reasons(), (
        f"{case}: причина {reason!r} не из семейства, которое "
        f"произносит extract.py: {sorted(_known_reasons())}")


def test_zip_bomb_refused_on_declared_size_before_unpacking(tmp_path):
    """Глава Ф3: бомба распознаётся по объявленному размеру, до
    распаковки — и объявленный размер больше потолка на порядок, а
    файла на диске нет вообще (125 байт)."""
    payload = _CASES["zip-bomb-1gib"]
    assert len(payload) < 4096, (
        f"бомба должна быть меньше 4 КиБ на диске, а не {len(payload)} Б")
    out, took = _call(tmp_path, "zip-bomb-1gib", payload)
    assert isinstance(out, ProviderError), repr(out)[:200]
    assert (out.reason or "").startswith("extract_zip_bomb:uncompressed>"), (
        f"бомба отвергнута не по потолку распаковки, а иначе: "
        f"{out.reason!r} — guard не сработал?")
    assert took < 1.0, f"отказ по объявленному размеру занял {took:.2f}s"


def test_zip_member_count_ceiling(tmp_path):
    """Второе крыло guard'а: не размер, а число элементов. Архив из
    `MAX_ZIP_MEMBERS + 1` файлов строится на месте (4 Кбайт с хвостиком
    на диск не просят) и обязан отказаться по потолку элементов — до
    этого эта ветка не была закреплена ни одним тестом."""
    payload = _zip({f"m{i}.txt": b"x"
                    for i in range(_extract.MAX_ZIP_MEMBERS + 1)})
    out, took = _call(tmp_path, "zip-many-members", payload)
    assert isinstance(out, ProviderError), repr(out)[:200]
    assert (out.reason or "") == (
        f"extract_zip_bomb:members>{_extract.MAX_ZIP_MEMBERS}"), (
        f"отказ по числу элементов пришёл с другой причиной: "
        f"{out.reason!r}")
    assert took < 1.0, f"потолок по числу элементов проверили за {took:.2f}s"


def test_zip_lying_about_small_size_fools_the_ceiling_and_still_refuses(
        tmp_path):
    """Честная граница потолка: `_zip_guard` суммирует ОБЪЯВЛЕННЫЕ
    размеры, поэтому архив, заявивший 16 байт вместо 2 МиБ, проходит
    мимо него. Замер Ф3 показывает, что дальше `zipfile` не даёт
    прочитать лишнее: CRC не сходится (замер: `BadZipFile: Bad CRC-32`
    и при `zf.read`, и при потоковом `zf.open`), а `extract_text`
    возвращает значение. Тест закрепляет именно
    это — отказ есть, но причиной стал не guard (иначе «страж по
    объявленному размеру» будет выглядеть всесильным)."""
    out, took = _call(tmp_path, "zip-lies-declares-16", _ZIP_LIES)
    assert isinstance(out, ProviderError), repr(out)[:200]
    assert not (out.reason or "").startswith("extract_zip_bomb"), (
        f"архив с объявленным размером 16 байт больше не проходит мимо "
        f"потолка — перепиши тест и заметку в отчёте: {out.reason!r}")
    assert took < 1.0, (
        f"ложь в заголовке распаковывалась {took:.2f}s — потолок по "
        f"объявленному размеру не помог, а дедлайн не спас")


def test_magic_table_knows_only_local_header_zip(tmp_path):
    """Что именно отказывает, а что только кажется отказом.

    Валидный пустой архив (один EOCD, PK\\x05\\x06) в контейнерную ветку
    не попадает: `_ZIP_MAGIC` в extract.py — это PK\\x03\\x04, то есть
    локальный заголовок. Вход всё равно отвергается, но причиной
    `format_unsupported:binary` — текстовая ветка увидела NUL. Это
    записано как есть (Disputed 5 отчёта), а тест держит фактическое
    поведение, чтобы будущая правка магической таблицы стала заметной.

    Вторая половина: бомба, у которой задано не то поле центрального
    каталога (compressed size вместо uncompressed), guard проходит —
    он читает `file_size`, то есть размер после распаковки. Отказ всё
    равно есть, но по другой причине; тест фиксирует и это, чтобы
    «страж по объявленному размеру» не выглядел всемогущим.
    """
    empty, _ = _call(tmp_path, "zip-empty-archive", _CASES["zip-empty-archive"])
    assert isinstance(empty, ProviderError), repr(empty)[:200]
    assert empty.reason == "format_unsupported:binary", (
        f"пустой архив отказывается иначе, чем замерено в Ф3: "
        f"{empty.reason!r}")
    wrong_field, _ = _call(tmp_path, "zip-bomb-compressed-field",
                           _CASES["zip-bomb-compressed-field"])
    assert isinstance(wrong_field, ProviderError), repr(wrong_field)[:200]
    assert not (wrong_field.reason or "").startswith("extract_zip_bomb"), (
        f"guard научился читать заявленный сжатый размер — перепиши "
        f"тест и заметку в отчёте: {wrong_field.reason!r}")


def test_traversal_members_write_nothing(tmp_path):
    """`../` и `..\\` в именах элементов: ни один вариант не должен
    оставить файл ни в tmp_path, ни рядом. Проверка `_call` смотрит
    родительский каталог tmp_path — именно туда попадёт запись, если
    какой-нибудь экстрактор решит раскладывать архив на диск."""
    for case in ("zip-traversal-slash", "zip-traversal-backslash"):
        out, _took = _call(tmp_path, case, _CASES[case])
        assert isinstance(out, ProviderError), f"{case}: {repr(out)[:200]}"
    escaped = sorted(p.name for p in tmp_path.parent.iterdir()
                     if _ESCAPE in p.name)
    assert not escaped, f"элементы архива оказались на диске: {escaped}"


def test_docx_route_refuses_without_its_parts(tmp_path):
    """Контейнер, который притворяется docx: без `word/document.xml`
    это не docx (ветка unknown_zip_container), а с ним, но без
    остальных частей — отказ от самой библиотеки форматов. Обе ветки
    допустимы и обе именованы; живая ли python-docx или нет — у теста
    спрашивать не должно."""
    plain, _ = _call(tmp_path, "docx-without-document-xml",
                     _CASES["docx-without-document-xml"])
    assert isinstance(plain, ProviderError), repr(plain)[:200]
    assert (plain.reason or "") == "format_unsupported:unknown_zip_container", (
        f"zip без документных частей должен отказать как неизвестный "
        f"контейнер, а не: {plain.reason!r}")
    sneaky, _ = _call(tmp_path, "zip-traversal-in-docx",
                      _CASES["zip-traversal-in-docx"])
    assert isinstance(sneaky, ProviderError), repr(sneaky)[:200]
    head = (sneaky.reason or "").split(":")[0]
    assert head in _known_reasons(), f"неизвестная причина {sneaky.reason!r}"


def test_magic_without_body_refuses(tmp_path):
    """«Магия есть, а после неё ничего»: пустой файл, голый PK\\x03\\x04,
    голое %PDF- и одиночный NUL. Отказ значением, не исключение и не
    пустой успех."""
    cases = dict(_CASES)
    cases["nul-only"] = b"\x00"
    for name in ("empty-file", "zip-magic-only", "pdf-magic-only",
                 "nul-only"):
        out, _took = _call(tmp_path, name, cases[name])
        assert isinstance(out, ProviderError), f"{name}: {repr(out)[:200]}"


def test_known_reason_family_is_not_empty():
    """Зубы: если regex причин в исходнике перестанет что-либо находить,
    проверка «причина из существующего семейства» станет пустой."""
    reasons = _known_reasons()
    assert len(reasons) >= 8, f"семейство причин: {sorted(reasons)}"
    assert "extract_zip_bomb" in reasons, sorted(reasons)
    assert "format_unsupported" in reasons, sorted(reasons)


def test_corpus_folder_matches_generated_inputs():
    """Папка tests/data/fuzz/extract кормит replay (Ф4): файлы обязаны
    совпадать с генератором побайтно, иначе replay проверяет не то, что
    находит тест."""
    assert _CORPUS.is_dir(), (
        f"нет папки корпуса {_CORPUS} — Ф3 обещает оставить её в "
        f"репозитории")
    stored = {p.stem: p.read_bytes() for p in _CORPUS.glob("*.bin")}
    assert stored, f"папка {_CORPUS} пуста"
    expected = {
        hashlib.sha256(payload).hexdigest()[:8]: payload
        for name, payload in _CASES.items() if payload
    }
    assert set(stored) == set(expected), (
        f"корпус разошёлся с генератором: в git {sorted(stored)}, "
        f"тест строит {sorted(expected)}")
    for sha8, payload in expected.items():
        assert stored[sha8] == payload, f"{sha8}.bin не совпадает с генератором"
