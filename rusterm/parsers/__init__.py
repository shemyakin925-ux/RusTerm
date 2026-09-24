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
import math
from dataclasses import dataclass, field
from typing import Protocol

# Правило basis одно на проект (I3): берётся из core, чтобы не плодить
# вторую копию правила, которая неизбежно разойдётся.
from rusterm.core.fact import determine_basis

PARSER_VERSION = "synthetic.v1"

# ТЗ-22 J1.0: правило валюты из ключа units живёт в core.fact —
# единая копия (k3/k6 используют его же в store).
from rusterm.core.fact import currency_of_unit  # noqa: E402,F401

# doc_type из индекса раскрытий -> метаданные, по которым парсер решает,
# не читая тела (processes.md: can_parse решает по типу и источнику).
_DOC_TYPE_TO_KIND = {
    "10-K": "xbrl",
    "10-Q": "xbrl",
    "INSIDER": "table",
    "PRICES": "table",
}


# ── ТЗ-83 F1: границы входа ───────────────────────────────────────────────
# Строки 2-4 таблицы контрактов ТЗ-83 обещают ЗНАЧЕНИЕ (ParseResult или
# None) и не обещают исключения. Битые байты, не-словари там, где ждали
# словарь, и неконечные числа долетали до вызывающего как
# UnicodeDecodeError / JSONDecodeError / AttributeError / TypeError.
# Здесь они превращаются в refusals на границе парсера: неразобранное
# считается (unparsed), а не игнорируется и не бросается.


def _document(raw) -> dict | None:
    """Байты -> документ верхнего уровня; None — весь документ нечитаем.

    Не-utf-8 и битый JSON — оба подклассы ValueError; рекурсивный
    сканер json на очень глубоком входе тонет стеком и поднимает
    RecursionError (замер: 100 000 открывающих скобок). Ни одно из трёх
    не является разрешённым исходом по строке контракта, поэтому отказ —
    значение.
    """
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        return None
    return doc if isinstance(doc, dict) else None


def _text(value) -> str:
    """Поле-строка (дата периода, концепт, валюта) или пусто.

    Не-строка — не дата: сравнение в determine_basis и в дедупликации
    флингов бросает TypeError на mixed-типах, а такой факт всё равно
    невоспроизводим.
    """
    return value if isinstance(value, str) else ""


