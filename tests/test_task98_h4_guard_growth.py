"""ТЗ-98 Х4: отслеженный страж `agent/p6_rule.sh` перестаёт расти.

Механика роста (измерена на живой истории): случай ТЗ-45 M1 пишет свою
правку в отслеженный страж и стейджит её, а снимает фикстура только в
конце модуля. Убитый посреди прогона процесс оставлял застейдженный
хвост ниже `exit 0`; пункт 13 приёмки смотрит только на `??` —
изменённый страж в него не попадал и уезжал в коммит, а следующий круг
дописывал второй хвост поверх первого (`WIDENED` строился от рабочего
файла).

Зубья:
1. `agent/p6_rule.sh` кончается `exit 0`, маркеров демонстрации в нём
   нет;
2. `selfcheck.sh` исполняет стража только из временной копии — ни
   записи в отслеженный файл, ни его стейджа;
3. хвост-мусор любого из четырёх порядков двух маркеров, застейдженный,
   возвращается к HEAD и деревом, и блобом индекса (porcelain пуст);
4. чужая правка самопочинкой не съедается — остаётся в дереве и в
   индексе;
5. чистый страж не перезаписывается (mtime цел, porcelain пуст);
6. расширение зелёного случая считается от HEAD: в дереве, оставшемся
   в хвосте, оно всё равно HEAD + ровно один маркер.

Песочница — свой git-репозиторий в `tmp_path` с копией настоящего
модуля-помощника: `tests/i5_guard_residue.py` не импортирует pytest,
поэтому его зовёт отдельный процесс. Настоящий `agent/acceptance.sh`
не запускается; `HOME` и `TMPDIR` указывают в песочницу (P7).

Вложенный прогон (`I5_NESTED=1`) модуль пропускает целиком — см.
`pytestmark` ниже: он seeded от рабочего отслеженного стража, а зелёный
случай I5 намеренно держит его расширенным ровно на время вложенной
приёмки.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD = REPO_ROOT / "agent" / "p6_rule.sh"
SELFCHECK = REPO_ROOT / "agent" / "selfcheck.sh"
HELPER_SOURCE = REPO_ROOT / "tests" / "i5_guard_residue.py"

from tests.i5_guard_residue import (GUARD_REL, GREEN_CASE_EDIT,
                                    LEAKED_GIT_ENV, PRE_STAGED_EDIT)


def _nested() -> bool:
    return bool(os.environ.get("I5_NESTED"))


# Зубья seeded from the tracked guard's CURRENT bytes, and the I5 green
# case deliberately writes + stages a widened guard, then nests a real
# selfcheck while it stands. Inside that window the facts teeth 1/3/6
# assert are false by design, not by defect — so the module skips when
# nested, the same precedent `test_i5_guard_source.py` sets for its own
# cases. Non-nested runs (relay.py verify, a plain selfcheck) run it all.
pytestmark = pytest.mark.skipif(
    _nested(),
    reason="вложенный прогон приёмки: демонстрация I5 держит страж "
           "намеренно расширенным")


def _env(sbx: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in LEAKED_GIT_ENV}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                "HOME": str(sbx / "home"), "TMPDIR": str(sbx / "tmp")})
    return env


def _git(sbx: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=sbx, capture_output=True,
                         text=True, env=_env(sbx))
    assert out.returncode == 0, f"git {' '.join(args)}: {out.stderr[-400:]}"
    return out.stdout


def _sandbox(tmp_path: Path) -> Path:
    """HEAD песочницы = тот самый страж, который едет в коммите Х4, и
    копия помощника рядом — чтобы чинил он песочницу, а не репозиторий
    исполнителя."""
    sbx = tmp_path / "sbx"
    (sbx / "agent").mkdir(parents=True)
    (sbx / "tests").mkdir(parents=True)
    (sbx / "home").mkdir()
    (sbx / "tmp").mkdir()
    (sbx / GUARD_REL).write_text(GUARD.read_text(encoding="utf-8"),
                                 encoding="utf-8")
    (sbx / "tests" / "i5_guard_residue.py").write_text(
        HELPER_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    _git(sbx, "init", "-q")
    _git(sbx, "add", GUARD_REL, "tests/i5_guard_residue.py")
    _git(sbx, "commit", "-qm", "база песочницы")
    return sbx


def _plant(sbx: Path, residue: str, staged: bool = True) -> str:
    """Страж = HEAD + хвост; вернуть посаженный текст."""
    planted = _git(sbx, "show", f"HEAD:{GUARD_REL}") + residue
    (sbx / GUARD_REL).write_text(planted, encoding="utf-8")
    if staged:
        _git(sbx, "add", GUARD_REL)
    return planted


def _run(sbx: Path, code: str) -> str:
    """Вызвать помощника внутри песочницы отдельным процессом."""
    out = subprocess.run([sys.executable, "-c", code], cwd=sbx,
                         capture_output=True, text=True, env=_env(sbx))
    assert out.returncode == 0, out.stdout + out.stderr
    return out.stdout


IMPORT = "import sys; sys.path.insert(0, 'tests'); " \
         "from pathlib import Path; import i5_guard_residue as m; "


def test_guard_ends_at_exit_zero_with_no_residue():
    """Зуб 1: хвоста демонстрации в коммите больше нет."""
    text = GUARD.read_text(encoding="utf-8")
    assert text.rstrip().splitlines()[-1] == "exit 0", text[-200:]
    assert "i5 green case" not in text, text[-200:]
    assert "застейдженная ДО прогона" not in text, text[-200:]


def test_selfcheck_runs_only_a_temp_copy_of_the_guard():
    """Зуб 2 (второй bullet Х4): демонстрация в selfcheck.sh не трогает
    отслеженный файл. Измерено: все три стража извлекаются в
    `mktemp -d` и сгорают по trap; ни записи, ни стейджа стража."""
    text = SELFCHECK.read_text(encoding="utf-8")
    assert "GUARD_DIR=$(mktemp -d" in text
    assert 'git show ":$guard" > "$GUARD_DIR/$base"' in text
    assert 'git show "HEAD:$guard" > "$GUARD_DIR/$base"' in text
    assert 'rm -rf "$GUARD_DIR"' in text
    assert not re.search(r">\s*['\"]?agent/p6_rule\.sh", text), \
        "selfcheck.sh пишет в отслеженный страж"
    assert not re.search(r"git add[^\n]*p6_rule\.sh", text), \
        "selfcheck.sh стейджит отслеженный страж"


@pytest.mark.parametrize("residue", [
    GREEN_CASE_EDIT,
    PRE_STAGED_EDIT,
    GREEN_CASE_EDIT + PRE_STAGED_EDIT,
    PRE_STAGED_EDIT + GREEN_CASE_EDIT,
], ids=["green", "pre-staged", "green+pre", "pre+green"])
def test_residue_returns_to_head(tmp_path, residue):
    """Зуб 3: застейдженный мусор любого порядка возвращается к HEAD —
    байты дерева и блоб индекса; porcelain пуст."""
    sbx = _sandbox(tmp_path)
    _plant(sbx, residue)
    assert _git(sbx, "status", "--porcelain", "--", GUARD_REL).strip(), \
        "посадка обязана была оставить след"
    out = _run(sbx, IMPORT + "print('HEALED', m.reconcile(Path('.')))")
    assert "HEALED True" in out, out
    head = _git(sbx, "show", f"HEAD:{GUARD_REL}")
    assert (sbx / GUARD_REL).read_text(encoding="utf-8") == head
    assert _git(sbx, "status", "--porcelain", "--", GUARD_REL) == ""
    assert _git(sbx, "diff", "--cached", "--name-only", "--",
                GUARD_REL) == ""


def test_foreign_edit_survives_reconcile(tmp_path):
    """Зуб 4: право возвращать — только у своих маркеров. Правку,
    которой среди них нет, прогон оставляет и в дереве, и в индексе."""
    sbx = _sandbox(tmp_path)
    foreign = "\n# чужая правка: разрешение координатора\n"
    planted = _plant(sbx, foreign + GREEN_CASE_EDIT)
    out = _run(sbx, IMPORT + "print('HEALED', m.reconcile(Path('.')))")
    assert "HEALED False" in out, out
    assert (sbx / GUARD_REL).read_text(encoding="utf-8") == planted
    assert _git(sbx, "status", "--porcelain", "--", \
                GUARD_REL).strip() == f"M  {GUARD_REL}"


def test_clean_guard_is_not_rewritten(tmp_path):
    """Зуб 5: на чистом страже самопочинка молчит и ничего не пишет —
    иначе каждый прогон трогал бы индекс перед коммитом."""
    sbx = _sandbox(tmp_path)
    before = (sbx / GUARD_REL).stat()
    out = _run(sbx, IMPORT + "print('HEALED', m.reconcile(Path('.')))")
    assert "HEALED False" in out, out
    assert _git(sbx, "status", "--porcelain", "--", GUARD_REL) == ""
    after = (sbx / GUARD_REL).stat()
    assert after.st_mtime_ns == before.st_mtime_ns


def test_widening_is_built_from_head_not_the_dirty_tree(tmp_path):
    """Зуб 6: `WIDENED` строился от рабочего файла — осевший хвост
    удваивался каждый круг. Теперь расширение = HEAD + ровно один
    маркер, даже когда рабочее дерево в хвосте (и он не застейджен)."""
    sbx = _sandbox(tmp_path)
    _plant(sbx, GREEN_CASE_EDIT + PRE_STAGED_EDIT, staged=False)
    out = _run(sbx, IMPORT +
               "head = m.head_guard(Path('.'))[2]; w = m.widened(Path('.')); "
               "print('FROM_HEAD', w == head + m.GREEN_CASE_EDIT); "
               "print('MARKERS', w.count('i5 green case'))")
    assert "FROM_HEAD True" in out, out
    assert "MARKERS 1" in out, out
