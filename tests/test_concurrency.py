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
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

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
