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

from rusterm.core.export import snapshot_to_csv, snapshot_to_json, \
    snapshot_to_md
from rusterm.normalize.concepts import CONCEPT_MAP_VERSION
from rusterm.providers.budget import ConfigError, RequestGate
from rusterm.providers import get_provider
from rusterm.core.snapshot import SnapshotBuilder, stale_exclusions
from rusterm.core.refresh import refresh_watchlist
from rusterm.core.verification import VerificationService
from rusterm.pipeline import IngestionPipeline, apply_concept_map
from rusterm.providers import SyntheticDisclosuresProvider
from rusterm.store.db import (
    _SCHEMA_VERSION,
    apply_migrations,
    current_schema_version,
    open_connection,
)
from rusterm.store.doctor import doctor_report
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    Listing,
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
    # тикерная история, чтобы --ticker работал и для демо (TASK-9 V3)
    instruments.upsert_listing(Listing(f"{DEMO_INSTRUMENT}-listing",
                                       DEMO_INSTRUMENT, "US", "USD", 1,
                                       None, None))
    instruments.add_ticker_history(f"{DEMO_INSTRUMENT}-listing",
                                   "DEMO", "2020-01-01", None, None, None)




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
                  f"инструмент; добавьте компанию: "
                  f"rusterm add --ticker {args.ticker} --market {market}",
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
        exit_code = 0
        for instrument_id, issuer_id in targets:
            code = _ingest_edgar_companyfacts(repos, instrument_id,
                                              issuer_id, args_as_of_default())
            if code != 0:
                exit_code = code
        conn.close()
        return exit_code
    from rusterm.providers.disclosures import DEMO_INDEX_FIXTURE
    providers = {"synthetic": SyntheticDisclosuresProvider(
        fixture_path=DEMO_INDEX_FIXTURE)}
    pipe = IngestionPipeline(repos, providers)
    for instrument_id, issuer_id in targets:
        result = pipe.run(instrument_id, issuer_id, "synthetic")
        print(f"{instrument_id}: заданий закрыто: {result.jobs_done}; "
              f"фактов: {result.facts_stored}; "
              f"дублей sha256: {result.duplicates}; неразобрано (E4): "
              f"{result.needs_verification}; suspect (E5): {result.suspects}; "
              f"неотображённых концептов: {result.unmapped_concepts}")
    conn.close()
    return 0


def _ingest_edgar_companyfacts(repos, instrument_id: str,
                               issuer_id: str, as_of: str) -> int:
    """Edgar-сбор (TASK-11 X1): карта тикеров (1 запрос на рынок) +
    companyfacts (1 запрос на эмитента) -> raw -> parse -> факты.
    Идемпотентно по sha256; неотображённые теги считаются."""
    import hashlib
    import uuid as _uuid

    from rusterm.normalize.concepts import CONCEPT_MAP_VERSION
    from rusterm.parsers import CompanyFactsParser
    from rusterm.providers.budget import ConfigError
    from rusterm.store.repos import persist_ingestion_results

    instrument = repos.instrument.get_instrument(instrument_id)
    issuer = repos.instrument.get_issuer(instrument.issuer_id) \
        if instrument else None
    if issuer is None or not (issuer.registry_id or "").isdigit():
        print(f"у эмитента {issuer_id!r} нет CIK — выполните "
              f"rusterm add --ticker ... --market ...", file=sys.stderr)
        return 1
    gate = RequestGate()
    provider = get_provider("edgar", gate=gate)
    if isinstance(provider, ConfigError):
        print(f"edgar-провайдер недоступен: {provider.reason}",
              file=sys.stderr)
        return 1
    provider.cik = int(issuer.registry_id)

    # TASK-12 Y5: тёплого прогона карты тикеров здесь больше нет — CIK
    # уже пришёл из issuer.registry_id выше, а resolve тянул всю карту
    # тикеров (один запрос за прогон) и выбрасывал результат.
    facts = provider.fetch_companyfacts()
    if isinstance(facts, ConfigError):
        print(f"edgar недоступен: {facts.reason}", file=sys.stderr)
        return 1
    raw = json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()
    sha = hashlib.sha256(raw).hexdigest()
    if repos.raw.has(sha):
        print(f"{instrument_id}: companyfacts уже в store — пропущено")
        return 0
    obj = repos.raw.put(raw, provider="edgar", block="fundamentals",
                        url=("https://data.sec.gov/api/xbrl/companyfacts/"
                             f"CIK{int(issuer.registry_id):010d}.json"),
                        instrument_id=instrument_id)
    parsed = CompanyFactsParser().parse(
        raw, {"issuer_id": issuer_id, "source_ref": obj.sha256})
    fact_dicts = []
    unmapped = 0
    for fact in parsed.facts:
        fact = dict(fact)
        fact["fact_id"] = str(_uuid.uuid4())
        unmapped += apply_concept_map(fact)
        fact_dicts.append(fact)
    persist_ingestion_results(repos.conn, fact_dicts, [])
    repos.coverage.upsert(instrument_id, "fundamentals", "ready")
    print(f"{instrument_id}: companyfacts загружены; фактов: "
          f"{len(fact_dicts)}; неотображённых концептов: {unmapped}")
    return 0


