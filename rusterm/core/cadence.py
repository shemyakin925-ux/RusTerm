"""Обход по полноте, а не по календарю (ТЗ-23 K5, ADR-0014 §2).

Решение пользователя: неполное добивается сразу и через ночи, полное
опрашивается раз в 7–14 дней. Полнота — вычисляемое свойство, не флаг:
она каждый проход выводится из stored-дат (сомкнутость до последнего
торгового дня и отсутствие внутренних дыр). Флаг, который можно забыть
снять, — тот же дефект, что отчёт без прогона.

Бюджет: backfill забирает его первым, poll получает остаток; при
исчерпании проход останавливается чисто и фиксирует, где остановился.
Возобновляемость — из перестраиваемости плана и идемпотентности сбора
(I7): ночь, оборвавшаяся посреди backfill, ничего не теряет, план
следующей ночи строится из данных заново.

Торговый календарь вендора офлайн неизвестен; правило честно
приближено и названо: дыра — разрыв между соседними датами больше
десяти календарных дней (выходные и одиночные праздники не дыра),
сомкнутость — последний день не старше семи дней от as_of.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Пороги каденции (ADR-0014 §2: «раз в неделю-две»).
# Согласование: интервал опроса 10 дней ≤ запас сомкнутости 14 дней —
# полный инструмент между опросами не успевает «протухнуть» и не
# переворачивается в backfill; пропущенный проход (15+ дней) — уже
# честный backfill.
POLL_INTERVAL_DAYS = 10
CLOSED_GRACE_DAYS = 14
GAP_LIMIT_DAYS = 10

BACKFILL_PRIORITY = 1   # забирает бюджет первым
POLL_PRIORITY = 2


@dataclass(frozen=True)
class PlanEntry:
    instrument_id: str
    state: str          # complete | incomplete
    action: str         # backfill | poll | skip
    reason: str
    last_date: str | None
    priority: int


def instrument_state(price_dates: list[str],
                     as_of: str) -> tuple[str, str, str | None]:
    """Состояние истории цен: (state, reason, last_date).

    state: incomplete — истории нет, есть внутренняя дыра или история
    не сомкнута к as_of; complete — иначе.
    """
    if not price_dates:
        return "incomplete", "no_history", None
    ordered = sorted(set(price_dates))
    last = ordered[-1]
    for prev, nxt in zip(ordered, ordered[1:]):
        gap = (date.fromisoformat(nxt) - date.fromisoformat(prev)).days
        if gap > GAP_LIMIT_DAYS:
            return "incomplete", f"gap:{prev}..{nxt}", last
    age = (date.fromisoformat(as_of) - date.fromisoformat(last)).days
    if age > CLOSED_GRACE_DAYS:
        return "incomplete", f"stale_history:{last}", last
    return "complete", "closed", last


def plan_pass(repos, as_of: str,
              poll_interval_days: int = POLL_INTERVAL_DAYS,
              block: str = "prices") -> list[PlanEntry]:
    """План обхода на дату: backfill первым, полные — по расписанию.

    Пересчитывается из данных при каждом вызове; состояние последнего
    обхода читается из очереди заданий (MAX(target_date) закрытых).
    """
    plan: list[PlanEntry] = []
    for instrument_id in repos.price.instruments_with_history():
        dates = repos.price.dates(instrument_id)
        state, reason, last_date = instrument_state(dates, as_of)
        if state == "incomplete":
            plan.append(PlanEntry(
                instrument_id=instrument_id, state=state,
                action="backfill", reason=reason, last_date=last_date,
                priority=BACKFILL_PRIORITY))
            continue
        last_poll = repos.job.last_poll_date(instrument_id, block)
        # точка отсчёта срока — ПОСЛЕДНЯЯ из отметки обхода и даты
        # последних данных: свежий сбор сам сдвигает следующий опрос
        reference = max(x for x in (last_poll, last_date) if x)
        due = (date.fromisoformat(as_of)
               - date.fromisoformat(reference)).days >= poll_interval_days
        plan.append(PlanEntry(
            instrument_id=instrument_id, state=state,
            action="poll" if due else "skip",
            reason="due" if due else
            f"polled:{reference}", last_date=last_date,
            priority=POLL_PRIORITY))
    # backfill первым (приоритет), внутри — по имени, детерминированно
    return sorted(plan, key=lambda e: (e.priority, e.instrument_id))


def run_pass(repos, as_of: str, collector,
             poll_interval_days: int = POLL_INTERVAL_DAYS,
             budget: int | None = None,
             now_ts: float | None = None) -> dict:
    """Один проход: план -> исполнение в рамках бюджета.

    collector(entry) выполняет сбор/опрос; считается один запрос на
    запись плана (вендорский пагинг считается внутри сборщика ночи K2).
    Бюджет: backfill забирает первым; при исчерпании проход
    останавливается и возвращает, на ком остановился. Каждый исполненный
    пункт закрывается заданием очереди (status done, target_date=as_of)
    — возобновляемость и отметка каденции.
    """
    import time as _time
    plan = plan_pass(repos, as_of, poll_interval_days)
    executed: list[str] = []
    stopped_at: str | None = None
    spent = 0
    for entry in plan:
        if entry.action == "skip":
            continue
        if budget is not None and spent >= budget:
            stopped_at = entry.instrument_id
            break
        collector(entry)
        spent += 1
        executed.append(entry.instrument_id)
        job_id = f"cadence:{entry.instrument_id}:{as_of}"
        repos.job.enqueue(
            job_id, entry.instrument_id, "prices", "cadence", as_of,
            None, entry.priority,
            idempotency_key=job_id, not_before=None)
        repos.job.claim(job_id)
        repos.job.finish(job_id)
    skipped = sum(1 for e in plan if e.action == "skip")
    return {"spent": spent, "executed": executed,
            "stopped_at": stopped_at, "skipped": skipped,
            "planned": len(plan)}
