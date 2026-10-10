"""ТЗ-92 C4: форма ручного факта — метрика, значение и единица становятся
парой «канонический концепт + число в деньгах».

Конвейер (pipeline) вызывает это на уже проверенной записи (③ verified);
здесь ни сети, ни SQL (проверки 7 и 8), только правила разбора:

- каноническое имя — из `MANUAL_METRIC_MAP` (нормализация: строчные,
  подчёркивания → пробелы); всё остальное остаётся NULL;
- значение: триадные разделители убираются тем же каноническим правилом,
  что у контроля цитат (`_canon_number` — единая копия правила), затем
  масштаб из единицы;
- масштаб: thousand|k|'000 → 1e3, million|m|mn → 1e6, billion|bn → 1e9;
- валюта: ISO-код в единице, иначе валюта эмитента, если она не XXX
  (ТЗ-92 C2), иначе None. Если валюта известна, в колонку unit ложится
  её ISO-код — иначе дверца «у всех потоков меры одна unit»
  (core/snapshot.py) не пустит ручную строку в пару к машинной;
- единица-ставка («USD/day», «$ per share») и единица вне правил —
  факт с canonical_concept NULL и значением дословно, как сегодня:
  годовые деньги из ставки в сутки были бы числом в 365 раз меньше,
  а это хуже неотображённой строки.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..normalize.concepts import MANUAL_MAP_VERSION, canonical_for_manual
from . import _canon_number

# масштаб по токену единицы; '000 и 000 — одна и та же запись тысяч
_SCALE: dict[str, float] = {
    "thousand": 1_000.0, "th": 1_000.0, "k": 1_000.0, "000": 1_000.0,
    "million": 1_000_000.0, "mn": 1_000_000.0, "mm": 1_000_000.0,
    "m": 1_000_000.0,
    "billion": 1_000_000_000.0, "bn": 1_000_000_000.0,
}
_SYMBOLS = "$€£₽¥₴₹"
_ISO_RE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class Shape:
    """Итог разбора одной записи: что класть в колонки факта."""
    canonical: str | None
    map_version: str | None
    value: str
    unit: str
    currency: str | None
    reason: str | None


def unit_shape(unit: str) -> tuple[float | None, str | None, str | None]:
    """(масштаб, ISO-валюта, причина отказа) для единицы записи.

    Отказ — не «не понял молча», а названная причина: rate_unit для
    ставки, unknown_unit:<токен> для слова, которого нет в правилах,
    empty_unit для пустой строки. Каждый токен обязан быть понятен:
    «thousand shares» — тысячи чего? Не деньги, и карта этого не знает."""
    text = (unit or "").strip()
    if not text:
        return None, None, "empty_unit"
    if "/" in text or " per " in text.lower():
        return None, None, "rate_unit"
    iso: str | None = None
    scale: float | None = None
    for raw in text.replace(",", " ").split():
        token = raw.strip("'’\"`().")
        if not token:
            continue
        if _ISO_RE.match(token):
            iso = iso or token
            continue
        bare = token.strip(_SYMBOLS)
        key = bare.lower()
        if key in _SCALE:
            scale = _SCALE[key]
            continue
        if not bare:
            continue                    # голый знак валюты: денег называет,
                                        # масштаб не задаёт
        return None, None, f"unknown_unit:{key}"
    if scale is None and iso is None:
        return None, None, "unknown_unit"
    return (1.0 if scale is None else scale), iso, None


def shape_record(record, issuer_currency: str | None = None) -> Shape:
    """Разобрать запись в форму факта. `issuer_currency` —
    `issuer.reporting_currency` (C2); XXX означает «валюты нет»."""
    canonical = canonical_for_manual(record.metric)
    if canonical is None:
        return Shape(None, None, record.value, record.unit, None,
                     "unmapped_metric")
    scale, iso, unit_reason = unit_shape(record.unit)
    number = _canon_number(record.value)
    if number is None:
        return Shape(None, None, record.value, record.unit, None,
                     "unparsed_value")
    if unit_reason:
        return Shape(None, None, record.value, record.unit, None,
                     unit_reason)
    currency = iso or (issuer_currency
                       if issuer_currency not in (None, "", "XXX")
                       else None)
    try:
        scaled = float(number) * float(scale)
    except (TypeError, ValueError):
        return Shape(None, None, record.value, record.unit, None,
                     "unparsed_value")
    return Shape(canonical, MANUAL_MAP_VERSION, repr(scaled),
                 currency or record.unit, currency, None)


__all__ = ["Shape", "shape_record", "unit_shape"]
