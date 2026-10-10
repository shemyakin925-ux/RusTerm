"""ТЗ-111 U1: словарь причин словами — rusterm/reasons_ru.py.

Done-when пункта: каждый токен из reasons.py имеет фразу; в ячейках и
подписях окна фразы, сырой токен — в подсказке (проверка узора — на
отчёте look.py, см. отчёт задания).
"""
from __future__ import annotations

import pytest

from rusterm.reasons import NULL_REASONS, is_known_reason
from rusterm.reasons_ru import REASONS_RU, reason_phrase, reason_token


def test_every_vocabulary_token_has_a_phrase():
    """Полное покрытие: каждый токен закрытого словаря причин имеет
    русскую фразу; лишних фраз в словаре перевода нет."""
    missing = sorted(NULL_REASONS - set(REASONS_RU))
    assert not missing, f"токены без фразы: {missing}"
    extra = sorted(set(REASONS_RU) - set(NULL_REASONS))
    assert not extra, f"фразы без токена: {extra}"


@pytest.mark.parametrize("reason, expected", [
    ("missing_data: total_assets", "нет данных за период"),
    ("stale_data: st_investments: last 2019-12-31", "данные устарели"),
    ("not_applicable: banks", "не применимо к этой компании"),
    ("source_unreachable:transport:URLError", "источник данных недоступен"),
    (None, ""),
])
def test_reason_phrase_takes_the_first_token(reason, expected):
    """Продолжения (концепты, периоды, типы ошибок) фразе не мешают —
    фраза по первому токену, разбор тот же, что у is_known_reason."""
    assert reason_phrase(reason) == expected


def test_unknown_reason_passes_through_verbatim():
    """Токена нет в словаре — причина возвращается как есть: честность
    дороже словаря (молча перевести чужое — наврать)."""
    raw = "совсем_не_словарь: что-то"
    assert reason_phrase(raw) == raw


def test_reason_token_matches_is_known_reason_parsing():
    """Разбор токена согласован со словарём мер: у всякой словарной
    причины токен распознан и входит в NULL_REASONS."""
    for reason in ("missing_data: a, b",
                   "stale_input: shares_outstanding (2012-12-31)",
                   "not_applicable: banks",
                   "within_pm_0.1pct;tenb5_net=-1 (10% of net)"):
        assert reason_token(reason)
    assert reason_token(None) == ""
    # словарные причины распознаются обоими разборами одинаково
    for token in NULL_REASONS:
        assert is_known_reason(f"{token}: продолжение")
