"""Модель факта, локаторы, валидация, resolve(locator).

Контракт по ADR-0001, data-model.md, module-contracts.md.
I1: Факт без locator не сохраняется.
I3: basis определяется правилом периода.
I12: resolve(locator) == value.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional, Literal
from uuid import uuid4


# --- Locator kinds ---

@dataclass(frozen=True)
class LocatorXBRL:
    kind: Literal["xbrl"] = "xbrl"
    doc_sha256: str = ""
    fact_id: str = ""
    concept: str = ""
    context_ref: str = ""
    unit_ref: str = ""
    decimals: Optional[str] = None
    taxonomy: str = ""
    schema: str = "xbrl.v1"

@dataclass(frozen=True)
class LocatorTable:
    kind: Literal["table"] = "table"
    doc_sha256: str = ""
    table_index: int = 0
    row: int = 0
    col: int = 0
    header_path: list[str] = field(default_factory=list)
    text_snippet: str = ""
    schema: str = "table.v1"

@dataclass(frozen=True)
class LocatorPDF:
    kind: Literal["pdf"] = "pdf"
    doc_sha256: str = ""
    page: int = 0
    text_snippet: str = ""
    extractor: str = ""
    extractor_version: str = ""
    hint_bbox: Optional[list[int]] = None  # [x0,y0,x1,y1] - только для UI
    schema: str = "pdf.v1"

@dataclass(frozen=True)
class LocatorHTML:
    kind: Literal["html"] = "html"
    doc_sha256: str = ""
    css_selector: Optional[str] = None
    xpath: Optional[str] = None
    char_range: Optional[list[int]] = None  # [start, end]
    text_snippet: str = ""
    schema: str = "html.v1"

@dataclass(frozen=True)
class LocatorAPI:
    kind: Literal["api"] = "api"
    endpoint: str = ""
    request_hash: str = ""
    response_sha256: str = ""
    json_pointer: str = ""
    schema: str = "api.v1"

@dataclass(frozen=True)
class LocatorDerived:
    kind: Literal["derived"] = "derived"
    inputs: list[str] = field(default_factory=list)  # fact_ids
    formula_id: str = ""
    method_version: str = ""
    schema: str = "derived.v1"


Locator = (
    LocatorXBRL | LocatorTable | LocatorPDF |
    LocatorHTML | LocatorAPI | LocatorDerived
)


def locator_to_json(loc: Locator) -> dict:
    """Сериализация локатора в JSON для хранения в БД."""
    return loc.__dict__


def locator_from_json(data: dict) -> Locator:
    """Десериализация локатора из JSON."""
    kind = data.get("kind")
    if kind == "xbrl":
        return LocatorXBRL(**{k: v for k, v in data.items() if k != "kind"})
    elif kind == "table":
        return LocatorTable(**{k: v for k, v in data.items() if k != "kind"})
    elif kind == "pdf":
        return LocatorPDF(**{k: v for k, v in data.items() if k != "kind"})
    elif kind == "html":
        return LocatorHTML(**{k: v for k, v in data.items() if k != "kind"})
    elif kind == "api":
        return LocatorAPI(**{k: v for k, v in data.items() if k != "kind"})
    elif kind == "derived":
        return LocatorDerived(**{k: v for k, v in data.items() if k != "kind"})
    else:
        raise ValueError(f"Unknown locator kind: {kind}")


# --- Fact model ---

Basis = Literal["as_reported", "restated"]
Origin = Literal["extracted", "manual"]
Status = Literal["ok", "suspect"]
PeriodType = Literal["instant", "duration"]


@dataclass
class Fact:
    """Единица истины. Неизменяемая после создания (кроме superseded_by)."""
    fact_id: str = field(default_factory=lambda: str(uuid4()))
    issuer_id: Optional[str] = None
    listing_id: Optional[str] = None
    concept: str = ""
    period_start: str = ""
    period_end: str = ""
    period_type: PeriodType = "duration"
    value: Optional[str] = None
    unit: str = ""
    currency: Optional[str] = None
    basis: Basis = "as_reported"
    origin: Origin = "extracted"
    source_ref: str = ""  # sha256 raw_object
    locator: dict = field(default_factory=dict)  # JSON-сериализованный Locator
    parser_version: str = ""
    status: Status = "ok"
    superseded_by: Optional[str] = None
    ingested_at: float = field(default_factory=lambda: __import__('time').time())

    def __post_init__(self):
        # Валидация
        if not self.locator or not self.locator.get("kind"):
            raise ValueError("locator must have 'kind' field")
        if self.locator.get("kind") == "derived" and not self.locator.get("formula_id"):
            raise ValueError("derived locator must have formula_id")
        # Проверка: ровно один из issuer_id / listing_id
        if (self.issuer_id is None) == (self.listing_id is None):
            raise ValueError("exactly one of issuer_id or listing_id must be set")
        if not self.locator:
            raise ValueError("locator cannot be empty")
        if self.basis not in ("as_reported", "restated"):
            raise ValueError("basis must be as_reported or restated")
        if self.origin not in ("extracted", "manual"):
            raise ValueError("origin must be extracted or manual")
        if self.status not in ("ok", "suspect"):
            raise ValueError("status must be ok or suspect")
        if self.period_type not in ("instant", "duration"):
            raise ValueError("period_type must be instant or duration")

    @property
    def locator_obj(self) -> Locator:
        return locator_from_json(self.locator)

    def to_db_tuple(self) -> tuple:
        """Для INSERT в БД."""
        return (
            self.fact_id,
            self.issuer_id,
            self.listing_id,
            self.concept,
            self.period_start,
            self.period_end,
            self.period_type,
            self.value,
            self.unit,
            self.currency,
            self.basis,
            self.origin,
            self.source_ref,
            json.dumps(self.locator, ensure_ascii=False),
            self.parser_version,
            self.status,
            self.superseded_by,
            self.ingested_at,
        )


def determine_basis(
    doc_period_end: str,
    fact_period_end: str,
    doc_filed_date: str,
) -> Basis:
    """Правило определения basis (ADR-0001, data-dictionary.md).
    
    - as_reported: период документа == период факта
    - restated: документ позже, но содержит сравнительное число за более ранний период
    
    doc_period_end — конец отчётного периода документа (e.g., 2024-12-31 для 10-K за 2024)
    fact_period_end — конец периода факта (e.g., 2023-12-31 для выручки 2023)
    doc_filed_date — дата публикации документа
    """
    if doc_period_end == fact_period_end:
        return "as_reported"
    # Документ позже, но факт относится к более раннему периоду -> restated
    if doc_period_end > fact_period_end:
        return "restated"
    # Документ раньше периода факта — аномалия, но считаем as_reported
    return "as_reported"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_locator(
    locator: Locator,
    raw_store_getter,  # callable(sha256) -> bytes
) -> Any:
    """Разрешает локатор обратно в значение.
    
    Возвращает извлечённое значение. Должно совпадать с fact.value.
    Используется в тестах разрешимости (I12).
    """
    kind = locator.kind
    
    if kind == "xbrl":
        # XBRL: читаем doc_sha256, парсим JSON, ищем fact_id
        raw = raw_store_getter(locator.doc_sha256)
        import json as _json
        data = _json.loads(raw.decode("utf-8"))
        # Ожидаем структуру: {facts: {fact_id: {value: ..., unit: ...}}}
        fact_data = data.get("facts", {}).get(locator.fact_id)
        if fact_data is None:
            raise ValueError(f"XBRL fact {locator.fact_id} not found in {locator.doc_sha256}")
        return str(fact_data.get("value"))
    
    elif kind == "table":
        # Table: читаем doc_sha256, парсим JSON таблиц
        raw = raw_store_getter(locator.doc_sha256)
        import json as _json
        data = _json.loads(raw.decode("utf-8"))
        tables = data.get("tables", [])
        if locator.table_index >= len(tables):
            raise ValueError(f"Table index {locator.table_index} out of range")
        table = tables[locator.table_index]
        rows = table.get("rows", [])
        if locator.row >= len(rows):
            raise ValueError(f"Row {locator.row} out of range")
        row = rows[locator.row]
        cells = row.get("cells", [])
        if locator.col >= len(cells):
            raise ValueError(f"Col {locator.col} out of range")
        return str(cells[locator.col].get("value"))
    
    elif kind == "pdf":
        # PDF: читаем, используем text_snippet как якорь
        raw = raw_store_getter(locator.doc_sha256)
        # В реальности тут был бы PDF-парсер. Для теста — ищем сниппет.
        text = raw.decode("utf-8", errors="ignore")
        if locator.text_snippet not in text:
            raise ValueError(f"PDF snippet not found in document")
        # Возвращаем то, что в сниппете (последнее число)
        import re
        numbers = re.findall(r"[\d,]+\.?\d*", locator.text_snippet)
        if not numbers:
            raise ValueError("No number in PDF snippet")
        return numbers[-1].replace(",", "")
    
    elif kind == "html":
        raw = raw_store_getter(locator.doc_sha256)
        text = raw.decode("utf-8", errors="ignore")
        if locator.text_snippet not in text:
            raise ValueError(f"HTML snippet not found")
        import re
        numbers = re.findall(r"[\d,]+\.?\d*", locator.text_snippet)
        if not numbers:
            raise ValueError("No number in HTML snippet")
        return numbers[-1].replace(",", "")
    
    elif kind == "api":
        # API: проверяем response_sha256, затем json_pointer
        raw = raw_store_getter(locator.response_sha256)
        import json as _json
        data = _json.loads(raw.decode("utf-8"))
        # Простой json_pointer парсинг (только /a/b/c)
        parts = locator.json_pointer.lstrip("/").split("/")
        for p in parts:
            data = data[p]
        return str(data)
    
    elif kind == "derived":
        # Derived: не разрешается к сырью, а пересчитывается по формуле
        # Здесь просто возвращаем None — проверяется иначе
        return None
    
    else:
        raise ValueError(f"Unknown locator kind: {kind}")


def validate_fact_for_write(fact: Fact) -> list[str]:
    """Возвращает список ошибок валидации. Пустой = OK.
    
    Проверки для I1, I3, I12.
    """
    errors = []
    
    # I1: locator not null/empty
    if not fact.locator or not fact.locator.get("kind"):
        errors.append("I1: fact.locator is empty or missing 'kind'")
    
    # I3: basis определяется правилом периода — проверяется при создании
    
    # I12: resolve(locator) == value — проверяется отдельно с реальным сырьём
    
    # Базовые поля
    if not fact.concept:
        errors.append("concept is required")
    if not fact.period_start or not fact.period_end:
        errors.append("period_start and period_end required")
    if not fact.unit:
        errors.append("unit required")
    if not fact.source_ref:
        errors.append("source_ref (raw_object sha256) required")
    if fact.value is None and fact.status == "ok":
        # NULL value разрешён только с null_reason, но это на уровне measure
        pass
    
    return errors