def _is_non_finite(value) -> bool:
    """True — значение неконечное (nan/inf): фиксирующее решение ТЗ-83,
    такой факт не факт, а неразобранное. Что числом не читается — то не
    сюда: его судьбу решает вызывающий слой."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return not math.isfinite(value)
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return False
    return not math.isfinite(number)


@dataclass
class ParseResult:
    """Разобранный документ: факты-словари + счётчик неразобранного."""
    facts: list[dict] = field(default_factory=list)
    unparsed: int = 0
    parser_version: str = PARSER_VERSION
    # Проигравшие дедупликации: тот же (concept, unit, период) от более
    # раннего флинга; несут superseded_by_locator победителя (TASK-8 U6).
    superseded: list[dict] = field(default_factory=list)


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
        doc = _document(raw)
        if doc is None:
            # ТЗ-83 F1: нечитаемый документ — отказ значением, один
            # зачтённый пропуск на весь документ.
            return ParseResult(unparsed=1)
        result = ParseResult()
        doc_period_end = _text(doc.get("period_end"))
        filed_at = _text(doc.get("filed_at"))

        facts = doc.get("facts")
        if not isinstance(facts, dict):
            result.unparsed += 1
            return result

        for fact_id, fd in facts.items():
            if not isinstance(fd, dict):
                result.unparsed += 1
                continue
            concept = _text(fd.get("concept"))
            value = fd.get("value")
            period_end = _text(fd.get("period_end"))
            if not concept or value is None or str(value) == "" or not period_end:
                # Недоразобранное считается, а не выбрасывается.
                result.unparsed += 1
                continue
            if _is_non_finite(value):
                # Фиксирующее решение ТЗ-83: неконечное число — не факт.
                result.unparsed += 1
                continue
            result.facts.append({
                "issuer_id": context.get("issuer_id"),
                "listing_id": context.get("listing_id"),
                "concept": concept,
                "value": str(value),
                "unit": _text(fd.get("unit")),
                "currency": None,
                "period_start": _text(fd.get("period_start")) or period_end,
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
        doc = _document(raw)
        if doc is None:
            return ParseResult(unparsed=1)
        result = ParseResult()
        doc_period_end = _text(doc.get("period_end"))
        filed_at = _text(doc.get("filed_at"))

        tables = doc.get("tables")
        if not isinstance(tables, list):
            # Секции нет или она не списка — разобрать нечего, и это
            # засчитывается (та же симметрия, что у раздела facts).
            result.unparsed += 1
            tables = []
        for ti, table in enumerate(tables):
            if not isinstance(table, dict):
                # Раздел есть, но это не таблица: зачитывается, а не
                # пролетает AttributeError на table.get.
                result.unparsed += 1
                continue
            unit = _text(table.get("unit"))
            table_period = _text(table.get("period_end"))
            table_period_type = table.get("period_type")
            columns = table.get("columns")
            if not isinstance(columns, list):
                columns = []
            rows = table.get("rows")
            if not isinstance(rows, list):
                result.unparsed += 1
                continue
            for ri, row in enumerate(rows):
                cells = row.get("cells") if isinstance(row, dict) else None
                if not isinstance(cells, list):
                    result.unparsed += 1
                    continue
                for ci, cell in enumerate(cells):
                    if not isinstance(cell, dict):
                        result.unparsed += 1
                        continue
                    concept = _text(cell.get("concept"))
                    value = cell.get("value")
                    if (not concept or value is None or str(value) == ""
                            or _is_non_finite(value)):
                        result.unparsed += 1
                        continue
                    # Период ячейки: cell -> column -> table -> документ.
                    # Сравнительная колонка более раннего периода не должна
                    # терять свой период (иначе I3 не к чему применять).
                    column = (columns[ci] if ci < len(columns)
                              and isinstance(columns[ci], dict) else {})
                    period_end = (_text(cell.get("period_end"))
                                  or _text(column.get("period_end"))
                                  or table_period
                                  or doc_period_end)
                    period_start = (_text(cell.get("period_start"))
                                    or _text(column.get("period_start"))
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
                        "unit": _text(cell.get("unit")) or unit,
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


class CompanyFactsParser:
    """Настоящий companyfacts SEC EDGAR (TASK-8 U6):
    facts.<taxonomy>.<concept>.units.<unit>[] с start/end/fy/fp/form/
    filed/accn/frame.

    basis — то же правило I3: determine_basis(latest_end_of_accn, end,
    filed), где latest_end_of_accn — конец периода, на который отчитывался
    этот accession. Дубликаты одного (concept, unit, период) из разных
    флингов: живой — новейший filed, проигравший сохраняется в
    result.superseded с ссылкой на локатор победителя — ничего не
    выбрасывается и не усредняется.
    """

    source_name = "edgar"
    parser_version = "companyfacts.v1"

    def can_parse(self, metadata: dict) -> bool:
        return metadata.get("doc_kind") == "companyfacts"

    def parse(self, raw: bytes, context: dict) -> ParseResult:
        from rusterm.core.fact import determine_basis

        doc = _document(raw)
        result = ParseResult(parser_version=self.parser_version)
        if doc is None:
            # ТЗ-83 F1: ответ API, который не читается как JSON-документ,
            # — отказ значением (весь payload в неразобранное), а не
            # UnicodeDecodeError/JSONDecodeError вызывающему.
            result.unparsed = 1
            return result
        request_hash = context.get("source_ref", "")
        endpoint = context.get(
            "endpoint", "https://data.sec.gov/api/xbrl/companyfacts")

        # TASK-18 G4 (§0.3 ruling 2): парсится та таксономия, которую
        # несёт payload; обе — побеждает us-gaap. Ни одной из двух —
        # разбираются все разделы как раньше (dei и прочие остаются
        # неотображёнными). Имя таксономии уже живёт в json_pointer
        # каждого факта — видимость без миграции.
        # ТЗ-78 Y2: dei добавляется как ДОПОЛНИТЕЛЬНЫЙ раздел к любой
        # основной таксономии, а не заменяет её: обложка 10-K несёт
        # EntityCommonStockSharesOutstanding, которого нет в us-gaap, и
        # приоритет решается в snapshot через priority_rank — us-gaap
        # ранг 0, dei ранг 1000+ (см. _DEI_RANK_OFFSET), поэтому если
        # эмитент подаёт оба тега для одной меры, us-gaap выигрывает.
        facts_root = doc.get("facts")
        if not isinstance(facts_root, dict):
            # Раздела facts нет или он не словарь: один зачтённый пропуск
            # на раздел (та же симметрия, что у tables и facts выше).
            result.unparsed += 1
            facts_root = {}
        if "us-gaap" in facts_root:
            taxonomies = [("us-gaap", facts_root["us-gaap"])]
        elif "ifrs-full" in facts_root:
            taxonomies = [("ifrs-full", facts_root["ifrs-full"])]
        else:
            taxonomies = list(facts_root.items())
        if "dei" in facts_root and all(t != "dei" for t, _ in taxonomies):
            taxonomies = taxonomies + [("dei", facts_root["dei"])]
        # ТЗ-83 F1: раздел таксономии, который не словарь, — зачитается,
        # а не даст AttributeError на concepts.items().
        usable: list[tuple] = []
        for name, concepts in taxonomies:
            if isinstance(concepts, dict):
                usable.append((name, concepts))
            else:
                result.unparsed += 1
        taxonomies = usable

        # Проход 1: конец периода, на который отчитывался каждый accn
        latest_end_by_accn: dict[str, str] = {}
        for _taxonomy, concepts in taxonomies:
            for key, node in concepts.items():
                if not isinstance(node, dict):
                    result.unparsed += 1
                    continue
                entries_by_unit = node.get("units")
                if not isinstance(entries_by_unit, dict):
                    result.unparsed += 1
                    continue
                for entries in entries_by_unit.values():
                    if not isinstance(entries, list):
                        result.unparsed += 1
                        continue
                    for entry in entries:
                        if not isinstance(entry, dict):
                            result.unparsed += 1
                            continue
                        accn, end = (_text(entry.get("accn")),
                                     _text(entry.get("end")))
                        if accn and (accn not in latest_end_by_accn
                                     or end > latest_end_by_accn[accn]):
                            latest_end_by_accn[accn] = end

        # Проход 2: факты; ключ дедупликации (concept, unit, start, end)
        seen: dict[tuple, dict] = {}
        for taxonomy, concepts in taxonomies:
            for key, node in concepts.items():
                if not isinstance(node, dict):
                    continue
                concept = f"{taxonomy}:{key}"
                entries_by_unit = node.get("units")
                if not isinstance(entries_by_unit, dict):
                    continue
                for unit_kind, entries in entries_by_unit.items():
                    if not isinstance(entries, list):
                        continue
                    for idx, entry in enumerate(entries):
                        if not isinstance(entry, dict):
                            result.unparsed += 1
                            continue
                        end = _text(entry.get("end"))
                        value = entry.get("val")
                        if not end or value is None or _is_non_finite(value):
                            # ТЗ-83 F1: nan/inf из ответа API — не факт,
                            # а неразобранное (фиксирующее решение).
                            result.unparsed += 1
                            continue
                        start = _text(entry.get("start")) or end
                        filed = _text(entry.get("filed"))
                        accn = _text(entry.get("accn"))
                        locator = {
                            "kind": "api",
                            "endpoint": endpoint,
                            "request_hash": request_hash,
                            "json_pointer": (
                                f"/facts/{taxonomy}/{key}"
                                f"/units/{unit_kind}/{idx}/val"),
                            "value_snapshot": str(value),
                            "retrieved_at": 0.0,
                            "schema": "api.v2",
                        }
                        fact = {
                            "issuer_id": context.get("issuer_id"),
                            "listing_id": context.get("listing_id"),
                            "concept": concept,
                            "value": str(value),
                            "unit": unit_kind,
                            # ТЗ-22 J1.0: ключ units и есть валюта для
                            # денежных концептов; shares/pure — не валюта
                            "currency": currency_of_unit(unit_kind),
                            "period_start": start,
                            "period_end": end,
                            "period_type": ("duration"
                                            if entry.get("start")
                                            else "instant"),
                            "basis": determine_basis(
                                latest_end_by_accn.get(accn, end),
                                end, filed),
                            "origin": "extracted",
                            "source_ref": request_hash,
                            "locator": locator,
                            "parser_version": self.parser_version,
                            "status": "ok",
                            "accn": accn,
                            "filed": filed,
                        }
                        dedup_key = (concept, unit_kind, start, end)
                        previous = seen.get(dedup_key)
                        if previous is None:
                            seen[dedup_key] = fact
                            result.facts.append(fact)
                        elif filed > previous.get("filed", ""):
                            # предыдущий флинг проигрывает новейшему
                            previous["superseded_by_locator"] = dict(locator)
                            previous["superseded_by_filed"] = filed
                            result.facts.remove(previous)
                            result.superseded.append(previous)
                            seen[dedup_key] = fact
                            result.facts.append(fact)
                        else:
                            fact["superseded_by_locator"] = dict(
                                previous["locator"])
                            fact["superseded_by_filed"] = \
                                previous.get("filed", "")
                            result.superseded.append(fact)
        return result


# Реестр парсеров: parse_auto выбирает первого, чей can_parse сказал «да».
_PARSERS: list[Parser] = [SyntheticXBRLParser(), TableParser(),
                          CompanyFactsParser()]


def registered_parsers() -> list[Parser]:
    return list(_PARSERS)


def parse_auto(raw: bytes, metadata: dict, context: dict) -> ParseResult | None:
    """Разобрать документ подходящим парсером; None — если такого нет.
    Отсутствие парсера — ветка E4 конвейера, не молчаливый пропуск."""
    for parser in _PARSERS:
        if parser.can_parse(metadata):
            return parser.parse(raw, context)
    return None
