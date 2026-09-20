"""ТЗ-57 A2: перепись мер Бразилии по образцу ТЗ-49 — все меры
словаря, офлайн на записанных нарезках CVM (живая выкачка 11.09:
tests/data/cvm/). Каждая строка сравнивается с
tests/data/golden_census_task57_br.json: значение — точная строка из
БД, отказ — точная причина из rusterm/reasons.py с продолжением,
называющим конкретный отсутствующий концепт. Ни одна причина не
выдумана — токен каждой refusal-строки сверяется со словарём (assert).

Путь — настоящий канал ТЗ-56 Z2 (add -> ingest --source cvm ->
snapshot), транспорт подменён записанными байтами, счёт запросов ведёт
настоящий гейт.

ТЗ-58 C4: кандидат REPORT-57 закрыт — знак 3.08 нормализует карта
(cvm-dfp.v2), clip() снят: ставка вне полосы [0, 0.5] — отказ
jurisdiction_rate с числом, а не выдуманные 0.0/0.5.
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.providers.budget import RequestGate
from rusterm.providers.cvm import CAD_URL, CvmProvider
from rusterm.reasons import is_known_reason
from rusterm.store.paths import AppPaths
from rusterm.store.repos import RepoRegistry

DATA = Path(__file__).resolve().parent / "data"
GOLDEN = json.loads(
    (DATA / "golden_census_task57_br.json").read_text(encoding="utf-8"))

CAD = (DATA / "cvm" / "cad_slice.csv").read_bytes()
DRE = (DATA / "cvm" / "dfp_2024_dre_slice.csv").read_bytes()
BPP = (DATA / "cvm" / "dfp_2024_bpp_slice.csv").read_bytes()

DRE_MEMBER = "dfp_cia_aberta_DRE_con_2024.csv"
BPP_MEMBER = "dfp_cia_aberta_BPP_con_2024.csv"

# десять мер переписи ТЗ-49 + roe_incl_nci (ТЗ-56 Z1)
MEASURES = ("asset_turnover", "ebitda", "effective_tax", "fcf",
            "gross_margin", "interest_coverage", "net_margin", "nopat",
            "operating_margin", "roe", "roe_incl_nci")


def _dfp_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dfp_cia_aberta_2024.csv", "CD_CVM\n009512\n")
        zf.writestr(DRE_MEMBER, DRE)
        zf.writestr(BPP_MEMBER, BPP)
    return buf.getvalue()


@pytest.fixture()
def br_app(monkeypatch, tmp_path):
    """Канал Z2 на записанных байтах: add -> ingest -> snapshot."""
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test a57.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    monkeypatch.delenv("RUSTERM_DART_KEY", raising=False)
    monkeypatch.delenv("RUSTERM_LLM_API_KEY", raising=False)
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
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    monkeypatch.setattr(cli, "args_as_of_default",
                        lambda: "2025-06-30")
    assert cli.main(["--root", str(root), "add", "--ticker", "AMBEV",
                     "--market", "BR"]) == 0
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "BR-AMBEV", "--source", "cvm"]) == 0
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     "BR-AMBEV"]) == 0
    return root, AppPaths.from_root(root)


def _census_rows(root):
    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(str(paths.db_path), timeout=30)
    try:
        repos = RepoRegistry(conn, paths)
        sid = repos.snapshot.latest_snapshot_id("BR-AMBEV")
        rows = {m[3]: {"value": m[4], "reason": m[10]}
                for m in repos.snapshot.get_measures(sid)
                if m[3] in MEASURES}
    finally:
        conn.close()
    assert len(rows) == len(MEASURES), sorted(rows)
    return {k: rows[k] for k in MEASURES}


def test_br_census_matches_golden_offline(br_app):
    """Вся перепись BR: значения и отказы закреплены строка за строкой;
    прогон полностью офлайн на записанных нарезках."""
    root, _ = br_app
    rows = _census_rows(root)
    assert rows == GOLDEN["census"]["BR-AMBEV"], rows


def test_br_refusals_name_dictionary_tokens(br_app):
    """Ни одна причина не выдумана: первый токен каждой refusal-строки
    из словаря rusterm/reasons.py, продолжение называет концепт."""
    root, _ = br_app
    for measure, row in _census_rows(root).items():
        if row["value"] is None:
            token = row["reason"].split(":", 1)[0]
            assert is_known_reason(token), (measure, row["reason"])
            assert row["reason"] != "missing_data", (
                measure, "отказ без имени концепта")
        else:
            assert row["reason"] is None, (measure, row["reason"])


def test_br_green_values_are_exact_strings(br_app):
    """Считающиеся меры дают ровно те числа, что в отчёте. ТЗ-58 C4:
    знак 3.08 нормализует карта (cvm-dfp.v2), clip() снят — AMBEV
    effective_tax даёт настоящую ставку ≈23.81%, а не выдуманный 0.0."""
    root, _ = br_app
    rows = _census_rows(root)
    assert rows["gross_margin"]["value"] == "0.5124228210563511"
    assert rows["net_margin"]["value"] == "0.16597550599636104"
    assert rows["roe_incl_nci"]["value"] == "0.16521917935689903"
    assert rows["effective_tax"]["value"] == "0.23812270405274155"


def test_br_roe_refusal_coexists_with_incl_nci(br_app):
    """Z1-правило на BR: roe отказывает missing_data: total_equity
    (никакой подстановки 2.03), roe_incl_nci по тому же payload
    считает."""
    root, _ = br_app
    rows = _census_rows(root)
    assert rows["roe"] == {"value": None,
                           "reason": "missing_data: total_equity"}
    assert rows["roe_incl_nci"]["value"] is not None


def test_census_command_lists_br_like_us_ca_otc(br_app, capsys,
                                                monkeypatch):
    """`rusterm census --instrument BR-AMBEV` показывает эмитента BR
    наравне с US/CA/OTC: та же команда, те же 11 мер словаря."""
    import contextlib
    root, _ = br_app
    monkeypatch.setattr(cli, "args_as_of_default",
                        lambda: "2025-06-30")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cli.main(["--root", str(root), "census", "--instrument",
                         "BR-AMBEV"]) == 0
    out = buf.getvalue()
    assert "BR-AMBEV" in out, out
    for measure in MEASURES:
        assert measure in out, (measure, out)
