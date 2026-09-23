"""Слой данных десктопа (TASK-C1): только чтение, без Qt.

Всё содержимое окна собирается здесь через ту же модель экранов,
что у TUI (rusterm/tui/model.py), и через репозитории — теми же
дверями, которыми ходит CLI. Ни SQL, ни сети, ни формул: окно не
считает, не пишет в базу и не создаёт каталог данных (B35/B40 —
`open_readonly` на отсутствующий каталог отвечает (paths, None),
а не строит его).

История мер по годам: слой данных её не отдаёт, потому что её не
отдаёт никто — снапшот хранит одну величину на меру (свежайший
период), а пересчитывать формулы по периодам интерфейсу запрещено
(ADR-0009). Годовые колонки честно говорят «нет данных»; дверь
истории — вопрос к координатору (Disputed в REPORT-C1).
"""
from __future__ import annotations

import csv
import datetime
import io
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from rusterm.core.export import snapshot_to_csv, snapshot_to_md
from rusterm.store.db import current_schema_version, open_connection
from rusterm.store.paths import AppPaths
from rusterm.tui import model as tui_model

# Отказ ячейки таблицы: словами, не пустотой и не прочерком (C1.2)
NO_DATA = "нет данных"

# Инструменты без peer set группируются честно названной строкой
NO_SECTOR = "без отрасли"

# Сколько годовых колонок просит окно по умолчанию: это ПОТОЛОК, а не
# минимум (ТЗ-81 B2) — пустую колонку рисовать нельзя. Сверх этого
# число решает ширина окна (C1.2)
DEFAULT_YEAR_COLUMNS = 4


def open_readonly(root: str | Path) -> tuple[AppPaths, Optional[sqlite3.Connection]]:
    """Открыть каталог данных, НЕ создавая его и НЕ мигрируя (B35/B40).

    Базы нет — (paths, None): читать нечего, и это не ошибка.
    Миграции не применяются: окно только читает, обновление схемы —
    путь пишущих команд CLI.
    """
    paths = AppPaths.from_root(root)
    if not paths.db_path.exists():
        return paths, None
    return paths, open_connection(paths)


def empty_base_message(paths: AppPaths) -> str:
    """Что сказать вместо пустого окна, когда читать нечего."""
    return (f"каталога данных нет: {paths.root}; выполните "
            "rusterm init, затем rusterm add и rusterm ingest")


def empty_watchlist_message() -> str:
    return ("список наблюдения пуст: добавьте компании командой "
            "rusterm add --ticker … и соберите их rusterm ingest")


def header_info(repos) -> dict:
    """Шапка окна: версия схемы и запросы провайдеров за сегодня.

    Схема — та же дверь, что у rusterm status (current_schema_version,
    БЕЗ тихой миграции: окно читает). «Запросов сегодня» — агрегат
    хранилища (requests_used_today, ТЗ-61 F1): одно число из одной
    двери для окна и rusterm status, окно не суммирует само.
    """
    return {"schema_version": current_schema_version(repos.conn)
            if hasattr(repos, "conn") else None,
            "requests_today": repos.metrics.requests_used_today()}


# ── Левая колонка: поиск и дерево отраслей (C1.1) ────────────────────────

def sidebar_companies(repos, watchlist_id: Optional[str] = None) -> list[dict]:
    """Компании списка наблюдения с названием эмитента и сектором.

    Строки берутся из tui-модели (list_rows); название — через ту же
    дверь репозитория, какой его читает CLI (get_issuer; list_rows сам
    читает get_instrument этого же инструмента), сектор — peer set
    инструмента (peer_set_for_instrument), как экран «o» в TUI.
    Ничего не досчитано: это выборки, не вычисления.
    """
    rows = []
    for row in tui_model.list_rows(repos, watchlist_id):
        instrument = repos.instrument.get_instrument(row["instrument_id"])
        name = None
        if instrument is not None:
            issuer = repos.instrument.get_issuer(instrument.issuer_id)
            name = issuer.name if issuer else None
        peer = repos.peer_set.peer_set_for_instrument(row["instrument_id"])
        rows.append({
            "instrument_id": row["instrument_id"],
            "ticker": row["ticker"],
            "market": row["market"],
            "name": name,
            "sector": peer["peer_set_id"] if peer else None,
            "peer_status": row["peer_status"],
        })
    return rows


NO_WATCHLISTS_HINT = ("соберите список одной командой: "
                      "rusterm watchlist create main --name main")


def all_instruments(repos) -> list[dict]:
    """ТЗ-75 S4: списков наблюдения нет — те же строки боковой панели
    по ВСЕМ инструментам базы (форма как у sidebar_companies), окно
    показывает инструменты, а не пустоту."""
    rows = []
    for iid in repos.instrument.list_instruments():
        instrument = repos.instrument.get_instrument(iid)
        name = None
        if instrument is not None:
            issuer = repos.instrument.get_issuer(instrument.issuer_id)
            name = issuer.name if issuer else None
        peer = repos.peer_set.peer_set_for_instrument(iid)
        ref = repos.instrument.ticker_for_instrument(iid, _today())
        rows.append({
            "instrument_id": iid,
            "ticker": (ref or {}).get("ticker") if isinstance(ref, dict)
            else None,
            "market": (ref or {}).get("market") if isinstance(ref, dict)
            else None,
            "name": name,
            "sector": peer["peer_set_id"] if peer else None,
            "peer_status": None,
        })
    return rows


