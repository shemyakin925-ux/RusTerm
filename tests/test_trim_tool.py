"""Тесты инструмента обрезки companyfacts (TASK-10 W1).

Ключевое правило: период схлопывается в as_reported-значение —
переживает самая ранняя дата filed, рестайт более позднего флинга
в фикстуру не попадает. Два прогона на одном входе байт-в-байт равны.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.trim_companyfacts import trim


def _two_filing_doc():
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {"us-gaap": {
            "Revenues": {
                "label": "пометка удаляется",
                "description": "и описание тоже",
                "units": {"USD": [
                    {"start": "2021-01-01", "end": "2021-12-31",
                     "val": 78740000000, "accn": "new-10-K",
                     "form": "10-K", "filed": "2025-02-16",
                     "fy": 2024, "fp": "FY",
                     "frame": "CY2021"},
                    {"start": "2021-01-01", "end": "2021-12-31",
                     "val": 93775000000, "accn": "orig-10-K",
                     "form": "10-K", "filed": "2022-02-17",
                     "fy": 2021, "fp": "FY"},
                    {"start": "2021-10-01", "end": "2021-12-31",
                     "val": 12345, "accn": "q4-10-K",
                     "form": "10-K", "filed": "2022-02-17",
                     "fy": 2021, "fp": "FY"},
                ]},
            },
            "PriceClose": {
                "units": {"USD": [{"end": "2021-12-31", "val": 1}]},
            },
        }},
    }


def test_earliest_filed_survives_restatement_dropped():
    doc = _two_filing_doc()
    out = trim(doc)
    revenues = out["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    # период схлопнут: годовой (2021-01-01..2021-12-31) — одна запись,
    # рестайт 78740000000 из более позднего флинга выброшен
    by_end = {e["end"]: e for e in revenues}
    entry = by_end["2021-12-31"] if "2021-12-31" in by_end else \
        by_end["2021-01-01→2021-12-31"]
    annual = [e for e in revenues
              if e["start"] == "2021-01-01" and e["end"] == "2021-12-31"]
    assert len(annual) == 1
    assert annual[0]["val"] == 93775000000, "рестайт вытеснил as_reported"
    assert annual[0]["accn"] == "orig-10-K"
    assert all(e["val"] != 78740000000 for e in revenues), \
        "рестайт остался в фикстуре"
    for field in ("val", "accn", "form", "filed", "fy", "fp",
                  "start", "end"):
        assert field in entry
    # label/description узла удалены; PriceClose вне карты — тег уходит
    assert "label" not in out["facts"]["us-gaap"]["Revenues"]
    assert "PriceClose" not in out["facts"]["us-gaap"]
    # верхний уровень
    assert out["cik"] == 320193
    assert out["entityName"] == "Apple Inc."
    assert set(out["facts"]) == {"us-gaap"}


def test_trim_is_deterministic_byte_for_byte():
    doc = _two_filing_doc()
    one = json.dumps(trim(json.loads(json.dumps(doc))),
                     separators=(",", ":"), sort_keys=True)
    two = json.dumps(trim(json.loads(json.dumps(doc))),
                     separators=(",", ":"), sort_keys=True)
    assert one == two


def test_quarter_and_annual_periods_kept_in_separate_bands():
    """Квартальный сравнительный период 10-K не вытесняет годовой:
    годовые и прочие периоды держат по шесть свежих в своих группах
    (TASK-10 W2: проверка JNJ требует годовые)."""
    from datetime import date
    doc = _two_filing_doc()
    # добавляем свежий квартальный период, который "вытеснил" бы годовой
    doc["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(
        {"start": "2025-10-01", "end": "2025-12-31", "val": 555,
         "accn": "q4-2025", "form": "10-K", "filed": "2026-02-15",
         "fy": 2025, "fp": "FY"})
    out = trim(doc)
    revenues = out["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    annual = [e for e in revenues
              if e["start"] == "2021-01-01" and e["end"] == "2021-12-31"]
    assert len(annual) == 1 and annual[0]["val"] == 93775000000
    q4 = [e for e in revenues if e["end"] == "2025-12-31"]
    assert q4 and q4[0]["val"] == 555


def test_b23_trim_recorded_payload_sha256_stable_across_runs():
    """BACKLOG B23: docstring инструмента обещает байт-в-байт
    повторяемость перегенерации — на записанном payload реального
    фида это никем не проверялось. Два прогона на одном входе обязаны
    дать одинаковый sha256."""
    import hashlib
    payload = (Path(__file__).resolve().parents[1] / "tests" / "data"
               / "edgar" / "companyfacts_m3_JNJ.json").read_text(
                   encoding="utf-8")

    def run() -> str:
        doc = json.loads(payload)
        out = json.dumps(trim(doc), separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(out.encode("utf-8")).hexdigest()

    sha_one = run()
    sha_two = run()
    assert sha_one == sha_two, (
        f"перегенерация нестабильна: {sha_one} != {sha_two}")
    assert len(sha_one) == 64
