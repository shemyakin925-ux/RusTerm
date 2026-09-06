#!/bin/bash
# ---------------------------------------------------------------------------
# probe.sh — разведка доступа к серверам раскрытия информации эмитентов.
#
# Отвечает на вопросы, от которых зависит вся Фаза 0a и governance-модуль:
#   1. Пускает ли e-disclosure.ru домашний IP (с датацентрового — 403 на всё).
#   2. Отдаётся ли содержимое без JavaScript.
#   3. На какой глубине доступен архив сообщений.
#   4. Где начинается rate limit.
#   5. Какие из пяти уполномоченных агентств доступны как запасной путь.
#
# Ничего не парсит и не интерпретирует — только измеряет и складывает сырые
# ответы. Разбирать их будем потом и по сохранённым файлам, а не по живому сайту.
#
# Запуск:   bash probe.sh
# Настройки: DELAY=3 RATE_N=15 bash probe.sh
# ---------------------------------------------------------------------------
set -u

DELAY="${DELAY:-3}"          # пауза между запросами, секунд
RATE_N="${RATE_N:-15}"       # сколько запросов в тесте на rate limit
TIMEOUT="${TIMEOUT:-25}"

BASE="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BASE/out/$STAMP"
RAW="$OUT/raw"
TSV="$OUT/results.tsv"
REPORT="$OUT/report.md"

UA_BROWSER='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'
UA_BOT='RusTermProbe/0.1 (research; +shemyakin925@gmail.com)'

mkdir -p "$RAW"
printf 'name\tua\tcode\ttime_s\tbytes\tctype\turl\n' > "$TSV"

say()  { printf '%s\n' "$*"; }
line() { printf -- '---------------------------------------------------------------\n'; }

slug() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'; }

# fetch <name> <url> <browser|bot>  -> печатает код, пишет тело в raw/
fetch() {
  name="$1"; url="$2"; uam="$3"
  if [ "$uam" = "browser" ]; then ua="$UA_BROWSER"; else ua="$UA_BOT"; fi
  f="$RAW/$(slug "$name").$uam"
  res=$(curl -sS -L --compressed --max-time "$TIMEOUT" \
        -A "$ua" \
        -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
        -H 'Accept-Language: ru-RU,ru;q=0.9,en-US;q=0.8' \
        -D "$f.headers" -o "$f.body" \
        -w '%{http_code}\t%{time_total}\t%{size_download}\t%{content_type}' \
        "$url" 2>"$f.err")
  if [ -z "$res" ]; then res=$(printf '000\t0\t0\tconnection-failed'); fi
  code=$(printf '%s' "$res" | cut -f1)
  printf '%s\t%s\t%s\t%s\n' "$name" "$uam" "$res" "$url" >> "$TSV"
  # копия в UTF-8, если сервер отдал windows-1251
  if grep -qi 'charset=windows-1251' "$f.headers" "$f.body" 2>/dev/null; then
    iconv -f windows-1251 -t utf-8 "$f.body" > "$f.utf8.html" 2>/dev/null
  fi
  printf '  %-34s %-7s -> %s\n' "$name" "$uam" "$code" >&2
  printf '%s' "$code"
}

pause() { sleep "$DELAY"; }

# ===========================================================================
say "RusTerm · разведка доступа к раскрытию   $(date '+%Y-%m-%d %H:%M:%S')"
say "Результаты: $OUT"
line

# --- 0. Контроль: работает ли сеть и ISS вообще ----------------------------
say "[0] Контроль сети"
ISS_CODE=$(fetch "control-iss-securities" \
  "https://iss.moex.com/iss/securities.json?q=SBER&iss.meta=off" bot)
pause
if [ "$ISS_CODE" != "200" ]; then
  say "!! ISS недоступен ($ISS_CODE). Дальше мерить бессмысленно — проверьте сеть/VPN."
fi
line

# --- 1. e-disclosure: главный вопрос ---------------------------------------
say "[1] e-disclosure.ru (Интерфакс) — пускает ли этот IP"
ED_ROBOTS_B=$(fetch "ed-robots" "https://www.e-disclosure.ru/robots.txt" browser); pause
ED_ROBOTS_R=$(fetch "ed-robots" "https://www.e-disclosure.ru/robots.txt" bot);     pause
ED_HOME=$(fetch    "ed-home"   "https://www.e-disclosure.ru/" browser);            pause
ED_LIST=$(fetch    "ed-companies" "https://www.e-disclosure.ru/portal/companies.aspx" browser); pause

ED_BODY="$RAW/ed-companies.browser.body"
if [ "$ED_LIST" = "200" ] && [ -s "$ED_BODY" ]; then
  N_LINKS=$(grep -o 'company\.aspx?id=[0-9]*' "$ED_BODY" | sort -u | wc -l | tr -d ' ')
  say "    ссылок на карточки компаний в HTML: $N_LINKS  (>0 = рендер серверный, JS не нужен)"
  FIRST_ID=$(grep -o 'company\.aspx?id=[0-9]*' "$ED_BODY" | head -1 | sed 's/.*=//')
