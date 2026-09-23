"""TASK-12 Y6: секции отчёта — машинная проверка вместо прозы.

Три задачи подряд просили в прозе писать споры в `## Disputed` — и три
раза раздел оставался пустым при живых спорах в других местах. Теперь
проверяет машина: отчёт, названный в agent/STATE.json ("report"),
обязан нести все пять секций; строки, начинающиеся с DISPUTED, живут
только внутри `## Disputed`; в `## HANDOFF` не осталось шаблонных
заполнителей. Пустой `## Disputed` легитимен — ловится перемещённый
спор, а не его отсутствие.

ТЗ-46 N1: заполнители ищутся в ПОСЛЕДНЕЙ секции, чей заголовок
начинается с HANDOFF, — финальный блок может называться
«## HANDOFF (FINAL …)», и именно он решает; промежуточный блок без
суффикса стража не устраивает.

ТЗ-62 G4 (BACKLOG B38): последний HANDOFF не должен ПРОТИВОРЕЧИТЬ
ветке. Если он называет пункт несделанным («Items not done», «не
сделан»), а коммит с этим пунктом на ветке есть — красный с именами
пункта и коммита. Правило одной строкой живёт в agent/PROTOCOL.md §5.

ТЗ-80 A1 (правило этого файла): **страж не вправе зависеть от того,
сколько кругов прошло после его написания.** Любое усечение истории
здесь задаётся номером круга, а не положением головы ветки: тест,
написанный в круге N, обязан давать тот же результат в круге N+100.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

REQUIRED_SECTIONS = ("Done", "Blocked", "What not to trust", "Disputed",
                     "HANDOFF")


def _report_text() -> str:
    state = json.loads(
        (REPO / "agent" / "STATE.json").read_text(encoding="utf-8"))
    return (REPO / state["report"]).read_text(encoding="utf-8")


def _sections(text: str) -> dict[str, list[str]]:
    """{имя секции '## X': строки до следующего '## '} — кроме строк
    самой шапки до первой секции."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        header = re.match(r"^## (.+?)\s*$", line)
        if header:
            # ТЗ-76 W2: повторённый заголовок «## HANDOFF» — НОВАЯ
            # секция, а не продолжение прежней. setdefault сливал все
            # промежуточные HANDOFF в один список, и правило «решает
            # последний» работало лишь через уникальный суффикс
            # (FINAL …). Одноимённые блоки нумеруются, чтобы
            # _handoff_section видел именно последний из них.
            name = header.group(1).strip()
            current = name
            dup = 2
            while current in sections:
                current = f"{name} #{dup}"
                dup += 1
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _handoff_section(text: str) -> list[str]:
    """ТЗ-46 N1: последняя секция, чей заголовок НАЧИНАЕТСЯ с HANDOFF
    (регистр как есть). Финальный HANDOFF может нести суффикс
    «(FINAL …)» — проверять надо именно его, а не промежуточный блок
    без суффикса: иначе смена может закончиться блоком из одних
    заполнителей, и страж этого не увидит."""
    found: list[str] = []
    for name, lines in _sections(text).items():
        if name.startswith("HANDOFF"):
            found = lines
    return found


def test_report_carries_every_required_section():
    sections = _sections(_report_text())
    missing = [name for name in REQUIRED_SECTIONS if name not in sections]
    assert not missing, f"нет секций: {missing}"


def test_disputed_lines_live_only_in_disputed_section():
    """Строка, начинающаяся с DISPUTED (без учёта регистра, после
    снятия маркеров списка), допустима только внутри ## Disputed.
    Вынести спор — значит записать его в секцию; пункт Done может
    ссылаться на него, но не тащить спор в себе."""
    text = _report_text()
    sections = _sections(text)
    current: str | None = None
    misplaced: list[str] = []
    for line in text.splitlines():
        header = re.match(r"^## (.+?)\s*$", line)
        if header:
            current = header.group(1).strip()
            continue
        marker = line.lstrip(" -*").strip()
        if marker.upper().startswith("DISPUTED") and current != "Disputed":
            misplaced.append(line)
    assert not misplaced, (
        f"DISPUTED вне ## Disputed (перенесите в секцию): {misplaced}; "
        f"в самой секции сейчас {len(sections.get('Disputed', []))} строк")


