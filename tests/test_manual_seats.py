"""TASK-19 F8: контракты ручного импорта (ADR-0011) и полная
реализация verify (③). Таблица verify — не меньше восьми случаев,
включая выдуманное число, подправленную цитату, верное число не на
своей странице и число в другой записи формата. Всё детерминировано:
ни сети, ни модели, ни SQL.
"""
from __future__ import annotations

import pytest

from rusterm.manual import Document, Page, Record, extract_text, verify
from rusterm.providers.base import ProviderError

_SHA = "ab" * 32


def _doc(*pages: tuple[int, str]) -> Document:
    return Document(sha256=_SHA, filename="annual.txt", format="txt",
                    pages=tuple(Page(p, t) for p, t in pages),
                    byte_len=1000)


PAGE_1 = ("The fleet comprised 42 ships at the end of 2025, "
          "revenue reached 1 234 million, margin 3,14 percent.")
PAGE_2 = ("Operating costs totalled 142 million; the fleet "
          "consumed 7.5 tonnes of fuel daily.")


def _record(**over) -> Record:
    base = dict(company="Fleet Co", category="physical",
                metric="fleet_size", value="42", unit="ships",
                period="FY2025",
                quote="The fleet comprised 42 ships",
                page_no=1)
    base.update(over)
    return Record(**base)


@pytest.mark.parametrize(
    "record,document,expected,case",
    [
        # 1. ок: цитата дословно на своей странице, число в цитате
        (_record(), _doc((1, PAGE_1), (2, PAGE_2)), True, "ok"),
        # 2. выдуманное число: цитата есть, числа значения в ней нет
        (_record(value="99"),
         _doc((1, PAGE_1)), False, "fabricated number"),
        # 3. подправленная цитата: такой строки на странице нет
        (_record(quote="The fleet comprised 40 ships"),
         _doc((1, PAGE_1)), False, "altered quote"),
        # 4. верное число не на своей странице (страница 2)
        (_record(page_no=2),
         _doc((1, PAGE_1), (2, PAGE_2)), False, "wrong page"),
        # 5. другая запись формата: 1234 против «1 234» (триады)
        (_record(value="1234", metric="revenue",
                 quote="revenue reached 1 234 million"),
         _doc((1, PAGE_1)), True, "thousands separator in quote"),
        # 6. другая запись формата числа: значение «3.14», в дословной
        # цитате «3,14»; цитата при этом неискажённа (дословна на
        # странице), меняется только запись числа значения
        (_record(value="3.14", metric="margin",
                 quote="margin 3,14 percent"),
         _doc((1, PAGE_1)), True, "decimal dot in value vs comma in quote"),
        # 7. числа нет в цитате-подстроке: «142» не содержит «42»
        (_record(quote="Operating costs totalled 142 million",
                 page_no=2),
         _doc((1, PAGE_1), (2, PAGE_2)), False,
         "number inside longer number"),
        # 8. страницы нет в документе вовсе
        (_record(page_no=9), _doc((1, PAGE_1)), False, "page absent"),
        # 9. пустая цитата: до контроля такие не доезжают, а если
        # доехали — False
        (_record(quote=""), _doc((1, PAGE_1)), False, "empty quote"),
        # 10. значение без числа
        (_record(value="n/a"),
         _doc((1, PAGE_1)), False, "value without numerals"),
    ],
)
def test_verify_table(record, document, expected, case):
    assert verify(record, document) is expected, case


def test_verify_is_string_law_not_rounding():
    """Тот же закон, что у цитат-сторожа: «42» и «42.0» — разные
    записи числа, сравнение строковое без допусков."""
    doc = _doc((1, "exactly 42.0 units reported"))
    assert verify(_record(quote="exactly 42.0 units"), doc) is False
    assert verify(_record(value="42.0",
                          quote="exactly 42.0 units"), doc) is True


def test_extract_text_seat_refuses_every_format_as_value(tmp_path):
    """① — место: до полосы L5 место отвечает format_unsupported
    значением на любой вход, не исключением и не молчанием."""
    path = tmp_path / "report.txt"
    path.write_text("обычный текст", encoding="utf-8")
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason.startswith("format_unsupported")
