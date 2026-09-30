"""Реестр рынков (TASK-18 G1; TASK-19 F1): рынок — строка таблицы, а не
литерал, размазанный по коду. `--market` валидируется здесь; дефолты
кода берут рынок отсюда.

Как добавить следующий рынок: одна строка в MARKETS ниже, провайдер,
который отвечает на её код, и свой записанный payload для тестов.
Никаких правок логики — реестр для того и существует. Строка обязана
иметь пару в трёх таблицах идентификатора (ТЗ-92 C2):
`IDENTIFIER_PREFIXES`, `IDENTIFIER_SCHEMES` и `REPORTING_CURRENCIES`;
отсутствующая пара падает громко, а не угадывается.

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

# Канал сбора CLI (ТЗ-56 Z2): у какого провайдера есть дверь
# `rusterm ingest --source <имя>`. Модуль провайдера без двери — «место
# построено и не вызывается» (ТЗ-20): реестр называет это прямо, а не
# provider_status=implemented при мёртвом канале. Отсутствия названы:
PROVIDER_CHANNELS: dict[str, str | None] = {
    "edgar": "edgar",   # companyfacts: US/CA/OTC
    "cvm": "cvm",       # годовые наборы DFP: BR (ТЗ-56 Z2)
    "dart": None,       # без ключа провайдер не строится (ТЗ-21 H8)
    "asx": "asx",       # анонсы эмитента: AU (ТЗ-57 A4); тела PDF
                        # машинно недостижимы (ADR-0010 §5) — каждая
                        # подача называется, manual import
}


def provider_channel(provider: str) -> str | None:
    """Имя --source для `rusterm ingest`, если канал есть; None —
    провайдер построить можно, собрать им нельзя ничего."""
    return PROVIDER_CHANNELS.get(provider)


def channel_degree_label(provider: str, produced: str | None,
                         key_env: str | None, key_present: bool) -> str:
    """Степень канала для показа (ТЗ-61 F4): прежде всего то, что
    канал произвёл (E4); канал, которого нет без ключа, а ключа нет —
    честное «нет ключа», не обещание мер; нечего и ключ есть — «—».
    key_env/key_present подставляет вызывающий (providers.channel_key_env
    и окружение после load_env) — подстановка проверяется тестом."""
    if produced and produced != "—":
        return produced
    if provider_channel(provider) is None and key_env and not key_present:
        return "нет ключа"
    return "—"


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


# ── ТЗ-92 C2: идентификатор эмитента принадлежит своему рынку ──────────
# Префикс `issuer_id` — часть схемы, а не украшение. До C2 `cmd_add`
# писал `cik-` всем рынкам, а `CD_CVM` и корейский `corp_code` — тоже
# цифры: `refresh` по смешанному списку запрашивал у SEC CIK = <код CVM>
# и клал чужие факты под этот id. Ключ таблицы — `Market.identifier`.
IDENTIFIER_PREFIXES: dict[str, str] = {
    "cik": "cik-",
    "cvm_code": "cvm-",
    "corp_code": "dart-",
    "asx_code": "asx-",
}

# Схема идентификатора по его `Market.identifier` (ТЗ-92 C2):
# `digits` — только цифры, `digits8` — ровно 8 цифр (corp_code DART:
# ведущие нули значащие, приведение к int превращало `00126380` в
# `126380`), `token` — непустая метка без пробелов (у ASX код буквенный:
# `CBA`, и требовать от него цифр — значит выдумывать схему).
IDENTIFIER_SCHEMES: dict[str, str] = {
    "cik": "digits",
    "cvm_code": "digits",
    "corp_code": "digits8",
    "asx_code": "token",
}

PROVIDER_PREFIXES: dict[str, str] = {}
for _market in MARKETS:
    # у одного провайдера все рынки делят identifier (US/CA/OTC — CIK);
    # первое значение и есть префикс канала
    PROVIDER_PREFIXES.setdefault(_market.provider,
                                 IDENTIFIER_PREFIXES[_market.identifier])

# Валюта отчётности рынка. `XXX` — ISO 4217 «валюты нет»: колонка
# `issuer.reporting_currency` NOT NULL, а валюту канадского или OTC-
# эмитента по площадке программа угадывает — ТЗ-92 C2 прямо это
# запрещает, поэтому честное «не знаю» вместо выдуманной строки.
# Это валюта ОТЧЁТОВ, не площадки: торговую валюту листинга таблица не
# описывает.
REPORTING_CURRENCIES: dict[str, str] = {
    "US": "USD",
    "CA": "XXX",
    "OTC": "XXX",
    "KR": "KRW",
    "BR": "BRL",
    "AU": "AUD",
}


def registry_prefix(market: Market) -> str:
    """Префикс `issuer_id` рынка. KeyError — рынок добавлен в реестр без
    строки `IDENTIFIER_PREFIXES`: угадать префикс безопаснее, чем
    молча написать чужой."""
    return IDENTIFIER_PREFIXES[market.identifier]


def provider_prefix(provider: str) -> str | None:
    """Префикс идентификатора, которым провайдер адресует эмитента;
    None — такого провайдера в реестре рынков нет (у котировок свой
    ключ, и сравнивать его с префиксом эмитента не за чем)."""
    return PROVIDER_PREFIXES.get(provider)


_PREFIX_OWNERS: dict[str, str] = {prefix: name
                                  for name, prefix in
                                  PROVIDER_PREFIXES.items()}


def registry_prefix_owner(issuer_id: str | None) -> str | None:
    """Провайдер, которому принадлежит префикс `issuer_id`; None —
    префикса нет в реестре. Строки вида `issuer-cli-demo` или `i1`
    идентификатора рынка не несут: это не «чужой рынок», а «рыночного
    идентификатора нет» — и отказывать им должен прежний путь, а не
    новый."""
    text = issuer_id or ""
    for prefix in sorted(_PREFIX_OWNERS, key=len, reverse=True):
        if text.startswith(prefix):
            return _PREFIX_OWNERS[prefix]
    return None


def reporting_currency(code: str) -> str | None:
    """Валюта отчётности рынка по коду; None — рынка нет в таблице."""
    return REPORTING_CURRENCIES.get((code or "").upper())


def registry_id_error(market: Market, raw: str | None) -> str | None:
    """None — идентификатор проходит схему рынка, иначе — что не так,
    одной фразой (её печатает CLI, а не молча чинит)."""
    scheme = IDENTIFIER_SCHEMES[market.identifier]
    text = (raw or "").strip()
    if not text:
        return f"{market.identifier} пуст"
    if scheme == "token":
        if any(ch.isspace() for ch in text):
            return f"{market.identifier} не может содержать пробелы"
        return None
    if not text.isascii() or not text.isdigit():
        return f"{market.identifier} обязан состоять только из цифр"
    if scheme == "digits8" and len(text) != 8:
        return f"{market.identifier} обязан быть ровно 8 цифр"
    return None