def test_handoff_carries_real_values_not_placeholders():
    handoff = "\n".join(_handoff_section(_report_text()))
    assert handoff.strip(), "секция ## HANDOFF пуста"
    for placeholder in ("N passed", "M skipped", "<"):
        assert placeholder not in handoff, (
            f"шаблонный заполнитель {placeholder!r} остался в HANDOFF")


def test_final_handoff_full_of_placeholders_reds_the_guard(monkeypatch):
    """ТЗ-46 N1, красный случай (временный текст, не живой отчёт):
    промежуточный ## HANDOFF заполнен честно, финальный
    ## HANDOFF (FINAL …) — из одних заполнителей. Страж обязан
    краснеть по финальному блоку и называть заполнитель."""
    text = (
        "# REPORT\n"
        "## Done\n"
        "- ok\n"
        "## HANDOFF\n"
        "Status: PARTIAL, всё честно, 12 passed\n"
        "## HANDOFF (FINAL — supersedes the interim values above)\n"
        "Status: N passed, M skipped\n"
        "Items done: <fill me>\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "_report_text",
                        lambda: text)
    with pytest.raises(AssertionError) as exc:
        test_handoff_carries_real_values_not_placeholders()
    message = str(exc.value)
    # страж падает на ПЕРВОМ заполнителе финального блока и зовёт его
    assert "N passed" in message, message


def test_honest_final_handoff_after_interim_passes(monkeypatch):
    """ТЗ-46 N1, зелёный случай того же разреза: промежуточный блок и
    честный финальный — страж зеленеет, interim-блок не проверяется."""
    text = (
        "# REPORT\n"
        "## HANDOFF\n"
        "Status: PARTIAL\n"
        "## HANDOFF (FINAL — supersedes the interim values above)\n"
        "Status: DONE, всё доведено до коммита\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "_report_text",
                        lambda: text)
    test_handoff_carries_real_values_not_placeholders()


# ── ТЗ-62 G4: последний HANDOFF не противоречит ветке ───────────────────

def _claimed_undone_ids(handoff: str) -> list[str]:
    """Пункты, которые последний HANDOFF называет несделанными:
    строки «Items not done» / «не сделан», идентификаторы вида буква
    + номер (E1, F2, G4...)."""
    ids: list[str] = []
    for line in handoff.splitlines():
        low = line.lower()
        if "items not done" in low or "не сделан" in low:
            ids += re.findall(r"\b[A-Z]\d+\b", line)
    return ids


def _commit_for_items(ids: list[str], round_no: int) -> dict[str, str]:
    """Коммиты ЭТОГО круга, в теме которых стоит пункт:
    {'F2': '<sha> <тема>'}. Круг ограничивает обзор: границы — коммит
    эстафеты «Эстафета: круг <N>», номера не уникальны между задачами
    (ТЗ-35 тоже имела G4/G5)."""
    if not ids:
        return {}
    proc = subprocess.run(
        ["git", "log", "--format=%h %s"], cwd=REPO,
        capture_output=True, text=True, check=True)
    lines = proc.stdout.splitlines()
    marker = f"Эстафета: круг {round_no},"
    end = next((i for i, ln in enumerate(lines) if marker in ln), None)
    if end is None:
        return {}
    found: dict[str, str] = {}
    for line in lines[:end]:
        sha, _, subject = line.partition(" ")
        for iid in ids:
            if iid not in found and re.search(rf"\b{iid}\b", subject):
                found[iid] = line
    return found


def _baton_round() -> int:
    baton = json.loads((REPO / "agent" / "BATON.json").read_text(
        encoding="utf-8"))
    return int(baton.get("round", 0))


def _round_under_review() -> int:
    """ТЗ-79 Z1: номер круга, чью РАБОТУ описывает отчёт.

    Пока ход у исполнителя, это текущий круг. Но `hand` увеличивает
    номер, и во время приёмки у координатора текущий круг — уже его
    собственный, а отчёт описывает предыдущий. Без этой поправки L3
    искал пункты отчёта в круге, где их заведомо нет, и краснел у
    координатора, оставаясь зелёным у исполнителя."""
    baton = json.loads((REPO / "agent" / "BATON.json").read_text(
        encoding="utf-8"))
    rnd = int(baton.get("round", 0))
    return rnd - 1 if baton.get("holder") == "coordinator" else rnd


