"""Сборка снапшота — процесс 2 по docs/processes.md §124-196.

Два прохода: фундаментальные меры считаются по компании независимо;
перцентили — только по уже посчитанным величинам пиров. Пир без свежих
данных исключается из расчёта с пометкой excluded_stale, не берётся
устаревшим. Три вида diff раздельны: изменение метрик, эффект пересостава
peer set, появившиеся ревизии (ADR-0002: смешивать первые два запрещено).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from rusterm.core.peers import evaluate, percentile_share
from rusterm.formulas import calculate_measure, measure_unit
from rusterm.normalize.concepts import priority_rank, strip_taxonomy

# Меры первого прохода: фундаментальные, считаются на issuer.
_BASE_MEASURES = {
    "net_margin": ("net_income", "revenue"),
    "operating_margin": ("operating_income", "revenue"),
    "effective_tax": ("tax_expense", "pretax_income"),
}


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

        # ── Проход 1: фундаментальные меры компании ──
        inputs, lineage_by_concept, input_reasons, periods, input_units = \
            self._issuer_inputs(issuer_id)
        computed: dict[str, float] = {}
        for concept, args in _BASE_MEASURES.items():
            kw = inputs.get(concept)
            value = None
            null_reason = input_reasons.get(concept, "missing_data")
            if kw is not None:
                m = calculate_measure(concept, **kw)
                value, null_reason = m.value, m.null_reason
            # период меры — период входов; пустой period_start не пишется:
            # меры без входов несут as_of и объясняются null_reason (V2)
            if concept in periods:
                period_start, period_end = periods[concept]
            else:
                period_start, period_end = as_of, as_of
            self._snapshots.insert_measure_with_lineage(
                dict(measure_id=str(uuid4()), snapshot_id=snapshot_id,
                     scope="issuer", scope_ref=issuer_id, concept=concept,
                     value=None if value is None else repr(value),
                     unit=measure_unit(concept, input_units.get(concept, "")),
                     period_start=period_start, period_end=period_end,
                     formula_id=concept, method_version="v1",
                     null_reason=null_reason, peer_set_version=None),
                lineage_by_concept.get(concept, []))
            result.measures += 1
            if value is not None:
                computed[concept] = value

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
                else ("missing", "no_as_reported_facts")),
            "peer_set": (
                ("ready", None) if peer_set_version
                else ("missing", "peer_set_not_confirmed")),
        }
        self._coverage.ensure_all(instrument_id, known,
                                  source_errors=source_errors)
        return result

    def _issuer_inputs(self, issuer_id: str) -> tuple[dict, dict, dict, dict]:
        """Входы мер из фактов as_reported по концепту; lineage ведёт
        к fact_id каждого входа.

        Одна мера — один период (TASK-9 V1): для меры берётся последняя
        period_end, на которую есть ВСЕ её входы с одинаковой единицей и
        basis='as_reported'; duration-вход дополнительно требует ту же
        period_start. Нет общего периода — period_mismatch; концепт
        отсутствует целиком — missing_data. Приоритет тега карты (V0):
        при равном каноническом имени выигрывает меньший ранг.
        """
        rows = self._snapshots.as_reported_facts(
            issuer_id, ("net_income", "revenue", "operating_income",
                        "tax_expense", "pretax_income"))
        base_concepts = ("net_income", "revenue", "operating_income",
                         "tax_expense", "pretax_income")
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

        inputs: dict[str, dict] = {}
        lineage: dict[str, list] = {}
        reasons: dict[str, str] = {}
        periods: dict[str, tuple[str, str]] = {}
        input_units: dict[str, str] = {}
        for concept, args in _BASE_MEASURES.items():
            if any(a not in by_concept for a in args):
                reasons[concept] = "missing_data"
                continue
            # пересечение периодов: (unit, period_start, period_end)
            key_sets = []
            for a in args:
                keys = set()
                for row in by_concept[a]:
                    keys.add((row["unit"], row["start"], row["end"]))
                key_sets.append(keys)
            common = set.intersection(*key_sets)
            if not common:
                reasons[concept] = "period_mismatch"
                continue
            chosen_period = max(common, key=lambda k: (k[2], k[1]))
            chosen = {}
            lin = []
            for a in args:
                candidates = [r for r in by_concept[a]
                              if (r["unit"], r["start"], r["end"])
                              == chosen_period]
                row = min(candidates, key=lambda r: r["rank"])
                chosen[a] = row["value"]
                input_units[concept] = row["unit"]
                lin.append({"fact_id": row["fact_id"],
                            "peer_measure_id": None, "role": "input"})
            inputs[concept] = chosen
            lineage[concept] = lin
            # мера несёт период своих входов, а не дату сборки (V2)
            periods[concept] = (chosen_period[1], chosen_period[2])
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
