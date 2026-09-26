"""ТЗ-61 F2: три лица одной правды — export, tui/model, desktop.

Один эмитент, одна мера: значение совпадает во всех трёх лицах
(ячейка окна — в пределах правила отображения, pinned в F1), отказ
узнаётся по одному токену во всех трёх. Расхождение красит тест,
назвав все три значения. Прогон по трём рынкам: US, CA, BR. Если
какое-то лицо меру не показывает — тест красится на списке концептов:
умолчального пропуска не бывает.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,  # noqa: E402
                                 SnapshotRepo)
from rusterm.tui import model as tui_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

PLAN = {
    "US": ("i-us7", "US-A7", [("revenues_total", "100", "USD"),
                              ("ebitda_total", "1234.56789", "USD")]),
    "CA": ("i-ca7", "CA-C7", [("equity_total", "0.25", "CAD")]),
    "BR": ("i-br7", "BR-B7", [("gross_debt", "12.5", "BRL")]),
}
REFUSAL = ("CA", "CA-C7", "total_equity", "missing_data: total_equity")


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for market, (issuer_id, iid, measures) in PLAN.items():
        repos.instrument.upsert_issuer(Issuer(
            issuer_id, f"Corp {market}", market, None, None,
            "us-gaap" if market == "US" else "ifrs-full", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer_id, None, "common", "active", None))
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, "2025-01-01",
                                       None, None, "ready")
        for n, (concept, value, unit) in enumerate(measures):
            repos.snapshot.insert_measure(
                f"m-{iid}-{n}", f"s-{iid}", "issuer", issuer_id, concept,
                value, unit, "2024-01-01", "2024-12-31", None,
                "t61-test", None, None)
    _market, iid, concept, reason = REFUSAL
    repos.snapshot.insert_measure(
        f"m-{iid}-ref", f"s-{iid}", "issuer", "i-ca7", concept,
        None, "CAD", "2024-01-01", "2024-12-31", None, "t61-test",
        reason, None)
    yield repos, paths
    conn.close()


def _export_face(root: Path, iid: str) -> dict:
    env = dict(os.environ, RUSTERM_ENV_FILE=str(root / "empty.env"))
    proc = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(root),
         "export", "--instrument", iid, "--format", "json"],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return {m["concept"]: m
            for m in json.loads(proc.stdout)["measures"]}


def _token(null_reason) -> str:
    return (null_reason or "").split(":", 1)[0]


def test_three_faces_agree(catalog, tmp_path):
    repos, paths = catalog
    for market, (issuer_id, iid, _measures) in PLAN.items():
        exported = _export_face(tmp_path / "app", iid)
        model = {m["concept"]: m
                 for m in tui_model.card_rows(repos, iid)["measures"]}
        table = desktop_data.measure_table_rows(repos, iid)
        desktop = {r["concept"]: r for r in table["measures"]}
        # никакое лицо не теряет меры молча
        assert set(exported) == set(model) == set(desktop), (
            f"{market}: лица показывают разные списки мер: "
            f"export={sorted(exported)} model={sorted(model)} "
            f"desktop={sorted(desktop)}")
        for concept in exported:
            exp, mod, dsk = (exported[concept], model[concept],
                             desktop[concept])
            period = exp["period_end"]
            assert mod["period"] == period, (
                market, concept, "model", mod["period"], period)
            assert dsk["measure"].get("period") == period, (
                market, concept, "desktop",
                dsk["measure"].get("period"), period)
            if exp["value"] is None:
                # отказ — один токен во всех лицах, слова разными быть
                # не должны и токен обязан совпадать
                token = _token(exp["null_reason"])
                assert _token(mod["null_reason"]) == token, (
                    market, concept, "model", mod["null_reason"], token)
                assert _token(dsk["null_reason"]) == token, (
                    market, concept, "desktop", dsk["null_reason"], token)
                assert mod["value"] == tui_model.NULL_MARK
                assert dsk["current"] == desktop_data.NO_DATA
                continue
            # модель = экспорт байт-в-байт
            assert mod["value"] == exp["value"], (
                f"{market} {concept}: model {mod['value']!r} != "
                f"export {exp['value']!r}")
            # ячейка окна: экспорт или его format_value (правило F1)
            if dsk["current"] != exp["value"]:
                assert dsk["current"] == desktop_data.format_value(
                    exp["value"]), (
                    f"{market} {concept}: desktop {dsk['current']!r} != "
                    f"export {exp['value']!r} и != format_value")


def test_refusal_token_named_across_faces(catalog, tmp_path):
    """Отказ total_equity: один токен в export, модели и окне."""
    repos, paths = catalog
    _market, iid, concept, reason = REFUSAL
    token = _token(reason)
    exported = _export_face(tmp_path / "app", iid)[concept]
    model = next(m for m in tui_model.card_rows(repos, iid)["measures"]
                 if m["concept"] == concept)
    dsk = next(r for r in desktop_data.measure_table_rows(
        repos, iid)["measures"] if r["concept"] == concept)
    assert _token(exported["null_reason"]) == token
    assert _token(model["null_reason"]) == token
    assert _token(dsk["null_reason"]) == token
    assert model["value"] == tui_model.NULL_MARK
    assert dsk["current"] == desktop_data.NO_DATA
