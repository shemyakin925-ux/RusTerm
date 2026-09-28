"""Governance-светофор: пять отдельных индикаторов, никакой свёртки
(TASK-7 T17, docs/governance-thresholds.md, method_version=governance.v1).

Жёсткие правила:
- светофор, а не балл: индикаторы не суммируются и не взвешиваются;
- нет данных — серый, никогда не зелёный;
- цвет без lineage не показывается: пустой lineage_ref — исключение;
- пороги — к последнему завершённому отчётному году, кроме индикатора 4
  (скользящие 12 месяцев; окно передаёт вызывающий).

Пороги взяты из документа дословно. Смена порога — новая method_version,
история не переписывается (запись только добавлением, GovernanceRepo).
"""
from __future__ import annotations

from datetime import date, timedelta
from dataclasses import dataclass

METHOD_VERSION = "governance.v1"

INDICATORS = (
    "independent_directors",
    "ceo_chair",
    "related_party",
    "insider_net",
    "auditor",
)

COLORS = ("green", "yellow", "red", "gray")

# Пороги §1: доля независимых директоров (доля состава совета)
INDEPENDENT_GREEN_MIN = 0.50   # зелёный: >= 50%
INDEPENDENT_YELLOW_MIN = 0.33  # жёлтый: 33-50%

# Пороги §3: related-party к выручке
RELATED_GREEN_MAX = 0.005      # зелёный: < 0,5%
RELATED_RED_MIN = 0.03         # красный: > 3%

# Пороги §4: чистые операции инсайдеров к капитализации, окно 12 месяцев
INSIDER_GREEN_MIN = 0.001      # зелёный: чистые покупки > 0,1%
INSIDER_RED_MIN = -0.005       # красный: чистые продажи > 0,5%


@dataclass(frozen=True)
class Assessment:
    """Одна строка governance_assessment: никакого агрегата, один цвет."""
    instrument_id: str
    indicator: str
    color: str
    method_version: str
    as_of: str
    lineage_ref: str
    reason: str


def _assess(instrument_id: str, indicator: str, as_of: str,
            lineage_ref: str, color: str, reason: str) -> Assessment:
    if not lineage_ref or not lineage_ref.strip():
        raise ValueError(
            f"I-governance: {indicator} без lineage не показывается")
    if color not in COLORS:
        raise ValueError(f"I-governance: неизвестный цвет {color!r}")
    if indicator not in INDICATORS:
        raise ValueError(f"I-governance: неизвестный индикатор {indicator!r}")
    return Assessment(instrument_id=instrument_id, indicator=indicator,
                      color=color, method_version=METHOD_VERSION,
                      as_of=as_of, lineage_ref=lineage_ref, reason=reason)


def _gray(instrument_id, indicator, as_of, lineage_ref, what: str):
    return _assess(instrument_id, indicator, as_of, lineage_ref, "gray",
                   f"no_data:{what}")


# ── 1. Доля независимых директоров ──────────────────────────────────────
def independent_directors(instrument_id: str, share, as_of: str,
                          lineage_ref: str) -> Assessment:
    """share — доля независимых по критерию самого эмитента (он же в lineage).
    None — состав или критерий не раскрыт."""
    if share is None:
        return _gray(instrument_id, "independent_directors", as_of,
                     lineage_ref, "board_independence_not_disclosed")
    if share >= INDEPENDENT_GREEN_MIN:
        color = "green"
    elif share >= INDEPENDENT_YELLOW_MIN:
        color = "yellow"
    else:
        color = "red"
    return _assess(instrument_id, "independent_directors", as_of,
                   lineage_ref, color, f"share={share}")