def cmd_refresh(args) -> int:
    """Инкрементальный проход по списку наблюдения (TASK-13 Z4).
    Одну команду ставят в cron; демона, службы и фонового потока в
    проекте нет. --dry-run печатает план, не делая ни одного запроса."""
    paths, conn = _open(args.root)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    # TASK-15 C3: команда, которой нечего делать, обязана это сказать.
    # Неизвестный id — ошибка (stderr + код 1); пустой, но существующий
    # список — обычная ситуация (строка, код 0). Топ-уровень --json не
    # расширяется: ошибка живёт в существующей форме results.
    if repos.watchlist.current_version(args.watchlist) is None:
        reason = f"список наблюдения {args.watchlist!r} не найден"
        print(reason, file=sys.stderr)
        if args.json:
            print(json.dumps({
                "watchlist_id": args.watchlist,
                "dry_run": bool(args.dry_run),
                "results": [{"instrument_id": "", "issuer_id": "",
                             "action": "error", "facts": None,
                             "last_filing_date": None, "reason": reason}],
                "requests": {"submissions": 0, "companyfacts": 0},
            }, ensure_ascii=False))
        conn.close()
        return 1
    if not repos.watchlist.members(args.watchlist):
        # --json обязан оставаться машиночитаемым: заметка о пустоте
        # идёт в тот же канал, что и весь не-JSON вывод команды
        message = (f"список наблюдения {args.watchlist!r} пуст —"
                   " участников нет")
        print(message, file=sys.stderr if args.json else sys.stdout)

    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    gate = RequestGate()

    def provider_factory(cik: int):
        provider = get_provider("edgar", gate=gate)
        if isinstance(provider, ConfigError):
            return provider
        provider.cik = cik
        return provider

    results = refresh_watchlist(
        repos, provider_factory, args.watchlist, args_as_of_default(),
        dry_run=args.dry_run, builder=None if args.dry_run else builder)
    errors = sum(1 for r in results if r.action == "error")

    # TASK-14 A5: проход мутирует store — факты, покрытие, снапшоты —
    # и обязан оставить строку аудита, как всякая мутирующая команда.
    # --dry-run ничего не меняет и строки не пишет. Отказ файла аудита
    # (B12) команду не роняет: причина уходит на stderr, строка при
    # этом всё равно в базе; код возврата — по результатам прохода.
    if not args.dry_run:
        file_error = repos.audit.log(
            "refresh", args.watchlist,
            {"updated": sum(1 for r in results if r.action == "updated"),
             "unchanged": sum(1 for r in results
                              if r.action == "unchanged"),
             "error": errors,
             "submissions": sum(r.calls.get("submissions", 0)
                                for r in results),
             "companyfacts": sum(r.calls.get("companyfacts", 0)
                                 for r in results)},
            confirmed=False,
            result="ok" if errors == 0 else "errors")
        if file_error:
            print(file_error, file=sys.stderr)
    conn.close()
    if args.json:
        print(json.dumps({
            "watchlist_id": args.watchlist,
            "dry_run": bool(args.dry_run),
            "results": [{"instrument_id": r.instrument_id,
                         "issuer_id": r.issuer_id, "action": r.action,
                         "facts": r.facts,
                         "last_filing_date": r.last_filing_date,
                         "reason": r.reason} for r in results],
            "requests": {"submissions": sum(
                             r.calls.get("submissions", 0)
                             for r in results if r.action != "planned"),
                         "companyfacts": sum(
                             r.calls.get("companyfacts", 0)
                             for r in results if r.action != "planned")},
        }, ensure_ascii=False))
        return 0
    for r in results:
        if r.action == "updated":
            print(f"{r.instrument_id}: обновлён (фактов {r.facts})")
        elif r.action == "unchanged":
            print(f"{r.instrument_id}: не изменилось ({r.reason}; "
                  f"последняя отчётность {r.last_filing_date})")
        elif r.action == "planned":
            print(f"{r.instrument_id}: запланировано ({r.reason})")
        else:
            print(f"{r.instrument_id}: ошибка ({r.reason})")
    return 0 if errors == 0 else 1


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
            else snapshot_to_json(snapshot, measures)
            if args.format == "json" else snapshot_to_md(measures))
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
    # TASK-15 C5: если правленный факт был исключён правилом давности,
    # пользователь видит почему — тот же маркер, что в панели источника
    wrong = repos.fact.get_fact(args.fact)
    if wrong and wrong.get("issuer_id"):
        exclusions = stale_exclusions(repos.snapshot, wrong["issuer_id"])
        if args.fact in exclusions:
            period_end, anchor = exclusions[args.fact]
            print(f"устаревший (последний {period_end}, anchor {anchor})")
    conn.close()
    return 0


