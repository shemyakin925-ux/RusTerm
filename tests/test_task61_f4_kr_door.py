"""ТЗ-61 F4: дверь KR без ключа — честная степень и честный отказ.

`RUSTERM_DART_KEY` на машине нет (измерено, принято координатором).
Пользователь должен видеть: степень KR — «нет ключа» (не обещание
мер); попытка сбора — отказ с причиной из словаря и строкой, где взять
ключ и в какую переменную положить; до сети дело не доходит вовсе.
"""
from __future__ import annotations

import json
import os
import sqlite3

import pytest

from rusterm.cli import main as cli_main
from rusterm.desktop import data as desktop_data
from rusterm.markets import channel_degree_label
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-krt", "Corp KR", "KR", None, None, "ifrs-full", "KRW"))
    repos.instrument.upsert_instrument(Instrument(
        "KR-KRT", "i-krt", None, "common", "active", None))
    yield repos, paths
    conn.close()


def _kr_degree(root, capsys) -> str:
    assert cli_main(["--root", str(root), "markets", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    return {row["code"]: row["degree"]
            for row in payload["markets"]}["KR"]


def test_markets_show_kr_as_no_key(catalog, tmp_path, capsys):
    """Каталог пуст, ключа нет: KR — «нет ключа», рынки с каналом — «—»."""
    assert _kr_degree(tmp_path / "app", capsys) == "нет ключа"


def test_degree_label_picks_by_key_presence():
    """Подстановка:-produced значение сильнее; канал без ключа даёт
    «нет ключа», тот же канал с ключом — честное «—»."""
    assert channel_degree_label(
        "dart", "сырьё", "RUSTERM_DART_KEY", False) == "сырьё"
    assert channel_degree_label(
        "dart", None, "RUSTERM_DART_KEY", False) == "нет ключа"
    assert channel_degree_label(
        "dart", "—", "RUSTERM_DART_KEY", False) == "нет ключа"
    assert channel_degree_label(
        "dart", None, "RUSTERM_DART_KEY", True) == "—"
    # канал, которому ключ не нужен, «нет ключа» не получает
    assert channel_degree_label(
        "asx", None, None, False) == "—"


def test_kr_ingest_refuses_with_instruction_and_no_network(
        catalog, tmp_path, monkeypatch, capsys):
    """Попытка сбора по KR без ключа: причина из словаря, строка
    называет сайт и переменную ПОДСТАНОВКОЙ из констант реестра;
    до сети дело не доходит (страж urlopen из conftest активен),
    фактов не появляется."""
    import rusterm.providers as providers_registry
    from rusterm.providers import dart as dart_module

    monkeypatch.setitem(providers_registry._CHANNEL_KEY_ENV,
                        "dart", "RUSTERM_DART_KEY_TEST")
    monkeypatch.setattr(dart_module, "KEY_SITE",
                        "https://example.invalid/get-key")
    code = cli_main(["--root", str(tmp_path / "app"), "ingest",
                     "--instrument", "KR-KRT"])
    err = capsys.readouterr().err
    assert code != 0
    assert "dart_key_unset" in err
    assert "RUSTERM_DART_KEY_TEST" in err, (
        "строка отказа несёт переменную подстановкой из реестра")
    assert "https://example.invalid/get-key" in err, (
        "строка отказа несёт сайт подстановкой из константы провайдера")
    # фактов нет: отказ не подменяется выдуманными данными
    assert repos_facts(catalog[0], "i-krt") == 0


def repos_facts(repos, issuer_id: str) -> int:
    return len(repos.fact.get_facts(issuer_id=issuer_id))


def test_desktop_names_kr_the_same_words(catalog, tmp_path, capsys):
    repos, _ = catalog
    assert desktop_data.channel_degrees(repos)["KR"] == "нет ключа"
    assert _kr_degree(tmp_path / "app", capsys) == "нет ключа"
