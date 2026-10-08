"""Действия из окна (TASK-C2): сбор и бюджет — через двери ядра.

Правило: окно зовёт ядро, тело CLI не повторяется. Сбор — тот же
`IngestionPipeline` (rusterm/pipeline.py) с тем же синтетическим
провайдером, что у `rusterm ingest` по умолчанию, и тот же
`SnapshotBuilder` с теми же крючками, что у `rusterm snapshot`.
Реальные источники окно собирает дверью `follow_instrument` — тем же
`cli.cmd_follow`, который зовёт терминал (ТЗ-97 Q12 строка 2): аргумент-
вектор разбирает настоящий парсер, стадии приходят колбэком, отмена
читается на границе стадий. Копии тел CLI в окне нет ни для одной стадии.

Поток: действия открывают СВОЁ соединение с базой (sqlite-соединение
не переезжает между потоками), UI-поток не блокируется (ADR-0004 §3).
Отмена кооперативная, на границах стадий: конвейер идемпотентен по
sha256, снапшот — один атомарный вызов ядра; половины снапшота не
бывает ни после отмены, ни после сбоя.
"""
from __future__ import annotations

import datetime
import os
from dataclasses import dataclass
from pathlib import Path
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
    # ТЗ-109 R4: по пути прошла строка с транспортным отказом
    # (`source_unreachable:transport…`) — окно называет «нет сети»
    # словами и показывает дату данных, а не немую старину
    offline: bool = False


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
    """Тот же строитель, что у cmd_snapshot: одна фабрика ядра (ТЗ-97
    Q6, ТЗ-94 `E1`), а не копия её аргументов."""
    from rusterm.core.snapshot import make_snapshot_builder
    return make_snapshot_builder(repos, _today())


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
    # ТЗ-65 K3: KR без ключа — отказ канала с инструкцией, те же
    # слова, что у rusterm ingest (ТЗ-61 F4), не синтетика
    from rusterm.markets import get_market, provider_channel
    from rusterm.providers import channel_key_env
    market = get_market(instrument_id.split("-", 1)[0])
    key_env = channel_key_env(market.provider) if market else None
    if (market is not None
            and provider_channel(market.provider) is None
            and key_env and not os.environ.get(key_env)):
        from rusterm.providers.dart import dart_key_instruction
        return CollectOutcome(
            ok=False, reason="dart_key_unset",
            detail=(f"сбор недоступен: dart_key_unset — "
                    f"{dart_key_instruction()}"))
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
        # ТЗ-64 J5: те же входы — честное «без изменений» в итоге
        from rusterm.core.snapshot import snapshot_measures_identical
        prev_id = repos.snapshot.previous_snapshot(instrument_id)
        unchanged = (prev_id is not None
                     and snapshot_measures_identical(
                         repos.snapshot.get_measures(built.snapshot_id),
                         repos.snapshot.get_measures(prev_id)))
        return CollectOutcome(
            ok=True, facts_stored=result.facts_stored,
            jobs_done=result.jobs_done,
            snapshot_id=built.snapshot_id,
            snapshot_version=built.version,
            detail=(f"фактов {result.facts_stored}; снапшот "
                    f"v{built.version}"
                    + ("; без изменений" if unchanged else "")))
    finally:
        conn.close()


def _live_ticker(root, instrument_id: str) -> Optional[str]:
    """Тикер — из двери магазина, а не из разбиения `instrument_id`.

    Идентификатор строится как `РЫНОК-ТИКЕР`, и у бумаги с дефисом в
    тикере («US-BRK-B») наивный split даёт «BRK»: окно пошло бы собирать
    в базу пользователя чужую бумагу. Дверь `ticker_for_instrument`
    отвечает действующим тикером на сегодня и заодно различает
    переименованные бумаги. Если базы ещё нет — ответа нет, и зовущий
    берёт суффикс идентификатора: `follow` создаёт каталог сам на стадии
    1/6, и тогда инструмента в магазине ещё нет по определению.
    """
    paths = AppPaths.from_root(root)
    if not Path(paths.db_path).exists():
        return None
    conn = open_connection(paths)
    try:
        apply_migrations(conn)
        from rusterm.store.repos import RepoRegistry
        row = RepoRegistry(conn, paths).instrument.ticker_for_instrument(
            instrument_id, _today())
    finally:
        conn.close()
    return row["ticker"] if row else None


