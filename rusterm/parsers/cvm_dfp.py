"""Разбор строк CVM DFP (Бразилия) в факты словаря (ТЗ-56 Z2).

Вход — строки ОДНОГО эмитента из ведомых CSV набора DFP
(CvmProvider.rows_for): DRE (отчёт о прибыли, duration) и BPP (баланс,
instant). Каждая строка становится фактом as_reported:

  concept   'cvm-dfp:3.01' — канонизирует карта cvm-dfp.v1
            (rusterm/normalize/concepts.py, намеренные отсутствия
            названы там);
  value     VL_CONTA × ESCALA_MOEDA (MIL — тысячи, MILHOES —
            миллионы): факт хранится в единицах MOEDA, исходное
            значение и множитель видны в локаторе;
  unit      MOEDA (например 'BRL'), currency = MOEDA;
  период    DRE — DT_INI_EXERC..DT_FIM_EXERC; BPP — instant на
            DT_FIM_EXERC;
  версии    несколько VERSAO одной строки — берётся старшая
            (перезапись отчётности регулятором).

Локатор kind=cvm-dfp разрешается из записанного ZIP повторным чтением
строки — факт воспроизводим без сети.
"""
from __future__ import annotations

_ESCALA = {"UNID": 1.0, "MIL": 1_000.0, "MILHOES": 1_000_000.0}

PARSER_VERSION = "cvm-dfp.v1"


class CvmDfpParser:
    """Строки DFP -> словари факта. Сети нет, состояний нет."""

    source_name = "cvm"
    parser_version = PARSER_VERSION

    def parse_rows(self, rows: list[dict], statement: str,
                   context: dict) -> tuple[list[dict], int]:
        """(факты, неразобрано). statement: 'DRE' | 'BPP'."""
        if statement not in ("DRE", "BPP"):
            raise ValueError(f"unknown statement: {statement}")
        # дедупликация по (CD_CONTA, ORDEM_EXERC, период): побеждает
        # старшая VERSAO — регулятор перепубликовывает набор целиком
        best: dict[tuple, dict] = {}
        unparsed = 0
        for r in rows:
            raw_value = (r.get("VL_CONTA") or "").strip()
            conta = (r.get("CD_CONTA") or "").strip()
            end = (r.get("DT_FIM_EXERC") or "").strip()
            start = ((r.get("DT_INI_EXERC") or "").strip()
                     if statement == "DRE" else end)
            if not raw_value or not conta or not end:
                unparsed += 1
                continue
            try:
                value = float(raw_value)
                versao = int((r.get("VERSAO") or "0").strip())
            except ValueError:
                unparsed += 1
                continue
            key = (conta, (r.get("ORDEM_EXERC") or "").strip(),
                   start, end)
            prev = best.get(key)
            if prev is None or versao > prev["versao"]:
                best[key] = {"versao": versao, "row": r,
                             "value": value, "raw": raw_value,
                             "start": start, "end": end, "conta": conta}

        facts: list[dict] = []
        for item in best.values():
            r = item["row"]
            escala = (r.get("ESCALA_MOEDA") or "UNID").strip().upper()
            scale = _ESCALA.get(escala)
            if scale is None:
                unparsed += 1
                continue
            moeda = (r.get("MOEDA") or "").strip()
            concept = f"cvm-dfp:{item['conta']}"
            facts.append({
                "issuer_id": context.get("issuer_id"),
                "listing_id": context.get("listing_id"),
                "concept": concept,
                "value": repr(item["value"] * scale),
                "unit": moeda,
                "currency": moeda,
                "period_start": item["start"],
                "period_end": item["end"],
                "period_type": "duration" if statement == "DRE"
                else "instant",
                "basis": "as_reported",
                "origin": "extracted",
                "source_ref": context.get("source_ref", ""),
                "locator": {
                    "kind": "cvm-dfp",
                    "doc_sha256": context.get("source_ref", ""),
                    "csv_member": context.get("csv_member", ""),
                    "cd_conta": item["conta"],
                    "ordem_exerc": (r.get("ORDEM_EXERC") or "").strip(),
                    "period_start": item["start"],
                    "period_end": item["end"],
                    "escala_moeda": escala,
                    "raw_value": item["raw"],
                },
                "parser_version": self.parser_version,
                "status": "ok",
            })
        return facts, unparsed
