"""Парсеры: can_parse и parse для синтетических XBRL-подобных JSON и таблиц.

Строгие запреты: сети нет (все из сырого объекта), никаких ORM, 
каждый факт с локатором и basis; недоразобранное считается и возвращается.
"""
from __future__ import annotations

from typing import Literal, Optional, list, dict as _listdict, Tuple

RawObject = dict[str, any]


class Parser:
    """Протокол парсера (module-contracts.md §4)."""

    def can_parse(self, raw: RawObject, metadata: dict) -> bool:
        """Может ли парсер обработать данный raw объект.

        По типу и источнику, без чтения тела целиком.
        """
        raise NotImplementedError

    def parse(self, raw: RawObject, context: dict) -> Tuple[list, int]:
        """Разбирает raw объект на факты.

        Возвращает (список фактов, счетчик неразобранного).
        Каждый факт с локатором и basis.
        Сети нет.
        Недоразобранное считается и возвращается, а не игнорируется.
        """
        raise NotImplementedError


class SyntheticXBRLParser(Parser):
    """Парсер синтетического XBRL-подобного JSON.

    Разбирает JSON с kind=xbrl локаторами в Fact-ы.
    Явно помечен как synthetic.
    """

    def can_parse(self, raw: RawObject, metadata: dict) -> bool:
        """Парсер может обработать если есть facts в raw объекте."""
        return "facts" in raw

    def parse(self, raw: RawObject, context: dict) -> Tuple[list, int]:
        """Разбирает синтетический XBRL JSON в список фактов.

        Возвращает (facts_list, unparsed_count).
        Каждый факт содержит локатор kind=xbrl и basis.
        """
        facts = []
        unparsed = 0

        # Ищем facts в raw объекте
        raw_facts = raw.get("facts", {})
        if not raw_facts:
            return [], 0

        # Простая эмуляция: создаем факты из доступных данных
        for fact_id, fact_data in raw_facts.items():
            # Базовый факт
            fact = {
                "fact_id": fact_id,
                "concept": fact_data.get("concept", "unknown"),
                "value": str(fact_data.get("value", "0")),
                "unit": fact_data.get("unit", "USD"),
                "basis": "as_reported",  # по умолчанию
                "origin": "extracted",
                "source_ref": metadata.get("sha256", ""),
                "locator": {
                    "kind": "xbrl",
                    "doc_sha256": metadata.get("sha256", ""),
                    "fact_id": fact_id,
                },
                "parser_version": "synthetic.v1",
            }
            facts.append(fact)

        unparsed = len(raw) - len(raw_facts) if raw else 0
        return facts, unparsed


class TableParser(Parser):
    """Парсер табличных данных.

    Разбирает JSON с kind=table локаторами в Fact-ы.
    """

    def can_parse(self, raw: RawObject, metadata: dict) -> bool:
        """Парсер может обработать если есть tables в raw объекте."""
        return "tables" in raw

    def parse(self, raw: RawObject, context: dict) -> Tuple[list, int]:
        """Разбирает табличный JSON в список фактов.

        Возвращает (facts_list, unparsed_count).
        """
        facts = []
        unparsed = 0

        raw_tables = raw.get("tables", [])
        if not raw_tables:
            return [], 0

        for ti, table in enumerate(raw_tables):
            rows = table.get("rows", [])
            for ri, row in enumerate(rows):
                cells = row.get("cells", [])
                for ci, cell in enumerate(cells):
                    value = cell.get("value", "0")
                    concept = cell.get("concept", f"table_{ti}_{ri}_{ci}")

                    fact = {
                        "fact_id": f"table_{ti}_{ri}_{ci}",
                        "concept": concept,
                        "value": str(value),
                        "unit": "USD",
                        "basis": "as_reported",
                        "origin": "extracted",
                        "source_ref": metadata.get("sha256", ""),
                        "locator": {
                            "kind": "table",
                            "doc_sha256": metadata.get("sha256", ""),
                            "table_index": ti,
                            "row": ri,
                            "col": ci,
                        },
                        "parser_version": "synthetic.v1",
                    }
                    facts.append(fact)

        unparsed = len(raw) - sum(len(t.get("rows", [])) for t in raw_tables) if raw else 0
        return facts, unparsed
