"""Общая изоляция окружения для всего набора (TASK-29 A1).

Ни один тест не читает настоящий ~/.rusterm.env: autouse-фикстура
ставит RUSTERM_ENV_FILE на пустой файл в tmp_path и вычищает все имена
ENV_NAMES из os.environ до теста; monkeypatch возвращает всё как было
после него. Тест, которому нужно значение, ставит его сам
(monkeypatch.setenv). Контракт load_env — писать в настоящий
os.environ — не меняется: тесты test_env.py продолжают это доказывать
уже со своим восстанавливающим fixture.

Исключение — живой прогон (ТЗ-105 R4): когда селектор маркеров зовёт
`live`, фикстура путь не подменяет (иначе живым тестам пришлось бы
_restore-ить его руками, как они и делают в test_b36_live и
test_c5_asx_body_live), но имена ключей вычищает по-прежнему.

Вторая часть изоляции — профили Hypothesis (ТЗ-82 E1, ADR-0024): они
зарегистрированы здесь и только здесь, выбор делает переменная
HYPOTHESIS_PROFILE. Ядро их не импортирует.

Третья — подмена HOME на весь прогон (ТЗ-97 Q11, дверь P7): с тех пор
как каталог данных по умолчанию стал `~/EquityLab/data`, тест без
подменённого HOME писал бы в рабочую базу пользователя. Живой прогон
(`-m live`) HOME не трогает: ему нужен настоящий `~/.rusterm.env` с
ключами.
"""
from __future__ import annotations

import os

import pytest
from hypothesis import settings

from rusterm import env as env_module
from tests import p7_home_isolation as p7_home

# ТЗ-82 E1: default — детерминированный и быстрый, deep — редкий прогон
# по требованию. database=None в обоих: база примеров по умолчанию
# пишется каталогом .hypothesis/ рабочего дерева, то есть файлом вне git
# (P3) и в домашнем каталоге того, кто запустил прогон (P7).
settings.register_profile("default", derandomize=True, database=None,
                          deadline=None, max_examples=200)
settings.register_profile("deep", derandomize=False, database=None,
                          deadline=None, max_examples=5000)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# ТЗ-109 R2: ретраи транспорта ждут 1/4/15 с между попытками — в тестах
# сон подставной (нулевая пауза), число попыток и счёт бюджета честные.
# Живые повторы спят настоящим сном: константа возвращается процессом,
# который conftest не импортировал.
from rusterm.providers import budget as _budget  # noqa: E402

_budget.RETRY_SLEEP = lambda _seconds: None


@pytest.fixture(autouse=True)
def _isolated_rusterm_env(request, tmp_path, monkeypatch):
    # ТЗ-105 R4: та же дверь, что у подмены HOME ниже (`_p7_isolated_home`,
    # ТЗ-97 Q11). Живому прогону нужен настоящий `~/.rusterm.env`, поэтому
    # пустышка ставится только когда селектор маркеров живых тестов не
    # зовёт. Правило — одна функция на обе двери
    # (`p7_home_isolation.live_run_selected`), а не копия условия.
    # Ключи при этом вычищаются в обоих прогонах: живой прогон получает
    # путь к файлу, а не значения в окружении процесса.
    if not p7_home.live_run_selected(request.config.getoption("markexpr")):
        env_file = tmp_path / "empty-rusterm.env"
        env_file.write_text("", encoding="utf-8")
        # 0600, как у настоящего файла: doctor иначе честно ругается на
        # файл, читаемый группой/остальными, и чистая база становится «не ok».
        env_file.chmod(0o600)
        monkeypatch.setenv("RUSTERM_ENV_FILE", str(env_file))
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    # Кэш происхождений у load_env процесса, а не теста: без сброса
    # report()/keys_view() читают origins чужого теста мимо
    # изолированного окружения (красила пара test_env + keys_view).
    env_module._LAST_ORIGINS = None
    yield


@pytest.fixture(autouse=True)
def _no_network_in_default_run(request, monkeypatch):
    """Доказательство «нуля запросов» (TASK-29 A2), машинное: в тесте
    без маркера live urllib.request.urlopen заменён на падающий страж.
    Любой выход в сеть в default-прогоне роняет тест с именем URL.
    Живые тесты несут маркер live и по умолчанию не собираются
    (addopts -m "not live"). Subprocess этой замены не видит — их
    закрывает само собранное окружение теста и изоляция из A1."""
    if request.node.get_closest_marker("live"):
        yield
        return

    import urllib.request

    def _forbidden(url, *args, **kwargs):
        raise AssertionError(
            "сеть в default-прогоне (тест обязан нести маркер live): "
            f"{url}")

    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)
    yield


# ── ТЗ-97 Q11: HOME подменён на весь прогон (дверь P7) ─────────────────────
#
# Сами правила — в `tests/p7_home_isolation.py` (без pytest), их проверяет
# tests/test_task97_q11_home_clean.py; здесь только применение.


@pytest.fixture(scope="session", autouse=True)
def _p7_isolated_home(request, tmp_path_factory):
    """Один HOME на прогон (не на тест): Qt-кэш тогда создаётся один раз,
    а страж ниже видит след всего набора, а не последнего теста."""
    if p7_home.live_run_selected(request.config.getoption("markexpr")):
        yield None
        return
    home = tmp_path_factory.mktemp("p7-home")
    old_home = os.environ.get("HOME")
    old_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["HOME"] = str(home)
    inherited = p7_home.child_import_paths(old_home or "")
    if inherited:
        # дети считают user-site по новому HOME и потеряли бы пакеты —
        # подробности в докстринге tests/p7_home_isolation.py
        kept = [p for p in (old_pythonpath or "").split(os.pathsep) if p]
        os.environ["PYTHONPATH"] = os.pathsep.join([*inherited, *kept])
    try:
        yield home
    finally:
        # Страж (Done when ТЗ-97 Q11): прогон всего набора не создал в
        # подменённом HOME ничего, кроме разрешённого. Падение здесь —
        # ошибка на teardown сессионной фикстуры: rc pytest != 0,
        # поэтому приёмка (проверка «код возврата 0») его видит.
        leftovers = p7_home.extra_entries(home)
        for name, value in (("HOME", old_home), ("PYTHONPATH", old_pythonpath)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        assert not leftovers, (
            f"прогон набора создал в подменённом HOME лишнее: {leftovers}\n"
            f"каталог прогона: {home}\n"
            f"разрешено: {sorted(p7_home.HOME_ALLOWED)}")
