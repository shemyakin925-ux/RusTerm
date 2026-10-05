"""Словарь причин словами (ТЗ-111 U1): токен null_reason → короткая
русская фраза для ячеек и подписей окна. Сырой токен при этом живёт в
подсказке ячейки и панели источника — пользователь видит слова, а
проверяемый машиной код остаётся в одном экземпляре (словарь причин —
rusterm/reasons.py, этот файл только переводит его на человеческий).

Каждый токен из NULL_REASONS обязан иметь фразу — страж в
tests/test_task111_reasons_ru.py сверяет множества.
"""
from __future__ import annotations

REASONS_RU: dict[str, str] = {
    "missing_data": "нет данных за период",
    "period_mismatch": "нет общего периода у входов",
    "missing_prior_period": "нет предыдущего периода для расчёта",
    "concept_not_mapped": "показатель не собирается из этой отчётности",
    "denominator_zero": "знаменатель равен нулю",
    "negative_denominator": "отрицательный знаменатель — доля не имеет смысла",
    "jurisdiction_rate": "ставка налога вне допустимой полосы",
    "peer_set_too_small": "слишком мало компаний в группе",
    "peer_set_not_confirmed": "группа компаний не подтверждена",
    "no_sec_filings": "компания не подаёт отчётность в SEC",
    "manual_import_required": "отчётность добавляется вручную",
    "manual_unverified": "ручная выписка не прошла проверку",
    "format_unsupported": "формат файла не поддерживается",
    "no_text_layer": "документ — скан без текстового слоя",
    "unknown_issuer": "компания не найдена в источнике",
    "source_unreachable": "источник данных недоступен",
    "currency_mismatch": "разные валюты в одном расчёте",
    "manual_near_miss": "ручная выписка близка к оригиналу, нужна проверка",
    "stale_data": "данные устарели",
    "non_finite": "в отчёте повреждённое число",
    "stale_input": "вход расчёта старше срока годности",
    "not_applicable": "не применимо к этой компании",
}


def reason_token(reason: str | None) -> str:
    """Первый токен причины до ':' или ';' — тот же разбор, что у
    is_known_reason, плюс продолжения через ';' (ТЗ-110 B1)."""
    if not reason:
        return ""
    for chunk in (reason or "").split(":"):
        token = chunk.split(";", 1)[0].strip()
        if token:
            return token
    return ""


def reason_phrase(reason: str | None) -> str:
    """Фраза для ячейки: словарная — по первому токену; токена нет в
    словаре — причина возвращается как есть (честность дороже словаря)."""
    token = reason_token(reason)
    return REASONS_RU.get(token, reason or "")
