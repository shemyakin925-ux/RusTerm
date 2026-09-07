"""Экспорт: CSV и JSON из готовых величин снапшота (module-contracts.md §6).

Экспорт не пересчитывает: берёт measure из базы как есть. Число в экспорте
обязано совпадать с числом на экране — оба читают одну запись.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Optional

MeasureRow = dict  # поля из SnapshotRepo.get_measures


def _rows_to_dicts(measures: list) -> list[MeasureRow]:
    return [
        {"measure_id": m[0], "scope": m[1], "scope_ref": m[2],
         "concept": m[3], "value": m[4], "unit": m[5],
         "period_start": m[6], "period_end": m[7], "formula_id": m[8],
         "method_version": m[9], "null_reason": m[10],
         "peer_set_version": m[11]}
        for m in measures
    ]


def snapshot_to_json(snapshot: dict, measures: list) -> str:
    """JSON снапшота: мета + меры с null-причинами, без досчётов."""
    payload = {
        "snapshot": snapshot,
        "measures": _rows_to_dicts(measures),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def snapshot_to_csv(measures: list) -> str:
    """CSV мер. NULL-значения идут с null_reason в отдельной колонке."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["scope", "scope_ref", "concept", "value", "unit",
                     "period_start", "period_end", "method_version",
                     "null_reason"])
    for m in _rows_to_dicts(measures):
        writer.writerow([m["scope"], m["scope_ref"], m["concept"],
                         m["value"], m["unit"], m["period_start"],
                         m["period_end"], m["method_version"],
                         m["null_reason"]])
    return buf.getvalue()
