"""ТЗ-27 N4: near_miss получает свою причину manual_near_miss;
failed остаётся manual_unverified; оба не попадают в меры.
"""
from __future__ import annotations

from rusterm.manual import (FAILED, NEAR_MISS, VERIFIED, Document, Page,
                            Record, verify_status)
from rusterm.reasons import is_known_reason


def _doc() -> Document:
    return Document(sha256="ab" * 32, filename="r.pdf", format="pdf",
                    pages=(Page(1, "revenue reached 1234 per the table"),),
                    byte_len=100)


def test_manual_near_miss_in_reason_dictionary():
    from rusterm.reasons import NULL_REASONS
    assert "manual_near_miss" in NULL_REASONS
    assert is_known_reason("manual_near_miss")
    assert is_known_reason("manual_unverified")


def test_near_miss_and_failed_are_distinguishable():
    good = Record(company="C", category="financial", metric="revenue",
                  value="1234", unit="USD", period="FY2024",
                  quote="revenue reached 1234", page_no=1)
    bad = Record(company="C", category="financial", metric="revenue",
                 value="9999", unit="USD", period="FY2024",
                 quote="unrelated text", page_no=1)
    assert verify_status(good, _doc()) == VERIFIED
    assert verify_status(good, _doc()) != NEAR_MISS
    # значение «1.234» при цитате «1234»: строгий канон не узнал,
    # свободная запись (только цифры) узнала — near_miss
    loose = Record(company="C", category="financial", metric="revenue",
                   value="1.234", unit="USD", period="FY2024",
                   quote="revenue reached 1234", page_no=1)
    # число в другой записи формата: near_miss, а не failed
    status = verify_status(loose, _doc())
    assert status in (NEAR_MISS, VERIFIED)
    assert verify_status(bad, _doc()) == FAILED
    # оба исхода не verified — в меры не попадают (pipeline: verified=0)
    assert verify_status(loose, _doc()) != VERIFIED
    assert verify_status(bad, _doc()) != VERIFIED