def test_last_handoff_does_not_call_committed_items_undone():
    """G4: если последний HANDOFF называет пункт несделанным, а
    коммит с этим пунктом на ветке есть — красный с именами пункта
    и коммита. Соглашение «последний HANDOFF отменяет предыдущие» —
    PROTOCOL §5 (B38)."""
    handoff = "\n".join(_handoff_section(_report_text()))
    committed = _commit_for_items(_claimed_undone_ids(handoff),
                                  _baton_round())
    assert not committed, (
        "последний HANDOFF зовёт несделанным то, что уже закоммичено "
        f"в этом круге: {committed}")


def test_stale_report61_handoff_reds_the_guard():
    """Красная демонстрация на настоящей лжи круга 76: interim-HANDOFF
    REPORT-61 называл F2-F4 несделанными, пока они коммитились тем же
    кругом. Текст зафиксирован литералом — живой отчёт уже починен."""
    stale = ("Status: PARTIAL (F1 done; F2-F4 ahead)\n"
             "Arrival state: task taken round 76 on 008aded, selfcheck green\n"
             "Items done: F1\n"
             "Items not done: F2 three-face cross-check, F3 window at "
             "volume, F4 KR door\n")
    ids = _claimed_undone_ids(stale)
    assert sorted(ids) == ["F2", "F3", "F4"], ids
    committed = _commit_for_items(ids, 76)
    assert set(committed) == {"F2", "F3", "F4"}, committed


def _l3_missing(done_ids: list[str], log_text: str,
                staged: list[str], round_no: int | None = None) -> list[str]:
    """Ядро L3 (ТЗ-66 L3, зубы — ТЗ-76 W1; граница круга — ТЗ-78 Y1):
    те пункты из «Items done», у которых нет коммита КРУГА, трогающего
    что-то кроме tests/.

    Разделитель блоков — %x1e, а не пустая строка: `--name-only` ставит
    пустую строку МЕЖДУ темой и списком файлов, поэтому деление по
    пустой строке делало первой строкой блока ИМЯ ФАЙЛА, тема не
    совпадала никогда, и страж проверял только staged-фолбэк (ТЗ-75,
    Disputed: приёмка 11/13 на чистом дереве).

    `staged` — список файлов индекса; фолбэк ТЗ-66 L2 (пункт
    материализуется этим же коммитом) включается только когда среди них
    есть нетестовый. Пустой список отключает фолбэк — так делают его в
    тестах-зубах, чтобы вырожденность парсера не прикрывал живая правка
    индекса.

    `round_no` (ТЗ-78 Y1): номер текущего круга из agent/BATON.json.
    Коммиты старше границы «Эстафета: круг <round_no>,» не имеют права
    закрывать пункт — идентификаторы пунктов между ТЗ повторяются
    (ТЗ-53 тоже писал «W3» в теме). Граница та же, что у G4
    (_commit_for_items): если маркера в логе нет, в этом круге ещё нет
    ни одного коммита, и любой «done» остаётся незакрытым (folds into
    `missing` — staged-фолбэк решает исход)."""
    named: dict[str, bool] = {}
    marker_seen = False
    work_seen = False
    for block in log_text.split("\x1e"):
        lines_ = [l for l in block.strip().splitlines() if l.strip()]
        if not lines_:
            continue
        sha_subject = lines_[0]
        # ТЗ-79 Z1 (починка границы ТЗ-78 Y1). Работа круга N лежит
        # МЕЖДУ маркером «Эстафета: круг N» и маркером круга N+1.
        # Прежнее правило упиралось в маркер round_no и собирало всё,
        # что НОВЕЕ его, — это верно, пока ход у исполнителя. Но после
        # hand маркер следующего круга становится самым свежим
        # коммитом, работа оказывается ПОД ним, и окно схлопывалось в
        # пустоту: страж был зелёным у исполнителя и красным у
        # координатора, то есть ровно там, где идёт приёмка.
        # Поэтому верхняя граница — маркер круга round_no + 1, если он
        # уже есть; нижняя, как и была, — маркер самого round_no.
        if round_no is not None and "Эстафета: круг" in sha_subject:
            if f"Эстафета: круг {round_no + 1}," in sha_subject \
                    and not work_seen:
                continue
            marker_seen = True
            break
        work_seen = True
        files = [l for l in lines_[1:] if l and not l.startswith("Эстафета")]
        for iid in done_ids:
            if re.search(rf"\b{iid}\b", sha_subject):
                named[iid] = named.get(iid, False) or any(
                    not f.startswith("tests/") for f in files if "/" in f
                    or f.endswith(".py") or f.endswith(".md"))
    if round_no is not None and not marker_seen:
        named = {}
    missing = [iid for iid in done_ids if not named.get(iid)]
    if missing and any(not f.startswith("tests/") for f in staged):
        missing = []
    return missing


