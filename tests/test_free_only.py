"""ТЗ-28: бесплатность — правило, которое проверяет машина (ADR-0018).

R1: каждый сетевой канал реестра объявляет тариф из закрытого набора
(open / free_key / paid); ни одно зарегистрированное имя не объявляет
paid; синтетическое paid-место, подсаженное в реестр тестом, выдаётся
отказом-значением paid_channel_refused, и ни один запрос не уходит.
"""
from __future__ import annotations

import ast

import pytest

from pathlib import Path

import rusterm.providers as providers
from rusterm.providers.budget import ConfigError, RequestGate

_TIERS = ("open", "free_key", "paid")


def _network_names() -> list[str]:
    return sorted(providers._NETWORK_PROVIDERS)


def test_every_network_name_declares_a_tier_from_the_closed_set():
    names = _network_names()
    assert names, "реестр сетевых каналов пуст — проверять нечего"
    declared = {}
    for name in names:
        tier = providers.channel_tier(name)
        assert tier in _TIERS, (name, tier)
        declared[name] = tier
    print("tiers:", declared)


def test_no_registered_name_declares_paid():
    for name in _network_names():
        assert providers.channel_tier(name) != "paid", name


def test_paid_seat_injected_into_registry_is_refused_by_value(monkeypatch):
    built = []
    calls = []

    def factory(gate):
        built.append(1)
        return object()

    monkeypatch.setitem(providers._NETWORK_PROVIDERS,
                        "paid-synthetic", factory)
    monkeypatch.setitem(providers._CHANNEL_TIERS, "paid-synthetic", "paid")
    gate = RequestGate()
    out = providers.get_provider("paid-synthetic", gate=gate)
    assert isinstance(out, ConfigError)
    assert out.reason == "paid_channel_refused", out.reason
    assert not built, "фабрика paid-канала отработала при отказе"
    assert gate.calls_made == 0, gate.calls_made
    assert not calls


def test_name_without_tier_is_refused_by_value(monkeypatch):
    def factory(gate):
        return object()

    monkeypatch.setitem(providers._NETWORK_PROVIDERS,
                        "tierless-synthetic", factory)
    out = providers.get_provider("tierless-synthetic", gate=RequestGate())
    assert isinstance(out, ConfigError)
    assert out.reason == "provider_declares_no_tier:tierless-synthetic"


def test_doctor_prints_free_section_without_paid_and_without_key_values(
        tmp_path, capsys):
    """ТЗ-28 R2: doctor несёт раздел бесплатности — каждое сетевое имя
    из реестра с его тарифом; слова paid в выводе нет; подставное
    значение ключа в вывод не попадает; отсутствие ключа не меняет код
    выхода."""
    import json
    import os

    import rusterm.cli as cli

    injected = {"RUSTERM_LLM_API_KEY": "dummykey",
                "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests"}
    saved = {n: os.environ.get(n) for n in injected}
    os.environ.update(injected)
    try:
        root = tmp_path / "app"
        assert cli.main(["--root", str(root), "init"]) == 0
        capsys.readouterr()
        assert cli.main(["--root", str(root), "doctor"]) == 0
        out = capsys.readouterr().out
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    payload = json.loads(out)
    section = payload["free_channels"]
    for name in providers.available():
        tier = providers.channel_tier(name)
        if tier is None:
            continue  # синтетические места — не внешние каналы, без тарифа
        assert name in section, (name, sorted(section))
        assert section[name]["tier"] == tier, name
    assert "paid" not in out
    assert "dummykey" not in out


def test_quotations_channel_declares_vendor_free_ceiling():
    """ТЗ-28 R3: потолок котировок — число вендора, не проектная цифра.
    Twelve Data free: 8 запросов/мин, 800/день (ADR-0014 §1)."""
    limit = providers.host_limit("twelvedata")
    assert limit is not None, "котировочный канал не объявлен в реестре"
    assert limit.host == "api.twelvedata.com"
    assert limit.nightly_max == 800, limit.nightly_max
    assert limit.per_second <= 8.0 / 60.0, limit.per_second
    assert providers.channel_tier("twelvedata") == "free_key"


def test_twelvedata_seat_is_refused_until_module_lands():
    """ТЗ-28 R3: модуль котировок не подделывается — место честно
    отвечает provider_not_implemented значением."""
    out = providers.get_provider("twelvedata", gate=RequestGate())
    assert isinstance(out, ConfigError)
    assert out.reason == "provider_not_implemented:twelvedata", out.reason


# ── R4: новый хост не появляется мимо реестра ──────────────────────────

# Известные двух-трёхметочные публичные суффиксы наших вендоров: для
# них регистрируемый домен — три метки, иначе две. Таблица короткая и
# закрытая; новый вендор с новым суффиксом обязан дополнить её явно.
_MULTI_LABEL_SUFFIXES = (".or.kr", ".com.br", ".gov.br", ".com.au",
                         ".co.uk", ".com.tr")


def _registrable(host: str) -> str:
    for suffix in _MULTI_LABEL_SUFFIXES:
        if host.endswith(suffix):
            return host.split(".")[-3] + suffix
    return ".".join(host.split(".")[-2:])


def _host_of(literal: str) -> str | None:
    """Hostname из строкового литерала, похожего на URL; не-URL — None.
    Берётся первый token с схемой: литералы-прозы без URL дают None."""
    from urllib.parse import urlparse
    for token in literal.split():
        if "://" in token:
            netloc = urlparse(token).netloc.lower().strip("/")
            if netloc and "." in netloc and netloc[0].isalnum():
                return netloc
    return None


def _docstring_spans(tree: ast.AST) -> list[tuple[int, int]]:
    """(lineno, end_lineno) докстрингов модуля/классов/функций: хост в
    докстринге, объясняющем отказанный платный аналог, — проза, а не
    канал, и страж краснеть от него не должен."""
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = node.body[0] if getattr(node, "body", None) else None
            if isinstance(body, ast.Expr) and \
                    isinstance(body.value, ast.Constant) and \
                    isinstance(body.value.value, str):
                spans.append((body.value.lineno, body.value.end_lineno))
    return spans


def _host_literals(path: Path) -> dict[str, int]:
    """{host: lineno} по строковым константам модуля, вне докстрингов.
    Разбор — через ast, не регэксп по тексту: комментарии вообще не
    попадают в дерево, а докстринги вырезаются позициями."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    spans = _docstring_spans(tree)
    hosts: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(a <= node.lineno <= b for a, b in spans):
                continue
            host = _host_of(node.value)
            if host and host not in hosts:
                hosts[host] = node.lineno
    return hosts


def test_every_host_literal_belongs_to_a_declared_channel():
    """ТЗ-28 R4: каждый хост, достижимый из rusterm/providers/*.py,
    принадлежит каналу, объявленному в реестре (по регистрируемому
    домену: www.sec.gov — тот же канал edgar, что data.sec.gov).
    Нарушение называется файлом, строкой и хостом."""
    import rusterm.providers as providers_mod
    declared = {_registrable(limit.host)
                for limit in providers_mod.all_host_limits().values()}
    assert declared, "реестр пуст — страж ничего не охраняет"
    zone = Path(providers_mod.__file__).parent
    offenders = []
    for path in sorted(zone.glob("*.py")):
        for host, lineno in _host_literals(path).items():
            if _registrable(host) not in declared:
                offenders.append(f"{path.name}:{lineno}: {host}")
    assert not offenders, "хосты мимо реестра: " + "; ".join(offenders)
