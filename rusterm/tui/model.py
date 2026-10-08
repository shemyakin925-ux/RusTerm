"""Чистая модель экранов TUI (TASK-8 U11).

Здесь всё содержимое экранов: списки строк и словари, собранные из
данных через репозитории. Никакого SQL, никакой сети, никаких формул,
никакого curses — рисование в rusterm/tui/app.py только красит то,
что собрали эти функции. Тесты гоняют модель без терминала.

Пустой блок показывается с причиной, мера без значения — «—» с
null_reason, governance — пять отдельных цветов без свёртки.
"""
from __future__ import annotations

import datetime
import json
import re
from typing import Optional

from rusterm.core.industry.aggregate import (build_sector_aggregates,
                                             period_note, shortfall_note)
from rusterm.core.snapshot import measure_inputs, stale_exclusions
from rusterm.markets import get_market

NULL_MARK = "—"

# Меры экрана «Отрасль» (ТЗ-22 J7): четыре ratio-меры M7 + абсолютные —
# на них видна валюта (J1) и отказ при смешении.
# ТЗ-97 Q1 (ТЗ-73 T1): абсолютной мерой больше не может быть `revenue` —
# выручки нет в словаре мер, ни один снапшот её не подаёт (в таблице
# measure строк `revenue` — 0), и строка не наполнится никогда: на копии
# базы пользователя она давала `peer_set_too_small (no_value=9)` во всех
# пяти наборах. `ebitda` — абсолютная мера словаря с тем же валютным
# сторожем, и она наполняется: строк агрегата с числами было 8 из 25,
# стало 10 из 25 (software 5 из 5, hardware_electronics 4 из 5); где не
# наполняется — называет настоящую причину (mining_metals
# `currency_mismatch: CAD, USD`, telecom — MXN/USD). `market_cap_total`
# стоит в списке с ТЗ-104 P5: раньше её вычеркнули как `revenue` — за
# отказ `currency_mismatch: USD, (blank)` на всех пяти наборах копии:
# пустоту в набор валют приносил факт числа акций, у которого валюты не
# бывает по единице.
_SECTOR_MEASURES: tuple[str, ...] = ("asset_turnover", "net_margin",
                                     "operating_margin", "ebitda", "roe",
                                     "market_cap_total")


def _market_of(instrument_id: str) -> str:
    """Код рынка инструмента: префикс id до первого дефиса, если он в
    реестре; иначе честное «—» (не догадка)."""
    prefix = (instrument_id or "").split("-", 1)[0]
    return prefix if get_market(prefix) else NULL_MARK


_MANUAL_PAGE_RE = re.compile(r"#page=(\d+)")


def _today() -> str:
    return datetime.date.today().isoformat()


def list_rows(repos, watchlist_id: Optional[str]) -> list[dict]:
    """Экран «Список»: по строке на текущего участника watchlist.
    Пустой watchlist_id или без участников — пустой список строк."""
    if not watchlist_id:
        watchlists = repos.watchlist.list_watchlists()
        watchlist_id = watchlists[0]["watchlist_id"] if watchlists else None
    if not watchlist_id:
        return []
    rows = []
    for member in repos.watchlist.members(watchlist_id):
        instrument_id = member["instrument_id"]
        instrument = repos.instrument.get_instrument(instrument_id)
        ref = repos.instrument.ticker_for_instrument(
            instrument_id, _today())
        snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
        snapshot = (repos.snapshot.get_snapshot(snapshot_id)
                    if snapshot_id else None)
        coverage = {r["block"]: r["status"]
                    for r in repos.coverage.for_instrument(instrument_id)}
        cells = [coverage.get(block, "-") for block in (
            "prices", "fundamentals", "ownership", "corporate_actions",
            "governance", "industry_metrics", "peer_set", "llm_summary")]
        rows.append({
            "instrument_id": instrument_id,
            "market": _market_of(instrument_id),
            "ticker": ref["ticker"] if ref else instrument_id,
            "as_of": snapshot["as_of"] if snapshot else NULL_MARK,
            "snapshot_id": snapshot_id,
            "coverage_cells": cells,
            "peer_status": repos.peer_set.peer_status_for_instrument(
                instrument_id),
        })
    return rows