else
  N_LINKS=0; FIRST_ID=""
fi
line

# --- 2. Карточка компании и глубина архива ---------------------------------
say "[2] Карточка эмитента и глубина архива"
if [ -n "${FIRST_ID:-}" ]; then
  fetch "ed-company"  "https://www.e-disclosure.ru/portal/company.aspx?id=$FIRST_ID" browser >/dev/null; pause
  fetch "ed-events"   "https://www.e-disclosure.ru/portal/event.aspx?id=$FIRST_ID"   browser >/dev/null; pause
  fetch "ed-files"    "https://www.e-disclosure.ru/portal/files.aspx?id=$FIRST_ID"   browser >/dev/null; pause
  for f in "$RAW/ed-company.browser.body" "$RAW/ed-events.browser.body" "$RAW/ed-files.browser.body"; do
    [ -s "$f" ] || continue
    YEARS=$(grep -oE '\b(19|20)[0-9]{2}\b' "$f" | sort -u | tr '\n' ' ')
    say "    $(basename "$f"): годы в тексте: ${YEARS:-нет}"
  done
else
  say "    пропущено: со страницы списка не удалось взять id эмитента"
fi
line

# --- 3. Rate limit ---------------------------------------------------------
say "[3] Rate limit: $RATE_N запросов с паузой ${DELAY}с"
RL_URL="https://www.e-disclosure.ru/portal/companies.aspx"
[ -n "${FIRST_ID:-}" ] && RL_URL="https://www.e-disclosure.ru/portal/company.aspx?id=$FIRST_ID"
RL_CODES=""; RL_FIRST_FAIL=""
i=1
while [ "$i" -le "$RATE_N" ]; do
  c=$(curl -sS -o /dev/null -L --compressed --max-time "$TIMEOUT" -A "$UA_BROWSER" \
        -w '%{http_code}' "$RL_URL" 2>/dev/null)
  [ -z "$c" ] && c="000"
  RL_CODES="$RL_CODES $i:$c"
  if [ "$c" != "200" ] && [ -z "$RL_FIRST_FAIL" ]; then RL_FIRST_FAIL="$i"; fi
  printf '  %2d -> %s\n' "$i" "$c"
  i=$((i+1))
  sleep "$DELAY"
done
if [ -n "$RL_FIRST_FAIL" ]; then
  say "    первый не-200 на запросе №$RL_FIRST_FAIL"
else
  say "    все $RATE_N прошли на паузе ${DELAY}с — лимит не нащупан, можно поднимать темп"
fi
line

# --- 4. Альтернативные уполномоченные агентства ----------------------------
say "[4] Запасные серверы раскрытия"
fetch "skrin-home"    "https://disclosure.skrin.ru/"                   browser >/dev/null; pause
fetch "skrin-by-inn"  "https://disclosure.skrin.ru/disclosure/7707083893" browser >/dev/null; pause
fetch "prime-home"    "https://disclosure.1prime.ru/"                  browser >/dev/null; pause
fetch "akm-home"      "https://disclosure.ru/"                         browser >/dev/null; pause
fetch "azipi-home"    "https://disclosure.azipi.ru/"                   browser >/dev/null; pause
line

# --- Отчёт -----------------------------------------------------------------
{
  echo "# Разведка доступа к раскрытию — $STAMP"
  echo
  echo "Пауза между запросами: ${DELAY}с. Запросов в rate-тесте: $RATE_N."
  echo
  echo '## Ключевые ответы'
  echo
  echo "- e-disclosure пускает этот IP: **$( [ "$ED_LIST" = "200" ] && echo ДА || echo "НЕТ (код $ED_LIST)" )**"
  echo "- Серверный рендер без JS: **$( [ "${N_LINKS:-0}" -gt 0 ] && echo "ДА, ссылок на карточки: $N_LINKS" || echo НЕТ )**"
  echo "- robots.txt: browser=$ED_ROBOTS_B, bot=$ED_ROBOTS_R"
  echo "- Rate limit: $( [ -n "$RL_FIRST_FAIL" ] && echo "сработал на запросе №$RL_FIRST_FAIL" || echo "не нащупан за $RATE_N запросов" )"
  echo
  echo '## Все запросы'
  echo
  echo '```'
  column -t -s "$(printf '\t')" "$TSV" 2>/dev/null || cat "$TSV"
  echo '```'
  echo
  echo '## Коды rate-теста'
  echo
  echo '```'
  echo "$RL_CODES"
  echo '```'
  echo
  echo "Сырые ответы: \`raw/\` (тело, заголовки, при cp1251 — копия \`.utf8.html\`)."
} > "$REPORT"

say "Готово."
say "Отчёт:  $REPORT"
say "Сырьё:  $RAW"