def _git_log_name_only() -> str:
    return subprocess.run(
        ["git", "log", "--format=%x1e%h %s", "--name-only"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout


def test_done_items_have_code_commits_in_round():
    """ТЗ-66 L3: пункт из «Items done» обязан быть назван коммитом
    круга, который трогает не только tests/ — отчёт отвечает за свои
    слова реализацией, а не декларацией."""
    handoff = "\n".join(_handoff_section(_report_text()))
    done_ids: list[str] = []
    for line in handoff.splitlines():
        if "items done" in line.lower():
            done_ids += re.findall(r"\b[A-Z]\d+\b", line)
    if not done_ids:
        pytest.skip("в отчёте нет пунктов Items done")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=REPO,
        capture_output=True, text=True).stdout.splitlines()
    missing = _l3_missing(done_ids, _git_log_name_only(), staged,
                          round_no=_round_under_review())
    assert not missing, (
        f"пункты {missing} объявлены сделанными, но коммита круга с "
        f"реализацией (не только tests/) не найдено")



# ── ТЗ-76 W1: зубы у L3 ─────────────────────────────────────────────────

# Форма вывода `git log --format=%x1e%h %s --name-only`: разделитель
# %x1e, тема, ПУСТАЯ СТРОКА, список файлов. Литерал, а не живой прогон:
# текст не должен меняться вместе с историей ветки.
FAKE_LOG = (
    "\x1e1111111 ТЗ-76 Q7: окно читает историю по периоду меры\n"
    "\n"
    "rusterm/desktop/data.py\n"
    "tests/test_desktop_history.py\n"
    "\x1e2222222 Эстафета: круг 101, ход у executor\n"
    "\n"
    "agent/BATON.json\n"
)


def test_l3_finds_the_item_by_subject_with_files_attached():
    """Зубы: Q7 закрыт коммитом с кодом — страж зелёный на настоящем
    формате. Дегенерация парсера (деление по пустой строке, как было до
    починки) этот же текст читает иначе и тест краснеет."""
    assert _l3_missing(["Q7"], FAKE_LOG, []) == []


def test_blank_line_split_leaves_the_subject_block_without_files():
    """Почему прежний парсер был пустым: при `split("\\n\\n")` блок,
    где стоит тема, оказывается ОДНОСТРОЧНЫМ — файлы уезжают в
    соседний блок, и `any(не tests/)` не видит ничего. Если форма
    вывода git изменится так, что старое деление снова заработает, —
    этот тест красный и W1 пересматривается."""
    naive = [b for b in FAKE_LOG.replace("\x1e", "").split("\n\n")
             if b.strip()]
    subject_block = next(b for b in naive if "Q7" in b)
    assert len(subject_block.splitlines()) == 1, subject_block


def test_l3_flags_an_item_that_no_commit_carries():
    """Заведомо несуществующий пункт Z9 не находит оправдания на живой
    истории ветки: фолбэк индекса в этом тесте отключен явным пустым
    staged-списком, а не унаследован от рабочего дерева."""
    assert _l3_missing(["Z9"], _git_log_name_only(), []) == ["Z9"]


def test_l2_staged_fallback_only_opens_for_a_non_test_file():
    """Как именно фолбэк не маскирует вырожденность: он проверяется
    отдельно и только на переданном списке. Индекс живого прогона в
    зубы не подмешивается."""
    log = _git_log_name_only()
    assert _l3_missing(["Z9"], log, ["tests/test_x.py"]) == ["Z9"]
    assert _l3_missing(["Z9"], log, ["rusterm/x.py"]) == []


# ── ТЗ-76 W2: одноимённые HANDOFF не сливаются ──────────────────────────

TWO_HANDOFFS = (
    "# REPORT\n"
    "## Done\n"
    "- ok\n"
    "## HANDOFF\n"
    "Status: PARTIAL (F1 done; F2 ahead)\n"
    "Items done: F1\n"
    "Items not done: F2 three-face cross-check\n"
    "## HANDOFF\n"
    "Status: DONE\n"
    "Items done: F1, F2\n"
)


def test_two_plain_handoff_blocks_stay_two_sections():
    """Зубы W2: ровно «## HANDOFF» дважды — это ДВЕ секции. setdefault
    (прежний код) склеивал их в одну, и проверить «решает последний»
    было нельзя без суффикса FINAL."""
    names = [n for n in _sections(TWO_HANDOFFS) if n.startswith("HANDOFF")]
    assert len(names) == 2, names


def test_last_handoff_decides_and_the_interim_one_is_ignored(monkeypatch):
    """Зубы W2 на живом правиле G4: промежуточный блок называет F2
    несделанным, финальный — нет. Склейка дала бы красный задним
    числом по работе, закоммиченной в круге 76."""
    monkeypatch.setattr(sys.modules[__name__], "_report_text",
                        lambda: TWO_HANDOFFS)
    monkeypatch.setattr(sys.modules[__name__], "_baton_round", lambda: 76)
    assert _claimed_undone_ids("\n".join(_handoff_section(TWO_HANDOFFS))) \
        == []
    test_last_handoff_does_not_call_committed_items_undone()


def test_merged_handoff_would_red_g4_retrospectively(monkeypatch):
    """Красный случай того же разреза, собранный вручную: если блоки
    склеить (как делал setdefault), промежуточная строка «Items not
    done: F2» попадает в проверяемый текст, коммит F2 в круге 76 на
    ветке есть — и G4 краснеет по уже сделанной работе."""
    merged = "\n".join(_sections(TWO_HANDOFFS)["HANDOFF"]
                       + _sections(TWO_HANDOFFS)["HANDOFF #2"])
    ids = _claimed_undone_ids(merged)
    assert ids == ["F2"], ids
    assert "F2" in _commit_for_items(ids, 76)


# ── ТЗ-78 Y1: L3 видит только свой круг ─────────────────────────────────

# Литерал вместо живой истории: коммит с W3 относится к ПРЕЖНЕМУ кругу
# (стоит НИЖЕ маркера «Эстафета: круг 103,»), и в круге 103 его нет.
# Без границы страж W3 находит — это и есть дыра, которую чинит Y1.
FAKE_LOG_TWO_ROUNDS = (
    "\x1e1111111 Эстафета: круг 103, ход у executor — agent/TASK-78.md\n"
    "\n"
    "agent/BATON.json\n"
    "\x1e2222222 ТЗ-53 W3: total_equity_incl_nci и версия карты us-gaap.v2\n"
    "\n"
    "rusterm/tui/model.py\n"
    "\x1e3333333 Эстафета: круг 102, ход у coordinator\n"
    "\n"
    "agent/BATON.json\n"
)


def test_l3_without_a_round_bound_credits_an_older_round():
    """ДЫРА до правки (Y1): без round_no страж видит W3 в чужом круге и
    молчит. Тест описывает нынешнее поведение, чтобы краснота была
    измеримой и чтобы будущий рефакторинг случайно не потерял границу."""
    assert _l3_missing(["W3"], FAKE_LOG_TWO_ROUNDS, []) == []


def test_l3_with_the_round_bound_flags_the_foreign_commit():
    """ЗУБ Y1 на границе круга: тот же лог, но с round_no=103 — коммит
    W3 лежит НИЖЕ маркера «Эстафета: круг 103,» и не имеет права
    закрывать пункт в этом круге. Страж обязан назвать W3 недостающим."""
    assert _l3_missing(["W3"], FAKE_LOG_TWO_ROUNDS, [],
                       round_no=103) == ["W3"]


def test_w3_is_not_closed_by_a_foreign_round_on_the_real_branch():
    """Y1 на настоящей истории: W3 на ветке закрывался и в круге 101
    (`1d39cd2`), и в ТЗ-53 (коммиты 2026-09-xx) — ни то, ни другое не
    имеет силы в круге 103. Без границы страж W3 находит, с границей —
    краснеет. Названо до/после, как требует ТЗ."""
    log = _git_log_name_only()
    before = _l3_missing(["W3"], log, [])
    after = _l3_missing(["W3"], log, [], round_no=_baton_round())
    assert before == [], (
        "W3 больше нет в истории ветки — тест-доказательство устарело, "
        "нужен другой пункт для той же дыры")
    assert after == ["W3"], (
        f"граница круга не сработала на настоящей ветке: after={after}")


def test_z9_teeth_still_hold_under_the_round_bound():
    """Z9 (заведомо fictitious) красен и до, и после Y1 — но его сила
    иллюзорна: он ловится любым стражем, даже без границы круга, потому
    что такого имени в истории не было НИКОГДА. Настоящий зуб — W3."""
    log = _git_log_name_only()
    assert _l3_missing(["Z9"], log, []) == ["Z9"]
    assert _l3_missing(["Z9"], log, [], round_no=_baton_round()) == ["Z9"]


def test_round_marker_missing_means_no_credits_at_all():
    """Если маркера текущего круга в логе нет (только чтоcreated-клон,
    история вне relay), страж не выдаёт ни одному пункту кредит —
    безопасная сторона; staged-фолбэк по-прежнему решает исход."""
    log = ("\x1e1111111 W9: реализация\n"
           "\n"
           "rusterm/x.py\n")
    assert _l3_missing(["W9"], log, [], round_no=103) == ["W9"]
    assert _l3_missing(["W9"], log, ["rusterm/x.py"], round_no=103) == []


# ── ТЗ-79 Z1: зубы на починку границы со стороны координатора ────────────

# Форма лога МОМЕНТА ПРИЁМКИ: `hand` ставит маркер круга N+1 самым
# свежим коммитом, работа круга N лежит под ним, ещё ниже — маркер
# круга N. Именно здесь прежнее правило (упор в маркер round_no)
# схлопывало окно в пустоту: Y1 был зелёным у исполнителя и красным у
# координатора. Литерал, а не живая история: форма не должна зависеть
# от того, сколько коммитов уже легло сверху.
FAKE_LOG_ACCEPTANCE_SHAPE = (
    "\x1e5555555 Эстафета: круг 105, ход у executor — agent/TASK-79.md\n"
    "\n"
    "agent/BATON.json\n"
    "\x1e4444444 ТЗ-78 Y2: маршрут dei и живые меры VZ\n"
    "\n"
    "rusterm/normalize/concepts.py\n"
    "tests/test_w5_verizon_shares.py\n"
    "\x1e3333333 Эстафета: круг 104, ход у coordinator — agent/TASK-78.md\n"
    "\n"
    "agent/BATON.json\n"
)


def test_item_is_found_under_the_next_round_marker():
    """ЗУБ Z1 на верхней границе: при round_no=104 работа круга 104
    обязана находиться, даже когда сверху стоит маркер круга 105 —
    `hand` увеличивает номер раньше, чем начинается приёмка."""
    assert _l3_missing(["Y2"], FAKE_LOG_ACCEPTANCE_SHAPE, [],
                       round_no=104) == []


def test_old_bound_collapsed_the_window_at_acceptance():
    """ДЫРА прежнего правила на той же истории: окно обязано быть
    непустым в ОБЕИХ формах — и когда верхний блок есть маркер самого
    round_no (ход ещё у исполнителя), и когда сверху встал маркер
    круга N+1 (уже у координатора). Прежнее правило, упиравшееся в
    маркер round_no, во второй форме обрывало обзор до всякой работы:
    на красном прогоне обе строки дают `['Y2']` вместо `[]`."""
    old_shape = FAKE_LOG_ACCEPTANCE_SHAPE.replace(
        "\x1e5555555 Эстафета: круг 105, ход у executor — agent/TASK-79.md\n"
        "\n"
        "agent/BATON.json\n", "")
    assert _l3_missing(["Y2"], old_shape, [], round_no=104) == []
    assert _l3_missing(["Y2"], FAKE_LOG_ACCEPTANCE_SHAPE, [],
                       round_no=104) == []


def test_leading_marker_of_another_round_is_not_a_lower_bound():
    """Маркер круга, НЕ совпадающего с round_no и round_no+1, сверху
    обязан остановить обзор: нижняя граница — маркер round_no, а не
    произвольная преграда. Проверка на настоящем ветвлении номеров:
    окно круга 104 не открывают коммиты из чужого маркера."""
    log = ("\x1e9999999 Эстафета: круг 107, ход у executor\n"
           "\n"
           "agent/BATON.json\n"
           "\x1e4444444 ТЗ-78 Y2: маршрут dei\n"
           "\n"
           "rusterm/normalize/concepts.py\n"
           "\x1e3333333 Эстафета: круг 104, ход у coordinator\n"
           "\n"
           "agent/BATON.json\n")
    assert _l3_missing(["Y2"], log, [], round_no=104) == ["Y2"]


def _round_under_review_cases(tmp_path, monkeypatch):
    """Обе развилки `_round_under_review()` на подставном BATON.json:
    REPO подменяется, живой baton не читается и не пишется."""
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "REPO", tmp_path)
    agent = tmp_path / "agent"
    agent.mkdir(parents=True, exist_ok=True)
    baton = agent / "BATON.json"

    def case(holder: str, rnd: int) -> int:
        baton.write_text(json.dumps({"holder": holder, "round": rnd}),
                         encoding="utf-8")
        return _round_under_review()

    return case