def follow_instrument(root, instrument_id: str,
                      cancel: Optional[CancelFlag] = None,
                      on_stage: Optional[Callable[[str], None]] = None
                      ) -> CollectOutcome:
    """ТЗ-97 Q12 (строка 2): собрать живую бумагу = `rusterm follow`.

    Это та же команда, что человек набрал бы в терминале: аргумент-вектор
    разбирает настоящий парсер CLI, путь делает `cli.cmd_follow`, и тело
    ни одной стадии в окно не переезжает. Окно получает два крючка:
    `on_stage` — строка стадии в момент, когда она напечатана (значит,
    прогресс виден во время пути, а не только итог), и `cancel` — флаг,
    который `cmd_follow` читает на границе стадий.

    Итог — тот же `CollectOutcome`, что у демо-сбора, чтобы окно отвечало
    одними словами: отказ стадии несёт `follow_failed` и последнюю строку
    пути — а последней у `follow` бывает строка «совет: rusterm …», то
    есть исполнимая команда (правило P8), а не описание проблемы.
    Всё тело под `try`: трассировка из воркера окну не ответ, а без него
    окно осталось бы с активной кнопкой отмены и без итогого слова.
    """
    from rusterm import cli

    if cancel is None:
        # не `cancel or CancelFlag()`: свежий флаг falsy, и `or`
        # подменил бы объект вызывателя — его cancel() не дошёл бы
        cancel = CancelFlag()
    market, _, ticker = instrument_id.partition("-")
    lines: list[str] = []

    def emit(line: str) -> None:
        lines.append(line)
        if on_stage is not None:
            on_stage(line)

    try:
        live = _live_ticker(root, instrument_id)
        if live:
            ticker = live
        args = cli._build_parser().parse_args(
            ["--root", str(root), "follow", ticker, "--market", market])
        rc = cli.cmd_follow(args, emit=emit, cancel=cancel)
    except Exception as e:  # трассировка — не ответ окна
        return CollectOutcome(ok=False, reason=f"unexpected_error:{e}",
                              detail="путь прерван ошибкой; база осталась "
                                     "целой")
    if rc == cli.FOLLOW_CANCELLED:
        # стадия не начата: половины пути нет, записанное до отмены
        # честно и переживёт повтор
        return CollectOutcome(cancelled=True,
                              detail=lines[-1] if lines else
                              "отменено до первой стадии")
    # ТЗ-109 R4: транспортный отказ виден в строках пути — и в строке
    # «пропущено» необязательной стадии (R1), и в отказе ребёнка,
    # который follow теперь передаёт в emit; окно называет его словами
    offline = any("source_unreachable:transport" in line for line in lines)
    if rc != 0:
        return CollectOutcome(ok=False, reason="follow_failed",
                              detail=lines[-1] if lines else f"код {rc}",
                              offline=offline)

    paths = AppPaths.from_root(root)
    conn = open_connection(paths)
    try:
        from rusterm.store.repos import RepoRegistry
        repos = RepoRegistry(conn, paths)
        snapshot_id = repos.snapshot.latest_snapshot_id(instrument_id)
        row = (repos.snapshot.get_snapshot(snapshot_id)
               if snapshot_id else None)
    finally:
        conn.close()
    version = row["version"] if row else None
    return CollectOutcome(
        ok=True, snapshot_id=snapshot_id, snapshot_version=version,
        offline=offline,
        detail=("путь пройден"
                + (f"; снапшот v{version}" if version is not None else "")))


# ── ТЗ-111 U3: обновление отставшей базы кнопкой ────────────────────────

