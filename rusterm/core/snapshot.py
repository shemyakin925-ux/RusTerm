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

from rusterm.core.peers import currency_guard, evaluate, percentile_share
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
    "invested_capital", "total_return", "drawdown", "price_adj", "hhi",
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

# ТЗ-22 J3: сравнивать величины пиров с разрывом концов периодов больше
# ста дней нельзя честно — ноябрь против июня. Порог примерно в квартал
# с люфтом; причина — существующая period_mismatch, новой нет.
_PERIOD_GAP_DAYS = 100


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
class BuildResult:
    snapshot_id: str
    version: int
    measures: int = 0
    percentiles: int = 0
    excluded_stale: list = field(default_factory=list)
    peer_suspect: bool = False
    diff: SnapshotDiff = field(default_factory=SnapshotDiff)


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
        """
        version = self._next_version(instrument_id)
        snapshot_id = str(uuid4())
        self._snapshots.create_snapshot(snapshot_id, instrument_id, version,
                                        as_of, peer_set_version,
                                        "unverified" if peer_set_version else "none",
                                        "ready")
        self._snapshots.add_block(snapshot_id, "fundamentals", "ready", None)
        result = BuildResult(snapshot_id=snapshot_id, version=version)

        # ── Проход 1: формулы §3, чьи входы в карте V0 ──
        inputs, lineage_by_concept, input_reasons, periods, input_units = \
            self._issuer_inputs(issuer_id, as_of=as_of)
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
                        # причина исходных входов не перекрывается
                        missing_chain = sorted(
                            {source for source in _CHAIN_MEASURES.get(
                                concept, {}).values()
                             if computed.get(source) is None})
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
                             measure_row_ids, result)

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
                computed = sum(1 for m in metrics
                               if m["value"] is not None)
                grey = [f"{m['concept']} ({m['reason']})"
                        for m in metrics if m["value"] is None]
                method = (metrics[0]["method_version"] if metrics
                          else "unknown")
                status = "ready" if computed else "missing"
                reason = (f"computed {computed}/{len(metrics)} "
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
            for peer_id, mid, concept, value, _fresh in fresh:
                if value is None:
                    continue
                by_concept.setdefault(concept, []).append(float(value))
                measure_ids.setdefault(concept, []).append(mid)
            for concept, values in by_concept.items():
                own = computed.get(concept)
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
                    lineage = [{"fact_id": None, "peer_measure_id": mid,
                                "role": "peer"}
                               for mid in measure_ids[concept]]
                    self._snapshots.insert_measure_with_lineage(
                        dict(measure_id=str(uuid4()),
                             snapshot_id=snapshot_id,
                             scope="issuer", scope_ref=issuer_id,
                             concept="percentile", value=None,
                             unit="ratio", period_start="",
                             period_end=as_of, formula_id="percentile",
                             method_version="v1", null_reason=guard,
                             peer_set_version=peer_set_version),
                        lineage)
                    result.percentiles += 1
                    continue
                # ТЗ-22 J3: у пиров на разных календарях свои последние
                # закрытые периоды; разрыв больше порога — честный отказ
                ends = sorted(e for e in
                              self._snapshots.period_ends_for_measures(
                                  measure_ids[concept]).values()
                              if e)
                if len(ends) >= 2 and (
                        date.fromisoformat(ends[-1])
                        - date.fromisoformat(ends[0])).days \
                        > _PERIOD_GAP_DAYS:
                    lineage = [{"fact_id": None, "peer_measure_id": mid,
                                "role": "peer"}
                               for mid in measure_ids[concept]]
                    self._snapshots.insert_measure_with_lineage(
                        dict(measure_id=str(uuid4()),
                             snapshot_id=snapshot_id,
                             scope="issuer", scope_ref=issuer_id,
                             concept="percentile", value=None,
                             unit="ratio", period_start="",
                             period_end=as_of, formula_id="percentile",
                             method_version="v1",
                             null_reason="period_mismatch",
                             peer_set_version=peer_set_version),
                        lineage)
                    result.percentiles += 1
                    continue
                share = percentile_share(values, own) if own is not None else None
                if share is None:
                    continue  # порог 5: перцентили не считаются
                lineage = [{"fact_id": None, "peer_measure_id": mid,
                            "role": "peer"} for mid in measure_ids[concept]]
                self._snapshots.insert_measure_with_lineage(
                    dict(measure_id=str(uuid4()), snapshot_id=snapshot_id,
                         scope="issuer", scope_ref=issuer_id,
                         concept="percentile", value=repr(share),
                         unit="ratio", period_start="", period_end=as_of,
                         formula_id="percentile", method_version="v1",
                         null_reason=None, peer_set_version=peer_set_version),
                    lineage)
                result.percentiles += 1
            if result.percentiles == 0:
                self._snapshots.add_block(
                    snapshot_id, "peer_comparison", "missing",
                    "percentile_threshold_not_met")

        result.diff = self._diff(instrument_id, issuer_id, snapshot_id,
                                 peer_members_previous, peer_members_current)

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
                       as_of: Optional[str] = None) -> tuple[dict, dict, dict,
                                                       dict, dict]:
        """Входы всех формул §3 по каноническим концептам (TASK-9 V0/V4).

        Однопериодные: пересечение периодов входов (unit, start, end),
        приоритет тега карты выбирает источник. Двухпериодные (roe,
        asset_turnover): конец выбранного периода + предыдущий период
        того же стока, иначе missing_prior_period. Цепочка nopat берёт
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

        inputs: dict[str, dict] = {}
        lineage: dict[str, list] = {}
        reasons: dict[str, str] = {}
        periods: dict[str, tuple[str, str]] = {}
        input_units: dict[str, str] = {}

        # ── Однопериодные формулы ──
        for concept, inputs_map in _MEASURE_FORMULAS.items():
            needed = set(inputs_map.values())
            absent = sorted(a for a in needed if a not in by_concept)
            if absent:
                # причина называет концепты, которых не было (X3)
                reasons[concept] = absent_reason(sorted(absent))
                continue
            key_sets = [{(r["unit"], r["start"], r["end"])
                         for r in by_concept[a]} for a in needed]
            common = set.intersection(*key_sets)
            if not common:
                reasons[concept] = "period_mismatch"
                continue
            chosen = max(common, key=lambda k: (k[2], k[1]))
            values: dict[str, float] = {}
            lin: list = []
            units: list[str] = []
            for kwarg, a in inputs_map.items():
                row = pick(a, chosen)
                values[kwarg] = row["value"]
                units.append(row["unit"])
                lin.append({"fact_id": row["fact_id"],
                            "peer_measure_id": None, "role": "input"})
            inputs[concept] = values
            lineage[concept] = lin
            periods[concept] = (chosen[1], chosen[2])
            input_units[concept] = units[0]

        # ── Двухпериодные: конец выбранного периода + предыдущий период
        # того же стока; нет предыдущего — missing_prior_period ──
        for concept, (flow, stock) in _TWO_PERIOD_MEASURES.items():
            flow_rows = by_concept.get(flow, [])
            stock_ends = period_ends(stock)
            absent = sorted(a for a in (flow, stock)
                            if a not in by_concept)
            if absent:
                # A4: пропуск называет отсутствующую сторону, как
                # однопериодная ветка (X3)
                reasons[concept] = absent_reason(sorted(absent))
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
                    {"fact_id": oi_row["fact_id"], "peer_measure_id": None,
                     "role": "input"},
                ]

        return inputs, lineage, reasons, periods, input_units

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
                              concepts: tuple) -> Optional[dict]:
        """Последний общий ГОДОВОЙ период (350..380 дней) по концептам:
        {concept: (value, fact_id)} с приоритетом карты, иначе None.
        Для ev_ebitda и roic (ТЗ-31 C2): квартальный знаменатель давал
        бы кратную ошибку; годовой период отчётности — честный TTM-
        эквивалент, период виден в строках lineage."""
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
                                   "role": "input"})
        return out

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
                        measure_row_ids: dict, result) -> None:
        """ТЗ-23 K4: шесть мер §3 получают входы.

        Цена — последняя закрытая строка таблицы price не позже as_of
        (K1): нет цены — missing_data: price_close; цена старше порога
        — причина, не число, и никакой перенос вчерашней цены за
        сегодняшний день. Фундаментальные входы — факты по
        каноническим концептам. K6: у ratio-мер числитель и
        знаменатель обязаны быть в одной валюте — иначе
        currency_mismatch, а не частное.
        """
        concepts = ("market_cap", "market_cap_total", "ev", "pb",
                    "ev_ebitda", "div_yield", "roic",
                    "pe", "ps", "fcf_yield", "net_debt",
                    "net_debt_ebitda")
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

        def mismatch(pair: list) -> str:
            a, b = sorted(pair)
            return f"currency_mismatch: {a}, {b}"

        if price_reason is not None:
            for concept in concepts:
                write(concept, None, price_reason, "", [])
            return

        # market_cap (класс) = price_close * shares_outstanding
        shares = inputs.get("shares_outstanding")
        shares_cur = shares[2] if shares else None
        mcap_value = None
        mcap_reason = None
        if shares is None:
            mcap_reason = "missing_data: shares_outstanding"
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
        equity = inputs.get("total_equity")
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
        debt = inputs.get("total_debt")
        cash = inputs.get("cash")
        stinv = inputs.get("st_investments")
        minority = inputs.get("minority_interest")
        # ТЗ-32 D7 (вердикт: отсутствие — не ноль): 0.0 требует
        # ПОЛОЖИТЕЛЬНОГО свидетельства — в фактах есть блок капитала
        # (total_equity) и ни разу не отчитан ни один концепт NCI;
        # тогда ноль производен от набора фактов, а его причина видна
        # в lineage ролью nci_absent_in_equity_block на факте блока
        # капитала. Нет блока капитала — minority остаётся None:
        # ev получает missing_data с именем входа.
        nci_lineage: list = []
        equity = inputs.get("total_equity")
        if minority is None and equity is not None                 and self._nci_never_reported(issuer_id):
            minority = (0.0, None, None, equity[3])
            nci_lineage = [{"fact_id": equity[3],
                            "peer_measure_id": None,
                            "role": "nci_absent_in_equity_block"}]
        ev_value = None
        ev_reason = None
        if total_value is None:
            ev_reason = "missing_data: market_cap_total"
        else:
            missing = sorted(
                name for name, v in (
                    ("total_debt", debt), ("cash", cash),
                    ("st_investments", stinv),
                    ("minority_interest", minority)) if v is None)
            if missing:
                ev_reason = "missing_data: " + ", ".join(missing)
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
        ev_mid = write("ev", ev_value, ev_reason, price_currency or "",
                       ev_lineage)

        # ── ТЗ-68 N1: net_debt = total_debt - cash - st_investments ──
        nd_value = None
        nd_reason = None
        if total_value is None:
            nd_reason = "missing_data: market_cap_total"
        else:
            missing = sorted(
                name for name, v in (
                    ("total_debt", debt), ("cash", cash),
                    ("st_investments", stinv)) if v is None)
            if missing:
                nd_reason = "missing_data: " + ", ".join(missing)
            else:
                nd_value = (debt[0] - cash[0] - stinv[0])
        nd_lineage = []
        for c in ("total_debt", "cash", "st_investments"):
            if inputs.get(c):
                nd_lineage += self._fact_lineage(inputs[c][3])
        nd_mid = write("net_debt", nd_value, nd_reason,
                       price_currency or "", nd_lineage)

        # net_debt_ebitda = net_debt / ebitda (ratio; ebitda — проход 1)
        ebitda_value = computed.get("ebitda")
        nde_value = None
        nde_reason = None
        if nd_value is None:
            nde_reason = "missing_data: net_debt"
        elif ebitda_value is None or ebitda_value <= 0:
            nde_reason = "missing_data: ebitda"
        else:
            nde_value = nd_value / ebitda_value
        ebitda_mid = measure_row_ids.get("ebitda")
        nde_lineage = ([{"fact_id": None,
                         "peer_measure_id": ebitda_mid,
                         "role": "from_ebitda"}] if ebitda_mid else [])
        write("net_debt_ebitda", nde_value, nde_reason, "ratio",
              nde_lineage)

        # ТЗ-69 P1: pe = market_cap_total / net_income_ttm (словарь) —
        # знаменатель: свежайший ГОДОВОЙ (>= 300 дней) net_income;
        # квартального потока в годовой мере не бывает
        annual = self._latest_annual_input(issuer_id, "net_income")
        if annual is None:
            pe_reason = "missing_data: net_income_ttm"
            pe_lineage = []
            pe_value = None
        else:
            ni_value, ni_end, _unit, ni_fact, ni_start, _len = annual
            if total_value is None:
                pe_reason = "missing_data: market_cap_total"
                pe_lineage = []
                pe_value = None
            elif ni_value <= 0:
                pe_reason = "missing_data: net_income"
                pe_lineage = []
                pe_value = None
            else:
                pe_value = total_value / ni_value
                pe_reason = None
                pe_lineage = [{"fact_id": ni_fact,
                               "peer_measure_id": None,
                               "role": (f"input:годовое окно "
                                        f"{ni_start}…{ni_end}")}]
        write("pe", pe_value, pe_reason, "ratio", pe_lineage)

        # ps = market_cap_total / revenue_ttm (словарь): годовой вход
        annual_rev = self._latest_annual_input(issuer_id, "revenue")
        ps_value = None
        ps_reason = None
        if total_value is None:
            ps_reason = "missing_data: market_cap_total"
        elif annual_rev is None:
            ps_reason = "missing_data: revenue_ttm"
        else:
            ps_value = total_value / annual_rev[0]
        ps_lineage = ([{"fact_id": annual_rev[3],
                        "peer_measure_id": None,
                        "role": (f"input:годовое окно "
                                 f"{annual_rev[4]}…{annual_rev[1]}")}]
                      if annual_rev is not None else [])
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
        # валюте (ev наследует валюту цены, ebitda — валюту фактов
        # эмитента); разные валюты фактов отсечены стражем выше.
        # ТЗ-31 C2: знаменатель — ГОДОВОЙ общий период (TTM-
        # эквивалент): квартальный ebitda давал бы кратную ошибку;
        # нет годового — прежнее поведение (мера ebitda первого
        # прохода, период виден в её строке)
        ebitda_value = computed.get("ebitda")
        ebitda_mid = measure_row_ids.get("ebitda")
        if ev_reason is not None and ev_value is None:
            write("ev_ebitda", None, "missing_data: ev", "ratio", [])
        else:
            annual_ebitda = self._annual_common_period(
                issuer_id, ("operating_income", "d_and_a"))
            if annual_ebitda is not None:
                m = calculate_measure(
                    "ev_ebitda", ev=ev_value,
                    ebitda_ttm=annual_ebitda["values"]["operating_income"]
                    + annual_ebitda["values"]["d_and_a"])
                write("ev_ebitda", m.value, m.null_reason, "ratio",
                      self._with_basis(
                          [{"fact_id": None, "peer_measure_id": ev_mid,
                            "role": "input"}]
                          + annual_ebitda["lineage"], "annual"))
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
        # ТЗ-31 C2: нет факта dps_ttm — TTM по скользящему окну 365
        # дней из corporate_action (вендорская база = база цены,
        # ADR-0020); валюты сверяются тем же правилом K6
        dps = inputs.get("dps_ttm")
        if dps is None:
            dps = self._dps_ttm_from_actions(instrument_id, as_of,
                                             price_currency)
        dps_cur = dps[2] if dps else None
        if dps is None:
            write("div_yield", None, "missing_data: dps_ttm", "ratio",
                  [])
        elif dps_cur and price_currency and dps_cur != price_currency:
            write("div_yield", None,
                  mismatch([dps_cur, price_currency]), "ratio",
                  self._fact_lineage(dps[3]))
        else:
            m = calculate_measure("div_yield", dps_ttm=dps[0],
                                  price_close=price_value)
            # ТЗ-31 C2: dps_ttm из corporate_action несёт lineage на
            # события окна (миграция 42); факт-маршрут — как прежде
            if isinstance(dps[3], list) and dps[3]:
                lineage = self._with_basis(
                    [{"ca_instrument_id": instrument_id,
                      "ca_ex_date": e["ex_date"],
                      "ca_kind": "dividend", "role": "input"}
                     for e in dps[3]], "ttm")
            else:
                lineage = self._with_basis(
                    self._fact_lineage(dps[3]), "ttm")
            write("div_yield", m.value, m.null_reason, "ratio", lineage)

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
                ic = (invested_capital(te[0], minority[0], td[0], c[0],
                                       si[0]), None, price_currency,
                      None)
                ic_lineage_extra = nci_lineage
        annual_nopat = self._annual_common_period(
            issuer_id, ("operating_income", "tax_expense",
                        "pretax_income"))
        nop = computed.get("nopat")
        if ic is None:
            write("roic", None, "missing_data: invested_capital",
                  "ratio", [])
        elif annual_nopat is not None:
            rate, rate_reason = effective_tax_rate(
                annual_nopat["values"]["tax_expense"],
                annual_nopat["values"]["pretax_income"])
            nop_value = nopat(annual_nopat["values"]["operating_income"],
                              rate) if rate is not None else None
            if nop_value is None:
                write("roic", None, "missing_data: nopat", "ratio",
                      annual_nopat["lineage"])
            else:
                m = calculate_measure("roic", nopat=nop_value,
                                      invested_capital_begin=ic[0],
                                      invested_capital_end=ic[0])
                write("roic", m.value, m.null_reason, "ratio",
                      self._with_basis(
                          annual_nopat["lineage"]
                          + self._fact_lineage(ic[3])
                          + ic_lineage_extra, "annual"))
        elif nop is None:
            write("roic", None, "missing_data: nopat", "ratio", [])
        else:
            m = calculate_measure("roic", nopat=nop,
                                  invested_capital_begin=ic[0],
                                  invested_capital_end=ic[0])
            write("roic", m.value, m.null_reason, "ratio",
                  self._fact_lineage(ic[3]))

    def _diff(self, instrument_id, issuer_id, snapshot_id,
              peer_prev, peer_cur) -> SnapshotDiff:
        diff = SnapshotDiff()
        prev_snapshot_id = self._snapshots.previous_snapshot(instrument_id)
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