# ── 2. Совмещение CEO и председателя совета ────────────────────────────
def ceo_chair(instrument_id: str, roles_separated, lead_independent,
              as_of: str, lineage_ref: str) -> Assessment:
    """roles_separated — роли разделены; lead_independent — назначен
    lead independent director (вопрос возникает только при совмещении:
    разделённые роли зелёные независимо от lead). Роли не раскрыты —
    серый."""
    if roles_separated is None:
        return _gray(instrument_id, "ceo_chair", as_of, lineage_ref,
                     "board_leadership_not_disclosed")
    if roles_separated:
        color, reason = "green", "roles_separated"
    elif lead_independent is None:
        return _gray(instrument_id, "ceo_chair", as_of, lineage_ref,
                     "combined_but_lead_status_not_disclosed")
    elif lead_independent:
        color, reason = "yellow", "combined_with_lead_independent"
    else:
        color, reason = "red", "combined_without_lead_independent"
    return _assess(instrument_id, "ceo_chair", as_of, lineage_ref,
                   color, reason)


# ── 3. Сделки со связанными сторонами ──────────────────────────────────
def related_party(instrument_id: str, ratio, approved_by_independents,
                  as_of: str, lineage_ref: str) -> Assessment:
    """ratio — объём сделок к выручке за год; approved_by_independents —
    одобрена независимой частью совета. None ratio — раздел отсутствует
    (серый: молчание не равно отсутствию сделок). approved=None — одобрение
    не раскрыто, цвет по порогам; approved=False — красный независимо."""
    if ratio is None:
        return _gray(instrument_id, "related_party", as_of, lineage_ref,
                     "related_party_section_absent")
    if approved_by_independents is False or ratio > RELATED_RED_MIN:
        color = "red"
    elif ratio >= RELATED_GREEN_MAX:
        color = "yellow"
    else:
        color = "green"
    return _assess(instrument_id, "related_party", as_of, lineage_ref,
                   color, f"ratio={ratio},"
                          f"approved={approved_by_independents}")


# ── 4. Чистые операции инсайдеров (скользящие 12 месяцев) ──────────────
def insider_net(instrument_id: str, net_ratio, as_of: str,
                lineage_ref: str, tenb5_net=None, net_shares=None
                ) -> Assessment:
    """net_ratio — чистые операции к капитализации за 12 месяцев.
    Продажи по планам 10b5-1 включаются, и их доля называется в
    детали цвета (вердикт BACKLOG 11, ТЗ-33 E1): запланированная
    продажа не искажает цвет незаметно."""
    if net_ratio is None:
        return _gray(instrument_id, "insider_net", as_of, lineage_ref,
                     "insider_deals_not_disclosed")
    if net_ratio > INSIDER_GREEN_MIN:
        color, reason = "green", f"net_buys>{INSIDER_GREEN_MIN}"
    elif net_ratio < INSIDER_RED_MIN:
        color, reason = "red", f"net_sales>{-INSIDER_RED_MIN}"
    elif net_ratio >= -INSIDER_GREEN_MIN:
        color, reason = "yellow", "within_pm_0.1pct"
    else:
        # −0,5%..−0,1%: ни зелёный, ни красный — жёлтый по поправленной
        # §4 документа (решение координатора по спору TASK-7)
        color, reason = "yellow", "sales_below_0.5pct_not_red_yellow_band"
    if tenb5_net:
        share = (abs(tenb5_net / net_shares)
                 if net_shares else None)
        reason += (f";tenb5_net={tenb5_net:+.0f}sh"
                   + (f" ({share:.0%} of net)" if share is not None
                      else ""))
    return _assess(instrument_id, "insider_net", as_of, lineage_ref,
                   color, reason)


