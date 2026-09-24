"""ТЗ-83 F2: враждебный XML на входе parse_form4.

Две атаки из ТЗ: billion laughs (разрастание сущностей) и внешний
entity, указывающий на файл с известным маркером. Контракт строки 1
таблицы ТЗ-83 — «OwnershipFiling или ValueError»; F2 добавляет к нему
два требования: уложиться в 2 секунды и не протащить маркер ни в одно
поле результата (проверяется repr).

Отказ держится на самом парсере, а не на том, что повезло с версией
libexpat: см. test_harmless_entity_is_refused_too — сущность в 3 байта,
которую потолок амплификации expat 2.6+ не трогает.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from rusterm.parsers.ownership import OwnershipFiling, parse_form4
from tests.test_fuzz_parsers import check_form4_contract

LIMIT_SECONDS = 2.0
MARKER = "RT83-MARKER-NEVER-LEAK-4f9c"
_DATA = (Path(__file__).resolve().parents[1] / "tests" / "data"
         / "edgar" / "ownership")

XML_PROLOG = b'<?xml version="1.0" encoding="UTF-8"?>\n'
FILING_HEAD = (b"<ownershipDocument>\n"
               b"<issuer><issuerCik>320193</issuerCik>"
               b"<issuerName>Apple Inc.</issuerName></issuer>\n"
               b"<documentType>4</documentType>\n"
               b"<periodOfReport>2024-01-31</periodOfReport>\n"
               b"<reportingOwner><reportingOwnerId>"
               b"<rptOwnerName>JANE DOE</rptOwnerName>"
               b"</reportingOwnerId></reportingOwner>\n")


def _doc(dtd: str, tail: str = "") -> bytes:
    """Враждебная DTD в прологе, тело — настоящая обложка Form 4."""
    return XML_PROLOG + dtd.encode() + FILING_HEAD + tail.encode() \
        + b"</ownershipDocument>"


def _lol_dtd(levels: int = 9, width: int = 10) -> str:
    """lol1 = «lol», каждое следующее поколение повторяет предыдущее
    width раз: после подстановки lol9 — 3 * 10**8 байт текста."""
    parts = ['<!DOCTYPE ownershipDocument [\n<!ENTITY lol1 "lol">\n']
    for i in range(2, levels + 1):
        parts.append(f'<!ENTITY lol{i} "' + f"&lol{i - 1};" * width
                     + '">\n')
    parts.append("]>\n")
    return "".join(parts)


def _call(raw: bytes):
    """parse_form4 с замером: (секунды, результат или исключение)."""
    start = time.monotonic()
    try:
        out = parse_form4(raw)
    except BaseException as exc:  # noqa: BLE001 — замер, не логика
        return time.monotonic() - start, exc
    return time.monotonic() - start, out


def test_billion_laughs_refused_within_two_seconds():
    raw = _doc(_lol_dtd(), "<note>&lol9;</note>")
    took, out = _call(raw)
    assert took < LIMIT_SECONDS, (
        f"parse_form4 молчал {took:.2f}s на разрастании сущностей — "
        f"потолок Ф2 в 2s нарушен")
    assert isinstance(out, (ValueError, OwnershipFiling)), (
        f"parse_form4 бросил {type(out).__name__}: {str(out)[:120]}")
    assert isinstance(out, ValueError), (
        "billion laughs разобрался в документ вместо отказа")
    check_form4_contract(raw)


def test_external_entity_never_reads_the_file(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text(MARKER)
    raw = _doc(
        '<!DOCTYPE ownershipDocument [\n'
        f'<!ENTITY xxe SYSTEM "file://{secret}">\n]>\n',
        "<issuerNote>&xxe;</issuerNote>")
    took, out = _call(raw)
    assert took < LIMIT_SECONDS, f"внешняя сущность читалась {took:.2f}s"
    assert isinstance(out, (ValueError, OwnershipFiling)), (
        f"внешняя сущность дала {type(out).__name__}: {str(out)[:120]}")
    leak = MARKER in str(out)
    if isinstance(out, OwnershipFiling):
        leak = leak or MARKER in repr(out)
    assert not leak, (
        f"маркер {MARKER!r} просочился в ответ parse_form4 через "
        f"внешнюю сущность")
    check_form4_contract(raw)


def test_parameter_entity_does_not_fetch_the_file(tmp_path):
    """Второй способ вытащить файл — параметрная сущность в DTD.
    Контракт тот же: отказ или разбор за 2s, маркера в ответе нет."""
    secret = tmp_path / "param.txt"
    secret.write_text(MARKER)
    raw = _doc(
        '<!DOCTYPE ownershipDocument [\n'
        f'<!ENTITY % p SYSTEM "file://{secret}">\n%p;\n]>\n')
    took, out = _call(raw)
    assert took < LIMIT_SECONDS
    assert isinstance(out, (ValueError, OwnershipFiling)), (
        f"параметрная сущность дала {type(out).__name__}: "
        f"{str(out)[:120]}")
    assert MARKER not in str(out)
    if isinstance(out, OwnershipFiling):
        assert MARKER not in repr(out)
    check_form4_contract(raw)


def test_harmless_entity_is_refused_too():
    """Зубы: отказ обязан быть у парсера, а не у libexpat хоста.
    Сущность в 3 байта потолок амплификации (expat 2.6+) не трогает, и
    на базовом коммите такой документ разбирался в OwnershipFiling —
    то есть защита держалась на версии библиотеки. Обложка Form 4 DTD
    не несёт никогда, поэтому объявленная сущность — признак атаки, а
    не «странный, но разборный» вход."""
    raw = _doc('<!DOCTYPE ownershipDocument [<!ENTITY tiny "xyz">]>\n',
               "<note>&tiny;</note>")
    with pytest.raises(ValueError):
        parse_form4(raw)


def test_dtd_in_a_comment_still_refused():
    """Обход «резать пролог по первому тегу»: DTD прячется за
    комментарием, где есть «<» — срез пролога оборвался бы раньше DTD.
    Поиск идёт по всему буферу, поэтому обхода нет."""
    raw = _doc('<!-- <x> -->\n<!DOCTYPE ownershipDocument '
               '[<!ENTITY tiny "xyz">]>\n', "<note>&tiny;</note>")
    with pytest.raises(ValueError):
        parse_form4(raw)


def test_escaped_markup_in_text_is_not_a_dtd():
    """Ложный отказ дороже отказа: текст обложки не содержит литерала
    «<!», он экранируется, поэтому настоящая сводка с упоминанием DTD
    в тексте продолжает разбираться."""
    raw = (XML_PROLOG + FILING_HEAD
           + b'<note>&lt;!ENTITY &lt;xyz&gt;</note>'
           + b"</ownershipDocument>")
    took, out = _call(raw)
    assert took < LIMIT_SECONDS
    assert isinstance(out, OwnershipFiling), (
        f"обложка без DTD не разобралась: {type(out).__name__} "
        f"{str(out)[:120]}")


def test_recorded_payloads_still_parse():
    """Ни один записанный EDGAR payload не теряется на guard'е:
    ни в файлах корпуса, ни в их текстах DTD нет (замер grep'ом по
    всему tests/data)."""
    files = sorted(_DATA.glob("*.xml"))
    assert files, f"нет записанных payload'ов в {_DATA}"
    for path in files:
        filing = parse_form4(path.read_bytes())
        assert isinstance(filing, OwnershipFiling), path.name