def upgrade_stale_base(root) -> CollectOutcome:
    """Кнопка «Обновить базу»: бэкап, затем миграции той же дверью, что
    `rusterm --root DIR init` (apply_migrations). Миграция происходит
    ТОЛЬКО по явному щелчку пользователя — до щелчка окно остаётся
    только читателем (ADR-0023). Отказ бэкапа отменяет обновление."""
    from rusterm.store.backup import BackupError, create_backup
    from rusterm.store.db import (_SCHEMA_VERSION, apply_migrations,
                                  current_schema_version)
    paths = AppPaths.from_root(root)
    conn = open_connection(paths)
    try:
        observed = current_schema_version(conn)
        if observed is None:
            return CollectOutcome(ok=False, reason="no_base",
                                  detail="каталога данных нет")
        if observed >= _SCHEMA_VERSION:
            return CollectOutcome(
                ok=True, detail=f"база уже актуальна (схема {observed})")
        try:
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            archive = (Path(root) / "backups" /
                       f"upgrade-{stamp}.zip")
            summary = create_backup(paths, archive)
        except BackupError as e:
            return CollectOutcome(
                ok=False, reason="backup_failed",
                detail=f"бэкап не создался ({e.reason}); база не менялась")
        applied = apply_migrations(conn)
        after = current_schema_version(conn)
        return CollectOutcome(
            ok=True, detail=(f"бэкап: {summary.archive}; схема "
                             f"{observed} → {after}; миграций: "
                             f"{len(applied)}"))
    except Exception as e:  # трассировка — не ответ окна
        return CollectOutcome(ok=False, reason=f"unexpected_error:{e}",
                              detail="обновление прервано; база "
                                     "осталась целой")
    finally:
        conn.close()


# ── ТЗ-134 W5: подсказка-команда становится кнопкой ─────────────────────

# Команды, которые окно запускает по кнопке-подсказке: без сети или с
# явным согласием пользователя в диалоге; остальное — не из окна
WINDOW_COMMANDS = frozenset({"snapshot", "history", "peers"})

# подпись кнопки по команде подсказки; команда без подписи кнопкой не
# становится — её строка остаётся в окне как была
BUTTON_TITLES = {
    "snapshot": "Посчитать ряд",
    "history": "Собрать историю по годам",
    "peers": "Создать группу аналогов…",
}


def split_hint(text: str | None) -> tuple[str, list[str] | None]:
    """Подсказка слоя данных → (слова для надписи, argv для кнопки).
    Строка «rusterm …» уходит из надписи на кнопку, если окно эту
    команду запускает; иначе текст возвращается нетронутым."""
    import shlex
    if not text or "rusterm " not in text:
        return text or "", None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        at = line.find("rusterm ")
        if at < 0:
            continue
        try:
            argv = shlex.split(line[at:])[1:]
        except ValueError:
            return text, None
        if not argv or argv[0] not in WINDOW_COMMANDS:
            return text, None
        head = line[:at].rstrip(" —:-").rstrip()
        lines[i] = head
        words = "\n".join(x for x in lines if x.strip())
        return words, argv
    return text, None


def button_title(argv: list[str]) -> str:
    """Подпись кнопки: подтверждение набора — своё слово."""
    if argv[:2] == ["peers", "set"] and "--approve" in argv:
        return "Подтвердить группу аналогов"
    return BUTTON_TITLES[argv[0]]


def run_core_command(root, argv: list[str]) -> CollectOutcome:
    """Выполнить команду ядра, названную подсказкой окна, той же дверью,
    что терминал (`rusterm.cli.main`, ADR-0027): argv разбирает настоящий
    парсер, тело в окно не переезжает. Вывод команды — в detail итога;
    трассировка окну не ответ."""
    import contextlib
    import io
    from rusterm import cli

    if not argv or argv[0] not in WINDOW_COMMANDS:
        return CollectOutcome(ok=False, reason="not_a_window_command",
                              detail=f"окно не запускает {argv[:1]}")
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = cli.main(["--root", str(root), *argv])
    except SystemExit as exc:      # парсер отказал: аргументы не те
        return CollectOutcome(ok=False, reason="bad_arguments",
                              detail=out.getvalue().strip()
                              or f"код {exc.code}")
    except Exception as e:  # трассировка — не ответ окна
        return CollectOutcome(ok=False, reason=f"unexpected_error:{e}",
                              detail="команда прервана; база осталась "
                                     "целой")
    lines = [line for line in out.getvalue().splitlines() if line.strip()]
    return CollectOutcome(ok=rc == 0,
                          reason=None if rc == 0 else "command_failed",
                          detail=lines[-1] if lines else f"код {rc}")


