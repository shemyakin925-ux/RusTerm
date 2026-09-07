"""DisclosuresProvider — раскрытия: отчётность, корпоративные действия, сделки.

Строгие запреты: только стандартная библиотека, HTTP только внутри rusterm/providers/.
Никаких ORM, асинхронных фреймворков, внешних зависимостей.
"""
from __future__ import annotations

from typing import Literal, Optional


class DisclosuresProvider:
    """Протокол DisclosuresProvider (module-contracts.md §3).

    Все методы возвращают либо валидные данные, либо явные маркеры ошибок,
    никогда исключения.
    """

    def poll_index(self, cursor: str = "") -> _listdict:
        """Индекс изменений.

        Один запрос на источник, не на компанию. Держится инкрементальность.
        Возвращает список записей о новых раскрытиях и новый курсор.
        """
        raise NotImplementedError

    def list_documents(self, issuer_id: str,
                      doc_type: Optional[str] = None,
                      period: Optional[str] = None) -> _listdict:
        """Перечень документов.

        issuer_id, тип, период -> перечень документов с URL и метаданными.
        Без скачивания тел.
        """
        raise NotImplementedError

    def fetch_document(self, url: str) -> _listdict:
        """Фetch документа по URL.

        Возвращает сырой объект идемпотентно: тот же документ даёт тот же sha256.
        """
        raise NotImplementedError


class FakeDisclosuresProvider(DisclosuresProvider):
    """Фейковый DisclosuresProvider на синтетических данных.

    Явно помечен как synthetic. Отдаёт poll_index и документы для тестирования.
    """

    # Курсор индекса
    _cursor: str = ""
    # Кэш записей индекса
    _index_cache: _listdict = {}
    # Кэш документов
    _doc_cache: _listdict = {}

    def _set_index(self, data: _listdict) -> None:
        """Установка данных индекса (для тестирования)."""
        self._index_cache = data

    def _set_docs(self, data: _listdict) -> None:
        """Установка данных документов (для тестирования)."""
        self._doc_cache = data

    # -- DisclosuresProvider implementation --

    def poll_index(self, cursor: str = "") -> _listdict:
        """Возвращает записи индекса с учётом курсора."""
        # Простая реализация: возвращаем то, что в кэше
        result = self._index_cache.get(cursor, [])
        # Новый_cursor — это следующийafter
        new_cursor = str(int(cursor) + 10) if cursor else "10"
        return {
            "records": result,
            "cursor": new_cursor,
        }

    def list_documents(self, issuer_id: str,
                      doc_type: Optional[str] = None,
                      period: Optional[str] = None) -> _listdict:
        """Возвращает документы для эмитента."""
        docs = self._doc_cache.get(issuer_id, [])
        return {
            "documents": docs,
            "issuer_id": issuer_id,
            "doc_type": doc_type or "annual",
            "period": period or "FY",
        }

    def fetch_document(self, url: str) -> _listdict:
        """Возвращает сырой объект документа (хешированный)."""
        # Идемпотентный возврат — тот же URL всегда тот же sha256
        import hashlib
        sha = hashlib.sha256(url.encode()).hexdigest()
        return {
            "url": url,
            "sha256": sha,
            "provider": "synthetic",
            "block": "fundamentals",
        }