def measure_reason_counts(repos, snapshot_id: str | None) -> dict:
    """Токены причин пустых мер снапшота (ТЗ-61 F1): одно счётное
    место для всех трёх лиц — `rusterm coverage --json`, окно и TUI.
    Мера со значением не считается; токен — первый до ':'."""
    counts: dict = {}
    if not snapshot_id:
        return counts
    for m in repos.snapshot.get_measures(snapshot_id):
        if m[4] is not None:
            continue
        token = (m[10] or "missing_data").split(":", 1)[0]
        counts[token] = counts.get(token, 0) + 1
    return counts


def card_rows(repos, instrument_id: str) -> dict:
    """Экран «Карточка»: меры, покрытие с причинами, governance."""
    snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
    instrument = repos.instrument.get_instrument(instrument_id)
    issuer_id = instrument.issuer_id if instrument else None
    measures = []
    for m in (repos.snapshot.get_measures(snapshot_id)
              if snapshot_id else []):
        measure_id, _scope, _ref, concept, value, unit, start, end, \
            formula_id, method_version, null_reason, _psv = m
        # ТЗ-20 L8: происхождение числа считывается с входных фактов
        facts = [repos.fact.get_fact(fid) for fid in
                 repos.snapshot.lineage_fact_ids(measure_id)]
        facts = [f for f in facts if f]
        kinds = {f.get("source_kind") or "provider" for f in facts}
        if not facts:
            source_kind = None
        elif "manual" in kinds:
            source_kind = "manual"
        else:
            source_kind = "provider"
        unverified = any(f.get("status") == "suspect" for f in facts)
        measures.append({
            "measure_id": measure_id,
            "concept": concept,
            # строка перцентиля называет свою меру (иначе восемь
            # одинаковых «percentile» подряд)
            "percentile_of": (repos.snapshot.percentile_base_concept(
                measure_id) if concept == "percentile" else None),
            "value": value if value is not None else NULL_MARK,
            "null_reason": null_reason if value is None else None,
            "unit": unit,
            # ТЗ-22 J1: валюта, в которой заявлена абсолютная мера
            # (или строка currency_mismatch с перечнем)
            "currency": (repos.snapshot.measure_currency(measure_id,
                                                         concept)
                         if snapshot_id else None),
            "period": end,
            "method_version": method_version,
            # TASK-15 C5: панель источника ищет исключённое по эмитенту
            "issuer_id": issuer_id,
            "source_kind": source_kind,
            "unverified": unverified,
        })
    coverage = [
        {"block": r["block"], "status": r["status"], "reason": r["reason"]}
        for r in repos.coverage.for_instrument(instrument_id)
    ]
    governance = []
    for indicator in ("independent_directors", "ceo_chair", "related_party",
                      "insider_net", "auditor"):
        latest = repos.governance.latest(instrument_id, indicator)
        if latest is not None:
            governance.append({"indicator": indicator,
                               "color": latest["color"],
                               "reason": latest["reason"],
                               "lineage_ref": latest["lineage_ref"],
                               "method_version": latest["method_version"]})
        else:
            # ТЗ-97 Q2 (P8): строки без оценки — не молчание: причина
            # словом и команда, которой она закрывается.
            governance.append({"indicator": indicator, "color": "gray",
                               "reason": "no_data:not_collected",
                               "method_version": None})
    return {
        "instrument_id": instrument_id,
        "snapshot_id": snapshot_id,
        "measures": measures,
        "coverage": coverage,
        "governance": governance,
        "peer_status": repos.peer_set.peer_status_for_instrument(
            instrument_id),
    }


