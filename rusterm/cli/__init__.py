"""CLI: init, ingest, snapshot, export, verify, doctor.

Точка входа rusterm.cli:main (pyproject.toml). Ни строки Qt; SQL только
в rusterm/store — команды оркестрируют store и core, сами в базу не ходят.
Все операции офлайн, на синтетических данных.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

from rusterm.core.export import snapshot_to_csv, snapshot_to_json
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.core.verification import VerificationService
from rusterm.pipeline import IngestionPipeline
from rusterm.providers import SyntheticDisclosuresProvider
from rusterm.store.db import apply_migrations, current_schema_version, open_connection
from rusterm.store.doctor import doctor_report
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RepoRegistry,
    SnapshotRepo,
)
from rusterm.store.raw_store import decompress_object

# Синтетическая цель сбора для CLI-прогонов (помечена synthetic).
DEMO_ISSUER = "issuer-cli-demo"
DEMO_INSTRUMENT = "US-CLI-DEMO"


def _open(root: str):
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    return paths, open_connection(paths)


def cmd_init(args) -> int:
    paths, conn = _open(args.root)
    applied = apply_migrations(conn)
    print(f"каталог: {args.root}")
    print(f"применено миграций: {len(applied)}; "
          f"schema_version={current_schema_version(conn)}")
    conn.close()
    return 0


def _ensure_demo_instrument(conn) -> None:
    instruments = InstrumentRepo(conn)
    instruments.upsert_issuer(Issuer(DEMO_ISSUER, "CLI Demo Corp (synthetic)",
                                     "US", None, None, "us_gaap", "USD"))
    instruments.upsert_instrument(Instrument(DEMO_INSTRUMENT, DEMO_ISSUER,
                                             None, "common", "active", None))




def _select_instruments(args, repos):
    """Селектор --instrument | --ticker+--market | --watchlist (U3).
    Возвращает список (instrument_id, issuer_id); при ошибке печатает
    причину в stderr и возвращает None. Молчаливый выбор первого
    кандидата запрещён."""
    chosen = [s for s in (getattr(args, "instrument", None),
                          getattr(args, "ticker", None),
                          getattr(args, "watchlist", None)) if s]
    if len(chosen) != 1:
        print("укажите ровно один способ выбора: --instrument ID, "
              "--ticker T --market M или --watchlist ID", file=sys.stderr)
        return None
    if args.instrument:
        instrument = repos.instrument.get_instrument(args.instrument)
        if instrument is None:
            print(f"инструмент {args.instrument!r} не найден; добавьте его "
                  "через rusterm watchlist add или создайте демо: rusterm demo",
                  file=sys.stderr)
            return None
        return [(instrument.instrument_id, instrument.issuer_id)]
    if args.ticker:
        market = getattr(args, "market", None)
        if not market:
            print("--ticker требует --market", file=sys.stderr)
            return None
        candidates = repos.instrument.resolve_ticker_candidates(
            args.ticker, market, getattr(args, "as_of", None)
            or args_as_of_default())
        if not candidates:
            print(f"тикер {args.ticker!r} на {market!r} не разрешён ни в один "
                  "инструмент; проверьте тикер или добавьте инструмент",
                  file=sys.stderr)
            return None
        if len(candidates) > 1:
            print(f"тикер {args.ticker!r} неоднозначен, кандидаты: "
                  f"{', '.join(candidates)}; уточните дату или рынок",
                  file=sys.stderr)
            return None
        instrument = repos.instrument.get_instrument(candidates[0])
        return [(instrument.instrument_id, instrument.issuer_id)]
    # --watchlist: текущие участники списка
    members = repos.watchlist.members(args.watchlist)
    if not members:
        print(f"список {args.watchlist!r} пуст или не найден",
              file=sys.stderr)
        return None
    out = []
    for member in members:
        instrument = repos.instrument.get_instrument(member["instrument_id"])
        if instrument is not None:
            out.append((instrument.instrument_id, instrument.issuer_id))
    return out


def args_as_of_default():
    import datetime
    return datetime.date.today().isoformat()


def cmd_demo(args) -> int:
    """Демо-данные (TASK-8 U3): синтетический эмитент и инструмент
    создаются только здесь, явно, с честной пометкой."""
    paths, conn = _open(args.root)
    apply_migrations(conn)
    _ensure_demo_instrument(conn)
    print(f"создан демо-инструмент {DEMO_INSTRUMENT} (эмитент {DEMO_ISSUER}); "
          "данные синтетические, выдуманные — не данные эмитента")
    print("далее: rusterm ingest --instrument " + DEMO_INSTRUMENT
          + " && rusterm snapshot --instrument " + DEMO_INSTRUMENT)
    conn.close()
    return 0


def cmd_ingest(args) -> int:
    paths, conn = _open(args.root)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    targets = _select_instruments(args, repos)
    if targets is None:
        conn.close()
        return 1
    if args.source == "edgar":
        # Реальный сбор никогда не является дефолтом (TASK-7 T14).
        try:
            from rusterm.providers.edgar import EdgarProvider
        except ImportError:
            print("edgar-провайдер недоступен: T4 не выполнялся "
                  "(RUSTERM_SEC_UA не задан)", file=sys.stderr)
            conn.close()
            return 1
        from rusterm.providers.budget import RequestGate
        provider = EdgarProvider(RequestGate())
        providers = {"edgar": provider}
    else:
        from rusterm.providers.disclosures import DEMO_INDEX_FIXTURE
        providers = {"synthetic": SyntheticDisclosuresProvider(
            fixture_path=DEMO_INDEX_FIXTURE)}
    pipe = IngestionPipeline(repos, providers)
    for instrument_id, issuer_id in targets:
        result = pipe.run(instrument_id, issuer_id, args.source)
        print(f"{instrument_id}: заданий закрыто: {result.jobs_done}; "
              f"фактов: {result.facts_stored}; "
              f"дублей sha256: {result.duplicates}; неразобрано (E4): "
              f"{result.needs_verification}; suspect (E5): {result.suspects}")
    conn.close()
    return 0


def cmd_snapshot(args) -> int:
    paths, conn = _open(args.root)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    targets = _select_instruments(args, repos)
    if targets is None:
        conn.close()
        return 1
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    as_of = args.as_of or args_as_of_default()
    for instrument_id, issuer_id in targets:
        result = builder.build(instrument_id, issuer_id, as_of)
        print(f"{instrument_id}: снапшот v{result.version}: "
              f"{result.snapshot_id}")
        # «написано» и «имеет значение» — разные счётчики (TASK-8 U3)
        measures = repos.snapshot.get_measures(result.snapshot_id)
        with_value = sum(1 for m in measures if m[4] is not None)
        null_measures = len(measures) - with_value
        print(f"{instrument_id}: мер: {result.measures} — со значением "
              f"{with_value}, пусто {null_measures}; "
              f"перцентилей: {result.percentiles}")
        if result.diff.metric_changes:
            print("изменение метрик: " + "; ".join(
                f"{c}: {o} -> {n}" for c, o, n in result.diff.metric_changes))
        if result.diff.revisions:
            print("ревизии: " + "; ".join(f"{c} за {p}"
                                          for c, p in result.diff.revisions))
    conn.close()
    return 0


def cmd_export(args) -> int:
    paths, conn = _open(args.root)
    repo = SnapshotRepo(conn)
    snapshot_id = repo.latest_snapshot_id(args.instrument)
    if snapshot_id is None:
        print(f"для {args.instrument!r} снапшотов нет — сначала "
              "rusterm snapshot --instrument "
              f"{args.instrument}", file=sys.stderr)
        conn.close()
        return 1
    snapshot = repo.get_snapshot(snapshot_id)
    measures = repo.get_measures(snapshot_id)
    text = (snapshot_to_csv(measures) if args.format == "csv"
            else snapshot_to_json(snapshot, measures))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"экспорт {args.instrument} снапшота "
              f"v{snapshot['version']} -> {args.out}")
    else:
        print(text)
    conn.close()
    return 0


def cmd_verify(args) -> int:
    """Процесс 5: ground truth по неверному факту + пересчёт зависимых
    мер (TASK-8 U2). Извлечённый факт не удаляется — получает
    superseded_by."""
    paths, conn = _open(args.root)
    repos = RepoRegistry(conn, paths)
    service = VerificationService(
        repos.fact, repos.verification, repos.snapshot, repos.instrument,
        paths.root / "golden_proposals.jsonl")
    try:
        correct = service.store_ground_truth(
            args.fact, args.expected,
            note=f"document:{_scrub_url(args.document)}")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        conn.close()
        return 1
    # исправленное число обязано доехать до производных мер (U2):
    # пересборка снапшотов инструментов, чей lineage ссылался на факт
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    rebuilds = service.recompute(args.fact, builder)
    rebuilt = "; ".join(f"{r.snapshot_id} v{r.version}" for r in rebuilds) \
        or "нет мер с lineage на этот факт"
    repos.audit.log("verify", args.fact,
                    {"document": _scrub_url(args.document),
                     "expected": args.expected},
                    True, f"manual_fact={correct}; rebuilt=[{rebuilt}]")
    print(f"manual-факт {correct} записан, {args.fact} помечен superseded")
    print(f"пересчитано: {rebuilt}")
    conn.close()
    return 0


def cmd_status(args) -> int:
    """«Что у меня есть»: каталог, схема, инструменты, снапшоты,
    покрытие, сеть, окружение (TASK-8 U9). --json — один объект."""
    from rusterm import env as env_module
    paths, conn = _open(args.root)
    apply_migrations(conn)  # идемпотентно; свежая база получает схему
    repos = RepoRegistry(conn, paths)
    applied = current_schema_version(conn)
    budget_samples = {s[1]: s[3] for s in repos.metrics.samples()
                      if s[1].startswith("provider_")}
    payload = {
        "data_dir": str(paths.root),
        "schema_version": applied,
        "instruments": repos.metrics.instrument_counts()["total"],
        "watchlists": len(repos.watchlist.list_watchlists()),
        "snapshots": repos.snapshot.latest_per_instrument(),
        "coverage": repos.coverage.status_summary(),
        "budget": {
            "ceiling_per_night": 5000,
            "rate_per_second": 5,
            "provider_ran": bool(budget_samples),
            "samples": budget_samples,
        },
        "env": env_module.report(),
    }
    conn.close()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    print(f"каталог данных: {payload['data_dir']}")
    print(f"схема: {('версия ' + str(applied)) if applied else 'нет базы (rusterm init)'}")
    print(f"инструментов: {payload['instruments']}; списков наблюдения: {payload['watchlists']}")
    if payload["snapshots"]:
        print("последние снапшоты:")
        for s in payload["snapshots"]:
            print(f"  {s['instrument_id']} — v{s['version']}, as_of {s['as_of']}")
    else:
        print("снапшотов нет")
    cov = payload["coverage"]
    print(f"покрытие: готово {cov['ready']}, устарело {cov['stale']}, "
          f"в работе {cov['processing']}, отсутствует {cov['missing']}, "
          f"ошибок {cov['error']}")
    print("сеть: потолок 5000 запросов/ночь, 5/сек; провайдер не работал"
          if not budget_samples else
          f"сеть: зафиксированы счётчики: {budget_samples}")
    print("окружение:")
    for name, origin in payload["env"]["vars"].items():
        state = "задана" if origin != "—" else "не задана"
        print(f"  {name}: {state} ({origin})")
    return 0


def cmd_tui(args) -> int:
    """Терминальный интерфейс (ADR-0009): только чтение, curses."""
    from rusterm.tui import app
    return app.run(args.root, args.watchlist)


def cmd_doctor(args) -> int:
    paths, conn = _open(args.root)
    report = doctor_report(paths, conn)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    conn.close()
    return 0 if report["ok"] else 1


def _scrub_url(url: str) -> str:
    from rusterm.store.repos import scrub_secret_url
    return scrub_secret_url(url)


def _next_version_full_composition(watchlist_repo, watchlist_id: str,
                                   action: str) -> str:
    """Правка состава = новая версия с полным новым составом (T10/T11)."""
    current = watchlist_repo.current_version(watchlist_id)
    if current is None:
        raise ValueError(f"список {watchlist_id!r} не найден")
    version_id = watchlist_repo.new_version(
        str(uuid.uuid4()), watchlist_id, current["version"] + 1,
        action, None)
    watchlist_repo.copy_members(current["watchlist_version_id"], version_id)
    return version_id


def cmd_watchlist(args) -> int:
    paths, conn = _open(args.root)
    repos = RepoRegistry(conn, paths)
    wl = repos.watchlist
    try:
        if args.action == "create":
            wl.create_watchlist(args.id, args.name, None, None)
            wl.new_version(str(uuid.uuid4()), args.id, 1, "create", None)
            repos.audit.log("watchlist_create", args.id,
                            {"name": args.name}, True, "ok")
            print(f"список {args.id} создан (версия 1)")
        elif args.action == "add":
            vid = _next_version_full_composition(wl, args.id, "edit")
            wl.add_member(vid, args.instrument, args.note)
            repos.audit.log("watchlist_add", args.id,
                            {"instrument": args.instrument}, True, "ok")
            print(f"{args.instrument} добавлен, версия "
                  f"{wl.current_version(args.id)['version']}")
        elif args.action == "remove":
            current = wl.current_version(args.id)
            vid = wl.new_version(str(uuid.uuid4()), args.id,
                                 current["version"] + 1, "edit", None)
            wl.copy_members_except(current["watchlist_version_id"], vid,
                                   args.instrument)
            repos.audit.log("watchlist_remove", args.id,
                            {"instrument": args.instrument}, True, "ok")
            print(f"{args.instrument} удалён, версия "
                  f"{wl.current_version(args.id)['version']}")
        elif args.action == "list":
            for row in wl.list_watchlists():
                print(f"{row['watchlist_id']}\t{row['name']}\t"
                      f"v{row['version']}\t{row['member_count']}")
        elif args.action == "show":
            current = wl.current_version(args.id)
            if current is None:
                print(f"список {args.id!r} не найден", file=sys.stderr)
                conn.close()
                return 1
            print(json.dumps({
                "watchlist_id": args.id,
                "current_version": current["version"],
                "action": current["action"],
                "members": wl.members(args.id),
                "groups": wl.groups(args.id),
                "filters": wl.filters(args.id),
            }, ensure_ascii=False, indent=2))
        elif args.action == "rollback":
            result = wl.rollback_to(args.id, args.to)
            repos.audit.log("watchlist_rollback", args.id,
                            {"to_version": args.to}, True, "ok")
            print(f"откат к версии {args.to}: создана версия "
                  f"{result['version']} ({result['action']})")
        elif args.action == "export":
            from rusterm.core.watchlist_io import export_csv, export_json
            text = (export_csv(wl, repos.instrument, args.list, args.as_of)
                    if args.format == "csv"
                    else export_json(wl, repos.instrument, args.list,
                                     args.as_of))
            print(text)
        elif args.action == "import":
            from rusterm.core.watchlist_io import import_rows, parse_import
            with open(args.file, encoding="utf-8") as fh:
                rows = parse_import(fh.read(), args.format)
            report = import_rows(wl, repos.instrument, args.list, rows,
                                 args.as_of)
            repos.audit.log("watchlist_import", args.list,
                            {"file": args.file, "rows": len(rows)},
                            True, json.dumps(
                                {k: len(v) for k, v in report.items()}))
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        conn.close()
        return 1
    conn.close()
    return 0


def cmd_coverage(args) -> int:
    paths, conn = _open(args.root)
    repos = RepoRegistry(conn, paths)
    instrument = args.instrument or args.target
    if (instrument is None) == (args.watchlist is None):
        print("укажите instrument-id или --watchlist, но не оба; "
              "например: rusterm coverage --instrument ID",
              file=sys.stderr)
        conn.close()
        return 1
    target = args.watchlist or instrument
    rows = (repos.coverage.for_watchlist(args.watchlist)
            if args.watchlist else repos.coverage.for_instrument(instrument))
    if not rows:
        print("покрытия нет — сбор ещё не запускался; начните с "
              "rusterm ingest", file=sys.stderr)
        conn.close()
        return 1
    if args.json:
        print(json.dumps({"target": target, "rows": rows},
                         ensure_ascii=False))
        conn.close()
        return 0
    for row in rows:
        reason = f" причина: {row['reason']}" if row["reason"] else ""
        print(f"{row['instrument_id']}\t{row['block']}\t"
              f"{row['status']}{reason}")
    conn.close()
    return 0


def cmd_metrics(args) -> int:
    paths, conn = _open(args.root)
    repos = RepoRegistry(conn, paths)
    from rusterm.core.metrics import SystemMetrics
    metrics = SystemMetrics(repos.metrics, request_gate=None)
    values = metrics.compute()
    written = metrics.record(values) if args.record else 0
    if args.json:
        print(json.dumps({"metrics": values, "recorded": written},
                         ensure_ascii=False))
        conn.close()
        return 0
    if args.record:
        print(f"записано проб: {written} (метрика без данных не пишется)")
    for name in values:
        value = values[name]
        print(f"{name}\t{'нет данных' if value is None else value}")
    conn.close()
    return 0


def cmd_budget(args) -> int:
    paths, conn = _open(args.root)
    repos = RepoRegistry(conn, paths)
    samples = {s[1]: s[3] for s in repos.metrics.samples()
               if s[1].startswith("provider_")}
    payload = {
        "ceiling_per_night": 5000,
        "rate_per_second": 5,
        "provider_ran": bool(samples),
        "used": 0 if not samples else None,
        "refused": 0 if not samples else None,
        "samples": samples,
    }
    conn.close()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    print("потолок запросов за ночь: 5000 (Budget), 5 в секунду "
          "(RateLimiter); лимитеры не хранят состояние между процессами")
    if not samples:
        print("сетевой провайдер не работал: использовано 0, отказано 0 "
              "(записей в metric_sample нет)")
    else:
        for name in sorted(samples):
            print(f"{name} = {samples[name]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from rusterm import env as env_module
    env_module.load_env()  # RUSTERM_* из ~/.rusterm.env, если не в окружении
    parser = argparse.ArgumentParser(
        prog="rusterm", description="EquityLab: локальный терминал (ядро)")
    parser.add_argument("--root", default=".", help="каталог данных")
    sub = parser.add_subparsers(dest="command", required=False)
    sub.add_parser("init", help="создать каталог данных и применить миграции")
    p_ing = sub.add_parser("ingest", help="сбор; реальный источник — не дефолт")
    p_ing.add_argument("--instrument", default=None)
    p_ing.add_argument("--ticker", default=None)
    p_ing.add_argument("--market", default=None)
    p_ing.add_argument("--watchlist", default=None)
    p_ing.add_argument("--source", choices=("synthetic", "edgar"),
                       default="synthetic")
    sub.add_parser("demo", help="создать синтетический демо-инструмент")
    p_snap = sub.add_parser("snapshot", help="собрать снапшот")
    p_snap.add_argument("--instrument", default=None)
    p_snap.add_argument("--ticker", default=None)
    p_snap.add_argument("--market", default=None)
    p_snap.add_argument("--watchlist", default=None)
    p_snap.add_argument("--as-of", default=None)
    p_exp = sub.add_parser("export", help="экспорт последнего снапшота")
    p_exp.add_argument("--instrument", required=True)
    p_exp.add_argument("--format", choices=("json", "csv"), default="json")
    p_exp.add_argument("--out", default=None)
    p_ver = sub.add_parser("verify", help="ручное исправление факта")
    p_ver.add_argument("--fact", required=True,
                       help="id факта, который неверен")
    p_ver.add_argument("--expected", required=True, help="правильное значение")
    p_ver.add_argument("--document", default="",
                       help="ссылка на документ (секреты из URL стираются)")
    sub.add_parser("doctor", help="самопроверка базы и store")
    p_st = sub.add_parser("status", help="что у меня есть: база, снапшоты, покрытие, сеть")
    p_st.add_argument("--json", action="store_true")

    p_wl = sub.add_parser("watchlist", help="списки наблюдения")
    wl_sub = p_wl.add_subparsers(dest="action", required=True)
    p_create = wl_sub.add_parser("create")
    p_create.add_argument("id")
    p_create.add_argument("--name", required=True)
    p_add = wl_sub.add_parser("add")
    p_add.add_argument("id")
    p_add.add_argument("--instrument", required=True)
    p_add.add_argument("--note", default=None)
    p_remove = wl_sub.add_parser("remove")
    p_remove.add_argument("id")
    p_remove.add_argument("--instrument", required=True)
    wl_sub.add_parser("list")
    p_show = wl_sub.add_parser("show")
    p_show.add_argument("id")
    p_rb = wl_sub.add_parser("rollback")
    p_rb.add_argument("id")
    p_rb.add_argument("--to", type=int, required=True)
    p_wl_exp = wl_sub.add_parser("export")
    p_wl_exp.add_argument("--list", required=True)
    p_wl_exp.add_argument("--format", choices=("csv", "json"),
                          default="csv")
    p_wl_exp.add_argument("--as-of", default=None)
    p_wl_imp = wl_sub.add_parser("import")
    p_wl_imp.add_argument("file")
    p_wl_imp.add_argument("--list", required=True)
    p_wl_imp.add_argument("--format", choices=("csv", "json"),
                          default="csv")
    p_wl_imp.add_argument("--as-of", default=None)

    p_cov = sub.add_parser("coverage", help="покрытие инструмента или списка")
    p_cov.add_argument("target", nargs="?", default=None)
    p_cov.add_argument("--instrument", default=None)
    p_cov.add_argument("--watchlist", default=None)
    p_cov.add_argument("--json", action="store_true")
    p_met = sub.add_parser("metrics", help="девять системных метрик")
    p_met.add_argument("--record", action="store_true")
    p_met.add_argument("--json", action="store_true")
    p_bud = sub.add_parser("budget", help="бюджет сетевых запросов")
    p_bud.add_argument("--json", action="store_true")
    p_tui = sub.add_parser("tui", help="терминальный интерфейс (только чтение)")
    p_tui.add_argument("--watchlist", default=None)
    args = parser.parse_args(argv)

    commands = {
        "init": cmd_init, "ingest": cmd_ingest, "snapshot": cmd_snapshot,
        "export": cmd_export, "verify": cmd_verify, "doctor": cmd_doctor,
        "demo": cmd_demo,
        "watchlist": cmd_watchlist, "coverage": cmd_coverage,
        "metrics": cmd_metrics, "budget": cmd_budget,
        "status": cmd_status, "tui": cmd_tui,
    }
    if args.command is None:
        print(f"RusTerm — локальный терминал по ценным бумагам. "
              f"Каталог данных: {args.root}")
        print("Обычный путь:")
        print("  rusterm init")
        print("  rusterm watchlist create <id> --name N   # или rusterm demo для пробы")
        print("  rusterm watchlist add <id> --instrument ID")
        print("  rusterm ingest --instrument ID [--source synthetic|edgar]")
        print("  rusterm snapshot --instrument ID")
        print("  rusterm status        # что у меня есть")
        print("Справка по команде: rusterm <команда> --help")
        return 0
    try:
        return commands[args.command](args)
    except SystemExit:
        raise
    except Exception:
        # неожиданная ошибка: трейсбек в журнал, путь — пользователю, код 2
        import logging
        import traceback
        log_path = AppPaths.from_root(getattr(args, "root", ".")).app_log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=str(log_path))
        logging.getLogger("rusterm.cli").exception("внутренняя ошибка")
        with open(log_path, "a", encoding="utf-8") as fh:
            traceback.print_exc(file=fh)
        print(f"внутренняя ошибка; подробности: {log_path}",
              file=sys.stderr)
        return 2
