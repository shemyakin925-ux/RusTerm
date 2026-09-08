"""DisclosuresProvider — раскрытия: отчётность, корпоративные действия,
сделки инсайдеров (module-contracts.md §3).

Реализация обязана уметь poll_index: один запрос на источник, не на
компанию — на этом держится инкрементальность процесса 1. Ошибки
возвращаются значением (ProviderError), исключения наружу не выходят.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .base import ProviderError

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# Синтетические документы: url -> имя файла фикстуры.
_SYNTHETIC_DOCS = {
    "synthetic://report-10k": "synthetic_report_10k.json",
    "synthetic://insider-form4": "synthetic_insider_form4.json",
    "synthetic://prices-table": "synthetic_prices_table.json",
    # демо-набор CLI (TASK-8 U3): 10-K с концептами базовых мер
    "synthetic://demo-10k": "synthetic_demo_report.json",
}

# Индекс для демо-режима CLI: 10-K с концептами базовых мер + инсайдеры.
DEMO_INDEX_FIXTURE = _FIXTURES / "synthetic_demo_index.json"


@dataclass(frozen=True)
class IndexRecord:
    """Запись индекса изменений источника."""
    cursor: str
    issuer_id: str
    doc_type: str
    period: str
    url: str
    published_at: str


@dataclass(frozen=True)
class IndexPoll:
    """Результат poll_index: новые записи и новый курсор."""
    records: tuple  # tuple[IndexRecord, ...]
    cursor: str


@dataclass(frozen=True)
class DocumentMeta:
    """Метаданные документа без тела."""
    issuer_id: str
    doc_type: str
    period: str
    url: str
    published_at: str


@dataclass(frozen=True)
class DocumentList:
    documents: tuple  # tuple[DocumentMeta, ...]


@dataclass(frozen=True)
class FetchedDocument:
    """Сырое тело документа. Тот же url — тот же sha256 (идемпотентность)."""
    url: str
    content: bytes
    sha256: str
    content_type: str


class DisclosuresProvider(Protocol):
    """Протокол по module-contracts.md §3."""

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError:
        """Индекс изменений: один запрос на источник, не на компанию."""
        ...

    def list_documents(self, issuer_id: str, doc_type: str | None = None,
                       period: str | None = None) -> DocumentList | ProviderError:
        """Перечень документов с URL и метаданными, без скачивания тел."""
        ...

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError:
        """Сырой документ; идемпотентно — тот же документ, тот же sha256."""
        ...


class SyntheticDisclosuresProvider:
    """Фейковый провайдер раскрытий на синтетических фикстурах
    fixtures/synthetic_disclosures_index.json. Все данные выдуманы;
    только для тестов И6-И8."""

    source_name = "synthetic"

    def __init__(self, fixture_path: Path | None = None):
        path = fixture_path or (_FIXTURES / "synthetic_disclosures_index.json")
        with open(path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._records: list[IndexRecord] = [
            IndexRecord(
                cursor=r["cursor"], issuer_id=r["issuer_id"],
                doc_type=r["doc_type"], period=r["period"],
                url=r["url"], published_at=r["published_at"],
            )
            for r in self._data.get("records", [])
        ]

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError:
        # Курсоры сортируются лексикографически: "0001" < "0002".
        fresh = tuple(r for r in self._records if r.cursor > cursor)
        new_cursor = fresh[-1].cursor if fresh else cursor
        return IndexPoll(records=fresh, cursor=new_cursor)

    def list_documents(self, issuer_id: str, doc_type: str | None = None,
                       period: str | None = None) -> DocumentList | ProviderError:
        docs = [
            DocumentMeta(issuer_id=r.issuer_id, doc_type=r.doc_type,
                         period=r.period, url=r.url,
                         published_at=r.published_at)
            for r in self._records
            if r.issuer_id == issuer_id
            and (doc_type is None or r.doc_type == doc_type)
            and (period is None or r.period == period)
        ]
        return DocumentList(tuple(docs))

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError:
        filename = _SYNTHETIC_DOCS.get(url)
        if filename is None:
            return ProviderError(f"document_not_found:{url}")
        path = _FIXTURES / filename
        content = path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        return FetchedDocument(url=url, content=content, sha256=sha,
                               content_type="application/json")