def empty_base_instruments_message() -> str:
    """ТЗ-75 S4: инструментов нет вовсе — первая команда целиком, с
    подстановкой, без многоточий (как в ТЗ-61 F4)."""
    return ("в базе нет инструментов: создайте демо-базу одной "
            "командой rusterm demo или добавьте первую бумагу: "
            "rusterm add --ticker AAPL --market US")


def matches_query(company: dict, query: str) -> bool:
    """Фильтр поиска: по тикеру и по названию, без учёта регистра."""
    query = (query or "").strip().casefold()
    if not query:
        return True
    ticker = (company.get("ticker") or "").casefold()
    name = (company.get("name") or "").casefold()
    return query in ticker or query in name


def sector_tree(companies: list[dict],
                query: str = "") -> list[dict]:
    """Дерево «отрасль → компании» по текущему поиску.

    При непустом поиске в дерево входят только совпадения; отрасли
    упорядочены по алфавиту, компании внутри — по тикеру. Компании
    без peer set — в честно названной группе, не выброшены.
    """
    groups: dict[str, list[dict]] = {}
    for company in companies:
        if not matches_query(company, query):
            continue
        sector = company.get("sector") or NO_SECTOR
        groups.setdefault(sector, []).append(company)
    tree = []
    for sector in sorted(groups):
        members = sorted(groups[sector], key=lambda c: c["ticker"])
        tree.append({"sector": sector, "companies": members})
    return tree


def expanded_sectors(tree: list[dict], query: str,
                      pinned: set[str] | None = None) -> set[str]:
    """Какие отрасли раскрыты: согласование поиска и дерева (C1.1).

    Поиск пуст — раскрыты только закреплённые пользователем отрасли
    (состояние переживает выбор компании). Поиск непуст — раскрыты
    все отрасли с совпадениями, остальные свёрнуты.
    """
    if (query or "").strip():
        return {node["sector"] for node in tree}
    return set(pinned or ())


# ── Центр: таблица «сейчас плюс годы истории» (C1.2) ─────────────────────

def format_value(value) -> str:
    """Число для ячейки таблицы: 4 знака после точки, без хвостов.

    Не число (текст меры) показывается как есть; полный precision
    остаётся в панели источника и экспорте — здесь только отображение.
    """
    if value is None:
        return NO_DATA
    try:
        return f"{float(value):.4f}".rstrip("0").rstrip(".") or "0"
    except (TypeError, ValueError):
        return str(value)


def history_years(card: dict, count: int = DEFAULT_YEAR_COLUMNS,
                  history: dict | None = None) -> list[str]:
    """Годовые колонки: только те годы, где хотя бы одна мера имеет значение.

    ТЗ-81 B2: правило ТЗ-72 Д1 («пустую колонку не рисуют») распространено
    на частично пустую таблицу. Прежняя версия выдавала ровно `count`
    колонок от года самого свежего периода вниз и додумывала текущий год,
    когда периодов нет вовсе, — на живой базе пользователя это четыре
    колонки, из них заполнена одна.

    `count` — потолок (окно считает его из ширины), а не минимум: один год
    законен, четыре пустых — нет. Значений нет ни в одном году — колонок
    нет, и вызывающий обязан сказать это словами (`suggestion`).
    """
    concepts = {m.get("concept") for m in card.get("measures", [])}
    filled = [year for year, cells in (history or {}).items()
              if any(concept in concepts for concept in cells)]
    return sorted(filled, reverse=True)[: max(count, 1)]


def snapshot_span(repos, instrument_id: str) -> Optional[tuple[str, str]]:
    """Границы дат снапшотов бумаги — через дверь store (I10: SQL живёт
    в rusterm/store, здесь только чтение её результата)."""
    dates = sorted({s["as_of"] for s in
                    repos.snapshot.snapshots_of_instrument(instrument_id)
                    if s["as_of"]})
    return (dates[0], dates[-1]) if dates else None


def _years_word(n: int) -> str:
    """Склонение числа лет: 1 год, 2 года, 5 лет; 11–14 — лет."""
    if 11 <= n % 100 <= 14:
        return "лет"
    return {1: "год", 2: "года", 3: "года", 4: "года"}.get(n % 10, "лет")


def history_note(repos, instrument_id: str, shown_years: int) -> Optional[str]:
    """Почему лет ровно столько, сколько видно (ТЗ-81 B2): число колонок и
    границы снапшотов из самой базы, не константа. Даты сказать нечем —
    строки нет."""
    span = snapshot_span(repos, instrument_id)
    if span is None:
        return None
    lo, hi = span
    dates = (f"снапшот от {lo}" if lo == hi
             else f"снапшоты с {lo} по {hi}")
    return f"история за {shown_years} {_years_word(shown_years)}: {dates}"


def measure_history(repos, instrument_id: str) -> dict[str, dict[str, float]]:
    """ТЗ-72 Д1: та же дверь, что у CLI/TUI — не пустой заглушка.

    Форма — ``{год: {концепт: значение}}`` (ТЗ-75 V1); ровно эту форму
    читает measure_table_rows. Год ячейки — период меры, а не год
    прогона (ТЗ-76 W3)."""
    return tui_model.measure_history_by_year(repos, instrument_id)


def measure_history_basis(repos, instrument_id: str) -> dict[str, dict[str, str]]:
    """Основание года клетки истории: ``{год: {концепт: "period"|
    "run_year"}}`` — та же форма, что у значений (ТЗ-76 W3)."""
    return tui_model.measure_history_basis(repos, instrument_id)


# Пометка клетки, отнесённой к году прогона, а не к году отчёта:
# молча подставлять год запуска под столбец нельзя (ТЗ-76 W3)
RUN_YEAR_MARK = " · год прогона"


