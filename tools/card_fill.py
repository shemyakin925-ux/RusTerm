"""Заполненность карточки по контрольной десятке (PRODUCT.md С2).

    python3 tools/card_fill.py --root <каталог данных> [US-JPM US-DELL …]

Только чтение. Печатает по бумаге «заполнено/применимо = %» за пять
закрытых лет и итог; код выхода 0, если итог ≥ 90 %, иначе 1. Пустые
клетки перечислены по мерам — что чинить первым.
"""
from __future__ import annotations

import argparse
import sys

from rusterm.desktop import card, data
from rusterm.store.repos import RepoRegistry

# PRODUCT.md «Контрольная десятка»: «на выбор пользователя» — ORCL,
# пока пользователь не назвал другую
CONTROL_TEN = ("US-JPM", "US-BAC", "US-DELL", "US-HPQ", "US-AAPL",
               "US-MSFT", "US-T", "US-AA", "US-FCX", "US-ORCL")
TARGET = 0.90


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("instruments", nargs="*")
    args = parser.parse_args(argv)
    paths, conn = data.open_readonly(args.root)
    if conn is None:
        print(f"базы нет: {args.root}")
        return 1
    repos = RepoRegistry(conn, paths)
    total_filled = total_applicable = 0
    gaps: dict[str, list[str]] = {}
    for instrument_id in args.instruments or CONTROL_TEN:
        info = data.measure_table_rows(repos, instrument_id,
                                       card.CARD_YEARS)
        view = card.card_view(repos, info, show_empty=True)
        filled, applicable, missing = card.fill_rate(view)
        total_filled += filled
        total_applicable += applicable
        share = filled / applicable if applicable else 0.0
        print(f"{instrument_id:10} {filled}/{applicable} = {share:.0%}")
        for concept, year in missing:
            gaps.setdefault(concept, []).append(f"{instrument_id[3:]}:{year}")
    share = total_filled / total_applicable if total_applicable else 0.0
    print(f"ИТОГ {total_filled}/{total_applicable} = {share:.0%} "
          f"(цель {TARGET:.0%})")
    for concept, where in sorted(gaps.items(), key=lambda kv: -len(kv[1])):
        print(f"  {concept:20} {len(where):3}  {' '.join(where[:10])}")
    conn.close()
    return 0 if share >= TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
