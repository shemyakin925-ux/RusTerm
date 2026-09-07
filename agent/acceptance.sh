#!/usr/bin/env bash
# Приёмка ночной работы. Часть ТЗ agent/TASK-2.md, не рабочий файл агента.
# Агенту править запрещено — см. TASK-2.md §4.
# Запуск из корня репозитория:  bash agent/acceptance.sh
#
# Код возврата 0 — принято. Ненулевой — число проваленных проверок.

set -u
cd "$(git rev-parse --show-toplevel)" || exit 99

if [ -z "${PY:-}" ] && [ -x .venv/bin/python ]; then PY="$PWD/.venv/bin/python"; fi
PY="${PY:-python3}"
PASS=0
FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ok()   { printf '  \033[32mOK\033[0m    %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31mПРОВАЛ\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }
detail() { sed 's/^/          /' | head -25; }

printf '\033[1mПриёмка EquityLab — %s\033[0m\n' "$(date '+%Y-%m-%d %H:%M')"
printf 'ветка: %s   HEAD: %s\n' \
  "$(git rev-parse --abbrev-ref HEAD)" "$(git rev-parse --short HEAD)"

# ── 12. Скрипт приёмки не изменён ────────────────────────────────────────
head_ '12. Скрипт приёмки не изменён'
if git cat-file -e origin/main:agent/acceptance.sh 2>/dev/null; then
  if git show origin/main:agent/acceptance.sh | diff -q - agent/acceptance.sh >/dev/null; then
    ok 'agent/acceptance.sh совпадает с origin/main'
  else
    bad 'agent/acceptance.sh ИЗМЕНЁН — приёмка подогнана, работа не принимается'
    git show origin/main:agent/acceptance.sh | diff - agent/acceptance.sh | detail
  fi
else
  printf '  \033[33mПРОПУСК\033[0m нет origin/main:agent/acceptance.sh для сверки\n'
fi

# ── 1. Каждый модуль импортируется ───────────────────────────────────────
head_ '1. Каждый модуль rusterm/ импортируется'
"$PY" - >"$TMP/imports.txt" 2>&1 <<'PYEOF'
import importlib, pkgutil, sys
sys.path.insert(0, ".")
bad = []
try:
    import rusterm
except Exception as e:
    print(f"rusterm: {type(e).__name__}: {e}"); sys.exit(1)
for mod in pkgutil.walk_packages(rusterm.__path__, "rusterm."):
    try:
        importlib.import_module(mod.name)
    except Exception as e:
        bad.append(f"{mod.name}: {type(e).__name__}: {e}")
for line in bad:
    print(line)
sys.exit(1 if bad else 0)
PYEOF
if [ $? -eq 0 ]; then
  ok "все модули импортируются ($("$PY" -V 2>&1))"
else
  bad 'модули не импортируются — код не запускался'
  detail < "$TMP/imports.txt"
fi

# ── 2. Пятнадцать инвариантов на месте ───────────────────────────────────
head_ '2. tests/test_invariants.py: пятнадцать инвариантов'
if [ -f tests/test_invariants.py ]; then
  MISSING=""
  for n in 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15; do
    grep -qE "^def test_i${n}_" tests/test_invariants.py || MISSING="$MISSING I$n"
  done
  if [ -z "$MISSING" ]; then
    ok 'все пятнадцать test_i01_…test_i15_ присутствуют'
  else
    bad "отсутствуют инварианты:$MISSING"
  fi
else
  bad 'tests/test_invariants.py не существует'
fi

# ── 3. Полный прогон тестов ──────────────────────────────────────────────
head_ '3. pytest целиком'
"$PY" -m pytest -q >"$TMP/pytest.txt" 2>&1
RC=$?
tail -3 "$TMP/pytest.txt" | detail
if [ $RC -eq 0 ]; then
  ok "pytest, код возврата 0"
else
  bad "pytest, код возврата $RC"
fi

# ── 4. У каждого xfail есть причина ──────────────────────────────────────
head_ '4. У каждого xfail непустая причина'
"$PY" - tests >"$TMP/xfail.txt" 2>&1 <<'XFEOF'
import ast, pathlib, sys
bad, total = [], 0
for f in sorted(pathlib.Path(sys.argv[1]).rglob("test_*.py")):
    try:
        tree = ast.parse(f.read_text())
    except SyntaxError as e:
        bad.append(f"{f}: синтаксическая ошибка: {e}"); continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not ast.unparse(node.func).endswith("mark.xfail"):
            continue
        total += 1
        kw = next((k.value for k in node.keywords if k.arg == "reason"), None)
        text = "" if kw is None else (kw.value if isinstance(kw, ast.Constant) else ast.unparse(kw))
        if not str(text).strip():
            bad.append(f"{f}:{node.lineno}: xfail без непустого reason=")
print(f"TOTAL={total}")
for line in bad:
    print(line)
sys.exit(1 if bad else 0)
XFEOF
if [ $? -eq 0 ]; then
  ok "все xfail с причиной ($(grep '^TOTAL=' "$TMP/xfail.txt" | cut -d= -f2) шт.)"
else
  bad 'есть xfail без непустой причины — молчаливое глушение теста'
  grep -v '^TOTAL=' "$TMP/xfail.txt" | detail
fi

# ── 5. Нет заглушек в рабочем пути ───────────────────────────────────────
head_ '5. Нет NotImplementedError / TODO / FIXME в rusterm/'
if grep -rnE 'NotImplementedError|\bTODO\b|\bFIXME\b' rusterm/ --include='*.py' >"$TMP/stubs.txt" 2>/dev/null; then
  bad "заглушки в рабочем пути ($(wc -l < "$TMP/stubs.txt" | tr -d ' ') шт.)"
  detail < "$TMP/stubs.txt"
else
  ok 'заглушек нет'
fi

# ── 6. Ни строки Qt ──────────────────────────────────────────────────────
head_ '6. Ни строки Qt'
if grep -rniE '(import|from)[[:space:]]+(PySide6|PyQt5|PyQt6|qtpy)' rusterm/ tests/ --include='*.py' >"$TMP/qt.txt" 2>/dev/null; then
  bad 'найдены импорты Qt'
  detail < "$TMP/qt.txt"
else
  ok 'Qt не импортируется нигде'
fi

# ── 7. SQL только в rusterm/store/ ───────────────────────────────────────
head_ '7. SQL только в rusterm/store/'
if grep -rnE 'execute\(|executemany\(|executescript\(|CREATE TABLE|SELECT .* FROM' \
     rusterm/ --include='*.py' 2>/dev/null | grep -v '^rusterm/store/' >"$TMP/sql.txt"; then
  bad 'SQL за пределами слоя хранилища'
  detail < "$TMP/sql.txt"
else
  ok 'SQL не выходит за rusterm/store/'
fi

# ── 8. HTTP только в rusterm/providers/ ──────────────────────────────────
head_ '8. HTTP-библиотеки только в rusterm/providers/'
if grep -rnE '^[[:space:]]*(import|from)[[:space:]]+(httpx|requests|urllib\.request|http\.client|aiohttp)' \
     rusterm/ --include='*.py' 2>/dev/null | grep -v '^rusterm/providers/' >"$TMP/http.txt"; then
  bad 'HTTP за пределами провайдеров (инвариант I9)'
  detail < "$TMP/http.txt"
else
  ok 'HTTP не выходит за rusterm/providers/'
fi

# ── 9. Провайдеры не пишут в базу ────────────────────────────────────────
head_ '9. Провайдеры не импортируют rusterm.store.db (I10)'
if [ -d rusterm/providers ] && \
   grep -rnE '(import|from)[[:space:]]+rusterm\.store' rusterm/providers/ --include='*.py' >"$TMP/prov.txt" 2>/dev/null; then
  bad 'провайдер тянет слой хранилища'
  detail < "$TMP/prov.txt"
else
  ok 'провайдеры не знают о хранилище'
fi

# ── 10. docs/ не изменён, кроме новых ADR ────────────────────────────────
head_ '10. docs/ не изменён, кроме новых ADR'
if git cat-file -e origin/main^{commit} 2>/dev/null; then
  git diff --name-status origin/main HEAD -- docs/ >"$TMP/docs.txt" 2>/dev/null
  if grep -vE '^A[[:space:]]+docs/adr/' "$TMP/docs.txt" | grep -q .; then
    bad 'docs/ правился помимо добавления новых ADR'
    grep -vE '^A[[:space:]]+docs/adr/' "$TMP/docs.txt" | detail
  else
    ADR=$(grep -cE '^A[[:space:]]+docs/adr/' "$TMP/docs.txt" || true)
    ok "docs/ нетронут, новых ADR: ${ADR:-0}"
  fi
else
  printf '  \033[33mПРОПУСК\033[0m нет origin/main для сверки\n'
fi

# ── 11. Тесты без сторонних пакетов, кроме pytest ────────────────────────
head_ '11. Тесты проходят без zstandard (обязателен gzip-фолбэк)'
mkdir -p "$TMP/block"
cat > "$TMP/block/zstandard.py" <<'PYEOF'
raise ImportError("zstandard заблокирован проверкой приёмки: нужен gzip-фолбэк")
PYEOF
PYTHONPATH="$TMP/block:${PYTHONPATH:-}" "$PY" -m pytest -q >"$TMP/nozstd.txt" 2>&1
RC2=$?
tail -3 "$TMP/nozstd.txt" | detail
if [ $RC2 -eq 0 ]; then
  ok 'без zstandard тесты зелёные'
else
  bad "без zstandard код возврата $RC2 — фолбэк не реализован"
fi

# ── Итог ─────────────────────────────────────────────────────────────────
printf '\n\033[1mИтог: пройдено %d, провалено %d\033[0m\n' "$PASS" "$FAIL"
if [ "$FAIL" -eq 0 ]; then
  printf '\033[32mПринято.\033[0m\n'
else
  printf '\033[31mНе принято. Разбирать по проваленным пунктам сверху вниз.\033[0m\n'
fi
exit "$FAIL"
