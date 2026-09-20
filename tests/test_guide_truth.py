"""ТЗ-52: GUIDE.md перестаёт врать — вставки проверяются прогоном.

Руководство обещает «все выводы — реальные прогоны»; этот страж
исполняет каждый офлайн-блок ```console на свежем каталоге данных (в
tmp_path, изолированный env-файл, ни сети, ни ключей) и сверяет вывод
с написанным.

Правило сравнения одной фразой: даты (\\d{4}-\\d{2}-\\d{2}), UUID,
абсолютные пути (каталог данных, env-файл, файл отчёта) и число в
строке «data_lag» заменяются плейсхолдерами, строка руководства,
содержащая «...», съедает любое число строк вывода, остальное —
дословно. Тест краснеет, если команда исчезла, переименовалась,
сменила формат вывода или порядок строк.

Блоки, которые нельзя исполнить без сети, ключа или терминала,
помечены в самом руководстве строкой-маркером («# требует …») и
пропускаются с непустой причиной. Сегодня такой ровно один — tui в §9.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "GUIDE.md"
GUIDE_DATA_ROOT = "/tmp/rusterm-guide"
GUIDE_REPORT = "/tmp/guide-report.txt"
GUIDE_ENVFILE = "/tmp/empty-guide-env"


@dataclass
class Step:
    command: str
    env_overrides: dict = field(default_factory=dict)
    expected: list[str] = field(default_factory=list)


@dataclass
class Block:
    lineno: int          # строка открывающего ```console
    markers: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)


def _split_env_prefix(command: str) -> tuple[dict, str]:
    """`FOO=bar python3 ...` -> ({FOO: bar}, `python3 ...`)."""
    parts = command.split(" ")
    overrides: dict[str, str] = {}
    while parts and re.match(r"^[A-Z_][A-Z0-9_]*=", parts[0]):
        key, _, value = parts[0].partition("=")
        overrides[key] = value
        parts = parts[1:]
    return overrides, " ".join(parts)


def parse_guide(text: str) -> list[Block]:
    blocks: list[Block] = []
    block: Block | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if line.strip() == "```console":
            block = Block(lineno=lineno)
            continue
        if block is None:
            continue
        if line.strip() == "```":
            blocks.append(block)
            block = None
            continue
        if line.startswith("#"):
            block.markers.append(line.strip())
            continue
        if line.startswith("$ "):
            raw_command = line[2:].strip()
            overrides, command = _split_env_prefix(raw_command)
            block.steps.append(Step(command=command,
                                    env_overrides=overrides))
            continue
        if line.strip() and block.steps:
            block.steps[-1].expected.append(line)
    return blocks


def _normalize(line: str, tmp_root: Path, envfile: Path,
               report: Path) -> str:
    for actual_root, guide_root in (
            (f"/private{tmp_root}", GUIDE_DATA_ROOT),
            (str(tmp_root), GUIDE_DATA_ROOT)):
        line = line.replace(actual_root, guide_root)
    line = line.replace(str(report), GUIDE_REPORT)
    line = line.replace(str(envfile), GUIDE_ENVFILE)
    line = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}"
                  r"-[0-9a-f]{12}", "<UUID>", line)
    line = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", line)
    line = re.sub(r"data_lag\t\d+(\.\d+)?", "data_lag\t<N>", line)
    # каскад покрытия зависит от порядка внутреннего прохода, не от
    # того, что написано в руководстве: блок-причина не стабилен
    line = re.sub(r"cascade:after_[a-z_]+", "cascade:<BLOCK>", line)
    line = re.sub(r"(?<![\w<])/(?:private/)?tmp/[\w.\-/]*", "<PATH>",
                  line)
    return line


def _match(expected: list[str], actual: list[str], tmp_root: Path,
           envfile: Path, report: Path) -> str | None:
    """None — совпало; иначе текст первого расхождения."""
    exp = [_normalize(e, tmp_root, envfile, report) for e in expected]
    act = [_normalize(a, tmp_root, envfile, report) for a in actual]
    i = 0
    for e in exp:
        if "..." in e:
            continue  # съедает любое число строк
        while i < len(act) and act[i] != e:
            i += 1
        if i >= len(act):
            return f"ожидалась строка: {e!r}"
        i += 1
    # хвост без элизии не должен содержать лишних строк
    if not exp or "..." not in exp[-1]:
        if i < len(act):
            return f"лишние строки вывода, начиная с: {act[i]!r}"
    return None


def test_guide_blocks_run_and_match(tmp_path):
    blocks = parse_guide(GUIDE.read_text(encoding="utf-8"))
    assert len(blocks) == 12, [b.lineno for b in blocks]
    envfile = tmp_path / "guide-env"
    envfile.write_text("", encoding="utf-8")
    envfile.chmod(0o600)
    base_env = dict(os.environ)
    base_env["RUSTERM_ENV_FILE"] = str(envfile)
    for name in ("RUSTERM_SEC_UA", "RUSTERM_DART_KEY",
                 "RUSTERM_TWELVEDATA_KEY", "RUSTERM_LLM_API_KEY"):
        base_env.pop(name, None)
    failures: list[str] = []
    skipped = 0
    for block in blocks:
        if block.markers:
            skipped += 1
            continue
        for step in block.steps:
            command = step.command
            command = command.replace(GUIDE_DATA_ROOT, str(tmp_path))
            command = command.replace(GUIDE_REPORT,
                                      str(tmp_path / "guide-report.txt"))
            env = dict(base_env)
            if step.env_overrides:
                env.update(step.env_overrides)
            # Блок исполняется из tmp_path — без этого python3 поднял бы
            # не код ЭТОГО дерева, а какую-нибудь установленную копию
            # с машины (круг 56: у каждого дерева свой путь). Корень
            # дерева идёт первым — страж проверяет вставки против того
            # кода, который и проверяет остальная приёмка.
            env["PYTHONPATH"] = (
                str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""))
            result = subprocess.run(
                command, shell=True, cwd=tmp_path, env=env,
                capture_output=True, text=True, timeout=120)
            # GUIDE показывает терминальный вывод: stdout и stderr
            # вместе, в порядке поступления
            merged = result.stdout + result.stderr
            actual = merged.splitlines()
            mismatch = _match(step.expected, actual, tmp_path, envfile,
                              tmp_path / "guide-report.txt")
            if mismatch is not None:
                failures.append(
                    f"GUIDE.md:{block.lineno}: {step.command}\n"
                    f"  {mismatch}\n"
                    f"  фактический вывод: {actual[:12]}")
    assert not failures, (
        "руководство расходится с прогоном:\n" + "\n".join(failures))
    assert skipped == 2, skipped


def test_marked_blocks_are_interactive():
    """Блоки под маркером не исполняются стражем: tui требует
    терминала, прогон окна — экрана (ТЗ-60 E3). Порядок разделов
    руководства держит tui первым из помеченных."""
    blocks = parse_guide(GUIDE.read_text(encoding="utf-8"))
    marked = [b for b in blocks if b.markers]
    assert len(marked) == 2
    assert "требует терминала" in marked[0].markers[0]
    assert marked[0].steps[0].command.endswith("tui")
    assert "требует экрана" in marked[1].markers[0]
    assert " desktop" in marked[1].steps[0].command


def test_parser_lists_every_command():
    blocks = parse_guide(GUIDE.read_text(encoding="utf-8"))
    commands = [s.command for b in blocks for s in b.steps]
    for expected in ("python3 -m rusterm.cli --root /tmp/rusterm-guide "
                     "init",
                     "python3 -m rusterm.cli --root /tmp/rusterm-guide "
                     "demo",
                     "python3 -m rusterm.cli --root /tmp/rusterm-guide "
                     "status --json",
                     "python3 -m rusterm.cli --root /tmp/rusterm-guide "
                     "ops --watchlist demo-list --request "
                     "\"добавь AAPL\" --json"):
        assert expected in commands, expected
