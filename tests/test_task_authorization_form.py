"""ТЗ-79 Z2: немое разрешение становится громким.

Класс дефекта: ТЗ выдаёт право править файл, `agent/p6_rule.sh` его не
видит, и исполнитель молча теряет возможность трогать названный файл —
три круга подряд (ТЗ-76, ТЗ-77, ТЗ-78) разрешение писалось маркдауном
и было немым, пока его не поймал отказ стража на приёмке.

Страж сверяет ТЗ с ПАРСЕРОМ, а не наоборот: `agent/p6_rule.sh` не
трогается, а его собственные команды воспроизводятся дословно —
`grep '^РАЗРЕШЕНО ПРАВИТЬ:'` (строка обязана начинаться с фразы) и
`grep -qF "РАЗРЕШЕНО ПРАВИТЬ: <path>"` (путь ищется фиксированной
подстрокой, поэтому обратные кавычки, `**` и висячий текст после
двоеточия путь уже не находят). Отдельный тест следит за самими
паттернами: изменит координатор парсер — страж покраснеет и заставит
перечитать, а не останется вежливым враньём.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
P6 = REPO / "agent" / "p6_rule.sh"
PHRASE = "РАЗРЕШЕНО ПРАВИТЬ"

# Те же две команды, что исполняет парсер (agent/p6_rule.sh:63 и :67).
ANCHOR_PATTERN = f"^{PHRASE}:"
PATH_TOKEN = re.compile(
    r"[\w][\w.\-/]*\.(?:py|md|sh|json|toml|ya?ml|txt|rs|csv|sql|html|cfg|ini)")


def _parser_lines(task_file: Path) -> list[str]:
    """Строки ТЗ, которые РЕАЛЬНО видит парсер: `grep '^РАЗРЕШЕНО
    ПРАВИТЬ:' <файл>` — тем же вызовом grep, что и p6_rule.sh. Код 1 у
    grep означает «совпадений нет», это не ошибка."""
    proc = subprocess.run(["grep", ANCHOR_PATTERN, str(task_file)],
                          capture_output=True, text=True)
    assert proc.returncode in (0, 1), proc.stderr
    return proc.stdout.splitlines()


def _claimed_paths(line: str) -> list[str]:
    """Пути, заявленные на строке как разрешённые: токены-файлы после
    каждого вхождения фразы. Строка без пути после фразы — проза
    (пояснение, цитата), а не притязание на разрешение."""
    claims: list[str] = []
    for pos in [m.start() for m in re.finditer(PHRASE, line)]:
        claims += [m.group(0) for m in
                   PATH_TOKEN.finditer(line, pos + len(PHRASE))]
    return claims


def _unaccepted(task_file: Path) -> list[tuple[str, str, list[str]]]:
    """Нарушения: (номер строки, текст строки, пути, которые парсер не
    принимает). Путь принят, только если он стоит в строке, видимой
    парсеру, как `РАЗРЕШЕНО ПРАВИТЬ: <путь>` — фиксированная
    подстрока, ровно как в `authorized()`."""
    accepted = _parser_lines(task_file)
    bad: list[tuple[str, str, list[str]]] = []
    for num, line in enumerate(
            task_file.read_text(encoding="utf-8").splitlines(), start=1):
        if PHRASE not in line:
            continue
        missing = [p for p in _claimed_paths(line)
                   if not any(f"{PHRASE}: {p}" in a for a in accepted)]
        if missing:
            bad.append((str(num), line, missing))
    return bad


def _live_task_file() -> Path | None:
    baton = json.loads((REPO / "agent" / "BATON.json").read_text(
        encoding="utf-8"))
    task = baton.get("task")
    path = REPO / task if task else None
    return path if path and path.is_file() else None


@pytest.mark.skipif(_live_task_file() is None,
                    reason="эстафета не называет файл ТЗ")
def test_authorized_lines_of_the_current_task_are_parseable():
    """Каждая строка действующего ТЗ, объявляющая разрешение, обязана
    быть в форме, которую принимает парсер. Красный называет номер
    строки, цитирует её и перечисляет пути, до которых парсер не
    дотянется."""
    task = _live_task_file()
    bad = _unaccepted(task)
    assert not bad, (
        f"{task.name}: разрешение написано формой, которую "
        f"agent/p6_rule.sh не видит — исполнитель молча теряет право "
        f"править эти файлы:\n"
        + "\n".join(f"  {task.name}:{n}: {line!r} — не принято: {paths}"
                    for n, line, paths in bad))


def test_markdown_form_from_task76_is_flagged(tmp_path):
    """Страж краснеет на маркдаунной форме ТЗ-76: та же строка, что
    выдавалась как разрешение три круга подряд, парсером не читается.
    Литерал, а не живой файл — ТЗ не правятся."""
    md = tmp_path / "TASK-76.md"
    md.write_text(
        "- **РАЗРЕШЕНО ПРАВИТЬ:** `tests/test_report_sections.py`\n",
        encoding="utf-8")
    bad = _unaccepted(md)
    assert len(bad) == 1, bad
    num, line, missing = bad[0]
    assert num == "1"
    assert "РАЗРЕШЕНО ПРАВИТЬ" in line
    assert missing == ["tests/test_report_sections.py"], missing
    assert _parser_lines(md) == [], "парсер всё-таки увидел строку"


def test_flat_form_is_accepted_and_prose_is_not_a_claim(tmp_path):
    """Зелёный случай той же проверки: плоская форма принимается,
    а проза с фразой (без пути после неё) притязанием не считается —
    иначе страж врал бы на пояснениях самого ТЗ-79."""
    ok = tmp_path / "TASK-79.md"
    ok.write_text(
        "РАЗРЕШЕНО ПРАВИТЬ: tests/test_report_sections.py\n"
        "РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md\n"
        "Проверено: `grep '^РАЗРЕШЕНО ПРАВИТЬ:'` берёт строку с начала\n"
        'и затем `grep -qF "РАЗРЕШЕНО ПРАВИТЬ: <path>"` — путь без кавычек\n',
        encoding="utf-8")
    assert _unaccepted(ok) == []


def test_two_paths_on_one_line_leave_the_second_unauthorized(tmp_path):
    """Полумера парсера, зафиксированная тестом: два пути через запятую
    в одной плоской строке — это разрешение ТОЛЬКО первого, второй
    `authorized()` не находит. Страж обязан покраснеть на втором."""
    one = tmp_path / "TASK-X.md"
    one.write_text(
        "РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md, GUIDE.md\n", encoding="utf-8")
    bad = _unaccepted(one)
    assert len(bad) == 1, bad
    assert bad[0][2] == ["GUIDE.md"], bad


def test_the_guard_still_matches_the_parser_it_emulates():
    """Z2 запрещает править парсер, но не запрещает следить, что
    страж эмулирует именно его. Обе команды должны стоять в
    agent/p6_rule.sh дословно; уедут — страж покраснеет и заставит
    сверить формы, а не молча разойтётся с парсером."""
    src = P6.read_text(encoding="utf-8")
    assert f"grep '{ANCHOR_PATTERN}'" in src, (
        "парсер больше не берёт разрешение грепом с начала строки — "
        "обновите форму, которую проверяет страж")
    assert 'grep -qF "РАЗРЕШЕНО ПРАВИТЬ: $1"' in src, (
        "authorized() больше не ищет путь фиксированной подстрокой — "
        "страж проверяет не ту форму")
