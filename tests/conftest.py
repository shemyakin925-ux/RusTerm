"""Общая изоляция окружения для всего набора (TASK-29 A1).

Ни один тест не читает настоящий ~/.rusterm.env: autouse-фикстура
ставит RUSTERM_ENV_FILE на пустой файл в tmp_path и вычищает все имена
ENV_NAMES из os.environ до теста; monkeypatch возвращает всё как было
после него. Тест, которому нужно значение, ставит его сам
(monkeypatch.setenv). Контракт load_env — писать в настоящий
os.environ — не меняется: тесты test_env.py продолжают это доказывать
уже со своим восстанавливающим fixture.
"""
from __future__ import annotations

import pytest

from rusterm import env as env_module


@pytest.fixture(autouse=True)
def _isolated_rusterm_env(tmp_path, monkeypatch):
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
