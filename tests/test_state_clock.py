"""ТЗ-47 O0: часы в STATE.json читаются командой, а не набираются.

Круг 58: updated_at вёл себя как ручной набор — значения всегда на
круглой минуте, два коммита подряд несли одну и ту же метку, дрейф дошёл
до +232 минуты вперёд при верных git-штампах тех же коммитов. Стоп смены
— 10:00 по Данангу (PROTOCOL §10), поэтому ложные «+4 часа» заканчивают
ночь на треть раньше.

Страж краснеет, когда updated_at расходится с настоящим временем больше
чем на 15 минут, и называет обе величины и разницу. Сравнение — с
реальными часами (datetime.now(timezone.utc), машинная форма `date -u`),
никак не с committer-датой: в момент проверки commit ещё не существует.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "agent" / "STATE.json"
TOLERANCE_SECONDS = 15 * 60


def _updated_at() -> datetime:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    raw = state.get("updated_at")
    assert isinstance(raw, str) and raw.strip(), (
        "в agent/STATE.json нет updated_at — поле обязательно")
    try:
        stamp = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        assert False, f"agent/STATE.json updated_at={raw!r} — не ISO-8601"
    assert stamp.tzinfo is not None, (
        f"agent/STATE.json updated_at={raw!r} — без часового пояса")
    return stamp.astimezone(timezone.utc)


def test_state_updated_at_tracks_the_real_clock():
    stamp = _updated_at()
    now = datetime.now(timezone.utc)
    delta_minutes = (now - stamp).total_seconds() / 60
    assert abs(delta_minutes) <= TOLERANCE_SECONDS / 60, (
        f"agent/STATE.json updated_at="
        f"{stamp.strftime('%Y-%m-%dT%H:%M:%SZ')} расходится с реальным "
        f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')} на "
        f"{delta_minutes:+.1f} мин (допуск 15)")


def test_state_updated_at_exists_and_parses():
    """Отдельный assert на разбор: дрейф и отсутствие поля — разные
    поломки, у каждой свой красный вывод."""
    assert _updated_at().year >= 2026
