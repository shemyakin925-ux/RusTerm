"""ТЗ-104 P7: `rusterm snapshot --as-of X` собирает ОДНУ дату.

Было (дефект, решение координатора — ТЗ-104, пункт 16 «one as_of»):
`cmd_snapshot` пекла в фабрику построителя `args_as_of_default()` —
сегодня машины — и рядом считала вторую дату, `args.as_of or
args_as_of_default()`, для `build()`. Меры жили на запрошенной дате,
а пять строк governance — на дате фабрики: `--as-of 2026-09-12` давал
строки с `as_of` сегодняшнего дня, и окно сделок инсайдера (365 дней от
as_of) считалось от сегодня. Прошлая дата сборки собирала сегодняшние
сделки и наоборот.

Стало: одна дата, посчитанная один раз, доезжает и в фабрику, и в
`build()` (`rusterm/cli/__init__.py:969-985`).

| зуб | было | стало |
|---|---|---|
| `--as-of 2026-09-12` | 5 строк датированы сегодня | 5 строк датированы 12.09 (Done when) |
| сделка 2024-06-01, сбор `--as-of 2025-01-10` | «в окне нет сделок» | сделка в окне: `ownership_without_market_cap`, `transactions=1` |
| сделка 2026-08-20, сбор `--as-of 2025-01-10` | сделка посчитана | вне окна сборки: `no_deals_in_window` |
| сбор без `--as-of` | сегодня | сегодня же (ничего не сломано) |
| явный `--as-of` = сегодня против сборки по умолчанию | — | пять строк identical (стоп-кран) |
| набор аналогов (`peer_inputs`) | дата сборки | дата сборки — было верно и осталось |
| тело `cmd_snapshot` | две даты | одна: фабрика получает ту же переменную |
"""
import inspect
import sqlite3
from datetime import date
from pathlib import Path

from rusterm.cli import cmd_snapshot, main
from rusterm.parsers.ownership import OwnershipTransaction
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

CORE_ROOT = Path(__file__).resolve().parents[1]
_PAYLOAD = (CORE_ROOT / "tests" / "data" / "edgar" / "ownership"
            / "000114036126036226_form4.xml")

_PAST = "2026-09-12"


def _seed(tmp_path):
    """Каталог данных в tmp: один эмитент, один инструмент, канал
    владения обойдён (coverage ready) — так резолвер отличает
    «не собирали» от «собрали и не нашли в окне».
    """
    root = tmp_path / "data"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-p7", "Peaches Corp.", "US", "111111", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-P7", "i-p7", None, "common", "active", None))
    repos.coverage.upsert("US-P7", "ownership", "ready")
    return root, conn, repos


def _deal(repos, day):
    """Одна сделка инсайдера на указанную дату. Цен и капитализации нет
    нарочно: резолвер знаменатель видит первым, и рядом с сделкой без
    знаменателя ряд серый с именованной причиной — по ней и читается,
    попала сделка в окно или нет."""
    sha = repos.document.put(_PAYLOAD.read_bytes(), filename="form4.xml",
                             format="xml", page_count=1, byte_len=3153,
                             issuer_id="i-p7")
    repos.ownership.replace_for_document(sha, "i-p7", [
        OwnershipTransaction(insider="P. Each", role="officer",
                             officer_title="CFO", date=day,
                             direction="acquired", shares=100.0,
                             price=None, security="Common Stock"),
    ])


def _governance(root):
    conn = sqlite3.connect(f"file:{root / 'rusterm.db'}?mode=ro", uri=True)
    try:
        return conn.execute(
            """SELECT indicator, as_of, color, reason, lineage_ref
               FROM governance_assessment WHERE instrument_id='US-P7'
               ORDER BY indicator""").fetchall()
    finally:
        conn.close()


def _snapshot_as_of(root):
    conn = sqlite3.connect(f"file:{root / 'rusterm.db'}?mode=ro", uri=True)
    try:
        return [r[0] for r in conn.execute(
            "SELECT as_of FROM snapshot ORDER BY snapshot_id")]
    finally:
        conn.close()


def _rows_by_indicator(root):
    return {r[0]: r for r in _governance(root)}


def _cli(root, *extra):
    return main(["--root", str(root), "snapshot",
                 "--instrument", "US-P7", *extra])


