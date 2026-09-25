#!/usr/bin/env python3
"""Эстафета координатора и исполнителя через git.

Один файл `agent/BATON.json` на ветке смены говорит, чей сейчас ход.
Кто держит эстафету — тот и пишет; второй ждёт. Ожидание — это блокирующий
`wait`, который опрашивает `git fetch` и выходит, как только ход перешёл
к нему. Так отчёт видят сразу, а не «когда заглянут».

Стандартная библиотека, git и всё. Сеть нужна только для fetch/push.

Коды возврата:
    0  ход твой (wait), команда выполнена
    2  таймаут ожидания — хода не дождались
    3  пауза (локальный стоп-файл или `paused` в эстафете)
    4  цикл закрыт (`finished`)
    5  ошибка
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BATON_PATH = "agent/BATON.json"
ROLES = ("coordinator", "executor")
EXIT_OK, EXIT_TIMEOUT, EXIT_PAUSED, EXIT_FINISHED, EXIT_ERROR = 0, 2, 3, 4, 5

# Разделы отчёта, которые координатор читает первыми (CLAUDE.md).
DIGEST_SECTIONS = (
    "handoff",
    "disputed",
    "blocked",
    "what not to trust",
    "заблокировано",
    "спорное",
    "чему верить нельзя",
)


# ── git ──────────────────────────────────────────────────────────────────


def git(*args: str, check: bool = True, stdin: bytes | None = None,
        env: dict[str, str] | None = None) -> str:
    """Запускает git и возвращает stdout строкой."""
    full_env = None
    if env:
        full_env = dict(os.environ)
        full_env.update(env)
    proc = subprocess.run(
        ("git",) + args,
        input=stdin,
        capture_output=True,
        env=full_env,
    )
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
        raise SystemExit(EXIT_ERROR)
    return proc.stdout.decode("utf-8", "replace").strip()


def git_ok(*args: str) -> bool:
    return subprocess.run(("git",) + args, capture_output=True).returncode == 0


def repo_root() -> Path:
    return Path(git("rev-parse", "--show-toplevel"))


def git_dir() -> Path:
    return Path(git("rev-parse", "--absolute-git-dir"))


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


# ── локальные маркеры ────────────────────────────────────────────────────


def stop_file() -> Path:
    """Стоп-файл живёт в .git — он не попадает ни в git status, ни в коммит."""
    return git_dir() / "relay-stop"


def branch_file() -> Path:
    return git_dir() / "relay-branch"


def resolve_branch(explicit: str | None) -> str:
    if explicit:
        branch_file().write_text(explicit + "\n", encoding="utf-8")
        return explicit
    env = os.environ.get("RUSTERM_RELAY_BRANCH")
    if env:
        return env
    cached = branch_file()
    if cached.exists():
        value = cached.read_text(encoding="utf-8").strip()
        if value:
            return value
    die("ветка смены неизвестна: передай --branch agent/night-N один раз, "
        "дальше она запомнится в .git/relay-branch")
    raise AssertionError  # недостижимо, для типов


def die(message: str) -> None:
    sys.stderr.write(f"relay: {message}\n")
    raise SystemExit(EXIT_ERROR)


# ── эстафета ─────────────────────────────────────────────────────────────


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(remote: str, branch: str) -> None:
    subprocess.run(
        ("git", "fetch", "--quiet", remote, f"{branch}:refs/remotes/{remote}/{branch}"),
        capture_output=True,
    )


def read_remote_baton(remote: str, branch: str) -> dict | None:
    ref = f"{remote}/{branch}:{BATON_PATH}"
    proc = subprocess.run(("git", "show", ref), capture_output=True)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die(f"{ref} не разбирается как JSON")
    return None


def show_remote(remote: str, branch: str, path: str) -> str | None:
    proc = subprocess.run(("git", "show", f"{remote}/{branch}:{path}"),
                          capture_output=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace")


def baton_line(baton: dict) -> str:
    flags = []
    if baton.get("paused"):
        flags.append("ПАУЗА")
    if baton.get("finished"):
        flags.append("ЗАКРЫТО")
    tail = ("  [" + ", ".join(flags) + "]") if flags else ""
    return (f"круг {baton.get('round')}: ход у {baton.get('holder')}"
            f"  task={baton.get('task')}  report={baton.get('report')}"
            f"  передал {baton.get('handed_by')} в {baton.get('handed_at')}{tail}")


def sync_worktree(remote: str, branch: str, quiet: bool = False) -> bool:
    """Подтягивает ветку смены в рабочее дерево, если она здесь выкачана.

    Без этого «исполнитель сразу видит задание» — неправда: файл лежит на
    origin, а не на диске. Локальные коммиты перебазируются поверх чужих.
    """
    if current_branch() != branch:
        return True
    fetch(remote, branch)
    local = git("rev-parse", "HEAD")
    remote_head = git("rev-parse", f"{remote}/{branch}")
    if local == remote_head:
        return True
    proc = subprocess.run(
        ("git", "pull", "--rebase", "--autostash", remote, branch),
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout.decode("utf-8", "replace"))
        sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
        # Не оставлять дерево в середине ребейза: откатываем, autostash вернётся.
        subprocess.run(("git", "rebase", "--abort"), capture_output=True)
        sys.stderr.write(
            "relay: рабочее дерево не удалось подтянуть к "
            f"{remote}/{branch} — ребейз откачен. Разреши расхождение "
            "руками (git log HEAD..%s/%s) и повтори.\n" % (remote, branch))
        return False
    if not quiet:
        print(f"рабочее дерево подтянуто к {remote}/{branch}: "
              f"{git('rev-parse', '--short', 'HEAD')}")
    return True


def push_baton(remote: str, branch: str, baton: dict, extra: list[str],
               message: str) -> str:
    """Кладёт BATON.json и перечисленные файлы одним коммитом на ветку.

    Если ветка смены выкачана в текущем дереве — обычный add/commit/push.
    Иначе коммит собирается плюмбингом поверх `remote/branch` и пушится
    напрямую: рабочее дерево координатора не трогается вовсе.
    """
    root = repo_root()
    payload = json.dumps(baton, ensure_ascii=False, indent=1) + "\n"

    if current_branch() == branch:
        if not sync_worktree(remote, branch, quiet=True):
            raise SystemExit(EXIT_ERROR)
        (root / BATON_PATH).write_text(payload, encoding="utf-8")
        # Чужое, уже лежащее в индексе, в коммит эстафеты не берётся:
        # ТЗ-37 I5 уехал внутрь коммита «Эстафета: круг 44» именно так.
        staged = [f for f in git("diff", "--cached", "--name-only").splitlines()
                  if f and f != BATON_PATH and f not in extra]
        if staged:
            # ТЗ-42 J1: эстафету нельзя передавать из грязного индекса —
            # именно так круг 48 остался непереданным
            die("в индексе лежит чужое: " + ", ".join(staged[:10])
                + ". Ход не передан и работа не сдана. Закоммить это "
                "своим коммитом и повтори: python3 agent/relay.py hand ...")
        git("add", "--", BATON_PATH, *extra)
        try:
            git("commit", "--only", "-m", message, "--", BATON_PATH, *extra)
        except SystemExit:
            # ТЗ-42 J1: провал коммита — не тишина: ход не передан
            die("коммит эстафеты не прошёл. Ход не передан и работа не "
                "сдана. Разберись (хук/индекс) и повтори: python3 "
                "agent/relay.py hand ...")
        proc = subprocess.run(("git", "push", remote, f"{branch}:{branch}"),
                              capture_output=True)
        if proc.returncode != 0:
            # Ветка ушла вперёд между sync и push. Коммит эстафеты снимается,
            # чтобы он не мешал следующей попытке; файлы остаются в дереве.
            sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
            git("reset", "--mixed", "HEAD~1")
            fetch(remote, branch)
            subprocess.run(("git", "checkout", f"{remote}/{branch}", "--",
                            BATON_PATH), capture_output=True)
            die(f"push отклонён: {remote}/{branch} ушла вперёд. Коммит эстафеты "
                "снят, файлы на месте. Перечитай relay.py status и повтори.")
        return git("rev-parse", "--short", "HEAD")

    fetch(remote, branch)
    base = git("rev-parse", f"{remote}/{branch}^{{commit}}")
    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git("read-tree", base, env=env)
        blobs: list[tuple[str, bytes]] = [(BATON_PATH, payload.encode("utf-8"))]
        for rel in extra:
            src = root / rel
            if not src.is_file():
                die(f"нечего добавить: {rel} не найден в рабочем дереве")
            blobs.append((rel, src.read_bytes()))
        for rel, data in blobs:
            sha = git("hash-object", "-w", "--stdin", stdin=data)
            git("update-index", "--add", "--cacheinfo", f"100644,{sha},{rel}",
                env=env)
        tree = git("write-tree", env=env)
    commit = git("commit-tree", tree, "-p", base, "-m", message)
    proc = subprocess.run(("git", "push", remote, f"{commit}:refs/heads/{branch}"),
                          capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
        die("push отклонён — ветка ушла вперёд. Ход не передан и работа "
            "не сдана. Перечитай состояние (relay.py status) и повтори "
            "передачу.")
    fetch(remote, branch)
    return commit[:7]


# ── команды ──────────────────────────────────────────────────────────────


def cmd_init(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    fetch(a.remote, branch)
    if not git_ok("rev-parse", "--verify", f"{a.remote}/{branch}^{{commit}}"):
        die(f"нет ветки {a.remote}/{branch} — создай и запушь её сначала")
    existing = read_remote_baton(a.remote, branch)
    if existing and not a.force:
        print("эстафета уже заведена:", baton_line(existing))
        print("перезаписать — только с --force")
        return EXIT_OK
    baton = {
        "holder": a.holder,
        "round": a.round,
        "branch": branch,
        "task": a.task or "",
        "report": a.report or "",
        "note": a.note or "",
        "handed_by": "coordinator",
        "handed_at": now(),
        "paused": False,
        "finished": False,
    }
    sha = push_baton(a.remote, branch, baton, [],
                     f"Эстафета: круг {a.round}, ход у {a.holder}")
    print(f"эстафета заведена коммитом {sha}")
    print(baton_line(baton))
    return EXIT_OK


def cmd_status(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    fetch(a.remote, branch)
    baton = read_remote_baton(a.remote, branch)
    if baton is None:
        die(f"на {a.remote}/{branch} нет {BATON_PATH} — сначала relay.py init")
    # ТЗ-42 J2: проверка держателя — код возврата, а не надежда.
    # После hand вызывающий обязан прогнать это; ненулевой код — ход
    # не доехал (см. PROTOCOL §12).
    if getattr(a, "assert_holder", None):
        expected = a.assert_holder
        if expected not in ROLES:
            die(f"--assert-holder принимает {ROLES}")
        if baton.get("holder") != expected:
            sys.stderr.write(
                f"relay: ход НЕ передан: на {a.remote}/{branch} держит "
                f"{baton.get('holder')!r}, а не {expected!r}. Работа не "
                "сдана. Разберись (relay.py status, журнал пуша) и "
                "повтори hand.\n")
            return EXIT_ERROR
    print(f"ветка: {a.remote}/{branch}")
    print(baton_line(baton))
    if baton.get("note"):
        print("записка:", baton["note"])
    if stop_file().exists():
        print("локальный стоп-файл на месте: "
              f"{stop_file()} — wait здесь выйдет с кодом 3")
    state = show_remote(a.remote, branch, "agent/STATE.json")
    if state:
        try:
            s = json.loads(state)
            print(f"STATE.json: status={s.get('status')} item={s.get('item')} "
                  f"step={s.get('step')} task={s.get('task')}")
        except json.JSONDecodeError:
            pass
    print("голова ветки:", git("log", "-1", "--oneline", f"{a.remote}/{branch}"))
    return EXIT_OK


def cmd_wait(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    if a.role not in ROLES:
        die(f"--for принимает {ROLES}")
    deadline = time.monotonic() + a.timeout
    first = True
    while True:
        if stop_file().exists():
            print(f"пауза: {stop_file()} на месте")
            return EXIT_PAUSED
        fetch(a.remote, branch)
        baton = read_remote_baton(a.remote, branch)
        if baton is None:
            die(f"на {a.remote}/{branch} нет {BATON_PATH} — сначала relay.py init")
        if baton.get("finished"):
            print("цикл закрыт:", baton_line(baton))
            return EXIT_FINISHED
        if baton.get("paused"):
            print("пауза объявлена в эстафете:", baton_line(baton))
            return EXIT_PAUSED
        if baton.get("holder") == a.role:
            print(f"ХОД ТВОЙ ({a.role})")
            print(baton_line(baton))
            if baton.get("note"):
                print("записка:", baton["note"])
            print("голова ветки:",
                  git("log", "-1", "--oneline", f"{a.remote}/{branch}"))
            if not a.no_sync and not sync_worktree(a.remote, branch):
                return EXIT_ERROR
            target = baton.get("task") if a.role == "executor" else baton.get("report")
            if target:
                where = repo_root() / target
                print(f"читать: {target}"
                      f"{'' if where.is_file() else f' (в рабочем дереве нет — смотри {a.remote}/{branch}:{target})'}")
            return EXIT_OK
        if first and not a.quiet:
            print(f"жду хода для {a.role}; сейчас держит {baton.get('holder')}; "
                  f"опрос раз в {a.interval} с, предел {a.timeout} с",
                  flush=True)
            first = False
        if time.monotonic() >= deadline:
            print(f"таймаут {a.timeout} с: ход так и не перешёл к {a.role} "
                  f"(держит {baton.get('holder')})")
            return EXIT_TIMEOUT
        time.sleep(a.interval)


def _sections(text: str, wanted: tuple[str, ...], limit: int) -> list[str]:
    """Вырезает из markdown разделы с нужными заголовками."""
    out: list[str] = []
    keep = False
    count = 0
    for line in text.splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip().lower()
            keep = any(title.startswith(w) for w in wanted)
            count = 0
            if keep:
                out.append("")
                out.append(line)
            continue
        if keep:
            if count >= limit:
                continue
            out.append(line)
            count += 1
    return out


def newest_report(remote: str, branch: str) -> str:
    """Самый свежий agent/REPORT-*.md на ветке — когда эстафета не назвала отчёт."""
    listing = git("ls-tree", "--name-only", f"{remote}/{branch}", "agent/")
    reports = [f for f in listing.splitlines()
               if f.startswith("agent/REPORT-") and f.endswith(".md")]
    if not reports:
        return ""

    def key(name: str) -> tuple[int, str]:
        # Только ведущее число: REPORT-20-L3 и REPORT-20-000 — это всё ещё 20.
        tail = name[len("agent/REPORT-"):]
        lead = "".join(itertools.takewhile(str.isdigit, tail))
        return (int(lead) if lead else 0, name)

    return max(reports, key=key)


def cmd_digest(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    fetch(a.remote, branch)
    baton = read_remote_baton(a.remote, branch)
    print("=" * 72)
    if baton is None:
        print(f"эстафета на {a.remote}/{branch} не заведена "
              f"(нет {BATON_PATH}) — пакет собран без неё")
        baton = {}
    else:
        print(baton_line(baton))
    print("=" * 72)

    state = show_remote(a.remote, branch, "agent/STATE.json")
    if state:
        try:
            s = json.loads(state)
            print(f"\n## STATE.json\nstatus={s.get('status')} item={s.get('item')} "
                  f"step={s.get('step')} model={s.get('model')} "
                  f"requests={s.get('requests')} net={s.get('net_requests')} "
                  f"llm={s.get('llm_calls')} updated={s.get('updated_at')}")
        except json.JSONDecodeError:
            pass

    report = a.report or baton.get("report") or newest_report(a.remote, branch)
    text = show_remote(a.remote, branch, report) if report else None
    if text:
        print(f"\n## {report} — HANDOFF, Disputed, Blocked, "
              f"What not to trust")
        body = _sections(text, DIGEST_SECTIONS, a.lines)
        print("\n".join(body) if body else "(нужных разделов в отчёте нет)")
    elif report:
        print(f"\n## {report} — на ветке нет такого файла")

    print(f"\n## коммиты {a.base}..{a.remote}/{branch}")
    print(git("log", "--oneline", f"{a.base}..{a.remote}/{branch}") or "(нет)")
    print(f"\n## diff --stat {a.base}...{a.remote}/{branch}")
    print(git("diff", "--stat", f"{a.base}...{a.remote}/{branch}") or "(нет)")

    diff = git("diff", f"{a.base}...{a.remote}/{branch}", "--", "tests/")
    removed = [ln for ln in diff.splitlines()
               if ln.startswith("-") and "assert" in ln]
    print("\n## удалённые assert в tests/ (P1)")
    print("\n".join(removed) if removed else "(нет — чисто)")

    touched = git("diff", "--name-only", f"{a.base}...{a.remote}/{branch}")
    guarded = [f for f in touched.splitlines()
               if f in ("agent/acceptance.sh", "agent/selfcheck.sh")
               or f.startswith("docs/")]
    print("\n## тронуто из защищённого (acceptance/selfcheck/docs)")
    print("\n".join(guarded) if guarded else "(нет — чисто)")
    print("\nследующий шаг: python3 agent/relay.py verify — приёмка на ветке смены "
          "в отдельном рабочем дереве")
    return EXIT_OK


def run_stamp() -> str:
    """Метка прогона по часам UTC до секунды."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def untracked_files(work: Path) -> list[str]:
    """Неотслеживаемые файлы дерева: ровно те, что переживают
    `checkout --detach` + `reset --hard` (ТЗ-88 C1). Спрятанное в
    .gitignore в список не входит — `--exclude-standard`."""
    if not (work / ".git").exists():
        return []
    return sorted(line for line in git("-C", str(work), "ls-files",
                                       "--others", "--exclude-standard",
                                       check=False).splitlines()
                  if line.strip())