NO_HISTORY_HINT = ("истории мер нет: посчитайте ряд одной командой — "
                   "rusterm snapshot --instrument {instrument_id}")


def measure_table_rows(repos, instrument_id: str,
                       year_count: int = DEFAULT_YEAR_COLUMNS) -> dict:
    """Строки центральной таблицы из card_rows: сейчас + годы.

    Ячейка без значения — слова «нет данных», и в текущей колонке, и
    в исторических; причина (какой концепт не подан) — в панели
    источника по клику, не в ячейке.

    История приходит формой ``{год: {концепт: значение}}`` — ячейка
    года N читается как history[год][концепт] (ТЗ-75 V1), а год —
    период меры (ТЗ-76 W3): ячейка, отнесённая к году прогона потому,
    что у меры нет периода, помечена ``RUN_YEAR_MARK``. Годовые
    колонки — только годы со значением хотя бы у одной меры (ТЗ-81 B2,
    правило ТЗ-72 Д1 и для частично пустой таблицы); ``year_count`` —
    потолок, а не минимум. Колонок нет вовсе — ``suggestion`` несёт
    исполнимую строку «посчитать ряд одним действием»; колонок меньше
    потолка — ``history_note`` говорит словами, почему."""
    card = tui_model.card_rows(repos, instrument_id)
    history = measure_history(repos, instrument_id)
    basis = measure_history_basis(repos, instrument_id)
    years = history_years(card, year_count, history)
    suggestion = None if years else NO_HISTORY_HINT.format(
        instrument_id=instrument_id)
    note = (history_note(repos, instrument_id, len(years))
            if years and len(years) < max(year_count, 1) else None)
    summary = tui_model.measure_summary(
        [(m.get("value"), m.get("null_reason"))
         for m in card["measures"]])
    summary_line = (tui_model.measure_summary_line(summary)
                    if summary else None)
    rows = []
    for measure in card["measures"]:
        current = measure["value"]
        has_value = current is not None and current != tui_model.NULL_MARK
        year_cells = {}
        for year in years:
            point = history.get(year, {}).get(measure["concept"])
            if point is None:
                year_cells[year] = NO_DATA
                continue
            cell = format_value(point)
            if (basis.get(year, {}).get(measure["concept"])
                    == tui_model.HISTORY_BASIS_RUN_YEAR):
                cell += RUN_YEAR_MARK
            year_cells[year] = cell
        period_end = measure.get("period") or ""
        rows.append({
            "concept": measure["concept"],
            "current": format_value(current) if has_value else NO_DATA,
            "years": year_cells,
            "has_value": has_value,
            "null_reason": measure.get("null_reason"),
            "unit": measure.get("unit"),
            "measure": measure,
            "stale_mark": staleness_mark(period_end),
        })
    instrument = repos.instrument.get_instrument(instrument_id)
    name = None
    if instrument is not None:
        issuer = repos.instrument.get_issuer(instrument.issuer_id)
        name = issuer.name if issuer else None
    ref = repos.instrument.ticker_for_instrument(instrument_id, _today())
    return {
        "instrument_id": instrument_id,
        "ticker": ref["ticker"] if ref else instrument_id,
        "name": name,
        "measures": rows,
        "years": years,
        "card": card,
        "suggestion": suggestion,
        "history_note": note,
        "summary": summary,
        "summary_line": summary_line,
    }


def _today() -> str:
    return datetime.date.today().isoformat()


# ── Диаграммы (C1.3): спецификации считаются без Qt ─────────────────────

CHART_KINDS = ("line", "bars", "candles", "box", "radar")

CHART_KIND_LABELS = {"line": "линия", "bars": "столбики",
                     "candles": "свечи", "box": "box-plot",
                     "radar": "радар"}

# Свечи требуют open/high/low/close; хранилище держит только close
# (PriceRepo, ТЗ-23 K1). Рисовать псевдо-OHLC из close — выдумка,
# поэтому тип честно отказывается словами.
CANDLES_REFUSAL = ("свечи: нет данных — хранилище котировок держит "
                   "только close (open/high/low не собираются)")

RATIO_UNIT = "ratio"


def chart_spec(kind: str, table: dict, industry_screen: dict | None,
               concept: str | None = None) -> dict:
    """Спецификация диаграммы по типу: чистые данные, рисует charts.py.

    concept — выбранная в переключателе мера (нет — первая из таблицы).
    Ни один тип не выдумывает точек: годы без значения не попадают в
    точки (разрыв линии, не ноль); тип без честных данных возвращает
    kind="message" с причиной словами, а не пустое полотно.
    """
    if kind == "candles":
        return {"kind": "message", "text": CANDLES_REFUSAL}
    if kind in ("line", "bars"):
        return _series_spec(kind, table, concept)
    if kind == "box":
        return _box_spec(table, industry_screen, concept)
    if kind == "radar":
        return _radar_spec(table)
    raise ValueError(f"неизвестный тип диаграммы: {kind}")


def chosen_measure_table_row(table: dict, concept: str) -> dict | None:
    for row in table["measures"]:
        if row["concept"] == concept:
            return row
    return None


