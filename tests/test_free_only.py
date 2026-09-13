"""ТЗ-28: бесплатность — правило, которое проверяет машина (ADR-0018).

R1: каждый сетевой канал реестра объявляет тариф из закрытого набора
(open / free_key / paid); ни одно зарегистрированное имя не объявляет
paid; синтетическое paid-место, подсаженное в реестр тестом, выдаётся
отказом-значением paid_channel_refused, и ни один запрос не уходит.
"""
from __future__ import annotations

import pytest

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
