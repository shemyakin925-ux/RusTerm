"""ТЗ-97 Q2 (ТЗ-73 T3, правило P8): серый ряд governance — со словами
причины и с командой, которой он закрывается.

Что проверяется и почему именно это:
- словарь причин покрывает ВСЕ токены, которые ядро само и печатает —
  разбор исходника `rusterm/core/governance.py` через `ast`, потому что
  на живой базе пользователя все пять строк показали код вместо слов
  (`no_data:not_collected` не совпадал с ключом `not_collected`);
- причины с префиксами (`no_data:`, `stale:`, `...:3y`) переводятся,
  незнакомый токен называется словами, а не оставляется пустым;
- у каждого серого ряда есть дверь — строка, которую принимает парсер
  CLI, а не описание проблемы;
- `insider_net` честно различает «канал не обошёл» и «канал обошёл и
  не нашёл» — раньше и то, и другое было `not_collected`;
- цвет появляется, когда у индикатора есть знаменатель: тот же wiring,
  что ставит фабрика построителя снапшота.

Qt здесь не нужен: окно проверяет
`tests/test_desktop_task96_r4_firsthour.py`, этот файл — ядро.
"""
from __future__ import annotations

import ast
import os
import sqlite3
from pathlib import Path

import pytest

from rusterm.cli import _build_parser
from rusterm.core.governance import (GREY_REASONS, INDICATORS,
                                     governance_inputs_from_records,
                                     grey_closing, grey_reason_key,
                                     grey_reason_text,
                                     insider_net_inputs_from_store,
                                     produce_assessments)
from rusterm.parsers.ownership import OwnershipTransaction
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry)

CORE_SOURCE = (Path(__file__).resolve().parents[1]
               / "rusterm" / "core" / "governance.py")
_PAYLOAD_DIR = (Path(__file__).resolve().parents[1] / "tests" / "data"
                / "edgar" / "ownership")


def _env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-q2", "Apple Inc.", "US", "320193", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-Q2", "i-q2", None, "common", "active", None))
    return conn, repos


def _stored_deals(repos):
    """Две сделки через тот же репозиторий, что пишет сборщик:
    куплено 200, продано 500 — числитель -300 акций."""
    sha = repos.document.put(
        (_PAYLOAD_DIR / "000114036126036226_form4.xml").read_bytes(),
        filename="form4.xml", format="xml", page_count=1, byte_len=3153,
        issuer_id="i-q2")
    repos.ownership.replace_for_document(sha, "i-q2", [
        OwnershipTransaction(insider="A", role="officer",
                             officer_title=None, date="2026-09-01",
                             direction="acquired", shares=200.0,
                             price=None, security="Common Stock"),
        OwnershipTransaction(insider="B", role="director",
                             officer_title=None, date="2026-08-20",
                             direction="disposed", shares=500.0,
                             price=300.0, security="Common Stock",
                             tenb5_one=True),
    ])
    return sha


def _snapshot_with_market_cap(repos):
    """Снапшот, у которого `market_cap_total` посчитан — знаменатель
    формулы словаря. Значение — строка-запись, как его пишет снапшот.

    ТЗ-104 P6: рядом кладутся и котировки на даты обеих сделок. С
    денежным числителем знаменатель больше не единственный вход: без
    close за дату сделки ряд право становится серым, а этим тестам нужен
    посчитанный цвет."""
    repos.snapshot.create_snapshot("s-q2", "US-Q2", 1, "2026-09-13",
                                   None, "none", "ready")
    repos.snapshot.add_block("s-q2", "fundamentals", "ready", None)
    repos.snapshot.insert_measure(
        "m-mcap-q2", "s-q2", "issuer", "i-q2", "market_cap_total",
        "1000000.0", "USD", "2026-09-13", "2026-09-13",
        "market_cap_total", "v1", None, None)
    repos.price.put_rows("US-Q2", "twelvedata", [
        {"date": "2026-09-01", "close": 100.0, "adjusted": 100.0,
         "currency": "USD"},
        {"date": "2026-08-20", "close": 200.0, "adjusted": 200.0,
         "currency": "USD"},
    ])


