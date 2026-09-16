#!/usr/bin/env bash
# ТЗ-33 E6 / ТЗ-36 H6: файлы координатора недоступны широкому
# `git add`. Регрессия e68c1b5: `git add -A` протащил устаревшую
# рабочую копию agent/TASK.md; обход 95b669a: расширенная в рабочем
# дереве версия ЭТОГО стража сделала зелёным то, что закоммиченный
# страж запрещает. Поэтому:
#   1) список защищённых файлов — отсюда, не из окружения (H6.1);
#   2) маркер РАЗРЕШЕНИЕ-<X>: работает только если файл задания,
#      названный в agent/BATON.json, несёт строку
#      `РАЗРЕШЕНО ПРАВИТЬ: <path>` (H6.2) — исключение нельзя выдать
#      самому себе;
#   3) пустой индекс — не зелёный свет: проверяется HEAD~1..HEAD, и в
#      выводе сказано, какой из двух диффов смотрели (H6.3).
# Запуск из корня git-репозитория: bash agent/p6_rule.sh.

set -u

# H6.1: список — собственность файла, переопределение окружением убрано
BLOCKED="agent/TASK.md
agent/TASK-*.md
agent/PROTOCOL.md
agent/CONTEXT.md
agent/BACKLOG.md
agent/LAUNCH.md
agent/acceptance.sh"

STAGED=$(git diff --cached --name-only 2>/dev/null || true)
SCOPE="staged (index vs HEAD)"
if [ -z "$STAGED" ]; then
    # H6.3: после коммита индекс пуст — смотрим последний коммит
    STAGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || true)
    SCOPE="HEAD~1..HEAD (last commit)"
    # ТЗ-43 K1: пропуск опирается на ПРОВЕРЯЕМОЕ, не на сообщение
    # (его пишешь ты): BATON.json в коммите действительно менялся, и
    # состав — только BATON.json плюс файлы координатора. Иначе —
    # красный: это обход 95b669a.
    LAST_MSG=$(git log -1 --format=%B HEAD 2>/dev/null || true)
    if printf '%s\n' "$LAST_MSG" | grep -q '^Эстафета: круг'; then
        BATON_CHANGED=$(git diff HEAD~1 HEAD -- agent/BATON.json \
            | grep -c '^[+-]' || true)
        FOREIGN=$(printf '%s\n' "$STAGED" | grep -v -E \
            '^agent/(BATON\.json|TASK-[0-9]+\.md|CONTEXT\.md|BACKLOG\.md|LAUNCH\.md|PROTOCOL\.md|REPORT-[0-9]+\.md)$')
        if [ -z "$FOREIGN" ] && [ "$BATON_CHANGED" -gt 0 ]; then
            echo "P6: $SCOPE — коммит эстафеты, пропущен"
            exit 0
        fi
        if [ -n "$FOREIGN" ]; then
            echo "P6: в коммите эстафеты чужие файлы (исполнителя):$FOREIGN"
        else
            echo "P6: BATON.json не менялся — сообщение «Эстафета» не доказательство"
        fi
        exit 1
    fi
fi

# файл задания, названный эстафетой; нет — авторизаций нет
TASK_FILE="none"
if [ -f agent/BATON.json ]; then
    TASK_FILE=$(python3 -c "import json;print(json.load(open('agent/BATON.json')).get('task','none'))" 2>/dev/null || echo none)
fi
AUTH_LINES=""
if [ "$TASK_FILE" != "none" ] && [ -f "$TASK_FILE" ]; then
    AUTH_LINES=$(grep '^РАЗРЕШЕНО ПРАВИТЬ:' "$TASK_FILE" 2>/dev/null || true)
fi

authorized() {  # <path> — есть ли строка РАЗРЕШЕНО ПРАВИТЬ: <path>
    printf '%s\n' "$AUTH_LINES" | grep -qF "РАЗРЕШЕНО ПРАВИТЬ: $1"
}

# сообщение коммита: HEAD (прогон по коммиту) или COMMIT_EDITMSG
# (декларация перед коммитом)
MSG="$(git log -1 --format=%B 2>/dev/null || true)"
# ТЗ-37 I7: .git не всегда папка (linked worktree) — путь через
# git rev-parse, как в p1_rule.sh
EDITMSG=$(git rev-parse --git-path COMMIT_EDITMSG 2>/dev/null || true)
if [ -n "$EDITMSG" ] && [ -f "$EDITMSG" ]; then
    MSG="$MSG
$(cat "$EDITMSG" 2>/dev/null || true)"
fi

FAIL=""
while IFS= read -r staged; do
    [ -z "$staged" ] && continue
    if [ "$staged" = "agent/PROTOCOL.md" ] || [ "$staged" = "agent/CONTEXT.md" ]; then
        # ТЗ-34 F6 / ТЗ-35 G3: правка возможна ТОЛЬКО с объявлением в
        # сообщении И строкой РАЗРЕШЕНО ПРАВИТЬ: в файле задания (H6.2)
        marker="РАЗРЕШЕНИЕ-ПРОТОКОЛА:"
        [ "$staged" = "agent/CONTEXT.md" ] && marker="РАЗРЕШЕНИЕ-КОНТЕКСТА:"
        if printf '%s\n' "$MSG" | grep -q "^$marker" \
                && authorized "$staged"; then
            continue
        fi
        FAIL="$FAIL $staged (нет маркера $marker или задания нет РАЗРЕШЕНО ПРАВИТЬ: $staged в $TASK_FILE)"
        continue
    fi
    while IFS= read -r pattern; do
        [ -z "$pattern" ] && continue
        case "$staged" in
            $pattern)
                FAIL="$FAIL $staged"
                break
                ;;
        esac
    done <<< "$BLOCKED"
done <<< "$STAGED"

if [ -n "$FAIL" ]; then
    printf '%s\n' "P6 ($SCOPE): файлы координатора:$FAIL"
    printf 'откат: git restore --staged <файл> && git checkout -- <файл>\n'
    exit 1
fi
exit 0
