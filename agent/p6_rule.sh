#!/usr/bin/env bash
# ТЗ-33 E6: файлы координатора недоступны широкому `git add`.
#
# Регрессия e68c1b5: `git add -A` протащил устаревшую рабочую копию
# agent/TASK.md в коммит исполнителя. Сторож смотрит staged-дифф и
# запрещает касаться файлов, которые пишет координатор:
#   agent/TASK.md  agent/TASK-*.md  agent/PROTOCOL.md  agent/CONTEXT.md
#   agent/BACKLOG.md  agent/LAUNCH.md  agent/acceptance.sh
# Свои файлы исполнителя не трогаются: agent/REPORT-*.md,
# agent/STATE.json, agent/BATON.json, agent/p1_rule.sh,
# agent/selfcheck.sh, rusterm/, tests/, docs/adr/.
# Красный вывод называет файл и команду отката.
# Запуск из корня git-репозитория: bash agent/p6_rule.sh.

set -u

BLOCKED="${P6_BLOCKED:-agent/TASK.md
agent/TASK-*.md
agent/PROTOCOL.md
agent/CONTEXT.md
agent/BACKLOG.md
agent/LAUNCH.md
agent/acceptance.sh}"

STAGED=$(git diff --cached --name-only 2>/dev/null || true)
[ -z "$STAGED" ] && exit 0

# Единственное исключение (ТЗ-34 F6): правка agent/PROTOCOL.md
# разрешена, когда сообщение коммита объявляет её строкой
#   РАЗРЕШЕНИЕ-ПРОТОКОЛА: <что и почему>
# (та же механика объявленной замены, что у P1/D5).
MSG="$(git log -1 --format=%B 2>/dev/null || true)"
if [ -f .git/COMMIT_EDITMSG ]; then
    MSG="$MSG
$(cat .git/COMMIT_EDITMSG 2>/dev/null || true)"
fi

FAIL=""
while IFS= read -r staged; do
    [ -z "$staged" ] && continue
    if [ "$staged" = "agent/PROTOCOL.md" ]; then
        if printf '%s\n' "$MSG" | grep -q '^РАЗРЕШЕНИЕ-ПРОТОКОЛА:'; then
            continue
        fi
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
    printf '%s\n' "P6: файлы координатора в staged-диффе:$FAIL"
    printf 'откат: git restore --staged <файл> && git checkout -- <файл>\n'
    exit 1
fi
exit 0