def _tokens_the_core_emits() -> set[str]:
    """Все токены серости из исходника: последние аргументы `_gray(...)`
    и значения `"gray": ...` в спеках сборщиков. Литерал и первая часть
    f-строки; `{...}` в конце отрезается — словарь живёт голыми именами.

   Сама `_gray` в обходе пропускается: она добавляет префикс `no_data:`,
    а токен даёт её вызывающий — иначе «токеном» стал бы сам префикс.
    """
    tree = ast.parse(CORE_SOURCE.read_text(encoding="utf-8"))
    found: set[str] = set()

    def add(value):
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            found.add(value.value)
        elif isinstance(value, ast.JoinedStr):
            first = value.values[0]
            if isinstance(first, ast.Constant) and isinstance(
                    first.value, str):
                found.add(first.value.rstrip(":"))

    def scan(node):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("_gray", "_assess")):
            args = list(node.args)
            if node.func.id == "_gray" and args:
                add(args[-1])
            elif node.func.id == "_assess" and len(args) >= 6:
                # _assess(..., color, reason): причина — последняя, и
                # только когда цвет буквально "gray"
                if (isinstance(args[4], ast.Constant)
                        and args[4].value == "gray"):
                    add(args[5])
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "gray":
                    add(value)
        for child in ast.iter_child_nodes(node):
            scan(child)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_gray":
            continue
        scan(node)
    return {t for t in found if t and not t.startswith("no_data:")}


def test_every_grey_token_the_core_emits_has_words():
    """Ни один токен, который ядро способно записать, не имеет права
    остаться без слов — иначе вкладка показывает код."""
    tokens = _tokens_the_core_emits()
    assert tokens, "разбор исходника ничего не нашёл — проверка пустая"
    missing = {t for t in tokens if grey_reason_key(t) not in GREY_REASONS}
    assert not missing, f"токены без слов в GREY_REASONS: {missing}"


def test_prefixed_reasons_resolve_to_words_not_codes():
    """Ядро пишет причины с префиксами; словарь живёт голыми именами.
    Без разбора на живой базе все пять строк показали бы код."""
    assert grey_reason_key("no_data:not_collected") == "not_collected"
    assert grey_reason_key("stale:assessed:2025-01-15") == "stale"
    assert grey_reason_key(
        "no_data:disclosure_window_short:3y") == "disclosure_window_short"
    for reason in ("no_data:not_collected", "stale:assessed:2025-01-15",
                   "no_data:disclosure_window_short:3y",
                   "no_data:ownership_without_market_cap"):
        words = grey_reason_text(reason)
        assert words and words == grey_reason_text(grey_reason_key(reason))
        assert "не описана" not in words, reason


def test_unknown_token_is_named_rather_than_left_blank():
    """Неизвестная причина — это тоже слова, а не пустая ячейка (P8)."""
    words = grey_reason_text("no_data:never_seen_before")
    assert "never_seen_before" in words
    assert "не описана" in words


def test_every_grey_row_after_an_uncharted_run_has_words_and_a_door(
        tmp_path):
    """Ни одного входа нет -> пять серых рядов, и каждое показание
    называет причину словами и команду одной строкой."""
    conn, repos = _env(tmp_path)
    produced = produce_assessments(repos.governance, "US-Q2", "2026-09-13",
                                   None)
    assert len(produced) == len(INDICATORS) == 5
    for a in produced:
        assert a.color == "gray"
        words = grey_reason_text(a.reason)
        assert words and "не описана" not in words, a.reason
        door = grey_closing(a.indicator, "US-Q2")
        assert door.startswith("rusterm "), door
        argv = door.split()
        assert "US-Q2" in argv, f"дверь не называет бумагу: {door}"
        parsed = _build_parser().parse_args(argv[1:])
        assert parsed.command == argv[1], door
    conn.close()


def test_doors_are_the_channels_that_actually_fill_the_indicator(
        tmp_path):
    """Владение закрывается каналом Forms 3/4/5, остальное — ручным
    импортом документа: у двери и индикатора один канал."""
    door = grey_closing("insider_net", "US-Q2")
    argv = _build_parser().parse_args(door.split()[1:])
    assert (argv.command, argv.source, argv.instrument) == (
        "ingest", "ownership", "US-Q2")
    for indicator in ("independent_directors", "ceo_chair",
                      "related_party", "auditor"):
        argv = _build_parser().parse_args(
            grey_closing(indicator, "US-Q2").split()[1:])
        assert argv.command == "import", indicator
        assert argv.issuer == "US-Q2", indicator
        assert argv.market is None, (
            f"--issuer без --market значит instrument_id: {indicator}")


