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

ТЗ-80 A4: та же фраза в тексте ТЗ бывает и выданным разрешением, и
цитатой разбираемой ошибки. Решают кавычки — обратные (`…`) и/или
ёлочки («…»): обёрнутое вхождение разрешением не считается, строка,
начинающаяся с фразы, считается всегда.

Осознанный предел, чтобы следующий читатель не принял его за дыру:
ПРОДОЛЖЕНИЕ строки — пути на следующей после разрешения строке, где
самой фразы уже нет (так раньше делало ТЗ-73) — страж не ловит. Их не
видит и парсер, а угадывать, какой перечисленный список файлов был
намерением выдать право, значило бы краснить ТЗ на прозе.
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


def _is_quoted(line: str, pos: int) -> bool:
    """ТЗ-80 A4: то же самое слово может быть разрешением и может быть
    цитатой, разбираемой в тексте ТЗ. Разрешением считается вхождение,
    НЕ обёрнутое в обратные кавычки (`…`) и не сидящее внутри
    кавычек-ёлочек («…»); строка, начинающаяся с фразы, — разрешение
    всегда (у неё pos = 0, ни одна обёртка её не касается).

    Ложное разрешение такой строка всё равно не выдаёт: её по-прежнему
    не видит парсер, и проверка ниже её бы не приняла. Но краснота на
    цитате — это не «тихое право потеряно», а «о дефекте больше нельзя
    написать там же, где он разобран»."""
    before = line[:pos]
    if before.count("`") % 2 == 1:
        return True
    return before.count("\u00ab") > before.count("\u00bb")


def _claimed_paths(line: str) -> list[str]:
    """Пути, заявленные на строке как разрешённые: токены-файлы после
    каждого вхождения фразы, не спрятанного в кавычки. Строка без пути
    после фразы — проза (пояснение, цитата), а не притязание."""
    claims: list[str] = []
    for m in re.finditer(PHRASE, line):
        if _is_quoted(line, m.start()):
            continue
        claims += [t.group(0) for t in
                   PATH_TOKEN.finditer(line, m.end())]
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


# Дословный абзац вердикта координатора из первой версии ТЗ-80
# (commit `ca678a1`), из-за которого страж Z2 покраснел на цитате:
# строка объясняла дефект ТЗ-74, а не выдавала право. Перефразированием
# её выправил `f8534a4`; этот тест закрывает сам разрез.
VERDICT_QUOTING_THE_BROKEN_FORM = (
    "независимо нашла ровно этот дефект в очереди: в ТЗ-74 строка\n"
    "`РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md, GUIDE.md` делала `GUIDE.md`\n"
    "немым, в ТЗ-73 то же самое плюс перенос строки. Обе ТЗ починены\n"
    "координатором: теперь один путь — одна строка. Проверено парсером,\n"
    "все пути живые.\n"
    "Тот же разбор в кавычках-ёлочках: «РАЗРЕШЕНО ПРАВИТЬ: GUIDE.md».\n"
)


def test_a_quoted_broken_form_is_not_read_as_a_grant(tmp_path):
    """A4, зелёный случай: цитата сломанной формы внутри обратных
    кавычек или ёлочек — разбор дефекта, а не выданное разрешение.
    На прежнем `_claimed_paths` этот абзац красен (пути из кавычек
    считались притязанием), и написать в ТЗ о самой болезни было
    нельзя."""
    f = tmp_path / "TASK-80-verdict.md"
    f.write_text(VERDICT_QUOTING_THE_BROKEN_FORM, encoding="utf-8")
    assert _unaccepted(f) == [], _unaccepted(f)


def test_the_same_form_outside_quotes_is_still_red(tmp_path):
    """A4, красный случай того же разреза: как только та же строка
    перестаёт быть цитатой и начинается с фразы, путь из обратных
    кавычек снова не принимается парсером — страж красен и не имел
    права молчать."""
    f = tmp_path / "TASK-broken.md"
    f.write_text(
        "РАЗРЕШЕНО ПРАВИТЬ: `agent/CONTEXT.md, GUIDE.md`\n",
        encoding="utf-8")
    bad = _unaccepted(f)
    assert len(bad) == 1, bad
    assert bad[0][0] == "1", bad
    assert sorted(bad[0][2]) == ["GUIDE.md", "agent/CONTEXT.md"], bad


def test_the_flat_form_is_still_a_grant_after_a_quoted_one(tmp_path):
    """A4 не должен дать лазейку: строка, начинающаяся с фразы,
    остаётся притязанием даже рядом с цитатой, и путь, спрятанный в
    кавычки в НАСТОЯЩЕМ разрешении, по-прежнему красен."""
    f = tmp_path / "TASK-A4b.md"
    f.write_text(
        "В разборе: `РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md` — это цитата.\n"
        "РАЗРЕШЕНО ПРАВИТЬ: `agent/CONTEXT.md`\n",
        encoding="utf-8")
    bad = _unaccepted(f)
    assert len(bad) == 1, bad
    assert bad[0][0] == "2", bad
    assert bad[0][2] == ["agent/CONTEXT.md"], bad


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
