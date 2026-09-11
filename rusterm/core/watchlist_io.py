"""Импорт и экспорт watchlist (TASK-7 T11, docs/watchlist-and-llm.md §1.4).

Экспорт — тикерный, для человека: ровно колонки
ticker,market,isin,industry,note,added_at. Импорт прогоняет каждую
строку через разрешение (тикер, рынок, дата): неразрешённая или
неоднозначная строка попадает в отчёт и НЕ добавляется — молчаливый
пропуск и есть дефект, ради которого существует этот модуль.

Состав меняется новой версией целиком (T10); один импорт — одна
новая версия, и только если есть что добавить.
"""
from __future__ import annotations

import csv
import datetime
import io
import json
import uuid

EXPORT_COLUMNS = ("ticker", "market", "isin", "industry", "note",
                  "added_at")

# Источника отрасли в схеме нет (TASK-8 U12.4): колонка честно пуста,
# и экспорт обязан это называть, а не молчать.
INDUSTRY_EMPTY_NOTE = "industry пуст: источника отрасли в схеме нет"


def export_rows(watchlist_repo, instrument_repo, watchlist_id: str,
                as_of: str) -> list[dict]:
    """Текущий состав списка в тикерных строках экспорта."""
    rows = []
    for member in watchlist_repo.members(watchlist_id):
        instrument = instrument_repo.get_instrument(member["instrument_id"])
        ref = instrument_repo.ticker_for_instrument(
            member["instrument_id"], as_of)
        added = datetime.datetime.fromtimestamp(
            member["added_at"]).strftime("%Y-%m-%d")
        rows.append({
            "ticker": ref["ticker"] if ref else "",
            "market": ref["market"] if ref else "",
            "isin": (instrument.isin or "") if instrument else "",
            # источника отрасли в схеме нет — колонка честно пустая
            "industry": "",
            "note": member["note"] or "",
            "added_at": added,
        })
    rows.sort(key=lambda r: r["ticker"])
    return rows, INDUSTRY_EMPTY_NOTE


def export_csv(watchlist_repo, instrument_repo, watchlist_id: str,
               as_of: str) -> tuple:
    rows, note = export_rows(watchlist_repo, instrument_repo,
                             watchlist_id, as_of)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(EXPORT_COLUMNS))
    writer.writeheader()
    writer.writerows(rows)
    # заметка идёт отдельно от CSV: файл обязан оставаться чистым
    # для обратного импорта
    return buf.getvalue(), note


def export_json(watchlist_repo, instrument_repo, watchlist_id: str,
                as_of: str) -> tuple:
    rows, note = export_rows(watchlist_repo, instrument_repo,
                             watchlist_id, as_of)
    return (json.dumps({"rows": rows, "note": note},
                       ensure_ascii=False, indent=2), note)


def parse_import(text: str, fmt: str) -> list[dict]:
    """Строки импорта из текста CSV или JSON; ключи — EXPORT_COLUMNS."""
    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(text))
        return [{k: (row.get(k) or "") for k in EXPORT_COLUMNS}
                for row in reader]
    if fmt == "json":
        return [{k: (row.get(k) or "") for k in EXPORT_COLUMNS}
                for row in json.loads(text)]
    raise ValueError(f"неизвестный формат импорта {fmt!r}")


def import_rows(watchlist_repo, instrument_repo, watchlist_id: str,
                rows: list[dict], as_of: str) -> dict:
    """Импорт с отчётом: added / already_present / not_found / ambiguous,
    у каждой категории свои причины. Молчаливых пропусков нет."""
    current = {m["instrument_id"]
               for m in watchlist_repo.members(watchlist_id)}
    report = {"added": [], "already_present": [], "not_found": [],
              "ambiguous": []}
    to_add: list[tuple[str, str]] = []
    for row in rows:
        ticker = (row.get("ticker") or "").strip()
        market = (row.get("market") or "").strip()
        if not ticker or not market:
            report["not_found"].append(
                {"ticker": ticker, "market": market,
                 "reason": "row_missing_ticker_or_market"})
            continue
        candidates = instrument_repo.resolve_ticker_candidates(
            ticker, market, as_of)
        if not candidates:
            report["not_found"].append(
                {"ticker": ticker, "market": market,
                 "reason": f"no_instrument_for_{ticker}.{market}@{as_of}"})
            continue
        if len(candidates) > 1:
            report["ambiguous"].append(
                {"ticker": ticker, "market": market,
                 "candidates": candidates,
                 "reason": f"{len(candidates)} instruments match"})
            continue
        instrument_id = candidates[0]
        if instrument_id in current or instrument_id in (i for i, _ in to_add):
            report["already_present"].append(
                {"ticker": ticker, "instrument_id": instrument_id,
                 "reason": "member_of_current_version"})
            continue
        to_add.append((instrument_id, row.get("note") or ""))
        report["added"].append(
            {"ticker": ticker, "instrument_id": instrument_id})

    if to_add:
        current_version = watchlist_repo.current_version(watchlist_id)
        source_vid = current_version["watchlist_version_id"]
        new_number = current_version["version"] + 1
        version_id = watchlist_repo.new_version(
            str(uuid.uuid4()), watchlist_id, new_number,
            "import", f"rows={len(rows)}")
        # новая версия — полный новый состав: прежние участники + добавленные
        watchlist_repo.copy_members(source_vid, version_id)
        for instrument_id, note in to_add:
            watchlist_repo.add_member(version_id, instrument_id, note)
    return report
