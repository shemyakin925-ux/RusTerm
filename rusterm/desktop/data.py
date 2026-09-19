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

import datetime
import sqlite3
from pathlib import Path
from typing import Optional

from rusterm.store.db import current_schema_version, open_connection
from rusterm.store.paths import AppPaths
from rusterm.tui import model as tui_model

# Отказ ячейки таблицы: словами, не пустотой и не прочерком (C1.2)
NO_DATA = "нет данных"

# Инструменты без peer set группируются честно названной строкой
NO_SECTOR = "без отрасли"

# Минимум годовых колонок; сколько показать сверх того, решает
# ширина окна (C1.2)
MIN_YEAR_COLUMNS = 4


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
    БЕЗ тихой миграции: окно читает). «Запросов сегодня» — сумма
    сэмплов provider_requests_used, записанных после местной полуночи
    (сэмпл пишет cmd_ingest по факту сбора; сэмплов нет — честный 0).
    """
    today = datetime.date.today().isoformat()
    requests_today = 0
    for sample in repos.metrics.samples():
        ts, name, _provider, value = sample[0], sample[1], sample[2], sample[3]
        if name != "provider_requests_used":
            continue
        day = datetime.datetime.fromtimestamp(ts).date().isoformat()
        if day == today:
            requests_today += int(value or 0)
    return {"schema_version": current_schema_version(repos.conn)
            if hasattr(repos, "conn") else None,
            "requests_today": requests_today}


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


def history_years(card: dict, count: int = MIN_YEAR_COLUMNS) -> list[str]:
    """Годовые колонки: от свежайшего периода мер вниз, минимум четыре.

    Периодов нет вовсе — якорем текущий год: колонки есть и честно
    говорят «нет данных», окно не схлопывается.
    """
    periods = [m.get("period") for m in card.get("measures", [])
               if m.get("period")]
    try:
        anchor = max(periods)[:4]
        anchor_year = int(anchor)
    except (ValueError, TypeError):
        anchor_year = datetime.date.today().year
    count = max(count, MIN_YEAR_COLUMNS)
    return [str(anchor_year - i) for i in range(count)]


def measure_history(repos, instrument_id: str) -> dict[str, dict]:
    """История мер по годам. Пусто — и это честно: двери нет.

    tui/model.py истории не отдаёт (снапшот хранит свежайший период
    меры), а своей выборки окно не пишет (C1.2). Координатору —
    Disputed: нужна функция модели поверх билдера снапшотов.
    """
    return {}


def measure_table_rows(repos, instrument_id: str,
                       year_count: int = MIN_YEAR_COLUMNS) -> dict:
    """Строки центральной таблицы из card_rows: сейчас + годы.

    Ячейка без значения — слова «нет данных», и в текущей колонке, и
    в исторических; причина (какой концепт не подан) — в панели
    источника по клику, не в ячейке.
    """
    card = tui_model.card_rows(repos, instrument_id)
    years = history_years(card, year_count)
    history = measure_history(repos, instrument_id)
    rows = []
    for measure in card["measures"]:
        current = measure["value"]
        has_value = current is not None and current != tui_model.NULL_MARK
        year_cells = {}
        for year in years:
            point = history.get(measure["concept"], {}).get(year)
            year_cells[year] = (format_value(point["value"])
                                if point else NO_DATA)
        rows.append({
            "concept": measure["concept"],
            "current": format_value(current) if has_value else NO_DATA,
            "years": year_cells,
            "has_value": has_value,
            "null_reason": measure.get("null_reason"),
            "unit": measure.get("unit"),
            "measure": measure,
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
    спецификация честно сообщает «нет данных»."""
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
    return {"kind": "box", "concept": chosen["concept"],
            "p25": chosen["p25"], "median": chosen["median"],
            "p75": chosen["p75"], "n": chosen["n"]}


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
