"""Действия из окна (TASK-C2): сбор и бюджет — через двери ядра.

Правило: окно зовёт ядро, тело CLI не повторяется. Сбор — тот же
`IngestionPipeline` (rusterm/pipeline.py) с тем же синтетическим
провайдером, что у `rusterm ingest` по умолчанию, и тот же
`SnapshotBuilder` с теми же крючками, что у `rusterm snapshot`.
Сбор РЕАЛЬНЫХ источников (edgar/twelvedata/cvm/asx/ownership) телом
живёт в приватных функциях CLI и из окна недоступен без копии —
Disputed в REPORT-C2 с именами функций; окно называет команду CLI.

Поток: действия открывают СВОЁ соединение с базой (sqlite-соединение
не переезжает между потоками), UI-поток не блокируется (ADR-0004 §3).
Отмена кооперативная, на границах стадий: конвейер идемпотентен по
sha256, снапшот — один атомарный вызов ядра; половины снапшота не
бывает ни после отмены, ни после сбоя.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Callable, Optional

from rusterm.pipeline import IngestionPipeline
from rusterm.store.db import apply_migrations, open_connection
from rusterm.store.paths import AppPaths


def _today() -> str:
    return datetime.date.today().isoformat()


# Демо-инструмент CLI: синтетический провайдер честно служит только
# ему — демо-факты на реальном эмитенте были бы выдумкой. Константа
# импортируется, а не копируется (расхождение поймало бы сравнение).
def demo_instrument_id() -> str:
    from rusterm.cli import DEMO_INSTRUMENT
    return DEMO_INSTRUMENT


# То, что окно честно называет пользователю, когда источник заперт в CLI
CLI_LOCKED_SOURCES = {
    "edgar": "rusterm ingest --source edgar --instrument …",
    "twelvedata": "rusterm ingest --source twelvedata --instrument …",
    "cvm": "rusterm ingest --source cvm --instrument …",
    "asx": "rusterm ingest --source asx --instrument …",
    "ownership": "rusterm ingest --source ownership --instrument …",
}

# Тела этих функций CLI не отделимы от командного слоя (печатют в
# stderr и возвращают int): сбор из окна без копии невозможен.
CLI_LOCKED_FUNCTIONS = (
    "_ingest_edgar_companyfacts",
    "_ingest_twelvedata_prices",
    "_ingest_cvm_dfp",
    "_ingest_asx_announcements",
    "_ingest_edgar_ownership",
)


@dataclass
class CollectOutcome:
    """Итог сбора: словарные причины словами, не трассировки."""
    ok: bool = False
    cancelled: bool = False
    reason: Optional[str] = None
    detail: str = ""
    facts_stored: int = 0
    jobs_done: int = 0
    snapshot_id: Optional[str] = None
    snapshot_version: Optional[int] = None


@dataclass
class CancelFlag:
    """Кооперативная отмена: читается на границах стадий."""
    flagged: bool = False

    def cancel(self) -> None:
        self.flagged = True

    def __bool__(self) -> bool:
        return self.flagged


def _synthetic_providers() -> dict:
    """Тот же словарь, что строит cmd_ingest по умолчанию."""
    from rusterm.providers.disclosures import (
        DEMO_INDEX_FIXTURE,
        SyntheticDisclosuresProvider,
    )
    return {"synthetic": SyntheticDisclosuresProvider(
        fixture_path=DEMO_INDEX_FIXTURE)}


def _snapshot_builder(repos):
    """Тот же строитель, что у cmd_snapshot: те же крючки отраслевых
    метрик и governance, те же репозитории."""
    from rusterm.core.governance import (governance_inputs_from_records,
                                         insider_net_inputs_from_store,
                                         produce_assessments)
    from rusterm.core.industry.inputs import industry_metrics_for
    from rusterm.core.snapshot import SnapshotBuilder
    as_of = _today()
    return SnapshotBuilder(
        repos.snapshot, repos.peer_set,
        coverage_repo=repos.coverage,
        price_repo=repos.price,
        corp_action_repo=repos.corp_action,
        industry=lambda iid, _issuer: industry_metrics_for(repos, iid),
        governance=lambda iid, issuer: produce_assessments(
            repos.governance, iid, as_of,
            {**governance_inputs_from_records(repos.manual_extraction,
                                              issuer),
             **insider_net_inputs_from_store(repos, iid, issuer,
                                             as_of)}))


def collect_synthetic(root, instrument_id: str,
                      cancel: Optional[CancelFlag] = None,
                      providers: Optional[dict] = None,
                      sleep: Optional[Callable[[float], None]] = None,
                      as_of: Optional[str] = None,
                      on_stage: Optional[Callable[[str], None]] = None
                      ) -> CollectOutcome:
    """Собрать выбранный инструмент синтетическим конвейером и
    построить снапшот — двери ядра те же, что у CLI.

    Синтетический провайдер служит только демо-инструменту: для
    любого другого окна отказывается словами и называет команду CLI
    (реальные источники — Disputed, тела заперты в CLI).
    Отмена проверяется перед конвейером и перед снапшотом; обе
    стадии оставляют базу целой (конвейер идемпотентен, снапшот
    атомарен — половины не бывает). on_stage сообщает прогресс по
    стадиям; выполняться обязан в потоке вызывателя (здесь это
    рабочий поток, не UI).
    """
    if cancel is None:
        # не `cancel or CancelFlag()`: свежий флаг falsy, и `or`
        # подменил бы объект вызывателя — его cancel() не дошёл бы
        cancel = CancelFlag()

    def stage(name: str) -> None:
        if on_stage is not None:
            on_stage(name)

    as_of = as_of or _today()
    if instrument_id != demo_instrument_id():
        return CollectOutcome(
            ok=False,
            reason="synthetic_demo_only",
            detail=(f"синтетический сбор честен только для демо-"
                    f"инструмента {demo_instrument_id()}; реальные "
                    "источники заперты в CLI — выполните "
                    + "; либо ".join(CLI_LOCKED_SOURCES.values())))
    if cancel:
        return CollectOutcome(cancelled=True, detail="отмена до старта")
    providers = providers if providers is not None else \
        _synthetic_providers()
    provider = providers.get("synthetic")
    reason = getattr(provider, "reason", None)
    if reason:
        # провайдер-значение отказа (нет ключа и т.п.) — причина словами
        return CollectOutcome(ok=False, reason=str(reason),
                              detail=f"провайдер недоступен: {reason}")

    paths = AppPaths.from_root(root)
    conn = open_connection(paths)
    try:
        apply_migrations(conn)
        from rusterm.store.repos import RepoRegistry
        repos = RepoRegistry(conn, paths)
        instrument = repos.instrument.get_instrument(instrument_id)
        if instrument is None:
            return CollectOutcome(
                ok=False, reason="unknown_issuer",
                detail=(f"инструмента {instrument_id} нет в базе; "
                        "создайте его командой rusterm demo"))
        issuer_id = instrument.issuer_id
        stage("конвейер: индекс и документы")
        pipeline = (IngestionPipeline(repos, providers) if sleep is None
                    else IngestionPipeline(repos, providers, sleep=sleep))
        try:
            result = pipeline.run(instrument_id, issuer_id, "synthetic")
        except Exception as e:  # трассировка — не ответ окна
            return CollectOutcome(ok=False,
                                  reason=f"unexpected_error:{e}",
                                  detail="сбор прерван ошибкой; "
                                         "база осталась целой")
        # отказ конвейера — словами из таблицы процессов (E1/E3), не тишина
        if result.coverage_errors:
            return CollectOutcome(
                ok=False, reason="index_unavailable",
                detail=("источник раскрытий недоступен (E1); "
                        "покрытие помечено ошибкой с причиной"))
        if result.fetch_failures:
            return CollectOutcome(
                ok=False, reason="fetch_failed",
                detail="документы источника не забрались (E3); "
                       "задания закрыты с причиной")
        if cancel:
            # конвейер идемпотентен: записанное им честно и переживёт
            # повтор; снапшота нет — см. тест отмены
            return CollectOutcome(
                cancelled=True, facts_stored=result.facts_stored,
                jobs_done=result.jobs_done,
                detail="отмена после конвейера, до снапшота")
        stage("снапшот: меры по формулам")
        try:
            built = _snapshot_builder(repos).build(instrument_id,
                                                   issuer_id, as_of)
        except Exception as e:
            return CollectOutcome(ok=False,
                                  reason=f"unexpected_error:{e}",
                                  detail="снапшот не построен; база "
                                         "осталась целой")
        return CollectOutcome(
            ok=True, facts_stored=result.facts_stored,
            jobs_done=result.jobs_done,
            snapshot_id=built.snapshot_id,
            snapshot_version=built.version,
            detail=(f"фактов {result.facts_stored}; снапшот "
                    f"v{built.version}"))
    finally:
        conn.close()


# ── C2.3: бюджет — тот же источник, что rusterm budget ─────────────────

def budget_view(repos) -> dict:
    """Потолок и израсходованные запросы — из metric_sample, тем же
    чтением, что cmd_budget (сэмплы provider_*; лимитеры состояния
    между процессами не хранят — used/refused это сэмплы, не память).
    «Сегодня» считается той же функцией, что шапку окна.
    """
    from rusterm.desktop.data import header_info
    samples = {s[1]: float(s[3]) for s in repos.metrics.samples()
               if s[1].startswith("provider_")}
    return {"ceiling_per_night": 5000, "rate_per_second": 5,
            "provider_ran": bool(samples), "samples": samples,
            "used_today": header_info(repos)["requests_today"]}


# ── TASK-C4: экспорт того, что на экране ────────────────────────────────

def _snapshot_measures(repos, instrument_id: str):
    """Меры последнего снапшота — та же дверь, что у rusterm export."""
    snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
    if snapshot_id is None:
        return None, []
    return snapshot_id, repos.snapshot.get_measures(snapshot_id)


def _lineage_facts(repos, measures) -> dict:
    """measure_id -> входные факты (FactRepo.get_fact) — та же цепочка,
    которую панель источника показывает по клику."""
    lineage: dict = {}
    for m in measures:
        facts = [repos.fact.get_fact(fid)
                 for fid in repos.snapshot.lineage_fact_ids(m[0])]
        lineage[m[0]] = [f for f in facts if f is not None]
    return lineage


def _source_cell(facts: list) -> str:
    """Ячейка источника: вид источника, хэш ответа (укороченный),
    дата периода факта. Реализация одна (data.source_cell, форма
    'export') — ТЗ-62 G3; строка со значением без источника уйти не
    должна — это проверяет тест."""
    from rusterm.desktop.data import source_cell
    return source_cell(facts, shape="export")


def export_snapshot_csv(repos, instrument_id: str) -> str:
    """CSV таблицы: базовые колонки — тем же кодом, что
    `rusterm export --format csv` (snapshot_to_csv ядра, байт в байт),
    плюс колонка «источник» из lineage фактов (C4.3). Отказ несёт
    причину в колонке null_reason — те же слова, что на экране.
    Ячейка источника не содержит запятых и кавычек по построению
    (вид:hex@дата, разделитель «;»), поэтому дописывается без
    перекавычивания строки ядра."""
    from rusterm.core.export import snapshot_to_csv
    _sid, measures = _snapshot_measures(repos, instrument_id)
    base = snapshot_to_csv(measures)
    lineage = _lineage_facts(repos, measures)
    lines = base.rstrip("\n").splitlines()
    out = [lines[0], lines[1] + ",источник"]
    for i, m in enumerate(measures):
        out.append(lines[2 + i] + "," + _source_cell(lineage.get(m[0], [])))
    return "\n".join(out) + "\n"


def export_snapshot_md(repos, instrument_id: str) -> str:
    """Markdown — в точности код ядра (snapshot_to_md): отказ — прочерк
    со сноской и причиной, те же слова, что на экране (C4.1)."""
    from rusterm.core.export import snapshot_to_md
    _sid, measures = _snapshot_measures(repos, instrument_id)
    return snapshot_to_md(measures)


def export_snapshot_json(repos, instrument_id: str) -> str:
    """JSON — код ядра (snapshot_to_json) с провенансом (ТЗ-20 L9:
    attach_provenance по lineage) и валютами мер (ТЗ-22 J1): документ,
    дата и хэш ответа едут в файл вместе с числом (C4.3)."""
    import json as _json

    from rusterm.core.export import snapshot_to_json
    sid, measures = _snapshot_measures(repos, instrument_id)
    if sid is None:
        return ""
    snapshot = repos.snapshot.get_snapshot(sid)
    lineage = _lineage_facts(repos, measures)
    currencies = {m[0]: repos.snapshot.measure_currency(m[0], m[3])
                  for m in measures}
    return snapshot_to_json(snapshot, measures, provenance=lineage,
                            currencies=currencies)


def chart_caption(table: dict, concept: str | None) -> str:
    """Подпись под картинкой (C4.2): эмитент, мера, период, дата
    выгрузки — из данных таблицы, без досчёта. Форма без источника:
    подпись не называет документ и хэш — для них в ней нет места
    (ТЗ-62 G3)."""
    years = table.get("years") or []
    period = f"{years[-1]}–{years[0]}" if years else "—"
    return (f"{table.get('ticker', '—')} · {table.get('name') or '—'}"
            f" · мера {concept or '—'} · период {period}"
            f" · выгружено {_today()}")
