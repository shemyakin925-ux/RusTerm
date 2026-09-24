"""Разбор Form 4 (Ownership XML, SEC EDGAR) — ТЗ-32 D2 (ТЗ-25 P4).

Корень ownershipDocument без namespace: документ типа 3/4/5 несёт
эмитента, инсайдера (роль флагами isDirector/isOfficer/
isTenPercentOwner/isOther) и таблицы сделок. Разбирается
nonDerivativeTable (обычные бумаги); производная таблица — отдельная
работа, её отсутствие названо здесь, а не спрятано. Каждая сделка:
дата, инсайдер, направление (A/D -> acquired/disposed), объём, цена
если вендор дал. Чистая функция над байтами — золотой тест гоняет её
по записанному payload офлайн.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

DIRECTION_BY_CODE = {"A": "acquired", "D": "disposed"}

_ROLE_FLAGS = (("isDirector", "director"),
               ("isOfficer", "officer"),
               ("isTenPercentOwner", "ten_percent_owner"),
               ("isOther", "other"))

_DTD = re.compile(rb"<!DOCTYPE|<!ENTITY", re.IGNORECASE)


def _refuse_dtd(raw: bytes) -> None:
    """ТЗ-83 F2: обложка Form 4 — всегда <ownershipDocument> без DTD. В
    записанном корпусе (tests/data/edgar/ownership, и grep по всему
    tests/data) нет ни DOCTYPE, ни CDATA, поэтому объявленная сущность —
    не «странный, но разборный» вход, а признак атаки: разрастание
    (billion laughs) либо чтение файла с машины (внешняя сущность).
    Отказываем по байтам ДО парсера: на этой машине expat 2.8.1
    останавливает разрастание сам (замер: 0.115s, «limit on input
    amplification factor breached»), но на libexpat < 2.6 того потолка
    нет, и контракт «ValueError за 2s» держался бы на версии библиотеки
    хоста. Ищем по всему буферу, а не в прологе: срез пролога обходится
    комментарием («<!-- <x> --> <!DOCTYPE ...>», тест Ф2), а в настоящем
    XML-тексте литерала «<!» быть не может — он оттуда экранируется."""
    found = _DTD.search(raw)
    if found is not None:
        raise ValueError(
            f"неразобран XML: в обложке Form 4 объявлена DTD "
            f"({found.group().decode()}) — отказ до разбора")


@dataclass
class OwnershipTransaction:
    """Одна сделка инсайдера из таблицы Form 3/4/5."""
    insider: str
    role: str | None
    officer_title: str | None
    date: str
    direction: str | None
    shares: float | None
    price: float | None
    security: str
    tenb5_one: bool = False
    """Сделка по плану Rule 10b5-1: сноски сделки упоминают план
    (вердикт BACKLOG 11: доля 10b5-1 называется в деталях цвета)."""


@dataclass
class OwnershipFiling:
    """Разобранный документ владения целиком."""
    document_type: str
    period: str
    issuer_cik: str | None
    issuer_name: str | None
    insider_cik: str | None
    insider: str
    role: str | None
    officer_title: str | None
    transactions: list[OwnershipTransaction] = field(default_factory=list)


def _value(node) -> str | None:
    """Текст <value> под узлом; None без узла или без значения."""
    if node is None:
        return None
    text = node.findtext("value")
    if text is None or not text.strip():
        return None
    return text.strip()


def _float(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _relationship(rel_node) -> tuple[str | None, str | None]:
    """Роль по флагам relationship: первый поднятый; титул офицера.
    Поднятый флаг — "1" или "true" (вендор встречает оба вида)."""
    if rel_node is None:
        return None, None
    for flag, role in _ROLE_FLAGS:
        if (rel_node.findtext(flag) or "").strip().lower() in \
                ("1", "true"):
            title = rel_node.findtext("officerTitle")
            return role, (title.strip() if title and title.strip()
                          else None)
    return None, None


def parse_form4(raw: bytes) -> OwnershipFiling:
    """Байты Form 3/4/5 XML -> OwnershipFiling; невалидный XML —
    ValueError наверх (парсер честен: разбор идёт по записанному
    сырью, отказ — значение вызывающему). DTD в обложке отвергается до
    разбора — см. _refuse_dtd."""
    _refuse_dtd(raw)
    try:
        root = ET.fromstring(raw.decode("utf-8", "replace"))
    except ET.ParseError as exc:
        # ТЗ-83 F1: контракт записи — «OwnershipFiling или ValueError».
        # ET.ParseError наследуется от SyntaxError, а не от ValueError,
        # поэтому битый XML проходил мимо обещанного отказа и прилетал
        # вызывающему (замер на b'<', обрубке и utf-16 — tests/data/fuzz).
        raise ValueError(f"неразобран XML: {exc}") from exc
    if root.tag != "ownershipDocument":
        raise ValueError(f"корень {root.tag!r} — не ownershipDocument")

    issuer = root.find("issuer")
    owner = root.find("reportingOwner")
    owner_id = owner.find("reportingOwnerId") if owner is not None else None
    role, officer_title = _relationship(
        owner.find("reportingOwnerRelationship")
        if owner is not None else None)

    filing = OwnershipFiling(
        document_type=root.findtext("documentType") or "",
        period=root.findtext("periodOfReport") or "",
        issuer_cik=issuer.findtext("issuerCik") if issuer is not None
        else None,
        issuer_name=issuer.findtext("issuerName") if issuer is not None
        else None,
        insider_cik=owner_id.findtext("rptOwnerCik")
        if owner_id is not None else None,
        insider=owner_id.findtext("rptOwnerName")
        if owner_id is not None else "",
        role=role,
        officer_title=officer_title,
    )

    footnotes = {node.get("id"): (node.text or "")
                 for node in root.findall("footnotes/footnote")}
    table = root.find("nonDerivativeTable")
    for tx in (table.findall("nonDerivativeTransaction")
               if table is not None else []):
        # объём, цена и направление живут в <transactionAmounts>
        # (замер ТЗ-32 D2 на записанном payload AAPL)
        # сделка по плану 10b5-1: её footnoteId указывает на сноску
        # с упоминанием плана (замер ТЗ-33 E1 на payload AAPL)
        tenb5 = any("10b5-1" in footnotes.get(ref.get("id", ""), "")
                    for ref in tx.findall(".//footnoteId"))
        amounts = tx.find("transactionAmounts")
        direction_code = _value(amounts.find("transactionAcquiredDisposedCode")
                                if amounts is not None else None)
        filing.transactions.append(OwnershipTransaction(
            insider=filing.insider,
            role=filing.role,
            officer_title=filing.officer_title,
            date=_value(tx.find("transactionDate"))
            or filing.period,
            direction=DIRECTION_BY_CODE.get(direction_code or ""),
            shares=_float(_value(amounts.find("transactionShares")
                                 if amounts is not None else None)),
            price=_float(_value(amounts.find("transactionPricePerShare")
                                if amounts is not None else None)),
            security=_value(tx.find("securityTitle")) or "",
            tenb5_one=tenb5,
        ))
    return filing
