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
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rusterm.normalize.concepts import CONCEPT_MAP  # noqa: E402

KEEP_ENTRY_FIELDS = ("val", "accn", "form", "filed", "fy", "fp",
                     "start", "end", "frame")
GOLDEN_PATH = REPO_ROOT / "tests" / "data" / "golden_m2.json"


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


def trim(doc: dict, golden_path: Path = GOLDEN_PATH) -> dict:
    tags = {tag for tags in CONCEPT_MAP.values() for tag in tags}
    tags |= golden_pointer_tags(golden_path)

    usgaap = doc.get("facts", {}).get("us-gaap", {})
    out_concepts: dict = {}
    for name in sorted(usgaap):
        if name not in tags:
            continue
        node = usgaap[name]
        units_out: dict = {}
        for unit, entries in node.get("units", {}).items():
            ten_k = [e for e in entries if e.get("form") == "10-K"]
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

    return {
        "cik": doc.get("cik"),
        "entityName": doc.get("entityName"),
        "facts": {"us-gaap": out_concepts},
    }


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        doc = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    else:
        doc = json.loads(sys.stdin.read())
    print(json.dumps(trim(doc), separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