def test_round_under_review_shifts_when_the_holder_is_coordinator(
        tmp_path, monkeypatch):
    """Z1: при ходе у координатора проверяется круг round − 1 (отчёт
    описывает предыдущий круг), при ходе у исполнителя — сам round."""
    case = _round_under_review_cases(tmp_path, monkeypatch)
    assert case("coordinator", 105) == 104
    assert case("executor", 105) == 105
    assert case("coordinator", 1) == 0


def test_round_under_review_and_live_baton_agree():
    """Живой baton: правило применено к настоящему BATON.json — сверка
    с `_baton_round()` не даёт расхождения кроме законной −1."""
    baton = json.loads((REPO / "agent" / "BATON.json").read_text(
        encoding="utf-8"))
    rnd = int(baton.get("round", 0))
    holder = baton.get("holder")
    expected = rnd - 1 if holder == "coordinator" else rnd
    assert _round_under_review() == expected, (
        f"holder={holder!r}, round={rnd}: получено {_round_under_review()}")


def _log_from_top_marker(log: str, round_no: int) -> str:
    """Лог, усечённый до формы момента приёмки: всё, что лежит ВЫШЕ
    маркера эстафеты, отбрасывается — на живой ветке там стоят коммиты
    следующих кругов, а в приёмный момент их нет.

    ТЗ-81 (починка ТЗ-79 Z1): ищется именно маркер круга
    `round_no + 1`, а не «самый свежий». Прежняя версия привязывалась к
    голове ветки: пока сверху стоял маркер 105, тест с `round_no=104`
    был зелёным, но следующий же круг поднял туда маркер 106 — и тест
    покраснел, не изменившись сам. Страж, зависящий от того, сколько
    кругов прошло после него, зеленеет у исполнителя и краснеет на
    приёмке — ровно та болезнь, которую Z1 и лечил.

    ТЗ-80 A1: `round_no` стал обязательным — форма «усечь по самому
    свежему маркеру» была единственным способом нарушить правило A1, и
    теперь её нельзя вызвать случайно."""
    blocks = log.split("\x1e")
    wanted = f"Эстафета: круг {round_no + 1},"
    for i, block in enumerate(blocks):
        lines_ = [l for l in block.strip().splitlines() if l.strip()]
        if lines_ and wanted in lines_[0]:
            return "\x1e".join(blocks[i:])
    return log