def _series_spec(kind: str, table: dict,
                 concept: str | None = None) -> dict:
    """Линия/столбики выбранной меры: год со значением — точка, год
    без значения — None (разрыв, не ноль). Истории нет — все None, и
    спецификация честно сообщает «нет данных».

    Пометка «год прогона» — аннотация отображения: клетка с ней
    остаётся значением и рисуется точкой (ТЗ-76 W3), пометка не
    отнимает данных."""
    concepts = [row["concept"] for row in table["measures"]]
    if not concepts:
        return {"kind": "message", "text": "нет данных"}
    concept = concept if concept in concepts else concepts[0]
    row = chosen_measure_table_row(table, concept)
    history = row["years"] if row else {}
    years, values = [], []
    for year in table["years"]:
        text = history.get(year, NO_DATA)
        years.append(int(year))
        if text == NO_DATA:
            values.append(None)
            continue
        if text.endswith(RUN_YEAR_MARK):
            text = text[:-len(RUN_YEAR_MARK)]
        try:
            values.append(float(text))
        except ValueError:
            values.append(None)
    if all(v is None for v in values):
        return {"kind": "message", "text": "нет данных",
                "concept": concept}
    return {"kind": kind, "concept": concept, "years": years,
            "values": values}


def _box_spec(table: dict, industry_screen: dict | None,
              concept: str | None = None) -> dict:
    """Box-plot по peer set: квартили экрана «Отрасль» (industry_rows)
    для выбранной меры. Экрана нет или мера не агрегируется — отказ
    словами с причиной из данных."""
    if not industry_screen or industry_screen.get("version") is None:
        sector = (industry_screen or {}).get("sector")
        return {"kind": "message",
                "text": f"нет данных: у сектора {sector or '—'} нет версии"
                        f" на {_today()}"}
    concepts = [row["concept"] for row in table["measures"]]
    concept = concept if concept in concepts else (concepts[0] if concepts
                                                   else None)
    for row in industry_screen.get("rows", []):
        if row["concept"] == concept:
            if row.get("null_reason"):
                return {"kind": "message", "text":
                        f"нет данных: {row['null_reason']}"}
            return {"kind": "box", "concept": concept,
                    "p25": row["p25"], "median": row["median"],
                    "p75": row["p75"], "n": row["n"]}
    return {"kind": "message",
            "text": f"нет данных: {concept or '—'} не агрегируется"
                    f" по сектору {industry_screen['sector']}"}


def _radar_spec(table: dict) -> dict:
    """Радар по БЕЗРАЗМЕРНЫМ мерам (unit == 'ratio'): ось на меру,
    значение — текущее. Абсолютные меры (USD, index) на один радар
    не ложатся — они не выдумывают ось, а не попадают на неё."""
    axes = []
    for row in table["measures"]:
        if row["unit"] != RATIO_UNIT or not row["has_value"]:
            continue
        axes.append({"concept": row["concept"],
                     "value": float(row["current"])})
    if not axes:
        return {"kind": "message",
                "text": "нет данных: нет безразмерных мер со значением"}
    return {"kind": "radar", "axes": axes}


# ── Низ: разговор (C1.4) ────────────────────────────────────────────────

def chat_unavailable_reason(client) -> Optional[str]:
    """Почему модель не ответит: причина словами, не молчание.

    make_chat_client без ключа/тарифа возвращает клиента-отказника
    (core/llm.py, _RefusingChatClient): его причина лежит в _reason и
    наружу отдаётся только ответом. Читаем атрибут — это локальный
    объект без сети; живой клиент атрибута не имеет (None — спрашивать
    можно, отказ, если случится, покажет сам ask словами).
    """
    reason = getattr(client, "_reason", None)
    return str(reason) if reason else None


# ── Peer set и отрасль (TASK-C3) ────────────────────────────────────────

def peer_screen(repos, instrument_id: str,
                as_of: Optional[str] = None) -> dict:
    """Peer set выбранной компании с правилом отбора словами (C3.1).

    Слова правила собираются из констант и evaluate() ядра
    (rusterm/core/peers.py) — пороги импортируются, не копируются.
    Компании без набора — слова об этом, не пустота.
    """
    from rusterm.core import peers as peers_core
    peer = repos.peer_set.peer_set_for_instrument(instrument_id)
    if peer is None:
        return {"has_peer_set": False,
                "message": ("у компании нет peer set — сравнение с "
                            "конкурентами недоступно; наборы появляются "
                            "вручную или классификатором (ADR-0002)")}
    composition = repos.peer_set.composition(peer["peer_set_version_id"])
    status = peers_core.evaluate(peer["origin"], peer["approved"],
                                 [], composition["members"])
    verified = "подтверждён" if status.verified else "не подтверждён"
    rule = (f"правило: происхождение {peer['origin']}, {verified}; "
            f"перцентиль от {peers_core.PERCENTILE_MIN_PEERS} участников,"
            f" отраслевой агрегат от "
            f"{peers_core.AGGREGATE_MIN_PEERS}, дрейф состава больше "
            f"{peers_core.DRIFT_SUSPECT_THRESHOLD:.0%} — подозрение")
    members = []
    for iid in composition["members"]:
        ref = repos.instrument.ticker_for_instrument(
            iid, as_of or _today())
        members.append({"instrument_id": iid,
                        "ticker": ref["ticker"] if ref else iid,
                        "is_self": iid == instrument_id})
    return {"has_peer_set": True,
            "peer_set_id": peer["peer_set_id"],
            "version": peer["version"],
            "scope": composition["scope"],
            "markets": composition["markets"],
            "currencies": composition["currencies"],
            "rule": rule,
            "members": members,
            "verified": status.verified}