# ── 5. Аудитор ──────────────────────────────────────────────────────────
def auditor(instrument_id: str, changes_in_5y, qualified_opinion,
            tenure_years, as_of: str, lineage_ref: str) -> Assessment:
    """changes_in_5y — смены аудитора за 5 лет; qualified_opinion —
    оговорка или отказ от мнения; tenure_years — сколько лет аудитор
    ведёт компанию (раскрыто). Принадлежность к «большой четвёрке»
    на цвет не влияет."""
    if changes_in_5y is None or qualified_opinion is None \
            or tenure_years is None:
        return _gray(instrument_id, "auditor", as_of, lineage_ref,
                     "auditor_not_disclosed")
    if qualified_opinion:
        color, reason = "red", "qualified_or_declined_opinion"
    elif changes_in_5y >= 2:
        color, reason = "red", f"{changes_in_5y} auditor_changes_in_5y"
    elif changes_in_5y == 1:
        color, reason = "yellow", "one_auditor_change_in_5y"
    elif tenure_years >= 5:
        color, reason = "green", "same_auditor_5y_clean_opinion"
    else:
        # окно раскрытия меньше 5 лет — «одна фирма 5 лет» не доказано.
        # ТЗ-97 Q2: токен именованный, число стажа — деталь за ним,
        # поэтому слова словаря находятся по первому сегменту.
        return _gray(instrument_id, "auditor", as_of, lineage_ref,
                     f"disclosure_window_short:{tenure_years}y")
    return _assess(instrument_id, "auditor", as_of, lineage_ref,
                   color, reason)


# ── ТЗ-25: продюсер оценок, причины серости, устаревание, override ──────

# P2: серый перестаёт быть одним цветом на все причины. Каждая причина
# называет, что пользователь может сделать.
#
# ТЗ-97 Q2 (ТЗ-73 T3): словарь обязан покрывать ВСЕ токены, которые ядро
# само и выдаёт, — иначе вкладка показывает читателю непереведённый код.
# Ниже каждый токена назван ровно так, как его печатает `_gray` или
# `produce_assessments`; страж `tests/test_task97_q2_governance_words.py`
# перебирает продюсеров и не даёт токену появиться без слов.
GREY_REASONS: dict[str, str] = {
    "not_collected": "источник ещё не обойдён — запустите refresh или "
                     "импорт прокси",
    "source_has_no_disclosure": "в источнике такого раскрытия нет — "
                                "сделать нечего",
    "collected_unparsed": "документ собран, но не разобрался — "
                          "повторите импорт",
    "manual_unverified": "извлечение не прошло проверку цитаты — "
                         "проверьте вручную через verify",
    "stale": "оценка старше порога — нужен свежий документ",
    # что само ядро размечает серостью по каждому индикатору
    "board_independence_not_disclosed":
        "доля независимых директоров не раскрыта — закрывается ручным "
        "импортом прокси-статемента (DEF 14A)",
    "board_leadership_not_disclosed":
        "роли председателя и CEO не раскрыты — закрывается ручным "
        "импортом прокси-статемента",
    "combined_but_lead_status_not_disclosed":
        "посты совмещены, есть ли lead independent — не раскрыто; "
        "закрывается ручным импортом прокси-статемента",
    "related_party_section_absent":
        "раздел о сделках со связанными сторонами не найден — "
        "закрывается ручным импортом годовой отчётности",
    "insider_deals_not_disclosed":
        "чистые операции инсайдеров не посчитаны — формы 3/4/5 не "
        "собраны или их нет в окне",
    "auditor_not_disclosed":
        "аудитор не раскрыт — закрывается ручным импортом годовой "
        "отчётности",
    "disclosure_window_short":
        "окно раскрытия короче пяти лет — про «одна фирма пять лет» "
        "судить нечем, нужен более длинный раскрытый стаж",
    # ТЗ-97 Q2: два случая, которые раньше прятались за not_collected,
    # хотя канал уже был обойдён
    "no_deals_in_window":
        "формы владения собраны, но за скользящие 12 месяцев сделок в "
        "них нет — цвета не будет, пока сделка не появится",
    "ownership_without_market_cap":
        "сделки инсайдеров собраны, знаменателя нет: нужна капитализация "
        "`market_cap_total` из снапшота (котировки)",
}


