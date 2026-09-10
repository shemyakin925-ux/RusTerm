"""Реестр рынков (TASK-18 G1; TASK-19 F1): рынок — строка таблицы, а не
литерал, размазанный по коду. `--market` валидируется здесь; дефолты
кода берут рынок отсюда.

Как добавить следующий рынок: одна строка в MARKETS ниже, провайдер,
который отвечает на её код, и свой записанный payload для тестов.
Никаких правок логики — реестр для того и существует.

`default_taxonomy` — advisory only: чего ждать от рынка. Применяет
таксономию payload, а не эта строка (TASK-18 §0.3 ruling 2).

`access` — уровень доступности раскрытий (ADR-0010 §2): auto — рынок
скачивается целиком; partial — программа обязана различать эмитентов
до создания (см. can_auto_ingest, ADR-0010 §3); manual — только ручной
импорт (ADR-0011). Строк с manual сейчас нет.

Юрисдикция и площадка (решение координатора, TASK-19 §0.1):
**юрисдикция следует за эмитентом, площадка — за тем, где торгуется.**
Канадский эмитент на NYSE — рынок CA, площадка NYSE.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str                    # что принимает --market
    jurisdiction: str            # юрисдикция эмитента по умолчанию
    venue_kind: str              # exchange | otc
    provider: str                # имя провайдера, отвечающего за рынок
    identifier: str              # схема идентификатора эмитента
    default_taxonomy: str        # advisory: см. ruling 2
    access: str                  # auto | partial | manual (ADR-0010 §2)


MARKETS: tuple[Market, ...] = (
    Market(code="US", jurisdiction="US", venue_kind="exchange",
           provider="edgar", identifier="cik", default_taxonomy="us-gaap",
           access="auto"),
    Market(code="CA", jurisdiction="CA", venue_kind="exchange",
           provider="edgar", identifier="cik", default_taxonomy="ifrs-full",
           access="auto"),
    Market(code="OTC", jurisdiction="US", venue_kind="otc",
           provider="edgar", identifier="cik", default_taxonomy="us-gaap",
           access="partial"),
    # KR/BR/AU — провайдеров ещё нет (TASK-19 F1 сажает места, TASK-20
    # строит модули); имена провайдеров намеренно не резолвятся.
    Market(code="KR", jurisdiction="KR", venue_kind="exchange",
           provider="dart", identifier="corp_code",
           default_taxonomy="ifrs-full", access="auto"),
    Market(code="BR", jurisdiction="BR", venue_kind="exchange",
           provider="cvm", identifier="cvm_code",
           default_taxonomy="ifrs-full", access="auto"),
    Market(code="AU", jurisdiction="AU", venue_kind="exchange",
           provider="asx", identifier="asx_code",
           default_taxonomy="ifrs-full", access="partial"),
)

MARKET_CODES: tuple[str, ...] = tuple(m.code for m in MARKETS)
DEFAULT_MARKET: str = MARKET_CODES[0]

_KNOWN: dict[str, Market] = {m.code: m for m in MARKETS}


def get_market(code: str) -> Market | None:
    """Рынок по коду; None — код вне реестра (для --market это ошибка
    с перечнем известных кодов, а не молчаливое создание эмитента с
    чужой юрисдикцией)."""
    return _KNOWN.get((code or "").upper())


def known_codes() -> str:
    """Известные коды одной строкой — для сообщения об ошибке."""
    return ", ".join(MARKET_CODES)

# Площадки по рынку (замер координатора для US: Nasdaq 4363, NYSE 3298,
# OTC 2500, CBOE 36). Биржевой рынок держит свои префиксы площадок;
# OTC — собственную. unknown площадке противоречит любому рынку.
# US/CA торгуются на биржах US (решение §0.1: CA-эмитент на NYSE —
# рынок CA, площадка NYSE); площадки KR/BR/AU — из замеров
# REPORT-MARKETS (KRX/KOSPI/KOSDAQ, B3/BVMF, ASX).
_VENUE_PREFIXES: dict[str, tuple[str, ...]] = {
    "US": ("NYSE", "NASDAQ", "CBOE"),
    "CA": ("NYSE", "NASDAQ", "CBOE"),
    "KR": ("KRX", "KOSPI", "KOSDAQ"),
    "BR": ("B3", "BVMF"),
    "AU": ("ASX",),
}


def venue_in_market(venue: str, code: str) -> bool:
    """Лежит ли площадка на рынке. unknown/'': не противоречит никому —
    площадка не была измерена (TASK-18 G2), и это не повод отбрасывать
    участника. Равенство строке рынка (исторические сиды 'US') — да."""
    m = get_market(code)
    if m is None:
        return False
    v = (venue or "").upper()
    if not v or v == "UNKNOWN" or v == m.code:
        return True
    if m.venue_kind == "otc":
        return "OTC" in v
    return any(prefix in v for prefix in _VENUE_PREFIXES.get(m.code, ()))
