"""ТЗ-20 L2: провайдер наборов CVM (Бразилия). Все тесты офлайн —
на ЗАПИСАННЫХ настоящих байтах tests/data/cvm/ (живая выкачка 11.09:
dfp_cia_aberta_2024.zip 13 396 366 B, Last-Modified как в замере;
cad_cia_aberta.csv 1 493 217 B). Сети нет: транспорт подставной,
счёт GET/HEAD ведётся им.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from rusterm.providers.base import ProviderError
from rusterm.providers.budget import (
    ConfigError, NetworkGate, RequestGate)
from rusterm.providers.cvm import CvmProvider, DatasetState

DATA = Path(__file__).resolve().parent / "data" / "cvm"
UA_ENV = {"RUSTERM_SEC_UA": "Synthetic Test l2.invalid"}


def _gate() -> RequestGate:
    return RequestGate(gate=NetworkGate(environ=dict(UA_ENV)))


def _provider(responses: dict[str, tuple[int, bytes, dict]]):
    """responses: url-часть -> (status, body, headers); счётчик методов
    ведётся в calls [('GET'|'HEAD', url), ...]."""
    calls: list[tuple[str, str]] = []

    def transport(url: str, headers: dict, method: str):
        calls.append((method, url))
        for part, (status, body, hdr) in responses.items():
            if part in url:
                return status, body, hdr
        return 404, b"not found", {}

    provider = CvmProvider(gate=_gate(), transport=transport)
    return provider, calls


# ── HEAD перед GET: ноль GET при неизменности ──────────────────────────

def test_head_first_zero_gets_when_last_modified_unchanged():
    """Ключевой тест полосы: та же метка Last-Modified — GET не
    выполняется вовсе, счётом вызовов транспорта (13 МБ не качаются)."""
    provider, calls = _provider({
        "dfp_cia_aberta_2024.zip": (
            200, b"", {"Last-Modified": "Sun, 06 Sep 2026 10:24:08 GMT",
                       "Content-Length": "13396366"}),
    })
    state = provider.dataset_if_changed(
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/"
        "dfp_cia_aberta_2024.zip",
        "Sun, 06 Sep 2026 10:24:08 GMT")
    assert isinstance(state, DatasetState)
    assert state.last_modified == "Sun, 06 Sep 2026 10:24:08 GMT"
    assert state.content_length == 13396366
    assert [m for m, _ in calls] == ["HEAD"], calls
    assert not any(b for m, _ in calls if m == "GET")


def test_get_happens_only_when_last_modified_changed():
    provider, calls = _provider({
        "dfp_cia_aberta_2024.zip": (
            200, b"ZIPBODY", {"Last-Modified": "Mon, 07 Sep 2026 10:00:00 GMT",
                              "Content-Length": "7"}),
    })
    out = provider.dataset_if_changed(
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/"
        "dfp_cia_aberta_2024.zip",
        "Sun, 06 Sep 2026 10:24:08 GMT")
    assert out == b"ZIPBODY"
    assert [m for m, _ in calls] == ["HEAD", "GET"]


def test_404_is_a_value_not_an_exception():
    provider, _ = _provider({})
    state = provider.dataset_state("https://dados.cvm.gov.br/x/absent.csv")
    assert isinstance(state, ProviderError)
    assert state.reason.startswith("cvm_not_found")


# ── кадастр: can_auto_ingest по записанной нарезке ─────────────────────

CAD = (DATA / "cad_slice.csv").read_bytes()


def test_can_auto_ingest_true_for_recorded_issuer_code():
    provider, _ = _provider({})
    # PETRÓLEO BRASILEIRO S.A. - PETROBRAS, CD_CVM 9512 (замер 11.09)
    assert provider.can_auto_ingest("9512", cadastro=CAD) is True
    assert provider.can_auto_ingest("009512", cadastro=CAD) is True


def test_can_auto_ingest_by_name_substring():
    provider, _ = _provider({})
    assert provider.can_auto_ingest("VALE", cadastro=CAD) is True


def test_unknown_issuer_is_value():
    provider, _ = _provider({})
    answer = provider.can_auto_ingest("999999", cadastro=CAD)
    assert isinstance(answer, ProviderError)
    assert answer.reason == "unknown_issuer"


# ── строки отчётности из записанных нарезок ────────────────────────────

DRE = (DATA / "dfp_2024_dre_slice.csv").read_bytes()
BPP = (DATA / "dfp_2024_bpp_slice.csv").read_bytes()


def test_dre_slice_holds_all_three_recorded_issuers():
    """Золотая привязка: каждое значение ниже разрешается в записанный
    файл tests/data/cvm/dfp_2024_dre_slice.csv (живая выкачка 11.09)."""
    provider, _ = _provider({})
    for code in ("9512", "4170", "23264"):
        rows = provider.rows_for(DRE, code)
        assert rows, code
        # FY2024 — ORDEM_EXERC 'ÚLTIMO' (источник: латиница-1, юникод)
        revenue = [r for r in rows if r["CD_CONTA"] == "3.01"
                   and r["ORDEM_EXERC"] == "ÚLTIMO"]
        assert revenue, (code, "revenue 3.01 ultimo")
        value = float(revenue[0]["VL_CONTA"])
        assert value > 0
        # Ambev FY2024: выручка 89 452 669 тыс. BRL (ESCALA_MOEDA=MIL)
        if code == "23264":
            assert 89_400_000 < value < 89_500_000, value


def test_bpp_slice_holds_balance_rows():
    provider, _ = _provider({})
    rows = provider.rows_for(BPP, "9512")
    # в нарезке баланса Петробраса — собственный капитал (замер 11.09:
    # Patrimônio Líquido Consolidado; FY2024 = 'ÚLTIMO',
    # 367 514 000 тыс. BRL; FY2023 = 'PENÚLTIMO', 382 340 000)
    equity = [r for r in rows
              if "PATRIMÔNIO" in (r.get("DS_CONTA") or "").upper()
              and r["ORDEM_EXERC"] == "ÚLTIMO"]
    assert equity
    assert 366_000_000 < float(equity[0]["VL_CONTA"]) < 369_000_000


def test_dfp_members_unzips_in_memory_only():
    """ZIP разбирается в памяти; на диск ничего не пишется (N5:
    архивы в git не попадают, временных файлов нет)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dfp_cia_aberta_2024.csv", "CD_CVM\n009512\n")
        zf.writestr("dfp_cia_aberta_DRE_con_2024.csv", "CD_CVM\n009512\n")
    provider, _ = _provider({})
    members = provider.dfp_members(buf.getvalue())
    assert set(members) == {"dfp_cia_aberta_2024.csv",
                            "dfp_cia_aberta_DRE_con_2024.csv"}
