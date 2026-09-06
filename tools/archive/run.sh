#!/bin/bash
# Ежедневный проход архиватора. Запускать на Mac при поднятом VPN с выходом в РФ.
#
# Перед сбором проверяет канал: если e-disclosure не отвечает 200, значит VPN
# отвалился или сменил страну — проход отменяется ЦЕЛИКОМ. Половина архива
# хуже, чем его отсутствие: неполный день не отличить от дня без новостей.
set -u

BASE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$BASE/../.." && pwd)"
ROOT="${ROOT:-$REPO/data/raw}"
DELAY="${DELAY:-3}"
UA='RusTermArchiver/0.1 (personal research; +shemyakin925@gmail.com)'
GUARD_URL="${GUARD_URL:-https://www.e-disclosure.ru/}"
LOGDIR="$ROOT/logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/$(date +%Y-%m).log"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

log "=== проход начат ==="

# --- проверка канала -------------------------------------------------------
code=$(curl -sS -o /dev/null -m 20 -A "$UA" -w '%{http_code}' "$GUARD_URL" 2>>"$LOG") || true
[ -z "${code:-}" ] && code=000
ip=$(curl -sS -m 10 https://api.ipify.org 2>/dev/null || echo '?')
if [ "$code" != "200" ]; then
  log "ОТМЕНА: guard вернул $code (внешний адрес $ip)."
  log "Похоже, VPN не поднят или выход не российский. Проход не выполнялся."
  exit 2
fi
log "guard 200, внешний адрес $ip — канал годен"

# --- сбор ------------------------------------------------------------------
PY=$(command -v python3 || true)
if [ -z "$PY" ]; then log "ОШИБКА: python3 не найден"; exit 3; fi

set +e
"$PY" "$BASE/archiver.py" \
  --root "$ROOT" \
  --delay "$DELAY" \
  --targets "$REPO/targets/edisclosure.txt" \
  --targets "$REPO/targets/agencies.txt" \
  --targets "$REPO/targets/ir.txt" 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}
set -e

log "=== проход завершён, код $rc ==="
exit "$rc"
