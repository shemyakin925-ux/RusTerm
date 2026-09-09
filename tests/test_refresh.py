"""TASK-13 Z2: инкрементальный проход — не изменилось, не скачивается.

Десять эмитентов на подставном транспорте (один записанный payload,
размноженный по CIK). Первый проход: по companyfacts на каждого.
Второй: только submissions — companyfacts не запрашивается вовсе,
факты и raw_object не растут. Настоящая сеть не трогается.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

from rusterm.core.refresh import refresh_watchlist
from rusterm.core.snapshot import SnapshotBuilder
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

N_ISSUERS = 10
FAKE_UA = "Synthetic Test synthetic.invalid"


def _saved_payload() -> bytes:
    data = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"
    return (data / "companyfacts_m3_AAPL.json").read_bytes()


class _MultiCikTransport:
    """Один записанный payload, размноженный по CIK: каждый эмитент
    получает ответ со своим cik (уникальные байты, как у настоящего
    фида); считает запросы по виду URL. submissions отдаёт свежую дату
    подачи один раз (проход 1), после чего «замирает» — второй проход
    видит ту же дату."""

    def __init__(self, payload: bytes):
        self._base = json.loads(payload)
        self._per_cik: dict[int, bytes] = {}
        self.log: list[str] = []
        self.freeze_after = None      # запросов, после которого дата фиксирована
        self._frozen_date = None

    def __call__(self, url, headers):
        self.log.append(url)
        if "submissions" in url:
            date = f"2026-01-{self._next_day():02d}"
            if self.freeze_after is not None and len(self.log) > self.freeze_after:
                date = self._frozen_date
            else:
                self._frozen_date = date
            body = {"filings": {"recent": {
                "form": ["10-K"], "filingDate": [date],
                "reportDate": ["2025-12-31"]}}}
            return 200, json.dumps(body).encode(), {}
        cik = int(url.rsplit("CIK", 1)[1].split(".")[0])
        if cik not in self._per_cik:
            doc = dict(self._base)
            doc["cik"] = cik
            self._per_cik[cik] = json.dumps(doc).encode()
        return 200, self._per_cik[cik], {}

    def _next_day(self) -> int:
        return min(28, 10 + len(self.log))


def test_z2_second_pass_requests_submissions_only():
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        watchlist = WatchlistRepo(conn)
        watchlist.create_watchlist("wl1", "десять", None, None)
        watchlist.new_version(str(uuid.uuid4()), "wl1", 1, "create", None)

        payload = _saved_payload()
        base_cik = 900000
        for n in range(N_ISSUERS):
            issuer_id = f"i-{n:03d}"
            instrument_id = f"US-T{n:03d}"
            repos.instrument.upsert_issuer(Issuer(
                issuer_id, f"Issuer {n:03d} (recorded payload)", "US",
                str(base_cik + n), None, "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                instrument_id, issuer_id, None, "common", "active", None))
            watchlist.add_member(
                watchlist.current_version("wl1")["watchlist_version_id"],
                instrument_id, None)

        gate = RequestGate(
            budget=Budget(max_requests=5000),
            limiter=RateLimiter(per_second=5000),
            gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))
        transport = _MultiCikTransport(payload)
        # заморозить дату подачи после первого submissions: второй
        # проход обязан увидеть «не изменилось»
        transport.freeze_after = 1

        def provider_factory(cik: int) -> EdgarProvider:
            return EdgarProvider(gate=gate, cik=cik, transport=transport)

        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)

        cf = lambda u: "companyfacts" in u
        sb = lambda u: "submissions" in u

        first = refresh_watchlist(repos, provider_factory, "wl1",
                                  "2026-09-09", builder=builder)
        assert len(first) == N_ISSUERS
        assert all(r.action == "updated" for r in first), \
            [(r.instrument_id, r.action, r.reason) for r in first]
        first_cf = sum(1 for u in transport.log if cf(u))
        assert first_cf == N_ISSUERS, (
            f"первый проход: {first_cf} companyfacts из {N_ISSUERS}")

        facts_after_first = conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0]
        raw_after_first = conn.execute(
            "SELECT COUNT(*) FROM raw_object").fetchone()[0]
        log_after_first = list(transport.log)

        second = refresh_watchlist(repos, provider_factory, "wl1",
                                   "2026-09-09", builder=builder)
        assert len(second) == N_ISSUERS
        assert all(r.action == "unchanged" for r in second), \
            [(r.instrument_id, r.action, r.reason) for r in second]

        second_cf = sum(1 for u in transport.log if cf(u)) - first_cf
        second_sb = sum(1 for u in transport.log if sb(u)) - \
            sum(1 for u in log_after_first if sb(u))
        assert second_cf == 0, \
            f"второй проход скачал {second_cf} companyfacts"
        assert second_sb == N_ISSUERS, \
            f"второй проход сделал {second_sb} запросов submissions"

        assert conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0] == facts_after_first
        assert conn.execute(
            "SELECT COUNT(*) FROM raw_object"
        ).fetchone()[0] == raw_after_first

        # skip виден: у каждой строки причина и дата последней отчётности
        for r in second:
            assert r.reason and r.last_filing_date, r
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_z4_refresh_command_dry_run_zero_requests_and_json_keys():
    """TASK-13 Z4: rusterm refresh --watchlist как команда для cron.
    --dry-run делает 0 запросов и печатает непустой план; обычный прогон
    печатает по строке на инструмент; --json разбирается json.loads,
    ключи закреплены этим тестом. Подпроцессы на подменном EDGAR."""
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

    def run(root, *argv, call_log=None):
        e = dict(env)
        if call_log is not None:
            e["RUSTERM_EDGAR_CALL_LOG"] = str(call_log)
        return subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root, *argv],
            capture_output=True, text=True, env=e)

    tmpdir = tempfile.mkdtemp()
    root = tmpdir
    call_log = Path(tmpdir) / "calls.txt"
    try:
        assert run(root, "init").returncode == 0
        r = run(root, "add", "--ticker", "AAPL", "--market", "US")
        assert r.returncode == 0, r.stderr
        assert run(root, "watchlist", "create", "w1",
                   "--name", "n").returncode == 0
        assert run(root, "watchlist", "add", "w1", "--ticker", "AAPL",
                   "--market", "US").returncode == 0

        # --dry-run: 0 запросов, непустой план
        r = run(root, "refresh", "--watchlist", "w1", "--dry-run",
                call_log=call_log)
        assert r.returncode == 0, r.stderr
        assert call_log.exists() is False or \
            call_log.read_text().strip() == "", \
            "dry-run обязан сделать 0 запросов"
        plan_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        assert plan_lines, "план dry-run пуст"

        # обычный прогон: по строке на инструмент, все обновлены
        r = run(root, "refresh", "--watchlist", "w1")
        assert r.returncode == 0, r.stderr
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        assert len(lines) == 1 and "обновлён" in lines[0], lines

        # повтор: не изменилось
        r = run(root, "refresh", "--watchlist", "w1")
        assert r.returncode == 0, r.stderr
        assert "не изменилось" in r.stdout

        # --json: ключи закреплены (B16-стиль)
        r = run(root, "refresh", "--watchlist", "w1", "--json")
        assert r.returncode == 0, r.stderr
        payload = json.loads(r.stdout)
        assert set(payload) == {"watchlist_id", "dry_run", "results",
                                "requests"}, sorted(payload)
        assert payload["watchlist_id"] == "w1"
        assert payload["dry_run"] is False
        assert set(payload["results"][0]) == {
            "instrument_id", "issuer_id", "action", "facts",
            "last_filing_date", "reason"}, sorted(payload["results"][0])
        assert payload["results"][0]["action"] == "unchanged"
        assert set(payload["requests"]) == {"submissions", "companyfacts"}
        assert payload["requests"]["companyfacts"] == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_a5_refresh_writes_one_audit_row_per_pass():
    """TASK-14 A5: refresh мутирует store и обязан писать аудит.
    Обычный проход — ровно одна строка audit_log (action=refresh,
    target=список, payload=счётчики, confirmed=0, result=ok/errors);
    --dry-run не пишет ничего; недоступный файл аудита даёт строку на
    stderr и при этом строку в базе (B12), код возврата — свои заслуги
    прохода. Подпроцессы на подменном EDGAR, настоящая сеть не трогается."""
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
        import sqlite3
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
        assert run(root, "add", "--ticker", "AAPL", "--market", "US") \
            .returncode == 0
        assert run(root, "watchlist", "create", "w1",
                   "--name", "n").returncode == 0
        assert run(root, "watchlist", "add", "w1", "--ticker", "AAPL",
                   "--market", "US").returncode == 0
        baseline = len(audit_rows(root))  # строки add/watchlist — не ours

        # --dry-run: изменений нет — строк нет
        r = run(root, "refresh", "--watchlist", "w1", "--dry-run")
        assert r.returncode == 0, r.stderr
        assert len(audit_rows(root)) == baseline

        # обычный проход: одна строка, счётчики и result закреплены
        r = run(root, "refresh", "--watchlist", "w1")
        assert r.returncode == 0, r.stderr
        rows = audit_rows(root)
        assert len(rows) == baseline + 1, rows[baseline:]
        action, target, payload, confirmed, result = rows[baseline]
        assert (action, target, confirmed, result) == \
            ("refresh", "w1", 0, "ok"), rows[baseline]
        assert json.loads(payload) == {
            "updated": 1, "unchanged": 0, "error": 0,
            "submissions": 1, "companyfacts": 1}, payload

        # второй проход: unchanged — строка пишется и здесь
        r = run(root, "refresh", "--watchlist", "w1")
        assert r.returncode == 0, r.stderr
        assert "не изменилось" in r.stdout
        rows = audit_rows(root)
        assert len(rows) == baseline + 2
        assert json.loads(rows[baseline + 1][2])["unchanged"] == 1

        # B12: logs/ только для чтения и audit.jsonl не существует —
        # создать файл нельзя, apppend падает: stderr-строка + строка
        # в базе, выход по заслугам прохода (0: ошибок в данных нет)
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return  # root игнорирует права каталога
        (Path(root) / "logs" / "audit.jsonl").unlink()
        (Path(root) / "logs").chmod(0o555)
        try:
            r = run(root, "refresh", "--watchlist", "w1")
            assert r.returncode == 0, r.stderr
            assert "audit_file_unavailable" in r.stderr, r.stderr
            rows = audit_rows(root)
            assert len(rows) == baseline + 3
            assert rows[baseline + 2][4] == "ok"
        finally:
            (Path(root) / "logs").chmod(0o755)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_b20_cli_request_totals_match_per_result_calls(monkeypatch, capsys):
    """BACKLOG B20: суммы requests в --json обязаны сходиться с суммой
    RefreshResult.calls по results — и на нормальном проходе, и на
    смешанном (один инструмент ошибается, его calls пусты). Проход
    перехватывается обёрткой ровно один раз: totals сверяются с тем же
    самым экземпляром результатов, который напечатан."""
    import rusterm.cli as cli
    from rusterm.providers.budget import RequestGate
    from rusterm.providers.edgar import EdgarProvider
    from rusterm.store.repos import Instrument, Issuer, WatchlistRepo

    captured: dict = {}
    real_refresh = cli.refresh_watchlist

    def spy(repos_, factory, watchlist_id, as_of, **kw):
        results = real_refresh(repos_, factory, watchlist_id, as_of, **kw)
        captured["results"] = results
        return results

    monkeypatch.setattr(cli, "refresh_watchlist", spy)
    monkeypatch.setenv("RUSTERM_SEC_UA", FAKE_UA)
    transport = _MultiCikTransport(_saved_payload())

    def fake_provider(name, gate: RequestGate):
        assert name == "edgar"
        return EdgarProvider(gate=gate, cik=0, transport=transport)

    monkeypatch.setattr(cli, "get_provider", fake_provider)

    tmpdir = tempfile.mkdtemp()
    try:
        from rusterm.store.db import apply_migrations
        from rusterm.store.paths import AppPaths, ensure_app_dir
        import sqlite3
        paths = AppPaths.from_root(tmpdir)
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = type("Repos", (), {"instrument": None, "watchlist": None})()
        from rusterm.store.repos import RepoRegistry
        repos = RepoRegistry(conn, paths)
        wl = WatchlistRepo(conn)
        wl.create_watchlist("w1", "n", None, None)
        wl.new_version("v1", "w1", 1, "create", None)
        vid = wl.current_version("w1")["watchlist_version_id"]
        for n, cik in ((1, "900001"), (2, "900002")):
            repos.instrument.upsert_issuer(Issuer(
                f"i-{n}", f"Issuer {n}", "US", cik, None, "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"US-B20-{n}", f"i-{n}", None, "common", "active", None))
            wl.add_member(vid, f"US-B20-{n}", None)
        conn.close()

        # нормальный проход: оба обновлены
        import json
        assert cli.main(["--root", tmpdir, "refresh",
                         "--watchlist", "w1", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        results = captured["results"]
        assert [r.action for r in results] == ["updated", "updated"]
        assert payload["requests"]["submissions"] == \
            sum(r.calls.get("submissions", 0) for r in results)
        assert payload["requests"]["companyfacts"] == \
            sum(r.calls.get("companyfacts", 0) for r in results)

        # смешанный: третий инструмент без CIK ошибается (calls пусты)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        repos2 = RepoRegistry(conn, paths)
        repos2.instrument.upsert_issuer(Issuer(
            "i-bad", "Bad", "US", "not-a-cik", None, "us_gaap", "USD"))
        repos2.instrument.upsert_instrument(Instrument(
            "US-B20-BAD", "i-bad", None, "common", "active", None))
        WatchlistRepo(conn).add_member(vid, "US-B20-BAD", None)
        conn.close()

        # --json-режим возвращает 0 и при ошибках (контракт закреплён
        # тестом Z4 до B20) — смешанность прохода проверяется по action
        assert cli.main(["--root", tmpdir, "refresh",
                         "--watchlist", "w1", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        results = captured["results"]
        actions = sorted(r.action for r in results)
        # второй проход качает companyfacts (дата подачи уехала), но
        # payload тот же байт-в-байт — sha256-дедупликация даёт
        # unchanged, не updated; ошибка CIK остаётся ошибкой
        assert actions == ["error", "unchanged", "unchanged"], actions
        bad = [r for r in results if r.action == "error"][0]
        assert bad.calls == {}
        assert payload["requests"]["submissions"] == \
            sum(r.calls.get("submissions", 0) for r in results)
        assert payload["requests"]["companyfacts"] == \
            sum(r.calls.get("companyfacts", 0) for r in results)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
