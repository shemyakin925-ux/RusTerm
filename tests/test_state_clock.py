"""ТЗ-47 O0: часы в STATE.json читаются командой, а не набираются.

Круг 58: updated_at вёл себя как ручной набор — значения всегда на
круглой минуте, два коммита подряд несли одну и ту же метку, дрейф дошёл
до +232 минуты вперёд при верных git-штампах тех же коммитов.

Зачем это стражу сейчас (ТЗ-88 C3): ночная смена отменена, и
обоснование «ложные +4 часа заканчивают ночь раньше» потеряло силу —
опаздывать больше не к событию. Осталось то, что правда: координатор
судит по updated_at, жив исполнитель или завис. Набранная вручную или
устаревшая метка читается как «завис», и приёмку назначают не туда.

Разрез стража: ЗДЕСЬ — синтетические проверка разбора и сообщения о
дрейфе (чистые функции, без настоящих часов: живой прогон в свежем
дереве координатора не может краснеть от того, что коммит проверяют
часами позже — этот промах размещения поймал живой прогон
test_i5_staged_and_authorised_widening_is_green в смене ТЗ-48).
Настоящие часы сравниваются в agent/selfcheck.sh в момент коммита,
когда updated_at ещё можно обновить командой.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "agent" / "STATE.json"
TOLERANCE_SECONDS = 15 * 60


def _drift_seconds(raw: str, now: datetime) -> float:
    stamp = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    assert stamp.tzinfo is not None, (
        f"agent/STATE.json updated_at={raw!r} — без часового пояса")
    return (now - stamp.astimezone(timezone.utc)).total_seconds()


def test_state_updated_at_exists_and_parses():
    """Поле обязано существовать и разбираться как ISO-8601 с поясом —
    без сравнения с настоящими часами (см. шапку)."""
    state = json.loads(STATE.read_text(encoding="utf-8"))
    raw = state.get("updated_at")
    assert isinstance(raw, str) and raw.strip(), (
        "в agent/STATE.json нет updated_at — поле обязательно")
    assert _drift_seconds(raw, datetime.now(timezone.utc)) is not None


def test_drift_message_names_both_values_and_difference():
    """Подставленные +3 часа: сообщение стража называет обе величины и
    разницу. Часы синтетические — красный случай воспроизводим всегда."""
    now = datetime(2026, 9, 17, 15, 46, 15, tzinfo=timezone.utc)
    stamp = "2026-09-17T18:46:13Z"
    with pytest.raises(AssertionError) as exc:
        drift = _drift_seconds(stamp, now)
        assert abs(drift) <= TOLERANCE_SECONDS, (
            f"agent/STATE.json updated_at={stamp} расходится с реальным "
            f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')} на "
            f"{drift / 60:+.1f} мин (допуск 15)")
    message = str(exc.value)
    assert "2026-09-17T18:46:13Z" in message
    assert "2026-09-17T15:46:15Z" in message
    assert "-180.0 мин" in message, message


def test_fresh_stamp_within_tolerance_passes():
    now = datetime(2026, 9, 17, 15, 46, 15, tzinfo=timezone.utc)
    stamp = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert abs(_drift_seconds(stamp, now)) <= TOLERANCE_SECONDS