def industry_table_rows(screen: dict) -> list[dict]:
    """Строки таблицы отрасли (C3.3): квартили, n, пометка отказа.

    Строка с отказом получает явную пометку «отказ: причина» — при
    любой сортировке видно, почему у неё нет чисел; молчаливого
    провала вниз нет.
    """
    rows = []
    for r in screen.get("rows", []):
        if r.get("null_reason"):
            counts = ", ".join(f"{k}={v}" for k, v
                               in sorted(r.get("reason_counts", {})
                                         .items()))
            mark = f"отказ: {r['null_reason']}"
            if counts:
                mark += f" ({counts})"
            rows.append({"concept": r["concept"], "p25": NO_DATA,
                         "median": NO_DATA, "p75": NO_DATA, "n": r["n"],
                         "mark": mark, "refused": True})
        else:
            rows.append({"concept": r["concept"],
                         "p25": format_value(r["p25"]),
                         "median": format_value(r["median"]),
                         "p75": format_value(r["p75"]), "n": r["n"],
                         "mark": "", "refused": False})
    return rows


def industry_chart_spec(screen: dict,
                        concept: str | None = None) -> dict:
    """Одна диаграмма отрасли (C3.3): box-plot выбранной меры по
    квартилям экрана; мера не выбрана — первая чистая. Отказ меры —
    слова с причиной, не пустое полотно."""
    if screen.get("version") is None:
        return {"kind": "message",
                "text": f"нет данных: у сектора "
                        f"{screen.get('sector', '—')} нет версии на "
                        f"{screen.get('as_of', _today())}"}
    rows = screen.get("rows", [])
    chosen = None
    if concept is not None:
        chosen = next((r for r in rows if r["concept"] == concept), None)
        if chosen is None:
            return {"kind": "message",
                    "text": f"нет данных: {concept} не агрегируется "
                            f"по сектору {screen['sector']}"}
    else:
        chosen = next((r for r in rows if not r.get("null_reason")),
                      None)
        if chosen is None:
            return {"kind": "message",
                    "text": "нет данных: все меры отрасли под отказом"}
    if chosen.get("null_reason"):
        return {"kind": "message",
                "text": f"нет данных: {chosen['null_reason']}"}
    # квартили приходят из ядра строками (repr квантилей, ТЗ-22 J7);
    # полотно считает по числам — находка S1: живой агрегат ронял
    # отрисовку TypeError (str - str)
    def _num(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return {"kind": "box", "concept": chosen["concept"],
            "p25": _num(chosen["p25"]), "median": _num(chosen["median"]),
            "p75": _num(chosen["p75"]), "n": chosen["n"]}


def radar_vs_group_spec(table: dict, industry_screen: dict | None) -> dict:
    """Радар «компания против медианы группы» (C3.2).

    Ось — мера со значением у компании И с медианой группы; мера без
    данных компании не занижает медиану — она исключена (счётчик
    excluded_company), мера без агрегата группы — исключена тоже
    (excluded_group). Оба счётчика возвращаются словами в окно.
    """
    base = {"excluded_company": 0, "excluded_group": 0}
    if not industry_screen or industry_screen.get("version") is None:
        return {"kind": "message",
                "text": "нет данных: группа без версии агрегата",
                **base}
    group = {r["concept"]: r for r in industry_screen.get("rows", [])
             if not r.get("null_reason")}
    axes = []
    for row in table["measures"]:
        if row["unit"] != RATIO_UNIT:
            continue
        if not row["has_value"]:
            base["excluded_company"] += 1
            continue
        g = group.get(row["concept"])
        if g is None:
            base["excluded_group"] += 1
            continue
        axes.append({"concept": row["concept"],
                     "value": float(row["current"]),
                     "median": float(g["median"])})
    if not axes:
        return {"kind": "message",
                "text": ("нет данных: нет мер, сравнимых с группой "
                         f"(исключены — без данных компании: "
                         f"{base['excluded_company']},"
                         " без данных группы: "
                         f"{base['excluded_group']})"),
                **base}
    return {"kind": "radar_vs", "axes": axes, **base}


# ── Экспорт (TASK-C4): тот же код ядра, что у rusterm export ────────────

def export_snapshot_measures(repos, instrument_id: str) -> Optional[list]:
    """Меры последнего снапшота — те же записи, что читает
    `rusterm export`; экспорт не пересчитывает и не досчитывает.
    Снапшота нет — None, и это честный отказ, а не пустой файл."""
    sid = repos.snapshot.latest_snapshot_id(instrument_id)
    if sid is None:
        return None
    return repos.snapshot.get_measures(sid)


def source_cell(facts: list, shape: str = "table") -> str:
    """ТЗ-62 G3 -> ТЗ-64 J2: делегация единой реализации ядра."""
    from rusterm.core.export import format_source_cell
    return format_source_cell(facts, shape=shape)


def _source_cell(repos, measure_row) -> str:
    """ТЗ-64 J2: делегация единой реализации ядра."""
    from rusterm.core.export import source_lineage_cell
    return source_lineage_cell(repos, measure_row)


def export_table_csv(repos, instrument_id: str) -> Optional[str]:
    """C4.1+C4.3: csv видимой таблицы. Значения и отказы — байт-в-байт
    snapshot_to_csv ядра (тот же вызов, что у rusterm export: та же
    запись меры, те же слова отказа в колонке null_reason); колонка
    «источник» дописана desktop-слоем из lineage фактов. Снапшота
    нет — None."""
    measures = export_snapshot_measures(repos, instrument_id)
    if measures is None:
        return None
    base = snapshot_to_csv(measures)
    rows = list(csv.reader(io.StringIO(base)))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(rows[0])
    writer.writerow(rows[1] + ["источник"])
    for row, measure in zip(rows[2:], measures):
        writer.writerow(row + [_source_cell(repos, measure)])
    return out.getvalue()


def export_table_md(repos, instrument_id: str) -> Optional[str]:
    """C4.1+C4.3: md — текст ядра snapshot_to_md как есть (отказы —
    его сноски с теми же null_reason, что на панели источника
    экрана), плюс раздел «Источники» по мерам. Снапшота нет — None."""
    measures = export_snapshot_measures(repos, instrument_id)
    if measures is None:
        return None
    text = snapshot_to_md(measures)
    sources = [f"- {m[3]}: {_source_cell(repos, m) or 'входов нет'}"
               for m in measures]
    return text + "\nИсточники:\n" + "\n".join(sources) + "\n"


def chart_caption(table: dict, concept: str, period: str = "",
                  exported_at: str | None = None) -> str:
    """Подпись png (C4.2): эмитент, мера, период, дата выгрузки.
    Форма без источника: подпись не называет документ и хэш — для них
    в ней нет места (ТЗ-62 G3)."""
    who = " · ".join(part for part in (table.get("ticker"),
                                       table.get("name")) if part)
    return (f"{who} — {concept}; период {period or '—'}; "
            f"выгружено {exported_at or _today()}")


# ── Списки наблюдения (TASK-C5): те же двери ядра, что у CLI ────────────

def watchlist_choices(repos) -> list[dict]:
    """Списки наблюдения для переключателя (C5.1): id, имя, текущая
    версия, сколько бумаг. Прямо то, что печатает rusterm watchlist
    list, — в словарях."""
    return [{"watchlist_id": r["watchlist_id"], "name": r["name"],
             "version": r["version"], "member_count": r["member_count"]}
            for r in repos.watchlist.list_watchlists()]


def _next_version_full(repos, watchlist_id: str, action: str) -> str:
    """Правка состава = новая версия с полным новым составом (T10/T11)
    — тот же шаг, что у rusterm watchlist add."""
    current = repos.watchlist.current_version(watchlist_id)
    if current is None:
        raise ValueError(f"список {watchlist_id!r} не найден")
    version_id = repos.watchlist.new_version(
        str(uuid.uuid4()), watchlist_id, current["version"] + 1,
        action, None)
    repos.watchlist.copy_members(current["watchlist_version_id"],
                                 version_id)
    return version_id


def add_instrument(repos, watchlist_id: str, ticker: str, market: str,
                   as_of: str | None = None) -> dict:
    """C5.2: добавление бумаги тем же путём, что CLI watchlist add:
    разрешение тикера вторым резолвером не пахнет — только
    InstrumentRepo.resolve_ticker_candidates; правка = новая версия;
    строка аудита. Отказ — словами."""
    candidates = repos.instrument.resolve_ticker_candidates(
        ticker, market, as_of or _today())
    if not candidates:
        return {"ok": False,
                "message": (f"инструмента {ticker}.{market} нет в базе — "
                            f"добавьте бумагу командой "
                            f"rusterm add --ticker {ticker} "
                            f"--market {market}")}
    if len(candidates) > 1:
        return {"ok": False,
                "message": f"тикер {ticker!r} неоднозначен: "
                           f"{', '.join(candidates)}"}
    instrument_id = candidates[0]
    version_id = _next_version_full(repos, watchlist_id, "edit")
    repos.watchlist.add_member(version_id, instrument_id, None)
    repos.audit.log("watchlist_add", watchlist_id,
                    {"instrument": instrument_id}, True, "ok")
    version = repos.watchlist.current_version(watchlist_id)["version"]
    return {"ok": True, "instrument_id": instrument_id, "version": version}


def remove_instruments(repos, watchlist_id: str,
                       instrument_ids: list[str],
                       confirmed: bool = False) -> dict:
    """C5.2/C5.3: удаление бумаг. Одна бумага — как CLI watchlist
    remove (новая версия без неё, строка аудита). Больше одной —
    операция требует подтверждения (confirmed=True): без него отказ
    словами и ничего не меняется; с ним — ОДНА новая версия и ОДНА
    строка аудита на операцию. Прежняя версия остаётся доступной
    (репозиторий append-only)."""
    if not instrument_ids:
        return {"ok": False, "message": "нечего удалять"}
    if len(instrument_ids) > 1 and not confirmed:
        return {"ok": False,
                "message": (f"затронуто бумаг: {len(instrument_ids)} — "
                            "подтвердите операцию"),
                "needs_confirm": True}
    current = repos.watchlist.current_version(watchlist_id)
    if current is None:
        return {"ok": False,
                "message": f"список {watchlist_id!r} не найден"}
    # состав читается ДО создания новой версии: current_version уже
    # смотрит на неё, а та рождается пустой
    current_members = [m["instrument_id"] for m in
                       repos.watchlist.members(watchlist_id)]
    version_id = repos.watchlist.new_version(
        str(uuid.uuid4()), watchlist_id, current["version"] + 1,
        "edit", None)
    # ТЗ-62 G2: одна дверь переноса состава — та же, что у
    # одиночного удаления в CLI (copy_members_except), строка или
    # список
    repos.watchlist.copy_members_except(
        current["watchlist_version_id"], version_id, instrument_ids)
    if len(instrument_ids) == 1:
        repos.audit.log("watchlist_remove", watchlist_id,
                        {"instrument": instrument_ids[0]}, True, "ok")
    else:
        repos.audit.log("watchlist_bulk_remove", watchlist_id,
                        {"instruments": instrument_ids,
                         "count": len(instrument_ids)}, True, "ok")
    version = repos.watchlist.current_version(watchlist_id)["version"]
    return {"ok": True, "removed": instrument_ids, "version": version}


# ── Панель источника (TASK-C6): только то, что отдаёт модель ────────────

def raw_object_location(paths: AppPaths, sha256: str) -> dict:
    """C6.2: где лежит сохранённый ответ и есть ли он. raw/store/<2>/<sha>;
    файла нет — exists=False, окно скажет словами, а не упадёт."""
    from rusterm.store.raw_store import object_path
    path = object_path(paths.raw_store, sha256)
    return {"path": str(path), "exists": path.exists()}


def source_panel_view(repos, paths: AppPaths, measure_row: dict,
                      instrument_id: str | None = None,
                      stale_detail: bool = False) -> dict:
    """C6.1/C6.3: панель источника целиком из source_panel модели и
    репозиториев — ничего не досчитано. Строки: концепт, значение,
    метод, единица, документ с хэшем сохранённого ответа, период
    входного факта, путь к сырью; для отказа — причина и неподанный
    концепт по имени, плюс совет действия теми же словами, что в CLI
    (ТЗ-64 J3). Устаревшие входы свёрнуты в одну строку с числом
    (ТЗ-72 Д4); перечень целиком — только по stale_detail=True.
    open_target — путь к сырью первой записи, если файл есть; иначе
    None (окно скажет словами). stale_count — число устаревших входов."""
    from rusterm.core.export import refusal_advice
    panel = tui_model.source_panel(repos, measure_row["measure"])
    value_text = measure_row.get("current")
    if value_text is None:
        value_text = format_value(
            (measure_row.get("measure") or {}).get("value"))
    lines = [f"источник {panel['concept']}"
             f" ({panel['method_version']})",
             f"значение: {value_text}",
             f"единица: {measure_row.get('unit') or '—'}"]
    if measure_row["null_reason"]:
        lines.append(f"причина: {measure_row['null_reason']}")
        tail = measure_row["null_reason"].split(":", 1)[1].strip() \
            if ":" in measure_row["null_reason"] else ""
        if tail:
            lines.append(f"не подан: {tail} — подстановки нет: "
                         "значение строится только из поданных фактов")
        advice = (refusal_advice(tail, instrument_id or "")
                  if instrument_id and tail else None)
        if advice:
            lines.append(f"что делать: {advice}")
    open_target = None
    for source in panel["sources"]:
        sha = str(source["document"])
        fact = repos.fact.get_fact(source["fact_id"])
        period = fact["period_end"] if fact else ""
        loc = raw_object_location(paths, sha)
        kind = (source["locator"].get("kind", "?")
                if isinstance(source["locator"], dict) else "?")
        where = "сырье: " + loc["path"] if loc["exists"] \
            else "сырья нет в хранилище"
        lines.append(f"{kind}: {sha[:16]}… {where}"
                     + (f" (период входа {period})" if period else ""))
        if loc["exists"] and open_target is None:
            open_target = loc["path"]
    stale = panel["stale"]
    if stale and not stale_detail:
        freshest = max(s["period_end"] for s in stale)
        lines.append(f"устаревших входов: {len(stale)}, "
                     f"самый свежий {freshest}")
    else:
        for entry in stale:
            lines.append(f"{entry['marker']} ({entry['source_tag']})")
    return {"text": "\n".join(lines), "open_target": open_target,
            "panel": panel, "stale_count": len(stale)}


# ── Разговор (TASK-C7): расшифровки и счётчики из тех же мест ───────────

def chat_sessions(repos) -> list[dict]:
    """C7.1: прошлые разговоры, свежие сверху — через дверь перечня
    ChatTranscriptRepo.list_sessions: SQL живёт в rusterm/store, а не
    здесь (инвариант I10). Таблица та же, что читает
    rusterm export --chat."""
    return repos.chat_transcript.list_sessions()


def chat_transcript_lines(repos, session_id: str) -> list[str]:
    """C7.1: ходы разговора тем же get(), что rusterm export --chat.
    Разговора нет — слова, не пустота."""
    transcript = repos.chat_transcript.get(session_id)
    if transcript is None:
        return [f"разговора {session_id} нет"]
    lines = [f"разговор {session_id} · модель {transcript['model']}"
             f" · вызовов {transcript['calls']}"]
    who = {"user": "вы", "assistant": "модель", "tool": "инструмент",
           "system-note": "система"}
    for turn in transcript["turns"]:
        lines.append(f"{who.get(turn['role'], turn['role'])}: "
                     f"{turn['text']}")
    return lines


def llm_usage_line(repos) -> str:
    """C7.2: вызовы — из calls_totals(), того же места, что
    rusterm status. Ключ модели не показывается никогда: в строке
    только счётчики."""
    totals = repos.chat_transcript.calls_totals()
    per = ", ".join(f"{model}: {calls}" for model, calls
                    in sorted(totals["per_model"].items()))
    line = (f"вызовы: {totals['calls_total']}"
            f" (сегодня {totals['calls_today']})")
    return f"{line}; {per}" if per else line


# ── Качество данных (TASK-C8): порог — константа ядра ───────────────────

def measure_coverage(repos, instrument_id: str) -> dict:
    """C8.1: сколько мер зелёные из скольких и чем красные красны —
    счётчик один на все лица (tui_model.measure_reason_counts,
    ТЗ-61 F1): rusterm coverage --json и окно считают одним кодом.
    Снапшота нет — has_snapshot False, не пустота."""
    sid = repos.snapshot.latest_snapshot_id(instrument_id)
    reasons = tui_model.measure_reason_counts(repos, sid)
    total = (len(repos.snapshot.get_measures(sid)) if sid else 0)
    return {"has_snapshot": bool(sid),
            "green": total - sum(reasons.values()),
            "total": total,
            "reasons": reasons}


def staleness_mark(period_end: str, as_of: str | None = None) -> str:
    """C8.2: период старше порога давности снапшота — пометка словами.
    Порог — имя константы ядра (_STALE_LOOKBACK_DAYS, TASK-12 Y2),
    не число в коде окна."""
    from datetime import date as _date
    from rusterm.core.snapshot import _STALE_LOOKBACK_DAYS
    if not period_end:
        return ""
    try:
        anchor = _date.fromisoformat(as_of or _today())
        end = _date.fromisoformat(period_end)
    except (TypeError, ValueError):
        return ""
    if (anchor - end).days > _STALE_LOOKBACK_DAYS:
        return (f"устаревшая: период {period_end} старше порога "
                f"давности снапшота ({_STALE_LOOKBACK_DAYS} дн.)")
    return ""


def governance_view(card: dict) -> dict:
    """C8.3: governance — пять отдельных показателей, каждый со своим
    цветом без свёртки; цвет и расшифровка серых причин берутся из
    ядра (GREY_REASONS), окно цвет не вычисляет."""
    from rusterm.core.governance import GREY_REASONS
    rows = []
    for g in card.get("governance", []):
        rows.append({"indicator": g["indicator"], "color": g["color"],
                     "reason": g.get("reason") or "",
                     "note": GREY_REASONS.get(g.get("reason") or "", ""),
                     "lineage_ref": g.get("lineage_ref") or ""})
    return {"rows": rows}


# ── Настройки (TASK-C9): ключи без значений, лимиты, каталог ────────────

KEY_PURPOSE = {
    "RUSTERM_SEC_UA": "запросы к SEC (companyfacts) без него отклоняются"
                      " гейтом",
    "RUSTERM_LLM_PROVIDER": "какой поставщик модели используется",
    "RUSTERM_LLM_API_KEY": "разговор с моделью",
    "RUSTERM_LLM_MODEL": "какая модель отвечает",
    "RUSTERM_TWELVEDATA_KEY": "котировки twelvedata",
}


def channel_degrees(repos) -> dict:
    """ТЗ-60 E4 + ТЗ-61 F4: степень канала по рынку — считает
    репозиторий из того, что канал произвёл в этой базе; канал, которого
    нет без ключа, а ключа нет — «нет ключа» (те же слова, что у
    `rusterm markets`). Каталога нет — пустой словарь, окно молча
    показывает «—»."""
    from rusterm.markets import (MARKETS, channel_degree_label,
                                 provider_channel)
    from rusterm.providers import channel_key_env
    if repos is None:
        return {}
    produced = repos.instrument.channel_degrees()
    out: dict = {}
    for m in MARKETS:
        key_env = channel_key_env(m.provider)
        out[m.code] = channel_degree_label(
            m.provider, produced.get(m.code), key_env,
            bool(os.environ.get(key_env or "")))
    return out


def keys_view() -> dict:
    """C9.1: какие ключи найдены и откуда — env.report() ядра, значений
    нет. Отсутствующий ключ назван вместе с тем, что из-за него
    недоступно."""
    from rusterm import env as env_module
    report = env_module.report()
    rows = []
    for name, origin in report["vars"].items():
        found = origin != "—"
        rows.append({"name": name, "origin": origin, "found": found,
                     "purpose": KEY_PURPOSE.get(name, "")})
    return {"file": report["file"], "exists": report["exists"],
            "rows": rows}


def host_limits_view(paths: AppPaths) -> dict:
    """C9.2: потолки по хостам из реестра провайдеров плюс оверрайды
    из конфигурации ядра — та же дверь load_config."""
    from rusterm.providers import all_host_limits
    from rusterm.store.config import load_config
    config = load_config(paths.config_path)
    rows = []
    for name, limit in sorted(all_host_limits().items()):
        rows.append({"host": limit.host,
                     "nightly_max": limit.nightly_max,
                     "per_second": limit.per_second,
                     "override": config.provider_rate_limit.get(
                         limit.host)})
    return {"config_path": str(paths.config_path), "rows": rows}


def set_host_rate_limit(paths: AppPaths, host: str,
                        per_second: float) -> dict:
    """C9.2 -> ТЗ-62 G1: правка лимита через дверь слоя конфигурации
    (set_provider_rate_limit) — окно про имя файла не знает. Битый
    конфиг: отказ причиной от двери, молчаливой перезаписи нет."""
    from rusterm.store.config import set_provider_rate_limit
    return set_provider_rate_limit(paths.config_path, host, per_second)


def catalog_view(paths: AppPaths) -> dict:
    """C9.3: где база, сколько занимает, когда обновлялась."""
    import datetime
    db = paths.db_path
    view = {"root": str(paths.root), "db_path": str(db),
            "exists": db.exists()}
    if db.exists():
        view["size_bytes"] = db.stat().st_size
        view["updated_at"] = datetime.datetime.fromtimestamp(
            db.stat().st_mtime).isoformat(timespec="seconds")
    return view


def catalog_switch_decision(candidate_root: str) -> dict:
    """C9.3: решение о смене каталога. Каталога данных нет —
    существует=False: окно обязано СПРОСИТЬ, молчаливого создания
    нет (B35/B40)."""
    from rusterm.store.paths import AppPaths
    db = AppPaths.from_root(candidate_root).db_path
    return {"candidate_root": str(candidate_root),
            "exists": db.exists()}
