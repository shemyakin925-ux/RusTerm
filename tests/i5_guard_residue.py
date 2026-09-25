"""ТЗ-98 Х4: отслеженный страж `agent/p6_rule.sh` перестаёт расти.

Модуль НЕ импортирует pytest — самопочинку вызывает отдельный процесс
(и песочница, и фикстура `tests/test_i5_guard_source.py`), а тянуть
ради этого всю приёмку нельзя.

Как файл рос: случай ТЗ-45 M1 пишет свою правку в отслеженный страж и
стейджит её, а снимает фикстура только в конце модуля. Убитый посреди
прогона процесс оставлял застейдженный хвост ниже `exit 0`; пункт 13
приёмки смотрит только на `??`, поэтому изменённый страж уезжал в
коммит молча, а следующий круг дописывал второй хвост поверх первого.

Отсюда два правила:
- расширение зелёного случая считается от блоба HEAD, а не от рабочего
  файла — осевший хвост не удваивается (`widened`);
- перед до-модульным снимком страж возвращается к HEAD, если отличается
  от него ТОЛЬКО своими маркерами (`reconcile`). Чужую правку не
  трогаем: её возвращает только владелец.

`git checkout` не используется нигде: он стирает застейдженное дело
исполнителя (627a0dc, ТЗ-45 M1).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

GUARD_REL = "agent/p6_rule.sh"

# Маркеры, которые демонстрация кладёт СТРОГО в конец файла ниже
# `exit 0`. Поэтому они и есть весь мусор, который прогон вправе
# оставить в отслеженном страже.
PRE_STAGED_EDIT = ("\n# ТЗ-45 M1: правка, застейдженная ДО прогона "
                   "модуля (сценарий 627a0dc)\n")
GREEN_CASE_EDIT = "\n# i5 green case: staged widening\n"
RESIDUE_EDITS = (PRE_STAGED_EDIT, GREEN_CASE_EDIT)

# Те же переменные, что чистит `tests/test_i5_guard_source.py`: хук
# даёт GIT_INDEX_FILE на .lock индекс коммита, а в связанном дереве ещё
# и абсолютный GIT_DIR — снимок снялся бы из одного индекса, а возврат
# записался в другой (ТЗ-46).
LEAKED_GIT_ENV = ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
                  "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")


def _git(root: Path, *argv: str, check: bool = False):
    env = {k: v for k, v in os.environ.items() if k not in LEAKED_GIT_ENV}
    return subprocess.run(["git", *argv], cwd=str(root),
                          capture_output=True, text=True, check=check,
                          env=env)


def head_guard(root: Path) -> tuple[str, str, str] | None:
    """(режим, sha, текст) стража из HEAD; None — если файла там нет
    либо он нечитается как UTF-8: тогда чинить нечем и нельзя."""
    listed = _git(root, "ls-tree", "HEAD", "--", GUARD_REL)
    if listed.returncode != 0 or not listed.stdout.strip():
        return None
    meta = listed.stdout.split("\t", 1)[0].split()
    if len(meta) < 3:
        return None
    shown = _git(root, "show", f"HEAD:{GUARD_REL}")
    if shown.returncode != 0:
        return None
    return meta[0], meta[2], shown.stdout


def strip_residue(text: str) -> str:
    """Снять с конца все подряд маркеры демонстрации."""
    changed = True
    while changed:
        changed = False
        for edit in RESIDUE_EDITS:
            if text.endswith(edit):
                text = text[:-len(edit)]
                changed = True
    return text


def widened(root: Path) -> str:
    """Расширение для зелёного случая: страж из HEAD плюс одна
    строка-комментарий — поведение стража не меняется, но в выводе
    selfcheck видно, что исполнялась копия из index. От HEAD, а не от
    рабочего файла, иначе осевший хвост удваивался бы каждый прогон."""
    head = head_guard(root)
    base = head[2] if head else (root / GUARD_REL).read_text(encoding="utf-8")
    return base + GREEN_CASE_EDIT


def reconcile(root: Path) -> bool:
    """Вернуть стража к HEAD, если он отличается от HEAD только
    своими маркерами; True — если что-то вернули.

    Вызывается ДО до-модульного снимка: иначе хвост попал бы в снимок
    и фикстура вернула бы мусор обратно. Дерево и индекс правятся
    раздельно: байты файла и блоб индекса через update-index
    --cacheinfo. Файл, уже совпадающий с HEAD (и в дереве, и в
    индексе), не перезаписывается вовсе.
    """
    head = head_guard(root)
    if head is None:
        return False
    mode, sha, blob = head
    path = root / GUARD_REL
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if strip_residue(text) != blob:
        return False
    staged = _git(root, "rev-parse", f":{GUARD_REL}")
    if text == blob and staged.returncode == 0 and staged.stdout.strip() == sha:
        return False
    path.write_text(blob, encoding="utf-8")
    if staged.returncode == 0:
        _git(root, "update-index", "--cacheinfo",
             f"{mode},{sha},{GUARD_REL}")
    return True
