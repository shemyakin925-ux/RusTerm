"""Точка входа собранного .app (TASK-C10): PyInstaller стартует отсюда.

python3 -m rusterm.desktop внутри сборки не работает — нужен обычный
импортируемый модуль; сюда же свалены скрытые импорты реестра
провайдеров (они резолвятся по именам в рантайме).
"""
from rusterm.desktop.window import run

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        prog="EquityLab", description="EquityLab десктоп")
    parser.add_argument("--root", default=None)
    parser.add_argument("--watchlist", default=None)
    args = parser.parse_args()
    from rusterm import env as env_module
    env_module.load_env()
    from rusterm.store.paths import resolve_root
    root, rule = resolve_root(args.root)
    raise SystemExit(run(root, args.watchlist, rule))