def cmd_status(args) -> int:
    """«Что у меня есть»: каталог, схема, инструменты, снапшоты,
    покрытие, сеть, окружение (TASK-8 U9). --json — один объект."""
    from rusterm import env as env_module
    paths, conn = _open(args.root)
    # BACKLOG B25: версия «как застали» снимается ДО тихой миграции —
    # база, отставшая от кода, видна в status, а не только в doctor
    observed = current_schema_version(conn)
    apply_migrations(conn)  # идемпотентно; свежая база получает схему
    repos = RepoRegistry(conn, paths)
    applied = current_schema_version(conn)
    budget_samples = {s[1]: s[3] for s in repos.metrics.samples()
                      if s[1].startswith("provider_")}
    payload = {
        "data_dir": str(paths.root),
        "schema_version": applied,
        "schema_version_expected": _SCHEMA_VERSION,
        "schema_version_observed": observed,
        "instruments": repos.metrics.instrument_counts()["total"],
        "watchlists": len(repos.watchlist.list_watchlists()),
        "snapshots": repos.snapshot.latest_per_instrument(),
        "coverage": repos.coverage.status_summary(),
        "concept_map_version": CONCEPT_MAP_VERSION,
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
    if observed is not None and applied != observed:
        print(f"схема: найдена версия {observed}, обновлена до {applied}")
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


def cmd_add(args) -> int:
    """Создать эмитента + инструмент + листинг + историю тикера
    (TASK-9 V3). Идемпотентно: повтор — «уже есть», код 0. Онлайн
    (есть контакт SEC) --cik/--name берутся из карты тикеров EDGAR;
    офлайн оба обязательны."""
    paths, conn = _open(args.root)
    # add не создаёт схему: на неинициализированной базе — одна фраза
    # и код 1, без трейсбека (TASK-10 W6)
    if current_schema_version(conn) is None:
        print("база не создана; выполните rusterm init", file=sys.stderr)
        conn.close()
        return 1
    repos = RepoRegistry(conn, paths)
    instruments = repos.instrument
    instrument_id = args.instrument_id or f"{args.market}-{args.ticker.upper()}"

    from rusterm.providers.base import ProviderError as _PE
    from rusterm.providers.budget import ConfigError, NetworkGate, RequestGate
    cik, name = args.cik, args.name
    if cik is None or name is None:
        headers = NetworkGate().headers()
        if isinstance(headers, ConfigError):
            # нет контакта и не хватает данных: пробуем сетевого
            # провайдера без гейта — реестр честно откажет значением
            provider = get_provider("edgar", gate=None)
            reason = (provider.reason if isinstance(provider, ConfigError)
                      else "contact_unset")
            missing = [flag for flag, value in
                       (("--cik", cik), ("--name", name)) if value is None]
            print(f"нет контакта SEC ({reason}); офлайн-режим "
                  f"требует {' и '.join(missing)}; задайте их или "
                  f"заполните ~/.rusterm.env", file=sys.stderr)
            conn.close()
            return 1
        # гейт обязателен: реестр возвращает ConfigError-значение,
        # а не провайдера, если гейт не передан (TASK-10 W0)
        provider = get_provider("edgar", gate=RequestGate())
        if isinstance(provider, ConfigError):
            print(f"сетевой провайдер недоступен: {provider.reason}",
                  file=sys.stderr)
            conn.close()
            return 1
        resolution = provider.resolve(args.ticker, args.market,
                                      args_as_of_default())
        if isinstance(resolution, _PE):
            print(f"тикер {args.ticker!r} не найден в EDGAR: "
                  f"{resolution.reason}", file=sys.stderr)
            conn.close()
            return 1
        cik = cik if cik is not None else resolution["cik"]
        name = name or resolution.get("title") or args.ticker.upper()

    if instruments.get_instrument(instrument_id) is not None:
        print(f"инструмент {instrument_id} уже существует")
        conn.close()
        return 0

    issuer_id = f"cik-{cik}"
    instruments.upsert_issuer(Issuer(
        issuer_id, name, "US", str(cik), None, "us_gaap", "USD"))
    instruments.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, args.class_, "active", None))
    listing_id = f"{instrument_id}-listing"
    instruments.upsert_listing(Listing(
        listing_id, instrument_id, args.market, "USD", 1, None, None))
    instruments.add_ticker_history(listing_id, args.ticker.upper(),
                                   args_as_of_default(), None, None, None)
    repos.audit.log("add", instrument_id,
                    {"ticker": args.ticker.upper(), "market": args.market,
                     "cik": cik}, True, "ok")
    print(f"создан инструмент {instrument_id} "
          f"(эмитент {name}, CIK {cik}, тикер {args.ticker.upper()} "
          f"на {args.market})")
    conn.close()
    return 0


