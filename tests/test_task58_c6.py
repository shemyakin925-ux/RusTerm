"""ТЗ-58 C6: у провайдера КАЖДОГО зарегистрированного рынка есть
resolve и ticker_venues — дверь add не падает AttributeError.

Дефект (находка ТЗ-57 A4, вердикт Q6): CvmProvider не имел resolve —
живой `rusterm add --ticker X --market BR` умирал с AttributeError,
а тесты ТЗ-56 маскировали это адаптером _BR. Теперь: resolve есть у
всех, тест краснеет, если у кого-то из реестра рынков его нет; и
`add --ticker AMBEV --market BR` проходит на записанном кадастре
через НАСТОЯЩЕГО провайдера, без адаптера.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.markets import MARKETS
from rusterm.providers.budget import ConfigError, RequestGate
from rusterm.providers.cvm import CAD_URL, CvmProvider

DATA = Path(__file__).resolve().parent / "data"
CAD = (DATA / "cvm" / "cad_slice.csv").read_bytes()
DRE = (DATA / "cvm" / "dfp_2024_dre_slice.csv").read_bytes()
BPP = (DATA / "cvm" / "dfp_2024_bpp_slice.csv").read_bytes()

DRE_MEMBER = "dfp_cia_aberta_DRE_con_2024.csv"
BPP_MEMBER = "dfp_cia_aberta_BPP_con_2024.csv"


def _dfp_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dfp_cia_aberta_2024.csv", "CD_CVM\n009512\n")
        zf.writestr(DRE_MEMBER, DRE)
        zf.writestr(BPP_MEMBER, BPP)
    return buf.getvalue()


def test_every_market_provider_has_resolve_and_venues(monkeypatch):
    """Краснеет, если у провайдера ЛЮБОГО зарегистрированного рынка
    нет resolve или ticker_venues — AttributeError add'а невозможен
    по построению."""
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test c6.invalid")
    monkeypatch.setenv("RUSTERM_DART_KEY", "fake-dart-key-for-build")
    from rusterm.providers import get_provider
    for market in MARKETS:
        provider = get_provider(market.provider, gate=RequestGate())
        assert not isinstance(provider, ConfigError), (
            market.code, getattr(provider, "reason", None))
        assert callable(getattr(provider, "resolve", None)), (
            f"{market.code}: провайдер {market.provider} без resolve")
        assert callable(getattr(provider, "ticker_venues", None)), (
            f"{market.code}: провайдер {market.provider} без "
            f"ticker_venues")


def test_add_market_br_works_through_real_provider(monkeypatch, tmp_path,
                                                   capsys):
    """add --ticker AMBEV --market BR на записанном кадастре —
    НАСТОЯЩИМ CvmProvider (адаптер _BR из ТЗ-56 убран): эмитент
    найден по подстроке DENOM_SOCIAL, CIK = CD_CVM."""
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test c6.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")

    def transport(url, headers, method):
        if url == CAD_URL and method == "HEAD":
            return 200, b"", {"Last-Modified": "recorded-cad"}
        if url == CAD_URL and method == "GET":
            return 200, CAD, {}
        if url.endswith(".zip") and method == "HEAD":
            return 200, b"", {"Last-Modified": "x",
                              "Content-Length": str(len(_dfp_zip()))}
        if url.endswith(".zip") and method == "GET":
            return 200, _dfp_zip(), {}
        return 404, b"", {}

    monkeypatch.setattr(
        cli, "get_provider",
        lambda name, gate=None: CvmProvider(gate=gate or RequestGate(),
                                            transport=transport))
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    monkeypatch.setattr(cli, "args_as_of_default",
                        lambda: "2025-06-30")
    assert cli.main(["--root", str(root), "add", "--ticker", "AMBEV",
                     "--market", "BR"]) == 0
    out = capsys.readouterr().out
    assert "AMBEV S.A." in out, out
    assert "CIK 23264" in out, out

    # не-эмитент: кадастровый поиск отвечает значением, а не падением
    from rusterm.providers.base import ProviderError
    provider = CvmProvider(gate=RequestGate(), transport=transport)
    outcome = provider.resolve("NOSUCHNAME", "BR", "2025-06-30")
    assert isinstance(outcome, ProviderError)
    assert outcome.reason == "unknown_issuer"