def source_panel(repos, measure: dict) -> dict:
    """Панель источника выделенной меры: документ, локатор входного
    факта, method_version. Всё через репозитории, вычислений нет.

    TASK-15 C5: у пустой меры показывается и то, что исключено правилом
    давности Y2 — «устаревший (последний 2012-12-31, anchor 2025-12-31)».
    Факт при этом остаётся в store, мера и её причина не меняются.
    """
    lineage = repos.snapshot.lineage_fact_ids(measure["measure_id"])
    sources = []
    for fact_id in lineage:
        fact = repos.fact.get_fact(fact_id)
        if fact is None:
            continue
        locator = fact["locator"]
        if isinstance(locator, str):
            locator = json.loads(locator)
        kind = fact.get("source_kind") or "provider"
        source = {
            "document": fact["source_ref"],
            "locator": locator,
            "fact_id": fact_id,
            "kind": kind,
            # какой тег стал этим числом и по какой карте (TASK-9 V6)
            "source_tag": fact["concept"],
            "concept_map_version": fact["concept_map_version"],
        }
        if kind == "manual":
            # ручной факт: вместо URL — файл и страница (ADR-0011)
            raw_locator = locator.get("locator", "") \
                if isinstance(locator, dict) else str(locator)
            match = _MANUAL_PAGE_RE.search(raw_locator)
            source["locator_label"] = \
                f"файл, страница {match.group(1)}" if match \
                else "файл"
        sources.append(source)
    stale = []
    issuer_id = measure.get("issuer_id")
    if issuer_id and measure.get("value") in (None, NULL_MARK):
        wanted = set(measure_inputs(measure["concept"]))
        exclusions = stale_exclusions(repos.snapshot, issuer_id)
        for fact_id, (period_end, anchor) in sorted(
                exclusions.items(), key=lambda kv: kv[1][0]):
            fact = repos.fact.get_fact(fact_id)
            if fact is None:
                continue
            key = fact.get("canonical_concept") or fact["concept"]
            if wanted and key not in wanted:
                continue
            stale.append({
                "fact_id": fact_id,
                "source_tag": fact["concept"],
                "period_end": period_end,
                "marker": f"устаревший (последний {period_end},"
                          f" anchor {anchor})",
            })
    return {
        "measure_id": measure["measure_id"],
        "concept": measure["concept"],
        "method_version": measure.get("method_version"),
        "sources": sources,
        "stale": stale,
    }


def industry_metric_rows(repos, sector: str,
                         as_of: Optional[str] = None) -> list[dict]:
    """ТЗ-24 N8: физические метрики сектора рядом с финансовым
    агрегатом. Серая метрика показывает недостающий вход; источник
    manual помечен полем source — рендер различает его."""
    from rusterm.core.industry.inputs import (compute_sector_metrics,
                                              collect_physical_inputs)
    module = None
    from rusterm.core.industry import module_for_sector
    module = module_for_sector(sector)
    if module is None:
        return []
    version = repos.peer_set.version_at(sector, as_of or _today())
    if version is None:
        return []
    rows: dict[str, dict] = {}
    members = repos.peer_set.member_snapshots_at(
        version["peer_set_version_id"], as_of or _today())
    for iid in members:
        instrument = repos.instrument.get_instrument(iid)
        if instrument is None:
            continue
        si = collect_physical_inputs(repos.manual_extraction,
                                     instrument.issuer_id, sector)
        for m in compute_sector_metrics(module, sector, si):
            row = rows.setdefault(m["concept"], {
                "concept": m["concept"], "unit": m["unit"],
                "method_version": m["method_version"],
                "values": [], "grey_reason": None, "source": None})
            if m["value"] is not None:
                row["values"].append(m["value"])
                if m.get("source") == "manual":
                    row["source"] = "manual"
            elif row["grey_reason"] is None and m["reason"]:
                row["grey_reason"] = m["reason"]
    return sorted(rows.values(), key=lambda r: r["concept"])


def render_industry_metric_rows(rows: list[dict]) -> list[str]:
    """Строки физических метрик: серые показывают недостающий вход,
    manual-источник виден рендеру (N8)."""
    lines = []
    for r in rows:
        if r["values"]:
            value = f"{sorted(r['values'])[len(r['values']) // 2]:g}"
            mark = " [manual]" if r["source"] == "manual" else ""
            lines.append(f"  {r['concept']}: {value} {r['unit']}"
                         f" n={len(r['values'])}{mark}"
                         f" ({r['method_version']})")
        else:
            reason = r["grey_reason"] or "no_data"
            mark = " [manual]" if r["source"] == "manual" else ""
            lines.append(f"  {r['concept']}: — ({reason}){mark}"
                         f" ({r['method_version']})")
    return lines


def industry_rows(repos, sector: str, as_of: Optional[str] = None) -> dict:
    """Экран «Отрасль» (ТЗ-22 J7): квартили по мерам сектора, валюта,
    в которой заявлена мера (J1), кто вложился. Чистая функция:
    только чтение репозиториев; curses красит render_industry."""
    as_of = as_of or _today()
    version = repos.peer_set.version_at(sector, as_of)
    if version is None:
        return {"sector": sector, "as_of": as_of, "version": None,
                "verified": None, "members": [], "rows": []}
    built = build_sector_aggregates(repos, sector, as_of, _SECTOR_MEASURES)
    members = repos.peer_set.member_snapshots_at(
        version["peer_set_version_id"], as_of)
    contributing = sorted(iid for iid, sid in members.items() if sid)
    rows = [{
        "concept": a.concept, "n": a.n,
        "p25": a.p25, "median": a.median, "p75": a.p75,
        "currency": a.currency, "null_reason": a.null_reason,
        "reason_counts": a.reason_counts,
        # ТЗ-97 Q8: за какие периоды сравнение и кто вне окна — экран
        # обязан показать это и при отказе, и при числе
        "period_from": a.period_from, "period_to": a.period_to,
        "excluded": dict(a.excluded), "period_note": period_note(a),
        # ТЗ-102 M4: чем именно «мало участников» — составом или
        # пустыми значениями; экран обязан сказать это числом
        "shortfall_note": shortfall_note(a),
    } for a in built["aggregates"]]
    return {"sector": sector, "as_of": as_of,
            "version": version["version"],
            "peer_set_version_id": version["peer_set_version_id"],
            "verified": built["verified"],
            "members": contributing, "rows": rows}


