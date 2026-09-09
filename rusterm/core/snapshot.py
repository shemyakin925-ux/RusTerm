"""Сборка снапшота — процесс 2 по docs/processes.md §124-196.

Два прохода: фундаментальные меры считаются по компании независимо;
перцентили — только по уже посчитанным величинам пиров. Пир без свежих
данных исключается из расчёта с пометкой excluded_stale, не берётся
устаревшим. Три вида diff раздельны: изменение метрик, эффект пересостава
peer set, появившиеся ревизии (ADR-0002: смешивать первые два запрещено).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from rusterm.core.peers import evaluate, percentile_share
from rusterm.formulas import calculate_measure, measure_unit
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
_TWO_PERIOD_MEASURES: dict[str, tuple[str, str]] = {
    "roe": ("net_income", "total_equity"),
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
_UNMAPPED_FORMULAS: tuple[str, ...] = (
    "invested_capital", "roic", "net_debt", "net_debt_ebitda",
    "fcf_yield", "market_cap", "market_cap_total", "ev", "pe", "pb",
    "ps", "ev_ebitda", "div_yield", "total_return", "drawdown",
    "price_adj", "hhi",
)

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


def _eligible_input(period_end: str, anchor_date: date) -> bool:
    """Входной факт годен, пока его конец отстаёт от anchor не более
    чем на _STALE_LOOKBACK_DAYS дней; неразбираемая дата не
    отбрасывается."""
    try:
        return (anchor_date - date.fromisoformat(period_end)).days \
            <= _STALE_LOOKBACK_DAYS
    except (TypeError, ValueError):
        return True


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

    def __init__(self, snapshot_repo, peer_set_repo, coverage_repo):
        self._snapshots = snapshot_repo
        self._peers = peer_set_repo
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
            self._issuer_inputs(issuer_id)
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

        result.diff = self._diff(instrument_id, snapshot_id,
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
        self._coverage.ensure_all(instrument_id, known,
                                  source_errors=source_errors)
        return result

    def _issuer_inputs(self, issuer_id: str) -> tuple[dict, dict, dict,
                                                       dict, dict]:
        """Входы всех формул §3 по каноническим концептам (TASK-9 V0/V4).

        Однопериодные: пересечение периодов входов (unit, start, end),
        приоритет тега карты выбирает источник. Двухпериодные (roe,
        asset_turnover): конец выбранного периода + предыдущий период
        того же стока, иначе missing_prior_period. Цепочка nopat берёт
        ставку из посчитанной effective_tax. Отсутствующий концепт —
        missing_data; нет общего периода — period_mismatch. Факт старше
        1100 дней от anchor (самого свежего конца периода эмитента) во
        входы не годится (TASK-12 Y2). Причины не сливаются.
        """
        rows = self._snapshots.as_reported_facts(
            issuer_id, tuple(sorted(base_concepts)))
        by_concept: dict[str, list] = {}
        for _concept, value, fact_id, unit, start, end, canonical in rows:
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
                "rank": priority_rank(key, local),
            })

        # ── Правило давности (TASK-12 Y2) ──
        # anchor — самый свежий period_end среди as_reported фактов
        # эмитента по концептам набора мер. Факт, отстающий от anchor
        # более чем на 1100 дней, во входы не годится: тег, которым
        # компания перестала пользоваться, — отсутствующее раскрытие
        # (missing_data), а не period_mismatch. Фильтр живёт в выборке
        # входов, не в as_reported_facts: store хранит всё, и старый
        # факт по-прежнему показывают verify и панель источника.
        anchor = max((r["end"] for rows in by_concept.values()
                      for r in rows), default=None)
        try:
            anchor_date = date.fromisoformat(anchor) if anchor else None
        except (TypeError, ValueError):
            anchor_date = None
        if anchor_date is not None:
            for key in list(by_concept):
                fresh = [r for r in by_concept[key]
                         if _eligible_input(r["end"], anchor_date)]
                if fresh:
                    by_concept[key] = fresh
                else:
                    del by_concept[key]

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
                reasons[concept] = "missing_data: " + ", ".join(absent)
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
            if not flow_rows or not stock_ends:
                reasons[concept] = "missing_data"
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
        if et_period is None or not oi_rows:
            reasons["nopat"] = "missing_data"
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

    def _diff(self, instrument_id, snapshot_id, peer_prev, peer_cur) -> SnapshotDiff:
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
                          in self._snapshots.restated_revisions()]
        return diff