def test_unknown_indicator_still_gets_a_executable_door(tmp_path):
    """Аварийный ряд (индикатора нет в карте) не имеет права дать пустую
    ячейку: возвращается команда просмотра покрытия."""
    door = grey_closing("brand_new_indicator", "US-Q2")
    argv = _build_parser().parse_args(door.split()[1:])
    assert argv.command == "coverage" and argv.instrument == "US-Q2"


def test_insider_gray_reason_distinguishes_walked_from_unwalked(tmp_path):
    """«Канал не обошли» и «обошли и не нашли» — разные слова. Раньше
    оба были `not_collected`, и вкладка врала о уже пройденной стадии."""
    conn, repos = _env(tmp_path)
    # покрытия нет вовсе — стадия не ходила: входа нет, продюсер сам
    # скажет not_collected
    assert insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                         "2026-09-13") == {}
    # обошли, форм нет -> источник не раскрывает
    repos.coverage.upsert("US-Q2", "ownership", "missing",
                          reason="source_has_no_disclosure")
    spec = insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                         "2026-09-13")
    assert spec["insider_net"]["gray"] == "source_has_no_disclosure"
    assert "coverage:ownership=missing" in spec["insider_net"]["lineage_ref"]
    # обошли, формы есть, но сделок в окне нет
    repos.coverage.upsert("US-Q2", "ownership", "ready", reason=None)
    spec = insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                         "2026-09-13")
    assert spec["insider_net"]["gray"] == "no_deals_in_window"
    conn.close()


def test_collector_gray_spec_is_recorded_with_its_own_lineage(tmp_path):
    """Продюсер обязан записать токен и lineage сборщика, а не
    перерисовать их в not_collected: именно lineage несёт число сделок."""
    conn, repos = _env(tmp_path)
    _stored_deals(repos)          # сделки есть, снапшота нет
    spec = insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                         "2026-09-13")
    assert spec["insider_net"]["gray"] == "ownership_without_market_cap"
    produced = produce_assessments(repos.governance, "US-Q2", "2026-09-13",
                                   spec)
    insider = [a for a in produced if a.indicator == "insider_net"][0]
    assert insider.color == "gray"
    assert insider.reason == "no_data:ownership_without_market_cap"
    assert "transactions=2" in insider.lineage_ref
    assert "not-collected" not in insider.lineage_ref
    # остальные четыре ряда при этом не притворяются посчитанными
    others = {a.indicator: a for a in produced
              if a.indicator != "insider_net"}
    assert {a.color for a in others.values()} == {"gray"}
    assert {a.reason for a in others.values()} == {"no_data:not_collected"}
    conn.close()


def test_insider_net_gets_a_measured_colour_once_the_denominator_exists(
        tmp_path):
    """ТЗ-73 T3: после сбора канала хотя бы один показатель перестаёт
    быть серым. Wiring — тот же, что у фабрики построителя снапшота."""
    conn, repos = _env(tmp_path)
    _stored_deals(repos)
    _snapshot_with_market_cap(repos)
    inputs = {**governance_inputs_from_records(repos.manual_extraction,
                                               "i-q2"),
              **insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                              "2026-09-13")}
    assert "gray" not in inputs["insider_net"], inputs["insider_net"]
    produced = produce_assessments(repos.governance, "US-Q2", "2026-09-13",
                                   inputs)
    insider = [a for a in produced if a.indicator == "insider_net"][0]
    # ТЗ-104 P6: те же сделки, посчитанные в деньгах (200×100 против
    # 500×200 при капитализации 1 000 000) — это продажа 8%
    # капитализации, то есть красный. Жёлтым ряд делало именно
    # безразмерное отношение акций к долларам (-300/1e6).
    assert insider.color == "red", (insider.color, insider.reason)
    assert insider.color != "gray"
    assert "buys=20000,sells=100000,net=-80000" in insider.lineage_ref
    colours = {a.indicator: a.color for a in produced}
    # свёртки нет: посчитанный ряд не перекрашивает остальные
    assert colours["insider_net"] != "gray"
    assert all(colours[k] == "gray" for k in
               ("independent_directors", "ceo_chair", "related_party",
                "auditor")), colours
    stored = repos.governance.latest("US-Q2", "insider_net")
    assert stored["color"] == "red", dict(stored)
    assert stored["method_version"] == "governance.v2", dict(stored)
    conn.close()


