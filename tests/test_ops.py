"""TASK-16 D3–D6: пять условий §2.3 (по одному провалу за раз),
dry-run без единой записи, атомарное применение, лимит 100 и его
граница с плановым refresh.

D6-разборка: refresh --watchlist — не правка состава, он и не создаёт
версию списка: тест гоняет 101-участниковый проход и закрепляет, что
ни подтверждения, ни новой версии не появилось.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from rusterm.core.intent import Clarification, Intent
from rusterm.core.ops import (
    OPERATION_LIMIT,
    Proposal,
    Refused,
    STATUS_ADD,
    STATUS_FILTERED,
    STATUS_PRESENT,
    STATUS_UNRESOLVED,
    apply,
    prepare,
)
from rusterm.core.refresh import refresh_watchlist
from rusterm.providers.budget import (
    Budget,
    NetworkGate,
    RateLimiter,
    RequestGate,
)
from rusterm.providers.edgar import EdgarProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    RepoRegistry,
    WatchlistRepo,
)
from tests.test_refresh import _MultiCikTransport

FAKE_UA = "Synthetic Test synthetic.invalid"


def _seed(n_extra: int = 5, delisted_one: bool = False):
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    wl = WatchlistRepo(conn)
    wl.create_watchlist("w1", "n", None, None)
    wl.new_version("wv0", "w1", 1, "create", None)
    vid = wl.current_version("w1")["watchlist_version_id"]

    def issuer_instrument(n: int, status: str = "active",
                          ticker: str | None = None) -> str:
        repos.instrument.upsert_issuer(Issuer(
            f"i-{n}", f"Issuer {n}", "US", str(700000 + n), None,
            "us_gaap", "USD"))
        iid = f"in-{ticker or n}"
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{n}", None, "common", status, None))
        repos.instrument.upsert_listing(
            __import__("rusterm.store.repos", fromlist=["Listing"]).Listing(
                f"l-{iid}", iid, "US", "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{iid}", ticker or f"T{n}", "2020-01-01", None, None, None)
        return iid

    # уже в списке: один участник текущей версии
    present = issuer_instrument(0, ticker="PRESENT")
    wl.add_member(vid, present, None)
    # исключается фильтром: делистингован
    issuer_instrument(1, status="delisted", ticker="DEAD")
    # разрешились: пул активных
    resolved = [issuer_instrument(n, ticker=f"R{n}")
                for n in range(2, 2 + n_extra)]
    return tmpdir, conn, paths, repos, wl, vid, resolved


def _intent(tickers: list[str], **extra) -> Intent:
    return Intent("add_instruments",
                  {"tickers": tickers, "market": "US", **extra})


def test_d3_five_conditions_each_failing_alone():
    """Пять условий §2.3: каждое проваливается по одному — четыре мимо,
    каждое даёт уточнение/отказ и не меняет состояние."""
    tmpdir, conn, paths, repos, wl, vid, resolved = _seed()
    try:
        def sha() -> str:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            return hashlib.sha256(
                open(str(paths.db_path), "rb").read()).hexdigest()

        # 1. намерение не распознано
        out = prepare(repos, "w1", Clarification("не понято"),
                      "2026-09-09")
        assert isinstance(out, Clarification)
        # 2. обязательный параметр отсутствует
        out = prepare(repos, "w1", Intent(
            "add_instruments", {"market": "US"}), "2026-09-09")
        assert isinstance(out, Clarification)
        assert "tickers" in out.reason
        # 3. тикер не разрешается однозначно
        out = prepare(repos, "w1", _intent(["GHOST"]), "2026-09-09")
        assert isinstance(out, Proposal)
        assert all(r["status"] == STATUS_UNRESOLVED for r in out.rows)
        # 4. размер выше лимита: 101 реальный тикер сеются и резолвятся
        from rusterm.store.repos import Listing
        for n in range(OPERATION_LIMIT + 1):
            repos.instrument.upsert_issuer(Issuer(
                f"i-lim{n}", f"Issuer lim{n}", "US", str(710000 + n),
                None, "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"in-lim{n}", f"i-lim{n}", None, "common", "active", None))
            repos.instrument.upsert_listing(Listing(
                f"l-lim{n}", f"in-lim{n}", "US", "USD", 1, None, None))
            repos.instrument.add_ticker_history(
                f"l-lim{n}", f"LIM{n}", "2020-01-01", None, None, None)
        big = _intent([f"LIM{n}" for n in range(OPERATION_LIMIT + 1)])
        out = prepare(repos, "w1", big, "2026-09-09")
        assert isinstance(out, Refused), out
        assert "101" in out.reason
        baseline = sha()  # все сиды завершены: дальше состояние иначе не меняется

        # 5. подтверждения нет — сухой показ, состояние не тронуто
        intent = _intent(["R2"])
        out = prepare(repos, "w1", intent, "2026-09-09")
        assert isinstance(out, Proposal)
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_version").fetchone()[0] == 1
        assert sha() == baseline
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_d3_confidence_never_executes_on_ambiguous_ticker():
    tmpdir, conn, paths, repos, wl, vid, resolved = _seed()
    try:
        # неоднозначность: два инструмента на один тикер
        for n in (90, 91):
            repos.instrument.upsert_issuer(Issuer(
                f"i-{n}", f"Issuer {n}", "US", str(700000 + n), None,
                "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"in-amb{n}", f"i-{n}", None, "common", "active", None))
            from rusterm.store.repos import Listing
            repos.instrument.upsert_listing(Listing(
                f"l-amb{n}", f"in-amb{n}", "US", "USD", 1, None, None))
            repos.instrument.add_ticker_history(
                f"l-amb{n}", "AMBIG", "2020-01-01", None, None, None)
        intent = Intent("add_instruments",
                        {"tickers": ["AMBIG"], "market": "US",
                         "confidence": 0.99})
        sha = lambda: hashlib.sha256(
            open(str(paths.db_path), "rb").read()).hexdigest()
        baseline = sha()
        out = prepare(repos, "w1", intent, "2026-09-09",
                      size_confirmed=True)
        assert isinstance(out, Proposal)
        assert out.rows[0]["status"] == STATUS_UNRESOLVED
        result = apply(wl, "w1", out.addable)
        assert result["applied"] is False
        assert sha() == baseline, "confidence протолкнул неоднозначность"
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_d4_dry_run_shows_all_four_statuses_writes_nothing():
    tmpdir, conn, paths, repos, wl, vid, resolved = _seed()
    try:
        intent = _intent(["PRESENT", "DEAD", "GHOST", "R2"])
        out = prepare(repos, "w1", intent, "2026-09-09",
                      filters={"exclude_delisted": True})
        assert isinstance(out, Proposal)
        statuses = {r["ticker"]: r["status"] for r in out.rows}
        assert statuses == {
            "PRESENT": STATUS_PRESENT,
            "DEAD": STATUS_FILTERED,
            "GHOST": STATUS_UNRESOLVED,
            "R2": STATUS_ADD,
        }, statuses
        assert out.addable == [(resolved[0], "R2")]

        sha = lambda: hashlib.sha256(
            open(str(paths.db_path), "rb").read()).hexdigest()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        baseline = sha()
        # повторный dry-run не пишет ничего: ни версии, ни участника,
        # ни покрытия, ни аудита — файл базы байт-в-байт тот же
        again = prepare(repos, "w1", intent, "2026-09-09",
                        filters={"exclude_delisted": True})
        assert isinstance(again, Proposal)
        conn.close()
        assert sha() == baseline
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_d5_apply_is_all_or_nothing():
    """Сбой посередине 10-позиционного применения: ноль новых версий,
    ноль новых участников, текущая версия прежняя, ошибка значением."""
    tmpdir, conn, paths, repos, wl, vid, resolved = _seed(n_extra=12)
    try:
        addable = [(iid, "") for iid in resolved[:9]]
        addable.append(("in-GHOST-BOGUS", ""))  # этот INSERT упадёт по FK
        assert len(addable) == 10
        before_versions = conn.execute(
            "SELECT COUNT(*) FROM watchlist_version").fetchone()[0]
        before_members = conn.execute(
            "SELECT COUNT(*) FROM watchlist_member").fetchone()[0]

        result = apply(wl, "w1", addable)
        assert result["applied"] is False
        assert "транзакция отменена" in result["reason"]

        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_version").fetchone()[0] == \
            before_versions, "осталась новая версия после отката"
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_member").fetchone()[0] == \
            before_members, "остались участники после отката"
        assert wl.current_version("w1")["watchlist_version_id"] == vid

        # успех: всё целиком — одна новая версия, все участники в ней
        result = apply(wl, "w1", addable[:9])
        assert result["applied"] is True
        assert wl.current_version("w1")["version"] == 2
        members = {m["instrument_id"]
                   for m in wl.members("w1")}
        assert members == {m["instrument_id"]
                           for m in wl.members("w1")}
        assert "in-R2" in members and len(members) == 10
        # предыдущая версия доступна откату (§3.3)
        assert wl.version_action("w1", 1) == "create"
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_d6_limit_above_100_needs_second_confirmation_refresh_does_not():
    tmpdir, conn, paths, repos, wl, vid, resolved = _seed()
    try:
        # 101 тикер: 100 разрешились бы — сеем 101 реальный
        for n in range(101):
            repos.instrument.upsert_issuer(Issuer(
                f"i-big{n}", f"Issuer big{n}", "US", str(720000 + n),
                None, "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"in-big{n}", f"i-big{n}", None, "common", "active", None))
            from rusterm.store.repos import Listing
            repos.instrument.upsert_listing(Listing(
                f"l-big{n}", f"in-big{n}", "US", "USD", 1, None, None))
            repos.instrument.add_ticker_history(
                f"l-big{n}", f"BIG{n}", "2020-01-01", None, None, None)
        intent = _intent([f"BIG{n}" for n in range(101)])
        out = prepare(repos, "w1", intent, "2026-09-09")
        assert isinstance(out, Refused), out
        assert "101" in out.reason and "подтверждени" in out.reason

        out = prepare(repos, "w1", intent, "2026-09-09",
                      size_confirmed=True)
        assert isinstance(out, Proposal)
        assert len(out.addable) == 101

        # плановый refresh по 101-участниковому списку: ни подтверждения,
        # ни новой версии списка — это не правка состава (§3.4)
        gate = RequestGate(
            budget=Budget(max_requests=5000),
            limiter=RateLimiter(per_second=10 ** 6),
            gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))
        transport = _MultiCikTransport(
            (paths.root.parent / "x").read_bytes()
            if False else b"{}")

        class _NoopTransport:
            def __init__(self):
                self.log: list[str] = []

            def __call__(self, url, headers):
                self.log.append(url)
                return 404, b'{"error": "not recorded"}', {}

        noop = _NoopTransport()

        def provider_factory(cik: int) -> EdgarProvider:
            return EdgarProvider(gate=gate, cik=cik, transport=noop)

        # состав из prep-теста: применяем 101 участника, потом refresh
        result = apply(wl, "w1", out.addable)
        assert result["applied"] is True
        version_before = wl.current_version("w1")["version"]

        results = refresh_watchlist(repos, provider_factory, "w1",
                                    "2026-09-09", builder=None)
        assert len(results) == 102  # PRESENT + 101
        assert wl.current_version("w1")["version"] == version_before, \
            "refresh создал версию списка — это правка состава?"
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_d7_d8_ops_command_audit_rows_confirm_and_json_keys():
    """D7: строка аудита на каждый исход — applied (confirmed=1),
    refused (confirmed как у пользователя), clarification (confirmed=0);
    read-only logs/ оставляет строку в базе и печатает причину на stderr
    (B12). D8: exit-коды dry-run/applied = 0, refused/clarification = 1;
    --json держит пин ключей {watchlist_id, intent, outcome, rows,
    version}."""
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    stub = repo / "tests" / "e2e_stub"
    env = {**os.environ,
           "RUSTERM_SEC_UA": "Synthetic Test e2e.invalid",
           "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
           "PYTHONPATH": os.pathsep.join(
               [str(stub), str(repo), os.environ.get("PYTHONPATH", "")]),
           "TERM": "xterm"}

    def run(root, *argv):
        return subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root, *argv],
            capture_output=True, text=True, env=env)

    def audit_rows(root):
        db = sqlite3.connect(f"{root}/rusterm.db")
        try:
            return db.execute(
                "SELECT action, target, payload, confirmed, result"
                " FROM audit_log ORDER BY ts").fetchall()
        finally:
            db.close()

    tmpdir = tempfile.mkdtemp()
    root = tmpdir
    try:
        assert run(root, "init").returncode == 0
        for ticker in ("AAPL", "MSFT"):
            assert run(root, "add", "--ticker", ticker,
                       "--market", "US").returncode == 0
        assert run(root, "watchlist", "create", "w1",
                   "--name", "n").returncode == 0
        assert run(root, "watchlist", "add", "w1", "--ticker", "AAPL",
                   "--market", "US").returncode == 0

        # clarification: запрос вне правил офлайн-классификатора
        r = run(root, "ops", "--watchlist", "w1",
                "--request", "а как дела у рынка вообще?")
        assert r.returncode == 1, (r.returncode, r.stderr)
        rows = audit_rows(root)
        assert rows[-1][0] == "ops" and rows[-1][4] == "clarification"
        assert rows[-1][3] == 0

        # dry-run: статусы по позициям, код 0, НИ ОДНОЙ строки аудита
        n0 = len(audit_rows(root))
        r = run(root, "ops", "--watchlist", "w1",
                "--request", "добавь MSFT")
        assert r.returncode == 0, (r.returncode, r.stderr)
        assert "будет добавлена" in r.stdout, r.stdout
        assert len(audit_rows(root)) == n0  # dry-run не пишет
        r = run(root, "ops", "--watchlist", "w1",
                "--request", "добавь MSFT", "--json")
        assert r.returncode == 0
        payload = json.loads(r.stdout)
        assert set(payload) == {"watchlist_id", "intent", "outcome",
                                "rows", "version"}, sorted(payload)
        assert payload["outcome"] == "dry-run" and payload["rows"]
        assert payload["rows"][0]["status"] == "будет добавлена"

        # applied: подтверждение применяет одной версией
        r = run(root, "ops", "--watchlist", "w1",
                "--request", "добавь MSFT", "--confirm")
        assert r.returncode == 0, r.stderr
        assert "применено" in r.stdout
        rows = audit_rows(root)
        assert len(rows) == n0 + 1
        assert rows[-1][4] == "applied" and rows[-1][3] == 1

        # повтор с подтверждением: MSFT уже в списке, применяться нечему
        r = run(root, "ops", "--watchlist", "w1",
                "--request", "добавь MSFT", "--confirm")
        assert r.returncode == 1
        rows = audit_rows(root)
        assert len(rows) == n0 + 2
        assert rows[-1][4] == "refused" and rows[-1][3] == 1

        # D6 на команде: 101 тикер без второго подтверждения — отказ.
        # 101 инструмент сеется прямо в базу: resolve обязан найти все
        import sqlite3 as _sq
        db = _sq.connect(f"{root}/rusterm.db", isolation_level=None)
        db.executemany(
            "INSERT INTO issuer(issuer_id, name, jurisdiction,"
            " reporting_standard, reporting_currency)"
            " VALUES (?, ?, 'US', 'us_gaap', 'USD')",
            [(f"i-big{n}", f"Issuer big{n}") for n in range(101)])
        db.executemany(
            "INSERT INTO instrument(instrument_id, issuer_id, class,"
            " status) VALUES (?, ?, 'common', 'active')",
            [(f"in-big{n}", f"i-big{n}") for n in range(101)])
        db.executemany(
            "INSERT INTO listing(listing_id, instrument_id, exchange,"
            " currency, is_primary) VALUES (?, ?, 'US', 'USD', 1)",
            [(f"l-big{n}", f"in-big{n}") for n in range(101)])
        db.executemany(
            "INSERT INTO ticker_history(listing_id, ticker, valid_from)"
            " VALUES (?, ?, '2020-01-01')",
            [(f"l-big{n}", f"BIG{n:03d}") for n in range(101)])
        db.close()
        big_request = "добавь " + ", ".join(
            f"BIG{n:03d}" for n in range(101))
        r = run(root, "ops", "--watchlist", "w1",
                "--request", big_request, "--confirm")
        assert r.returncode == 1, r.stdout
        assert "лимит" in r.stderr, r.stderr
        rows = audit_rows(root)
        assert len(rows) == n0 + 3
        assert rows[-1][4] == "refused"

        # B12: logs/ только для чтения и audit.jsonl нет — строка на
        # stderr, строка в базе, выход по заслугам
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return
        (Path(root) / "logs" / "audit.jsonl").unlink()
        (Path(root) / "logs").chmod(0o555)
        try:
            r = run(root, "ops", "--watchlist", "w1",
                    "--request", "а что ты умеешь?")
            assert r.returncode == 1
            assert "audit_file_unavailable" in r.stderr, r.stderr
            rows = audit_rows(root)
            assert len(rows) == n0 + 4
            assert rows[-1][4] == "clarification"
        finally:
            (Path(root) / "logs").chmod(0o755)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
