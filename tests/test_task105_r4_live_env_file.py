"""ТЗ-105 R4: живой прогон видит настоящий env-файл.

Было (дефект, решение координатора — ТЗ-105, пункт «live tests see the
real env file»): `_isolated_rusterm_env` в `tests/conftest.py` ставила
пустышку на `RUSTERM_ENV_FILE` безусловно — и в прогоне `-m live` тоже.
Живому тесту это обходилось ручной строкой
`os.environ["RUSTERM_ENV_FILE"] = str(Path.home() / ".rusterm.env")`:
файл пользователя возвращали себе сами те, кому он положен по смыслу
прогона (tests/test_b36_live.py:64, :127, tests/test_c5_asx_body_live.py:48).

Стало: та же дверь, что у подмены HOME (`_p7_isolated_home`, ТЗ-97 Q11) —
`p7_home_isolation.live_run_selected(markexpr)`. Одно правило на обе
двери, а не второй пересказ условия. Ключи (`ENV_NAMES`) вычищаются в
обоих прогонах: живой прогон получает путь к файлу, а не значения в
окружении процесса.

Что проверяется: тело фикстуры вызывается напрямую, с подставным
`request`, то есть правило, а не обещание в докстринге. Сетевых
запросов нет ни в одном зубе; значения ключей никуда не печатаются — в
окружении стоят заведомо выдуманные метки, и проверяется их отсутствие,
а не содержимое.

| зуб | было | стало |
|---|---|---|
| `-m live` | путь подменён на пустышку | путь пользователя уцелевает |
| `-m "live and not slow"` | то же | уцелевает |
| обычный прогон (пустой селектор, addopts `not live`) | пустышка | пустышка, 0600, в tmp |
| `-m firsthour` (живым не считается) | пустышка | пустышка |
| ключи в обоих прогонах | вычищены | вычищены |
| откуда фикстура знает про живой прогон | ниоткуда | из той же функции, что и дверь HOME |
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

from rusterm import env as env_module
from tests import conftest
from tests import p7_home_isolation as p7_home

# Выдуманные метки: ни один ключ пользователя сюда не попадает.
_FAKE_KEY = "definitely-not-a-real-key-000"
_REALISH = "/Users/someone/.rusterm.env"


class _Request:
    """Минимум, который читает фикстура: `request.config.getoption`."""

    def __init__(self, markexpr):
        self._markexpr = markexpr

    class _Config:
        def __init__(self, markexpr):
            self._markexpr = markexpr

        def getoption(self, name):
            assert name == "markexpr"
            return self._markexpr

    @property
    def config(self):
        return self._Config(self._markexpr)


def _apply(monkeypatch, tmp_path, markexpr):
    """Вызвать тело autouse-фикстуры с нужным селектором.

    `request` фикстура получила не сразу (Р4 и есть про это), поэтому
    параметры собираются по её подписи: на прежнем дереве фикстура
    отрабатывает без `request` — и ровно это даёт красное сравнение
    «путь пользователя уцелел / не уцелел», а не TypeError.
    """
    fn = conftest._isolated_rusterm_env
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    kwargs = {"tmp_path": tmp_path, "monkeypatch": monkeypatch}
    if "request" in inspect.signature(fn).parameters:
        kwargs["request"] = _Request(markexpr)
    gen = fn(**kwargs)
    next(gen)
    return gen


@pytest.mark.parametrize("markexpr", ["live", "live and not slow",
                                      "not slow and live"])
def test_a_live_run_keeps_the_users_env_file(markexpr, monkeypatch,
                                             tmp_path):
    """Done-when: живой селектор — и `RUSTERM_ENV_FILE` остаётся тем,
    что дал запускающий, а не пустышкой из tmp."""
    monkeypatch.setenv("RUSTERM_ENV_FILE", _REALISH)
    _apply(monkeypatch, tmp_path, markexpr)
    assert os.environ["RUSTERM_ENV_FILE"] == _REALISH


@pytest.mark.parametrize("markexpr", ["", "not live", "firsthour",
                                       "unit and not live"])
def test_an_ordinary_run_still_gets_the_stub(markexpr, monkeypatch,
                                             tmp_path):
    """Обычный прогон герметичен, как был: путь указывает на файл этого
    теста, и прав 0600 — иначе doctor ругается на чистую базу."""
    monkeypatch.setenv("RUSTERM_ENV_FILE", _REALISH)
    _apply(monkeypatch, tmp_path, markexpr)
    stub = Path(os.environ["RUSTERM_ENV_FILE"])
    assert stub != Path(_REALISH)
    assert stub.is_relative_to(tmp_path)
    assert stub.read_text(encoding="utf-8") == ""
    assert stub.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("markexpr", ["live", ""])
def test_keys_are_wiped_in_both_runs(markexpr, monkeypatch, tmp_path):
    """Живой прогон получает путь, а не значения: и в `live`, и в
    обычном `ENV_NAMES` вычищены из окружения процесса."""
    monkeypatch.setenv("RUSTERM_ENV_FILE", _REALISH)
    for name in env_module.ENV_NAMES:
        monkeypatch.setenv(name, _FAKE_KEY)
    _apply(monkeypatch, tmp_path, markexpr)
    left = [name for name in env_module.ENV_NAMES
            if os.environ.get(name) == _FAKE_KEY]
    assert left == [], f"ключи остались в окружении: {left}"


def test_the_live_gate_is_the_same_rule_as_the_home_gate():
    """Одно условие на две двери: фикстура env-файла зовёт
    `live_run_selected`, а не пересказывает регулярку."""
    src = inspect.getsource(conftest._isolated_rusterm_env)
    assert "live_run_selected" in src
    assert "markexpr" in src
    # и та же функция, что решает подмену HOME
    assert "live_run_selected" in inspect.getsource(
        conftest._p7_isolated_home)
    assert p7_home.live_run_selected("live") is True
    assert p7_home.live_run_selected("not live") is False


def test_the_user_env_file_is_never_opened_by_the_fixture(monkeypatch,
                                                          tmp_path):
    """Ни один прогон не дочитывается до файла пользователя: путь
    остаётся строкой, фикстура его не читает и не создаёт."""
    nowhere = tmp_path / "definitely" / "absent.env"
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(nowhere))
    _apply(monkeypatch, tmp_path, "live")
    assert not nowhere.exists()
    assert os.environ["RUSTERM_ENV_FILE"] == str(nowhere)