def grey_reason_key(reason: str) -> str:
    """Токен оценки -> ключ словаря причин.

    Ядро пишет причины с префиксом (`no_data:not_collected`,
    `stale:assessed:2025-01-15`, `no_data:disclosure_window_short:3y`),
    а словарь живёт голыми именами. Без этого разбора вкладка «Качество»
    на базе пользователя показывала код вместо слов: все пять строк были
    `no_data:not_collected`, и `GREY_REASONS.get(reason)` не находил
    ничего (ТЗ-97 Q2).
    """
    parts = (reason or "").split(":")
    if parts[0] == "no_data" and len(parts) > 1:
        return parts[1]
    return parts[0]


def grey_reason_text(reason: str) -> str:
    """Слова причины для серый строки. Пустой cell запрещён (P8): если
    токена в словаре нет — так и сказано, а не молчание."""
    key = grey_reason_key(reason)
    if key in GREY_REASONS:
        return GREY_REASONS[key]
    return (f"причина «{reason or 'пусто'}» в словаре не описана — "
            f"известны только: {', '.join(sorted(GREY_REASONS))}")


# ТЗ-97 Q2 (ТЗ-73 T3, правило P8): у серой строки мало причины — нужен
# ещё и способ закрыть её одной командой. Двери названы по индикатору,
# потому что каналы разные: владение приходит из ленты SEC, остальное —
# из документов, которые обходит ручной импорт. Placeholder файла
# намеренно в угловых скобках: строка печатается в таблице, а не
# выполняется, и читатель подставляет свой файл.
_GREY_DOORS: dict[str, str] = {
    "insider_net": "rusterm ingest --source ownership --instrument {iid}",
    "independent_directors": "rusterm import <DEF-14A.pdf> --issuer {iid}",
    "ceo_chair": "rusterm import <DEF-14A.pdf> --issuer {iid}",
    "related_party": "rusterm import <10-K.pdf> --issuer {iid}",
    "auditor": "rusterm import <10-K.pdf> --issuer {iid}",
}


def grey_closing(indicator: str, instrument_id: str) -> str:
    """Чем закрывается показатель: команда целиком, как её принимает
    парсер CLI (страж `tests/test_task97_q2_governance_words.py` разбора
    требует). Незнакомого индикатора здесь быть не может — продюсер
    перебирает `INDICATORS`, — но пустая ячейка хуже исключения, поэтому
    возвращается общая команда просмотра покрытия."""
    door = _GREY_DOORS.get(indicator)
    if door is None:
        return f"rusterm coverage --instrument {instrument_id}"
    return door.format(iid=instrument_id)


# P9: порог устаревания. Число утверждено координатором (BACKLOG 10,
# ТЗ-33 E4): годовой прокси плюс люфт на позднюю подачу — 450 дней;
# 550 позволял двум сезонам пройти за текущие.
STALENESS_DAYS = 450

# P1: продюсер — какой вход какую функцию кормит.
_PRODUCER_SIGNATURES = {
    "independent_directors": ("share",),
    "ceo_chair": ("roles_separated", "lead_independent"),
    "related_party": ("ratio", "approved_by_independents"),
    "insider_net": ("net_ratio", "tenb5_net", "net_shares"),
    "auditor": ("changes_in_5y", "qualified_opinion", "tenure_years"),
}

# P7: прокси-факты из ручного импорта (категория other) -> входы.
GOVERNANCE_RECORD_MAP: dict[str, dict[str, str]] = {
    "independent_directors": {"share": "independent_directors_share"},
    "ceo_chair": {"roles_separated": "ceo_chair_roles_separated",
                  "lead_independent": "ceo_chair_lead_independent"},
    "related_party": {"ratio": "related_party_ratio"},
    "auditor": {"changes_in_5y": "auditor_changes_in_5y",
                "qualified_opinion": "auditor_qualified_opinion",
                "tenure_years": "auditor_tenure_years"},
}


