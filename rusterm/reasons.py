"""Разрешённый словарь null_reason для мер (B15) — единственное место,
где он определён. Производители причин (formulas.py, core/snapshot.py,
покрытие) пишут только эти строки; запись меры с причиной вне словаря
отклоняется сторожем в SnapshotRepo — тем же стилем, что инвариант I4.
formulas.NullReason — типизированное подмножество для сигнатур.
missing_data может нести продолжение с именами концептов (X3):
словарь сравнивает первый токен до ':'.
"""
from __future__ import annotations

NULL_REASONS: frozenset[str] = frozenset({
    "missing_data",          # входа нет: концепт не раскрывается или тег мёртв (Y2)
    "period_mismatch",       # годные входы есть, общего периода нет
    "missing_prior_period",  # двухпериодные: нет предыдущего периода стока
    "concept_not_mapped",    # формула §3 вне карты: строка видна, числа нет
    "denominator_zero",      # знаменатель формулы равен нулю
    "negative_denominator",  # отрицательный знаменатель — доля не имеет смысла
    "jurisdiction_rate",     # ставка налога вне допустимой юрисдикционной полосы
    "peer_set_too_small",    # вкладчиков меньше AGGREGATE_MIN_PEERS (I6, TASK-17 E1)
    "no_sec_filings",        # эмитент не подаёт XBRL в SEC (404; TASK-18 G5)
    # TASK-19 F2: причины рынков вне EDGAR и ручного импорта
    "manual_import_required",  # эмитент на рынке есть, раскрытия машинно недоступны (ADR-0010 §3)
    "manual_unverified",     # факт из ручного импорта не прошёл детерминированный контроль (ADR-0011 ③)
    "format_unsupported",    # формат файла требует библиотеки, которой нет в окружении
    "no_text_layer",         # скан без текстового слоя; OCR в проекте нет
    "unknown_issuer",        # рынок не знает этого идентификатора
    "source_unreachable",    # хост провайдера отказал или не ответил (403/429/timeout)
})


def is_known_reason(reason: str | None) -> bool:
    """True — причина в словаре (или None); 'missing_data: a, b'
    сравнивается первым токеном (X3)."""
    if reason is None:
        return True
    return reason.split(":", 1)[0] in NULL_REASONS
