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
