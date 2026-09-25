"""ТЗ-73 T2: набор аналогов заводится обычным путём (координатор, 24.09).

На базе пользователя peer_set — 0 строк: ни одна команда не умела
создать набор, и вкладка «Отрасль» не могла наполниться. Проверяется
дверь rusterm peers и правила ADR-0002: версии без двойного покрытия
даты, обязательное происхождение, модель сама себя не подтверждает,
повтор той же команды не рождает новую версию.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.cli import main as cli_main
from rusterm.core.peer_sets import PeerSetRefused, set_industry_peers
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

TODAY = "2026-09-24"
LATER = "2026-10-01"


@pytest.fixture()
def repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    r = RepoRegistry(conn, paths)
    for i in range(10):
        r.instrument.upsert_issuer(Issuer(
            f"i{i}", f"Corp {i}", "US", None, None, "us_gaap", "USD"))
        r.instrument.upsert_instrument(Instrument(
            f"US-T{i}", f"i{i}", None, "common", "active", None))
    return r


def ids(n):
    return [f"US-T{i}" for i in range(n)]


def test_first_set_creates_version_one(repos):
    res = set_industry_peers(repos, "software", ids(9), "manual", True,
                             TODAY)
    assert (res.version, res.created, res.members) == (1, True, 9)
    cur = repos.peer_set.open_version("software")
    assert cur["origin"] == "manual" and cur["approved"]
    assert cur["members"] == set(ids(9))


def test_repeating_the_same_set_adds_no_version(repos):
    set_industry_peers(repos, "software", ids(9), "manual", True, TODAY)
    res = set_industry_peers(repos, "software", ids(9), "manual", True,
                             LATER)
    assert (res.version, res.created) == (1, False)


def test_new_composition_closes_the_old_version(repos):
    set_industry_peers(repos, "software", ids(9), "classifier", False,
                       TODAY)
    res = set_industry_peers(repos, "software", ids(10), "manual", True,
                             LATER)
    assert (res.version, res.closed_version) == (2, 1)
    # одна дата — одна версия: version_at не видит двойного покрытия
    assert repos.peer_set.version_at("software", TODAY)["version"] == 1
    assert repos.peer_set.version_at("software", LATER)["version"] == 2


def test_model_suggestion_cannot_approve_itself(repos):
    with pytest.raises(PeerSetRefused):
        set_industry_peers(repos, "banks", ids(9), "llm_suggested", True,
                           TODAY)


def test_empty_set_is_refused(repos):
    with pytest.raises(PeerSetRefused):
        set_industry_peers(repos, "banks", [], "manual", True, TODAY)


def test_cli_refuses_unknown_ticker_with_ready_command(tmp_path, capsys):
    root = str(tmp_path / "cli")
    assert cli_main(["--root", root, "init"]) == 0
    rc = cli_main(["--root", root, "peers", "set", "banks", "--tickers",
                   "NOPE", "--market", "US", "--origin", "manual"])
    assert rc == 1
    assert "rusterm add --ticker NOPE --market US" in capsys.readouterr().err


def test_cli_show_on_empty_base_names_the_command(tmp_path, capsys):
    root = str(tmp_path / "cli")
    assert cli_main(["--root", root, "init"]) == 0
    assert cli_main(["--root", root, "peers", "show"]) == 0
    assert "rusterm peers set" in capsys.readouterr().out
