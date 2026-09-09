"""Реестр рынков (TASK-18 G1): рынок — строка таблицы, а не литерал,
размазанный по коду. `--market` валидируется здесь; дефолты кода берут
рынок отсюда.

Как добавить четвёртый рынок после MVP: одна строка в MARKETS ниже,
провайдер, который отвечает на её код, и свой записанный payload для
тестов. Никаких правок логики — реестр для того и существует.

`default_taxonomy` — advisory only: чего ждать от рынка. Применяет
таксономию payload, а не эта строка (TASK-18 §0.3 ruling 2).
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


MARKETS: tuple[Market, ...] = (
    Market(code="US", jurisdiction="US", venue_kind="exchange",
           provider="edgar", identifier="cik", default_taxonomy="us-gaap"),
    Market(code="CA", jurisdiction="CA", venue_kind="exchange",
           provider="edgar", identifier="cik", default_taxonomy="ifrs-full"),
    Market(code="OTC", jurisdiction="US", venue_kind="otc",
           provider="edgar", identifier="cik", default_taxonomy="us-gaap"),
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

# Площадки из файла SEC (замер координатора: Nasdaq 4363, NYSE 3298,
# OTC 2500, CBOE 36). Биржевые рынки US/CA держат эти префиксы; OTC —
# собственная площадка. unknown площадке противоречит любому рынку.
_EXCHANGE_VENUES: tuple[str, ...] = ("NYSE", "NASDAQ", "CBOE")


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
    return any(prefix in v for prefix in _EXCHANGE_VENUES)
