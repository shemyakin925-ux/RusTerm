"""ТЗ-84: конкурентные писатели одной базы — I14 исполняемая проверка.

До этого круга «один писатель» проверялся чтением кода: в `tests/` нет ни
одного файла, где два писателя исполняются одновременно (замер приёма
круга — `grep -rln "threading\\|Thread(" tests/` без совпадений). Здесь
писатели настоящие: потоки, подпроцессы, читатель под WAL, сбор из окна
под записью UI и бэкап во время инжеста.

Правило ТЗ про зависание действует в каждом тесте: рабочие потоки —
daemon, и у ожидания есть потолок (`join(JOIN_TIMEOUT)`,
`subprocess.run(timeout=…)`). Таймаут здесь — красный тест, а не
терпеливое ожидание: висячий `writer_transaction` иначе выглядел бы как
медленно зелёный прогон.

Каталоги — только `tmp_path` этого теста (страж `test_no_shared_tmp`),
никаких запусков против базы пользователя (P7).
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import subprocess
import sys
import threading
import time

from rusterm.store import db
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.desktop import actions
from rusterm.store.repos import Instrument, Issuer, Listing, RepoRegistry

# Сколько транзакций делает каждый из двух потоков (строка K1).
N_WRITES = 200
# Потолок ожидания: «таймаут — это красный, а не ожидание». Ниже 30 с из
# Done when, чтобы зависание стало провалом теста, а не его концом.
JOIN_TIMEOUT = 25.0


def _fresh_root(tmp_path):
    """Корень приложения в tmp_path: свои миграции, своё соединение.

    Возвращает (paths, conn) — conn принадлежит основному потоку; рабочие
    потоки открывают соединения сами, как это делают CLI и окно.
    """
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = db.open_connection(paths)
    apply_migrations(conn)
    return paths, conn


def _seed_issuer(repos: RepoRegistry, issuer_id: str) -> None:
    """Эмитент, под который поток пишет инструменты: FK включён
    (`open_connection` ставит `PRAGMA foreign_keys=ON`)."""
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Concurrency issuer {issuer_id}", "US", None, None,
        "us_gaap", "USD"))


# ── K1: два потока, одна база ─────────────────────────────────────────


def test_two_threads_two_hundred_writer_transactions_each(tmp_path):
    """K1: 200 реальных записей репозитория из каждого потока.

    Проверка не «не упало», а точное число строк: проигранная гонкой
    запись — это то, чего обязан не допускать единый писатель. Кого
    именно считать виноватым — процессный лок или сериализацию SQLite на
    уровне файла, — этот тест не решает: замер мутацией (отсутствие
    `with _writer_lock` зелёное) смотрит в отчёт круга.
    """
    paths, conn = _fresh_root(tmp_path)
    for issuer_id in ("K1A", "K1B"):
        _seed_issuer(RepoRegistry(conn, paths), issuer_id)
    conn.close()

    barrier = threading.Barrier(2)
    errors: list[str] = []
    # Когда каждый поток реально писал: без пересечения интервалов тест
    # был бы «один писатель, потом второй», а не конкурентная запись.
    spans: list[list[float]] = [[], []]

    def worker(thread_no: int) -> None:
        issuer_id = "K1A" if thread_no == 0 else "K1B"
        mine = db.open_connection(paths)
        repos = RepoRegistry(mine, paths)
        try:
            # Старт одновременно: без барьера второй поток успевал бы
            # закончить до того, как первый начнёт писать.
            barrier.wait(JOIN_TIMEOUT)
            began = time.monotonic()
            for i in range(N_WRITES):
                repos.instrument.upsert_instrument(Instrument(
                    f"US-K1T{thread_no}-{i}", issuer_id, None, "common",
                    "active", None))
            spans[thread_no] = [began, time.monotonic()]
        except BaseException as exc:  # noqa: BLE001 — тип и есть результат
            # Без сбора оно утонуло бы в потоке: тест был бы зелёным.
            errors.append(f"поток {thread_no}: {type(exc).__name__}: {exc}")
        finally:
            mine.close()

    threads = [threading.Thread(target=worker, args=(n,), daemon=True)
               for n in (0, 1)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(JOIN_TIMEOUT)
    took = time.monotonic() - started

    hung = [n for n, thread in enumerate(threads) if thread.is_alive()]
    assert not hung, (
        f"поток(и) {hung} не завершились за {JOIN_TIMEOUT} с — это "
        f"зависание на локе, а не медленная работа")
    assert not errors, f"запись упала исключением: {errors}"
    assert took < 30.0, f"K1 обязан уложиться в 30 с, вышло {took:.1f} с"
    assert all(len(span) == 2 for span in spans), (
        f"поток(и) не дошли до замера интервала: {spans}")
    overlapped = max(span[0] for span in spans) < min(
        span[1] for span in spans)
    assert overlapped, (
        f"интервалы записи не пересеклись ({spans}) — тест проверял "
        f"последовательную запись, а не конкурентную")

    check = db.open_connection(paths)
    try:
        rows = check.execute(
            "SELECT instrument_id FROM instrument "
            "WHERE instrument_id LIKE 'US-K1T%'").fetchall()
    finally:
        check.close()
    got = {row[0] for row in rows}
    expected = {f"US-K1T{n}-{i}" for n in (0, 1) for i in range(N_WRITES)}
    assert len(rows) == 2 * N_WRITES, (
        f"строк {len(rows)} вместо {2 * N_WRITES}: часть записей "
        f"потеряна при конкурентной записи")
    assert got == expected, (
        f"пропало {len(expected - got)} id, чужих {len(got - expected)} — "
        f"первый пример: {sorted(expected - got)[:3]}")
# ── K2: вложенный writer_transaction ──────────────────────────────────

NEST_TIMEOUT = 5.0


def _issuer(issuer_id: str) -> Issuer:
    """Эмитент для K2: поля-обязанки схемы (`name`, `jurisdiction`,
    `reporting_standard`, `reporting_currency` — NOT NULL)."""
    return Issuer(issuer_id, f"Issuer {issuer_id}", "US", None, None,
                  "us_gaap", "USD")


def test_nested_writer_transaction_fails_fast(tmp_path):
    """K2: вложенная транзакция обязана падать, а не ждать вечно.

    Вложенность собрана из дверей самого продукта: поток открыл
    `writer_transaction` и внутри него вызвал репозиторий, который берёт
    тот же лок сам. До починки это зависание навсегда — `threading.Lock`
    непереживаемый, а SQLite не умеет вложенный BEGIN, — поэтому потолок
    ожидания является частью проверки, а не вежливостью.

    Соединение поток открывает сам: `sqlite3.connect` по умолчанию
    запрещает использовать объект в чужом потоке (`check_same_thread`), и
    проверка именованной ошибки утонула бы в `ProgrammingError`.
    """
    paths, conn = _fresh_root(tmp_path)
    conn.close()
    outcome: list = []

    def nested() -> None:
        mine = db.open_connection(paths)
        try:
            with db.writer_transaction(mine):
                # своя строка внешней транзакции — по ней видно, что
                # откат после падения вложенного вызова откатил всё, а не
                # оставил половину
                mine.execute(
                    "INSERT INTO issuer(issuer_id, name, jurisdiction, "
                    "reporting_standard, reporting_currency) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("K2-outer", "Outer row", "US", "us_gaap", "USD"))
                RepoRegistry(mine, paths).instrument.upsert_issuer(
                    _issuer("K2-in"))  # ← здесь вложенность
            outcome.append("вернулся без ошибки")
        except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
            outcome.append(exc)
        finally:
            mine.close()

    worker = threading.Thread(target=nested, daemon=True)
    worker.start()
    worker.join(NEST_TIMEOUT)

    assert not worker.is_alive(), (
        f"вложенный вызов висит дольше {NEST_TIMEOUT} с: ошибку "
        f"программиста лок превращает в зависание процесса")
    assert outcome, "поток не сообщил результат"
    result = outcome[0]
    assert not isinstance(result, str), (
        "вложенный writer_transaction вернулся нормально — значит "
        "вложенность никто не заметила")
    assert isinstance(result, RuntimeError), (
        f"ожидался RuntimeError, получено {type(result).__name__}: {result!r}")
    assert "writer_transaction" in str(result), (
        f"текст ошибки обязан называть дверь, а не только жаловаться: "
        f"{result}")

    # Падение обязано откатить внешнюю транзакцию целиком: её строка не
    # переживает ошибку, иначе полузаписанная база была бы нормой.
    check = db.open_connection(paths)
    try:
        left = check.execute(
            "SELECT issuer_id FROM issuer WHERE issuer_id IN (?, ?)",
            ("K2-outer", "K2-in")).fetchall()
    finally:
        check.close()
    assert not left, (
        f"после вложенного вызова в базе остались строки "
        f"{[r[0] for r in left]} — откат не сработал")

    # Замок обязан остаться свободным: следующий писатель входит за секунду.
    entered = threading.Event()
    late_errors: list[str] = []

    def late_writer() -> None:
        mine = db.open_connection(paths)
        try:
            RepoRegistry(mine, paths).instrument.upsert_issuer(
                _issuer("K2-after"))
            entered.set()
        except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
            late_errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            mine.close()

    late = threading.Thread(target=late_writer, daemon=True)
    late.start()
    late.join(1.0)
    assert entered.is_set(), (
        f"замок не освободился за 1 с (ошибки: {late_errors}) — вложенный "
        f"вызов оставил процесс без писателя")
# ── K3: исключение внутри транзакции отпускает всё ───────────────────

# Сколько ждать следующего писателя: строка «a second thread's transaction
# starts within 1 s» из Done when.
RESUME_TIMEOUT = 1.0


class _K3Boom(Exception):
    """Исключение самого теста. Важно, что это не `sqlite3.Error`: ветка
    `except Exception` в `writer_transaction` обязана отработать и с чужим
    типом — иначе половина записанного висела бы в открытой транзакции."""


def _instrument(instrument_id: str, issuer_id: str) -> Instrument:
    return Instrument(instrument_id, issuer_id, None, "common", "active", None)


def _fail_and_hold(paths, body):
    """Выполняет `body(conn)` на своём потоке, ловит исключение и ДЕРЖИТ соединение открытым.

    Держать — обязанность теста: `close()` у sqlite3 откатывает незавершённую
    транзакцию сам, и иначе «откат не сработал» было бы не отличить от
    «молча откатилось при закрытии». Вызывающий код обязан позвать
    `release.set()` и `join`: поток — daemon, так что затяжного зависания
    прогона не будет, но смысл проверки без релиза потеряется.
    """
    outcome: list = []
    ready = threading.Event()
    release = threading.Event()

    def worker() -> None:
        mine = db.open_connection(paths)
        try:
            try:
                body(mine)
                outcome.append("вышел без ошибки")
            except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
                outcome.append(exc)
            ready.set()
            release.wait(JOIN_TIMEOUT)
        finally:
            mine.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert ready.wait(JOIN_TIMEOUT), (
        "поток не сообщил о результате за потолок ожидания — это зависание, "
        "а не медленная работа")
    return thread, outcome, release


def _next_writer_writes(paths, instrument_id: str, issuer_id: str) -> None:
    """Отдельный поток обязан записать за секунду: и Python-лок, и писательский
    lock SQLite после отказа свободны.

    Ошибки собираются, а не пробрасываются: из чужого потока они всё равно не
    дошли бы до отчёта, а «молча не записал» и «записал с ошибкой» — разные
    диагнозы.
    """
    entered = threading.Event()
    errors: list[str] = []

    def late_writer() -> None:
        mine = db.open_connection(paths)
        try:
            RepoRegistry(mine, paths).instrument.upsert_instrument(
                _instrument(instrument_id, issuer_id))
            entered.set()
        except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            mine.close()

    late = threading.Thread(target=late_writer, daemon=True)
    late.start()
    late.join(RESUME_TIMEOUT)
    assert entered.is_set(), (
        f"писатель не вошёл за {RESUME_TIMEOUT} с (ошибки: {errors}) — "
        f"отказавшая транзакция оставила замок занятым")


def _instruments_like(paths, like: str) -> list[str]:
    conn = db.open_connection(paths)
    try:
        rows = conn.execute(
            "SELECT instrument_id FROM instrument WHERE instrument_id "
            "LIKE ?", (like,)).fetchall()
    finally:
        conn.close()
    return sorted(r[0] for r in rows)


def test_raise_inside_transaction_rolls_back_and_frees_lock(tmp_path):
    """K3, первая половина: `raise` внутри двери = откат + свободный замок.

    Внутри транзакции — только `execute`, без вызовов репозитория: репозиторий
    сам открывает `writer_transaction`, и на внешнем потоке это та самая
    вложенность, которую K2 превращает в `RuntimeError` (первая версия этого
    теста на неё и напоролась — см. отчёт). Здесь исключение бросается уже
    после записи, когда транзакция открыта и о репозиториях не знает.
    """
    paths, conn = _fresh_root(tmp_path)
    _seed_issuer(RepoRegistry(conn, paths), "K3")
    conn.close()

    def body(mine) -> None:
        with db.writer_transaction(mine):
            mine.execute(
                "INSERT INTO instrument(instrument_id, issuer_id, class, "
                "status) VALUES (?, ?, ?, ?)",
                ("US-K3-inside", "K3", "common", "active"))
            raise _K3Boom("строка записана — и намеренно брошена")

    worker, outcome, release = _fail_and_hold(paths, body)
    try:
        error = outcome[0]
        assert isinstance(error, _K3Boom), (
            f"наружу должен уйти тот же тип, что брошен, получено "
            f"{type(error).__name__}: {error!r}")
        assert _instruments_like(paths, "US-K3%") == [], (
            "откат не сработал: строка из отменённой транзакции осталась в "
            "базе")
        # Следующий писатель проверяется, пока отказавшее соединение ещё
        # открыто: только так видно, что отпустил его именно ROLLBACK.
        _next_writer_writes(paths, "US-K3-after", "K3")
    finally:
        release.set()
        worker.join(JOIN_TIMEOUT)
    assert not worker.is_alive(), "поток не закрыл соединение после релиза"
    assert _instruments_like(paths, "US-K3%") == ["US-K3-after"], (
        "после отказа должен пережить только следующий писатель")


def test_repo_integrity_error_releases_everything(tmp_path):
    """K3, вторая половина: то же обязательство на настоящей двери продукта.

    Ни ручного `BEGIN`, ни ручного `INSERT`: пишется инструмент под
    несуществующий эмитент, и `PRAGMA foreign_keys=ON` из `open_connection`
    превращает это в `IntegrityError` внутри `writer_transaction`
    репозитория. Отказ в продукте выглядит именно так, а не вымышленным
    `raise` в тестовом коде.
    """
    paths, conn = _fresh_root(tmp_path)
    _seed_issuer(RepoRegistry(conn, paths), "K3R")
    conn.close()

    def body(mine) -> None:
        RepoRegistry(mine, paths).instrument.upsert_instrument(
            _instrument("US-K3-dangling", "K3-нет-такого"))

    worker, outcome, release = _fail_and_hold(paths, body)
    try:
        error = outcome[0]
        assert isinstance(error, sqlite3.IntegrityError), (
            f"ожидался IntegrityError от включённого FK, получено "
            f"{type(error).__name__}: {error!r}")
        assert _instruments_like(paths, "US-K3%") == [], (
            "ошибочная запись оставила строку — откат не покрыл дверь "
            "репозитория")
        _next_writer_writes(paths, "US-K3-good", "K3R")
    finally:
        release.set()
        worker.join(JOIN_TIMEOUT)
    assert not worker.is_alive(), "поток не закрыл соединение после релиза"
    assert _instruments_like(paths, "US-K3%") == ["US-K3-good"], (
        "после ошибки целостности должен пережить только следующий писатель")


# ── K4: два процесса на одной базе ────────────────────────────────────

# Сколько раз прогнать пару процессов заново (строка K4: «5 repetitions»).
K4_REPETITIONS = 5
# Потолок ожидания дочернего процесса: зависший инжест — красный тест.
K4_PROC_TIMEOUT = 60.0
# Пауза обращения к демо-индексу в дочерних процессах (`tests/k4_stub`).
# Без неё второй процесс приходит на уже записанный курсор и не делает
# ни одной записи: замок проверялся бы «на удаче». С ней оба процесса
# пишут одновременно (зубы по мутациям — в отчёте, ТЗ-84 K4).
K4_POLL_PAUSE = 0.4
# Два инструмента одной базы. `add` здесь офлайн-формой: --cik и --name
# вместе, иначе команда идёт в сеть, а бюджет круга — ноль запросов.
K4_INSTRUMENTS = (("US-K4A", "1234567", "K4 issuer Alpha"),
                  ("US-K4B", "7654321", "K4 issuer Beta"))
# Таблицы, которыми меряется «факты равны последовательному прогону».
# `coverage` тут нет намеренно: её строки привязаны к инструменту, а то,
# какой инструмент окажется победителем гонки курсора, — законная
# свобода прогона (замер 30 повторов без паузы: 29 раз выиграл запущенный
# первым, один раз — вторым). Счётчики fact/job/raw_object от победителя
# не зависят ни в одном исходе, и сравнивается именно они.
K4_TABLES = ("fact", "job", "raw_object")


def _k4_env() -> dict:
    """Среда дочернего CLI: PYTHONPATH на этот клон и на подмену индекса
    (`tests/k4_stub`), файл окружения пользователя не читается, корень
    всегда передан явно (P7)."""
    here = pathlib.Path(__file__).resolve()
    return {**os.environ,
            "PYTHONPATH": os.pathsep.join([str(here.parent / "k4_stub"),
                                           str(here.parents[1])]),
            "RUSTERM_SEC_UA": "Synthetic Test k4.invalid",
            "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
            "RUSTERM_K4_POLL_PAUSE": str(K4_POLL_PAUSE),
            "TERM": "xterm"}


def _k4_cli(root, *argv):
    """Одна команда rusterm отдельным процессом — тот же способ, что в
    `tests/test_e2e_cli.py`, и с тем же потолком ожидания."""
    return subprocess.run([sys.executable, "-m", "rusterm.cli",
                           "--root", str(root), *argv],
                          capture_output=True, text=True,
                          env=_k4_env(), timeout=K4_PROC_TIMEOUT)


def _k4_prepare(root) -> None:
    """init + два инструмента: ровно то, что говорит сделать строка K4."""
    assert _k4_cli(root, "init").returncode == 0
    for instrument_id, cik, name in K4_INSTRUMENTS:
        ticker = instrument_id.split("-", 1)[1]
        done = _k4_cli(root, "add", "--ticker", ticker, "--market", "US",
                       "--cik", cik, "--name", name)
        assert done.returncode == 0, done.stderr


def _k4_spawn(root, instrument_id) -> subprocess.Popen:
    """ingest --source synthetic по одному инструменту, не дожидаясь
    окончания: второй процесс запускается, пока этот работает."""
    return subprocess.Popen(
        [sys.executable, "-m", "rusterm.cli", "--root", str(root),
         "ingest", "--source", "synthetic", "--instrument", instrument_id],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=_k4_env())


def _k4_pair(root, order: tuple) -> dict:
    """Пара процессов одновременно: {инструмент: (код, stdout, stderr,
    старт, финиш)}.

    Времена снимаются вокруг каждого процесса, чтобы тест мог отличить
    два одновременных прогона от двух последовательных.
    """
    launched = []
    for instrument_id in order:
        proc = _k4_spawn(root, instrument_id)
        launched.append((instrument_id, proc, time.monotonic()))
    done = {}
    for instrument_id, proc, started in launched:
        out, err = proc.communicate(timeout=K4_PROC_TIMEOUT)
        done[instrument_id] = (proc.returncode, out, err, started,
                               time.monotonic())
    return done


def _k4_counts(root) -> dict:
    """Счётчики таблиц и вердикт `PRAGMA integrity_check` — через
    read-only соединение: тест не дописывает в базу, которую проверил CLI.
    """
    db_file = root / "rusterm.db"
    con = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    try:
        counts = {table: con.execute(
            f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in K4_TABLES}
        counts["integrity"] = con.execute(
            "PRAGMA integrity_check").fetchone()[0]
        return counts
    finally:
        con.close()


def test_two_ingest_processes_match_the_sequential_run(tmp_path):
    """K4: два процесса ingest на одной базе — коды 0, «database is
    locked» нет, счётчики равны последовательному прогону.

    Гонка настоящая: `source_cursor` синтетического источника общий для
    всей базы (ключ — провайдер + индекс, не инструмент), так что оба
    процесса читают один и тот же курсор и борются за одни и те же
    ключи идемпотентности задания. Без паузы `tests/k4_stub` второй
    процесс приходит на уже записанный курсор, не находит новых записей
    индекса и пишет только сам курсор — тогда тест не краснеет ни от
    схлопнутого busy timeout, ни от выключенной дедупликации (замеры в
    отчёте, ТЗ-84 K4).

    Распределение работы по инструментам не проверяется и это измерено, а
    не предполагается: 30 повторов пары без паузы — 29 раз шесть фактов
    записал запущенный первым, один раз запущенный вторым; 30 повторов с
    паузой — те же шесть фактов, два задания и два raw-объекта в каждом
    исходе.
    """
    seq_root = tmp_path / "sequential"
    _k4_prepare(seq_root)
    first = _k4_cli(seq_root, "ingest", "--source", "synthetic",
                    "--instrument", "US-K4A")
    assert first.returncode == 0, first.stderr
    second = _k4_cli(seq_root, "ingest", "--source", "synthetic",
                     "--instrument", "US-K4B")
    assert second.returncode == 0, second.stderr
    baseline = _k4_counts(seq_root)
    assert baseline["fact"] > 0, (
        f"последовательный прогон не записал ни одного факта "
        f"({baseline['fact']}) — сравнение счётчиков ничего не доказывает")

    instruments = tuple(inst for inst, _, _ in K4_INSTRUMENTS)
    for i in range(K4_REPETITIONS):
        root = tmp_path / f"repeat-{i}"
        _k4_prepare(root)
        # очерёдность запуска меняется от повтора к повтору: победа в
        # гонке курсора не должна зависеть от того, кто стартовал первым
        order = instruments if i % 2 == 0 else instruments[::-1]
        done = _k4_pair(root, order)
        for instrument_id, (code, out, err, _s, _e) in done.items():
            assert code == 0, (f"{instrument_id}: код {code} вместо 0, "
                               f"stderr: {err!r}")
            assert "database is locked" not in err, (
                f"{instrument_id}: второй писатель упёрся в замок — "
                f"stderr: {err!r}")
            assert "Traceback" not in err, (f"{instrument_id}: трейсбек в "
                                            f"stderr: {err!r}")
            assert "Traceback" not in out, (f"{instrument_id}: трейсбек в "
                                            f"stdout: {out!r}")
        starts = [record[3] for record in done.values()]
        ends = [record[4] for record in done.values()]
        assert min(ends) > max(starts), (
            f"повтор {i}: процессы не перекрывались (старты {starts}, "
            "финиши {ends}) — это два последовательных прогона, а не два "
            "одновременных")
        assert _k4_counts(root) == baseline, (
            f"повтор {i}: счётчики разошлись с последовательного "
            f"прогона: {_k4_counts(root)} против {baseline}")


# ── K5: читатель не видит половины транзакции ─────────────────────────

# Размер атомарной пачки: счётчик у читателя обязан быть кратен именно ему.
BATCH = 100
N_BATCHES = 5
# Пауза после коммита пачки: без неё состояние «100 строк видно» живёт
# миллисекунды, и «читатель ничего не увидел» нельзя отличить от
# «читатель не успел спросить».
PLATEAU = 0.02
# Пауза между отдельными строками в контрольном прогоне: частичное
# состояние обязано наблюдаться, иначе контроль ничего не контролирует.
ROW_PAUSE = 0.001
# Сколько наблюдений обязан сделать читатель за прогон: ниже этого
# зелёный результат значит лишь «не успел спросить».
MIN_OBSERVATIONS = 50


def _poll_batches(root, prefix: str, atomic: bool):
    """Писатель кладёт N_BATCHES×BATCH строк, читатель непрерывно опрашивает счётчик.

    `atomic=True` — каждая пачка одной транзакцией (то, что обязан
    гарантировать `writer_transaction`); `atomic=False` — каждая строка
    своей транзакцией, то есть ровно та поломка, которую проверяющий
    обязан заметить. Возвращает список наблюдённых счётчиков.

    Instrument_id строится как «US-<prefix>-<пачка>-<строка>», поэтому
    фильтр читателя — `LIKE 'US-<prefix>%'`: чужие инструменты (K1, K3) в
    той же базе на него не влияют.
    """
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = db.open_connection(paths)
    apply_migrations(conn)
    RepoRegistry(conn, paths).instrument.upsert_issuer(Issuer(
        prefix, f"Issuer {prefix}", "US", None, None, "us_gaap", "USD"))
    conn.close()

    like = f"US-{prefix}%"
    count_sql = ("SELECT COUNT(*) FROM instrument "
                 "WHERE instrument_id LIKE ?")
    seen: list[int] = []
    errors: list[str] = []
    stop = threading.Event()
    written = threading.Event()
    # Читатель обязан догнать писателя: без этого «зелёный» мог означать,
    # что опрос закончился, когда в базе было десять строк.
    reached = threading.Event()

    def reader() -> None:
        mine = db.open_connection(paths)
        try:
            while not stop.is_set():
                n = mine.execute(count_sql, (like,)).fetchone()[0]
                seen.append(n)
                if n == N_BATCHES * BATCH:
                    reached.set()
        except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
            errors.append(f"читатель: {type(exc).__name__}: {exc}")
        finally:
            mine.close()

    def writer() -> None:
        mine = db.open_connection(paths)
        row = ("INSERT INTO instrument(instrument_id, issuer_id, class, "
               "status) VALUES (?, ?, ?, ?)")
        try:
            for b in range(N_BATCHES):
                if atomic:
                    # Вся пачка — одна транзакция: наружу выходит сразу
                    # BATCH строк либо ничего.
                    with db.writer_transaction(mine):
                        for i in range(BATCH):
                            mine.execute(row, (f"US-{prefix}-{b}-{i}",
                                               prefix, "common", "active"))
                    time.sleep(PLATEAU)
                else:
                    for i in range(BATCH):
                        with db.writer_transaction(mine):
                            mine.execute(row, (f"US-{prefix}-{b}-{i}",
                                               prefix, "common", "active"))
                        time.sleep(ROW_PAUSE)
            written.set()
        except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
            errors.append(f"писатель: {type(exc).__name__}: {exc}")
        finally:
            mine.close()

    rd = threading.Thread(target=reader, daemon=True)
    wr = threading.Thread(target=writer, daemon=True)
    rd.start()
    wr.start()
    wr.join(JOIN_TIMEOUT)
    stop.set()
    rd.join(JOIN_TIMEOUT)
    assert not wr.is_alive(), "писатель не завершился за потолок ожидания"
    assert not rd.is_alive(), "читатель не завершился за потолок ожидания"
    assert written.is_set(), f"писатель не дописал: {errors}"
    assert not errors, f"гонка уронила поток: {errors}"
    assert reached.is_set(), (
        f"читатель не досчитался {N_BATCHES * BATCH} строк "
        f"(наблюдений {len(seen)}, максимум {max(seen) if seen else 'нет'}) "
        "— опрос закончился раньше записи")
    assert len(seen) >= MIN_OBSERVATIONS, (
        f"читатель сделал {len(seen)} наблюдений — слишком редко, чтобы "
        "отличить атомарную пачку от построчной записи")
    return seen


def test_reader_sees_only_whole_batches(tmp_path):
    """K5: каждое наблюдение читателя кратно пачке.

    В WAL читатель по устройству видит последний коммит, а не середину
    транзакции; смысл теста — не поверить этому на слово, а измерить
    часами на настоящем писателе. Контрольный прогон (`atomic=False`)
    обязателен: он показывает, что тот же способ опроса частичное
    состояние замечает. Без него зелёный результат означал бы лишь то,
    что читатель не успевал спросить.
    """
    control = _poll_batches(tmp_path / "control", "K5C", atomic=False)
    partial = sorted({n for n in control if n % BATCH != 0})
    assert partial, (
        f"построчный писатель показал только кратные счётчики "
        f"({sorted(set(control))}) — опрос читателя слишком редкий, и "
        f"настоящий прогон ничего бы не доказал")

    atomic = _poll_batches(tmp_path / "atomic", "K5A", atomic=True)
    halves = sorted({n for n in atomic if n % BATCH != 0})
    assert not halves, f"читатель видел половину пачки: {halves}"
    observed = sorted(set(atomic))
    assert len(observed) >= 2, (
        f"читатель не различил промежуточные состояния ({observed}) — "
        f"опрос был либо до записи, либо после неё")
    assert observed[-1] == N_BATCHES * BATCH, (
        f"последнее наблюдение {observed[-1]} ≠ {N_BATCHES * BATCH}: "
        "пачки потеряны")


# ── K6: сбор из окна под записями UI ─────────────────────────────────

# Минимальное число подходов «UI»: цикл продолжается, пока рабочий поток
# собирает (см. `running` в `_k6_ui_churn`), так что это пол, а не потолок:
# добавление, удаление и откат версии успевают попасть и до стадий сбора,
# и после них.
K6_CHURN_ROUNDS = 12
# Потолок подходов: зависший сбор не должен превратить тест в ожидание —
# для этого есть `JOIN_TIMEOUT` на `thread.join`.
K6_CHURN_MAX_ROUNDS = 120
# Пауза между подходами UI: без неё подходы укладываются в один шаг
# сборщика, и «запись поверх его коммита» остаётся неиспытанной.
K6_CHURN_PAUSE = 0.03
# Как часто UI опрашивает прогресс сборщика, ожидая первого коммита.
K6_POLL = 0.005
# Пауза вокруг обращений к индексу и документам (см. `_k6_paced_providers`).
K6_PAUSE = 0.05
# Инструменты, которыми UI наполняет список: FK `watchlist_member` ведёт в
# `instrument`, так что выдуманный id дал бы ошибку целостности вместо
# проверки конкурентности.
K6_MEMBERS = tuple(f"US-K6-m{i}" for i in range(6))
# Таблицы, по которым видно, что конвейер закоммитил: их заполняет только
# сборщик (цикл UI трогает `watchlist_*`), и их общее число внутри одного
# сбора монотонно не убывает, а растёт шагами — по шагам и проверяется
# перемешивание двух писателей.
K6_PROGRESS_TABLES = ("job", "fact", "raw_object", "coverage")


def _k6_progress(conn) -> int:
    return sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in K6_PROGRESS_TABLES)


def _k6_seed(paths, conn) -> str:
    """Демо-инструмент — теми же дверями, что `rusterm demo` (identifiers
    импортируются, не копируются), плюс список и инструменты для его
    состава."""
    from rusterm.cli import DEMO_INSTRUMENT, DEMO_ISSUER
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        DEMO_ISSUER, "CLI Demo Corp (synthetic)", "US", None, None,
        "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        DEMO_INSTRUMENT, DEMO_ISSUER, None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        f"{DEMO_INSTRUMENT}-listing", DEMO_INSTRUMENT, "XNAS", "USD", 1,
        None, None))
    repos.instrument.add_ticker_history(f"{DEMO_INSTRUMENT}-listing",
                                        "DEMO", "2020-01-01", None, None,
                                        None)
    for instrument_id in K6_MEMBERS:
        repos.instrument.upsert_instrument(
            _instrument(instrument_id, DEMO_ISSUER))
    repos.watchlist.create_watchlist("K6", "K6 watchlist", None, None)
    repos.watchlist.new_version("K6-v1", "K6", 1, "create", None)
    return DEMO_INSTRUMENT


def _k6_paced_providers(cancel=None):
    """Настоящий синтетический провайдер, у которого шаги идут медленнее.

    Без паузы сбор демо-инструмента занимает доли миллисекунды между
    коммитами, и «окно пишет поверх сборщика» сводится к редким шагам,
    между которыми UI не успевает сделать ни одной записи. Пауза ставится
    вокруг `poll_index` и `fetch_document` — между записями конвейера, а не
    внутри них, — и ничего не подменяет: данные отдаёт тот же
    `SyntheticDisclosuresProvider` с той же фикстурой. Приём `providers=` —
    дверь продукта, ею пользуются тесты самого окна.

    `cancel` поднимается после ответа индекса: это отмена на лету, а не до
    старта.
    """
    inner = actions._synthetic_providers()["synthetic"]

    class Paced:
        reason = None

        def poll_index(self, cursor):
            index = inner.poll_index(cursor)
            time.sleep(K6_PAUSE)
            if cancel is not None:
                cancel.cancel()
            return index

        def fetch_document(self, url):
            document = inner.fetch_document(url)
            time.sleep(K6_PAUSE)
            return document

    return {"synthetic": Paced()}


def _k6_ui_churn(paths, rounds: int, log: list, errors: list,
                 running=None, witnesses=None, gate=None) -> None:
    """«UI» в основном потоке: добавляет участника, убирает участника,
    каждую четвёртую итерацию откатывает версию.

    Три разные двери записи списка — `new_version`+`copy_members_except`
    (единственная дверь удаления, ТЗ-62 G2), `add_member` и `rollback_to`;
    у каждой своё `writer_transaction` в этом же процессе. `log` — то, что
    UI прочитал сразу после своей записи: по нему тест проверяет, что ни
    одна правка не пропала в гонке со сборщиком.

    Три рычага делают пересечение проверкой, а не удачей. `gate` — сколько
    записей конвейера обязано быть видно до первой записи UI: иначе сборщик
    управляется раньше, чем окно начинает писать. `running` — пока поток
    сбора жив, цикл не останавливается на `rounds`: интервал UI заведомо
    накрывает сбор. `witnesses` — пары «прогресс сборщика до записи UI и
    после неё»; по ним видно, что коммиты двух писателей шли вперемешку, а
    не друг за другом.
    """
    mine = db.open_connection(paths)
    try:
        w = RepoRegistry(mine, paths).watchlist
        if gate is not None:
            deadline = time.monotonic() + JOIN_TIMEOUT
            while _k6_progress(mine) <= gate:
                if time.monotonic() > deadline:
                    errors.append(
                        f"UI не дождался коммитов сборщика: на {K6_PROGRESS_TABLES} "
                        f"так и не стало больше {gate} записей за "
                        f"{JOIN_TIMEOUT} с")
                    return
                time.sleep(K6_POLL)
        n = 0
        while (n < rounds
               or (running is not None and running()
                   and n < K6_CHURN_MAX_ROUNDS)):
            pre = _k6_progress(mine)
            current = w.current_version("K6")
            assert current is not None, "список K6 исчез из базы"
            prev = [row["instrument_id"] for row in
                    w.members("K6", current["version"])]
            number = current["version"] + 1
            vid = f"K6-churn-{n}"
            w.new_version(vid, "K6", number, "edit", None)
            dropped = K6_MEMBERS[n % len(K6_MEMBERS)]
            w.copy_members_except(current["watchlist_version_id"], vid,
                                  [dropped])
            kept = [m for m in prev if m != dropped]
            added = next((m for m in K6_MEMBERS if m not in kept), None)
            if added is not None:
                w.add_member(vid, added, None)
            log.append((number, sorted(row["instrument_id"]
                                       for row in w.members("K6"))))
            if n % 4 == 3:
                rolled = w.rollback_to("K6", max(1, n // 2))
                log.append((rolled["version"],
                            sorted(row["instrument_id"]
                                   for row in w.members("K6"))))
            if witnesses is not None:
                witnesses.append((pre, _k6_progress(mine)))
            n += 1
            time.sleep(K6_CHURN_PAUSE)
    except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
        errors.append(f"UI: {type(exc).__name__}: {exc}")
    finally:
        mine.close()


def _k6_snapshots(conn, instrument_id: str) -> list:
    """Снапшоты инструмента с числом мер у каждого: «половина набора мер»
    ищется здесь, поэтому считается не только число строк в `snapshot`, но
    и полнота мер каждой версии."""
    rows = conn.execute(
        "SELECT snapshot_id, version FROM snapshot WHERE instrument_id=? "
        "ORDER BY version", (instrument_id,)).fetchall()
    return [(row["snapshot_id"], row["version"],
             conn.execute("SELECT COUNT(*) FROM measure WHERE snapshot_id=?",
                          (row["snapshot_id"],)).fetchone()[0])
            for row in rows]


def test_desktop_collect_finishes_under_ui_writes(tmp_path):
    """K6: рабочий поток собирает, пока основной поток правит список.

    `desktop_actions.collect_synthetic` — та дверь, из которой окно пишет в
    ту же базу: конвейер, coverage, снапшот. Пока она идёт, «UI» добавляет и
    убирает участников списка и откатывает версии — все его записи идут
    через `writer_transaction` этого же процесса. Ровно та пара писателей,
    о которой говорит I14, и ровно та, которой в тестах не было.

    Пересечение доказывается не часами: UI начинает писать только после
    первого коммита сборщика (`gate`), кончает только после его смерти
    (`running`), а пары `witnesses` показывают, что коммиты двух писателей
    чередовались. Замеры того, что остаётся без этих рычагов, — в отчёте.
    """
    paths, conn = _fresh_root(tmp_path)
    instrument_id = _k6_seed(paths, conn)
    conn.close()

    outcome: list = []
    stages: list = []
    churn_log: list = []
    churn_errors: list = []
    witnesses: list = []
    span: list = []
    underway = threading.Event()

    def on_stage(name: str) -> None:
        stages.append(name)
        underway.set()  # сборщик в деле — «UI» может писать поверх него

    def worker() -> None:
        began = time.monotonic()
        try:
            outcome.append(actions.collect_synthetic(
                paths.root, instrument_id, on_stage=on_stage,
                providers=_k6_paced_providers()))
        except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
            outcome.append(exc)
        finally:
            span.append((began, time.monotonic()))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert underway.wait(JOIN_TIMEOUT), (
        "сбор не объявил ни одной стадии — «UI» не дождался бы его")
    ui_began = time.monotonic()
    _k6_ui_churn(paths, K6_CHURN_ROUNDS, churn_log, churn_errors,
                 running=thread.is_alive, witnesses=witnesses, gate=0)
    ui_finished = time.monotonic()
    thread.join(JOIN_TIMEOUT)

    assert not thread.is_alive(), (
        f"сбор не вернулся за {JOIN_TIMEOUT} с под записями UI — это "
        "зависание на локе, а не медленная работа")
    assert not churn_errors, f"запись UI упала: {churn_errors}"
    assert outcome, "поток сбора не сообщил результат"
    result = outcome[0]
    assert not isinstance(result, BaseException), (
        f"сбор под записями UI упал исключением: {type(result).__name__}: "
        f"{result}")
    assert result.ok, (f"сбор не завершился: reason={result.reason} "
                       f"detail={result.detail}")
    assert "конвейер" in " ".join(stages) and "снапшот" in " ".join(stages), (
        f"стадии сообщены не полностью: {stages}")
    assert span and ui_began < span[0][1] < ui_finished, (
        f"сбор кончился не посреди записей UI (UI {ui_began:.3f}…"
        f"{ui_finished:.3f}, сбор {span[0][0]:.3f}…{span[0][1]:.3f}) — тест "
        "проверял двух последовательных писателей, а не двух одновременных")
    assert witnesses, "UI не записал ни одного свидетельства прогресса"

    check = db.open_connection(paths)
    try:
        # Перемешивание по коммитам, а не по часам: первая запись UI легла
        # после коммита сборщика, и после неё сборщик закоммитил ещё что-то.
        assert all(pre > 0 for pre, _post in witnesses), (
            f"запись UI легла до первого коммита сборщика: {witnesses[0]} — "
            "одновременность по часам ещё не конкурентная запись")
        final = _k6_progress(check)
        assert final > witnesses[0][1], (
            f"сборщик не добавил ни одной записи после первой записи UI "
            f"(после неё {witnesses[0][1]}, всего {final}) — коммиты шли "
            "последовательно, а не вперемешку")
        assert len({pre for pre, _post in witnesses}) >= 2, (
            f"UI за все подходы не увидел ни одного промежуточного шага "
            f"сборщика: {sorted({pre for pre, _ in witnesses})}")
        snaps = _k6_snapshots(check, instrument_id)
        assert snaps, "сбор не оставил ни одного снапшота"
        assert all(measures > 0 for _s, _v, measures in snaps), (
            f"снапшот без мер: {snaps}")
        # Ни одна правка UI не потерялась: число версий и состав последней
        # версии — те же, что записал и прочитал сам UI.
        versions = check.execute(
            "SELECT COUNT(*) FROM watchlist_version "
            "WHERE watchlist_id='K6'").fetchone()[0]
        assert versions == len(churn_log) + 1, (
            f"версий списка {versions} вместо {len(churn_log) + 1} — часть "
            "записей UI в гонке пропала")
        last = sorted(row["instrument_id"] for row in
                      RepoRegistry(check, paths).watchlist.members("K6"))
        assert last == churn_log[-1][1], (
            f"состав последней версии разошёлся с тем, что записывал UI: "
            f"{last} против {churn_log[-1][1]}")
        assert check.execute(
            "PRAGMA integrity_check").fetchone()[0] == "ok", (
            "база повреждена после одновременной записи сборщика и UI")
    finally:
        check.close()


def test_cancelled_desktop_collect_leaves_no_half_snapshot(tmp_path):
    """K6, вторая половина: отмена посреди сбора, пока UI пишет.

    Флаг поднимается после ответа `poll_index` — то есть тогда, когда
    конвейер уже начал работу, а снапшот ещё не строился. Проверка отмены в
    двери идёт после конвейера и до снапшота, поэтому второй сбор обязан
    честно вернуться «отменён» и не изменить числа снапшотов: ни половины
    набора мер, ни новой версии пополам.

    Здесь сборщик после дедупликации заданий не оставляет ни одной новой
    строки (замер — в отчёте), поэтому пересечение доказывается часами и
    живостью потока: UI пишет, пока поток сбора жив, и кончается только
    после его конца.
    """
    paths, conn = _fresh_root(tmp_path)
    instrument_id = _k6_seed(paths, conn)
    conn.close()

    # Первый сбор — целиком: с ним и сравнивается «old».
    first = actions.collect_synthetic(paths.root, instrument_id)
    assert first.ok, f"первый сбор не удался: {first.reason} {first.detail}"

    base = db.open_connection(paths)
    try:
        before = _k6_snapshots(base, instrument_id)
    finally:
        base.close()
    assert before, "первый сбор не оставил снапшота — сравнивать не с чем"

    flag = actions.CancelFlag()
    outcome: list = []
    churn_errors: list = []
    churn_log: list = []
    span: list = []
    underway = threading.Event()

    def worker() -> None:
        began = time.monotonic()
        try:
            outcome.append(actions.collect_synthetic(
                paths.root, instrument_id, cancel=flag,
                on_stage=lambda _name: underway.set(),
                providers=_k6_paced_providers(cancel=flag)))
        except BaseException as exc:  # noqa: BLE001 — тип и есть ответ
            outcome.append(exc)
        finally:
            span.append((began, time.monotonic()))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert underway.wait(JOIN_TIMEOUT), "отменённый сбор не объявил стадии"
    ui_began = time.monotonic()
    _k6_ui_churn(paths, K6_CHURN_ROUNDS, churn_log, churn_errors,
                 running=thread.is_alive)
    ui_finished = time.monotonic()
    thread.join(JOIN_TIMEOUT)

    assert not thread.is_alive(), "отменённый сбор не вернулся за потолок"
    assert not churn_errors, f"запись UI упала: {churn_errors}"
    assert outcome, "второй сбор не сообщил результат"
    result = outcome[0]
    assert not isinstance(result, BaseException), (
        f"отмена уронила сбор исключением: {type(result).__name__}: "
        f"{result}")
    assert result.cancelled, (
        f"отменённый сбор вернулся не статусом «отменён»: ok={result.ok} "
        f"reason={result.reason} detail={result.detail}")
    assert result.snapshot_id is None, (
        f"отменённый сбор построил снапшот {result.snapshot_id}, хотя "
        "отмена проверяется до этой стадии")
    assert span and ui_began < span[0][1] < ui_finished, (
        f"отменённый сбор кончился не посреди записей UI (UI "
        f"{ui_began:.3f}…{ui_finished:.3f}, сбор {span[0][0]:.3f}…"
        f"{span[0][1]:.3f})")

    check = db.open_connection(paths)
    try:
        after = _k6_snapshots(check, instrument_id)
        assert len(after) - len(before) in (0, 1), (
            f"снапшотов было {len(before)}, стало {len(after)}: Done when "
            "разрешает old или old+1, а не «сколько успело дойти»")
        assert [v for _s, v, _m in after] == sorted(
            {v for _s, v, _m in after}), (
            f"версии снапшотов перестали быть рядом без повторов: {after}")
        assert all(measures > 0 for _s, _v, measures in after), (
            f"половина набора мер осталась: {after}")
        assert check.execute(
            "PRAGMA integrity_check").fetchone()[0] == "ok", (
            "база повреждена после отмены сбора")
        versions = check.execute(
            "SELECT COUNT(*) FROM watchlist_version "
            "WHERE watchlist_id='K6'").fetchone()[0]
        assert versions == len(churn_log) + 1, (
            f"версий списка {versions} вместо {len(churn_log) + 1}: отмена "
            "сбора задела и записи UI")
    finally:
        check.close()
