"""ТЗ-56 Z2: канал ingest Бразилии — add → ingest --source cvm →
snapshot → export, всё офлайн на записанных нарезках CVM (живая
выкачка 11.09: tests/data/cvm/). ZIP набора в git не попадает (N5) —
собирается в памяти из нарезок; транспорт подменён, счёт запросов
ведёт настоящий RequestGate, и то же число печатает rusterm budget.

Честные отказы сохранены: CD_CONTA 3.05 (EBIT-подобная строка) под
operating_income не ставится (вердикт ТЗ-55), 2.03 — капитал С НКД,
то есть total_equity_incl_nci: roe отказывает
missing_data: total_equity, а roe_incl_nci по тому же payload считает
(З1 pays off).
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.core.fact import LocatorCvmDfp
from rusterm.core.fact import locator_from_json
from rusterm.core.fact import resolve_locator
from rusterm.normalize.concepts import canonical_for
from rusterm.parsers.cvm_dfp import CvmDfpParser
from rusterm.providers.base import ProviderError  # noqa: F401
from rusterm.providers.budget import RequestGate
from rusterm.providers.cvm import CAD_URL, CvmProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.raw_store import decompress_object

DATA = Path(__file__).resolve().parent / "data"
CAD = (DATA / "cvm" / "cad_slice.csv").read_bytes()
DRE = (DATA / "cvm" / "dfp_2024_dre_slice.csv").read_bytes()
BPP = (DATA / "cvm" / "dfp_2024_bpp_slice.csv").read_bytes()

DRE_MEMBER = "dfp_cia_aberta_DRE_con_2024.csv"
BPP_MEMBER = "dfp_cia_aberta_BPP_con_2024.csv"

_TEN = ("asset_turnover", "ebitda", "effective_tax", "fcf",
        "gross_margin", "interest_coverage", "net_margin", "nopat",
        "operating_margin", "roe")


def _dfp_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dfp_cia_aberta_2024.csv", "CD_CVM\n009512\n")
        zf.writestr(DRE_MEMBER, DRE)
        zf.writestr(BPP_MEMBER, BPP)
    return buf.getvalue()


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test z2.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    monkeypatch.delenv("RUSTERM_DART_KEY", raising=False)
    monkeypatch.delenv("RUSTERM_LLM_API_KEY", raising=False)
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    # as_of середины 2025: последний закрытый год = 2024 — год
    # записанного набора; канал просит dfp_cia_aberta_2024.zip
    monkeypatch.setattr(cli, "args_as_of_default",
                        lambda: "2025-06-30")
    return root, AppPaths.from_root(root)


@pytest.fixture()
def cvm_channel(monkeypatch):
    """Подменный транспорт на записанных байтах + адаптер add.
    calls — журнал (method, url) всех запросов настоящего гейта."""
    calls: list[tuple[str, str]] = []

    def transport(url, headers, method):
        calls.append((method, url))
        if url == CAD_URL and method == "HEAD":
            return 200, b"", {"Last-Modified": "recorded-cad"}
        if url == CAD_URL and method == "GET":
            return 200, CAD, {}
        if url.endswith(".zip") and method == "HEAD":
            return 200, b"", {"Last-Modified": "recorded-dfp",
                              "Content-Length": str(len(_dfp_zip()))}
        if url.endswith(".zip") and method == "GET":
            return 200, _dfp_zip(), {}
        return 404, b"", {}

    class _BR:
        """add требует resolve/can_auto_ingest/ticker_venues; ingest —
        методов настоящего CvmProvider под тем же транспортом
        (dataset_state, dataset_if_changed, dfp_members, rows_for)."""

        def __init__(self, gate=None):
            self.gate = gate
            self.cvm = CvmProvider(gate=gate or RequestGate(),
                                   transport=transport)

        def __getattr__(self, name):
            return getattr(self.cvm, name)

        def resolve(self, ticker, market, as_of):
            return {"ticker": ticker.upper(), "cik": 23264,
                    "title": "AMBEV S.A."}

        def can_auto_ingest(self, identifier):
            return self.cvm.can_auto_ingest(identifier, cadastro=CAD)

        def ticker_venues(self):
            return {}

    monkeypatch.setattr(cli, "get_provider",
                        lambda name, gate=None: _BR(gate=gate))
    return calls


def test_add_ingest_snapshot_export_full_path(app, cvm_channel, capsys):
    """Полный путь канала: эмитент создан, ingest собрал факты,
    snapshot посчитал меры;-values и отказы честны."""
    root, paths = app
    assert cli.main(["--root", str(root), "add", "--ticker", "AMBEV",
                     "--market", "BR"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "BR-AMBEV", "--source", "cvm"]) == 0
    ingested = capsys.readouterr().out
    assert "фактов" in ingested, ingested
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     "BR-AMBEV"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "export", "--instrument",
                     "BR-AMBEV", "--format", "json"]) == 0
    export = json.loads(capsys.readouterr().out)
    assert export["snapshot"]["instrument_id"] == "BR-AMBEV"

    rows = {m["concept"]: m for m in export["measures"]
            if m["concept"] in _TEN + ("roe_incl_nci",)}
    assert len(rows) == 11, sorted(rows)
    # считается: выручка/прибыль/налог/капитал с НКД есть в DFP
    for concept in ("net_margin", "gross_margin", "effective_tax",
                    "roe_incl_nci"):
        assert rows[concept]["value"] is not None, (concept,
                                                    rows[concept])
    # roe не подменяется: тот же отказ, что в переписи CNQ
    assert rows["roe"]["value"] is None
    assert rows["roe"]["null_reason"] == "missing_data: total_equity"
    # EBIT-строка 3.05 намеренно вне карты — отказ называет входы
    for concept, reason in (
            ("operating_margin", "missing_data: operating_income"),
            ("ebitda", "missing_data: d_and_a, operating_income"),
            ("nopat", "missing_data: operating_income"),
            ("interest_coverage",
             "missing_data: interest_expense, operating_income")):
        assert rows[concept]["value"] is None, concept
        assert rows[concept]["null_reason"] == reason, \
            (concept, rows[concept]["null_reason"])
    assert rows["asset_turnover"]["null_reason"] == \
        "missing_data: total_assets"
    assert rows["fcf"]["null_reason"] == "missing_data: capex, ocf"


def test_budget_names_requests_by_number(app, cvm_channel, capsys):
    """Бюджет назван числом из rusterm budget: счёт настоящего гейта
    (HEAD + HEAD + GET = 3 на свежую загрузку) попадает в
    metric_sample и печатается командой."""
    root, paths = app
    assert cli.main(["--root", str(root), "add", "--ticker", "AMBEV",
                     "--market", "BR"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "BR-AMBEV", "--source", "cvm"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "budget"]) == 0
    out = capsys.readouterr().out
    assert "provider_requests_used" in out, out
    named = float(out.split("provider_requests_used =")[1].split()[0])
    assert named == 3.0, out


def test_second_run_costs_one_head(app, cvm_channel, capsys):
    """Инкрементальность: метка Last-Modified сохранена — второй прогон
    ограничивается одним HEAD, GET не выполняется вовсе."""
    root, paths = app
    assert cli.main(["--root", str(root), "add", "--ticker", "AMBEV",
                     "--market", "BR"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "BR-AMBEV", "--source", "cvm"]) == 0
    capsys.readouterr()
    before = len(cvm_channel)
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "BR-AMBEV", "--source", "cvm"]) == 0
    out = capsys.readouterr().out
    assert "не изменился" in out, out
    delta = cvm_channel[before:]
    assert [m for m, _ in delta] == ["HEAD"], delta


def test_facts_carry_cvm_provenance_and_resolve(app, cvm_channel,
                                                capsys):
    """Провенанс: fact.source_ref разрешается в raw_object провайдера
    cvm с URL набора; локатор cvm-dfp разрешается тем же значением из
    записанного ZIP (I12)."""
    root, paths = app
    assert cli.main(["--root", str(root), "add", "--ticker", "AMBEV",
                     "--market", "BR"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "BR-AMBEV", "--source", "cvm"]) == 0
    capsys.readouterr()

    conn = sqlite3.connect(str(paths.db_path))
    conn.row_factory = sqlite3.Row
    try:
        facts = conn.execute(
            """SELECT fact_id, concept, canonical_concept, value,
                      unit, period_type, source_ref, locator
               FROM fact WHERE issuer_id='cik-23264'""").fetchall()
        assert facts, "факты CVM не записаны"
        raw = conn.execute(
            """SELECT provider, url FROM raw_object
               WHERE sha256=?""",
            (facts[0]["source_ref"],)).fetchone()
        assert raw["provider"] == "cvm", raw
        assert raw["url"].endswith("dfp_cia_aberta_2024.zip"), raw
    finally:
        conn.close()

    getter = lambda sha: decompress_object(paths.raw_store, sha)
    by_concept = {}
    unmapped_rows = 0
    for row in facts:
        loc = locator_from_json(json.loads(row["locator"]))
        assert loc.kind == "cvm-dfp"
        assert resolve_locator(loc, getter) == row["value"], row
        canonical = canonical_for(loc.cd_conta, "cvm-dfp")
        if canonical is None:
            # строки вне карты (например 3.04) факт остаётся, канон NULL
            unmapped_rows += 1
            continue
        by_concept[canonical] = row["value"]
    assert unmapped_rows, "вне карты должен быть хотя бы один факт"
    assert {"revenue", "gross_profit", "pretax_income", "tax_expense",
            "net_income", "total_equity_incl_nci"} <= set(by_concept), \
        sorted(by_concept)
    # 2.03 — капитал с НКД; его канонический концепт не total_equity
    assert "total_equity" not in by_concept


def test_markets_shows_channel_honestly(app, cvm_channel, capsys):
    """rusterm markets: у BR канал назван, у AU — честное отсутствие
    вместо provider_status=implemented при мёртвом канале."""
    root, paths = app
    assert cli.main(["--root", str(root), "markets", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_code = {row["code"]: row for row in payload["markets"]}
    assert by_code["BR"]["channel"] == "cvm"
    assert by_code["BR"]["provider_status"] == "implemented"
    assert by_code["AU"]["channel"] is None
    assert by_code["AU"]["provider_status"] == "implemented"
    assert by_code["KR"]["channel"] is None
    assert by_code["US"]["channel"] == "edgar"


def test_cvm_dfp_parser_scales_and_dedupes():
    """Юнит парсера: ESCALA_MOEDA=MIL умножается на 1000, старшая
    VERSAO побеждает, неразобранное считается."""
    parser = CvmDfpParser()
    rows = [
        {"CD_CONTA": "3.01", "ORDEM_EXERC": "ÚLTIMO", "VERSAO": "1",
         "DT_INI_EXERC": "2024-01-01", "DT_FIM_EXERC": "2024-12-31",
         "VL_CONTA": "89452669", "MOEDA": "BRL",
         "ESCALA_MOEDA": "MIL"},
        {"CD_CONTA": "2.03", "ORDEM_EXERC": "ÚLTIMO", "VERSAO": "2",
         "DT_FIM_EXERC": "2024-12-31", "VL_CONTA": "1000",
         "MOEDA": "BRL", "ESCALA_MOEDA": "MIL"},
        {"CD_CONTA": "2.03", "ORDEM_EXERC": "ÚLTIMO", "VERSAO": "1",
         "DT_FIM_EXERC": "2024-12-31", "VL_CONTA": "999",
         "MOEDA": "BRL", "ESCALA_MOEDA": "MIL"},
        {"CD_CONTA": "x", "ORDEM_EXERC": "ÚLTIMO", "VERSAO": "1",
         "DT_FIM_EXERC": "2024-12-31", "VL_CONTA": "abc",
         "MOEDA": "BRL", "ESCALA_MOEDA": "MIL"},
    ]
    facts, unparsed = parser.parse_rows(
        rows + [{"CD_CONTA": "3.01", "ORDEM_EXERC": "PENÚLTIMO",
                 "VERSAO": "1", "DT_INI_EXERC": "2023-01-01",
                 "DT_FIM_EXERC": "2023-12-31", "VL_CONTA": "1",
                 "MOEDA": "BRL", "ESCALA_MOEDA": "MIL"}],
        "DRE", {"issuer_id": "i", "source_ref": "sha", "csv_member": "m"})
    assert unparsed == 1
    rev = [f for f in facts if f["concept"] == "cvm-dfp:3.01"]
    assert len(rev) == 2  # ÚLTIMO и PENÚLTIMO — разные периоды
    assert rev[0]["value"] == repr(89452669 * 1000.0)
    assert rev[0]["period_type"] == "duration"
    eq = [f for f in facts if f["concept"] == "cvm-dfp:2.03"]
    assert len(eq) == 1 and eq[0]["value"] == repr(1000 * 1000.0)


def test_locator_unknown_row_is_value_error():
    """Локатор cvm-dfp по строке, которой нет в записанном ZIP, —
    ValueError, а не молчаливое значение."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(DRE_MEMBER, DRE)
    body = {"sha": buf.getvalue()}
    loc = LocatorCvmDfp(doc_sha256="sha", csv_member=DRE_MEMBER,
                        cd_conta="9.99", ordem_exerc="ÚLTIMO",
                        period_start="2024-01-01",
                        period_end="2024-12-31",
                        escala_moeda="MIL", raw_value="1")
    with pytest.raises(ValueError):
        resolve_locator(loc, lambda sha: body[sha])