def verify_worktree(path_arg: str | None, head: str) -> Path:
    """Куда ставить рабочее дерево приёмки (ТЗ-88 C1).

    Явно данный путь уважаем как есть: человек вправе держать своё
    дерево и переиспользовать его. По умолчанию путь уникальный на
    прогон — прежний `rusterm-relay-verify` был один на всю машину,
    `reset --hard` неотслеживаемое не трогает, и мусор одного прогона
    переходил следующему (красный `test_i5` и ложный вывод о том, что
    приёмку ломает связанное дерево).
    """
    if path_arg:
        return Path(path_arg)
    return (Path(tempfile.gettempdir())
            / f"rusterm-relay-verify-{head[:7]}-{run_stamp()}"
            f"-{os.getpid()}-{next(_VERIFY_RUNS)}")


def verify_refusal(work: Path) -> str | None:
    """Почему приёмку в этом дереве начинать нельзя (ТЗ-88 C1).

    Молча чужие файлы не убираем: `reset --hard` их всё равно не
    трогает, а следующий прогон унаследовал бы тот же мусор. Отказ
    называет каждый файл и команду, которой убрать его самому.
    """
    if not work.exists():
        return None
    if not (work / ".git").exists():
        if any(work.iterdir()):
            return (f"каталог {work} существует, это не рабочее дерево git "
                    f"и он не пуст — файлы оттуда verify не убирает; "
                    f"освободите путь сами: rm -rf {work}")
        return None
    extra = untracked_files(work)
    if extra:
        return (f"в дереве приёмки {work} лежат неотслеживаемые файлы "
                f"(прошлый прогон или чужая работа):\n  "
                + "\n  ".join(extra)
                + f"\nverify их не удаляет. убрать самому: "
                  f"git -C {work} clean -fd")
    return None


