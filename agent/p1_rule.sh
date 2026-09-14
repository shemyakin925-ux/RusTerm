#!/usr/bin/env bash
# ТЗ-32 D5: правило замены булавки для сторожа P1.
#
# Прежний grep любой '-...assert' строки делал НЕВОЗМОЖНОЙ законную
# замену «снял -> стал сильнее» (каждая миграция версий tripается,
# REPORT-31 Disputed; задача ТЗ-32 D5 прямо разрешает правку
# selfcheck.sh). Правило теперь такое: снятые assert-строки из файла
# проходят только когда (а) в сообщении коммита есть блок
#     ЗАМЕНА-БУЛАВКИ: <file>::<test> -> <successor file>::<test>
#     ПОЧЕМУ СИЛЬНЕЕ: <одна строка>
# с именем ЭТОГО файла, и (б) тот же файл получает не меньше
# assert-строк, чем потерял. Всё остальное остаётся красным.
#
# Сообщение берётся из HEAD (прогон по уже сделанному коммиту) либо
# из .git/COMMIT_EDITMSG (декларация перед коммитом). Запуск из корня
# git-репозитория: bash agent/p1_rule.sh; 0 = зелёный, 1 = красный.

set -u

STAGED=$(git diff --cached --name-only -- '*.py' 2>/dev/null || true)
[ -z "$STAGED" ] && exit 0

MSG="$(git log -1 --format=%B 2>/dev/null || true)"
if [ -f .git/COMMIT_EDITMSG ]; then
    MSG="$MSG
$(cat .git/COMMIT_EDITMSG 2>/dev/null || true)"
fi

FAIL=""
for f in $STAGED; do
    removed=$(git diff --cached -- "$f" | grep -c '^-.*assert' || true)
    [ "$removed" -eq 0 ] && continue
    added=$(git diff --cached -- "$f" | grep -c '^+.*assert' || true)
    declared=$(printf '%s\n' "$MSG" | grep -cF "ЗАМЕНА-БУЛАВКИ: ${f}::" \
        || true)
    why=$(printf '%s\n' "$MSG" | grep -c '^ПОЧЕМУ СИЛЬНЕЕ:' || true)
    if [ "$added" -ge "$removed" ] && [ "$declared" -ge 1 ] \
            && [ "$why" -ge 1 ]; then
        continue
    fi
    if [ "$declared" -eq 0 ] || [ "$why" -eq 0 ]; then
        FAIL="$FAIL $f (нет объявления ЗАМЕНА-БУЛАВКИ/ПОЧЕМУ СИЛЬНЕЕ)"
    else
        FAIL="$FAIL $f (добавлено assert: $added, снято: $removed)"
    fi
done

if [ -n "$FAIL" ]; then
    printf '%s\n' "P1: необъявленная замена булавок:$FAIL"
    exit 1
fi
exit 0
