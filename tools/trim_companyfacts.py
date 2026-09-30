"""Обрезка ответа companyfacts SEC до компактного тестового payload'а
(TASK-10 W1).

Инструмент разработки: живёт вне rusterm/ намеренно — проверки приёмки
5, 7 и 8 смотрят только на пакет, поэтому здесь допустим urllib и не
нужен провайдер. Приложением не импортируется.

Правила (детерминированные):
- теги: ровно те, что в rusterm.normalize.concepts.CONCEPT_MAP, плюс
  теги, названные в json_pointer файла tests/data/golden_m2.json;
- записи: только form == "10-K"; период (start, end) схлопывается в
  одну запись с ранней датой filed — это as_reported-значение периода;
  рестайты обрабатывают determine_basis при ingest, не фикстура;
- периоды: шесть самых свежих по end на тег на единицу — отдельно
  среди годовых длительностей (>= 350 дней) и отдельно среди прочих
  (мгновенных); иначе квартальные сравнительные периоды 10-K
  вытесняют годовые, и проверка JNJ из W2 невыполнима;
- поля записи: val, accn, form, filed, fy, fp, start, end, frame;
- верхний уровень: cik, entityName, facts.us-gaap.

Использование: python3 tools/trim_companyfacts.py [файл] < payload
(файл или stdin). Контракт вывода (TASK-12 Y3): json.dumps c
sort_keys=True, разделители без пробелов — байт-в-байт повторяем при
перегенерации; обрезка детерминирована, повторный прогон на том же
входе даёт те же байты и тот же sha256 в manifest.

Второй режим — `--keep-duplicates` (TASK-92 C1): обрезка, СОХРАНЯЮЩАЯ
повторы одного периода. Отбор идёт по ПОДАЧАМ (accession), а не по
периодам, и внутри отобранного не схлопывается ничего:

- теги: те, что CONCEPT_MAP ставит концептам `base_concepts`;
- подачи: несколько самых свежих годовых (10-K) и несколько самых свежих
  квартальных (10-Q) + поправки 10-K/A отобранных годовых периодов +
  пара подач вокруг самого свежего годового числа, которое эмитент позже
  изменил (оригинал и подача, где число повторило сравнительной
  колонкой);
- все повторные записи периода остаются своими строками.

Почему подачами, а не периодами: basis строит `latest_end_by_accn` из
того же payload'а. Обрезка по периодам выбрасывает собственный год
поздней подачи — и её сравнительная колонка начинает выглядеть как
as_reported. Такая фикстура врёт о правиле, которое обязана проверять
(замер: периодов с обоими basis и разным числом — 0).

Использование режима: python3 tools/trim_companyfacts.py --keep-duplicates
файл (статистика — в stderr, payload — в stdout).
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rusterm.core.fact import determine_basis  # noqa: E402
from rusterm.normalize.concepts import (  # noqa: E402
    CONCEPT_MAP,
    CONCEPT_MAP_IFRS,
)

KEEP_ENTRY_FIELDS = ("val", "accn", "form", "filed", "fy", "fp",
                     "start", "end", "frame")
GOLDEN_PATH = REPO_ROOT / "tests" / "data" / "golden_m2.json"

# Формы годовой отчётности по таксономии (TASK-18 G6): us-gaap —
# домашние 10-K; ifrs-full — иностранные эмитенты MJDS: 20-F, 40-F и 6-K.
# ТЗ-97 Q4: 20-F добавлен — это годовой отчёт иностранного эмитента по
# МСФО (KSPI, VALE), без него обрезка выбрасывала весь годовой раздел.
_FORMS_BY_TAXONOMY = {"us-gaap": ("10-K",),
                      "ifrs-full": ("20-F", "40-F", "6-K")}

# Роли форм для обрезки по подачам (TASK-92 C1): годовой отчёт, его
# поправка и квартальная подача. Поправка — не «свежая» годовая подача:
# она несёт тот же собственный период и обязана оставаться повтором
# оригинала, а не занимать его место в отборе.
_ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
_AMENDMENT_FORMS = {"10-K/A", "20-F/A"}
_QUARTERLY_FORMS = {"10-Q", "6-K"}


def _financial_taxonomies(doc: dict) -> list:
    """Финансовые разделы payload'а в порядке приоритета: us-gaap,
    ifrs-full — ровно те, что разбирает парсер (ТЗ-97 Q4: оба, если оба
    в payload; раньше инструмент держал один раздел, как и прежний
    парсер). Пусто — значит ни одного из двух."""
    facts = doc.get("facts", {})
    return [name for name in ("us-gaap", "ifrs-full") if name in facts]


def _taxonomy_of(doc: dict) -> str | None:
    """Таксономия payload'а: us-gaap, если есть; иначе ifrs-full;
    иначе None (TASK-18 G6: обрезка держит ту таксономию, что несёт
    payload, — поменялся только верхний ключ)."""
    taxonomies = _financial_taxonomies(doc)
    return taxonomies[0] if taxonomies else None


def golden_pointer_tags(golden_path: Path) -> set[str]:
    """Теги, названные в json_pointer golden-файла (могут быть за
    пределами CONCEPT_MAP — их payload обязан сохранить)."""
    tags: set[str] = set()
    if not golden_path.exists():
        return tags
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    for row in golden:
        parts = row.get("json_pointer", "").split("/")
        if len(parts) > 3 and parts[1] == "facts" and parts[2] == "us-gaap":
            tags.add(parts[3])
    return tags


def _trim_section(section: dict, tags: set[str], taxonomy: str) -> dict:
    out_concepts: dict = {}
    for name in sorted(section):
        if name not in tags:
            continue
        node = section[name]
        units_out: dict = {}
        forms = _FORMS_BY_TAXONOMY.get(taxonomy, ("10-K",))
        for unit, entries in node.get("units", {}).items():
            ten_k = [e for e in entries if e.get("form") in forms]
            by_period: dict = {}
            durations: dict = {}
            for e in ten_k:
                key = (e.get("start") or "", e.get("end") or "")
                target = by_period
                if e.get("start"):
                    d0 = date.fromisoformat(e["start"])
                    d1 = date.fromisoformat(e["end"])
                    if (d1 - d0).days >= 350:
                        target = durations
                prev = target.get(key)
                if prev is None or e.get("filed", "") < prev.get("filed", ""):
                    target[key] = e
            kept_annual = sorted(durations.values(),
                                 key=lambda e: (e.get("end", ""),
                                                e.get("filed", "")))[-6:]
            kept_other = sorted(by_period.values(),
                                key=lambda e: (e.get("end", ""),
                                               e.get("filed", "")))[-6:]
            kept = kept_annual + kept_other
            if kept:
                kept.sort(key=lambda e: (e.get("end", ""),
                                         e.get("filed", "")))
                units_out[unit] = [
                    {k: e[k] for k in KEEP_ENTRY_FIELDS if k in e}
                    for e in kept]
        if units_out:
            out_concepts[name] = {"units": units_out}
    return out_concepts


def _annual_or_instant(entry: dict) -> bool:
    """Годовая длительность (>= 350 дней) или мгновенное значение — то,
    чем подача отчитывается за СВОЙ период."""
    start, end = entry.get("start"), entry.get("end")
    if not start or not end:
        return True
    return (date.fromisoformat(end) - date.fromisoformat(start)).days >= 350


def _section_entries(section: dict):
    for name, node in section.items():
        for unit, arr in (node.get("units") or {}).items():
            if not isinstance(arr, list):
                continue
            for entry in arr:
                if isinstance(entry, dict):
                    yield name, unit, entry


def _by_accession(entries) -> tuple:
    """(latest_end, by_accn): конец периода подачи по всем её записям и
    сводка форм/своего года/даты filed на accession."""
    latest_end: dict = {}
    by_accn: dict = {}
    for _name, _unit, entry in entries:
        accn, end = entry.get("accn"), entry.get("end")
        if not accn or not end:
            continue
        if end > latest_end.get(accn, ""):
            latest_end[accn] = end
        row = by_accn.setdefault(accn, {"forms": set(), "own_end": "",
                                        "filed": ""})
        row["forms"].add(entry.get("form"))
        if _annual_or_instant(entry) and end > row["own_end"]:
            row["own_end"] = end
        row["filed"] = max(row["filed"], entry.get("filed") or "")
    return latest_end, by_accn


def _chosen_accessions(entries, latest_end, by_accn, annual: int,
                       quarterly: int) -> tuple:
    """Отбор ПОДАЧАМИ (TASK-92 C1): свежие годовые, свежие квартальные,
    поправки отобранных годовых периодов и пара подач вокруг самого
    свежего изменённого годового числа."""
    annuals = sorted((a for a, r in by_accn.items()
                      if r["forms"] & _ANNUAL_FORMS and r["own_end"]),
                     key=lambda a: (by_accn[a]["own_end"], a))
    quarterlies = sorted((a for a, r in by_accn.items()
                          if r["forms"] & _QUARTERLY_FORMS),
                         key=lambda a: (by_accn[a]["filed"], a))
    chosen = set(annuals[-annual:]) | set(quarterlies[-quarterly:])
    own_ends = {by_accn[a]["own_end"] for a in chosen}
    chosen |= {a for a, r in by_accn.items()
               if r["forms"] & _AMENDMENT_FORMS and r["own_end"] in own_ends}

    groups: dict = {}
    for name, unit, entry in entries:
        if not _annual_or_instant(entry):
            continue
        end = entry.get("end")
        accn = entry.get("accn")
        basis = determine_basis(latest_end.get(accn, end), end,
                                entry.get("filed"))
        groups.setdefault(
            (name, unit, entry.get("start") or end, end, basis),
            []).append(entry)
    revised = []
    for (name, unit, start, end, basis), group in groups.items():
        if basis != "as_reported":
            continue
        later = groups.get((name, unit, start, end, "restated"))
        if not later:
            continue
        original = min(group, key=lambda e: (e.get("filed", ""),
                                             e.get("accn", "")))
        newest = max(later, key=lambda e: (e.get("filed", ""),
                                           e.get("accn", "")))
        if str(original.get("val")) != str(newest.get("val")):
            revised.append((end, original.get("accn"), newest.get("accn")))
    if revised:
        _end, orig_accn, new_accn = max(revised)
        chosen |= {orig_accn, new_accn}
        own_of_orig = by_accn.get(orig_accn, {}).get("own_end")
        chosen |= {a for a, r in by_accn.items()
                   if r["forms"] & _AMENDMENT_FORMS
                   and r["own_end"] == own_of_orig}
    return chosen


def trim_keep_duplicates(doc: dict, annual: int = 4,
                         quarterly: int = 3) -> dict:
    """Обрезка, сохраняющая повторы периода (TASK-92 C1).

    Возвращает payload в той же форме, что и `trim`, но внутри отобранных
    подач не схлопывается ни одна запись: сравнительные колонки поздних
    флингов остаются своими строками, иначе фикстура не проверяет то
    правило, ради которого заведена.
    """
    from rusterm.core.snapshot import base_concepts

    out_facts: dict = {}
    for taxonomy in _financial_taxonomies(doc):
        section = doc["facts"][taxonomy]
        tag_map = (CONCEPT_MAP_IFRS if taxonomy == "ifrs-full"
                   else CONCEPT_MAP)
        tags = {tag for canonical in base_concepts
                for tag in tag_map.get(canonical, ())}
        entries = [(n, u, e) for n, u, e in _section_entries(section)
                   if n in tags]
        latest_end, by_accn = _by_accession(entries)
        chosen = _chosen_accessions(entries, latest_end, by_accn, annual,
                                    quarterly)
        out_concepts: dict = {}
        for name, unit, entry in entries:
            if entry.get("accn") not in chosen:
                continue
            units_out = out_concepts.setdefault(
                name, {"units": {}})["units"]
            units_out.setdefault(unit, []).append(
                {k: entry[k] for k in KEEP_ENTRY_FIELDS if k in entry})
        for node in out_concepts.values():
            for arr in node["units"].values():
                arr.sort(key=lambda e: (e.get("end", ""),
                                        e.get("filed", ""),
                                        e.get("accn", "")))
        if out_concepts:
            out_facts[taxonomy] = dict(sorted(out_concepts.items()))
    return {
        "cik": doc.get("cik"),
        "entityName": doc.get("entityName"),
        "facts": out_facts,
    }


def duplicate_report(doc: dict) -> str:
    """Сводка обрезки `--keep-duplicates`: что в payload'е на самом деле
    есть повторного (stderr, в stdout не мешает контракту байтов)."""
    lines = []
    for taxonomy in _financial_taxonomies(doc):
        section = doc["facts"][taxonomy]
        entries = list(_section_entries(section))
        latest_end, _by_accn = _by_accession(entries)
        keys4: dict = {}
        keys5: dict = {}
        for name, unit, entry in entries:
            end = entry.get("end")
            start = entry.get("start") or end
            basis = determine_basis(latest_end.get(entry.get("accn"), end),
                                    end, entry.get("filed"))
            keys4.setdefault((name, unit, start, end), 0)
            keys4[(name, unit, start, end)] += 1
            keys5.setdefault((name, unit, start, end, basis), [])
            keys5[(name, unit, start, end, basis)].append(entry)
        both_diff = 0
        for (name, unit, start, end), total in keys4.items():
            a = keys5.get((name, unit, start, end, "as_reported"))
            b = keys5.get((name, unit, start, end, "restated"))
            if a and b and str(a[0].get("val")) != str(b[0].get("val")):
                both_diff += 1
        lines.append(
            f"{taxonomy}: записей {len(entries)}, подач "
            f"{len({e.get('accn') for _n, _u, e in entries})}, "
            f"4-ключей {len(keys4)}, 5-ключей {len(keys5)}, "
            f"групп с повтором в одном basis "
            f"{sum(1 for v in keys5.values() if len(v) > 1)}, "
            f"периодов с двумя basis и разным числом {both_diff}")
    return "\n".join(lines)


def trim(doc: dict, golden_path: Path = GOLDEN_PATH) -> dict:
    taxonomies = _financial_taxonomies(doc)
    if not taxonomies:
        return {
            "cik": doc.get("cik"),
            "entityName": doc.get("entityName"),
            "facts": {},
        }
    facts = doc.get("facts", {})
    golden_tags = golden_pointer_tags(golden_path)
    out_facts: dict = {}
    for taxonomy in taxonomies:
        tag_map = (CONCEPT_MAP_IFRS if taxonomy == "ifrs-full"
                   else CONCEPT_MAP)
        tags = {tag for values in tag_map.values() for tag in values}
        if taxonomy != "ifrs-full":
            # golden-указатели относятся к us-gaap словарю (TASK-10 W1)
            tags |= golden_tags
        trimmed = _trim_section(facts.get(taxonomy, {}), tags, taxonomy)
        if trimmed:
            out_facts[taxonomy] = trimmed

    return {
        "cik": doc.get("cik"),
        "entityName": doc.get("entityName"),
        "facts": out_facts,
    }


def main(argv: list[str]) -> int:
    keep_duplicates = "--keep-duplicates" in argv
    args = [a for a in argv if not a.startswith("--")]
    if args:
        doc = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    else:
        doc = json.loads(sys.stdin.read())
    if keep_duplicates:
        trimmed = trim_keep_duplicates(doc)
        # Сводка — в stderr: stdout остаётся контрактом байтов (TASK-12 Y3).
        print(duplicate_report(trimmed), file=sys.stderr)
    else:
        trimmed = trim(doc)
    print(json.dumps(trimmed, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
