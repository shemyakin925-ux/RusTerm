"""Ступень ② ручного импорта: страницы -> записи-кандидаты (ADR-0011,
ТЗ-20 L6). Модель — ровно по API (rusterm/providers/llm_api.py); эта
модуль сети не касается — клиент приходит снаружи.

Категории ровно financial | physical | other (ADR-0011 ②). Каждая
запись несёт ДОСЛОВНУЮ цитату и номер страницы; запись без цитаты
отбрасывается целиком (и это считается), с чужой категорией — тоже.
Разбор ответа модели — значение, не исключение: битый JSON — отказ
parse_failed значением.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..providers.base import ProviderError
from . import Record

PROMPT_VERSION = "records.v1"
CATEGORIES = ("financial", "physical", "other")

_PROMPT_HEAD = """You extract numeric records from a company document.
Return ONLY a JSON array, no prose. Each item has exactly these keys:
{"company": string, "category": "financial"|"physical"|"other",
 "metric": string, "value": string, "unit": string, "period": string,
 "quote": string, "page_no": integer}
Rules:
- "quote" MUST be copied VERBATIM from the page text (a sentence that
  contains the number);
- "value" is the number exactly as written on the page;
- never invent a number that is not on the page;
- category "financial" = accounting figures, "physical" = operating
  volumes (tonnes, vessels, capacities), "other" = corporate events.
DOCUMENT PAGES:
"""


@dataclass(frozen=True)
class ParsedRecords:
    records: tuple[Record, ...]
    dropped_no_quote: int
    dropped_bad_category: int
    dropped_bad_shape: int


def build_prompt(pages) -> str:
    """Промпт ②: страницы с номерами, требование дословной цитаты."""
    parts = [_PROMPT_HEAD]
    for page in pages:
        parts.append(f"[page {page.page_no}]\n{page.text}\n")
    return "\n".join(parts)


def parse_records(raw: str) -> ParsedRecords | ProviderError:
    """Разобрать ответ модели. Битый/нечестный JSON — ProviderError
    значением; записи с пустой цитатой или чужой категорией —
    отбрасываются со счётчиком (не молча)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except ValueError:
        return ProviderError(reason="parse_failed:not_json")
    if not isinstance(data, list):
        return ProviderError(reason="parse_failed:not_a_list")
    records: list[Record] = []
    dropped_no_quote = dropped_bad = dropped_shape = 0
    for item in data:
        if not isinstance(item, dict):
            dropped_shape += 1
            continue
        keys = ("company", "category", "metric", "value", "unit",
                "period", "quote", "page_no")
        if any(not item.get(k) for k in keys):
            dropped_shape += 1
            continue
        quote = str(item["quote"])
        if not quote.strip():
            dropped_no_quote += 1
            continue
        category = str(item["category"])
        if category not in CATEGORIES:
            dropped_bad += 1
            continue
        try:
            page_no = int(item["page_no"])
        except (TypeError, ValueError):
            dropped_shape += 1
            continue
        records.append(Record(
            company=str(item["company"]),
            category=category,
            metric=str(item["metric"]),
            value=str(item["value"]),
            unit=str(item["unit"]),
            period=str(item["period"]),
            quote=quote,
            page_no=page_no,
        ))
    return ParsedRecords(records=tuple(records),
                         dropped_no_quote=dropped_no_quote,
                         dropped_bad_category=dropped_bad,
                         dropped_bad_shape=dropped_shape)


def period_bounds(period: str) -> tuple[str, str, str]:
    """Детерминированное отображение периода записи на границы факта:
    'FY2025' -> (2025-01-01, 2025-12-31, duration); дата -> та же дата,
    instant; что-то иное -> строка в оба поля, instant."""
    text = (period or "").strip()
    if len(text) == 4 and text.isdigit():
        return f"{text}-01-01", f"{text}-12-31", "duration"
    if text.startswith(("FY", "fy")) and text[2:].strip().isdigit():
        year = text[2:].strip()
        return f"{year}-01-01", f"{year}-12-31", "duration"
    import datetime as _dt
    try:
        _dt.date.fromisoformat(text)
        return text, text, "instant"
    except ValueError:
        return text or "unknown", text or "unknown", "instant"


__all__ = ["build_prompt", "parse_records", "period_bounds",
           "PROMPT_VERSION", "CATEGORIES", "ParsedRecords"]