def test_grey_rows_carry_words_and_measured_rows_carry_a_door(tmp_path):
    """Слой данных окна: у серого ряда — слово причины, у каждого ряда —
    дверь. Пустой ячейки расшифровки рядом с gray слой выдать не может."""
    from rusterm.desktop import data as desktop_data
    conn, repos = _env(tmp_path)
    _stored_deals(repos)
    _snapshot_with_market_cap(repos)
    produced = produce_assessments(repos.governance, "US-Q2", "2026-09-13", {
        **governance_inputs_from_records(repos.manual_extraction, "i-q2"),
        **insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                        "2026-09-13")})
    card = {"instrument_id": "US-Q2",
            "governance": [{"indicator": a.indicator, "color": a.color,
                            "reason": a.reason,
                            "lineage_ref": a.lineage_ref}
                           for a in produced]}
    by_indicator = {r["indicator"]: r
                    for r in desktop_data.governance_view(card)["rows"]}
    # ТЗ-104 P6: ряд посчитан в деньгах — при этих котировках это
    # красный; для теста важно, что цвет измеримый, а не серый
    assert by_indicator["insider_net"]["color"] == "red"
    assert by_indicator["insider_net"]["closing"] == (
        "rusterm ingest --source ownership --instrument US-Q2")
    for indicator, row in by_indicator.items():
        assert row["closing"], f"{indicator}: пустая дверь"
        if row["color"] == "gray":
            assert row["note"], f"{indicator}: пустая расшифровка"
            assert "не описана" not in row["note"], row["note"]
    # вкладка не просит общую подсказку, когда хоть один ряд посчитан
    assert not desktop_data.governance_needs_hint(
        desktop_data.governance_view(card))
    conn.close()


# ── живой зуб: обычный путь красит `insider_net` (первый абзац Q2) ──────

def _live_env() -> dict | None:
    """Оба контакта нужны: SEC для форм владения, Twelve Data для
    котировки, от которой считается знаменатель. Нет одного — пропуск,
    а не подделка числа (правило N7).

    `conftest._isolated_rusterm_env` вычищает RUSTERM_* и ставит
    RUSTERM_ENV_FILE на пустой файл для всякого теста, живого тоже,
    поэтому решение принимается по настоящему ~/.rusterm.env: читаются
    только ИМЕНА (значения наружу не идут), а дочернему CLI путь
    подменяется обратно на домашний файл — сам он его и загрузит.
    """
    from rusterm import env as env_module

    home_file = Path.home() / ".rusterm.env"
    if not home_file.exists():
        return None
    names = set(env_module.parse_env_file(
        home_file.read_text(encoding="utf-8")))
    if not {"RUSTERM_SEC_UA", "RUSTERM_TWELVEDATA_KEY"} <= names:
        return None
    child = os.environ.copy()
    child.pop("RUSTERM_ENV_FILE", None)
    return child


@pytest.mark.integration
@pytest.mark.live
def test_live_usual_path_gives_insider_net_a_measured_colour(tmp_path):
    """ТЗ-97 Q2: «после обычного пути `rusterm follow AAPL` у AAPL как
    минимум `insider_net` обязан стать жёлтым или зелёным (не серым) с
    посчитанным lineage — на копии каталога в /tmp, не на базе
    пользователя». База здесь — `tmp_path`, сеть живая, бюджет пункта
    (до 40 запросов) замерен отдельно и назван в отчёте."""
    import subprocess
    import sys

    base = _live_env()
    if base is None:
        pytest.skip("SEC_UA или TWELVEDATA_KEY не заданы — живой путь не проверен")
    root = str(tmp_path / "catalog")
    env = {**base,
           "PYTHONPATH": os.pathsep.join(
               [str(Path(__file__).resolve().parents[1]),
                os.environ.get("PYTHONPATH", "")])}

    def run(*argv):
        return subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root, *argv],
            capture_output=True, text=True, env=env)

    assert run("init").returncode == 0
    follow = run("follow", "AAPL")
    assert follow.returncode == 0, follow.stdout + follow.stderr
    assert "6/6 снапшот — готово" in follow.stdout, follow.stdout
    assert "4/6 формы владения — готово" in follow.stdout, follow.stdout

    con = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                          uri=True)
    row = con.execute(
        "select color, reason, lineage_ref from governance_assessment "
        "where instrument_id='US-AAPL' and indicator='insider_net' "
        "order by as_of desc limit 1").fetchone()
    deals = con.execute(
        "select count(*) from ownership_transaction").fetchone()[0]
    con.close()
    assert row is not None, "обычный путь не оставил строку insider_net"
    color, reason, lineage = row
    assert color in ("green", "yellow", "red"), (
        f"путь пройден, а цвет остался {color} при причине {reason}")
    assert lineage.startswith("ownership:buys="), lineage
    assert "net=" in lineage and "window=365d" in lineage, lineage
    assert deals > 0, "форма владения прошла, а сделок в базе нет"