def render_industry(screen: dict) -> list[str]:
    """Строки экрана «Отрасль» (чистая функция). Смешение валют и
    нехватка участников рендерятся отказом по имени, не числом."""
    if screen["version"] is None:
        return [f"Сектор {screen['sector']}: нет версии на "
                f"{screen['as_of']}"]
    lines = [f"Сектор {screen['sector']} — версия {screen['version']} "
             f"на {screen['as_of']}"
             + ("" if screen["verified"] else " [набор не подтверждён]"),
             f"внесли: {', '.join(screen['members']) or '—'}"]
    for r in screen["rows"]:
        # ТЗ-97 Q8: «за какие периоды» и «кто вне окна» — и у числа, и
        # у отказа: без этого агрегат выглядит ответом на весь набор
        # ТЗ-102 M4: сюда же и «участников N, значение меры есть у K»
        notes = [p for p in (r.get("shortfall_note"), r.get("period_note"))
                 if p]
        note = f" [{'; '.join(notes)}]" if notes else ""
        if r["null_reason"]:
            counts = ", ".join(f"{k}={v}" for k, v
                               in sorted(r["reason_counts"].items()))
            suffix = f" ({counts})" if counts else ""
            lines.append(f"  {r['concept']}: {r['null_reason']} "
                         f"n={r['n']}{suffix}{note}")
        else:
            currency = f" {r['currency']}" if r["currency"] else ""
            lines.append(f"  {r['concept']}: {r['p25']} / "
                         f"{r['median']} / {r['p75']} n={r['n']}"
                         f"{currency}{note}")
    return lines


def render_list(rows: list[dict]) -> list[str]:
    """Строки для отрисовки экрана «Список» (чистая функция)."""
    lines = []
    for row in rows:
        mark = {"verified": " [peer verified]",
                "unverified": " [peer не подтверждён]"}.get(
            row["peer_status"], "")
        cells = "|".join(row["coverage_cells"])
        lines.append(f"{row['market']:<4} {row['ticker']:<10} "
                     f"{row['instrument_id']:<14} "
                     f"{row['as_of']:<12} [{cells}]{mark}")
    return lines


def render_card(card: dict) -> list[str]:
    """Строки для отрисовки «Карточки» (чистая функция)."""
    lines = [f"Инструмент: {card['instrument_id']}"
             + (f"  (peer {card['peer_status']})"
                if card["peer_status"] else ""),
             "Меры:"]
    for m in card["measures"]:
        line = f"  {m['concept']}: {m['value']} {m['unit']}"
        # ТЗ-22 J1: абсолютное число несёт свою валюту; смешение
        # рендерится отказом, а не числом
        if m.get("currency"):
            line += f" [{m['currency']}]"
        if m.get("source_kind") == "manual":
            # ручное число видно с первого взгляда; непроверенное —
            # с явной пометкой недоверия (ТЗ-20 L8)
            line += " [manual]"
            if m.get("unverified"):
                line += " [manual · НЕ проверено]"
        if m["null_reason"]:
            line += f" ({m['null_reason']})"
        lines.append(line)
    lines.append("Покрытие:")
    for block in card["coverage"]:
        reason = f" — {block['reason']}" if block["reason"] else ""
        lines.append(f"  {block['block']}: {block['status']}{reason}")
    lines.append("Governance (пять цветов, не сворачиваются):")
    for g in card["governance"]:
        line = f"  {g['indicator']}: {g['color']}"
        # ТЗ-97 Q2 (ТЗ-73 T3, P8): у серого цвета — слово причины и
        # команда, которой строка закрывается; ядро их уже посчитало.
        if g["color"] == "gray" and g.get("reason"):
            from rusterm.core.governance import (grey_closing,
                                                 grey_reason_text)
            words = grey_reason_text(g["reason"])
            door = grey_closing(g["indicator"], card["instrument_id"],
                                g["reason"])
            line += f" — {words} [{door}]"
        lines.append(line)
    return lines


