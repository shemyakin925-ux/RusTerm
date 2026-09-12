"""ТЗ-21 H5: путь отказа — полноценный путь, один сквозной тест.

add эмитента, которого нельзя скачать, -> manual_import_required с
ТОЧНОЙ командой ручного импорта -> эмитент создаётся явно (офлайн) ->
команда импорта выполняется -> факты с source_kind='manual' лежат,
непроверённые в формулы не попадают. Всё офлайн: модель — подстава,
сети нет.
"""
from __future__ import annotations

import json
import re
import sqlite3

import pytest

import rusterm.cli as cli
from rusterm.providers.base import ProviderError
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir


class RefusingProvider:
    """Эмитент известен рынку, но раскрытия машинно недоступны."""

    def resolve(self, ticker, market, as_of):
        return {"ticker": ticker.upper(), "cik": 1234567,
                "title": "Refusal Co"}

    def ticker_venues(self):
        return {}

    def can_auto_ingest(self, identifier):
        return False


class FakeLlm:
    model = "fake-model"

    def complete(self, prompt):
        return json.dumps([
            {"company": "Refusal Co", "category": "physical",
             "metric": "fleet_size", "value": "42", "unit": "ships",
             "period": "FY2025",
             "quote": "the fleet comprised 42 ships at year end",
             "page_no": 1},
            {"company": "Refusal Co", "category": "physical",
             "metric": "crew", "value": "33", "unit": "people",
             "period": "FY2025",
             "quote": "the fleet comprised 42 ships at year end",
             "page_no": 1},
        ])


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test h5.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(tmp_path / "no.env"))
    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    conn.close()
    return root, paths, tmp_path


def _issuer_count(paths) -> int:
    conn = sqlite3.connect(str(paths.db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM issuer").fetchone()[0]
    finally:
        conn.close()


def test_refusal_path_is_first_class(app, tmp_path, monkeypatch, capsys):
    root, paths, scratch = app

    # 1. add: эмитент известен, раскрытия недоступны -> отказ по имени
    monkeypatch.setattr(cli, "get_provider",
                        lambda name, gate=None: RefusingProvider())
    code = cli.main(["--root", str(root), "add", "--ticker", "XYZ",
                     "--market", "US"])
    capsys.readouterr()
    assert code == 0
    assert _issuer_count(paths) == 0  # ноль строк, счётом

    # 2. отказ назвал точную команду; достаём её из вывода отказа
    #    (повторяем отказ, чтобы прочитать текст)
    monkeypatch.setattr(cli, "get_provider",
                        lambda name, gate=None: RefusingProvider())
    cli.main(["--root", str(root), "add", "--ticker", "XYZ",
              "--market", "US"])
    out = capsys.readouterr().out
    match = re.search(r"rusterm import <файл> --issuer \S+ "
                      r"--market \S+", out)
    assert match, out
    command = match.group(0)

    # 3. пользователь создаёт эмитента явно (офлайн, --cik/--name)
    monkeypatch.setattr(cli, "get_provider",
                        lambda name, gate=None: RefusingProvider())
    code = cli.main(["--root", str(root), "add", "--ticker", "XYZ",
                     "--market", "US", "--cik", "1234567",
                     "--name", "Refusal Co"])
    capsys.readouterr()
    assert code == 0
    assert _issuer_count(paths) == 1

    # 4. названная команда выполняется (файл пользователя, модель-подстава)
    doc = scratch / "annual.txt"
    doc.write_text("the fleet comprised 42 ships at year end\n",
                   encoding="utf-8")
    tokens = command.replace("<файл>", str(doc)).split()
    monkeypatch.setattr(
        "rusterm.providers.llm_api.LlmApiClient.from_env",
        classmethod(lambda cls, gate, environ=None: FakeLlm()))
    code = cli.main(["--root", str(root)] + tokens[1:])
    assert code == 0
    capsys.readouterr()

    # 5. факты с source_kind='manual' лежат (непусто), непроверённая
    #    запись факта не получила
    conn = sqlite3.connect(str(paths.db_path))
    try:
        manual_facts = conn.execute(
            """SELECT COUNT(*) FROM fact WHERE source_kind='manual'
               AND concept='fleet_size'""").fetchone()[0]
        assert manual_facts == 1
        unverified_fact = conn.execute(
            """SELECT COUNT(*) FROM fact f
               JOIN manual_extraction e ON e.metric = f.concept
               WHERE e.verified = 0 AND f.concept = 'crew'""").fetchone()[0]
        assert unverified_fact == 0
        marked = conn.execute(
            "SELECT COUNT(*) FROM manual_extraction WHERE verified=0"
        ).fetchone()[0]
        assert marked == 1
    finally:
        conn.close()

    # 6. снапшот собирается; непроверённой метрики в мерах нет
    from rusterm.core.snapshot import SnapshotBuilder
    from rusterm.store.repos import RepoRegistry
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    repos = RepoRegistry(conn, paths)
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    builder.build("US-XYZ", "cik-1234567", "2025-12-31")
    measures = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-XYZ"))
    concepts_with_value = {m[3] for m in measures if m[4] is not None}
    assert "crew" not in concepts_with_value
    conn.close()
