"""Сборка снапшота — процесс 2 по docs/processes.md §124-196.

Два прохода: фундаментальные меры считаются по компании независимо;
перцентили — только по уже посчитанным величинам пиров. Пир без свежих
данных исключается из расчёта с пометкой excluded_stale, не берётся
устаревшим. Три вида diff раздельны: изменение метрик, эффект пересостава
peer set, появившиеся ревизии (ADR-0002: смешивать первые два запрещено).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import uuid4

from rusterm.core.peers import (currency_guard, evaluate,
                                percentile_share, period_window)
from rusterm.core.ttm import (ANNUAL_FALLBACK, TTM, TtmWindow,
                              is_annual_window, ttm_window)
from rusterm.formulas import (calculate_measure, effective_tax_rate,
                              invested_capital, measure_unit, nopat)
from rusterm.normalize.concepts import priority_rank, strip_taxonomy

# Меры первого прохода (TASK-9 V4): все формулы §3 data-dictionary,
# чьи входы — эмитентские концепты из карты V0.
_MEASURE_FORMULAS: dict[str, dict[str, str]] = {
    # концепт -> {ключ kwargs -> канонический вход}
    "net_margin": {"net_income": "net_income", "revenue": "revenue"},
    "operating_margin": {"operating_income": "operating_income",
                         "revenue": "revenue"},
    "effective_tax": {"tax_expense": "tax_expense",
                      "pretax_income": "pretax_income"},
    "gross_margin": {"gross_profit": "gross_profit", "revenue": "revenue"},
    "ebitda": {"operating_income": "operating_income",
               "d_and_a": "d_and_a"},
    "fcf": {"ocf": "ocf", "capex": "capex"},
    "interest_coverage": {"operating_income": "operating_income",
                          "interest_expense": "interest_expense"},
}

# Двухпериодные: поток + сток (начало = предыдущий период стока).
# ТЗ-56 Z1: roe_incl_nci — своя мера на стоке total_equity_incl_nci;
# roe не получает подстановку и отказывает missing_data: total_equity.
_TWO_PERIOD_MEASURES: dict[str, tuple[str, str]] = {
    "roe": ("net_income", "total_equity"),
    "roe_incl_nci": ("net_income", "total_equity_incl_nci"),
    "asset_turnover": ("revenue", "total_assets"),
}

# Цепочка: nopat = operating_income * (1 - effective_tax); ставка берётся
# из уже посчитанной меры effective_tax того же периода.
_CHAIN_MEASURES: dict[str, dict[str, str]] = {
    "nopat": {"operating_income": "operating_income",
              "tax_rate": "effective_tax"},
}

# Формулы §3, чьи входы вне карты V0: строка видна с постоянной
# причиной concept_not_mapped, не выбрасывается.
# cagr исключён решением координатора (TASK-10 §0.2.3): cagr(V, n) —
# функция над именованным рядом, а не мера эмитента; функция остаётся
# в formulas.py со своим unit-тестом.
# ТЗ-23 K4: шесть мер получили входы (цена из таблицы price + факты)
# и считаются в отдельном проходе; остальные ждут своих концептов.
# ТЗ-68 N1: pe/ps/fcf_yield/net_debt/net_debt_ebitda считаются
# проходом оценки (их входы в карте v4: cash/total_debt/
# shares_outstanding — ТЗ-31 C2; eps_diluted/revenue — исходно).
# Остались честно несчитаемые формулами v0: invested_capital (нужна
# сумма долга), hhi (нужны пиры), price_adj/total_return/drawdown
# (нужен ряд цен, а не одна закрытая).
_UNMAPPED_FORMULAS: tuple[str, ...] = (
    "total_return", "drawdown", "price_adj", "hhi",
)

# Канонические входы оценочных мер, которых нет в карте V0 (ТЗ-23 K4).
_VALUATION_INPUT_CONCEPTS: tuple[str, ...] = (
    "shares_outstanding", "total_debt", "cash", "st_investments",
    "minority_interest", "preferred_equity", "dps_ttm",
    "invested_capital", "total_equity",
    "eps_diluted", "revenue",  # ТЗ-68 N1: pe и ps
)

# ТЗ-23 K4: цена старше семи дней — поводок, а не число; перенос
# вчерашней цены за сегодня запрещён задачей, устаревшая — тем более.
_PRICE_STALE_DAYS = 7

_BASE_MEASURES = _MEASURE_FORMULAS  # совместимость с существующими тестами

# Все канонические входы формул — то, что as_reported_facts запрашивает.
base_concepts: tuple[str, ...] = tuple(sorted(
    {c for inputs_map in _MEASURE_FORMULAS.values()
     for c in inputs_map.values()}
    | {flow for flow, _stock in _TWO_PERIOD_MEASURES.values()}
    | {stock for _flow, stock in _TWO_PERIOD_MEASURES.values()}
    | {"operating_income"}
))

# Правило давности (TASK-12 Y2): три года плюс люфт на сдвиг фингода.
_STALE_LOOKBACK_DAYS = 1100

# Годовой dps из отчётности годен как «последние 12 месяцев», пока его
# год кончился не больше ~18 месяцев назад; старше — следующего годового
# отчёта с дивидендами нет, и выплаты могли прекратиться (координатор,
# 24.09.2026).
_DPS_ANNUAL_STALE_DAYS = 550

# ТЗ-102 M1: число акций — множитель цены, и свежий отчёт о выручке его
# не обновляет: тег CommonStockSharesOutstanding датирован своим числом.
# Тот же порог, что у годового dps (координатор, 27.09.2026:
# «цена × 14-летнее число акций хуже честного отказа»).
_SHARES_FRESH_DAYS = _DPS_ANNUAL_STALE_DAYS


def _share_count_refusal(period_end: Optional[str],
                         as_of: Optional[str]) -> Optional[str]:
    """ТЗ-102 M1: причина отказа по давности числа акций, или None.
    Якорь — as_of сборки, а не самый свежий факт эмитента. Неразбираемая
    дата не отбрасывается — то же соглашение, что у `_eligible_input`."""
    try:
        age = (date.fromisoformat(as_of)
               - date.fromisoformat(period_end)).days
    except (TypeError, ValueError):
        return None
    if age > _SHARES_FRESH_DAYS:
        return f"stale_input: shares_outstanding ({period_end})"
    return None


def _denominator_refusal(value: float) -> str:
    """ТЗ-91 B2: отказ знаменателя, у которого ЕСТЬ число: ноль —
    denominator_zero, отрицательный — negative_denominator (словарь
    §1.4). `missing_data: <вход>` здесь врёт: вход на месте, нет
    частного."""
    return "denominator_zero" if value == 0 else "negative_denominator"


def _eligible_input(period_end: str, anchor_date: date) -> bool:
    """Входной факт годен, пока его конец отстаёт от anchor не более
    чем на _STALE_LOOKBACK_DAYS дней; неразбираемая дата не
    отбрасывается."""
    try:
        return (anchor_date - date.fromisoformat(period_end)).days \
            <= _STALE_LOOKBACK_DAYS
    except (TypeError, ValueError):
        return True


def measure_inputs(concept: str) -> tuple[str, ...]:
    """Канонические входы меры §3 — для показа исключённого (TASK-15
    C5). Пусто для концепта без формулы в картах V4."""
    if concept in _MEASURE_FORMULAS:
        return tuple(sorted(set(_MEASURE_FORMULAS[concept].values())))
    if concept in _TWO_PERIOD_MEASURES:
        flow, stock = _TWO_PERIOD_MEASURES[concept]
        return tuple(sorted({flow, stock}))
    if concept in _CHAIN_MEASURES:
        return tuple(sorted(set(_CHAIN_MEASURES[concept].values())))
    return ()


def stale_exclusions(snapshot_repo, issuer_id: str) -> dict:
    """TASK-15 C5: факты эмитента, исключённые правилом давности Y2.

    anchor — тот же, что в _issuer_inputs: самый свежий period_end
    среди as_reported фактов эмитента по концептам набора мер (значение
    обязано разбираться числом). Возвращает {fact_id: (period_end,
    anchor)} для фактов, отставших от anchor более чем на
    _STALE_LOOKBACK_DAYS дней. Это чтение на as_reported_facts, без
    новых колонок: мера ничего не узнаёт о показе, исключённое видит
    представление.
    """
    rows = snapshot_repo.as_reported_facts(issuer_id, base_concepts)
    anchor = None
    for _concept, value, _fact_id, _unit, _start, end, canonical in rows:
        key = canonical or _concept
        if key not in base_concepts:
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            continue
        if end > (anchor or ""):
            anchor = end
    if anchor is None:
        return {}
    try:
        anchor_date = date.fromisoformat(anchor)
    except (TypeError, ValueError):
        return {}
    out: dict[str, tuple[str, str]] = {}
    for _concept, value, fact_id, _unit, _start, end, canonical in rows:
        key = canonical or _concept
        if key not in base_concepts:
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            continue
        if not _eligible_input(end, anchor_date):
            out[fact_id] = (end, anchor)
    return out


@dataclass
class SnapshotDiff:
    """Три раздельных сравнения с предыдущей версией (processes.md §142)."""
    metric_changes: list = field(default_factory=list)    # [(concept, old, new)]
    peer_set_changes: list = field(default_factory=list)  # [(added, removed)]
    revisions: list = field(default_factory=list)         # [(concept, period_end)]


@dataclass
class IssuerInputs:
    """Входы мер первого прохода (ТЗ-97 Q10): к прежним четырём словарям
    добавлены окна — TTM-окно по каждому потоковому концепту и меры,
    которые из-за отсутствия окна пришлось читать годовым (в значении
    названо недостающее слагаемое)."""
    inputs: dict = field(default_factory=dict)
    lineage: dict = field(default_factory=dict)
    reasons: dict = field(default_factory=dict)
    periods: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)
    windows: dict = field(default_factory=dict)
    fallbacks: dict = field(default_factory=dict)


def window_lineage(window: TtmWindow, why: str = "") -> list:
    """Строки lineage слагаемых окна (ТЗ-97 Q10): роль называет слагаемое
    и его период, база периода едет в той же строке — приближение
    перестает быть невидимым (ТЗ-32 D6). `why` — почему окна TTM нет:
    для запасного годового оно обязательно."""
    rows = []
    if not why and window.basis == ANNUAL_FALLBACK:
        # Причина живёт в самом окне, а не в доброй воле вызывающей
        # стороны: запасной выход не молчит ни на одном пути.
        why = "; ".join(window.missing)
    for c in window.components:
        role = f"input:{window.basis} {c.role} {c.start}…{c.end}"
        rows.append({"fact_id": c.fact_id, "peer_measure_id": None,
                     "role": (role + f"; TTM не собран: {why}"
                              if why else role),
                     "period_basis": window.basis})
    return rows


def fallback_role(window_start: str, window_end: str, note: str) -> str:
    """Роль строки lineage для меры, считанной годовым вместо трейлинга
    (ТЗ-97 Q10): база периода, окно и названное недостающее слагаемое —
    читатель не должен догадываться. Одно написание на все запасные
    годовые пути (общий годовой период входов, свежий годовой факт,
    `_annual_common_period`): иначе ветки одного отказа расходятся
    текстом и поверхностями."""
    role = (f"input:{ANNUAL_FALLBACK} годовое окно "
            f"{window_start}…{window_end}")
    return f"{role}; TTM не собран: {note}" if note else role


def annual_window_note(concept: str) -> str:
    """Годовое основание меры, у потока которого окно в проходе входов
    не собралось (ТЗ-97 Q10): в отличие от `fallback_note` здесь
    годового факта как раз хватает (его и берут), поэтому называть
    недостающее слагаемое нечем — названо само окно."""
    return f"{concept}: окна потока нет в проходе входов"


def fallback_note(windows: dict, concepts) -> str:
    """Почему мера читана годовым, а не трейлингом (ТЗ-97 Q10): текст
    называет каждое недостающее слагаемое. Концепт без окна — тоже
    назван: «годовой запасной» молча не бывает."""
    parts: list = []
    for c in concepts:
        window = windows.get(c)
        if window is None:
            parts.append(f"{c}: нет ни TTM-окна, ни годового факта")
        elif window.basis == ANNUAL_FALLBACK:
            parts.extend(window.missing)
    return "; ".join(parts)


def annual_route_note(windows: dict, concepts) -> str:
    """Почему мера всё-таки села на общий ГОДОВОЙ период, а не на
    TTM-окно (ТЗ-97 Q10): либо у потока нет окна и `fallback_note`
    называет недостающее слагаемое, либо окна потоков меры РАЗНЫЕ и в
    одной мере их смешивать нельзя. Пустой строки не бывает: запасной
    выход не молчит, иначе пометка «годовой» исчезает с поверхностей, а
    основание меры остаётся годовым.
    """
    note = fallback_note(windows, concepts)
    if note:
        return note
    spans = []
    for c in concepts:
        w = windows.get(c)
        spans.append(f"{c} {w.start}…{w.end}" if w else f"{c} без окна")
    return "общего TTM-окна нет: " + "; ".join(spans)


@dataclass
class BuildResult:
    snapshot_id: str
    version: int
    measures: int = 0
    percentiles: int = 0
    excluded_stale: list = field(default_factory=list)
    # ТЗ-97 Q8: пиры, чей последний закрытый период старше самого
    # свежего в наборе больше чем на окно (2 года). Исключены с
    # пометкой, а не отменили сравнение; их называет `rusterm snapshot`.
    excluded_period: list = field(default_factory=list)
    peer_suspect: bool = False
    diff: SnapshotDiff = field(default_factory=SnapshotDiff)
    # ТЗ-97 Q10: [(концепт меры, почему TTM не собран)] — их показывает
    # `rusterm snapshot` и подвал экспорта; мера на годовом основании
    # не должна выглядеть трейлинговой.
    annual_fallbacks: list = field(default_factory=list)


class SnapshotBuilder:
    """Собирает и записывает новую версию снапшота по фактам из базы."""

    def __init__(self, snapshot_repo, peer_set_repo, coverage_repo,
                 price_repo=None, industry=None, governance=None,
                 corp_action_repo=None):
        self._snapshots = snapshot_repo
        self._peers = peer_set_repo
        # ТЗ-23 K4: репозиторий цен; None — цены недоступны, меры
        # получают честную причину missing_data: price_close
        self._prices = price_repo
        # ТЗ-31 C2: корпоративные действия для dps_ttm (скользящее
        # окно 365 дней по ex_date); None — вход недоступен, div_yield
        # получает честную причину missing_data: dps_ttm
        self._corp_actions = corp_action_repo
        # ТЗ-25 P1: резолвер governance (instrument_id, issuer_id) ->
        # список Assessment (продюсер сам пишет через GovernanceRepo)
        self._governance = governance
        # ТЗ-24 N2: резолвер отрасли (instrument_id, issuer_id) ->
        # {"sector", "reason", "metrics", "unmapped"}; None — блок
        # industry_metrics не строится (старые вызовы и тесты)
        self._industry = industry
        # coverage_repo обязателен (TASK-8 U1): сборка без записи покрытия
        # делает блоки молча отсутствующими — забытый аргумент должен
        # падать громко, а не молчать.
        self._coverage = coverage_repo

    def build(self, instrument_id: str, issuer_id: str, as_of: str,
              peer_set_version: str | None = None,
              peer_measures: list | None = None,
              peer_members_previous: list[str] | None = None,
              peer_members_current: list[str] | None = None,
              source_errors: dict | None = None) -> BuildResult:
        """peer_measures — [(peer_id, measure_id, concept, value, fresh)]
        величин пиров из первого прохода. fresh=False — пир без свежих
        данных: исключается с пометкой excluded_stale.

        source_errors — {block: причина} для блоков, чей сборщик вернул
        внешнюю ошибку (E1/E2): покрытие получает error, сборка продолжается
        на том, что есть (docs/threat-model-sources.md §2 class A).

        ТЗ-90 A3: строка снапшота создаётся со статусом `building` и
        помечается `ready` последней записью сборки. Любое исключение
        удаляет строки этого снапшота и перевынивается — половины
        снапшота в базе не остаётся, читатели (latest_snapshot_id,
        previous_snapshot) и так видят только `ready`.
        """
        version = self._next_version(instrument_id)
        snapshot_id = str(uuid4())
        self._snapshots.create_snapshot(snapshot_id, instrument_id, version,
                                        as_of, peer_set_version,
                                        "unverified" if peer_set_version else "none",
                                        "building")
        try:
            result = self._assemble(
                instrument_id, issuer_id, as_of, peer_set_version,
                peer_measures, peer_members_previous, peer_members_current,
                source_errors, snapshot_id, version)
        except BaseException:
            self._snapshots.delete_snapshot(snapshot_id)
            raise
        self._snapshots.set_status(snapshot_id, "ready")
        return result

    def _assemble(self, instrument_id: str, issuer_id: str, as_of: str,
                  peer_set_version: str | None,
                  peer_measures: list | None,
                  peer_members_previous: list[str] | None,
                  peer_members_current: list[str] | None,
                  source_errors: dict | None,
                  snapshot_id: str, version: int) -> BuildResult:
        """Тело сборки: меры, блоки, diff и покрытие. Строку создал
        build() в статусе `building`; готовность ставит build() после
        возврата отсюда (ТЗ-90 A3)."""
        self._snapshots.add_block(snapshot_id, "fundamentals", "ready", None)
        result = BuildResult(snapshot_id=snapshot_id, version=version)

        # ── Проход 1: формулы §3, чьи входы в карте V0 ──
        issuer = self._issuer_inputs(issuer_id, as_of=as_of)
        inputs, lineage_by_concept, input_reasons, periods, input_units = \
            issuer.inputs, issuer.lineage, issuer.reasons, issuer.periods, \
            issuer.units
        # ТЗ-97 Q10: где TTM-окно не собралось, мера читана годовым —
        # пометка уходит в вывод команды и в подвал экспорта.
        result.annual_fallbacks.extend(sorted(issuer.fallbacks.items()))
        computed: dict[str, float] = {}
        formula_groups: list[tuple[dict, bool]] = [
            (_MEASURE_FORMULAS, False),
            (_CHAIN_MEASURES, False),
            (_TWO_PERIOD_MEASURES, True),
        ]
        written_measures: set[str] = set()
        measure_row_ids: dict[str, str] = {}
        for formulas, _is_two_period in formula_groups:
            for concept in formulas:
                if concept in written_measures:
                    continue
                raw_inputs = inputs.get(concept)
                value = None
                null_reason = input_reasons.get(concept, "missing_data")
                if raw_inputs is not None:
                    kw = dict(raw_inputs)
                    # цепочка: значения-меры подставляются после расчёта
                    # исходных мер того же прохода
                    for kwarg, source in _CHAIN_MEASURES.get(
                            concept, {}).items():
                        if kw.get(kwarg) is None:
                            kw[kwarg] = computed.get(source)
                    if all(v is not None for v in kw.values()):
                        m = calculate_measure(concept, **kw)
                        value, null_reason = m.value, m.null_reason
                    else:
                        # ТЗ-58 C4: отказ цепочки называет отвалившееся
                        # ЗВЕНО (например effective_tax при снятом
                        # clip), а не голое missing_data; уже названная
                        # причина исходных входов не перекрывается.
                        # ТЗ-91 B2: звеном считается только тот kwarg,
                        # который остался None, — исходный вход цепочки
                        # (operating_income) мерой не был и в computed
                        # не попадает, а факт с числом называть
                        # отсутствующим нельзя.
                        missing_chain = sorted(
                            {source for kwarg, source in
                             _CHAIN_MEASURES.get(concept, {}).items()
                             if kw.get(kwarg) is None})
                        if missing_chain:
                            named = input_reasons.get(concept)
                            if named in (None, "missing_data"):
                                null_reason = ("missing_data: "
                                               + ", ".join(missing_chain))
                if value is None and null_reason is None:
                    null_reason = "missing_data"  # I4: NULL обязан причиной
                if concept in periods:
                    period_start, period_end = periods[concept]
                else:
                    period_start, period_end = as_of, as_of
                measure_id = str(uuid4())
                lineage_rows = lineage_by_concept.get(concept, [])
                if concept in _CHAIN_MEASURES and "effective_tax" in \
                        measure_row_ids:
                    lineage_rows = lineage_rows + [
                        {"fact_id": None,
                         "peer_measure_id": measure_row_ids["effective_tax"],
                         "role": "input"}]
                self._snapshots.insert_measure_with_lineage(
                    dict(measure_id=measure_id, snapshot_id=snapshot_id,
                         scope="issuer", scope_ref=issuer_id,
                         concept=concept,
                         value=None if value is None else repr(value),
                         unit=measure_unit(
                             concept, input_units.get(concept, "")),
                         period_start=period_start, period_end=period_end,
                         formula_id=concept, method_version="v1",
                         null_reason=null_reason, peer_set_version=None),
                    lineage_rows)
                written_measures.add(concept)
                measure_row_ids[concept] = measure_id
                result.measures += 1
                if value is not None:
                    computed[concept] = value

        # ── Реестр формул §3 вне карты V0: строка видна, причина честна ──
        for concept in _UNMAPPED_FORMULAS:
            if concept in written_measures:
                continue
            self._snapshots.insert_measure_with_lineage(
                dict(measure_id=str(uuid4()), snapshot_id=snapshot_id,
                     scope="issuer", scope_ref=issuer_id, concept=concept,
                     value=None, unit=measure_unit(concept),
                     period_start=as_of, period_end=as_of,
                     formula_id=concept, method_version="v1",
                     null_reason="concept_not_mapped", peer_set_version=None),
                [])
            written_measures.add(concept)
            result.measures += 1

        # ── ТЗ-23 K4: проход 1b — оценочные меры ──
        # цена последним ЗАКРЫТЫМ торговым днём не позже as_of; нет
        # цены — missing_data: price_close; цена старше порога —
        # причина, не число. Валюты числителя и знаменателя обязаны
        # совпадать (K6), иначе currency_mismatch.
        self._valuation_pass(snapshot_id, issuer_id, instrument_id,
                             as_of, computed, written_measures,
                             measure_row_ids, result, issuer.windows)

        # ── ТЗ-24 N2: блок industry_metrics из секторного модуля ──
        industry_entry = None
        if self._industry is not None:
            report = self._industry(instrument_id, issuer_id)
            if report["sector"] is None:
                industry_entry = ("missing", "industry_no_sector")
                self._snapshots.add_block(
                    snapshot_id, "industry_metrics", "missing",
                    "industry_no_sector")
            elif report["reason"]:
                industry_entry = ("missing", report["reason"])
                self._snapshots.add_block(
                    snapshot_id, "industry_metrics", "missing",
                    report["reason"])
            else:
                metrics = report["metrics"]
                # ТЗ-90 A3: имя отдельное. Здесь локальная переменная
                # называлась `computed` и перепривязывала словарь величин
                # прохода 1 к целому — `computed.get(concept)` ниже падал
                # AttributeError, а покрытие fundamentals читалось
                # счётчиком отрасли.
                industry_computed = sum(1 for m in metrics
                                        if m["value"] is not None)
                grey = [f"{m['concept']} ({m['reason']})"
                        for m in metrics if m["value"] is None]
                method = (metrics[0]["method_version"] if metrics
                          else "unknown")
                status = "ready" if industry_computed else "missing"
                reason = (f"computed {industry_computed}/{len(metrics)} "
                          f"method {method}")
                if grey:
                    reason += "; grey: " + "; ".join(grey[:8])
                industry_entry = (status, reason)
                self._snapshots.add_block(
                    snapshot_id, "industry_metrics", status, reason)

        # ── ТЗ-25 P1: governance-оценки — пять строк на записи ──
        if self._governance is not None:
            self._governance(instrument_id, issuer_id)

        # ── Проход 2: перцентили по посчитанным величинам пиров ──
        if peer_set_version and peer_measures:
            fresh = [pm for pm in peer_measures if pm[4]]
            stale = [pm for pm in peer_measures if not pm[4]]
            result.excluded_stale = [pm[0] for pm in stale]
            for peer_id in result.excluded_stale:
                # исключается с пометкой, а не берётся устаревшим
                self._peers.add_member(peer_set_version, peer_id,
                                       "excluded_stale", excluded_stale=1)
            status = evaluate("manual", False,
                              peer_members_previous or [],
                              peer_members_current or [])
            result.peer_suspect = status.suspect
            by_concept: dict[str, list[float]] = {}
            measure_ids: dict[str, list[str]] = {}
            peer_of_measure: dict[str, str] = {}
            for peer_id, mid, concept, value, _fresh in fresh:
                if value is None:
                    continue
                by_concept.setdefault(concept, []).append(float(value))
                measure_ids.setdefault(concept, []).append(mid)
                peer_of_measure[mid] = peer_id
            for concept, values in by_concept.items():
                own = computed.get(concept)
                # ТЗ-97 Q8 (решение пользователя 24.09): окно периодов
                # сравнения — 2 года. Пир, чей последний закрытый период
                # старше самого свежего в наборе больше чем на окно,
                # исключается с пометкой, а не отменяет перцентили:
                # один другой фингод (Vodafone — март) больше не стоит
                # всего набора. Строка несёт диапазон включённых.
                mids = measure_ids[concept]
                ends = self._snapshots.period_ends_for_measures(mids)
                window = period_window({peer_of_measure[mid]:
                                        ends.get(mid) or ""
                                        for mid in mids})
                kept, dropped = [], []
                for mid in mids:
                    (dropped if peer_of_measure[mid] in window.excluded
                     else kept).append(mid)
                if dropped:
                    measure_ids[concept] = kept
                    values = [v for mid, v in zip(mids, values)
                              if mid in kept]
                    for mid in dropped:
                        if peer_of_measure[mid] not in \
                                result.excluded_period:
                            result.excluded_period.append(
                                peer_of_measure[mid])
                            # пометка в составе — тем же механизмом, что
                            # у excluded_stale: исключённый виден не
                            # только в этой сборке
                            self._peers.add_member(
                                peer_set_version, peer_of_measure[mid],
                                "excluded_period")
                # строка перцентиля показывает, за какие периоды идёт
                # сравнение; без окон (у пиров нет дат) — как раньше
                pct_start = window.period_from or ""
                pct_end = window.period_to or as_of
                lineage = [{"fact_id": None, "peer_measure_id": mid,
                            "role": "peer"} for mid in measure_ids[concept]]
                lineage += [
                    {"fact_id": None, "peer_measure_id": mid,
                     "role": f"peer: вне окна {peer_of_measure[mid]} "
                             f"{ends.get(mid)}"} for mid in dropped]
                # ТЗ-21 H3: валютный стоп-кран — абсолютные меры в
                # наборе с разными валютами получают currency_mismatch
                # с перечнем валют; ratio/count не трогаются
                currencies: set[str] = set()
                for mid in measure_ids.get(concept, []):
                    currencies |= self._snapshots.currencies_for_measure(mid)
                own_mid = measure_row_ids.get(concept)
                if own_mid:
                    currencies |= self._snapshots.currencies_for_measure(own_mid)
                guard = currency_guard(concept, currencies)
                if guard:
                    self._snapshots.insert_measure_with_lineage(
                        dict(measure_id=str(uuid4()),
                             snapshot_id=snapshot_id,
                             scope="issuer", scope_ref=issuer_id,
                             concept="percentile", value=None,
                             unit="ratio", period_start=pct_start,
                             period_end=pct_end, formula_id="percentile",
                             method_version="v1", null_reason=guard,
                             peer_set_version=peer_set_version),
                        lineage)
                    result.percentiles += 1
                    continue
                share = percentile_share(values, own) if own is not None else None
                if share is None:
                    continue  # порог 5: перцентили не считаются
                self._snapshots.insert_measure_with_lineage(
                    dict(measure_id=str(uuid4()), snapshot_id=snapshot_id,
                         scope="issuer", scope_ref=issuer_id,
                         concept="percentile", value=repr(share),
                         unit="ratio", period_start=pct_start,
                         period_end=pct_end,
                         formula_id="percentile", method_version="v1",
                         null_reason=None, peer_set_version=peer_set_version),
                    lineage)
                result.percentiles += 1
            if result.percentiles == 0:
                self._snapshots.add_block(
                    snapshot_id, "peer_comparison", "missing",
                    "percentile_threshold_not_met")

        result.diff = self._diff(instrument_id, issuer_id, snapshot_id,
                                 peer_members_previous, peer_members_current,
                                 version)

        # ── Покрытие: все восемь блоков существуют после каждой сборки ──
        known = {
            "fundamentals": (
                ("ready", None) if computed
                else ("missing",
                      input_reasons.get("net_margin",
                                        "no_as_reported_facts"))),
            "peer_set": (
                ("ready", None) if peer_set_version
                else ("missing", "peer_set_not_confirmed")),
        }
        if industry_entry is not None:
            known["industry_metrics"] = industry_entry
        self._coverage.ensure_all(instrument_id, known,
                                  source_errors=source_errors)
        return result

    def _issuer_inputs(self, issuer_id: str,
                       as_of: Optional[str] = None) -> IssuerInputs:
        """Входы всех формул §3 по каноническим концептам (TASK-9 V0/V4).

        ТЗ-97 Q10: потоковый вход меры — последние двенадцать месяцев на
        дату as_of (окно собирается в rusterm.core.ttm), а не свежий
        неполный период и не внаглую годовой. Все потоки одной меры
        обязаны прийти из одного окна: разные окна в одной мере —
        смешивание баз. Собрать окно нечем — мера берёт последний общий
        ГОДОВОЙ период входов, и это помечено (period_basis
        'annual_fallback' + названное недостающее слагаемое); нет и
        годового — прежний отказ. Запасной выход и окна уходят в
        IssuerInputs.windows / .fallbacks, чтобы их увидел проход оценки.

        Однопериодные: пересечение периодов входов (unit, start, end),
        приоритет тега карты выбирает источник. Двухпериодные (roe,
        asset_turnover): сток берётся на НАЧАЛО и на КОНЕЦ окна потока,
        иначе missing_prior_period. Цепочка nopat берёт
        ставку из посчитанной effective_tax. Отсутствующий вход назван
        по имени — «missing_data: <концепты>» через запятую в
        отсортированном порядке (X3, TASK-14 A4); нет общего периода —
        period_mismatch. Факт старше _STALE_LOOKBACK_DAYS дней от
        anchor (самого свежего конца периода эмитента) во входы не
        годится (Y2). Причины не сливаются.
        """
        rows = self._snapshots.as_reported_facts(
            issuer_id, tuple(sorted(base_concepts)))
        by_concept: dict[str, list] = {}
        for _concept, value, fact_id, unit, start, end, canonical in rows:
            # ТЗ-22 J3: на дату as_of период, кончившийся позже, ещё не
            # закрыт — такой факт в входы не годится, чей календарь ни
            # был. as_of не задан — фильтра нет (старое поведение).
            if as_of and end > as_of:
                continue
            key = canonical or _concept
            if key not in base_concepts:
                continue
            _taxonomy, local = strip_taxonomy(_concept)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            by_concept.setdefault(key, []).append({
                "value": numeric, "fact_id": fact_id, "unit": unit,
                "start": start, "end": end,
                "rank": priority_rank(key, local, _taxonomy or "us-gaap"),
            })

        # ── Правило давности (TASK-12 Y2) ──
        # anchor — самый свежий period_end среди as_reported фактов
        # эмитента по концептам набора мер. Факт, отстающий от anchor
        # более чем на _STALE_LOOKBACK_DAYS, во входы не годится: тег,
        # которым компания перестала пользоваться, — отсутствующее
        # раскрытие (missing_data), а не period_mismatch. Фильтр живёт
        # в выборке входов, не в as_reported_facts: store хранит всё,
        # и старый факт по-прежнему показывают verify и панель источника.
        anchor = max((r["end"] for rows in by_concept.values()
                      for r in rows), default=None)
        try:
            anchor_date = date.fromisoformat(anchor) if anchor else None
        except (TypeError, ValueError):
            anchor_date = None
        # ТЗ-55 Y1: концепт, вычищенный фильтром давности, — не то же
        # самое, что никогда не поданный: факт был и перестал
        # приходить. Последний известный период запоминается, и отказ
        # по такому входу зовёт stale_data, а не missing_data.
        stale: dict[str, str] = {}
        if anchor_date is not None:
            for key in list(by_concept):
                fresh = [r for r in by_concept[key]
                         if _eligible_input(r["end"], anchor_date)]
                if fresh:
                    by_concept[key] = fresh
                else:
                    stale[key] = max(r["end"] for r in by_concept[key])
                    del by_concept[key]

        def absent_reason(concepts: list[str]) -> str:
            """Отказ по отсутствующим входам: вычищенные давностью —
            stale_data с последним известным периодом, никогда не
            поданные — missing_data (ТЗ-55 Y1)."""
            stale_parts = [f"{c}: last {stale[c]}"
                           for c in concepts if c in stale]
            missing_parts = [c for c in concepts if c not in stale]
            parts = []
            if stale_parts:
                parts.append("stale_data: " + ", ".join(stale_parts))
            if missing_parts:
                parts.append("missing_data: " + ", ".join(missing_parts))
            return "; ".join(parts)

        def pick(concept: str, key: tuple) -> Optional[dict]:
            candidates = [r for r in by_concept.get(concept, [])
                          if (r["unit"], r["start"], r["end"]) == key]
            return min(candidates, key=lambda r: r["rank"]) \
                if candidates else None

        def period_ends(concept: str) -> list[str]:
            return sorted({r["end"] for r in by_concept.get(concept, [])},
                          reverse=True)

        # ── ТЗ-97 Q10: одно TTM-окно на каждый потоковый концепт ──
        # Двери (as_of, правило давности) пройдены выше: окно собирается
        # по тем же строкам, что видят меры, второго запроса нет.
        # Стоки окна не дают: их период короче года, ядро возвращает
        # None, и в windows концепт не попадает.
        unit_by_fact: dict = {}
        for rows in by_concept.values():
            for r in rows:
                unit_by_fact[r["fact_id"]] = r["unit"]
        windows: dict[str, TtmWindow] = {}
        window_units: dict[str, str] = {}
        for key, rows in by_concept.items():
            best: dict = {}
            for r in rows:
                # приоритет тега карты выбирает ОДИН факт на период:
                # пересоставленный факт не должен попасть в слагаемое
                # вместо предпочтительного тега
                span = (r["start"], r["end"])
                if span not in best or r["rank"] < best[span]["rank"]:
                    best[span] = r
            window = ttm_window(
                [(r["value"], r["start"], r["end"], r["fact_id"])
                 for r in best.values()], as_of or anchor or "", key)
            if window is None:
                continue
            units = {unit_by_fact.get(c.fact_id) for c in window.components}
            if len(units) != 1:
                continue  # окно из разных валют — не вход меры (K6)
            windows[key] = window
            window_units[key] = units.pop()

        def flow_window(concepts) -> Optional[TtmWindow]:
            """Общее TTM-окно потоковых входов меры (ТЗ-97 Q10): все
            входы собраны, границы окна одни и те же, валюта одна.
            Иначе None — числитель из трейлинга и знаменатель из
            годового в одной мере смешивать запрещено.

            Равные границы — ещё не равные базы: у потока, для которого
            после годового ничего не подано, годовой и есть окно (база
            `ttm`), а у потока, чьё окно собрать нечем, тот же годовой
            стоит как запасной выход (`annual_fallback`). Два таких входа
            дают одну меру с двумя объяснениями в lineage, и читатель
            карточки не знает, какое верно: база тоже обязана совпасть."""
            found = [windows.get(c) for c in concepts]
            if any(w is None for w in found):
                return None
            first = found[0]
            if any((w.start, w.end) != (first.start, first.end)
                   for w in found[1:]):
                return None
            if any(w.basis != first.basis for w in found[1:]):
                return None
            if len({window_units[c] for c in concepts}) != 1:
                return None
            return first

        inputs: dict[str, dict] = {}
        lineage: dict[str, list] = {}
        reasons: dict[str, str] = {}
        periods: dict[str, tuple[str, str]] = {}
        input_units: dict[str, str] = {}
        fallbacks: dict[str, str] = {}

        # ── Однопериодные формулы ──
        for concept, inputs_map in _MEASURE_FORMULAS.items():
            needed = sorted(set(inputs_map.values()))
            absent = [a for a in needed if a not in by_concept]
            if absent:
                # причина называет концепты, которых не было (X3)
                reasons[concept] = absent_reason(absent)
                continue
            # ТЗ-97 Q10: поток меры — последние двенадцать месяцев, а не
            # свежий неполный период; все входы из одного окна.
            window = flow_window(needed)
            if window is not None:
                inputs[concept] = {kw: windows[a].value
                                   for kw, a in inputs_map.items()}
                lineage[concept] = [row for a in needed
                                    for row in window_lineage(windows[a])]
                periods[concept] = (window.start, window.end)
                input_units[concept] = window_units[needed[0]]
                if window.basis == ANNUAL_FALLBACK:
                    # Та же отметка, что и в общем годовом пути: мера
                    # считана годовой, и это идёт и в lineage, и в окно.
                    fallbacks[concept] = fallback_note(windows, needed)
                continue
            key_sets = [{(r["unit"], r["start"], r["end"])
                         for r in by_concept[a]} for a in needed]
            common = set.intersection(*key_sets)
            if not common:
                reasons[concept] = "period_mismatch"
                continue
            # окна нет — вся мера берёт последний ОБЩИЙ ГОДОВОЙ период
            # входов (числитель и знаменатель одного года); общего года
            # нет — прежнее поведение по свежайшему общему периоду
            annual = [k for k in common if is_annual_window(k[1], k[2])]
            basis = ANNUAL_FALLBACK if annual else None
            # Причина «почему не TTM» обязана быть и здесь: окна меры нет,
            # и названо либо недостающее слагаемое, либо то, что окна
            # входов разные (Q10: смесь окон в одной мере запрещена).
            note = annual_route_note(windows, needed) if basis else ""
            if basis:
                fallbacks[concept] = note
                chosen = max(annual, key=lambda k: (k[2], k[1]))
            else:
                chosen = max(common, key=lambda k: (k[2], k[1]))
            values: dict[str, float] = {}
            lin: list = []
            units: list[str] = []
            for kwarg, a in inputs_map.items():
                row = pick(a, chosen)
                values[kwarg] = row["value"]
                units.append(row["unit"])
                lin.append({"fact_id": row["fact_id"],
                            "peer_measure_id": None,
                            "role": ("input" if basis is None else
                                     fallback_role(chosen[1], chosen[2],
                                                   note)),
                            "period_basis": basis})
            inputs[concept] = values
            lineage[concept] = lin
            periods[concept] = (chosen[1], chosen[2])
            input_units[concept] = units[0]

        # ── ТЗ-102 M3: сток на границе окна может быть подан только в
        # базисе restated (годовой баланс едет в следующем отчёте
        # сравнительной колонкой). as_reported приоритетнее; ДРУГАЯ ДАТА
        # не подставляется — вход берётся ровно на дату границы. Те же
        # двери, что у as_reported: as_of и правило давности от anchor.
        restated_cache: dict[str, dict[str, dict]] = {}

        def restated_rows(concept: str) -> dict[str, dict]:
            """Стоковые строки этого концепта в базисе restated: дата →
            строка входа. Приоритет тега выбирает источник и на этой
            ветке; имя подачи берётся из raw_object-файла, где факт
            прочитан (accession разборщик знает, но в `fact` он не
            пишется)."""
            if concept not in restated_cache:
                by_date: dict[str, dict] = {}
                for (_tag, value, fact_id, unit, start, end, _canonical,
                     url) in self._snapshots.restated_stock_facts(
                        issuer_id, (concept,)):
                    if as_of and end > as_of:
                        continue
                    if anchor_date is not None and not _eligible_input(
                            end, anchor_date):
                        continue
                    try:
                        numeric = float(value)
                    except (TypeError, ValueError):
                        continue
                    _taxonomy, local = strip_taxonomy(_tag)
                    cand = {"value": numeric, "fact_id": fact_id,
                            "unit": unit, "start": start, "end": end,
                            "rank": priority_rank(concept, local,
                                                  _taxonomy or "us-gaap"),
                            "filing": (url or "").rsplit("/", 1)[-1]}
                    prev = by_date.get(end)
                    if prev is None or cand["rank"] < prev["rank"]:
                        by_date[end] = cand
                restated_cache[concept] = by_date
            return restated_cache[concept]

        def stock_at(concept: str, end: str):
            """Сток на дату конца периода: у мгновенной величины только
            эта дата и значима; приоритет тега выбирает источник.
            ТЗ-102 M3: если на ЭТОЙ дате as_reported нет, берётся
            restated того же числа — и помечается в lineage."""
            rows = [r for r in by_concept.get(concept, [])
                    if r["end"] == end]
            if rows:
                return min(rows, key=lambda r: r["rank"])
            return restated_rows(concept).get(end)

        def stock_role(row: dict, basis: str, why: str) -> str:
            """Роль стокового входа: база окна, дата границы и — если сток
            пришёл из restated-подачи — её отметка с именем подачи
            (ТЗ-102 M3). Хвост про несобранный TTM прежний."""
            mark = (f" basis: restated ({row['filing']})"
                    if "filing" in row else "")
            return (f"input:{basis} stock {row['end']}{mark}"
                    + (f"; TTM не собран: {why}" if why else ""))

        # ── Двухпериодные: поток — окно TTM (или годовой запасной),
        # сток — на НАЧАЛО и на КОНЕЦ этого окна; нет предыдущего —
        # missing_prior_period ──
        for concept, (flow, stock) in _TWO_PERIOD_MEASURES.items():
            flow_rows = by_concept.get(flow, [])
            stock_ends = period_ends(stock)
            absent = [a for a in (flow, stock) if a not in by_concept]
            if absent:
                # A4: пропуск называет отсутствующую сторону, как
                # однопериодная ветка (X3)
                reasons[concept] = absent_reason(absent)
                continue
            # ── ТЗ-97 Q10: окно потока задаёт обе даты стока ──
            window = windows.get(flow)
            if window is not None:
                # Сток ищется СТРОГО на границы окна: на его конец и
                # последний не позже начала (баланс на дату года эмитент
                # подаёт днём раньше). Ближайшая «похожая» дата вместо
                # границы — это уже другое окно, а смесь окон Q10
                # запрещает: поток из трейлинга, сток с даты годом
                # раньше даёт меру, которую нельзя прочесть.
                window_end = stock_at(stock, window.end)
                # ТЗ-102 M3: граница «не позже начала окна» ищется по
                # обеим базам: годовой баланс, приехавший сравнительной
                # колонкой, — такой же конец периода, как и поданный
                # свежим отчётом. Даты не подменяются: стока на выбранной
                # дате нет ни в какой базе — прежний period_mismatch.
                borders = sorted(set(stock_ends)
                                 | set(restated_rows(stock)),
                                 reverse=True)
                earlier = [e for e in borders if e <= window.start]
                window_begin = (stock_at(stock, earlier[0])
                                if earlier else None)
                if window_end is None or window_begin is None:
                    reasons[concept] = "period_mismatch"
                    continue
                why = (fallback_note(windows, [flow])
                       if window.basis == ANNUAL_FALLBACK else "")
                if why:
                    fallbacks[concept] = why
                inputs[concept] = {
                    flow: window.value,
                    f"{stock}_begin": window_begin["value"],
                    f"{stock}_end": window_end["value"],
                }
                input_units[concept] = window_units[flow]
                periods[concept] = (window.start, window.end)
                lineage[concept] = window_lineage(window, why) + [
                    {"fact_id": row["fact_id"], "peer_measure_id": None,
                     "role": stock_role(row, window.basis, why),
                     "period_basis": window.basis}
                    for row in (window_end, window_begin)]
                continue
            chosen = max((k for k in
                          {(r["unit"], r["start"], r["end"])
                           for r in flow_rows}
                          if k[2] in stock_ends),
                         key=lambda k: (k[2], k[1]), default=None)
            if chosen is None:
                reasons[concept] = "period_mismatch"
                continue
            chosen_end = chosen[2]
            earlier = [e for e in stock_ends if e < chosen_end]
            if not earlier:
                reasons[concept] = "missing_prior_period"
                continue
            prev_end = earlier[0]
            flow_row = pick(flow, chosen)
            # сток — мгновенная величина: выбирается по концу периода
            cur_rows = [r for r in by_concept[stock]
                        if r["end"] == chosen_end]
            cur_row = min(cur_rows, key=lambda r: r["rank"])
            prev_rows = [r for r in by_concept[stock]
                         if r["end"] == prev_end]
            prev_row = min(prev_rows, key=lambda r: r["rank"])
            if flow_row is None or cur_row is None:
                reasons[concept] = "period_mismatch"
                continue
            inputs[concept] = {
                flow: flow_row["value"],
                f"{stock}_begin": prev_row["value"],
                f"{stock}_end": cur_row["value"],
            }
            input_units[concept] = flow_row["unit"]
            periods[concept] = (chosen[1], chosen_end)
            lineage[concept] = [
                {"fact_id": flow_row["fact_id"], "peer_measure_id": None,
                 "role": "input"},
                {"fact_id": cur_row["fact_id"], "peer_measure_id": None,
                 "role": "input"},
                {"fact_id": prev_row["fact_id"], "peer_measure_id": None,
                 "role": "input"},
            ]

        # ── Цепочка: nopat = operating_income * (1 - effective_tax) ──
        # ставку даёт посчитанная effective_tax — собирается в build()
        oi_rows = by_concept.get("operating_income", [])
        et_period = periods.get("effective_tax")
        # A4: называется то, чего не хватило (ставка или операционная
        # прибыль); оба — через запятую в отсортированном порядке
        absent = []
        if et_period is None:
            absent.append("effective_tax")
        if not oi_rows:
            absent.append("operating_income")
        if absent:
            reasons["nopat"] = absent_reason(sorted(absent))
        else:
            oi_window = windows.get("operating_income")
            if oi_window is not None and \
                    (oi_window.start, oi_window.end) == et_period:
                # ТЗ-97 Q10: ставка и операционная прибыль — из одного
                # окна; window_lineage уже несёт базу периода
                why = (fallback_note(windows, ["operating_income"])
                       if oi_window.basis == ANNUAL_FALLBACK else "")
                if why:
                    fallbacks["nopat"] = why
                inputs["nopat"] = {"operating_income": oi_window.value}
                periods["nopat"] = et_period
                input_units["nopat"] = window_units["operating_income"]
                lineage["nopat"] = window_lineage(oi_window, why)
            else:
                et_end = et_period[1]
                oi_candidates = [r for r in oi_rows if r["end"] == et_end]
                if not oi_candidates:
                    reasons["nopat"] = "period_mismatch"
                else:
                    oi_row = min(oi_candidates, key=lambda r: r["rank"])
                    inputs["nopat"] = {"operating_income": oi_row["value"]}
                    periods["nopat"] = et_period
                    input_units["nopat"] = oi_row["unit"]
                    lineage["nopat"] = [
                        {"fact_id": oi_row["fact_id"],
                         "peer_measure_id": None, "role": "input"},
                    ]

        return IssuerInputs(inputs=inputs, lineage=lineage,
                            reasons=reasons, periods=periods,
                            units=input_units, windows=windows,
                            fallbacks=fallbacks)

    def _next_version(self, instrument_id: str) -> int:
        return self._snapshots.max_version(instrument_id) + 1

    def _latest_canonical(self, issuer_id: str) -> dict:
        """Свежайшее значение по каждому каноническому входу оценочных
        мер: concept -> (value, period_end, currency, fact_id).
        Валюта и fact_id нужны K6 (проверка валют) и lineage."""
        out: dict = {}
        rows = self._snapshots.as_reported_facts(
            issuer_id, _VALUATION_INPUT_CONCEPTS)
        for concept, value, fact_id, _unit, _start, end, canonical in rows:
            key = canonical or concept
            if key not in _VALUATION_INPUT_CONCEPTS:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            prev = out.get(key)
            if prev is None or end > prev[1]:
                currency = self._fact_currency_by_id(fact_id)
                out[key] = (numeric, end, currency, fact_id)
        return out

    def _fact_currency_by_id(self, fact_id: str) -> Optional[str]:
        return self._snapshots.fact_currency(fact_id)

    def _latest_annual_input(self, issuer_id: str, canonical: str,
                             min_days: int = 300) -> tuple | None:
        """ТЗ-69 P1: свежайший ГОДОВОЙ (окно >= min_days дней) факт по
        каноническому входу — знаменатель поток-меры. Квартальный поток
        в знаменателе годовой меры — выдумка, а не значение. Теги
        входа берутся из карты концептов (в фактах — сырые теги)."""
        return self._snapshots.latest_annual_fact(issuer_id, canonical,
                                                  min_days=min_days)

    # ── ТЗ-31 C2: входы оценочных мер из реальных данных ────────────────

    def _nci_never_reported(self, issuer_id: str) -> bool:
        """Истинно, если эмитент НИ РАЗУ не отчитывал неконтролирующую
        долю ни отдельным концептом, ни включённым капиталом: в его
        отчётности нет строки NCI, и 0.0 — производное от набора
        фактов, а не выдумка. Хотя бы один признак NCI — deriving
        невозможен, возвращается False."""
        rows = self._snapshots.as_reported_facts(
            issuer_id, ("minority_interest", "total_equity_incl_nci"))
        return not rows

    def _annual_common_period(self, issuer_id: str,
                              concepts: tuple,
                              note: str = "") -> Optional[dict]:
        """Последний общий ГОДОВОЙ период (350..380 дней) по концептам:
        {concept: (value, fact_id)} с приоритетом карты, иначе None.
        Для ev_ebitda и roic (ТЗ-31 C2): квартальный знаменатель давал
        бы кратную ошибку. ТЗ-97 Q10: это НЕ «честный TTM-эквивалент» —
        это годовой вместо трейлинга, и он помечен `annual_fallback` с
        окном и названной причиной в каждой строке lineage. `note` —
        почему общего окна меры нет."""
        rows = self._snapshots.as_reported_facts(issuer_id, concepts)
        by_concept: dict[str, list] = {}
        for concept, value, fact_id, _unit, start, end, canonical in rows:
            key = canonical or concept
            if key not in concepts:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            by_concept.setdefault(key, []).append(
                {"value": numeric, "fact_id": fact_id, "start": start,
                 "end": end,
                 "rank": priority_rank(key, strip_taxonomy(concept)[1],
                                       strip_taxonomy(concept)[0]
                                       or "us-gaap")})
        if any(c not in by_concept for c in concepts):
            return None
        key_sets = [{(r["start"], r["end"]) for r in by_concept[c]}
                    for c in concepts]
        common = set.intersection(*key_sets)
        annual = [k for k in common
                  if 350 <= (date.fromisoformat(k[1])
                             - date.fromisoformat(k[0])).days <= 380]
        if not annual:
            return None
        start, end = max(annual, key=lambda k: (k[1], k[0]))
        out: dict = {"period": (start, end), "lineage": [], "values": {}}
        for c in concepts:
            row = min((r for r in by_concept[c]
                       if (r["start"], r["end"]) == (start, end)),
                      key=lambda r: r["rank"])
            out["values"][c] = row["value"]
            out["lineage"].append({"fact_id": row["fact_id"],
                                   "peer_measure_id": None,
                                   "role": fallback_role(start, end, note)})
        return out

    def _dps_window(self, issuer_id: str,
                    as_of: str) -> "tuple | str | None":
        """TTM-окно по подачам dps из отчётности (ТЗ-97 Q10): дивиденды
        считаются тем же окном, что и остальные потоки, — четыре подряд
        квартала, алгебра FY + YTD − YTD прошлого года, а если после
        последнего годового ничего не подано, годовой И ЕСТЬ окно.

        Возвращает (окно, валюта), строку отказа stale_data (окно кончилось
        больше _DPS_ANNUAL_STALE_DAYS назад — выплаты могли прекратиться,
        координатор 24.09.2026) либо None, если окна нет. Валюта: все
        слагаемые обязаны быть в одной, иначе окну не доверять (K6)."""
        rows = self._snapshots.duration_facts(issuer_id, "dps")
        if not rows:
            return None
        # duration_facts отдаёт (value, start, end, currency, fact_id)
        # новыми первыми: пересоставленный факт того же периода — тот,
        # что подан позже (ТЗ-22 J2)
        currency_by_fact = {r[4]: r[3] for r in rows}
        window = ttm_window([(r[0], r[1], r[2], r[4]) for r in rows],
                            as_of, "dps")
        if window is None:
            return None
        currencies = {currency_by_fact.get(c.fact_id)
                      for c in window.components}
        if len(currencies) != 1:
            return None
        try:
            age = (date.fromisoformat(as_of)
                   - date.fromisoformat(window.end)).days
        except (TypeError, ValueError):
            return None
        if age > _DPS_ANNUAL_STALE_DAYS:
            return f"stale_data: dps: last {window.end}"
        return (window, currencies.pop())

    def _dps_input(self, dps_fact, issuer_id: str, instrument_id: str,
                   as_of: str, price_currency: Optional[str]):
        """dps для div_yield в порядке источников (ТЗ-31 C2, ТЗ-97 Q10):
        факт dps_ttm → события корпоративных действий (вендорская база =
        база цены, ADR-0020) → окно TTM по подачам dps.

        Возвращает ((значение, конец, валюта), строки lineage, отказ,
        почему TTM не собран). Отказ назван всегда, когда значения нет:
        NULL без причины запрещён (I4)."""
        if dps_fact is not None:
            return ((dps_fact[0], dps_fact[1], dps_fact[2]),
                    self._with_basis(self._fact_lineage(dps_fact[3]),
                                     TTM), None, "")
        events = self._dps_ttm_from_actions(instrument_id, as_of,
                                           price_currency)
        if events is not None:
            return ((events[0], events[1], events[2]),
                    self._with_basis(
                        [{"ca_instrument_id": instrument_id,
                          "ca_ex_date": e["ex_date"],
                          "ca_kind": "dividend", "role": "input"}
                         for e in events[3]], TTM), None, "")
        window = self._dps_window(issuer_id, as_of)
        if isinstance(window, str):
            return (None, [], window, "")
        if window is not None:
            edge, currency = window
            why = fallback_note({"dps": edge}, ["dps"])
            return ((edge.value, edge.end, currency),
                    window_lineage(edge, why), None, why)
        return (None, [], "missing_data: dps_ttm", "")

    def _dps_ttm_from_actions(self, instrument_id: str, as_of: str,
                              price_currency: Optional[str]) -> Optional[tuple]:
        """dps_ttm по скользящему окну 365 дней из corporate_action
        (ТЗ-31 C2): суммы вендора в сегодняшней базе акций — той же,
        что цена (ADR-0020), поэтому отношение корректно. Валюта
        событий обязана совпасть с валютой цены. Возвращает
        (сумма, as_of, валюта, события окна) — события идут в lineage
        меры (миграция 42). Нет окна/репозитория — None: calling
        сторона ставит missing_data: dps_ttm."""
        if self._corp_actions is None:
            return None
        try:
            low = (date.fromisoformat(as_of)
                   - timedelta(days=365)).isoformat()
        except (TypeError, ValueError):
            return None
        events = self._corp_actions.all(instrument_id)
        total = 0.0
        window: list[dict] = []
        for e in events:
            if e["kind"] != "dividend" or e["amount"] is None:
                continue
            if not (low < e["ex_date"] <= as_of):
                continue
            if price_currency and e["currency"] \
                    and e["currency"] != price_currency:
                return None  # K6: разные валюты — не частное
            total += float(e["amount"])
            window.append(e)
        if not window:
            return None
        return (total, as_of, price_currency, window)

    @staticmethod
    def _with_basis(rows: list, basis: str) -> list:
        """Пометить строки lineage базой периода (ТЗ-32 D6: ttm |
        annual) — приближение перестаёт быть невидимым."""
        return [dict(row, period_basis=basis) for row in rows]

    def _fact_lineage(self, fact_id: Optional[str]) -> list:
        if not fact_id:
            return []
        return [{"fact_id": fact_id, "peer_measure_id": None,
                 "role": "input"}]

    def _valuation_pass(self, snapshot_id: str, issuer_id: str,
                        instrument_id: str, as_of: str,
                        computed: dict, written_measures: set,
                        measure_row_ids: dict, result,
                        windows: Optional[dict] = None) -> None:
        """ТЗ-23 K4: шесть мер §3 получают входы.

        Цена — последняя закрытая строка таблицы price не позже as_of
        (K1): нет цены — missing_data: price_close; цена старше порога
        — причина, не число, и никакой перенос вчерашней цены за
        сегодняшний день. Фундаментальные входы — факты по
        каноническим концептам. K6: у ratio-мер числитель и
        знаменатель обязаны быть в одной валюте — иначе
        currency_mismatch, а не частное.
        """
        # Окна TTM считаются один раз в _issuer_inputs и приходят сюда;
        # None — только у вызывающей стороны вне сборки снапшота (тесты
        # старого прогона): тогда потоки считают прежним годовым проходом.
        windows = windows or {}
        price_concepts = ("market_cap", "market_cap_total", "ev", "pb",
                          "ev_ebitda", "div_yield", "roic",
                          "pe", "ps", "fcf_yield")
        price = (self._prices.price_as_of(instrument_id, as_of)
                 if self._prices is not None else None)
        if price is None:
            price_reason = "missing_data: price_close"
            price_value = None
            price_currency = None
        elif price["age_days"] > _PRICE_STALE_DAYS \
                or price["close"] is None:
            price_reason = \
                f"missing_data: price_close_stale:{price['date']}"
            price_value = None
            price_currency = price["currency"]
        else:
            price_reason = None
            price_value = price["close"]
            price_currency = price["currency"]

        inputs = self._latest_canonical(issuer_id)

        def write(concept: str, value, reason, unit: str,
                  lineage: list) -> str:
            if concept in written_measures:
                return ""
            written_measures.add(concept)
            measure_id = str(uuid4())
            self._snapshots.insert_measure_with_lineage(
                dict(measure_id=measure_id, snapshot_id=snapshot_id,
                     scope="issuer", scope_ref=issuer_id, concept=concept,
                     value=None if value is None else repr(value),
                     unit=unit, period_start=as_of, period_end=as_of,
                     formula_id=concept, method_version="v1",
                     null_reason=reason, peer_set_version=None),
                lineage)
            result.measures += 1
            return measure_id

        def mismatch(currencies: list) -> str:
            """ТЗ-91 B3: перечень валют в согласованном порядке; две
            стороны у pb — частный случай того же формата."""
            return ("currency_mismatch: "
                    + ", ".join(sorted({c for c in currencies if c})))

        def fact_currencies(*names: str) -> set:
            return {inputs[n][2] for n in names
                    if inputs.get(n) and inputs[n][2]}

        def money_currency(names: tuple, with_price: bool = False):
            """ТЗ-91 B3: валюта денежной меры — валюта её фактов, а не
            цены: OTC/ADR-бумага с ценой в USD и отчётностью в GBP
            получает GBP под тем же числом. Цена участвует только там,
            где она вход (`with_price` — ev). Вход с пустой валютой в
            спор не вступает: на легасивных строках отказ вытеснил бы
            прежнюю подпись, а не чужой код. Больше одной валюты —
            подписи нет: несуществующему числу валюта не назначается.
            """
            curs = fact_currencies(*names)
            if with_price and price_currency:
                curs.add(price_currency)
            if len(curs) > 1:
                return "", mismatch(sorted(curs))
            return (curs.pop() if curs else ""), None

        def upstream(reason, name: str) -> str:
            """ТЗ-91 B3: отказ входа-меры передаётся наружу своим
            токеном: `missing_data: <name>` на месте назвало бы
            отсутствующим то, что пришло и отклонено по валюте, — та же
            ложь, которую запретил B2."""
            if (reason or "").startswith("currency_mismatch"):
                return reason
            return f"missing_data: {name}"

        def mark_fallback(concept: str, why: str) -> None:
            """ТЗ-97 Q10: мера, прочитанная годовым вместо трейлинга,
            попадает в список пометок — его печатает `rusterm snapshot`
            и показывает окно."""
            if why:
                result.annual_fallbacks.append((concept, why))

        # ── ТЗ-91 B2: меры, которым цена не нужна, считаются всегда ───
        # До этого пункта отказ по цене писался во все 13 строк прохода,
        # и net_debt / net_debt_ebitda / invested_capital стояли пустыми
        # с `missing_data: price_close`, хотя их входы — факты
        # отчётности и ebitda первого прохода.
        debt = inputs.get("total_debt")
        cash = inputs.get("cash")
        stinv = inputs.get("st_investments")
        minority = inputs.get("minority_interest")
        equity = inputs.get("total_equity")
        # ТЗ-32 D7 (вердикт: отсутствие — не ноль): 0.0 требует
        # ПОЛОЖИТЕЛЬНОГО свидетельства — в фактах есть блок капитала
        # (total_equity) и ни разу не отчитан ни один концепт NCI;
        # тогда ноль производен от набора фактов, а его причина видна
        # в lineage ролью nci_absent_in_equity_block на факте блока
        # капитала. Нет блока капитала — minority остаётся None:
        # ev получает missing_data с именем входа.
        nci_lineage: list = []
        if (minority is None and equity is not None
                and self._nci_never_reported(issuer_id)):
            minority = (0.0, None, None, equity[3])
            nci_lineage = [{"fact_id": equity[3],
                            "peer_measure_id": None,
                            "role": "nci_absent_in_equity_block"}]

        # ── ТЗ-68 N1: net_debt = total_debt - cash - st_investments ──
        # ТЗ-91 B2: рынок капитала в формуле не участвует, поэтому
        # отказ `missing_data: market_cap_total` исчез — долг и деньги
        # на месте, числа нет только без них.
        nd_value = None
        nd_reason = None
        nd_unit, nd_conflict = money_currency(
            ("total_debt", "cash", "st_investments"))
        nd_missing = sorted(
            name for name, v in (
                ("total_debt", debt), ("cash", cash),
                ("st_investments", stinv)) if v is None)
        if nd_missing:
            nd_reason = "missing_data: " + ", ".join(nd_missing)
        elif nd_conflict:
            nd_reason = nd_conflict
        else:
            nd_value = (debt[0] - cash[0] - stinv[0])
        nd_lineage = []
        for c in ("total_debt", "cash", "st_investments"):
            if inputs.get(c):
                nd_lineage += self._fact_lineage(inputs[c][3])
        write("net_debt", nd_value, nd_reason,
              measure_unit("net_debt", nd_unit), nd_lineage)

        # net_debt_ebitda = net_debt / ebitda (ratio; ebitda — проход 1)
        # ТЗ-91 B2: у ebitda, отличного от нуля, знаменатель есть —
        # причина называется им, а не missing_data.
        ebitda_value = computed.get("ebitda")
        nde_value = None
        nde_reason = None
        if nd_value is None:
            nde_reason = upstream(nd_reason, "net_debt")
        elif ebitda_value is None:
            nde_reason = "missing_data: ebitda"
        elif ebitda_value <= 0:
            nde_reason = _denominator_refusal(ebitda_value)
        else:
            nde_value = nd_value / ebitda_value
        ebitda_mid = measure_row_ids.get("ebitda")
        nde_lineage = ([{"fact_id": None,
                         "peer_measure_id": ebitda_mid,
                         "role": "from_ebitda"}] if ebitda_mid else [])
        write("net_debt_ebitda", nde_value, nde_reason, "ratio",
              nde_lineage)

        # ТЗ-71 R2: invested_capital = total_equity + total_debt
        # - cash - st_investments (словарь; minority = 0 для AAPL
        # подтверждён ТЗ-68 N3, отсутствие названо в lineage)
        ic_value = None
        ic_reason = None
        ic_unit, ic_conflict = money_currency(
            ("total_equity", "total_debt", "cash", "st_investments"))
        ic_missing = sorted(
            name for name, v in (
                ("total_equity", equity), ("total_debt", debt),
                ("cash", cash), ("st_investments", stinv)) if v is None)
        if ic_missing:
            ic_reason = "missing_data: " + ", ".join(ic_missing)
        elif ic_conflict:
            ic_reason = ic_conflict
        else:
            ic_value = (equity[0] + debt[0] - cash[0] - stinv[0])
        ic_lineage = []
        for c in ("total_equity", "total_debt", "cash", "st_investments"):
            if inputs.get(c):
                ic_lineage += self._fact_lineage(inputs[c][3])
        write("invested_capital", ic_value, ic_reason,
              measure_unit("invested_capital", ic_unit), ic_lineage)

        if price_reason is not None:
            for concept in price_concepts:
                write(concept, None, price_reason, "", [])
            return

        # market_cap (класс) = price_close * shares_outstanding
        shares = inputs.get("shares_outstanding")
        shares_cur = shares[2] if shares else None
        mcap_value = None
        mcap_reason = None
        if shares is None:
            mcap_reason = "missing_data: shares_outstanding"
        elif (stale_shares := _share_count_refusal(shares[1], as_of)):
            # ТЗ-102 M1: давность проверяется раньше валюты — у просрочен-
            # ного числа акций нет права на частное, какой бы валюты оно
            # ни было.
            mcap_reason = stale_shares
        elif shares_cur and price_currency \
                and shares_cur != price_currency:
            mcap_reason = mismatch([shares_cur, price_currency])
        else:
            m = calculate_measure(
                "market_cap", price_close=price_value,
                shares_outstanding=shares[0])
            mcap_value, mcap_reason = m.value, m.null_reason
        write("market_cap", mcap_value, mcap_reason,
              price_currency or "",
              self._fact_lineage(shares[3] if shares else None))

        # market_cap_total = сумма по классам; класс один, если только
        # он раскрыт; неполная сумма запрещена формулой
        total_value = None
        total_reason = None
        if mcap_value is None:
            total_reason = (mcap_reason
                            or "missing_data: shares_outstanding")
        else:
            m = calculate_measure("market_cap_total",
                                  class_caps=[mcap_value])
            total_value, total_reason = m.value, m.null_reason
        write("market_cap_total", total_value, total_reason,
              price_currency or "",
              self._fact_lineage(shares[3] if shares else None))

        # pb = market_cap_total / total_equity; валюты сторон совпадать
        equity_cur = equity[2] if equity else None
        pb_value = None
        pb_reason = None
        if total_value is None:
            pb_reason = "missing_data: market_cap_total"
        elif equity is None:
            pb_reason = "missing_data: total_equity"
        elif equity_cur and price_currency \
                and equity_cur != price_currency:
            pb_reason = mismatch([equity_cur, price_currency])
        else:
            m = calculate_measure("pb", market_cap_total=total_value,
                                  total_equity=equity[0])
            pb_value, pb_reason = m.value, m.null_reason
        write("pb", pb_value, pb_reason, "ratio",
              self._fact_lineage(equity[3] if equity else None))

        # ev = market_cap_total + долг - деньги + меньшинство + префы
        # (входы и решение о нулевом меньшинстве — выше, в блоке мер
        # без цены)
        # ТЗ-91 B3: отказ по отсутствующему входу первее валютного спора —
        # спор касается только тех входов, что на месте, а без входа мера
        # невозможна при любых валютах.
        ev_value = None
        ev_reason = None
        ev_unit, ev_conflict = money_currency(
            ("total_debt", "cash", "st_investments", "minority_interest",
             "preferred_equity"), with_price=True)
        if total_value is None:
            ev_reason = upstream(mcap_reason, "market_cap_total")
        else:
            missing = sorted(
                name for name, v in (
                    ("total_debt", debt), ("cash", cash),
                    ("st_investments", stinv),
                    ("minority_interest", minority)) if v is None)
            if missing:
                ev_reason = "missing_data: " + ", ".join(missing)
            elif ev_conflict:
                ev_reason = ev_conflict
            else:
                m = calculate_measure(
                    "ev", market_cap_total=total_value,
                    total_debt=debt[0], cash=cash[0],
                    st_investments=stinv[0],
                    minority_interest=minority[0],
                    preferred_equity=(inputs.get("preferred_equity")
                                      or (0.0,))[0],
                    preferred_is_separate_class=False)
                ev_value, ev_reason = m.value, m.null_reason
        ev_lineage = []
        for c in ("total_debt", "cash", "st_investments",
                  "minority_interest"):
            if inputs.get(c):
                ev_lineage += self._fact_lineage(inputs[c][3])
        ev_lineage += nci_lineage
        ev_mid = write("ev", ev_value, ev_reason,
                       measure_unit("ev", ev_unit), ev_lineage)

        # ТЗ-97 Q10: pe = market_cap_total / net_income_ttm (словарь) —
        # знаменатель берётся из окна TTM первого прохода; нет окна —
        # прежний свежайший годовой вход (ТЗ-69 P1), квартального потока
        # в мере не бывает ни в одном из путей
        pe_value = None
        pe_lineage: list = []
        ni_win = windows.get("net_income")
        if ni_win is not None:
            if total_value is None:
                pe_reason = "missing_data: market_cap_total"
            elif ni_win.value <= 0:
                # ТЗ-91 B2: у net_income ЕСТЬ число, нет только частного
                pe_reason = _denominator_refusal(ni_win.value)
            else:
                pe_reason = None
                pe_value = total_value / ni_win.value
                why = fallback_note(windows, ["net_income"])
                pe_lineage = window_lineage(ni_win, why)
                mark_fallback("pe", why)
        else:
            annual = self._latest_annual_input(issuer_id, "net_income")
            if annual is None:
                pe_reason = "missing_data: net_income_ttm"
            else:
                ni_value, ni_end, _unit, ni_fact, ni_start, _len = annual
                if total_value is None:
                    pe_reason = "missing_data: market_cap_total"
                elif ni_value <= 0:
                    pe_reason = _denominator_refusal(ni_value)
                else:
                    pe_value = total_value / ni_value
                    pe_reason = None
                    # ТЗ-97 Q10: окно по net_income в проходе не собрало —
                    # мера на последнем годовом, и это помечено так же,
                    # как на остальных запасных годовых путях.
                    why = annual_window_note("net_income")
                    pe_lineage = self._with_basis(
                        [{"fact_id": ni_fact, "peer_measure_id": None,
                          "role": fallback_role(ni_start, ni_end, why)}],
                        ANNUAL_FALLBACK)
                    mark_fallback("pe", why)
        write("pe", pe_value, pe_reason, "ratio", pe_lineage)

        # ps = market_cap_total / revenue_ttm (словарь): то же окно
        ps_value = None
        ps_reason = None
        ps_lineage: list = []
        rev_win = windows.get("revenue")
        if rev_win is not None:
            if total_value is None:
                ps_reason = "missing_data: market_cap_total"
            elif rev_win.value == 0:
                # ТЗ-90 A3: нулевая выручка (pre-revenue эмитент) —
                # отказ по словарю §1.4, а не ZeroDivisionError
                ps_reason = "denominator_zero"
            elif rev_win.value < 0:
                ps_reason = "negative_denominator"
            else:
                ps_value = total_value / rev_win.value
                why = fallback_note(windows, ["revenue"])
                ps_lineage = window_lineage(rev_win, why)
                mark_fallback("ps", why)
        else:
            annual_rev = self._latest_annual_input(issuer_id, "revenue")
            if total_value is None:
                ps_reason = "missing_data: market_cap_total"
            elif annual_rev is None:
                ps_reason = "missing_data: revenue_ttm"
            elif annual_rev[0] == 0:
                # ТЗ-90 A3: нулевая годовая выручка (pre-revenue эмитент) —
                # отказ по словарю §1.4, а не ZeroDivisionError на всю
                # сборку
                ps_reason = "denominator_zero"
            elif annual_rev[0] < 0:
                ps_reason = "negative_denominator"
            else:
                ps_value = total_value / annual_rev[0]
            if annual_rev is not None:
                # ТЗ-97 Q10: то же годовое основание, что и у pe — помечено
                # окном и причиной, а не молча «годовое окно» в lineage.
                why = annual_window_note("revenue")
                ps_lineage = self._with_basis(
                    [{"fact_id": annual_rev[3], "peer_measure_id": None,
                      "role": fallback_role(annual_rev[4], annual_rev[1],
                                            why)}], ANNUAL_FALLBACK)
                if ps_value is not None:
                    mark_fallback("ps", why)
        write("ps", ps_value, ps_reason, "ratio", ps_lineage)

        # fcf_yield = fcf_ttm / market_cap (класс, словарь)
        fcf_value = computed.get("fcf")
        fcfy_value = None
        fcfy_reason = None
        if mcap_value is None:
            fcfy_reason = "missing_data: market_cap"
        elif fcf_value is None:
            fcfy_reason = "missing_data: fcf"
        else:
            fcfy_value = fcf_value / mcap_value
        fcf_mid = measure_row_ids.get("fcf")
        fcfy_lineage = ([{"fact_id": None,
                          "peer_measure_id": fcf_mid,
                          "role": "from_fcf"}] if fcf_mid else [])
        write("fcf_yield", fcfy_value, fcfy_reason, "ratio",
              fcfy_lineage)

        # ev_ebitda = ev / ebitda — ratio: обе стороны уже в одной
        # валюте (ev отказан по валютам своих входов выше, ebitda —
        # валюты фактов эмитента).
        # ТЗ-97 Q10: знаменатель — окно TTM по слагаемым ebitda; нет
        # окна — прежний годовой общий период (ТЗ-31 C2), и он же
        # последняя опора перед мерой первого прохода.
        ebitda_value = computed.get("ebitda")
        ebitda_mid = measure_row_ids.get("ebitda")
        oi_win = windows.get("operating_income")
        dna_win = windows.get("d_and_a")
        if ev_reason is not None and ev_value is None:
            write("ev_ebitda", None, upstream(ev_reason, "ev"), "ratio", [])
        elif (oi_win is not None and dna_win is not None
                and (oi_win.start, oi_win.end) == (dna_win.start,
                                                   dna_win.end)):
            why = fallback_note(windows, ["operating_income", "d_and_a"])
            m = calculate_measure("ev_ebitda", ev=ev_value,
                                  ebitda_ttm=oi_win.value + dna_win.value)
            write("ev_ebitda", m.value, m.null_reason, "ratio",
                  self._with_basis(
                      [{"fact_id": None, "peer_measure_id": ev_mid,
                        "role": "input"}], oi_win.basis)
                  + window_lineage(oi_win, why)
                  + window_lineage(dna_win, why))
            mark_fallback("ev_ebitda", why)
        else:
            # ТЗ-97 Q10: общего окна EBITDA не собрало (окна её потоков
            # разошлись или одного из них нет) — мера садится на последний
            # общий ГОДОВОЙ период и помечается как запасной выход, а не
            # как TTM.
            ebitda_flows = ("operating_income", "d_and_a")
            why = annual_route_note(windows, ebitda_flows)
            annual_ebitda = self._annual_common_period(
                issuer_id, ebitda_flows, why)
            if annual_ebitda is not None:
                m = calculate_measure(
                    "ev_ebitda", ev=ev_value,
                    ebitda_ttm=annual_ebitda["values"]["operating_income"]
                    + annual_ebitda["values"]["d_and_a"])
                write("ev_ebitda", m.value, m.null_reason, "ratio",
                      self._with_basis(
                          [{"fact_id": None, "peer_measure_id": ev_mid,
                            "role": "input"}]
                          + annual_ebitda["lineage"], ANNUAL_FALLBACK))
                mark_fallback("ev_ebitda", why)
            elif ebitda_value is None or not ebitda_mid:
                write("ev_ebitda", None, "missing_data: ebitda", "ratio",
                      [])
            else:
                m = calculate_measure("ev_ebitda", ev=ev_value,
                                      ebitda_ttm=ebitda_value)
                # I4: входы — МЕРЫ (ev и ebitda), lineage идёт по
                # peer_measure_id на их строки
                write("ev_ebitda", m.value, m.null_reason, "ratio",
                      [{"fact_id": None, "peer_measure_id": ev_mid,
                        "role": "input"},
                       {"fact_id": None, "peer_measure_id": ebitda_mid,
                        "role": "input"}])

        # div_yield = dps_ttm / price_close — валюты обязаны совпасть.
        # ТЗ-97 Q10: dps приведены к той же функции окна, что и
        # остальные потоки (было: квартальная цепочка и годовой вход
        # двумя отдельными маршрутами с ручным выбором свежего).
        dps, dps_lineage, dps_refusal, why = self._dps_input(
            inputs.get("dps_ttm"), issuer_id, instrument_id, as_of,
            price_currency)
        mark_fallback("div_yield", why)
        dps_cur = dps[2] if dps else None
        if dps is None:
            write("div_yield", None, dps_refusal, "ratio", dps_lineage)
        elif dps_cur and price_currency and dps_cur != price_currency:
            write("div_yield", None, mismatch([dps_cur, price_currency]),
                  "ratio", dps_lineage)
        else:
            m = calculate_measure("div_yield", dps_ttm=dps[0],
                                  price_close=price_value)
            write("div_yield", m.value, m.null_reason, "ratio", dps_lineage)

        # roic = nopat / avg(invested_capital) — оба входа в валюте
        # отчётности; nopat посчитан из тех же фактов (K6: одна валюта)
        ic = inputs.get("invested_capital")
        ic_lineage_extra: list = []
        if ic is None:
            # ТЗ-31 C2: производный инвестированный капитал по формуле
            # словаря из фактов последнего момента; NCI — по правилу
            # нулевого меньшинства выше
            te, td = inputs.get("total_equity"), inputs.get("total_debt")
            c, si = inputs.get("cash"), inputs.get("st_investments")
            if None not in (te, td, c, si, minority):
                # ТЗ-91 B3: подпись этого числа — валюта тех же фактов,
                # из которых оно собрано, а не валюта цены: roic читает
                # отсюда свою знаменательную сторону.
                ic = (invested_capital(te[0], minority[0], td[0], c[0],
                                       si[0]), None,
                      money_currency(("total_equity", "total_debt", "cash",
                                      "st_investments",
                                      "minority_interest"))[0],
                      None)
                ic_lineage_extra = nci_lineage
        # ТЗ-91 B3: стороны roic — поток nopat и моментный капитал;
        # больше одной валюты между ними — K6-отказ, а не частное.
        # Валюта числителя берётся с уже записанной строки nopat: его
        # слагаемые — потоки, а они в этот проход не попадают.
        nopat_mid = measure_row_ids.get("nopat")
        roic_curs: set = set()
        if nopat_mid:
            roic_curs = {c for c
                         in self._snapshots.currencies_for_measure(nopat_mid)
                         if c}
        if ic is not None and ic[2]:
            roic_curs.add(ic[2])
        roic_conflict = (mismatch(sorted(roic_curs))
                         if len(roic_curs) > 1 else None)
        annual_nopat = None
        nop = computed.get("nopat")
        # ТЗ-97 Q10: поток roic (nopat) — из общего окна TTM его
        # слагаемых; знаменатель остаётся моментным значением
        # производного invested_capital (ТЗ-31 C2) — см. отклонение в
        # отчёте
        roi_flows = ("operating_income", "tax_expense", "pretax_income")
        roi_windows = [windows.get(c) for c in roi_flows]
        roi_window = (roi_windows[0]
                      if all(w is not None for w in roi_windows) and
                      len({(w.start, w.end) for w in roi_windows}) == 1
                      else None)
        if roi_window is None:
            # Окна нет — знаменатель меры берёт последний ОБЩИЙ ГОДОВОЙ
            # период, и помечается он как запасной выход, а не как TTM.
            roi_note = annual_route_note(windows, list(roi_flows))
            annual_nopat = self._annual_common_period(issuer_id,
                                                      roi_flows, roi_note)
        if ic is None:
            write("roic", None, "missing_data: invested_capital",
                  "ratio", [])
        elif roic_conflict is not None:
            write("roic", None, roic_conflict, "ratio", [])
        elif roi_window is not None:
            values = dict(zip(roi_flows, roi_windows))
            why = fallback_note(windows, list(roi_flows))
            rate, _rate_reason = effective_tax_rate(
                values["tax_expense"].value,
                values["pretax_income"].value)
            nop_value = (nopat(values["operating_income"].value, rate)
                         if rate is not None else None)
            lineage = self._with_basis(
                window_lineage(values["operating_income"], why)
                + window_lineage(values["tax_expense"], why)
                + window_lineage(values["pretax_income"], why)
                + self._fact_lineage(ic[3]) + ic_lineage_extra,
                roi_window.basis)
            if nop_value is None:
                write("roic", None, "missing_data: nopat", "ratio",
                      lineage)
            else:
                m = calculate_measure("roic", nopat=nop_value,
                                      invested_capital_begin=ic[0],
                                      invested_capital_end=ic[0])
                write("roic", m.value, m.null_reason, "ratio", lineage)
                mark_fallback("roic", why)
        elif annual_nopat is not None:
            rate, rate_reason = effective_tax_rate(
                annual_nopat["values"]["tax_expense"],
                annual_nopat["values"]["pretax_income"])
            nop_value = nopat(annual_nopat["values"]["operating_income"],
                              rate) if rate is not None else None
            if nop_value is None:
                write("roic", None, "missing_data: nopat", "ratio",
                      self._with_basis(annual_nopat["lineage"],
                                       ANNUAL_FALLBACK))
            else:
                m = calculate_measure("roic", nopat=nop_value,
                                      invested_capital_begin=ic[0],
                                      invested_capital_end=ic[0])
                write("roic", m.value, m.null_reason, "ratio",
                      self._with_basis(
                          annual_nopat["lineage"]
                          + self._fact_lineage(ic[3])
                          + ic_lineage_extra, ANNUAL_FALLBACK))
                mark_fallback("roic", roi_note)
        elif nop is None:
            write("roic", None, "missing_data: nopat", "ratio", [])
        else:
            m = calculate_measure("roic", nopat=nop,
                                  invested_capital_begin=ic[0],
                                  invested_capital_end=ic[0])
            write("roic", m.value, m.null_reason, "ratio",
                  self._fact_lineage(ic[3]))

    def _diff(self, instrument_id, issuer_id, snapshot_id,
              peer_prev, peer_cur, version) -> SnapshotDiff:
        diff = SnapshotDiff()
        # ТЗ-90 A3: базой сравнения служит последняя ГОТОВАЯ версия —
        # своя building-строка этой сборки версией ниже не является.
        prev_snapshot_id = self._snapshots.previous_snapshot(
            instrument_id, before_version=version)
        if prev_snapshot_id:
            prev = {m[3]: m[4] for m in self._snapshots.get_measures(prev_snapshot_id)
                    if m[3] != "percentile" and m[4] is not None}
            cur = {m[3]: m[4] for m in self._snapshots.get_measures(snapshot_id)
                   if m[3] != "percentile" and m[4] is not None}
            diff.metric_changes = [(c, old, cur[c])
                                   for c, old in prev.items()
                                   if cur.get(c) is not None and cur[c] != old]
        if peer_prev is not None and peer_cur is not None:
            diff.peer_set_changes = [(sorted(set(peer_cur) - set(peer_prev)),
                                      sorted(set(peer_prev) - set(peer_cur)))]
        diff.revisions = [(c, p) for c, p
                          in self._snapshots.restated_revisions(issuer_id)]
        return diff


def snapshot_measures_identical(rows_a: list, rows_b: list) -> bool:
    """ТЗ-64 J5: содержимое двух снапшотов совпадает — те же меры с
    теми же величинами, единицами, периодами и причинами отказов.
    Версия и идентификаторы не участвуют: сбор на тех же входах не
    должен выдавать себя за изменение."""
    def key(rows):
        return sorted((m[3], str(m[4]), m[5], m[6], m[7],
                       (m[10] or "")) for m in rows)
    return key(rows_a) == key(rows_b)