# ── Экран «Разговор» (ТЗ-42 I3, Q10): ходы, цитаты, стоимость ───────────

def chat_screen(session: dict, calls_made: int) -> dict:
    """Собрать экран разговора из сохранённой/текущей расшифровки:
    ходы (роль, текст), цитаты ответов, строка стоимости (вызовы).
    session — словарь chat_transcript.get(): model, turns, calls.
    Чистая функция: ничего не читает и не пишет."""
    turns: list[dict] = []
    for turn in session.get("turns", []):
        turns.append({
            "role": turn["role"],
            "text": turn.get("text") or "",
            "rejected": bool(turn.get("rejected")),
            "citations": list(turn.get("citations") or []),
        })
    return {"model": session.get("model", ""),
            "calls": session.get("calls", calls_made),
            "turns": turns}


def render_chat(screen: dict) -> list[str]:
    """Строки экрана разговора: ходы с цитатами и строка стоимости.
    Ни одной управляющей последовательности — рисование в app.py."""
    lines: list[str] = []
    for turn in screen["turns"]:
        mark = {"user": "вы", "assistant": "модель",
                "tool": "инструмент"}.get(turn["role"], turn["role"])
        for raw in (turn["text"] or "").splitlines() or [""]:
            line = f"{mark}: {raw}"
            if turn["rejected"]:
                line = f"{line} [ОТКЛОНЕНО]"
            lines.append(line)
        for citation in turn["citations"]:
            lines.append(f"   цитата: {citation}")
    lines.append(f"вызовов: {screen['calls']}; модель: {screen['model']}")
    return lines


def measure_summary(rows) -> dict | None:
    """ТЗ-72 S5: «источник почти ничего не даёт по этой бумаге».

    rows — пары (значение, null_reason): карточка card_rows или сырые
    меры get_measures, одна реализация для окна и CLI. Правило: мер со
    значением строго меньше четверти карточки. Причина сводки — самый
    частый первый токен словарных отказов (выдумки нет); меры без
    причины не участвуют в подсчёте причин. Сырая карточка — None.
    """
    total = len(rows)
    if total == 0:
        return None
    valued = 0
    counts: dict[str, int] = {}
    for value, reason in rows:
        if value is not None and value != NULL_MARK:
            valued += 1
            continue
        if reason:
            token = reason.split(":", 1)[0]
            counts[token] = counts.get(token, 0) + 1
    if valued * 4 >= total:
        return None
    dominant = (min(counts, key=lambda t: (-counts[t], t))
                if counts else None)
    return {"valued": valued, "total": total,
            "dominant_reason": dominant,
            "reason_count": counts.get(dominant, 0) if dominant else 0}


def measure_summary_line(summary: dict) -> str:
    """Слова сводки S5: одна формулировка для окна и CLI."""
    tail = (f"; массовый отказ: {summary['dominant_reason']}"
            f" ({summary['reason_count']})"
            if summary.get("dominant_reason") else "")
    return (f"источник почти ничего не даёт по этой бумаге: мер со "
            f"значением {summary['valued']} из {summary['total']}{tail}")


# ТЗ-76 W3: год ячейки истории — год периода меры, а не год прогона.
# as_of снапшота остаётся фолбэком, когда периода нет, и фолбэк этот
# виден: окно помечает клетку как отнесённую к году прогона.
HISTORY_BASIS_PERIOD = "period"
HISTORY_BASIS_RUN_YEAR = "run_year"


def _period_year(value) -> Optional[str]:
    """Год из даты периода: первые четыре ASCII-цифры, иначе None."""
    text = str(value or "").strip()
    head = text[:4]
    if len(head) == 4 and head.isascii() and head.isdigit():
        return head
    return None


def _sub_annual_period(start, end) -> bool:
    """Поток короче ~10 месяцев (квартал, полугодие, 9 месяцев)."""
    if not start or not end or start == end:
        return False
    try:
        days = (datetime.date.fromisoformat(end)
                - datetime.date.fromisoformat(start)).days
    except (TypeError, ValueError):
        return False
    return 0 < days < 300


