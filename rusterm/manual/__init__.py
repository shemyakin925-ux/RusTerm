"""Конвейер ручного импорта: интерфейсы трёх ступеней (ADR-0011,
TASK-19 F8). Реализацию привозят полосы L5 и L6 TASK-20 — они не
должны договариваться между собой в три часа ночи, поэтому контракты
зафиксированы заранее:

    файл ──①──> текст по страницам ──②──> записи ──③──> факты
         детерм.                  модель по API       детерм. контроль

Единственная полная реализация этой ночи — verify (③): контроль
детерминированный, маленький, и обе полосы зависят от его точного
поведения. extract_text — место: полоса L5 привозит реализацию в
rusterm/manual/extract.py (разбор по содержимому файла, не по
расширению), до той ночи место честно отказывает значением —
фальшивого разбора здесь нет.

Границы: HTTP в этом пакете нет (проверка 8), SQL нет (проверка 7),
модели нет — ступень ② живёт в rusterm/providers/llm_api.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..providers.base import ProviderError

_NUMBER_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS_RE = re.compile(r"(\d)[,\u00a0 ](\d{3})(?=\D|$)")


@dataclass(frozen=True)
class Page:
    """Страница документа: номер (с единицы) и текстовый слой."""
    page_no: int
    text: str


@dataclass(frozen=True)
class Document:
    """Импортированный документ: содержимое по страницам + заголовок.
    sha256 — тот же файл, тот же ключ (строка document, миграция 40)."""
    sha256: str
    filename: str
    format: str
    pages: tuple[Page, ...]
    byte_len: int

    def page(self, page_no: int) -> Page | None:
        for p in self.pages:
            if p.page_no == page_no:
                return p
        return None


@dataclass(frozen=True)
class Record:
    """Запись-кандидат ступени ② (ADR-0011): метрика со значением,
    единицей с масштабом, периодом и ДОСЛОВНОЙ цитатой со своей
    страницей. Запись без цитаты до контроля не доезжает."""
    company: str
    category: str      # financial | physical | other (ADR-0011 ②)
    metric: str
    value: str
    unit: str
    period: str
    quote: str
    page_no: int


def extract_text(path) -> Document | ProviderError:
    """Ступень ① (ADR-0011): файл -> Document со страницами и sha256.

    Место (TASK-19 F8): реализацию привозит полоса L5 в
    rusterm/manual/extract.py. До той ночи место отвечает
    format_unsupported ЗНАЧЕНИЕМ на любой вход — формат без реализации
    в проекте, а не молчание и не исключение (§7).
    """
    return ProviderError(
        reason="format_unsupported:manual_extract_not_implemented")


def _merge_thousands(text: str) -> str:
    """Склеить разделители триад во всём тексте до токенизации:
    «1 234» обязан стать «1234» одним числом, а не двумя токенами."""
    t = text.replace("\u00a0", " ")
    while True:
        stripped = _THOUSANDS_RE.sub(r"\1\2", t)
        if stripped == t:
            break
        t = stripped
    return t


def _canon_number(text: str) -> str | None:
    """Канонический вид числа-токена: разделители триад убираются,
    запятая и точка — один десятичный разделитель. Сравнение строковое,
    без округлений и допусков — тот же закон, что у цитат-сторожа
    core/llm (TASK-8 U0): «42» и «42.0» — разные записи числа."""
    t = text.strip().replace("\u00a0", " ")
    if not t:
        return None
    sign = ""
    if t[0] in "+-":
        sign = "-" if t[0] == "-" else ""
        t = t[1:].strip()
    t = _merge_thousands(t).replace(",", ".")
    if not _NUMBER_TOKEN_RE.fullmatch(t):
        return None
    return sign + t


def _quote_numbers(quote: str) -> set[str]:
    """Все числа цитаты в каноническом виде: триады склеиваются во
    всём тексте цитаты, затем текст токенизируется."""
    numbers: set[str] = set()
    for token in _NUMBER_TOKEN_RE.findall(_merge_thousands(quote)):
        canon = _canon_number(token)
        if canon is not None:
            numbers.add(canon)
    return numbers


def verify(record: Record, document: Document) -> bool:
    """Ступень ③ (ADR-0011): детерминированный контроль записи.

    True — обе проверки сошлись:
      1. цитата дословно присутствует на своей странице;
      2. число значения стоит числом среди чисел цитаты (токены,
         канонический вид; «142» не содержит «42»).
    False — что-то не сошлось: запись с False сохраняется и видна, но
    в меры снапшота не попадает (причина manual_unverified).

    Пределы честны (ADR-0011 ③): проверка не доказывает, что модель
    взяла число из правильной колонки правильного периода.
    """
    if not record.quote:
        return False
    page = document.page(record.page_no)
    if page is None or record.quote not in page.text:
        return False
    value = _canon_number(record.value)
    if value is None:
        return False
    return value in _quote_numbers(record.quote)


__all__ = ["Page", "Document", "Record", "extract_text", "verify"]