# ── ТЗ-97 Q2: порядок сборки — цвет не отстаёт на прогон ────────────────

SNAPSHOT_SOURCE = (Path(__file__).resolve().parents[1]
                   / "rusterm" / "core" / "snapshot.py").read_text(
    encoding="utf-8")


def test_the_denominator_comes_from_the_snapshot_being_built(tmp_path):
    """«Цвета могут отставать на один прогон — это проверяется, а не
    декларируется» (ТЗ-97 Q2). Живой путь на пустом каталоге это
    отставание показал: в момент сборки строка версии ещё `building`,
    а `latest_snapshot_id` прячет её от читателя (ТЗ-90 A3), поэтому
    первый же `follow` оставлял `insider_net` серым с
    `ownership_without_market_cap`. Зуб ровняет два вызова резолвера на
    одном и том же состоянии базы: без знака сборки — честный серый, со
    знаком — посчитанная доля тех же сделок на тот же знаменатель."""
    conn, repos = _env(tmp_path)
    _stored_deals(repos)
    repos.snapshot.create_snapshot("s-building", "US-Q2", 1, "2026-09-13",
                                   None, "none", "building")
    repos.snapshot.insert_measure(
        "m-mcap-building", "s-building", "issuer", "i-q2",
        "market_cap_total", "1000000.0", "USD", "2026-09-13", "2026-09-13",
        "market_cap_total", "v1", None, None)
    assert repos.snapshot.latest_snapshot_id("US-Q2") is None, (
        "готового снапшота нет — то самое состояние первого прогона")
    # ТЗ-104 P6: денежному числителю нужны котировки на даты сделок —
    # тот же вход, что резолвер видит внутри сборки
    repos.price.put_rows("US-Q2", "twelvedata", [
        {"date": "2026-09-01", "close": 100.0, "adjusted": 100.0,
         "currency": "USD"},
        {"date": "2026-08-20", "close": 200.0, "adjusted": 200.0,
         "currency": "USD"},
    ])

    lagging = insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                           "2026-09-13")
    assert lagging["insider_net"]["gray"] == "ownership_without_market_cap"

    inside = insider_net_inputs_from_store(repos, "US-Q2", "i-q2",
                                          "2026-09-13", "s-building")
    inputs = inside["insider_net"]["inputs"]
    assert inputs["net_value"] == -80_000.0
    assert inputs["net_ratio"] == -80_000.0 / 1_000_000.0
    assert "gray" not in inside["insider_net"], inside
    conn.close()


def test_the_builder_calls_governance_after_the_valuation_pass():
    """Тот же порядок закреплён в исходнике сборки: резолвер governance
    вызывается ПОСЛЕ оценочного прохода и получает id собираемого
    снапшота. Иначе зуб выше — про договорёжность, а не про код."""
    tree = ast.parse(SNAPSHOT_SOURCE)
    host = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for inner in ast.walk(node):
            if (isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "_governance"):
                host = node
    assert host is not None, "метод, зовущий self._governance, не найден"
    valuation = None
    governance = None
    for node in ast.walk(host):
        if isinstance(node, ast.Call) and isinstance(node.func,
                                                    ast.Attribute):
            attr = node.func.attr
            if attr == "_valuation_pass":
                valuation = node
            elif attr == "_governance":
                governance = node
    assert valuation is not None and governance is not None
    assert governance.lineno > valuation.lineno, (
        "governance вызывается до оценочного прохода — знаменателя ещё нет")
    passed = ast.dump(governance.args[-1])
    assert "id='snapshot_id'" in passed, (
        "резолвер не получает собираемый снапшот: цвет отстаёт на прогон")
