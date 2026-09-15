#!/usr/bin/env bash
# TASK-19 F7: замаскированный пайпом код выхода становится невозможным.
#
# Дефект трёх ночей подряд (REPORT-15 Disputed, REPORT-17 вопрос 1):
# `bash agent/acceptance.sh | tail -5` возвращал код tail — всегда 0 —
# и красная приёмка уезжала в push. Здесь приёмка пишется в файл, её
# статус читается отдельно, последние строки печатаются только после
# того, как статус известен, и любой провал гасит выход.
#
# Использование: bash agent/selfcheck.sh   (из любой точки репозитория)
# Заменяет четыре ручные проверки §1.3 ТЗ-19. agent/acceptance.sh не
# правится никогда (проверка 12 сверяет его с origin/main).
set -u
cd "$(dirname "$0")/.." || exit 1

fail() {
    printf 'SELFCHECK FAIL (%s): %s\n' "$1" "$2" >&2
    exit 1
}

# ТЗ-37 I5: стражи исполняются из КОММИТА, не из рабочего дерева —
# иначе правка стража в рабочем дереве легализует один обходной
# коммит (случай 95b669a). Незастейдженная правка стража — красная
# сама по себе, с именем файла.
GUARD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/selfcheck-guards.XXXXXX")
for guard in agent/p1_rule.sh agent/p6_rule.sh; do
    base=$(basename "$guard")
    if ! git diff --quiet -- "$guard"; then
        fail "I5" "страж изменён в рабочем дереве и не застейджен: $guard"
    fi
    if git diff --cached --name-only -- "$guard" | grep -q .; then
        git show ":$guard" > "$GUARD_DIR/$base" 2>/dev/null \
            || fail "I5" "$guard нет в индексе"
        echo "I5: $base исполняется из index"
    else
        git show "HEAD:$guard" > "$GUARD_DIR/$base" 2>/dev/null \
            || fail "I5" "$guard нет в HEAD"
        echo "I5: $base исполняется из HEAD"
    fi
done

# ТЗ-44 L1: коммит, обещающий правку стража сообщением, обязан её
# нести. Проверяются ОБА состояния: pending (сообщение + staged) и
# последний коммит (HEAD + HEAD~1..HEAD). Красный называет файл.
CMSG="$(git rev-parse --git-path COMMIT_EDITMSG 2>/dev/null || true)"
PENDING_FILES=$(mktemp "${TMPDIR:-/tmp}/selfcheck-pf.XXXXXX")
git diff --cached --name-only > "$PENDING_FILES" 2>/dev/null || true
PENDING_MSG=$(mktemp "${TMPDIR:-/tmp}/selfcheck-pm.XXXXXX")
if [ -n "$CMSG" ] && [ -f "$CMSG" ]; then cp "$CMSG" "$PENDING_MSG"; else : > "$PENDING_MSG"; fi
if ! bash agent/check_mention.sh "$PENDING_MSG" "$PENDING_FILES"; then
    fail "L1" "pending commit mentions a guard it does not carry"
fi
rm -f "$PENDING_MSG" "$PENDING_FILES"
LAST_FILES=$(mktemp "${TMPDIR:-/tmp}/selfcheck-lf.XXXXXX")
git diff --name-only HEAD~1 HEAD > "$LAST_FILES" 2>/dev/null || true
LAST_MSG=$(mktemp "${TMPDIR:-/tmp}/selfcheck-lm.XXXXXX")
git log -1 --format=%B HEAD > "$LAST_MSG" 2>/dev/null || : > "$LAST_MSG"
if ! bash agent/check_mention.sh "$LAST_MSG" "$LAST_FILES"; then
    fail "L1" "last commit mentions a guard it does not carry"
fi
rm -f "$LAST_MSG" "$LAST_FILES"

# P1: снятые assert-строки — только через объявленную замену булавки
# (правило ТЗ-32 D5: блок ЗАМЕНА-БУЛАВКИ/ПОЧЕМУ СИЛЬНЕЕ в сообщении
# коммита и не меньше assert-строк в том же файле; всё остальное
# красное). Сторож смотрит только код: в прозе (*.md) слово «assert» —
# часть русской речи бэклога, и маркер диффа '-' делает из неё ложную
# тревогу (случай B24, 11.09).
if ! bash "$GUARD_DIR/p1_rule.sh"; then
    fail "P1" "undeclared pin replacement in staged diff"
fi

# P2: db.py не правится, кроме подъёма _SCHEMA_VERSION (P2 ТЗ)
P2=$(git diff --cached rusterm/store/db.py \
        | grep '^-[^-]' | grep -v '^-_SCHEMA_VERSION' || true)
if [ -n "$P2" ]; then
    printf '%s\n' "$P2" | head -5
    fail "P2" "db.py lines removed beyond the _SCHEMA_VERSION bump"
fi

# P6: файлы координатора не касаются широким git add (ТЗ-33 E6,
# регрессия e68c1b5: устаревший agent/TASK.md уехал в коммит).
# Исполняется извлечённая из коммита копия стража (I5).
if ! bash "$GUARD_DIR/p6_rule.sh"; then
    fail "P6" "coordinator-owned files staged"
fi

# P3/P4: ничего вне git, никакого мусора
P34=$(git status --porcelain | grep '^??' || true)
if [ -n "$P34" ]; then
    printf '%s\n' "$P34"
    fail "P3/P4" "untracked files present - git add or delete them"
fi

# Приёмка: статус читается из файла, не из пайпа; последние строки
# печатаются только когда статус известен.
ACC=$(mktemp "${TMPDIR:-/tmp}/selfcheck-acc.XXXXXX") \
    || fail "acceptance" "cannot create temp file"
trap 'rm -f "$ACC"' EXIT
bash agent/acceptance.sh > "$ACC" 2>&1
ACC_STATUS=$?
tail -4 "$ACC"
[ "$ACC_STATUS" -eq 0 ] \
    || fail "acceptance" "exit status $ACC_STATUS"
# ТЗ-27 N6: ожидаемое число проверок читается из acceptance.sh, а не
# захардкожено — добавление четырнадцатой проверки не делает селфчек лжецом
EXPECTED_CHECKS=$(grep -cE "^head_ '" agent/acceptance.sh)
[ "$EXPECTED_CHECKS" -ge 1 ] || EXPECTED_CHECKS=13
grep -q "пройдено $EXPECTED_CHECKS, провалено 0" "$ACC" \
    || fail "acceptance" "expected $EXPECTED_CHECKS checks passed, 0 failed"

printf 'SELFCHECK OK\n'
exit 0
