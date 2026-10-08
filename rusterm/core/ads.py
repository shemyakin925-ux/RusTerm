"""Коэффициент депозитарной расписки (ТЗ-138 A2): «одна ADS = N акций».

Цена на американской бирже у иностранного эмитента — за расписку, а
число акций в отчётности — обыкновенных. Без коэффициента капитализация
завышена в N раз (AMX ×20, BHP ×2 — сверка с Yahoo 08.10). Коэффициент —
факт с источником: фраза с обложки или из раздела 12 формы 20-F,
цитата уходит в locator факта. Ядро без сети: разбор готового текста.
"""
from __future__ import annotations

import html
import re
from typing import Optional

CONCEPT = "rusterm:AdsRatio"
CANONICAL = "ads_ratio"
PARSER_VERSION = "ads.v1"

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "twenty-five": 25,
    "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100,
    "one hundred": 100,
}
_NUMBER = r"(\d+(?:\.\d+)?|" + "|".join(
    sorted((re.escape(w) for w in _WORDS), key=len, reverse=True)) + r")"
_ADS = r"(?:American\s+Depositary\s+Shares?|ADSs?|ADRs?)"
# «ADSs, each representing 20 Series B shares», «each ADS represents two
# ordinary shares», «each American Depositary Share representing one share»
_PATTERNS = (
    re.compile(_ADS + r"[^.;]{0,160}?\beach\s+(?:representing|represents|"
               r"representative\s+of)\s+" + _NUMBER + r"\b", re.I),
    re.compile(r"\beach\s+" + _ADS + r"\s+(?:representing|represents)\s+"
               + _NUMBER + r"\b", re.I),
)


def plain_text(document: bytes) -> str:
    """HTML 20-F → плоский текст: теги вон, сущности раскрыты, пробелы
    схлопнуты (между словами в iXBRL бывают &#160; и переносы)."""
    text = document.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text)


def parse_ads_ratio(document: bytes) -> Optional[tuple[float, str]]:
    """(N, цитата) — сколько акций в одной расписке, или None.

    Берётся первое совпадение (обложка идёт первой). Число словом или
    цифрой; ноль и абсурд (> 1000) не принимаются — это не коэффициент."""
    text = plain_text(document)
    for pattern in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        token = match.group(1).lower()
        try:
            ratio = float(token)
        except ValueError:
            ratio = float(_WORDS.get(token, 0))
        if 0 < ratio <= 1000:
            start = max(match.start() - 40, 0)
            return ratio, text[start:match.end() + 40].strip()
    return None
