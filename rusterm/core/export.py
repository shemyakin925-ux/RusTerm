"""Экспорт: CSV и JSON из готовых величин снапшота (module-contracts.md §6).

Экспорт не пересчитывает: берёт measure из базы как есть. Число в экспорте
обязано совпадать с числом на экране — оба читают одну запись.

ТЗ-20 L9: провенанс переживает выгрузку. attach_provenance добавляет
каждой мере блок provenance (source_kind; у ручного факта — хэш
документа и страница), а snapshot_to_json принимает его опциональным
параметром: существующие вызовы и их вывод не меняются ни именем, ни
порядком. Потребитель ответа на вопрос «это подано регулятору или
достано из PDF моделью?» не открывает базу — только текст экспорта.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Optional

from rusterm.normalize.concepts import CONCEPT_MAP_VERSION

MeasureRow = dict  # поля из SnapshotRepo.get_measures

_PAGE_RE = re.compile(r"#page=(\d+)")


def attach_provenance(measures: list[MeasureRow],
                      lineage: dict[str, list[dict]]) -> list[MeasureRow]:
    """Добавить каждой мере блок provenance по её входным фактам.

    lineage: measure_id -> список фактов в виде dict от FactRepo.get_fact.
    Провенанс честен о пределах: он показывает, КУДА число пришло
    (регулятор или файл пользователя), и у ручного факта — хэш
    документа и страницу; правильность колонки он не доказывает.
    """
    enriched: list[MeasureRow] = []
    for m in measures:
        row = dict(m)
        facts = lineage.get(m.get("measure_id"), [])
        entries = []
        for f in facts:
            kind = f.get("source_kind") or "provider"
            entry = {"kind": kind, "fact_id": f.get("fact_id"),
                     "concept": f.get("concept"),
                     "status": f.get("status")}
            if kind == "manual":
                sha = f.get("source_ref")
                locator = f.get("locator")
                if isinstance(locator, str):
                    try:
                        locator = json.loads(locator)
                    except ValueError:
                        locator = {"locator": locator}
                raw = (locator or {}).get("locator", "")
                page = _PAGE_RE.search(raw)
                entry["document"] = sha
                entry["page"] = int(page.group(1)) if page else None
                entry["locator"] = raw
            else:
                entry["source_ref"] = f.get("source_ref")
            entries.append(entry)
        kinds = {e["kind"] for e in entries}
        if not entries:
            provenance = None
        else:
            provenance = {
                "source_kind": "manual" if "manual" in kinds
                else "provider",
                "facts": entries,
            }
        row["provenance"] = provenance
        enriched.append(row)
    return enriched


def _rows_to_dicts(measures: list) -> list[MeasureRow]:
    out: list[MeasureRow] = []
    for m in measures:
        if isinstance(m, dict):  # уже словарь (напр. с provenance)
            out.append(dict(m))
            continue
        out.append(
            {"measure_id": m[0], "scope": m[1], "scope_ref": m[2],
             "concept": m[3], "value": m[4], "unit": m[5],
             "period_start": m[6], "period_end": m[7], "formula_id": m[8],
             "method_version": m[9], "null_reason": m[10],
             "peer_set_version": m[11]})
    return out


def snapshot_to_json(snapshot: dict, measures: list,
                     provenance: dict[str, list[dict]] | None = None,
                     currencies: dict[str, str | None] | None = None) -> str:
    """JSON снапшота: мета + меры с null-причинами, без досчётов.
    Файл переживает базу — несёт версию карты, его породившую (X4).
    provenance (ТЗ-20 L9) — необязателен: передан — каждая мера несёт
    блок провенанса; не передан — вывод байт-в-байт прежний.
    currencies (ТЗ-22 J1) — необязателен: measure_id -> записанная
    валюта меры или строка отказа; каждая абсолютная мера несёт
    валюту, в которой заявлена."""
    rows = _rows_to_dicts(measures)
    if provenance is not None:
        rows = attach_provenance(rows, provenance)
    if currencies is not None:
        for row in rows:
            if row["measure_id"] in currencies:
                row["currency"] = currencies[row["measure_id"]]
    payload = {
        "snapshot": snapshot,
        "concept_map_version": CONCEPT_MAP_VERSION,
        "measures": rows,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def snapshot_to_csv(measures: list) -> str:
    """CSV мер. NULL-значения идут с null_reason в отдельной колонке.
    Первая строка — версия карты, породившей числа (X4)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["concept_map_version", CONCEPT_MAP_VERSION])
    writer.writerow(["scope", "scope_ref", "concept", "value", "unit",
                     "period_start", "period_end", "method_version",
                     "null_reason"])
    for m in _rows_to_dicts(measures):
        writer.writerow([m["scope"], m["scope_ref"], m["concept"],
                         m["value"], m["unit"], m["period_start"],
                         m["period_end"], m["method_version"],
                         m["null_reason"]])
    return buf.getvalue()


def snapshot_to_md(measures: list) -> str:
    """Markdown-таблица снапшота для чтения в терминале или заметках
    (B13). Пустая мера — прочерк со сноской, где названа её причина;
    числа без периода не бывает: у каждой величины стоят оба конца
    периода. Первая строка — версия карты, породившей числа (X4)."""
    lines = [f"concept_map_version: {CONCEPT_MAP_VERSION}", "",
             "| concept | value | unit | period_start | period_end |",
             "|---|---|---|---|---|"]
    footnotes: list[str] = []
    for m in _rows_to_dicts(measures):
        if m["value"] is None:
            marker = len(footnotes) + 1
            footnotes.append(
                f"- [{marker}] {m['concept']}: {m['null_reason']}")
            value = f"— [{marker}]"
            unit = period_start = period_end = ""
        else:
            value = m["value"]
            unit = m["unit"] or ""
            period_start, period_end = m["period_start"], m["period_end"]
        lines.append(f"| {m['concept']} | {value} | {unit} | "
                     f"{period_start} | {period_end} |")
    if footnotes:
        lines += ["", "Причины пустых значений:"] + footnotes
    return "\n".join(lines) + "\n"
