"""python3 -m rusterm.desktop — запуск окна (TASK-C1).

Только чтение: каталог не создаётся (B35/B40), миграции не
применяются, сети нет кроме вопроса модели из строки разговора.
"""
from __future__ import annotations

import argparse


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m rusterm.desktop",
        description="EquityLab — десктопное окно (только чтение)")
    parser.add_argument("--root", default=None,
                        help="каталог данных (по умолчанию — те же "
                             "правила, что у CLI: $RUSTERM_DATA, "
                             "./rusterm.db, ~/.rusterm)")
    parser.add_argument("--watchlist", default=None,
                        help="список наблюдения (по умолчанию первый)")
    args = parser.parse_args(argv)

    # та же дверь, что у CLI: RUSTERM_* из ~/.rusterm.env, если их нет
    # в окружении — без неё окно на машине с ключом говорило бы
    # «модель недоступна»
    from rusterm import env as env_module
    env_module.load_env()

    from rusterm.store.paths import resolve_root
    root, rule = resolve_root(args.root)

    from rusterm.desktop import window
    return window.run(root, args.watchlist, rule)


if __name__ == "__main__":
    raise SystemExit(main())