def _history_walk(repos, instrument_id: str):
    """Один обход ВСЕХ снапшотов инструмента: значения по годам и
    основание года каждой клетки (ТЗ-76 W3).

    Год берётся из периода меры: period_end, при его отсутствии
    period_start. as_of снапшота — только фолбэк для меры без периода
    (пересобранная сегодня база иначе схлопывает всю историю в один
    столбец года запуска). В пределах года побеждает старшая версия
    снапшота: снапшоты идут по возрастанию версии, позднейший
    перезаписывает клетку."""
    values: dict[str, dict[str, float]] = {}
    basis: dict[str, dict[str, str]] = {}
    # PRODUCT.md С2 (06.10, сверка с Yahoo): колонка года — финансовый
    # год. Снапшот на конец года (`history`) побеждает снапшот, снятый
    # посреди года, а клетка позже последнего закрытого года — это
    # «сейчас», не год: у DELL «2026» показывало капитализацию октября
    # (344 млрд) вместо конца FY2026 (75 млрд). Без годовых концов в
    # фактах (фикстуры, демо) правило молчит — прежний порядок версий.
    instrument = repos.instrument.get_instrument(instrument_id)
    ends = (set(repos.snapshot.annual_period_ends(instrument.issuer_id))
            if instrument is not None else set())
    last_closed = _period_year(max(ends)) if ends else None
    year_end_cell: dict[str, dict[str, bool]] = {}
    snapshots = repos.snapshot.snapshots_of_instrument(instrument_id)
    # пересборка (`history --rebuild`) кладёт новую версию снапшота на
    # КОНЕЦ ГОДА: старая версия той же даты не даёт ни одной клетки, иначе
    # мера, которую новые правила честно не считают, доживала бы из старых
    # (AT&T: валовая прибыль по отозванному тегу себестоимости, 08.10).
    # Снапшоты посреди года не трогаются: один прогон законно кладёт на
    # одну дату снапшоты разных периодов (ТЗ-76 W3)
    latest_at = {}
    for s in snapshots:
        latest_at[s["as_of"]] = max(latest_at.get(s["as_of"], 0),
                                    s["version"])
    for s in snapshots:
        if s["as_of"] in ends and s["version"] != latest_at[s["as_of"]]:
            continue
        run_year = _period_year(s["as_of"])
        at_year_end = s["as_of"] in ends
        for m in repos.snapshot.get_measures(s["snapshot_id"]):
            if m[4] is None:
                continue
            try:
                val = float(m[4])
            except (TypeError, ValueError):
                continue
            if _sub_annual_period(m[6], m[7]):
                # квартал в годовой колонке — не год: у BAC клетка
                # «2026» показывала asset_turnover за Q2 (0,009 против
                # 0,03 у всех лет); аналоги держат в колонке года только
                # годовой период или остаток
                continue
            year = _period_year(m[7]) or _period_year(m[6])
            why = HISTORY_BASIS_PERIOD
            if year is None:
                year, why = run_year, HISTORY_BASIS_RUN_YEAR
            if year is None:
                continue
            if last_closed and not at_year_end and year > last_closed:
                continue
            if (year_end_cell.get(year, {}).get(m[3])
                    and not at_year_end):
                continue
            values.setdefault(year, {})[m[3]] = val
            basis.setdefault(year, {})[m[3]] = why
            year_end_cell.setdefault(year, {})[m[3]] = at_year_end
    return values, basis


def measure_history_by_year(repos, instrument_id: str) -> dict[str, dict[str, float]]:
    """ТЗ-72 Д1: история мер по годам из ВСЕХ сохранённых снапшотов
    инструмента.

    Форма результата — ``{год: {концепт: значение}}``: год — период
    меры (ТЗ-76 W3), в пределах года побеждает старшая версия
    снапшота. Эту же форму словами читает measure_table_rows окна
    (ТЗ-75 V1) — обе докстроки называют её одинаково, чтобы
    расхождение не вернулось. Используется окном и CLI/TUI — одна
    реализация для всех лиц."""
    return _history_walk(repos, instrument_id)[0]


def measure_history_basis(repos, instrument_id: str) -> dict[str, dict[str, str]]:
    """Основание года для каждой клетки истории — ``{год: {концепт:
    "period"|"run_year"}}``, той же формой, что значения (ТЗ-76 W3).

    «run_year» значит, что у меры нет периода и клетка отнесена к году
    прогона по as_of снапшота: интерфейс обязан показать это, а не
    выдавать год запуска за год отчётности."""
    return _history_walk(repos, instrument_id)[1]