def cmd_verify(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    fetch(a.remote, branch)
    head = git("rev-parse", f"{a.remote}/{branch}")
    work = verify_worktree(a.worktree, head)
    refusal = verify_refusal(work)
    if refusal:
        sys.stderr.write(f"verify: {refusal}\n")
        return EXIT_ERROR
    print(f"дерево приёмки: {work}", flush=True)
    if (work / ".git").exists():
        subprocess.run(("git", "-C", str(work), "checkout", "--detach", head),
                       capture_output=True, check=False)
        subprocess.run(("git", "-C", str(work), "reset", "--hard", head),
                       capture_output=True, check=False)
    else:
        subprocess.run(("git", "worktree", "prune"), capture_output=True)
        git("worktree", "add", "--detach", str(work), head)
    print(f"приёмка в {work} на {head[:7]} ({a.remote}/{branch})", flush=True)
    proc = subprocess.run(("bash", "agent/acceptance.sh"), cwd=str(work))
    print(f"\nкод возврата приёмки: {proc.returncode} "
          f"({'ПРИНЯТО' if proc.returncode == 0 else 'провалов: %d' % proc.returncode})")
    return EXIT_OK if proc.returncode == 0 else EXIT_ERROR


# ── красная приёмка: что упало и где полный лог (ТЗ-80 A2) ──────────────

_VERIFY_RUNS = itertools.count(1)

ANSI = re.compile(r"\x1b\[[0-9;]*m")
FAILED_NAMES_CAP = 20


def acceptance_log() -> Path:
    """Куда relay пишет полный прогон приёмки перед передачей хода.

    Лог живёт в git-каталоге этого дерева, а не в `/tmp`: два рабочих
    дерева на одной машине делят `/tmp` (CONTEXT §3, круг 56), и
    прогон координатора затёр бы прогон исполнителя.
    """
    return git_dir() / "relay-acceptance.log"


def failed_test_names(text: str) -> list[str]:
    """Строки pytest вида «FAILED файл::тест» из произвольного вывода."""
    names: list[str] = []
    for raw in text.splitlines():
        line = ANSI.sub("", raw).strip()
        if line.startswith(("FAILED ", "ERROR ")) and line not in names:
            names.append(line)
    return names


def failed_checks(text: str) -> list[str]:
    """Проваленные проверки самой приёмки (`bad …`), по именам."""
    checks: list[str] = []
    for raw in text.splitlines():
        line = ANSI.sub("", raw).strip()
        if line.startswith("ПРОВАЛ ") and line not in checks:
            checks.append(line)
    return checks


def run_acceptance(cwd: Path) -> tuple[int, str]:
    """Прогон приёмки: вывод идёт в терминал и сохраняется целиком.

    Сохранение нужно потому, что acceptance.sh печатает только хвост
    каждой проверки — по одному ему не восстановить, что именно упало.
    """
    chunks: list[str] = []
    with acceptance_log().open("w", encoding="utf-8", buffering=1) as log:
        proc = subprocess.Popen(("bash", "agent/acceptance.sh"),
                                cwd=str(cwd),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                errors="replace", bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            chunks.append(line)
        proc.wait()
    return proc.returncode, "".join(chunks)


def pytest_failure_names(cwd: Path) -> list[str]:
    """Имена упавших тестов отдельным прогоном, без трейсбэков.

    Нужно, когда приёмка их не показала: она печатает три последние
    строки прогона, и при нескольких падениях туда попадает не всё.
    """
    proc = subprocess.run(
        (sys.executable, "-m", "pytest", "-q", "--tb=no", "-rf",
         "-p", "no:randomly"),
        cwd=str(cwd), capture_output=True, text=True)
    return failed_test_names(proc.stdout or "")


def red_acceptance(rc: int, text: str, cwd: Path) -> str:
    """Отказ hand: какие тесты упали, какие проверки красные, где лог."""
    lines = [f"приёмка на дереве красная (код возврата {rc}) — ход не передан."]
    names = failed_test_names(text) or pytest_failure_names(cwd)
    if names:
        lines.append("упавшие тесты:")
        lines += [f"  {n}" for n in names[:FAILED_NAMES_CAP]]
        if len(names) > FAILED_NAMES_CAP:
            lines.append(f"  … и ещё {len(names) - FAILED_NAMES_CAP}")
    else:
        lines.append("упавших тестов нет — красна не проверка тестов, "
                     "а сама приёмка; смотри проваленные проверки ниже")
    checks = failed_checks(text)
    if checks:
        lines.append("проваленные проверки приёмки:")
        lines += [f"  {c}" for c in checks]
    lines.append(f"полный лог прогона: {acceptance_log()}")
    lines.append("исправь и повтори hand")
    return "\n".join(lines)


def cmd_hand(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    if a.to not in ROLES:
        die(f"--to принимает {ROLES}")
    if stop_file().exists() and not a.force:
        die(f"пауза: {stop_file()} на месте. relay.py resume — и повтори")
    # ТЗ-66 L1: красная приёмка на дереве — ход не передаётся.
    # Это закрывает щель: работа, уехавшая мимо хуков (плюмбинг,
    # amend), больше не уезжает на ветку.
    acc_script = Path.cwd() / "agent" / "acceptance.sh"
    if acc_script.exists():
        # ТЗ-66 L1: в песочницах unit-тестов relay acceptance.sh нет —
        # проверка опциональна по наличию скрипта
        rc, text = run_acceptance(Path.cwd())
        if rc != 0:
            die(red_acceptance(rc, text, Path.cwd()))
    fetch(a.remote, branch)
    baton = read_remote_baton(a.remote, branch)
    if baton is None:
        die(f"на {a.remote}/{branch} нет {BATON_PATH} — сначала relay.py init")
    me = "executor" if a.to == "coordinator" else "coordinator"
    if baton.get("holder") != me and not a.force:
        die(f"ход не твой: эстафету держит {baton.get('holder')}, "
            f"а передать пытается {me}. --force, если уверен.")
    new = dict(baton)
    new["holder"] = a.to
    new["round"] = baton.get("round", 0) + 1
    new["handed_by"] = me
    new["handed_at"] = now()
    new["note"] = a.note or ""
    new["paused"] = False
    if a.task:
        new["task"] = a.task
    if a.report:
        new["report"] = a.report
    message = a.message or (
        f"Эстафета: круг {new['round']}, ход у {a.to}"
        + (f" — {new['task']}" if new.get("task") else "")
    )
    sha = push_baton(a.remote, branch, new, list(a.add or []), message)
    # ТЗ-42 J1: пуш — не доказательство. Перечитываем BATON с origin:
    # ход считается переданным, только если там теперь держатель a.to.
    fetch(a.remote, branch)
    on_origin = read_remote_baton(a.remote, branch)
    if on_origin is None or on_origin.get("holder") != a.to:
        die(f"ход НЕ передан: на {a.remote}/{branch} держит "
            f"{(on_origin or {}).get('holder', 'никто')!r}, а не {a.to!r}. "
            "Работа не сдана. Проверь relay.py status и повтори hand.")
    print(f"передано коммитом {sha}")
    print(baton_line(on_origin))
    for rel in a.add or []:
        print("  вложено:", rel)
    return EXIT_OK


def cmd_pause(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    stop_file().write_text(now() + "\n", encoding="utf-8")
    print("пауза локально:", stop_file())
    fetch(a.remote, branch)
    baton = read_remote_baton(a.remote, branch)
    if baton is None:
        return EXIT_PAUSED
    if baton.get("holder") == a.side and not baton.get("paused"):
        new = dict(baton)
        new["paused"] = True
        new["note"] = a.note or "пауза по команде пользователя"
        new["handed_at"] = now()
        sha = push_baton(a.remote, branch, new, [], "Эстафета: пауза")
        print(f"пауза объявлена и второй стороне, коммит {sha}")
    else:
        print(f"эстафету держит {baton.get('holder')} — вторая сторона узнает "
              f"о паузе, когда вернёт ход")
    return EXIT_PAUSED


def cmd_resume(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    if stop_file().exists():
        stop_file().unlink()
        print("локальная пауза снята")
    fetch(a.remote, branch)
    baton = read_remote_baton(a.remote, branch)
    if baton is None:
        return EXIT_OK
    if (baton.get("paused") or baton.get("finished")) and baton.get("holder") == a.side:
        upd = dict(baton)
        upd["paused"] = False
        upd["finished"] = False
        upd["handed_at"] = now()
        sha = push_baton(a.remote, branch, upd, [], "Эстафета: продолжаем")
        print(f"пауза снята и на ветке, коммит {sha}")
    print(baton_line(read_remote_baton(a.remote, branch) or baton))
    return EXIT_OK


def cmd_finish(a: argparse.Namespace) -> int:
    branch = resolve_branch(a.branch)
    fetch(a.remote, branch)
    baton = read_remote_baton(a.remote, branch)
    if baton is None:
        die(f"на {a.remote}/{branch} нет {BATON_PATH}")
    new = dict(baton)
    new["finished"] = True
    new["note"] = a.note or "цикл закрыт"
    new["handed_at"] = now()
    sha = push_baton(a.remote, branch, new, [], "Эстафета: цикл закрыт")
    print(f"закрыто коммитом {sha}")
    print(baton_line(new))
    return EXIT_FINISHED


# ── разбор аргументов ────────────────────────────────────────────────────


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="agent/relay.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--remote", default=os.environ.get("RUSTERM_RELAY_REMOTE", "origin"))
    p.add_argument("--branch", default=None,
                   help="ветка смены; один раз — дальше помнится в .git/relay-branch")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="завести эстафету на ветке смены")
    s.add_argument("--holder", default="executor", choices=ROLES)
    s.add_argument("--round", type=int, default=1)
    s.add_argument("--task", default=None)
    s.add_argument("--report", default=None)
    s.add_argument("--note", default=None)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("status", help="чей ход прямо сейчас")
    s.add_argument("--assert-holder", dest="assert_holder", default=None,
                   metavar="РОЛЬ",
                   help="ненулевой код, если на origin/<ветка> держит не "
                        "эта роль (ТЗ-42 J2)")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("wait", help="блокирующее ожидание своего хода")
    s.add_argument("--for", dest="role", required=True, choices=ROLES)
    s.add_argument("--timeout", type=int, default=3600)
    s.add_argument("--interval", type=int, default=20)
    s.add_argument("--quiet", action="store_true")
    s.add_argument("--no-sync", action="store_true",
                   help="не подтягивать ветку смены в рабочее дерево, когда ход пришёл")
    s.set_defaults(func=cmd_wait)

    s = sub.add_parser("digest", help="пакет для рецензии: отчёт, коммиты, стражи")
    s.add_argument("--base", default="main")
    s.add_argument("--report", default=None,
                   help="какой отчёт разбирать, если эстафета его не назвала")
    s.add_argument("--lines", type=int, default=60,
                   help="сколько строк печатать из каждого раздела отчёта")
    s.set_defaults(func=cmd_digest)

    s = sub.add_parser("verify", help="прогнать acceptance.sh на ветке смены")
    s.add_argument("--worktree", default=os.environ.get("RUSTERM_RELAY_VERIFY_DIR"))
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("hand", help="передать ход второй стороне")
    s.add_argument("--to", required=True, choices=ROLES)
    s.add_argument("--task", default=None)
    s.add_argument("--report", default=None)
    s.add_argument("--note", default=None)
    s.add_argument("--add", action="append", default=[],
                   help="файл из рабочего дерева, который уезжает вместе с эстафетой")
    s.add_argument("-m", "--message", default=None)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_hand)

    s = sub.add_parser("pause", help="остановить цикл")
    s.add_argument("--side", default="coordinator", choices=ROLES)
    s.add_argument("--note", default=None)
    s.set_defaults(func=cmd_pause)

    s = sub.add_parser("resume", help="продолжить цикл")
    s.add_argument("--side", default="coordinator", choices=ROLES)
    s.set_defaults(func=cmd_resume)

    s = sub.add_parser("finish", help="закрыть цикл насовсем")
    s.add_argument("--note", default=None)
    s.set_defaults(func=cmd_finish)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(EXIT_PAUSED)