# ── ТЗ-110 B2: фоновый проход окна — та же команда, что у cron ──────────

def refresh_pass(root, cancel: Optional[CancelFlag] = None,
                 on_stage: Optional[Callable[[str], None]] = None
                 ) -> CollectOutcome:
    """Один проход `rusterm refresh --all` (цены инкрементально,
    отчётность — изменившаяся, снапшоты — где приехало) дверью CLI:
    аргумент-вектор разбирает настоящий парсер, тело в окно не
    переезжает. Итог несёт строку «обновлено HH:MM · N бумаг ·
    M запросов» — дату ставит момент завершения, бумаги и запросы
    считает база, а не слова воркера. cancel читается командой на
    границе бумаги; всё тело под try: трассировка из воркера окну
    не ответ."""
    from rusterm import cli

    if cancel is None:
        cancel = CancelFlag()
    # ADR-0023: окно не мигрирует базу — фоновый проход тоже. Отставшая
    # схема названа словами с командой обновления, проход не начинается
    # (cmd_refresh открыл бы базу пишущей дверью и наделал миграций).
    import sqlite3
    from rusterm.store.db import _SCHEMA_VERSION, current_schema_version
    paths0 = AppPaths.from_root(root)
    if Path(paths0.db_path).exists():
        ro = sqlite3.connect(f"file:{paths0.db_path}?mode=ro", uri=True)
        try:
            observed = current_schema_version(ro)
        finally:
            ro.close()
        if observed is not None and observed != _SCHEMA_VERSION:
            return CollectOutcome(
                ok=False, reason="schema_stale",
                detail=(f"база в {root} — схема {observed}, программе "
                        f"нужна {_SCHEMA_VERSION}; обновите: "
                        f"rusterm --root {root} init"))
    lines: list[str] = []

    def emit(line: str) -> None:
        lines.append(line)
        if on_stage is not None:
            on_stage(line)

    try:
        before = cli._requests_used(str(root))
        args = cli._build_parser().parse_args(
            ["--root", str(root), "refresh", "--all"])
        rc = cli.cmd_refresh(args, emit=emit, cancel=cancel)
    except Exception as e:  # трассировка — не ответ окна
        return CollectOutcome(ok=False, reason=f"unexpected_error:{e}",
                              detail="проход прерван ошибкой; база "
                                     "осталась целой")
    if rc == cli.FOLLOW_CANCELLED:
        return CollectOutcome(cancelled=True,
                              detail=lines[-1] if lines else
                              "проход остановлен")
    if rc != 0:
        return CollectOutcome(ok=False, reason="refresh_failed",
                              detail=lines[-1] if lines else f"код {rc}")

    n = 0
    paths = AppPaths.from_root(root)
    conn = open_connection(paths)
    try:
        from rusterm.store.repos import RepoRegistry
        repos = RepoRegistry(conn, paths)
        n = len(list(repos.instrument.list_instruments()))
    finally:
        conn.close()
    spent = cli._requests_used(str(root)) - before
    stamp = datetime.datetime.now().strftime("%H:%M")
    return CollectOutcome(
        ok=True, detail=(f"обновлено {stamp} · {n} бумаг · "
                         f"{spent} запросов"))


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
    """ТЗ-64 J2: делегация единой реализации ядра."""
    from rusterm.core.export import lineage_facts
    return lineage_facts(repos, measures)


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
