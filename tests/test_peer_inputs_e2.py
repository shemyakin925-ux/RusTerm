"""ТЗ-94 E2: перцентили доходят до настоящего снапшота (координатор, 24.09).

Второй проход SnapshotBuilder считал перцентили ADR-0002 только в
тестах: ни один рабочий вызов не передавал ему набор аналогов. На базе
пользователя (44 бумаги, 5 наборов по 8–9) — 0 перцентилей. После
связки: 143 перцентиля со значением. Здесь — связка и команда целиком.
"""
from __future__ import annotations

from rusterm.cli import main as cli_main
from rusterm.core.peer_sets import peer_inputs
from rusterm.core.snapshot import SnapshotBuilder

from tests.test_currency_firewall import _six_issuer_set, env  # noqa: F401

AS_OF = "2024-12-31"


def test_peer_inputs_resolve_the_set_and_exclude_self(env):  # noqa: F811
    conn, repos = env
    _, _, ids = _six_issuer_set(repos, conn, None)
    version, measures = peer_inputs(repos, ids[0], AS_OF)
    assert version == "psv1"
    peers = {m[0] for m in measures}
    assert ids[0] not in peers and peers == set(ids[1:])
    assert all(m[2] != "percentile" for m in measures)


def test_instrument_outside_any_set_gets_no_peer_input(env):  # noqa: F811
    conn, repos = env
    assert peer_inputs(repos, "US-NOBODY", AS_OF) == (None, None)


def test_peer_inputs_feed_the_second_pass(env):  # noqa: F811
    conn, repos = env
    _, _, ids = _six_issuer_set(repos, conn, None)
    version, measures = peer_inputs(repos, ids[0], AS_OF)
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    result = builder.build(ids[0], "i0", AS_OF, peer_set_version=version,
                           peer_measures=measures)
    assert result.percentiles >= 1


def test_cli_snapshot_prints_real_percentiles(env, capsys):  # noqa: F811
    """Команда, а не функция: до связки печатала «перцентилей: 0»."""
    conn, repos = env
    _, _, ids = _six_issuer_set(repos, conn, None)
    root = str(repos.raw.paths.root)
    rc = cli_main(["--root", root, "snapshot", "--instrument", ids[0],
                   "--as-of", AS_OF])
    assert rc == 0
    line = next(l for l in capsys.readouterr().out.splitlines()
                if "перцентилей:" in l)
    count = int(line.split("перцентилей:")[1].split(",")[0].strip())
    assert count >= 1, line
