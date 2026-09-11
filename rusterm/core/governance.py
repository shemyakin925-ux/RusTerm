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
                lineage_ref: str) -> Assessment:
    """net_ratio — чистые операции к капитализации за 12 месяцев.
    Продажи по планам 10b5-1 включаются (открытый вопрос §4 документа)."""
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
        # окно раскрытия меньше 5 лет — «одна фирма 5 лет» не доказано
        return _gray(instrument_id, "auditor", as_of, lineage_ref,
                     f"disclosure_window_only_{tenure_years}y")
    return _assess(instrument_id, "auditor", as_of, lineage_ref,
                   color, reason)