def cmd_doctor(args) -> int:
    paths, conn = _open(args.root)
    report = doctor_report(paths, conn)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    conn.close()
    return 0 if report["ok"] else 1


def _scrub_url(url: str) -> str:
    from rusterm.store.repos import scrub_secret_url
    return scrub_secret_url(url)


def instruments_resolve(repos, ticker: str, market: str) -> list | None:
    """Разрешение тикера через InstrumentRepo.resolve_ticker_candidates —
    второго резолвера нет (TASK-9 V3)."""
    return repos.instrument.resolve_ticker_candidates(
        ticker, market, args_as_of_default())


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
    instruments = repos.instrument
    try:
        if args.action == "create":
            wl.create_watchlist(args.id, args.name, None, None)
            wl.new_version(str(uuid.uuid4()), args.id, 1, "create", None)
            repos.audit.log("watchlist_create", args.id,
                            {"name": args.name}, True, "ok")
            print(f"список {args.id} создан (версия 1)")
        elif args.action == "add":
            if args.instrument is None:
                if not args.ticker or not args.market:
                    print("нужен --instrument ID либо --ticker T "
                          "--market M", file=sys.stderr)
                    conn.close()
                    return 1
                candidates = instruments_resolve(repos,
                                                 args.ticker, args.market)
                if candidates is None:
                    conn.close()
                    return 1
                if len(candidates) > 1:
                    print(f"тикер {args.ticker!r} неоднозначен: "
                          f"{', '.join(candidates)}", file=sys.stderr)
                    conn.close()
                    return 1
                args.instrument = candidates[0]
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
            version = args.version if args.version is not None \
                else current["version"]
            action = wl.version_action(args.id, version)
            if action is None and args.version is not None:
                print(f"версия {version} списка {args.id!r} не найдена",
                      file=sys.stderr)
                conn.close()
                return 1
            print(json.dumps({
                "watchlist_id": args.id,
                "version": version,
                "action": action or "",
                "members": wl.members(args.id, version=version),
                "groups": wl.groups(args.id, version=version),
                "filters": wl.filters(args.id, version=version),
            }, ensure_ascii=False, indent=2))
        elif args.action == "rollback":
            result = wl.rollback_to(args.id, args.to)
            repos.audit.log("watchlist_rollback", args.id,
                            {"to_version": args.to}, True, "ok")
            print(f"откат к версии {args.to}: создана версия "
                  f"{result['version']} ({result['action']})")
        elif args.action == "export":
            from rusterm.core.watchlist_io import export_csv, export_json
            outcome = (export_csv(wl, repos.instrument, args.list,
                                  args.as_of)
                       if args.format == "csv"
                       else export_json(wl, repos.instrument, args.list,
                                        args.as_of))
            text, note = outcome
            print(text)
            print(f"примечание: {note}", file=sys.stderr)
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
        # X3: список отсутствующих концептов — массивом рядом с причиной
        for row in rows:
            if (row["status"] == "missing"
                    and (row["reason"] or "").startswith("missing_data:")):
                row["missing_concepts"] = [
                    c.strip() for c in row["reason"].split(":", 1)[1].split(",")
                    if c.strip()]
        print(json.dumps({"target": target,
                          "concept_map_version": CONCEPT_MAP_VERSION,
                          "rows": rows}, ensure_ascii=False))
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
    p_add = sub.add_parser("add", help="добавить настоящую компанию")
    p_add.add_argument("--ticker", required=True)
    p_add.add_argument("--market", required=True)
    p_add.add_argument("--cik", type=int, default=None)
    p_add.add_argument("--name", default=None)
    p_add.add_argument("--instrument-id", dest="instrument_id", default=None)
    p_add.add_argument("--class", dest="class_", default="common")
    p_snap = sub.add_parser("snapshot", help="собрать снапшот")
    p_snap.add_argument("--instrument", default=None)
    p_snap.add_argument("--ticker", default=None)
    p_snap.add_argument("--market", default=None)
    p_snap.add_argument("--watchlist", default=None)
    p_snap.add_argument("--as-of", default=None)
    p_exp = sub.add_parser("export", help="экспорт последнего снапшота")
    p_exp.add_argument("--instrument", required=True)
    p_exp.add_argument("--format", choices=("json", "csv", "md"),
                       default="json")
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
    p_add.add_argument("--instrument", default=None)
    p_add.add_argument("--ticker", default=None)
    p_add.add_argument("--market", default=None)
    p_add.add_argument("--note", default=None)
    p_remove = wl_sub.add_parser("remove")
    p_remove.add_argument("id")
    p_remove.add_argument("--instrument", required=True)
    wl_sub.add_parser("list")
    p_show = wl_sub.add_parser("show")
    p_show.add_argument("id")
    p_show.add_argument("--version", type=int, default=None)
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
    p_ref = sub.add_parser("refresh",
                           help="инкрементальный проход по списку наблюдения (для cron)")
    p_ref.add_argument("--watchlist", required=True)
    p_ref.add_argument("--dry-run", dest="dry_run", action="store_true")
    p_ref.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    commands = {
        "init": cmd_init, "ingest": cmd_ingest, "snapshot": cmd_snapshot,
        "export": cmd_export, "verify": cmd_verify, "doctor": cmd_doctor,
        "demo": cmd_demo,
        "watchlist": cmd_watchlist, "coverage": cmd_coverage,
        "metrics": cmd_metrics, "budget": cmd_budget,
        "status": cmd_status, "tui": cmd_tui, "add": cmd_add,
        "refresh": cmd_refresh,
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
        import traceback as _tb
        logging.basicConfig(filename=str(log_path))
        logging.getLogger("rusterm.cli").exception("внутренняя ошибка")
        _tb.print_exc()  # при отладке e2e traceback виден и в stderr
        with open(log_path, "a", encoding="utf-8") as fh:
            traceback.print_exc(file=fh)
        print(f"внутренняя ошибка; подробности: {log_path}",
              file=sys.stderr)
        return 2
