"""ТЗ-97 Q12 (вердикт 5, вариант 1): отказ корпоративных действий по
тарифу — стадия пройдена, а не путь оборван.

Замерено в поле (REPORT-96, Disputed 5, Runs 24/30): пять из шести бумаг
записали котировки (5000 строк, KSPI 672), после чего `rusterm follow`
остановился с rc=1 и без снапшота, потому что `/splits` ответил 403.
Напечатанный совет — `rusterm ingest --source twelvedata --instrument
US-ADBE` — ведёт в ту же стену: под канонический URL кешируются только
успешные payload'ы, поэтому повтор заново платит запрос `/splits` и
получает то же сообщение о тарифе, детерминированно, пока ключ на этом
тарифе.

Что закреплено здесь:
- отказ по тарифу не топит стадию котировок и не отменяет снапшот;
- причина названа словами, а не кодом возврата;
- то, что ответило, записывается (один отказанный эндпоинт не отменяет
  второй);
- снисходительность — только к тарифу: транспорт, 429, 5xx и отсутствующий
  тикер по-прежнему отказ;
- отказа, который нельзя обойти повтором, в выводе не остаётся.

Офлайн: те же настоящие классы провайдеров с транспортом на записанных
ответах, дверь одна — `cli.get_provider` (стиль `test_task96_r2_follow`).
Каталог — `tmp_path`, сеть не трогается (P7, страж `test_no_shared_tmp`).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.cli import _build_parser
from rusterm.providers.edgar import EdgarProvider
from rusterm.providers.twelvedata import TwelveDataProvider
from tests.edgar_fixtures import ownership_body

REPO = Path(__file__).resolve().parents[1]
TICKERS = REPO / "tests/data/edgar/company_tickers.json"
FACTS = REPO / "tests/data/edgar/companyfacts_m3_AAPL.json"
SUBS = REPO / "tests/data/edgar/submissions_aapl.json"
TIMES = REPO / "tests/data/twelvedata/time_series_AAPL_1day_trimmed.json"
SPLITS = REPO / "tests/data/twelvedata/splits_AAPL_full.json"
DIVS = REPO / "tests/data/twelvedata/dividends_AAPL_full.json"

NOTE = "недоступны на бесплатном тарифе Twelve Data (ADR-0018)"
# 403 — то, чем бесплатный тариф Twelve Data отвечает на /splits и
# /dividends (замер в поле: REPORT-96 Runs 24).
PLAN_403 = (403, b'{"status": "error", "code": 403, "message": '
            b'"This endpoint is available to professional plan"}', {})


def _edgar_transport(url, headers):
    if "company_tickers" in url:
        return 200, TICKERS.read_bytes(), {}
    if "companyfacts" in url:
        return 200, FACTS.read_bytes(), {}
    if "submissions" in url:
        return 200, SUBS.read_bytes(), {}
    if "/Archives/edgar/data/" in url:
        # ТЗ-97 Q2: стадии 4/6 нужны тела Forms 3/4/5 — этот файл
        # проверяет отказ по котировкам, а не по владению.
        body = ownership_body(url)
        return (200, body, {}) if body is not None \
            else (404, b'{"ok": false}', {})
    return 404, b'{"ok": false}', {}


def _twelvedata_transport(splits=PLAN_403, dividends=PLAN_403,
                          calls=None):
    """Котировки всегда успешны — их тариф не отменяет; корпоративные
    действия отвечают тем, что попросили. `calls` — список, куда
    пишется каждое обращение к транспорту (зубы на счётчик запросов)."""
    def transport(url, headers):
        if "time_series" in url:
            kind = "time_series"
        elif "/splits" in url:
            kind = "splits"
        elif "/dividends" in url:
            kind = "dividends"
        else:
            kind = "unknown"
        if calls is not None:
            calls.append(kind)
        if kind == "time_series":
            return 200, TIMES.read_bytes(), {}
        if kind == "splits":
            return splits
        if kind == "dividends":
            return dividends
        return 404, b'{"status": "error"}', {}
    return transport


def _patch(monkeypatch, ca_transport):
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_transport)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                      transport=ca_transport)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")


def _run(root, *argv) -> int:
    return cli.main(["--root", str(root), *argv])


def _stage_ready(root, monkeypatch, ca_transport) -> int:
    """Бумага заведена и отчётность собрана; остаётся стадия котировок —
    ровно та, где в поле случился 403. Возвращает счётчик запросов до
    этой стадии."""
    _patch(monkeypatch, ca_transport)
    assert _run(root, "init") == 0
    assert _run(root, "add", "--ticker", "AAPL", "--market", "US") == 0
    assert _run(root, "ingest", "--source", "edgar",
                "--instrument", "US-AAPL") == 0
    return cli._requests_used(str(root))


def _prices_stage(root) -> int:
    return _run(root, "ingest", "--source", "twelvedata",
                "--instrument", "US-AAPL")


def _seed(root, monkeypatch, ca_transport) -> int:
    _stage_ready(root, monkeypatch, ca_transport)
    return _prices_stage(root)


def _counts(root) -> tuple[int, dict]:
    """Сколько строк цены и сколько корпоративных действий по видам —
    чтение той же базы, что пишет стадия."""
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        prices = db.execute(
            "SELECT COUNT(*) FROM price WHERE instrument_id='US-AAPL'"
        ).fetchone()[0]
        actions = {row[0]: row[1] for row in db.execute(
            "SELECT kind, COUNT(*) FROM corporate_action "
            "WHERE instrument_id='US-AAPL' GROUP BY kind")}
        return prices, actions
    finally:
        db.close()


def _note_lines(out: str) -> list[str]:
    return [l for l in out.splitlines() if NOTE in l]


def test_a_plan_refusal_does_not_fail_the_price_stage(tmp_path, monkeypatch,
                                                      capsys):
    rc = _seed(tmp_path / "app", monkeypatch, _twelvedata_transport())
    assert rc == 0, "отказ по тарифу утонул стадию котировок"


def test_the_tier_refusal_is_said_in_words(tmp_path, monkeypatch, capsys):
    root = tmp_path / "app"
    _seed(root, monkeypatch, _twelvedata_transport())
    out = capsys.readouterr().out
    notes = _note_lines(out)
    assert notes, f"пометки о тарифе нет в выводе: {out}"
    for kind in ("splits", "dividends"):
        assert kind in notes[0], notes[0]


def test_quotes_are_written_even_when_both_actions_refuse(tmp_path,
                                                         monkeypatch):
    """Снисходительность не должна выглядеть как «стадия ничего не
    сделала»: котировки доезжают в базу при том же отказе."""
    root = tmp_path / "app"
    assert _seed(root, monkeypatch, _twelvedata_transport()) == 0
    prices, _ = _counts(root)
    assert prices > 0, "котировок в базе нет"


def test_a_refused_split_does_not_lose_the_dividends_that_answered(
        tmp_path, monkeypatch, capsys):
    """/splits 403 и /dividends 200 — записывается то, что ответило;
    отказанный эндпоинт назван, а не промолчан."""
    root = tmp_path / "app"
    rc = _seed(root, monkeypatch,
               _twelvedata_transport(dividends=(200, DIVS.read_bytes(), {})))
    assert rc == 0
    _, actions = _counts(root)
    assert actions.get("dividend"), f"дивидендов не записано: {actions}"
    notes = _note_lines(capsys.readouterr().out)
    assert notes and "splits" in notes[0] and "dividends" not in notes[0], \
        notes


def test_a_plain_failure_still_fails_the_stage(tmp_path, monkeypatch,
                                               capsys):
    """Не тариф — обычный отказ: 500 на /splits топит стадию, как и
    до правки (снисходительность только к плану)."""
    root = tmp_path / "app"
    rc = _seed(root, monkeypatch,
               _twelvedata_transport(splits=(500, b'{}', {}),
                                     dividends=(200, DIVS.read_bytes(), {})))
    assert rc != 0
    assert "http_500" in capsys.readouterr().err


def test_a_rate_limit_is_not_called_a_plan_limit(tmp_path, monkeypatch,
                                                 capsys):
    """429 — «временной», а не «тарифный» отказ: называть его бесплатным
    тарифом значило бы соврать пользователю про его ключ."""
    root = tmp_path / "app"
    rc = _seed(root, monkeypatch,
               _twelvedata_transport(splits=(429, b'{}', {}),
                                     dividends=(429, b'{}', {})))
    assert rc != 0
    out = capsys.readouterr().out
    assert NOTE not in out


def test_a_refused_by_plan_call_is_still_counted(tmp_path, monkeypatch,
                                                 capsys):
    """Отказ по тарифу — потраченный запрос: счётчик остаётся равным
    числу обращений к транспорту (правило ТЗ-96 R3 на новом пути), расход
    пишется один раз на стадию, а не на каждый отказ, и строка самой
    стадии называет оба отказанных вызова."""
    root = tmp_path / "app"
    calls: list = []
    before = _stage_ready(root, monkeypatch,
                          _twelvedata_transport(calls=calls))
    assert _prices_stage(root) == 0
    assert calls == ["time_series", "splits", "dividends"], calls
    spent = cli._requests_used(str(root)) - before
    assert spent == len(calls), f"потрачено {spent}, обращений {calls}"
    stage = [l for l in capsys.readouterr().out.splitlines()
             if l.startswith("US-AAPL: корп.действия: сплитов")]
    assert len(stage) == 1, stage
    assert "запросов: 2" in stage[0], \
        f"строка стадии теряет отказанные вызовы: {stage[0]}"


def test_a_hard_failure_is_counted_too(tmp_path, monkeypatch):
    """Тот же счётчик на жёстком отказе: 500 на /splits топит стадию,
    но оба пропущенных гейтом запроса в счётчике остаются."""
    root = tmp_path / "app"
    calls: list = []
    before = _stage_ready(
        root, monkeypatch,
        _twelvedata_transport(splits=(500, b'{}', {}),
                              dividends=(200, DIVS.read_bytes(), {}),
                              calls=calls))
    assert _prices_stage(root) != 0
    assert calls == ["time_series", "splits"], calls
    assert cli._requests_used(str(root)) - before == len(calls)


def test_the_refused_payload_is_not_cached(tmp_path, monkeypatch):
    """Отказанный по тарифу payload не попадает в raw — иначе следующий
    прогон читал бы кеш как успех и ничего бы не записал."""
    root = tmp_path / "app"
    _seed(root, monkeypatch, _twelvedata_transport())
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        rows = db.execute(
            "SELECT COUNT(*) FROM raw_object WHERE block='corporate_actions'"
        ).fetchone()[0]
    finally:
        db.close()
    assert rows == 0, f"отказ записан как payload: {rows}"


def test_the_second_run_says_the_same_thing(tmp_path, monkeypatch, capsys):
    """Повтор детерминирован: тот же нулевой код и та же пометка — без
    тихого «записано» на втором прогоне."""
    root = tmp_path / "app"
    transport = _twelvedata_transport()
    assert _seed(root, monkeypatch, transport) == 0
    capsys.readouterr()
    assert _run(root, "ingest", "--source", "twelvedata",
                "--instrument", "US-AAPL") == 0
    out = capsys.readouterr().out
    assert _note_lines(out), out
    assert "записано новых: 0" in out


def test_follow_finishes_the_path_and_builds_the_snapshot(tmp_path,
                                                          monkeypatch,
                                                          capsys):
    """Сквозной прогон версии 1: отказ по тарифу — путь пройден до
    снапшота, и совета, который не может сработать, в выводе нет."""
    root = tmp_path / "app"
    _patch(monkeypatch, _twelvedata_transport())
    args = _build_parser().parse_args(
        ["--root", str(root), "follow", "AAPL", "--market", "US"])
    rc = cli.cmd_follow(args)
    captured = capsys.readouterr()
    assert rc == 0, f"путь оборвался: rc={rc}\n{captured.out}"
    assert "6/6 снапшот — готово" in captured.out, captured.out
    assert "путь пройден" in captured.out
    assert NOTE in captured.out
    assert "совет:" not in captured.out + captured.err, \
        "совет-повтор обещает то, что не может сработать"

    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        sid = db.execute(
            "SELECT snapshot_id FROM snapshot WHERE instrument_id='US-AAPL' "
            "ORDER BY snapshot_id DESC LIMIT 1").fetchone()
        assert sid, "снапшота нет"
        valued = db.execute(
            "SELECT COUNT(*) FROM measure WHERE snapshot_id=? AND "
            "value IS NOT NULL", (sid[0],)).fetchone()[0]
    finally:
        db.close()
    assert valued > 0, "снапшот пуст: ни одной меры со значением"


def test_the_plan_refusal_reasons_are_named(tmp_path):
    """Множество «это тариф» замкнуто и названо: 403 в обеих формах
    (HTTP-код и тело вендора), и ничего кроме него."""
    from rusterm.providers.twelvedata import is_plan_refusal

    for reason in ("source_unreachable:http_403", "twelvedata_error:403"):
        assert is_plan_refusal(reason), reason
    for reason in ("vendor_rate_limited", "source_unreachable:transport",
                   "source_unreachable:http_500", "twelvedata_error:429",
                   "twelvedata_bad_response", ""):
        assert not is_plan_refusal(reason), reason