def test_strictness_holds_on_the_real_branch(tmp_path, monkeypatch):
    """Z1: граница осталась строгой — из окна круга 104 не видно ни
    пунктов прошлого круга (W1, W5), ни чужого W3, ни вымышленного Z9,
    при том что работа этого круга (Y1, Y2) находится. Числа
    воспроизводят прогон координатора."""
    log = _log_from_top_marker(_git_log_name_only(), round_no=104)
    assert _l3_missing(["Y1", "Y2"], log, [], round_no=104) == []
    assert _l3_missing(["W1", "W5"], log, [], round_no=104) == ["W1", "W5"]
    assert _l3_missing(["W3"], log, [], round_no=104) == ["W3"]
    assert _l3_missing(["Z9"], log, [], round_no=104) == ["Z9"]


# ── ТЗ-80 A1: страж не смотрит на голову ветки ──────────────────────────

LIVE_PROBES = (["Y1", "Y2"], ["W1", "W5"], ["W3"], ["Z9"])

# Окно круга 104 — таблица, измеренная в ТЗ-79 Z1 и подтверждённая
# прогоном координатора. Она же и эталон симуляции: то, что обязано
# НЕ измениться, сколько бы кругов ни наросло сверху.
WINDOW_OF_ROUND_104 = {
    ("Y1", "Y2"): [],
    ("W1", "W5"): ["W1", "W5"],
    ("W3",): ["W3"],
    ("Z9",): ["Z9"],
}


