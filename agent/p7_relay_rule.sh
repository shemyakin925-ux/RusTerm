#!/usr/bin/env bash
# ТЗ-65 K1: эстафетный коммит перестаёт быть щелью.
#   1) заголовок «Эстафета:» — только у передач хода: agent/BATON.json
#      плюс файлы координатора, и с меткой Relay-Hand в теле;
#   2) ребейз не тащит работу в эстафетный коммит (rebase-merge идёт
#      с EDITMSG, чей заголовок —_subject перенесённого коммита);
#   3) audit-режим: p7_relay_rule.sh check:<sha> — красный/зелёный на
#      любом коммите (круг 82 показан в тестах на настоящих SHA).
# Amend-попытка хуком не различима (GIT_REFLOG_ACTION пуст,
# COMMIT_EDITMSG при -m/--no-edit не обновляется — измерено) —
# результат ловится post-hoc в HEAD~1..HEAD и аудитом.
set -u

ALLOWED_RE='^(agent/BATON\.json|agent/(TASK-[0-9]+\.md|CONTEXT\.md|BACKLOG\.md|LAUNCH\.md|PROTOCOL\.md|REPORT-[0-9]+\.md))$'

foreign_files() {
    grep -v -E "$ALLOWED_RE" || true
}

case "${1:-precommit}" in
    precommit)
        # ребейз: перенос эстафетного коммита с работой — красный
        REBASE_DIR=$(git rev-parse --git-path rebase-merge 2>/dev/null || true)
        if [ -n "$REBASE_DIR" ] && [ -d "$REBASE_DIR" ]; then
            EDITMSG=$(git rev-parse --git-path COMMIT_EDITMSG 2>/dev/null || true)
            if [ -n "$EDITMSG" ] && [ -f "$EDITMSG" ] \
                    && head -1 "$EDITMSG" | grep -q '^Эстафета:'; then
                FOREIGN=$(git diff --cached --name-only 2>/dev/null \
                    | foreign_files)
                if [ -n "$FOREIGN" ]; then
                    printf '%s\n' "P7: ребейз тащит работу в эстафетном коммите:$FOREIGN" >&2
                    exit 1
                fi
            fi
        fi
        exit 0
        ;;
    check:*)
        SHA="${1#check:}"
        if ! git log -1 --format=%s "$SHA" 2>/dev/null | grep -q '^Эстафета:'; then
            echo "P7: $SHA — не эстафетный (обычный коммит, зелёный)"
            exit 0
        fi
        FOREIGN=$(git diff-tree --no-commit-id --name-only -r "$SHA" \
            | foreign_files)
        if [ -n "$FOREIGN" ]; then
            printf '%s\n' "P7: $SHA — эстафета несёт работу:$FOREIGN" >&2
            exit 1
        fi
        echo "P7: $SHA — чистая передача хода"
        exit 0
        ;;
    *)
        echo "P7: неизвестный режим $1" >&2
        exit 1
        ;;
esac