# ── Done when: дата доходит до строк governance ────────────────────────
def test_requested_date_reaches_every_governance_row(tmp_path):
    """`--as-of 2026-09-12` → пять строк датированы 12.09, а не сегодня.
    Дефект был именно в этом: фабрика получала `args_as_of_default()`,
    и продюсер писал часы машины там, где пользователь просил прошлый
    день."""
    root, conn, _repos = _seed(tmp_path)
    conn.close()
    assert _cli(root, "--as-of", _PAST) == 0
    rows = _governance(root)
    assert len(rows) == 5, rows
    assert {r[1] for r in rows} == {_PAST}, rows
    # строка снапшота и строки оценок — одна дата: иначе «сборка на
    # 12.09» и «оценка на сегодня» живут в одном прогоне
    assert _snapshot_as_of(root) == [_PAST], _snapshot_as_of(root)


def test_default_build_is_still_today(tmp_path):
    """Без `--as-of` поведение не меняется: дата — сегодня. Зуб не даёт
    сузить правку до «всегда брать args.as_of, даже когда его нет»."""
    root, conn, _repos = _seed(tmp_path)
    conn.close()
    assert _cli(root) == 0
    today = date.today().isoformat()
    assert {r[1] for r in _governance(root)} == {today}
    assert _snapshot_as_of(root) == [today]


def test_explicit_today_is_indistinguishable_from_the_default(tmp_path):
    """Стоп-кран: явная `--as-of` = сегодня и сборка по умолчанию дают
    пять identical строк. Правка меняет только то, ЧТО за дата
    передаётся, а не то, как считается значение."""
    today = date.today().isoformat()
    root_a, conn, _repos = _seed(tmp_path / "a")
    conn.close()
    root_b, conn, _repos = _seed(tmp_path / "b")
    conn.close()
    assert _cli(root_a) == 0
    assert _cli(root_b, "--as-of", today) == 0
    assert _governance(root_a) == _governance(root_b)


# ── Окно сделок привязано к дате сборки, а не к часам ─────────────────
def test_the_insider_window_is_anchored_on_the_build_date(tmp_path):
    """Сделка 2024-06-01 входит в окно сборки `--as-of 2025-01-10` и не
    входит в окно сегодняшнего дня. Было: резолвер получил сегодняшнюю
    дату из фабрики и сказал «в окне нет сделок»; стало: сделка
    посчитана, и ряда нет по настоящей причине — нет знаменателя."""
    root, conn, repos = _seed(tmp_path)
    _deal(repos, "2024-06-01")
    conn.close()
    assert _cli(root, "--as-of", "2025-01-10") == 0
    row = _rows_by_indicator(root)["insider_net"]
    assert row[2] == "gray", row
    assert row[3] == "no_data:ownership_without_market_cap", row
    assert "transactions=1" in row[4], row


def test_a_deal_outside_the_requested_window_is_not_counted(tmp_path):
    """Вторая половина той же привязки: сделка 2026-08-20 сегодня в
    окне, а для сборки `--as-of 2025-01-10` — в будущем. Было: часы
    машины тянули её в ряд; стало: окно упирается в запрошенную дату,
    и причина — «нет сделок в окне»."""
    root, conn, repos = _seed(tmp_path)
    _deal(repos, "2026-08-20")
    conn.close()
    assert _cli(root, "--as-of", "2025-01-10") == 0
    row = _rows_by_indicator(root)["insider_net"]
    assert row[2] == "gray", row
    assert row[3] == "no_data:no_deals_in_window", row
    assert "transactions" not in row[4], row


# ── Форма правки: одна дата, посчитанная один раз ─────────────────────
def test_the_date_is_computed_once_and_shared(tmp_path):
    """`cmd_snapshot` обязан вычислить дату ДО фабрики и передать её и
    фабрике, и `build()`. Два вызова `args_as_of_default()` в команде —
    это два разных дня, если сборка пересекла полночь."""
    src = inspect.getsource(cmd_snapshot)
    assert "make_snapshot_builder(repos, as_of)" in src, src
    assert src.count("args_as_of_default()") == 1, src
    assert "builder.build(instrument_id, issuer_id, as_of)" in src, src


def test_the_peer_set_still_uses_the_build_date(tmp_path, monkeypatch):
    """Набор аналогов и так брал дату сборки (ТЗ-97 Q6, «дата набора
    берётся из as_of самой сборки»). Зуб не даёт правке P7 утащить эту
    дату обратно в фабрику: был зелёный до, зелёный после."""
    from rusterm.core import peer_sets

    seen = []
    original = peer_sets.peer_inputs

    def spy(repos_arg, instrument_id, date_value):
        seen.append(date_value)
        return original(repos_arg, instrument_id, date_value)

    monkeypatch.setattr(peer_sets, "peer_inputs", spy)
    root, conn, _repos = _seed(tmp_path)
    conn.close()
    assert _cli(root, "--as-of", _PAST) == 0
    assert seen, "peer_inputs не вызывался"
    assert set(seen) == {_PAST}, seen