def governance_inputs_from_records(manual_repo, issuer_id: str) -> dict:
    """Прокси-факты из manual_extraction (категория other, verified)
    -> спецификации входов продюсера; lineage_ref несёт документ и
    страницу дословной цитаты (P7). verified=no даёт серость
    manual_unverified, никогда цвет."""
    import re as _re
    out: dict[str, dict] = {}
    rows = manual_repo.for_issuer(issuer_id, category="other")
    for row in rows:
        (_rowid, sha, page, _cat, metric, value, _unit, _period,
         quote, verified, _model, _pv) = row
        norm = _re.sub(r"[\s\-]+", "_", (metric or "").strip().lower())
        matched = None
        for indicator, mapping in GOVERNANCE_RECORD_MAP.items():
            key = next((k for k, v in mapping.items()
                        if _re.sub(r"[\s\-]+", "_", (v or "").strip().lower())
                        == norm), None)
            if key is not None:
                matched = (indicator, key)
                break
        if matched is None:
            continue
        indicator, key = matched
        if True:
            spec = out.setdefault(indicator, {
                "inputs": {}, "lineage_ref": f"{sha}#page={page}",
                "verified": True})
            if not verified:
                spec["verified"] = False
            key = next((k for k, v in mapping.items() if v == metric),
                       None)
            if key:
                low = (value or "").strip().lower()
                parsed: object = value
                if low in ("yes", "да", "true"):
                    parsed = True
                elif low in ("no", "нет", "false"):
                    parsed = False
                else:
                    try:
                        parsed = float(value)
                    except (TypeError, ValueError):
                        parsed = value
                spec["inputs"][key] = parsed
            if quote:
                spec.setdefault("quote", quote)
            spec.setdefault("page", page)
    return out


def _insider_gray_from_coverage(repos, instrument_id: str) -> dict:
    """ТЗ-97 Q2 (ТЗ-73 T3): почему insider_net сер, если сделок нет.

    Раньше здесь молча возвращался `{}`, и продюсер рисовал
    `not_collected` — «источник ещё не обойдён» — на бумаге, где канал
    владения уже обошёл ленту и ничего не нашёл. Покрытие блока
    `ownership` знает настоящий ответ: `missing`/`error` — обошли и не
    нашли (или нашли и не смогли), `ready` — формы есть, но все они
    старше окна. Слово берётся из словаря причин.
    """
    for row in repos.coverage.for_instrument(instrument_id):
        if row["block"] != "ownership":
            continue
        if row["status"] in ("ready", "stale"):
            token = "no_deals_in_window"
        elif grey_reason_key(row["reason"] or "") in GREY_REASONS:
            token = grey_reason_key(row["reason"])
        else:
            # покрытие записано status=missing, а причину словари не
            # знают: честнее сказать «обходили и не нашли», чем
            # «не собирали» — legacy-причина `no_data:ownership` именно
            # это и значила (её писал тот же сборщик до переименования)
            token = "source_has_no_disclosure"
        return {"insider_net": {
            "gray": token,
            "lineage_ref": (f"coverage:ownership={row['status']},"
                            f"reason={row['reason'] or '—'}")}}
    return {}


