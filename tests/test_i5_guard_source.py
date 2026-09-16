"""ТЗ-37 I5: страж исполняется из коммита, а не из рабочего дерева.

Воспроизведение манёвра 95b669a end to end:
- правка agent/CONTEXT.md застейджена, агентский страж расширен
  ТОЛЬКО в рабочем дереве -> selfcheck красный и называет стража;
- то же расширение, но ЗАСТЕЙДЖЕННОЕ (задание разрешает строкой
  РАЗРЕШЕНО ПРАВИТЬ) -> зелёный, и в выводе видно, что исполнялась
  копия из index.

Оба случая гоняют настоящий bash agent/selfcheck.sh. Вложенный
прогон приёмки (selfcheck запускает pytest) пропускает сами тесты
I5 через переменную I5_NESTED, чтобы не рекурсироваться.

ТЗ-45 M1: модуль убирает за собой. Каждый тест возвращает стража и
agent/CONTEXT.md ровно в засталенное состояние — байты рабочего
дерева и блоб индекса, БЕЗ git checkout: именно checkout стирал
застейдженную правку исполнителя в 627a0dc. Отдельный случай: правка
стража, застейдженная ДО прогона модуля, переживает весь модуль
дословно и попадает в индекс без изменений.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
P6_GUARD = ROOT / "agent" / "p6_rule.sh"
CONTEXT_MD = ROOT / "agent" / "CONTEXT.md"

# ТЗ-43 K2: идентификатор прогона — генерируется при импорте модуля,
# то есть СВОЙ для каждого процесса pytest. Маркер, принесённый другим
# прогоном, несёт чужой session id и приёмку зелёной не делает.
DEMO_SESSION_ID = str(uuid.uuid4())


def _snapshot(path: Path):
    """ТЗ-45 M1: снять состояние файла ДО теста: байты рабочего дерева,
    режим и блоб индекса (git ls-files -s). HEAD здесь не участвует."""
    worktree = path.read_bytes()
    meta = subprocess.run(
        ["git", "ls-files", "-s", "--", path.relative_to(ROOT).as_posix()],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    if meta:
        return worktree, meta[0], meta[1]
    return worktree, None, None


def _restore(path: Path, worktree: bytes, mode: str | None,
             index_sha: str | None) -> None:
    """ТЗ-45 M1: вернуть ровно снятое — и дерево, и индекс.
    Восстановление идёт блобом через update-index --cacheinfo;
    git checkout запрещён: он стирал застейдженную правку (627a0dc)."""
    path.write_bytes(worktree)
    if index_sha:
        subprocess.run(
            ["git", "update-index", "--cacheinfo",
             f"{mode},{index_sha},{path.relative_to(ROOT).as_posix()}"],
            cwd=ROOT, capture_output=True, text=True, check=True)


# Расширение для зелёного случая: поведение то же (красные случаи
# стража остаются красными), но копию из index видно в выводе
# selfcheck. «Расширение» — поведение не меняется: добавляется
# строка-комментарий. Смысл случая — ЗАСТЕЙДЖЕННОЕ отличие рабочей
# копии от HEAD, а не поломка стража.
WIDENED = (P6_GUARD.read_text(encoding="utf-8")
           + "\n# i5 green case: staged widening\n")

# ТЗ-45 M1, сценарий 627a0dc: правка, которая УЖЕ в индексе до прогона
# модуля (своё незакоммиченное дело исполнителя), обязана пережить
# модуль дословно — её снимает и возвращает нижняя фикстура.
PRE_STAGED_EDIT = ("\n# ТЗ-45 M1: правка, застейдженная ДО прогона "
                   "модуля (сценарий 627a0dc)\n")
_PRE_MODULE = None


def _git(*argv: str, check: bool = True):
    return subprocess.run(["git", *argv], cwd=ROOT,
                          capture_output=True, text=True, check=check)


def _selfcheck(extra: dict | None = None):
    env = dict(os.environ)
    env.update(extra or {})
    return subprocess.run(["bash", "agent/selfcheck.sh"], cwd=ROOT,
                          env=env, capture_output=True, text=True)


def _nested() -> bool:
    return bool(os.environ.get("I5_NESTED"))


def _marker_path() -> Path:
    """ТЗ-45 M2: маркер демонстрации живёт в git-каталоге ЭТОГО дерева
    (git rev-parse --git-path), а не в общем /tmp: чужой прогон любой
    другой рабочей копии на той же машине больше не перезаписывает
    его между тестом модуля и sentinel (гонка круга 56: верификация
    в соседнем connected-дереве красила sentinel чужим session)."""
    out = subprocess.run(
        ["git", "rev-parse", "--git-path", "i5-demo-ran.json"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    path = Path(out.stdout.strip())
    return path if path.is_absolute() else (ROOT / path)


def _editmsg_read():
    """ТЗ-45 M3: отсутствие COMMIT_EDITMSG — законное состояние свежего
    подключённого дерева, а не ошибка. Возвращает (путь, прежний текст
    или None)."""
    path = Path(subprocess.run(
        ["git", "rev-parse", "--git-path", "COMMIT_EDITMSG"],
        cwd=ROOT, capture_output=True, text=True,
        check=True).stdout.strip())
    saved = path.read_text(encoding="utf-8") if path.exists() else None
    return path, saved


def _editmsg_restore(path: Path, saved: str | None) -> None:
    """ТЗ-45 M3: вернуть ровно то, что было: было отсутствие — вернуть
    отсутствие, а не пустой файл."""
    if saved is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(saved, encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def _guard_edit_staged_before_the_module():
    """ТЗ-45 M1: до всяких тестов в индекс кладётся СВОЯ правка стража —
    как у исполнителя в 627a0dc. Все случаи ниже отрабатывают поверх
    неё; до-модульное состояние снято и возвращается в конце модуля."""
    global _PRE_MODULE
    _PRE_MODULE = _snapshot(P6_GUARD)
    P6_GUARD.write_bytes(
        _PRE_MODULE[0] + PRE_STAGED_EDIT.encode("utf-8"))
    _git("add", "agent/p6_rule.sh")
    yield
    _restore(P6_GUARD, *_PRE_MODULE)


@pytest.fixture(autouse=True)
def _module_restores_what_it_touches():
    """ТЗ-45 M1: каждый тест модуля возвращает страж и CONTEXT.md ровно
    в засталенное состояние — байты дерева и блоб индекса. Прежняя
    уборка красного случая потеряла возврат CONTEXT.md в рабочее
    дерево — мусор «I5 red demo» оставался в файле после прогона."""
    saved = {p: _snapshot(p) for p in (P6_GUARD, CONTEXT_MD)}
    yield
    for path, state in saved.items():
        _restore(path, *state)


@pytest.fixture(scope="module", autouse=True)
def _demonstration_ran():
    """ТЗ-36 I8: замок с фиксированным путём мог протухнуть (SIGKILL,
    reboot) и молча выкидывать демонстрацию из любого прогона на хосте.
    Замок убран: рекурсию держит I5_NESTED (хук и зелёный случай), а
    этот маркер доказывает sentinel-тесту, что демонстрация ВЫПОЛНЕНА
    в текущем процессе. Путь — git-каталог дерева (_marker_path), не
    общий /tmp (ТЗ-45 M2)."""
    marker = _marker_path()
    marker.write_text(json.dumps({"pid": os.getpid(),
                                  "session": DEMO_SESSION_ID}),
                      encoding="utf-8")
    yield


@pytest.mark.skipif(_nested(), reason="вложенный прогон приёмки")
def test_i5_working_tree_widening_is_red_and_named(tmp_path):
    editmsg = None
    editmsg_saved = None
    try:
        CONTEXT_MD.write_text(CONTEXT_MD.read_text(encoding="utf-8")
                              + "\nI5 red demo\n", encoding="utf-8")
        _git("add", "agent/CONTEXT.md")
        P6_GUARD.write_text(WIDENED, encoding="utf-8")  # НЕ стейджится
        editmsg, editmsg_saved = _editmsg_read()
        Path(editmsg).write_text(
            "demo\n\nРАЗРЕШЕНИЕ-КОНТЕКСТА: demo\n", encoding="utf-8")
        result = _selfcheck({"I5_NESTED": "1"})
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "agent/p6_rule.sh" in combined, combined[-800:]
        assert "рабочем дереве" in combined, combined[-800:]
    finally:
        # страж и CONTEXT.md возвращает autouse-фикстура ТЗ-45 M1
        # (байты + блоб индекса); здесь только декларация коммита,
        # и только если она была объявлена (M3: отсутствие законно)
        if editmsg is not None:
            _editmsg_restore(editmsg, editmsg_saved)


@pytest.mark.skipif(_nested(), reason="вложенный прогон приёмки")
def test_i5_staged_and_authorised_widening_is_green(tmp_path):
    editmsg = None
    editmsg_saved = None
    try:
        P6_GUARD.write_text(WIDENED, encoding="utf-8")
        _git("add", "agent/p6_rule.sh")  # расширение ЗАСТЕЙДЖЕНО
        # файл задания из agent/BATON.json несёт
        # РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh
        editmsg, editmsg_saved = _editmsg_read()
        # реальное ожидаемое сообщение сохраняется и ДОПОЛНЯЕТСЯ
        # маркером; в свежем дереве основания нет — маркер кладётся
        # поверх пустой строки (M3)
        Path(editmsg).write_text(
            (editmsg_saved or "") + "\nРАЗРЕШЕНИЕ-КОНТЕКСТА: demo\n",
            encoding="utf-8")
        result = _selfcheck({"I5_NESTED": "1"})
        assert result.returncode == 0, (
            result.stdout[-1500:] + result.stderr[-800:])
        combined = result.stdout + result.stderr
        assert "p6_rule.sh исполняется из index" in combined
    finally:
        if editmsg is not None:
            _editmsg_restore(editmsg, editmsg_saved)


@pytest.mark.skipif(_nested(), reason="вложенный прогон приёмки")
def test_stale_single_flight_lock_does_not_skip_the_module(tmp_path):
    """ТЗ-36 I8: протухший замок старой схемы (pid мёртвого процесса)
    не влияет ни на что — замок убран, все случаи модуля собираются
    и выполняются: два случая I5 и уборочный тест ТЗ-45 M1."""
    import sys

    stale = Path(tempfile.gettempdir()) / "i5-demo-single-flight.lock"
    stale.write_text(json.dumps({"pid": 999999999}), encoding="utf-8")
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "tests/test_i5_guard_source.py"], cwd=ROOT,
            capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
        # все тесты модуля собираются к исполнению — ни замок, ни
        # skipif ни на что не влияют: 2 случая I5 + уборочный ТЗ-45 M1
        assert "tests/test_i5_guard_source.py: 4" in out.stdout, out.stdout
        assert "skipped" not in out.stdout, out.stdout
    finally:
        stale.unlink(missing_ok=True)


@pytest.mark.skipif(_nested(), reason="вложенный прогон приёмки")
def test_module_returns_guard_exactly_as_found():
    """ТЗ-45 M1: (1) сценарий 627a0dc — правка, застейдженная ДО
    прогона модуля, после всех случаев дословно в индексе; (2)
    самоутверждение уборки — модуль возвращает стража в до-модульное
    состояние, и `git status --porcelain` не показывает его ни в одном
    столбце."""
    staged_bytes = subprocess.run(
        ["git", "cat-file", "blob", ":agent/p6_rule.sh"], cwd=ROOT,
        capture_output=True, check=True).stdout
    assert PRE_STAGED_EDIT.encode("utf-8") in staged_bytes
    _restore(P6_GUARD, *_PRE_MODULE)
    out = _git("status", "--porcelain", "--", "agent/p6_rule.sh")
    assert out.stdout.strip() == "", out.stdout
