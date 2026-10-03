"""ТЗ-103 N1: барьер упоминаний читает только ТЕМУ сообщения.

Решение координатора по пункту 3 из спорных REPORT-102 (вариант (a)):
обещание живёт в первой строке сообщения, а ссылка на файл стража в теле
— это цитата. Публикованный коммит M1 (49c6320) пример ровно такой формы:
в теме имени стража нет, в теле строкой «красный до правки зуб на страж
agent/p1_rule.sh из I5» описывается что было, и барьер обязан молчать.

git revert копирует тему отменяемого коммита, поэтому «Revert "…
p6_rule.sh …» остаётся покрытым: обещание в теме — страж в составе.

Черновики — в tmp_path (соседний test_task102_m2_mention_filename.py
объясняет, почему не в tests/).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "agent" / "check_mention.sh"
NO_GUARD = ["tests/test_x.py", "rusterm/core/snapshot.py"]

# подлинная форма из тела 49c6320: цитата имени стража в описании
M1_BODY = (
    "ТЗ-102 M1: цена умножается только на свежее число акций\n"
    "\n"
    "Решение координатора по пункту 1 из спорных REPORT-97.\n"
    "- Починка соседних строк (утверждения не удалены и не ослаблены):\n"
    "  красный до правки зуб на страж agent/p1_rule.sh из I5 — известный\n"
    "  след неотслеживаемого файла, исчез после git add.\n"
)


def _run(tmp_path: Path, message: str,
         files: list[str]) -> subprocess.CompletedProcess:
    msg = tmp_path / "msg.txt"
    lst = tmp_path / "files.txt"
    msg.write_text(message, encoding="utf-8")
    lst.write_text("\n".join(files) + "\n", encoding="utf-8")
    return subprocess.run(["bash", str(CHECK), str(msg), str(lst)],
                          capture_output=True, text=True)


def test_body_citation_without_the_guard_is_green(tmp_path):
    """Цитата в теле — не обещание: тот самый 49c6320 без стража в
    составе зелёный. До правки — красный (барьер читал всё сообщение)."""
    result = _run(tmp_path, M1_BODY, NO_GUARD)
    assert result.returncode == 0, result.stdout


def test_body_citation_of_both_guards_is_green(tmp_path):
    """Попарность в теле не срабатывает: названы оба стража, в составе
    ни одного — и не должно быть."""
    message = ("ТЗ-103 N1: барьер видит тему\n"
               "\n"
               "В теле упомянуты p1_rule.sh и agent/p6_rule.sh как\n"
               "обстоятельства прежних кругов.\n")
    assert _run(tmp_path, message, NO_GUARD).returncode == 0


def test_subject_naming_guard_without_the_guard_is_red(tmp_path):
    """Тема обещает правку стража — страж обязан в составе."""
    result = _run(tmp_path,
                  "ТЗ-103 N1: правка p6_rule.sh — только тема\n"
                  "тело не важно\n",
                  NO_GUARD)
    assert result.returncode != 0
    assert "agent/p6_rule.sh" in result.stdout, result.stdout


def test_subject_naming_guard_with_the_guard_is_green(tmp_path):
    assert _run(tmp_path,
                "ТЗ-103 N1: правка p6_rule.sh — только тема\n",
                NO_GUARD + ["agent/p6_rule.sh"]).returncode == 0


def test_pairwise_still_holds_on_the_subject(tmp_path):
    """Назван в теме один страж, уехал соседний — обещание без
    исполнения: переход на тему не отменяет попарности."""
    result = _run(tmp_path,
                  "ТЗ-44 L1: p1_rule.sh читает индекс коммита\n"
                  "вместе с agent/p6_rule.sh в теле как справку\n",
                  NO_GUARD + ["agent/p6_rule.sh"])
    assert result.returncode != 0
    assert "agent/p1_rule.sh" in result.stdout, result.stdout


def test_revert_subject_stays_covered(tmp_path):
    """git revert копирует тему: отмена коммита стража без стража в
    составе по-прежнему красный."""
    result = _run(tmp_path,
                  'Revert "ТЗ-103 N1: правка p6_rule.sh — только тема"\n'
                  "\n"
                  'This reverts commit 0123456789abcdef0123456789abcdef'
                  "01234567.\n",
                  NO_GUARD)
    assert result.returncode != 0
    assert "agent/p6_rule.sh" in result.stdout, result.stdout


def test_revert_subject_with_the_guard_is_green(tmp_path):
    result = _run(tmp_path,
                  'Revert "ТЗ-103 N1: правка p6_rule.sh — только тема"\n',
                  ["agent/p6_rule.sh"])
    assert result.returncode == 0, result.stdout


def test_single_line_message_without_trailing_newline(tmp_path):
    """Одна строка без перевода — она же тема: красным обязана остаться
    и в этом виде (чтение темы не теряет последнюю строку без \\n)."""
    msg = tmp_path / "msg.txt"
    lst = tmp_path / "files.txt"
    msg.write_text("правка p6_rule.sh", encoding="utf-8")  # без \n
    lst.write_text("\n".join(NO_GUARD) + "\n", encoding="utf-8")
    res = subprocess.run(["bash", str(CHECK), str(msg), str(lst)],
                         capture_output=True, text=True)
    assert res.returncode != 0, res.stdout


def test_empty_subject_is_green(tmp_path):
    """Пустое сообщение (например, --allow-empty-message) не может
    ничего обещать."""
    assert _run(tmp_path, "", NO_GUARD).returncode == 0
