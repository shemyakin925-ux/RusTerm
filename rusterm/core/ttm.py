"""ТЗ-97 Q10: одно окно TTM на все потоковые входы (решение пользователя 24.09).

TTM — «последние двенадцать месяцев». Из XBRL эмитента он собирается двумя
способами; ADR-0021 показал причину, по которой наивная схема не работает:
квартальный факт четвёртого квартала эмитент НЕ подаёт (10-K содержит
12-месячный период, а не 3-месячный), поэтому:

1. сумма четырёх ПОДРЯД идущих кварталов — работает, когда эмитент подаёт
   квартальную отчётность;
2. алгебра `FY + YTD − YTD прошлого года` — Q4 физически отсутствует в
   подаче, но он равен разности годового факта и двух YTD.

Ни один способ не собрался — берём последний годовой факт и ЧЕСТНО помечаем
его `annual_fallback`: это 12 месяцев, но закончившиеся в конце прошлого
периода, а не на дату снапшота. Ни того, ни другого — None: вызывающая
сторона ставит прежний отказ `missing_data`, а не quarterly x 4.

Дверь `as_of` и правило давности остаются у вызывающей стороны: строки
приходят уже отфильтрованными, второго запроса ядро не делает и
`_STALE_LOOKBACK_DAYS` не дублирует.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

# Значения basis — они же попадают в measure_lineage.period_basis
TTM = "ttm"
ANNUAL_FALLBACK = "annual_fallback"

_ANNUAL_MIN_DAYS = 350
_ANNUAL_MAX_DAYS = 380
_QUARTER_MIN_DAYS = 80
_QUARTER_MAX_DAYS = 100
# «Подряд» и «стыкуется с годовым»: дырка в один день — это не пропущенный
# период (52/53-недельные календари), дырка в шесть недель — пропущенный.
_ADJACENCY_DAYS = 5
# Шаг годового календаря: 52/53 недели — от 358 до 372 дней.
_YEAR_MIN_DAYS = 358
_YEAR_MAX_DAYS = 372


@dataclass(frozen=True)
class Component:
    """Одно слагаемое окна: роль, факт, его период и знак в сумме."""
    role: str
    fact_id: str
    start: str
    end: str
    sign: int
    value: float


@dataclass(frozen=True)
class TtmWindow:
    """Собранное окно: значение, границы, база ('ttm' |
    'annual_fallback'), слагаемые и названные недостающие слагаемые."""
    value: float
    start: str
    end: str
    basis: str
    components: tuple
    missing: tuple


def _period(value, start, end, fact_id) -> Optional[dict]:
    """Кортеж строки факта -> словарь периода; None на мусоре и на
    перевёрнутом периоде (ядро вызывается на всём наборе бумаг сразу)."""
    try:
        s, e, v = (date.fromisoformat(start), date.fromisoformat(end),
                   float(value))
    except (TypeError, ValueError):
        return None
    if e <= s:
        return None
    return {"value": v, "start": s, "end": e, "fact_id": fact_id}


def _component(p: dict, role: str, sign: int) -> Component:
    return Component(role=role, fact_id=p["fact_id"],
                     start=p["start"].isoformat(),
                     end=p["end"].isoformat(), sign=sign, value=p["value"])


def _days(start: date, end: date) -> int:
    return (end - start).days


def _is_annual(p: dict) -> bool:
    return _ANNUAL_MIN_DAYS <= _days(p["start"], p["end"]) <= _ANNUAL_MAX_DAYS


def is_annual_window(start: str, end: str) -> bool:
    """Годовое ли окно по строкам ISO: тот же коридор, что у годового
    слагаемого. Вызывающей стороне (сборка снапшота) нужно отличить
    общий годовой период входов от квартального, не пересчитывая дни и
    не дублируя границы — иначе два определения «года» разъедутся."""
    try:
        s, e = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError):
        return False
    return _is_annual({"start": s, "end": e})


def _is_quarter(p: dict) -> bool:
    return (_QUARTER_MIN_DAYS <= _days(p["start"], p["end"])
            <= _QUARTER_MAX_DAYS)


def _year_before(d: date) -> date:
    """Та же дата годом ранее; 29 февраля в прошлом году не бывает."""
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        return d.replace(year=d.year - 1, day=28)


def _four_quarters(periods: list, concept: str):
    """Цепочка четырёх подряд идущих кварталов, заканчивающаяся на самом
    свежем периоде. (components, start, end) либо строка отказа."""
    anchor = periods[0]
    if not _is_quarter(anchor):
        return None
    quarters = [p for p in periods if _is_quarter(p)]
    chain = [quarters[0]]
    for q in quarters[1:]:
        if len(chain) == 4:
            break
        gap = _days(q["end"], chain[-1]["start"])
        if 0 < gap <= _ADJACENCY_DAYS:
            chain.append(q)
            continue
        lost = (q["end"] + timedelta(days=1)).isoformat()
        upto = (chain[-1]["start"] - timedelta(days=1)).isoformat()
        return f"quarters: {concept} — нет квартала {lost}…{upto}"
    if len(chain) < 4:
        return (f"quarters: {concept} — подряд идущих кварталов только "
                f"{len(chain)} из четырёх")
    start, end = chain[-1]["start"], chain[0]["end"]
    if not _ANNUAL_MIN_DAYS <= _days(start, end) <= _ANNUAL_MAX_DAYS:
        return (f"quarters: {concept} — четыре квартала дали окно "
                f"{_days(start, end)} дней, а не 12 месяцев")
    return [_component(q, "quarterly", 1) for q in reversed(chain)], start, end


def _algebra_addends(periods: list, anchor: dict):
    """(FY, YTD прошлого года) для алгебры; None — если слагаемого нет."""
    fy = None
    for p in periods:
        if not _is_annual(p) or p["end"] >= anchor["start"]:
            continue
        if 0 < _days(p["end"], anchor["start"]) <= _ADJACENCY_DAYS:
            if fy is None or p["end"] > fy["end"]:
                fy = p
    prior = None
    for p in periods:
        if p is anchor or p is fy:
            continue
        back = (_days(p["start"], anchor["start"]),
                _days(p["end"], anchor["end"]))
        if all(_YEAR_MIN_DAYS <= d <= _YEAR_MAX_DAYS for d in back):
            if prior is None or p["end"] > prior["end"]:
                prior = p
    return fy, prior


def _algebra(periods: list, anchor: dict, concept: str):
    """`FY + YTD − YTD годом ранее`: (components, start, end), строка
    отказа или None (годовое слагаемое ещё поискать запасным значением).
    Окно начинается днём после вычитаемого YTD — это и есть настоящие
    12 месяцев, а не полтора года от начала годового факта."""
    fy, prior = _algebra_addends(periods, anchor)
    if fy is None:
        return (f"fy: {concept} — нет годового факта, стыкующегося с "
                f"{anchor['start'].isoformat()}")
    if prior is None:
        # Название недостающего куска — тем же календарным сдвигом, каким
        # его ищут (коридор 358–372 дня): сдвиг на 365 дней в високосном
        # году показал бы 2 января там, где эмитент подаёт 1 января, и
        # пометка врала бы о периода, которого на самом деле не ищут.
        low = _year_before(anchor["start"]).isoformat()
        high = _year_before(anchor["end"]).isoformat()
        return (f"ytd_prior: {concept} — нет факта того же куска года "
                f"годом ранее ({low}…{high})")
    return [_component(fy, "fy", 1), _component(anchor, "ytd", 1),
            _component(prior, "ytd_prior", -1)], \
        prior["end"] + timedelta(days=1), anchor["end"]


def _annual_fallback(periods: list, concept: str,
                     missing: list) -> Optional[TtmWindow]:
    """Последний годовой факт как запасное значение — с окном годового
    периода и названными недостающими слагаемыми, а не «последние 12
    месяцев»."""
    annuals = [p for p in periods if _is_annual(p)]
    if not annuals:
        return None
    annual = max(annuals, key=lambda p: p["end"])
    if not missing:
        missing.append(f"fy: {concept} — после годового "
                       f"{annual['end'].isoformat()} не подано ничего, "
                       f"что давало бы окно")
    return TtmWindow(
        value=annual["value"],
        start=annual["start"].isoformat(), end=annual["end"].isoformat(),
        basis=ANNUAL_FALLBACK,
        components=(_component(annual, "annual", 1),),
        missing=tuple(missing))


def ttm_window(rows, as_of: str, concept: str = "") -> Optional[TtmWindow]:
    """TTM-окно потокового концепта по его duration-фактам.

    rows — итерируемое (value, period_start, period_end, fact_id) от
    newest-first; as_of — дата снапшота (ISO); concept — каноническое имя
    для строк `missing`. None — ни TTM, ни годового: вызывающая сторона
    сохраняет прежний отказ."""
    try:
        door = date.fromisoformat(as_of)
    except (TypeError, ValueError):
        return None
    periods: list = []
    seen: set = set()
    for row in rows or ():
        try:
            value, start, end, fact_id = row
        except (TypeError, ValueError):
            continue
        p = _period(value, start, end, fact_id)
        if p is None or p["end"] > door:
            continue  # период ещё не закрыт на дату снапшота
        key = (p["start"], p["end"])
        if key in seen:
            continue  # пересоставленный факт того же периода — одно слагаемое
        seen.add(key)
        periods.append(p)
    if not periods:
        return None
    periods.sort(key=lambda p: p["end"], reverse=True)
    anchor = periods[0]

    if _is_annual(anchor):
        # После последнего годового ничего не подано — годовой И ЕСТЬ
        # окно: 12 месяцев в нём есть, они просто закончились раньше
        # as_of. Дверь давности — на стороне вызывающей.
        return TtmWindow(
            value=anchor["value"],
            start=anchor["start"].isoformat(),
            end=anchor["end"].isoformat(), basis=TTM,
            components=(_component(anchor, "annual", 1),), missing=())

    missing: list = []
    for attempt in (_four_quarters(periods, concept),
                    _algebra(periods, anchor, concept)):
        if isinstance(attempt, str):
            missing.append(attempt)
            continue
        if attempt is None:
            continue
        comps, start, end = attempt
        return TtmWindow(
            value=sum(c.value * c.sign for c in comps),
            start=start.isoformat(), end=end.isoformat(), basis=TTM,
            components=tuple(comps), missing=())

    return _annual_fallback(periods, concept, missing)


def declared_window(rows, as_of: str, days: int = 365) -> Optional[TtmWindow]:
    """ТЗ-130 K4: окно по ОБЪЯВЛЕНИЯМ дивиденда, поданным датами.

    BAC подаёт `CommonStockDividendsPerShareDeclared` с началом периода,
    равным концу, — по факту на каждое объявление (2023: 0,22 / 0,22 /
    0,24 / 0,24). Квартального окна из таких строк не собрать, а сумма
    объявленного за последние `days` дней и есть дивиденд за 12 месяцев.
    rows — (value, start, end, fact_id); берутся только мгновенные
    (start == end), одна дата — одно объявление (первая строка: вызывающий
    отдаёт свежую подачу первой). Ни одного объявления в окне — None."""
    try:
        anchor = date.fromisoformat(as_of)
    except (TypeError, ValueError):
        return None
    seen: dict[str, tuple] = {}
    for value, start, end, fact_id in rows:
        if not end or start != end or end in seen:
            continue
        try:
            day, amount = date.fromisoformat(end), float(value)
        except (TypeError, ValueError):
            continue
        if anchor - timedelta(days=days) < day <= anchor:
            seen[end] = (amount, fact_id)
    if not seen:
        return None
    first, last = min(seen), max(seen)
    components = tuple(
        Component(role="declared", fact_id=fact_id, start=end, end=end,
                  sign=1, value=amount)
        for end, (amount, fact_id) in sorted(seen.items()))
    return TtmWindow(value=sum(a for a, _f in seen.values()), start=first,
                     end=last, basis=TTM, components=components, missing=())


def declared_by_year(rows) -> dict[str, tuple[float, list[str]]]:
    """Сумма объявлений дивиденда по календарному году даты объявления:
    {год: (сумма, [fact_id])} — строка «Дивиденд на акцию» карточки для
    эмитента, который подаёт объявления датами (см. declared_window)."""
    seen: dict[str, tuple] = {}
    for value, start, end, fact_id in rows:
        if not end or start != end or end in seen:
            continue
        try:
            seen[end] = (float(value), fact_id)
        except (TypeError, ValueError):
            continue
    out: dict[str, tuple[float, list[str]]] = {}
    for end, (amount, fact_id) in sorted(seen.items()):
        total, ids = out.get(end[:4], (0.0, []))
        out[end[:4]] = (total + amount, ids + [fact_id])
    return out
