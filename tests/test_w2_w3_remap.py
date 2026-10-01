"""ТЗ-108 W2/W3: теги долга SMCI и вложений CRM в карте us-gaap.v5, и
`reparse` дописывает каноническое имя уже сохранённым фактам — только
тем, у кого его не было."""
from __future__ import annotations

import sqlite3

from rusterm.cli import fill_canonical_from_map
from rusterm.normalize.concepts import CONCEPT_MAP_VERSION, canonical_for
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Issuer, RepoRegistry


def test_v5_maps_successor_tags():
    assert CONCEPT_MAP_VERSION == "us-gaap.v5"
    assert canonical_for("DebtLongtermAndShorttermCombinedAmount") \
        == "total_debt"
    assert canonical_for("AvailableForSaleSecuritiesDebtSecuritiesCurrent") \
        == "st_investments"
    # прежние теги на месте и первыми
    assert canonical_for("LongTermDebt") == "total_debt"


def test_fill_canonical_only_where_missing(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer("i-S", "S", "US", "1", None,
                                          "us-gaap", "USD"))
    common = dict(issuer_id="i-S", listing_id=None, period_start="2026-06-30",
                  period_end="2026-06-30", period_type="instant",
                  unit="USD", currency="USD", basis="as_reported",
                  origin="extracted", source_ref="sha", locator={},
                  parser_version="t", status="ok")
    repos.fact.insert_fact(fact_id="f-new",
                           concept="us-gaap:DebtLongtermAndShorttermCombinedAmount",
                           value="4056148000", **common)
    repos.fact.insert_fact(fact_id="f-old", concept="us-gaap:LongTermDebt",
                           value="1", canonical_concept="other_concept",
                           concept_map_version="us-gaap.v1", **common)
    assert fill_canonical_from_map(repos) == 1
    new = repos.fact.get_fact("f-new")
    assert new["canonical_concept"] == "total_debt"
    assert new["concept_map_version"] == "us-gaap.v5"
    assert new["value"] == "4056148000"
    old = repos.fact.get_fact("f-old")
    assert old["canonical_concept"] == "other_concept"   # не переназначен
    assert fill_canonical_from_map(repos) == 0           # идемпотентно
