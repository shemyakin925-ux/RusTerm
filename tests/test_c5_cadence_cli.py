"""ТЗ-31 C5: кадентность получает поверхность — команду и строку
доктора. Правило обхода видно пользователю: состояние, дыры, срок
опроса, цена следующего прохода против потолка вендора."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sqlite3
import tempfile

import pytest

from rusterm.cli import main
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry)

DAY0 = "2026-09-01"


def _root() -> str:
    return tempfile.mkdtemp()


def _seed_price_env(root: str):
    """База с полным (данные до DAY0) и неполным (дыра 11 дней)
    инструментами; цены в USD, тикеров не нужно: каденция идёт по
    stored-датам."""
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-c", "Corp complete", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-CPL", "i-c", None, "common", "active", None))
    repos.instrument.upsert_issuer(Issuer(
        "i-g", "Corp gapped", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-GAP", "i-g", None, "common", "active", None))
    repos.price.put_rows("US-CPL", "twelvedata",
                         [{"date": DAY0, "close": 100.0,
                           "currency": "USD"}])
    repos.price.put_rows("US-GAP", "twelvedata",
                         [{"date": DAY0, "close": 50.0,
                           "currency": "USD"},
                          {"date": "2026-09-12", "close": 51.0,
                           "currency": "USD"}])
    return conn, repos


def _run_json(root: str) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert main(["--root", root, "cadence", "--json",
                     "--as-of", "2026-09-13"]) == 0
    return json.loads(buf.getvalue())


def test_cadence_surface(tmp_path, capsys):
    """JSON: закреплённые ключи, неполный раньше полного, дыры и срок
    опроса; текстовая форма несёт свод и цену следующего прохода."""
    root = str(tmp_path / "app")
    conn, repos = _seed_price_env(root)
    conn.close()
    try:
        payload = _run_json(root)
        assert set(payload) == {"as_of", "instruments", "incomplete",
                                "next_pass_requests", "daily_ceiling"}
        assert payload["as_of"] == "2026-09-13"
        assert payload["incomplete"] == 1
        assert payload["next_pass_requests"] == 2
        assert payload["daily_ceiling"] == 800
        ids = [r["instrument_id"] for r in payload["instruments"]]
        assert ids == ["US-GAP", "US-CPL"], \
            "неполный обязан идти раньше полного (backfill первым)"
        gap_row = payload["instruments"][0]
        assert gap_row["state"] == "incomplete"
        assert gap_row["gaps"] == 1
        assert gap_row["last_date"] == "2026-09-12"
        assert gap_row["next_poll_due"] == "2026-09-13"
        cpl = payload["instruments"][1]
        assert cpl["state"] == "complete" and cpl["gaps"] == 0
        assert cpl["next_poll_due"] == "2026-09-11", \
            "опрос полный: последняя дата + 10 дней"
        # текстовая форма: сводная строка и строка инструмента
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert main(["--root", root, "cadence",
                         "--as-of", "2026-09-13"]) == 0
        out = buf.getvalue()
        assert "неполных 1" in out
        assert "2 запросов из 800/день" in out
        assert "US-GAP: incomplete; дыр 1" in out
        # US-GAP раньше US-CPL и в тексте
        assert out.index("US-GAP") < out.index("US-CPL")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_doctor_gains_cadence_line(capsys):
    """doctor: одна строка-раздел — неполных инструментов и цена
    следующего прохода против 800/день."""
    root = _root()
    try:
        assert main(["--root", root, "init"]) == 0
        main(["--root", root, "demo"])
        capsys.readouterr()
        assert main(["--root", root, "doctor"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["cadence"] == {
            "incomplete": 0, "next_pass_requests": 0,
            "daily_ceiling": 800}
    finally:
        shutil.rmtree(root)