def insider_net_inputs_from_store(repos, instrument_id: str,
                                  issuer_id: str, as_of: str,
                                  snapshot_id: str | None = None) -> dict:
    """E1: входы insider_net из СОХРАНЁННЫХ сделок Forms 3/4/5
    (миграция 44): окно 365 дней по дате сделки; числитель —
    куплено минус продано; знаменатель — market_cap_total снапшота.
    `snapshot_id` — сборка, внутри которой резолвер вызывается
    (ТЗ-97 Q2): строка версии в этот момент ещё `building`, а
    `latest_snapshot_id` показывает читателю только `ready` (ТЗ-90 A3),
    поэтому первый же путь `rusterm follow AAPL` на пустом каталоге
    терял знаменатель и красил ряд в серый — цвет отставал на прогон.
    Вне сборки `snapshot_id` не передаётся, и знаменатель берётся у
    последнего готового снапшота, как раньше. Доля 10b5-1 передаётся
    отдельным входом (BACKLOG 11). Нет сделок или нет знаменателя —
    серость с честной причиной, число не выдумывается."""
    try:
        low = (date.fromisoformat(as_of)
               - timedelta(days=365)).isoformat()
    except (TypeError, ValueError):
        return {}
    rows = repos.ownership.for_issuer(issuer_id, since=low, until=as_of)
    if not rows:
        return _insider_gray_from_coverage(repos, instrument_id)
    # накопление в цикле: сторож «никакой свёртки индикаторов»
    # смотрит текст исходника и запрещает агрегатные вызовы
    buys = 0.0
    sells = 0.0
    tenb5_net = 0.0
    for r in rows:
        shares = float(r["shares"] or 0.0)
        if r["direction"] == "acquired":
            buys += shares
        elif r["direction"] == "disposed":
            sells += shares
        if r["tenb5_one"]:
            tenb5_net += shares if r["direction"] == "acquired" \
                else -shares
    net = buys - sells
    sid = (snapshot_id or repos.snapshot.latest_snapshot_id(instrument_id))
    mcap = None
    if sid:
        for m in repos.snapshot.get_measures(sid):
            if m[3] == "market_cap_total" and m[4] is not None:
                mcap = float(m[4])
                break
    if not mcap:
        # ТЗ-97 Q2: сделки собраны, делить не на что — это не
        # «не собирали». Причина именованная, число сделок в lineage.
        return {"insider_net": {
            "gray": "ownership_without_market_cap",
            "lineage_ref": (f"ownership:transactions={len(rows)},"
                            f"window=365d,market_cap_total=нет")}}
    documents = len({r["document_sha256"] for r in rows})
    return {"insider_net": {
        "inputs": {"net_ratio": net / mcap, "tenb5_net": tenb5_net,
                   "net_shares": net},
        "lineage_ref": (f"ownership:buys={buys:.0f},sells={sells:.0f},"
                        f"net={net:.0f}sh,window=365d,"
                        f"documents={documents}")}}


def produce_assessments(governance_repo, instrument_id: str, as_of: str,
                        inputs: dict | None, now=None) -> list:
    """P1: пять индикаторов с чем есть — пять строк в
    governance_assessment. Нет входа — серый not_collected (на записи,
    не молчание). P8: индикатор с override не пересобирается. P9:
    нестарая цветная оценка старше STALENESS_DAYS становится серой
    stale — прошлогодний прокси не описывает сегодняшний совет."""
    from datetime import date as _date
    inputs = inputs or {}
    produced: list = []
    for indicator in INDICATORS:
        if governance_repo.has_override(instrument_id, indicator):
            continue  # P8: ручная поправка сильнее пересборки
        spec = inputs.get(indicator)
        if spec is None:
            a = _gray(instrument_id, indicator, as_of,
                      "not-collected", "not_collected")
            produced.append(a)
            governance_repo.record(a)
            continue
        # ТЗ-97 Q2: вход может быть найден и всё равно не давать числа —
        # тогда сборщик сам называет причину (своим токеном и своим
        # lineage), а продюсер её записывает, не выдумывая цвет.
        if spec.get("gray"):
            a = _gray(instrument_id, indicator, as_of,
                      spec.get("lineage_ref") or "no-lineage",
                      spec["gray"])
            produced.append(a)
            governance_repo.record(a)
            continue
        fn = globals()[indicator]
        kwargs = dict(spec.get("inputs") or {})
        for param in _PRODUCER_SIGNATURES[indicator]:
            kwargs.setdefault(param, None)
        a = fn(instrument_id, as_of=as_of,
               lineage_ref=spec["lineage_ref"], **kwargs)
        if a.color != "gray":
            ref = now or _date.today()
            if isinstance(ref, str):
                ref = _date.fromisoformat(ref)
            try:
                age = (ref - _date.fromisoformat(as_of)).days
            except (TypeError, ValueError):
                age = 0
            if age > STALENESS_DAYS:
                a = _assess(instrument_id, indicator, as_of,
                            spec["lineage_ref"], "gray",
                            f"stale:assessed:{as_of}")
        produced.append(a)
        governance_repo.record(a)
    return produced
