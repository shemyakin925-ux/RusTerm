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
