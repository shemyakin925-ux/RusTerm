"""Парсеры: can_parse и parse для синтетических XBRL-подобного JSON и таблиц.

Границы (module-contracts.md §4): сети нет — парсинг воспроизводится
на сохранённом сырье; can_parse решает по метаданным, не читая тела;
каждый факт имеет локатор и basis; недоразобранное считается и
возвращается, а не игнорируется.

Парсер возвращает словари факта по data-model.md §3. Сборка объектов
core.Fact — обязанность конвейера, не парсера.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

# Правило basis одно на проект (I3): берётся из core, чтобы не плодить
# вторую копию правила, которая неизбежно разойдётся.
from rusterm.core.fact import determine_basis

PARSER_VERSION = "synthetic.v1"

# doc_type из индекса раскрытий -> метаданные, по которым парсер решает,
# не читая тела (processes.md: can_parse решает по типу и источнику).
_DOC_TYPE_TO_KIND = {
    "10-K": "xbrl",
    "10-Q": "xbrl",
    "INSIDER": "table",
    "PRICES": "table",
}


@dataclass
class ParseResult:
    """Разобранный документ: факты-словари + счётчик неразобранного."""
    facts: list[dict] = field(default_factory=list)
    unparsed: int = 0
    parser_version: str = PARSER_VERSION


class Parser(Protocol):
    """Протокол парсера (module-contracts.md §4). Наследования не нужно."""

    def can_parse(self, metadata: dict) -> bool:
        """По типу и источнику, без чтения тела."""
        ...

    def parse(self, raw: bytes, context: dict) -> ParseResult:
        """Сырой объект + контекст эмитента -> факты и счётчик неразобранного."""
        ...


class SyntheticXBRLParser:
    """XBRL-подобный JSON: {"facts": {fact_id: {...}}}; локатор kind=xbrl."""

    source_name = "synthetic"

    def can_parse(self, metadata: dict) -> bool:
        kind = metadata.get("doc_kind") or _DOC_TYPE_TO_KIND.get(
            metadata.get("doc_type"))
        return kind == "xbrl"

    def parse(self, raw: bytes, context: dict) -> ParseResult:
        doc = json.loads(raw.decode("utf-8"))
        result = ParseResult()
        doc_period_end = doc.get("period_end", "")
        filed_at = doc.get("filed_at", "")

        for fact_id, fd in doc.get("facts", {}).items():
            concept = fd.get("concept", "")
            value = fd.get("value")
            period_end = fd.get("period_end", "")
            if not concept or value is None or str(value) == "" or not period_end:
                # Недоразобранное считается, а не выбрасывается.
                result.unparsed += 1
                continue
            result.facts.append({
                "issuer_id": context.get("issuer_id"),
                "listing_id": context.get("listing_id"),
                "concept": concept,
                "value": str(value),
                "unit": fd.get("unit", ""),
                "currency": None,
                "period_start": fd.get("period_start") or period_end,
                "period_end": period_end,
                "period_type": fd.get("period_type", "duration"),
                "basis": determine_basis(doc_period_end, period_end, filed_at),
                "origin": "extracted",
                "source_ref": context.get("source_ref", ""),
                "locator": {
                    "kind": "xbrl",
                    "doc_sha256": context.get("source_ref", ""),
                    "fact_id": fact_id,
                    "concept": concept,
                },
                "parser_version": PARSER_VERSION,
                "status": "ok",
            })
        return result


class TableParser:
    """Табличный JSON: {"tables": [{rows: [{cells: [...]}]}]}; локатор kind=table."""

    source_name = "synthetic"

    def can_parse(self, metadata: dict) -> bool:
        kind = metadata.get("doc_kind") or _DOC_TYPE_TO_KIND.get(
            metadata.get("doc_type"))
        return kind == "table"

    def parse(self, raw: bytes, context: dict) -> ParseResult:
        doc = json.loads(raw.decode("utf-8"))
        result = ParseResult()
        doc_period_end = doc.get("period_end", "")
        filed_at = doc.get("filed_at", "")

        for ti, table in enumerate(doc.get("tables", [])):
            unit = table.get("unit", "")
            table_period = table.get("period_end")
            table_period_type = table.get("period_type")
            columns = table.get("columns", [])
            for ri, row in enumerate(table.get("rows", [])):
                for ci, cell in enumerate(row.get("cells", [])):
                    concept = cell.get("concept", "")
                    value = cell.get("value")
                    if not concept or value is None or str(value) == "":
                        result.unparsed += 1
                        continue
                    # Период ячейки: cell -> column -> table -> документ.
                    # Сравнительная колонка более раннего периода не должна
                    # терять свой период (иначе I3 не к чему применять).
                    column = columns[ci] if ci < len(columns) else {}
                    period_end = (cell.get("period_end")
                                  or column.get("period_end")
                                  or table_period
                                  or doc_period_end)
                    period_start = (cell.get("period_start")
                                    or column.get("period_start")
                                    or period_end)
                    period_type = (cell.get("period_type")
                                   or column.get("period_type")
                                   or table_period_type
                                   or doc.get("period_type")
                                   or "instant")
                    result.facts.append({
                        "issuer_id": context.get("issuer_id"),
                        "listing_id": context.get("listing_id"),
                        "concept": concept,
                        "value": str(value),
                        "unit": cell.get("unit", unit),
                        "currency": None,
                        "period_start": period_start,
                        "period_end": period_end,
                        "period_type": period_type,
                        # Правило basis одно на проект (I3), как в XBRL-парсере.
                        "basis": determine_basis(
                            doc_period_end, period_end, filed_at),
                        "origin": "extracted",
                        "source_ref": context.get("source_ref", ""),
                        "locator": {
                            "kind": "table",
                            "doc_sha256": context.get("source_ref", ""),
                            "table_index": ti,
                            "row": ri,
                            "col": ci,
                        },
                        "parser_version": PARSER_VERSION,
                        "status": "ok",
                    })
        return result


# Реестр парсеров: parse_auto выбирает первого, чей can_parse сказал «да».
_PARSERS: list[Parser] = [SyntheticXBRLParser(), TableParser()]


def registered_parsers() -> list[Parser]:
    return list(_PARSERS)


def parse_auto(raw: bytes, metadata: dict, context: dict) -> ParseResult | None:
    """Разобрать документ подходящим парсером; None — если такого нет.
    Отсутствие парсера — ветка E4 конвейера, не молчаливый пропуск."""
    for parser in _PARSERS:
        if parser.can_parse(metadata):
            return parser.parse(raw, context)
    return None