def _top_round_in(log: str) -> int:
    """Номер самого свежего маркера в логе — нужен только чтобы
    приставить сверху ЧЕРЕД следующих кругов, а не обрезать по нему."""
    nums = [int(m.group(1)) for m in re.finditer(r"Эстафета: круг (\d+),",
                                                 log)]
    assert nums, "в живом логе нет ни одного маркера эстафеты"
    return max(nums)


def _rounds_later(log: str, count: int) -> str:
    """Тот же живой лог, но сверху приписано `count` маркеров следующих
    кругов — так ветка выглядит через 1, 2 и 5 кругов после того, как
    этот тест написали. Тем самым кругом, что проверяет тест."""
    top = _top_round_in(log)
    prefix = "".join(
        "\x1e%07x Эстафета: круг %d, ход у executor — agent/TASK-80.md\n"
        "\n"
        "agent/BATON.json\n" % (0x0A0A0A0 + k, top + k)
        for k in range(count, 0, -1))
    return prefix + log


def _window_of_round_104(log: str) -> dict[tuple[str, ...], list[str]]:
    return {tuple(ids): _l3_missing(list(ids),
                                    _log_from_top_marker(log, round_no=104),
                                    [], round_no=104)
            for ids in LIVE_PROBES}


def test_the_window_survives_rounds_passing_after_the_test_was_written():
    """ЗУБ A1 симуляцией: окно круга 104 обязано давать ту же таблицу,
    сколько бы кругов ни прошло сверху. Прежний `_log_from_top_marker`,
    резавший по самому свежему маркеру, спотыкается уже на первом
    приписанном круге и теряет Y1 с Y2 — краснота показана цитатой в
    отчёте (ТЗ-79 Z1 болел тем же, но с точностью до наоборот: зелёный
    у исполнителя, красный на приёмке)."""
    log = _git_log_name_only()
    for count in (1, 2, 5):
        moved = _window_of_round_104(_rounds_later(log, count))
        assert moved == WINDOW_OF_ROUND_104, (
            f"через {count} круг(ов) сверху окно круга 104 изменилось: "
            f"{moved}")
    assert _window_of_round_104(log) == WINDOW_OF_ROUND_104, (
        "и без приписанных кругов окно обязано давать ту же таблицу")


def test_the_helper_refuses_to_cut_by_the_newest_marker():
    """A1 структурно: `round_no` у `_log_from_top_marker` обязателен,
    поэтому «усечь по самому свежему маркеру» больше не вызываемо —
    единственный способ нарушить правило закрыт сигнатурой."""
    import inspect

    params = inspect.signature(_log_from_top_marker).parameters
    assert params["round_no"].default is inspect.Parameter.empty, (
        "round_no снова со значением по умолчанию: вызов без номера "
        "круга молча режет по голове ветки")
    assert params["round_no"].annotation in (int, "int"), (
        f"аннотация round_no = {params['round_no'].annotation!r} — "
        "Optional[int] возвращает зависимость от головы ветки")
