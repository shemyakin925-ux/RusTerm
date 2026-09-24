"""CLI: init, ingest, snapshot, export, verify, doctor.

Точка входа rusterm.cli:main (pyproject.toml). Ни строки Qt; SQL только
в rusterm/store — команды оркестрируют store и core, сами в базу не ходят.
Все операции офлайн, на синтетических данных.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import uuid

from rusterm.core.export import format_source_cell, refusal_advice, snapshot_to_csv, snapshot_to_json, \
    snapshot_to_md
from rusterm.normalize.concepts import CONCEPT_MAP_VERSION
from rusterm.providers.budget import ConfigError, RequestGate
from rusterm.providers import get_provider
from rusterm.core.industry.aggregate import build_sector_aggregates
from rusterm.core.snapshot import snapshot_measures_identical
from rusterm.core.snapshot import SnapshotBuilder, stale_exclusions
from rusterm.markets import MARKET_CODES
from rusterm.normalize.concepts import CONCEPT_MAP_VERSION_IFRS
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
from rusterm.store.paths import AppPaths, ensure_app_dir, resolve_root
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


def _open_readonly(root: str):
    """Открыть каталог данных, НЕ создавая его (BACKLOG B35).

    Дефект (измерено координатором 17.09.2026): `rusterm markets` —
    команда, которая только читает реестр рынков, — создавала в
    ТЕКУЩЕМ каталоге rusterm.db, exports/, logs/ и raw/. Запуск из
    корня репозитория ронял приёмку пунктом 13 у того, кто её запустил.
    Базы нет — возвращается (paths, None): читать нечего, и это не
    ошибка. Команды, которые пишут, по-прежнему идут через _open.
    """
    paths = AppPaths.from_root(root)
    if not paths.db_path.exists():
        return paths, None
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
    if args.source == "twelvedata":
        # Котировки (ТЗ-30 B2): сбор никогда не дефолт — только по
        # явному --source, как edgar.
        exit_code = 0
        for instrument_id, issuer_id in targets:
            code = _ingest_twelvedata_prices(repos, instrument_id,
                                             args_as_of_default())
            if code != 0:
                exit_code = code
            # Корпоративные действия (ТЗ-31 C3): тот же вендор, свои
            # два payload'а со своим кешем; отказ не топит котировки
            code = _ingest_twelvedata_actions(repos, instrument_id,
                                              args_as_of_default())
            if code != 0:
                exit_code = code
        conn.close()
        return exit_code
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
    if args.source == "cvm":
        # Фундаментал Бразилии (ТЗ-56 Z2): годовые наборы DFP; дверь
        # только по явному --source, как у edgar
        exit_code = 0
        for instrument_id, issuer_id in targets:
            code = _ingest_cvm_dfp(repos, instrument_id,
                                   issuer_id, args_as_of_default())
            if code != 0:
                exit_code = code
        conn.close()
        return exit_code
    if args.source == "asx":
        # Анонсы Австралии (ТЗ-57 A4): дверь только по явному
        # --source, как у edgar/cvm
        exit_code = 0
        for instrument_id, issuer_id in targets:
            code = _ingest_asx_announcements(repos, instrument_id,
                                             issuer_id,
                                             args_as_of_default())
            if code != 0:
                exit_code = code
        conn.close()
        return exit_code
    if args.source == "ownership":
        # Владение Forms 3/4/5 (ТЗ-32 D2): реальный сбор никогда не
        # дефолт; metadata из submissions, тела — с Archives
        exit_code = 0
        for instrument_id, issuer_id in targets:
            code = _ingest_edgar_ownership(repos, instrument_id,
                                           issuer_id, args_as_of_default())
            if code != 0:
                exit_code = code
        conn.close()
        return exit_code
    from rusterm.markets import get_market, provider_channel
    from rusterm.providers import channel_key_env
    import os as _os
    # ТЗ-61 F4: дефолтный синтетический сбор честно служит демо; рынок,
    # чей канал закрыт ключом (KR: dart), получает отказ с причиной из
    # словаря и строкой, что именно сделать, — не выдуманные факты.
    runnable = []
    exit_code = 0
    for instrument_id, issuer_id in targets:
        market = get_market(instrument_id.split("-", 1)[0])
        key_env = channel_key_env(market.provider) if market else None
        if (market is not None
                and provider_channel(market.provider) is None
                and key_env and not _os.environ.get(key_env)):
            from rusterm.providers.dart import dart_key_instruction
            exit_code = 1
            print(f"{instrument_id}: сбор недоступен: dart_key_unset — "
                  f"{dart_key_instruction(key_env)}", file=sys.stderr)
            continue
        runnable.append((instrument_id, issuer_id))
    from rusterm.providers.disclosures import DEMO_INDEX_FIXTURE
    providers = {"synthetic": SyntheticDisclosuresProvider(
        fixture_path=DEMO_INDEX_FIXTURE)}
    pipe = IngestionPipeline(repos, providers)
    for instrument_id, issuer_id in runnable:
        result = pipe.run(instrument_id, issuer_id, "synthetic")
        total_tags = result.facts_stored + result.unmapped_concepts
        print(f"{instrument_id}: заданий закрыто: {result.jobs_done}; "
              f"фактов: {result.facts_stored}; "
              f"дублей sha256: {result.duplicates}; неразобрано (E4): "
              f"{result.needs_verification}; suspect (E5): {result.suspects}; "
              f"неотображённых концептов: {result.unmapped_concepts} "
              f"(теги вне карты концептов мерами не стали — это норма; "
              f"карта узнала {result.facts_stored} из {total_tags})")
    conn.close()
    return exit_code


def _ingest_twelvedata_prices(repos, instrument_id: str, as_of: str,
                              start: str | None = None,
                              provider=None) -> int:
    """Котировочный сбор (ТЗ-30 B2, ТЗ-23 K2, ADR-0014, ТЗ-90 A1): один
    запрос /time_series на дату, payload в raw-хранилище, строки в
    price. Повторный сбор того же `as_of` находит payload по
    каноническому URL без ключа (raw_object.url) и тратит ноль
    запросов (ADR-0003); следующий `as_of` — новый URL, то есть новый
    запрос, иначе первый сбор оставался последним навсегда. Дубли дат
    не пишутся (I7). provider инъецируется тестами с фейковым
    транспортом; в команде строится из окружения."""
    from rusterm.providers.base import ProviderError
    from rusterm.providers.budget import (
        BudgetExceeded,
        ConfigError,
        RequestGate,
    )

    tick = repos.instrument.ticker_for_instrument(instrument_id, as_of)
    if tick is None:
        print(f"у {instrument_id!r} нет тикера на {as_of}",
              file=sys.stderr)
        return 1
    symbol = tick["ticker"]
    price_gate = None
    if provider is None:
        price_gate = RequestGate()
        provider = get_provider("twelvedata", gate=price_gate)
    if isinstance(provider, ConfigError):
        print(f"twelvedata недоступен: {provider.reason}",
              file=sys.stderr)
        if provider.reason == "twelvedata_key_unset":
            from rusterm.providers.twelvedata import key_instruction
            print(f"что делать: {key_instruction()}", file=sys.stderr)
        return 1

    cache_url = provider.cache_url(symbol, start, as_of)
    cached_sha = repos.raw.find_by_provider_url("twelvedata", cache_url)
    requests_spent = 0
    if cached_sha is not None:
        payload = json.loads(repos.raw.get(cached_sha).decode("utf-8"))
    else:
        outcome = provider.time_series(symbol, start=start, end=as_of)
        if isinstance(outcome, (ProviderError, ConfigError,
                                BudgetExceeded)):
            # Отказ — тоже запрос: гейт его пропустил, значит budget
            # обязан его назвать (ТЗ-96 R3: на живом прогоне 403-ный
            # вызов исчезал из счётчика).
            _record_gate_usage(repos, "twelvedata", price_gate)
            print(f"twelvedata: {outcome.reason}", file=sys.stderr)
            return 1
        payload = outcome
        requests_spent = 1
        raw = json.dumps(payload, sort_keys=True,
                         ensure_ascii=False).encode("utf-8")
        repos.raw.put(raw, provider="twelvedata", block="prices",
                      url=cache_url, instrument_id=instrument_id)
    rows = provider.parse_series(payload)
    inserted = repos.price.put_rows(instrument_id, "twelvedata", rows)
    last = rows[-1]["date"] if rows else "—"
    # ТЗ-64 J1: путь через RequestGate записывает его расход; цена была
    # единственным путём, который этого не делал — живая котировка
    # считалась нулём запросов. Инъецированный провайдер оставляет gate
    # равным None: чужой гейт не считаем.
    _record_gate_usage(repos, "twelvedata", price_gate)
    print(f"{instrument_id}: строк получено: {len(rows)}; "
          f"записано новых: {inserted}; запросов: {requests_spent}; "
          f"последняя дата: {last}")
    return 0


def _ingest_twelvedata_actions(repos, instrument_id: str, as_of: str,
                               provider=None) -> int:
    """Корпоративные действия с вендора (ТЗ-31 C3, ТЗ-90 A1): /splits и
    /dividends тем же каналом, что котировки; каждый payload кешируется
    по каноническому URL без ключа (ADR-0003), и URL этот датированный —
    на следующий `as_of` он другой, то есть свежее событие действительно
    доходит до нас. События пишутся в corporate_action (I7:
    уникальность (инструмент, ex_date, вид)).
    Суммы пишутся КАК ОТДАЛ ВЕНДОР — в сегодняшней базе акций, той же,
    в которой вендорский close (ADR-0020): отношение дивиденд/close
    инвариантно к базе, и пересчёт в объявленную сумму на дату в
    хранилище не делается. Сплиты пишутся как есть: фактор
    k = from_factor/to_factor."""
    from rusterm.providers.base import ProviderError
    from rusterm.providers.budget import (
        BudgetExceeded,
        ConfigError,
        RequestGate,
    )

    tick = repos.instrument.ticker_for_instrument(instrument_id, as_of)
    if tick is None:
        print(f"у {instrument_id!r} нет тикера на {as_of}",
              file=sys.stderr)
        return 1
    symbol = tick["ticker"]
    ca_gate = None
    if provider is None:
        ca_gate = RequestGate()
        provider = get_provider("twelvedata", gate=ca_gate)
    if isinstance(provider, ConfigError):
        print(f"twelvedata недоступен: {provider.reason}",
              file=sys.stderr)
        if provider.reason == "twelvedata_key_unset":
            from rusterm.providers.twelvedata import key_instruction
            print(f"что делать: {key_instruction()}", file=sys.stderr)
        return 1

    payloads: dict[str, dict] = {}
    requests_spent = 0
    for kind, fetch in (("splits", provider.splits),
                        ("dividends", provider.dividends)):
        cache_url = provider.cache_url_ca(kind, symbol, as_of)
        cached_sha = repos.raw.find_by_provider_url("twelvedata", cache_url)
        if cached_sha is not None:
            payloads[kind] = json.loads(
                repos.raw.get(cached_sha).decode("utf-8"))
            continue
        outcome = fetch(symbol, as_of)
        if isinstance(outcome, (ProviderError, ConfigError,
                                BudgetExceeded)):
            # Тот же счёт, что у котировок: отказанный вызов гейт уже
            # пропустил, и терять его на выходе из стадии нельзя.
            _record_gate_usage(repos, "twelvedata", ca_gate)
            print(f"twelvedata: {kind}: {outcome.reason}", file=sys.stderr)
            return 1
        payloads[kind] = outcome
        requests_spent += 1
        raw = json.dumps(outcome, sort_keys=True,
                         ensure_ascii=False).encode("utf-8")
        repos.raw.put(raw, provider="twelvedata",
                      block="corporate_actions", url=cache_url,
                      instrument_id=instrument_id)

    splits, splits_skipped = provider.parse_splits(payloads["splits"])
    dividends, currency, div_skipped = provider.parse_dividends(
        payloads["dividends"])
    written = 0
    for s in splits:
        if repos.corp_action.put(instrument_id, s["ex_date"], "split",
                                 factor=s["factor"]):
            written += 1
    for d in dividends:
        if repos.corp_action.put(instrument_id, d["ex_date"], "dividend",
                                 amount=d["amount"], currency=currency):
            written += 1
    skipped = splits_skipped + div_skipped
    _record_gate_usage(repos, "twelvedata", ca_gate)
    print(f"{instrument_id}: корп.действия: сплитов {len(splits)}; "
          f"дивидендов {len(dividends)}; записано новых: {written}; "
          f"запросов: {requests_spent}; неразобрано: {skipped}")
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
    print(f"{instrument_id}: стадия загрузки — companyfacts "
          "(data.sec.gov)…", file=sys.stderr, flush=True)
    facts = provider.fetch_companyfacts()
    if isinstance(facts, ConfigError):
        print(f"edgar недоступен: {facts.reason}", file=sys.stderr)
        if facts.reason == "sec_ua_unset":
            from rusterm.providers.edgar import sec_ua_instruction
            print(f"что делать: {sec_ua_instruction()}",
                  file=sys.stderr)
        return 1
    _record_gate_usage(repos, "edgar", gate)
    from rusterm.providers.base import ProviderError as _PE
    if isinstance(facts, _PE) and facts.reason == "no_sec_filings":
        # TASK-18 G5 (§0.3 ruling 4): «не подаёт XBRL в SEC» — ответ, а
        # не сбой. Инструмент существует, coverage missing с причиной,
        # команда успешно завершилась.
        repos.coverage.upsert(instrument_id, "fundamentals", "missing",
                              reason="no_sec_filings")
        print(f"{instrument_id}: эмитент не подаёт XBRL в SEC "
              f"(companyfacts 404) — покрытие missing: no_sec_filings")
        return 0
    raw = json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()
    print(f"{instrument_id}: стадия записи — получено {len(raw)} байт…",
          file=sys.stderr, flush=True)
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


def _record_gate_usage(repos, provider: str, gate) -> None:
    """ТЗ-64 J1: расход гейта пишется немедленно в metric_sample —
    budget и status называют число сделанных запросов, а не память.
    Один хелпер для всякого пути через RequestGate."""
    if gate is None:
        return
    import time as _time
    repos.metrics.record_sample(_time.time(), "provider_requests_used",
                                provider, float(gate.calls_made))


def _record_cvm_budget(repos, gate) -> None:
    """Счётчик гейта — в metric_sample: rusterm budget называет число
    израсходованных запросов, а не память (ТЗ-56 Z2)."""
    import time as _time
    repos.metrics.record_sample(_time.time(), "provider_requests_used",
                                "cvm", float(gate.calls_made))


def _ingest_asx_announcements(repos, instrument_id: str, issuer_id: str,
                              as_of: str) -> int:
    """ASX-канал (ТЗ-57 A4, форма ТЗ-56 Z2): список анонсов эмитента —
    сырьё с провенансом в raw store (кеш по каноническому URL без
    ключа, неизменный список — ноль запросов). ТЕЛА документов
    бесплатным каналом недостижимы (двухшаговая PDF-цепочка не
    проверена живьём, ADR-0010 §5): каждая подача честно называется
    manual_import_required:asxdoc:<ключ> — фактов канал не приносит,
    ни одна мера не возникает из воздуха. Рыночного индекса у канала
    нет (asx_no_marketwide_index) — инкрементальность по эмитенту:
    повторный прогон переиспользует тело по URL-кешу."""
    import json as _json
    import time as _time

    from rusterm.providers.base import ProviderError as _PE
    from rusterm.providers.budget import BudgetExceeded, ConfigError

    instrument = repos.instrument.get_instrument(instrument_id)
    if instrument is None:
        print(f"инструмента нет в базе: {instrument_id}", file=sys.stderr)
        return 1
    tick = repos.instrument.ticker_for_instrument(instrument_id, as_of)
    if tick is None:
        print(f"у {instrument_id!r} нет тикера на {as_of}",
              file=sys.stderr)
        return 1
    code = str(tick["ticker"]).upper()
    gate = RequestGate()
    provider = get_provider("asx", gate=gate)
    if isinstance(provider, ConfigError):
        print(f"asx-провайдер недоступен: {provider.reason}",
              file=sys.stderr)
        return 1

    url = (f"https://asx.api.markitdigital.com/asx-research/1.0/"
           f"companies/{code}/announcements")
    cached_sha = repos.raw.find_by_provider_url("asx", url)
    requests_spent = 0
    if cached_sha is not None:
        raw = repos.raw.get(cached_sha)
    else:
        raw = provider.announcements_raw(code)
        if isinstance(raw, (ConfigError, BudgetExceeded, _PE)):
            reason = getattr(raw, "reason", "budget_exceeded")
            print(f"asx недоступен: {reason}", file=sys.stderr)
            repos.metrics.record_sample(_time.time(),
                                        "provider_requests_used",
                                        "asx", float(gate.calls_made))
            return 1
        repos.raw.put(raw, provider="asx", block="disclosures",
                      url=url, instrument_id=instrument_id)
        requests_spent = 1
    repos.metrics.record_sample(_time.time(), "provider_requests_used",
                                "asx", float(gate.calls_made))

    items = ((_json.loads(raw.decode("utf-8")).get("data") or {})
             .get("items") or [])
    named = 0
    for item in items:
        key = item.get("documentKey", "")
        outcome = provider.fetch_document(f"asxdoc:{key}")
        if isinstance(outcome, _PE) and outcome.reason.startswith(
                "manual_import_required"):
            named += 1
    print(f"{instrument_id}: анонсов: {len(items)}; тел машинно "
          f"недостижимо: {named} (manual_import_required); фактов: 0; "
          f"запросов: {requests_spent}")
    return 0


def _ingest_cvm_dfp(repos, instrument_id: str, issuer_id: str,
                    as_of: str) -> int:
    """CVM-сбор фундаментала (ТЗ-56 Z2): годовой набор DFP за последний
    закрытый год, консолидированные DRE+BPP -> строки эмитента -> факты
    с провенансом (сырьё — ZIP целиком в raw store).

    Инкрементальность по Last-Modified из issuer_ingest_state
    (source='cvm'): неизменный набор — один HEAD, GET не выполняется.
    Бюджет: 1 запрос при неизменности, до 3 на свежую загрузку
    (HEAD + HEAD+GET: публичная поверхность провайдера), потолок хоста
    по объявлению CvmProvider; счёт — в rusterm budget.
    """
    import hashlib
    import uuid as _uuid

    from rusterm.parsers.cvm_dfp import CvmDfpParser
    from rusterm.pipeline import apply_concept_map
    from rusterm.providers.base import ProviderError as _PE
    from rusterm.providers.budget import BudgetExceeded, ConfigError
    from rusterm.providers.cvm import DFP_URL, DatasetState
    from rusterm.store.repos import persist_ingestion_results

    instrument = repos.instrument.get_instrument(instrument_id)
    issuer = repos.instrument.get_issuer(instrument.issuer_id) \
        if instrument else None
    if issuer is None or not (issuer.registry_id or "").isdigit():
        print(f"у эмитента {issuer_id!r} нет кода CD_CVM — выполните "
              f"rusterm add --ticker ... --market BR", file=sys.stderr)
        return 1
    gate = RequestGate()
    provider = get_provider("cvm", gate=gate)
    if isinstance(provider, ConfigError):
        print(f"cvm-провайдер недоступен: {provider.reason}",
              file=sys.stderr)
        return 1

    year = int(as_of[:4]) - 1
    url = DFP_URL.format(year=year)
    state_row = repos.issuer_state.get(issuer_id, source="cvm")
    known = state_row.get("last_modified") if state_row else None

    head = provider.dataset_state(url)
    if isinstance(head, _PE) and head.reason.startswith("cvm_not_found"):
        repos.coverage.upsert(instrument_id, "fundamentals", "missing",
                              reason=head.reason)
        print(f"{instrument_id}: набора DFP {year} нет у источника "
              f"({head.reason}) — покрытие missing")
        _record_cvm_budget(repos, gate)
        return 0
    if isinstance(head, (ConfigError, BudgetExceeded, _PE)):
        reason = getattr(head, "reason", "budget_exceeded")
        print(f"cvm недоступен: {reason}", file=sys.stderr)
        _record_cvm_budget(repos, gate)
        return 1
    if known is not None and head.last_modified == known:
        print(f"{instrument_id}: набор DFP {year} не изменился — "
              f"пропущено (HEAD, GET не выполнялся)")
        _record_cvm_budget(repos, gate)
        return 0

    outcome = provider.dataset_if_changed(url, None)
    _record_cvm_budget(repos, gate)
    if isinstance(outcome, DatasetState):
        # набор изменился между HEAD и GET-решением: честный пропуск,
        # следующий прогон сравнит метку заново
        print(f"{instrument_id}: набор DFP {year} изменился в ходе "
              f"прогона — пропущено")
        return 0
    if isinstance(outcome, (ConfigError, BudgetExceeded, _PE)):
        print(f"cvm недоступен: {outcome.reason}", file=sys.stderr)
        return 1
    raw = outcome

    sha = hashlib.sha256(raw).hexdigest()
    if repos.raw.has(sha):
        repos.issuer_state.put(issuer_id, last_filing_date=None,
                               last_modified=head.last_modified,
                               source="cvm")
        print(f"{instrument_id}: набор DFP уже в store — пропущено")
        return 0
    obj = repos.raw.put(raw, provider="cvm", block="fundamentals",
                        url=url, instrument_id=instrument_id)

    members = provider.dfp_members(raw)
    dre_member = next((n for n in members if "_DRE_con_" in n), None)
    bpp_member = next((n for n in members if "_BPP_con_" in n), None)
    if dre_member is None or bpp_member is None:
        repos.coverage.upsert(instrument_id, "fundamentals", "missing",
                              reason="cvm_no_consolidated_members")
        print(f"{instrument_id}: в наборе нет консолидированных "
              f"DRE/BPP — покрытие missing")
        return 0

    parser = CvmDfpParser()
    fact_dicts: list[dict] = []
    unmapped = 0
    unparsed = 0
    for member, statement in ((dre_member, "DRE"),
                              (bpp_member, "BPP")):
        rows = provider.rows_for(members[member],
                                 str(issuer.registry_id))
        facts, skipped = parser.parse_rows(
            rows, statement,
            {"issuer_id": issuer_id, "source_ref": obj.sha256,
             "csv_member": member})
        unparsed += skipped
        for fact in facts:
            fact = dict(fact)
            fact["fact_id"] = str(_uuid.uuid4())
            unmapped += apply_concept_map(fact)
            fact_dicts.append(fact)
    persist_ingestion_results(repos.conn, fact_dicts, [])
    repos.coverage.upsert(instrument_id, "fundamentals", "ready")
    repos.issuer_state.put(issuer_id, last_filing_date=None,
                           last_modified=head.last_modified,
                           source="cvm")
    print(f"{instrument_id}: DFP {year} загружен; фактов: "
          f"{len(fact_dicts)}; неразобрано: {unparsed}; "
          f"неотображённых концептов: {unmapped}")
    return 0


def _ingest_edgar_ownership(repos, instrument_id: str, issuer_id: str,
                            as_of: str, limit_per_form: int = 2,
                            provider=None) -> int:
    """Владение: Forms 3/4/5 -> document + raw (ТЗ-32 D2, ТЗ-25 P4).

    Метаданные — из уже загруженного submissions (ноль запросов);
    тела сырых XML тянутся с Archives по одному, sha256-идемпотентно.
    Эмитент без форм владения получает coverage missing с именованной
    причиной (D3) — пустой успех запрещён. Разбор сделок —
    rusterm.parsers.ownership.parse_form4, чистый по записанному
    сырью; хранение сделок — P5, здесь только сбор с провенансом."""
    import hashlib as _hashlib
    import xml.etree.ElementTree as _ET

    from rusterm.parsers.ownership import parse_form4
    from rusterm.providers.base import ProviderError as _PE
    from rusterm.providers.budget import ConfigError, RequestGate

    instrument = repos.instrument.get_instrument(instrument_id)
    issuer = repos.instrument.get_issuer(instrument.issuer_id) \
        if instrument else None
    if issuer is None or not (issuer.registry_id or "").isdigit():
        print(f"у эмитента {issuer_id!r} нет CIK — выполните "
              f"rusterm add --ticker ... --market ...", file=sys.stderr)
        return 1
    if provider is None:
        ownership_gate = RequestGate()
        provider = get_provider("edgar", gate=ownership_gate)
    else:
        ownership_gate = None
    if isinstance(provider, ConfigError):
        print(f"edgar-провайдер недоступен: {provider.reason}",
              file=sys.stderr)
        return 1
    provider.cik = int(issuer.registry_id)

    listed = provider.list_ownership(instrument_id,
                                     limit_per_form=limit_per_form)
    _record_gate_usage(repos, "edgar", ownership_gate)
    if isinstance(listed, _PE):
        print(f"edgar: {listed.reason}", file=sys.stderr)
        repos.coverage.upsert(instrument_id, "ownership", "missing",
                              reason=listed.reason)
        return 1
    if not listed.documents:
        # D3: отказ — не пустой успех
        reason = "source_has_no_disclosure"
        repos.coverage.upsert(instrument_id, "ownership", "missing",
                              reason=reason)
        print(f"{instrument_id}: форм владения 3/4/5 в ленте нет — "
              f"покрытие missing: {reason}")
        return 0

    newest = listed.documents  # лимит уже по видам в list_ownership
    collected = 0
    transactions = 0
    for meta in newest:
        url = provider.raw_document_url(meta.url)
        # кеш по каноническому URL без ключа (ADR-0003, как у котировок):
        # тело уже в сырьё-хранилище — ноль запросов на повторе
        cached_sha = repos.raw.find_by_provider_url("edgar", url)
        if cached_sha is not None:
            raw = repos.raw.get(cached_sha)
            sha = cached_sha
        else:
            fetched = provider.fetch_document(url)
            if isinstance(fetched, _PE):
                print(f"edgar: {fetched.reason}", file=sys.stderr)
                return 1
            raw = fetched.content
            sha = _hashlib.sha256(raw).hexdigest()
            repos.raw.put(raw, provider="edgar", block="ownership",
                          url=url, instrument_id=instrument_id)
            filename = url.rsplit("/", 1)[-1]
            repos.document.put(sha, filename=filename, format="xml",
                               page_count=1, byte_len=len(raw),
                               issuer_id=issuer.issuer_id)
            collected += 1
        try:
            filing = parse_form4(raw)
        except (_ET.ParseError, ValueError) as e:
            print(f"edgar: {filename}: неразобрано: {e}",
                  file=sys.stderr)
            return 1
        # сделки хранятся (миграция 44): вход insider_net считался бы
        # из сохранённого, а не пересобирался из воздуха (ТЗ-33 E1)
        repos.ownership.replace_for_document(sha, issuer.issuer_id,
                                             filing.transactions)
        transactions += len(filing.transactions)
    repos.coverage.upsert(instrument_id, "ownership", "ready")
    print(f"{instrument_id}: форм владения в ленте "
          f"{len(listed.documents)}; собрано документов {collected} "
          f"(по {limit_per_form} свежих на вид); сделок разобрано: "
          f"{transactions}")
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

    from rusterm.core.industry.inputs import industry_metrics_for
    from rusterm.core.governance import (governance_inputs_from_records,
                                         insider_net_inputs_from_store,
                                         produce_assessments)
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price,
                              corp_action_repo=repos.corp_action,
                              industry=lambda iid, _issuer:
                                  industry_metrics_for(repos, iid),
                              governance=lambda iid, issuer:
                                  produce_assessments(
                                      repos.governance, iid,
                                      args_as_of_default(),
                                      {**governance_inputs_from_records(
                                          repos.manual_extraction,
                                          issuer),
                                       **insider_net_inputs_from_store(
                                           repos, iid, issuer,
                                           args_as_of_default())}))
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
    from rusterm.core.industry.inputs import industry_metrics_for
    from rusterm.core.governance import (governance_inputs_from_records,
                                         insider_net_inputs_from_store,
                                         produce_assessments)
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price,
                              corp_action_repo=repos.corp_action,
                              industry=lambda iid, _issuer:
                                  industry_metrics_for(repos, iid),
                              governance=lambda iid, issuer:
                                  produce_assessments(
                                      repos.governance, iid,
                                      args_as_of_default(),
                                      {**governance_inputs_from_records(
                                          repos.manual_extraction,
                                          issuer),
                                       **insider_net_inputs_from_store(
                                           repos, iid, issuer,
                                           args_as_of_default())}))
    as_of = args.as_of or args_as_of_default()
    for instrument_id, issuer_id in targets:
        result = builder.build(instrument_id, issuer_id, as_of)
        print(f"{instrument_id}: снапшот v{result.version}: "
              f"{result.snapshot_id}")
        # ТЗ-64 J5: вторая сборка на тех же входах честно говорит
        # «без изменений» (версия создаётся — append-only хранилище)
        prev_id = repos.snapshot.previous_snapshot(instrument_id)
        if prev_id is not None and snapshot_measures_identical(
                repos.snapshot.get_measures(result.snapshot_id),
                repos.snapshot.get_measures(prev_id)):
            print(f"{instrument_id}: без изменений — значения "
                  f"идентичны предыдущей версии")
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
    if getattr(args, "chat", None):
        # ТЗ-36 H2: расшифровка разговора экспортируется как данные
        repos = RepoRegistry(conn, paths)
        transcript = repos.chat_transcript.get(args.chat)
        if transcript is None:
            print(f"расшифровки {args.chat!r} нет", file=sys.stderr)
            conn.close()
            return 1
        print(json.dumps(transcript, ensure_ascii=False, indent=1))
        conn.close()
        return 0
    repo = SnapshotRepo(conn)
    if not args.instrument:
        print("укажите --instrument ИНСТРУМЕНТ или --chat SESSION_ID",
              file=sys.stderr)
        conn.close()
        return 1
    snapshot_id = repo.latest_snapshot_id(args.instrument)
    if snapshot_id is None:
        print(f"для {args.instrument!r} снапшотов нет — сначала "
              "rusterm snapshot --instrument "
              f"{args.instrument}", file=sys.stderr)
        conn.close()
        return 1
    snapshot = repo.get_snapshot(snapshot_id)
    measures = repo.get_measures(snapshot_id)
    # ТЗ-72 S5: источник почти ничего не даёт — слова для человека,
    # таблица не пересобирается и машину не ломает (stderr)
    from rusterm.tui import model as tui_model
    summary = tui_model.measure_summary([(m[4], m[10]) for m in measures])
    if summary:
        print(tui_model.measure_summary_line(summary), file=sys.stderr)
    if args.format == "json":
        # ТЗ-22 J1: каждая абсолютная мера несёт валюту, в которой
        # заявлена, или строку отказа с перечнем
        currencies = {m[0]: repo.measure_currency(m[0], m[3])
                      for m in measures}
    else:
        currencies = None
    # ТЗ-64 J2: происхождение едет в экспорт тем же путём по lineage,
    # что у десктопного экспорта (одна реализация — core/export)
    from rusterm.core.export import lineage_facts
    from rusterm.store.repos import FactRepo
    repos = RepoRegistry(conn, paths)
    lineage = lineage_facts(repos, measures)
    if args.format == "md":
        from rusterm.core.export import refusal_advice
        sources = [f"- {m[3]}: "
                   f"{format_source_cell(lineage.get(m[0], [])) or 'входов нет'}"
                   for m in measures]
        lines = snapshot_to_md(measures).splitlines()
        advised = []
        for line in lines:
            advised.append(line)
            if line.startswith("- [") and ": " in line:
                token = line.rsplit(": ", 1)[1].split(":", 1)[0].strip()
                advice = refusal_advice(token, args.instrument)
                if advice:
                    advised.append(f"  что делать: {advice}")
        text = ("\n".join(advised) + "\nИсточники:\n"
                + "\n".join(sources) + "\n")
    elif args.format == "json":
        text = snapshot_to_json(snapshot, measures, provenance=lineage,
                                currencies=currencies)
    else:
        text = snapshot_to_csv(measures)
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
    from rusterm.core.industry.inputs import industry_metrics_for
    from rusterm.core.governance import (governance_inputs_from_records,
                                         insider_net_inputs_from_store,
                                         produce_assessments)
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price,
                              corp_action_repo=repos.corp_action,
                              industry=lambda iid, _issuer:
                                  industry_metrics_for(repos, iid),
                              governance=lambda iid, issuer:
                                  produce_assessments(
                                      repos.governance, iid,
                                      args_as_of_default(),
                                      {**governance_inputs_from_records(
                                          repos.manual_extraction,
                                          issuer),
                                       **insider_net_inputs_from_store(
                                           repos, iid, issuer,
                                           args_as_of_default())}))
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


from rusterm.core.llm import make_intent_client  # noqa: E402


def cmd_ops(args) -> int:
    """Массовая операция под подтверждением (TASK-16 D7/D8,
    docs/watchlist-and-llm.md §2–3): без --confirm — dry-run с пометкой
    по каждой позиции и без единой записи; с --confirm — применение
    одной транзакцией. Аудит: строка на исход (applied / refused /
    clarification); dry-run строк не пишет (D4). Ключ модели tonight
    есть — API-клиент, нет — детерминированный RuleClient; выбор
    только через make_intent_client (ТЗ-27 N1, единственная дверь)."""
    from rusterm.core.intent import Clarification, classify
    make_intent_client = globals().get("make_intent_client")
    from rusterm.core.ops import Refused, apply, prepare

    paths, conn = _open(args.root)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    import os as _os
    decision = classify(make_intent_client(_os.environ), args.request)
    outcome, rows, version = "clarification", [], None
    intent_name = getattr(decision, "name", None)
    as_of = args_as_of_default()

    if isinstance(decision, Clarification):
        reason = decision.reason
    else:
        prepared = prepare(repos, args.watchlist, decision, as_of)
        if isinstance(prepared, Clarification):
            reason = prepared.reason
        elif isinstance(prepared, Refused):
            # отказ — исход, а не сухой показ: строка аудита обязана
            # остаться и без подтверждения («мы этого не делали» —
            # доказуемая часть, §3.5)
            outcome, reason, rows = "refused", prepared.reason, []
        else:
            rows = prepared.rows
            outcome = "dry-run"
            reason = None
            if args.confirm:
                result_apply = apply(repos.watchlist, args.watchlist,
                                     prepared.addable)
                if result_apply["applied"]:
                    outcome = "applied"
                    version = result_apply["version"]
                    reason = None
                else:
                    outcome, reason = "refused", result_apply["reason"]

    if outcome != "dry-run":
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        payload = {"intent": intent_name, "counts": counts,
                   "decision": outcome}
        file_error = repos.audit.log(
            "ops", args.watchlist, payload,
            confirmed=bool(args.confirm), result=outcome)
        if file_error:
            print(file_error, file=sys.stderr)
    conn.close()

    if args.json:
        print(json.dumps({
            "watchlist_id": args.watchlist,
            "intent": intent_name,
            "outcome": outcome,
            # причина отказа не зависит от формата вывода: в
            # человеческом выводе она печаталась, в машинном терялась
            "reason": reason,
            "rows": rows,
            "version": version,
        }, ensure_ascii=False))
        exit_code = 0 if outcome in ("applied", "dry-run") else 1
        return exit_code
    for r in rows:
        line = f"  {r['ticker']}: {r['status']}"
        if r.get("reason"):
            line += f" — {r['reason']}"
        print(line)
    if outcome == "dry-run":
        print(f"сухой прогон: {len(rows)} позиций; примените с --confirm")
        return 0
    if outcome == "applied":
        print(f"применено: версия {version}")
        return 0
    print(f"{outcome}: {reason}", file=sys.stderr)
    return 1


def cmd_industry(args) -> int:
    """Агрегат по сектору на дату (TASK-17 E5/E6, веха M7).
    --as-of выбирает версию peer set и снапшоты участников по дате;
    каждая строка несёт n и счётчики причин — агрегат не прячет, сколько
    участников за числом. Хранится в industry_aggregate (миграция 39)."""
    paths, conn = _open(args.root)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    as_of = args.as_of or args_as_of_default()

    if repos.peer_set.version_at(args.sector, as_of) is None:
        exists = repos.peer_set.exists(args.sector)
        if exists:
            reason = f"у сектора {args.sector!r} нет версии на {as_of}"
        else:
            known = repos.peer_set.all_ids()
            have = ("известные секторы: " + ", ".join(known)
                    if known else "в базе нет ни одного сектора — "
                    "секторы появляются вместе с наборами (ADR-0015)")
            reason = f"сектор {args.sector!r} не найден; {have}"
        print(reason, file=sys.stderr)
        if args.json:
            print(json.dumps({"sector": args.sector, "as_of": as_of,
                              "verified": None, "aggregates": []},
                             ensure_ascii=False))
        conn.close()
        return 1

    built = build_sector_aggregates(repos, args.sector, as_of,
                                    ("net_margin", "operating_margin",
                                     "roe", "asset_turnover"))
    conn.close()
    if not built["verified"]:
        print(f"peer set сектора {args.sector!r} не подтверждён "
              f"(unverified)", file=sys.stderr)
        if args.json:
            print(json.dumps({
                "sector": args.sector, "as_of": as_of, "verified": False,
                "aggregates": [{"concept": a.concept, "p25": a.p25,
                                "median": a.median, "p75": a.p75, "n": a.n,
                                "null_reason": a.null_reason,
                                "reason_counts": a.reason_counts}
                               for a in built["aggregates"]]},
                ensure_ascii=False))
        return 1

    # сборка сохраняется: append-only, повтор той же (версия, дата)
    # обновляет строку, не плодя дублей (миграция 39)
    paths2, conn2 = _open(args.root)
    repos2 = RepoRegistry(conn2, paths2)
    repos2.industry.store_aggregates(
        built["peer_set_version_id"], as_of, built["aggregates"])
    conn2.close()

    if args.json:
        print(json.dumps({
            "sector": args.sector, "as_of": as_of,
            "verified": built["verified"],
            "aggregates": [{"concept": a.concept, "p25": a.p25,
                            "median": a.median, "p75": a.p75, "n": a.n,
                            "null_reason": a.null_reason,
                            "reason_counts": a.reason_counts}
                           for a in built["aggregates"]],
        }, ensure_ascii=False))
        return 0
    print(f"сектор {args.sector}: версия {built['version']} на {as_of} "
          f"(участников {len(built['members'])})")
    for a in built["aggregates"]:
        if a.null_reason:
            counts = ("; ".join(f"{k}={v}"
                                for k, v in sorted(a.reason_counts.items()))
                      ) or "нет причин"
            print(f"  {a.concept}: {a.null_reason} ({counts})")
        else:
            counts = "; ".join(f"{k}={v}"
                               for k, v in sorted(a.reason_counts.items()))
            suffix = f"; {counts}" if counts else ""
            print(f"  {a.concept}: {a.p25} / {a.median} / {a.p75} "
                  f"(n={a.n}{suffix})")
    return 0


def cmd_status(args) -> int:
    """«Что у меня есть»: каталог, схема, инструменты, снапшоты,
    покрытие, сеть, окружение (TASK-8 U9). --json — один объект."""
    from rusterm import env as env_module
    # B40: status отвечает «что есть» — отсутствующий каталог данных
    # он называет по имени, а не создаёт пустой
    paths, conn = _open_readonly(args.root)
    if conn is None:
        message = (f"каталога данных нет: {args.root}; выполните "
                   "rusterm init")
        if getattr(args, "json", False):
            print(json.dumps({"error": "no_data_dir", "data_dir":
                              str(AppPaths.from_root(args.root).root)},
                             ensure_ascii=False))
        else:
            print(message, file=sys.stderr)
        return 1
    # BACKLOG B25: версия «как застали» снимается ДО тихой миграции —
    # база, отставшая от кода, видна в status, а не только в doctor
    observed = current_schema_version(conn)
    apply_migrations(conn)  # идемпотентно; свежая база получает схему
    repos = RepoRegistry(conn, paths)
    applied = current_schema_version(conn)
    budget_samples = {s[1]: s[3] for s in repos.metrics.samples()
                      if s[1].startswith("provider_")}
    requests_used = int(sum(
        float(s[3]) for s in repos.metrics.samples()
        if s[1] == "provider_requests_used"))
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
        "concept_map_version_ifrs": CONCEPT_MAP_VERSION_IFRS,
        "market_codes": list(MARKET_CODES),
        # ТЗ-22 J2: состав каждого набора — рынки, валюты, mixed/нет
        "peer_sets": repos.peer_set.latest_compositions(),
        "budget": {
            "ceiling_per_night": 5000,
            "rate_per_second": 5,
            "provider_ran": bool(budget_samples),
            "used": requests_used,
            "samples": budget_samples,
        },
        "env": env_module.report(),
        # ТЗ-36 H3: стоимость разговора видна до счёта — вызовы по
        # моделям из расшифровок
        "chat": repos.chat_transcript.calls_totals(),
    }
    conn.close()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    # ТЗ-90 A5: путь называется вместе с правилом, по которому его
    # выбрали, — «открылась не та база» отличается от «тут нет данных»
    # строкой, а не догадкой
    print(f"каталог данных: {payload['data_dir']} "
          f"(правило: {args.root_rule})")
    if observed is not None and applied != observed:
        print(f"схема: найдена версия {observed}, обновлена до {applied}")
    print(f"схема: {('версия ' + str(applied)) if applied else 'нет базы (rusterm init)'}")
    print(f"инструментов: {payload['instruments']}; списков наблюдения: {payload['watchlists']}")
    for p in payload["peer_sets"]:
        print(f"peer set {p['peer_set_id']} v{p['version']}: {p['scope']}"
              f"; рынки: {','.join(p['markets']) or '—'}"
              f"; валюты: {','.join(p['currencies']) or '—'}")
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


def cmd_desktop(args) -> int:
    """Десктопное окно (ТЗ-60 E3): та же дверь, что
    python3 -m rusterm.desktop, — один код, копии нет.

    Каталог выбирает `resolve_root` (ТЗ-90 A5), и окно делает то же
    самое: явно названный корень передаём дальше, а выбранный по
    правилам 2-4 не пересылаем — иначе вторая дверь посчитала бы его
    правилом 1 и шапка окна наврала бы пользователю. Отказ без PySide6
    словами даёт сам window.run — общего кода меньше, а слова не
    расходятся между точками входа.
    """
    from rusterm.desktop.__main__ import main as desktop_main
    argv = []
    if getattr(args, "root_rule", 1) == 1:
        argv += ["--root", str(args.root)]
    if getattr(args, "watchlist", None):
        argv += ["--watchlist", args.watchlist]
    return desktop_main(argv)


def cmd_add(args) -> int:
    """Создать эмитента + инструмент + листинг + историю тикера
    (TASK-9 V3). Идемпотентно: повтор — «уже есть», код 0. Онлайн
    (есть контакт SEC) --cik/--name берутся из карты тикеров EDGAR;
    офлайн оба обязательны."""
    # TASK-18 G1: --market валидируется реестром до всякой базы;
    # опечатка не должна становиться эмитентом с чужой юрисдикцией
    from rusterm.markets import get_market, known_codes
    market_row = get_market(args.market)
    if market_row is None:
        print(f"неизвестный рынок {args.market!r}; известные коды: "
              f"{known_codes()}", file=sys.stderr)
        return 1
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
    from rusterm.providers import UnknownProvider
    cik, name = args.cik, args.name
    provider = None
    add_gate = None
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
        # а не провайдера, если гейт не передан (TASK-10 W0).
        # Провайдер — по строке реестра рынка (ADR-0010 §1), а не
        # захардкоженный edgar: у KR/BR/AU он свой (TASK-19 F3).
        add_gate = RequestGate()
        provider = get_provider(market_row.provider, gate=add_gate)
        if isinstance(provider, (ConfigError, UnknownProvider)):
            reason = (provider.reason if isinstance(provider, ConfigError)
                      else f"provider_not_implemented:{provider.name}")
            print(f"провайдер рынка {args.market} недоступен: {reason}",
                  file=sys.stderr)
            conn.close()
            return 1
        resolution = provider.resolve(args.ticker, args.market,
                                      args_as_of_default())
        if isinstance(resolution, _PE):
            # ТЗ-64 J1: расход пишется на выходе команды, а не сразу за
            # resolve — после него add тянет ещё и площадку, и этот
            # запрос терялся из budget.
            _record_gate_usage(repos, market_row.provider, add_gate)
            print(f"тикер {args.ticker!r} не найден в EDGAR: "
                  f"{resolution.reason}", file=sys.stderr)
            conn.close()
            return 1
        cik = cik if cik is not None else resolution["cik"]
        name = name or resolution.get("title") or args.ticker.upper()

    if instruments.get_instrument(instrument_id) is not None:
        _record_gate_usage(repos, market_row.provider, add_gate)
        print(f"инструмент {instrument_id} уже существует")
        conn.close()
        return 0

    # TASK-19 F3 (ADR-0010 §3): провайдер рынка отвечает «забирается ли
    # эмитент автоматически» ДО создания. Пустых эмитентов программа не
    # делает молча; предложение ручного импорта — единственный совет
    # действия в программе.
    if provider is not None:
        answer = provider.can_auto_ingest(args.ticker.upper())
        if isinstance(answer, _PE):
            if answer.reason.split(":", 1)[0] == "unknown_issuer":
                print(f"рынок {args.market} не знает тикер "
                      f"{args.ticker.upper()!r} (unknown_issuer)",
                      file=sys.stderr)
            else:
                print(f"провайдер {market_row.provider} не ответил о "
                      f"доступности эмитента: {answer.reason}",
                      file=sys.stderr)
            _record_gate_usage(repos, market_row.provider, add_gate)
            conn.close()
            return 1
        if answer is not True:
            _record_gate_usage(repos, market_row.provider, add_gate)
            print(f"{args.ticker.upper()} на {args.market}: раскрытия "
                  f"эмитента недоступны машинно (manual_import_required); "
                  f"эмитент не создан")
            print(f"добавьте отчёты вручную: rusterm import <файл> "
                  f"--issuer {args.ticker.upper()} "
                  f"--market {args.market}")
            conn.close()
            return 0

    # TASK-18 G2: площадка — из собственного файла SEC, а не догадка
    # вызывающего; тикера нет в файле — venue unknown, без исключения
    venue = "unknown"
    if provider is not None:
        venues = provider.ticker_venues()
        if not isinstance(venues, (ConfigError, _PE)):
            venue = venues.get(args.ticker.upper(), "unknown")

    issuer_id = f"cik-{cik}"
    instruments.upsert_issuer(Issuer(
        issuer_id, name, market_row.jurisdiction, str(cik),
        args.fye, "us_gaap", "USD"))
    instruments.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, args.class_, "active", None))
    listing_id = f"{instrument_id}-listing"
    instruments.upsert_listing(Listing(
        listing_id, instrument_id, venue, "USD", 1, None, None))
    instruments.add_ticker_history(listing_id, args.ticker.upper(),
                                   args_as_of_default(), None, None, None)
    repos.audit.log("add", instrument_id,
                    {"ticker": args.ticker.upper(), "market": args.market,
                     "cik": cik}, True, "ok")
    print(f"создан инструмент {instrument_id} "
          f"(эмитент {name}, CIK {cik}, тикер {args.ticker.upper()} "
          f"на {args.market}, площадка {venue})")
    _record_gate_usage(repos, market_row.provider, add_gate)
    conn.close()
    return 0


def cmd_reparse(args) -> int:
    """Заново разобрать сохранённые companyfacts нынешним разборщиком и
    выровнять basis фактов (регрессия ТЗ-78 Y2: дата обложки dei делала
    каждый факт restated). Сеть не нужна; меняется только basis. После
    — пересчитайте снапшоты: rusterm snapshot --watchlist <id>."""
    from rusterm.core.reparse import rebasis_companyfacts

    paths, conn = _open(args.root)
    repos = RepoRegistry(conn, paths)
    res = rebasis_companyfacts(repos)
    print(f"повторный разбор companyfacts: объектов {res.objects}, "
          f"фактов сверено {res.facts_checked}")
    print(f"basis исправлен у {res.changed}: в as_reported "
          f"{res.to_as_reported}, в restated {res.to_restated}; "
          f"не найдено среди сохранённых {res.unmatched}")
    for line in res.unreadable:
        print(f"не прочитан сырой объект: {line}")
    if res.changed:
        print("дальше: пересчитайте снапшоты — rusterm snapshot "
              "--watchlist <id> (или --ticker T --market M)")
    return 0 if not res.unreadable else 1


def cmd_cadence(args) -> int:
    """Кадентность котировок — на поверхность (ТЗ-31 C5, ruling
    REPORT-30 Q1: «да, команда»). По каждому инструменту: состояние
    (incomplete/complete), последняя сохранённая дата, число дыр,
    срок следующего опроса. Правило обхода перестаёт быть
    непрозрачным: пользователь видит, что сделает следующий проход и
    сколько он стоит против дневного потолка вендора."""
    from rusterm.core import cadence
    from rusterm.providers import host_limit

    # B40: каденция — планирование, только чтение; каталог не создаётся
    paths, conn = _open_readonly(args.root)
    if conn is None:
        print("каденция: каталога данных нет — нечего планировать; "
              "начните с rusterm init")
        return 0
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    as_of = args.as_of or args_as_of_default()
    plan = cadence.plan_pass(repos, as_of)
    rows = []
    for entry in plan:
        hole_count = len(cadence.gaps(
            repos.price.dates(entry.instrument_id)))
        last_poll = repos.job.last_poll_date(entry.instrument_id,
                                             "prices")
        rows.append({
            "instrument_id": entry.instrument_id,
            "state": entry.state,
            "action": entry.action,
            "reason": entry.reason,
            "gaps": hole_count,
            "last_date": entry.last_date,
            "next_poll_due": cadence.next_poll_due(
                last_poll, entry.last_date, as_of, entry.state),
        })
    incomplete = sum(1 for r in rows if r["state"] == "incomplete")
    next_pass_requests = sum(1 for e in plan if e.action != "skip")
    limit = host_limit("twelvedata")
    ceiling = limit.nightly_max if limit is not None else None
    if conn is not None:
        conn.close()
    if args.json:
        print(json.dumps({
            "as_of": as_of,
            "instruments": rows,
            "incomplete": incomplete,
            "next_pass_requests": next_pass_requests,
            "daily_ceiling": ceiling,
        }, ensure_ascii=False))
        return 0
    print(f"каденция на {as_of}: инструментов {len(rows)}; неполных "
          f"{incomplete}; следующий проход ≈ {next_pass_requests} "
          f"запросов из {ceiling}/день")
    for r in rows:
        print(f"  {r['instrument_id']}: {r['state']}; дыр "
              f"{r['gaps']}; последняя дата "
              f"{r['last_date'] or '—'}; опрос к "
              f"{r['next_poll_due']}; ({r['action']}: {r['reason']})")
    return 0


def cmd_census(args) -> int:
    """Перепись отказов (ТЗ-49 R1): мера × значение × причина по
    последнему снапшоту инструмента — десять строк, у отказа причина
    из rusterm/reasons.py с продолжением, называющим конкретный
    отсутствующий концепт или период. Никакого ремонта: только
    измерение; вход для решений о покрытии."""
    from rusterm.core.snapshot import SnapshotBuilder

    # ТЗ-58 C3 (расхождение A3): перепись читает меры; пересборка
    # (--rebuild или нет снапшота) пишется в СУЩЕСТВУЮЩИЙ каталог —
    # отсутствующий называется по имени, а не создаётся
    paths, conn = _open_readonly(args.root)
    if conn is None:
        print(f"переписи нет — каталога данных нет: {args.root}; "
              f"выполните rusterm init", file=sys.stderr)
        return 1
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    instrument = repos.instrument.get_instrument(args.instrument)
    if instrument is None:
        print(f"census: инструмента нет в базе: {args.instrument}",
              file=sys.stderr)
        conn.close()
        return 1
    as_of = args.as_of or args_as_of_default()
    if args.rebuild or repos.snapshot.latest_snapshot_id(
            instrument.instrument_id) is None:
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build(instrument.instrument_id, instrument.issuer_id, as_of)
    sid = repos.snapshot.latest_snapshot_id(instrument.instrument_id)
    rows = [{"measure": m[3], "value": m[4], "reason": m[10]}
            for m in repos.snapshot.get_measures(sid)]
    conn.close()
    if args.json:
        print(json.dumps({"instrument_id": instrument.instrument_id,
                          "snapshot_id": sid, "measures": rows},
                         ensure_ascii=False))
        return 0
    print(f"перепись отказов {instrument.instrument_id} (снапшот {sid}):")
    for r in rows:
        cell = r["value"] if r["value"] is not None \
            else f"отказ ({r['reason']})"
        print(f"  {r['measure']:18s} {cell}")
    return 0


def _instrument_exists(root: str, instrument_id: str) -> bool:
    """Есть ли инструмент в базе — чтение, каталог не создаётся."""
    paths, conn = _open_readonly(root)
    if conn is None:
        return False
    try:
        return RepoRegistry(conn, paths).instrument.get_instrument(
            instrument_id) is not None
    finally:
        conn.close()


def _requests_used(root: str) -> int:
    """Сумма всех проб запросов в базе — та же арифметика, что у
    `rusterm budget` (ТЗ-64 J1): слагать надо `provider_requests_used`,
    а не помнить про прошлый вызов. Каталог не создаётся (B35): базы
    нет — ноль."""
    paths, conn = _open_readonly(root)
    if conn is None:
        return 0
    try:
        repos = RepoRegistry(conn, paths)
        return sum(int(float(row[3])) for row in repos.metrics.samples()
                   if row[1] == "provider_requests_used")
    finally:
        conn.close()


def cmd_follow(args) -> int:
    """ТЗ-96 R2: один вызов проводит бумагу путь «пустой каталог →
    снапшот»: поиск в SEC, отчётность, цены, снапшот.

    Тела стадий не копируются: каждая стадия — тот же аргмент-вектор,
    что человек набрал бы сам, разобранный настоящим парсером и
    переданный настоящей команде (`add`/`ingest`/`snapshot`). Отсюда
    два обещания сразу: повтор стадии даёт ровно тот же вывод, что и
    та же команда в терминале, и строка совета, которая печатается при
    отказе, разбирается этим же парсером (есть тест).

    Двух открытых писателей одновременно это не делает: дочерняя
    команда сама открывает и закрывает базу, а `follow` соединения не
    держит вовсе — счётчик запросов читается коротким открытием до и
    после стадии (ТЗ-84 K2).

    Отрасль и governance в путь не входят — их собирает не эта
    команда; слова об этом печатаются в конце, а не оставляются
    пустотой.
    """
    from rusterm.markets import get_market

    market_row = get_market(args.market)
    if market_row is None:
        from rusterm.markets import known_codes
        print(f"неизвестный рынок {args.market!r}; известные коды: "
              f"{known_codes()}", file=sys.stderr)
        print("совет: rusterm markets", file=sys.stderr)
        return 1
    ticker = args.ticker.upper()
    instrument_id = f"{args.market}-{ticker}"
    commands = {"init": cmd_init, "add": cmd_add, "ingest": cmd_ingest,
                "snapshot": cmd_snapshot}

    stages = [
        ("1/5 каталог", ["init"]),
        ("2/5 поиск в SEC", ["add", "--ticker", ticker,
                             "--market", args.market]),
        ("3/5 отчётность", ["ingest", "--source", "edgar",
                            "--instrument", instrument_id]),
        ("4/5 цены", ["ingest", "--source", "twelvedata",
                      "--instrument", instrument_id]),
        ("5/5 снапшот", ["snapshot", "--instrument", instrument_id]),
    ]

    parser = _build_parser()
    spent_total = 0
    for name, argv in stages:
        if name.startswith("2/") and \
                _instrument_exists(args.root, instrument_id):
            print(f"{instrument_id}: {name} — инструмент уже есть, "
                  f"поиск пропущен (запросов 0)")
            continue
        before = _requests_used(args.root)
        child = parser.parse_args(["--root", str(args.root), *argv])
        rc = commands[child.command](child)
        spent = _requests_used(args.root) - before
        spent_total += spent
        print(f"{instrument_id}: {name} — "
              f"{'готово' if rc == 0 else 'отказ'} (запросов {spent})")
        if rc != 0:
            # Совет — та же стадия, одним вызовом: он обязан разбираться
            # парсером CLI, поэтому это строка команды, а не описание
            # проблемы. Причина отказа и что чинить — в выводе самой
            # стадии выше.
            print(f"{instrument_id}: стадия не прошла (код {rc}); "
                  f"починив, повторяют только её", file=sys.stderr)
            if name.startswith("2/"):
                print(f"без контакта SEC нужны оба значения вручную: "
                      f"--cik и --name (см. rusterm markets)",
                      file=sys.stderr)
            print(f"совет: rusterm {' '.join(argv)}", file=sys.stderr)
            return rc

    print(f"{instrument_id}: путь пройден; всего запросов: {spent_total}")
    print(f"{instrument_id}: отрасль и governance в этот путь не входят "
          f"— их собирает не эта команда (см. rusterm industry, "
          f"rusterm coverage)")
    return 0


def cmd_doctor(args) -> int:
    # ТЗ-58 C3 (расхождение A3): диагностика по умолчанию только
    # читает — absent-каталог не создаётся, а отсутствие базы есть
    # находка отчёта (schema_version=None; булавки закрепляют);
    # писать умеет лишь --fix, он и создаёт как прежде
    paths, conn = (_open(args.root)
                   if getattr(args, "fix", False)
                   else _open_readonly(args.root))
    # ТЗ-51 U2: путь «база старой версии → схема 45» идёт через тот же
    # apply_migrations, что и init, — но только с --fix. По умолчанию
    # doctor остаётся диагностикой (булавки набора закрепляют:
    # test_cli_doctor_detects_schema_gap и соседние ловят разрыв схемы
    # на НЕмигрирующем прогоне), база не меняется.
    schema_before = None
    migrations_now: list = []
    schema_after = None
    if getattr(args, "fix", False):
        from rusterm.store.db import apply_migrations as _apply_migrations, \
            current_schema_version as _schema_version
        schema_before = _schema_version(conn)
        migrations_now = _apply_migrations(conn)
        schema_after = _schema_version(conn)
    report = doctor_report(paths, conn)
    report["migrations_applied"] = {"before": schema_before,
                                    "applied": migrations_now,
                                    "after": schema_after}
    # B24: к счётчикам хостов из базы добавляются потолки из объявлений
    # реестра — used/ceiling видны рядом, без ручного свода
    from rusterm.providers import all_host_limits
    host_to_limit = {limit.host.lower(): limit
                     for limit in all_host_limits().values()}
    report["request_budget"] = {
        host: {"used": used,
               "ceiling": host_to_limit[host.lower()].nightly_max,
               "per_second": host_to_limit[host.lower()].per_second}
        if host.lower() in host_to_limit else {"used": used,
                                               "ceiling": None,
                                               "per_second": None}
        for host, used in report.get("request_budget", {}).items()}
    # ТЗ-28 R2: раздел «бесплатность» — по каждому каналу реестра: хост,
    # тариф, потолок (число вендора или «проектный потолок») и факт
    # наличия ключа. Значения ключей не печатаются никогда; отсутствие
    # ключа здесь не ошибка и код выхода не меняет.
    from rusterm import env as env_module
    from rusterm.providers import all_host_limits, channel_key_env, \
        channel_tier
    origins = env_module.report()["vars"]
    channels = {}
    for name, limit in sorted(all_host_limits().items()):
        key_env = channel_key_env(name)
        if key_env:
            present = "да" if origins.get(key_env, "—") != "—" else "нет"
        else:
            present = "—"
        channels[name] = {
            "host": limit.host,
            "tier": channel_tier(name),
            "per_second": limit.per_second,
            "nightly_max": limit.nightly_max,
            "ceiling_kind": ("проектный потолок"
                             if limit.nightly_max == 5000
                             else "тариф вендора"),
            "key_env": key_env or "—",
            "key_present": present,
        }
    report["free_channels"] = channels
    # ТЗ-31 C5: каденция видна доктору — сколько инструментов неполны
    # и сколько запросов стоит следующий проход против потолка вендора.
    # База может быть не инициализирована — раздел честно называет это.
    import sqlite3 as _sqlite3
    from rusterm.core import cadence as cadence_mod
    tw_limit = all_host_limits().get("twelvedata")
    ceiling = tw_limit.nightly_max if tw_limit else None
    repos = RepoRegistry(conn, paths) if conn is not None else None
    if repos is None:
        # ТЗ-58 C3: absent-каталог — находка отчёта, а не создание
        report["cadence"] = {
            "incomplete": None,
            "next_pass_requests": None,
            "daily_ceiling": ceiling,
            "reason": "no_data_dir",
        }
    else:
        try:
            plan = cadence_mod.plan_pass(repos, args_as_of_default())
            report["cadence"] = {
                "incomplete": sum(1 for e in plan
                                  if e.state == "incomplete"),
                "next_pass_requests": sum(1 for e in plan
                                          if e.action != "skip"),
                "daily_ceiling": ceiling,
            }
        except _sqlite3.DatabaseError:
            report["cadence"] = {
                "incomplete": None,
                "next_pass_requests": None,
                "daily_ceiling": ceiling,
                "reason": "schema_not_ready",
            }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if conn is not None:
        conn.close()
    return 0 if report["ok"] else 1


def cmd_backup(args) -> int:
    """Резервная копия (ТЗ-22 J4): база, манифесты и объекты raw-хранилища
    в один zip с MANIFEST.json (sha256 на члена, версия схемы)."""
    from rusterm.store.backup import BackupError, create_backup
    paths, conn = _open(args.root)
    conn.close()
    try:
        summary = create_backup(paths, args.archive)
    except BackupError as e:
        print(f"backup: {e.reason}", file=sys.stderr)
        return 1
    print(f"backup: {summary.archive}; членов: {summary.members}; "
          f"байт: {summary.bytes_total}; схема {summary.schema_version}")
    return 0


def cmd_restore(args) -> int:
    """Восстановление (ТЗ-22 J4): отказ при схеме новее кода, при
    несовпавшем хеше члена; непустой каталог — только с --force."""
    from rusterm.store.backup import BackupError, restore_backup
    target = AppPaths.from_root(args.root)
    try:
        result = restore_backup(args.archive, target, force=args.force)
    except BackupError as e:
        print(f"restore: {e.reason}", file=sys.stderr)
        return 1
    print(f"restore: {result['restored']} членов в {result['target']}; "
          f"схема {result['schema_version']}")
    return 0


def cmd_chat(args) -> int:
    """Чат с цитатами (ТЗ-26 Q1): вопрос -> read-only инструменты ->
    ответ, где каждое число доказуемо. Чат никогда не пишет.
    Без RUSTERM_LLM_API_KEY — внятное сообщение и код 1, не падение."""
    from rusterm.core.chat import ChatSession, save_transcript
    from rusterm.core.llm import make_chat_client
    from rusterm.providers.budget import ConfigError, RequestGate
    # ТЗ-90 A2: один гейт на сессию — та же дверь бюджета и темпа, что у
    # проверки доступности канала; раньше make_chat_client строил второй,
    # невидимый, и инъекции теста до него не долетали.
    gate = RequestGate()
    client = get_provider("llm-api", gate=gate)
    if isinstance(client, ConfigError):
        # ТЗ-28 R5: отказ называет бесплатный тариф и не предлагает
        # платного плана — платного в проекте нет (ADR-0018).
        print(f"chat: модель недоступна: {client.reason}; задайте "
              f"RUSTERM_LLM_API_KEY (ключ бесплатный — регистрация на "
              f"openrouter.ai без карты, ADR-0018)", file=sys.stderr)
        return 1
    paths, conn = _open(args.root)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    # Адаптер «complete -> chat» живёт за дверью make_chat_client, а не
    # локальным классом здесь: экран разговора звал ту же дверь и падал
    # AttributeError, потому что дверь отдавала клиента без chat
    # (находка координатора 17.09.2026).
    session = ChatSession(repos, make_chat_client(gate=gate),
                          max_total=args.max_calls)
    print("чат: пустая строка — выход; модель отвечает только "
          "цитированными числами")
    while True:
        try:
            question = input("вопрос> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            break
        result = session.ask(question)
        if result["rejected"]:
            print(f"[отказ: {result['reason']}]")
        else:
            print(result["answer"])
    print(f"вызовов модели/инструментов за сессию: {session.calls_made}")
    # ТЗ-36 H2: расшифровка — данные, переживает процесс
    session_id = f"chat-{int(time.time()*1000)}"
    save_transcript(repos, session, session_id,
                    instrument_id=args.instrument
                    if hasattr(args, "instrument") else None)
    print(f"расшифровка сохранена: {session_id}")
    conn.close()
    return 0


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
    # B40: покрытие — только чтение; каталог данных не создаётся
    paths, conn = _open_readonly(args.root)
    if conn is None:
        print("покрытия нет — каталога данных нет; начните с "
              "rusterm init и rusterm ingest", file=sys.stderr)
        return 1
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
        payload = {"target": target,
                   "concept_map_version": CONCEPT_MAP_VERSION,
                   "rows": rows}
        # ТЗ-22 J1: currency_mismatch считается отдельно от missing_data —
        # это разные проблемы, чинятся по-разному
        if args.watchlist is None:
            from rusterm.tui import model as tui_model
            snapshot_id = repos.snapshot.latest_snapshot_id(instrument)
            # ТЗ-61 F1: счётчик один на все лица — tui_model
            if snapshot_id:
                counts = tui_model.measure_reason_counts(repos, snapshot_id)
            else:
                counts = {}
            if counts:
                payload["measure_reason_counts"] = counts
        print(json.dumps(payload, ensure_ascii=False))
        conn.close()
        return 0
    for row in rows:
        reason = f" причина: {row['reason']}" if row["reason"] else ""
        print(f"{row['instrument_id']}\t{row['block']}\t"
              f"{row['status']}{reason}")
    conn.close()
    return 0


def cmd_metrics(args) -> int:
    # ТЗ-58 C3 (расхождение A3): метрика только читает; писать она
    # умеет лишь с --record — absent-каталог называется по имени, а
    # не создаётся
    if getattr(args, "record", False):
        paths, conn = _open(args.root)
    else:
        paths, conn = _open_readonly(args.root)
        if conn is None:
            print(f"метрик нет — каталога данных нет: {args.root}; "
                  f"выполните rusterm init", file=sys.stderr)
            return 1
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
    # B40: бюджет — только чтение; каталог данных не создаётся
    paths, conn = _open_readonly(args.root)
    if conn is None:
        payload = {"ceiling_per_night": 5000, "rate_per_second": 5,
                   "provider_ran": False, "used": 0, "refused": 0,
                   "samples": {}}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
            return 0
        print("потолок запросов за ночь: 5000 (Budget), 5 в секунду "
              "(RateLimiter); лимитеры не хранят состояние между процессами")
        print("сетевой провайдер не работал: использовано 0, отказано 0 "
              "(записей в metric_sample нет)")
        return 0
    repos = RepoRegistry(conn, paths)
    # ТЗ-64 J1: used — сумма ВСЕХ проб гейта (каждый сбор пишет свою),
    # не память; samples — последняя проба по имени (ТЗ-56/57 пин)
    used = 0
    last_probe = None
    samples: dict[str, float] = {}
    for s in repos.metrics.samples():
        if s[1].startswith("provider_"):
            samples[s[1]] = float(s[3])
        if s[1] == "provider_requests_used":
            used += int(float(s[3]))
            last_probe = float(s[3])
    payload = {
        "ceiling_per_night": 5000,
        "rate_per_second": 5,
        "provider_ran": bool(samples),
        "used": used,
        "used_total": used,
        "last_probe": last_probe,
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
        # ТЗ-65 K5: два счёта названы, чтобы не путались
        print(f"использовано запросов за жизнь каталога: {used}")
        print(f"последняя проба гейта: provider_requests_used = "
              f"{last_probe}")
        for host in sorted(h for h in samples if h != "provider_requests_used"):
            print(f"{host} = {samples[host]}")
    return 0


def _provider_status(provider: str) -> str:
    """Реализован ли модуль провайдера: importlib внутри вызова —
    та же дверь, что у мест (ТЗ-19 F5). Нет модуля — дословно
    provider_not_implemented, а не пустота (ТЗ-21 H1)."""
    try:
        importlib.import_module(f"rusterm.providers.{provider}")
    except ModuleNotFoundError as e:
        if e.name in (provider, f"rusterm.providers.{provider}"):
            return "provider_not_implemented"
        raise
    return "implemented"


def _issuer_count(conn, paths) -> str:
    """Эмитентов в локальной базе; схемы нет — честное «—». Сам
    запрос живёт в репозитории (приёмка, пункт 7: SQL только в слое
    хранилища). Базы нет вовсе (B35) — тоже «—», без её создания."""
    if conn is None:
        return "—"
    try:
        return str(RepoRegistry(conn, paths).instrument.issuer_count())
    except Exception:
        return "—"


def cmd_markets(args) -> int:
    """Реестр рынков как данные (BACKLOG B19; ТЗ-21 H1): коды,
    юрисдикции, провайдеры, уровни доступа, реализован ли провайдер и
    сколько эмитентов в локальной базе; --json для машинного
    потребления. Ответ на вопрос «достанет ли программа корейские
    данные?» — без чтения исходников."""
    from rusterm.markets import (MARKETS, channel_degree_label,
                                 provider_channel)
    from rusterm.providers import channel_key_env
    import os as _os
    # только чтение реестра: каталог данных не создаётся (B35)
    paths, conn = _open_readonly(args.root)
    # степень канала — из того, что канал произвёл в этой базе;
    # базы нет (B35) или схема не готова — честное «—» (ТЗ-60 E4)
    degrees = {}
    if conn is not None:
        try:
            degrees = RepoRegistry(conn, paths).instrument.channel_degrees()
        except Exception:
            degrees = {}
    rows = []
    for m in MARKETS:
        rows.append({"code": m.code, "jurisdiction": m.jurisdiction,
                     "venue_kind": m.venue_kind, "provider": m.provider,
                     "identifier": m.identifier,
                     "default_taxonomy": m.default_taxonomy,
                     "access": m.access,
                     "provider_status": _provider_status(m.provider),
                     "channel": provider_channel(m.provider),
                     "degree": channel_degree_label(
                         m.provider, degrees.get(m.code),
                         channel_key_env(m.provider),
                         bool(_os.environ.get(
                             channel_key_env(m.provider) or ""))),
                     "issuers": _issuer_count(conn, paths)})
    if conn is not None:
        conn.close()
    if args.json:
        print(json.dumps({"markets": rows}, ensure_ascii=False))
        return 0
    for row in rows:
        print(f"{row['code']}\t{row['jurisdiction']}\t"
              f"{row['venue_kind']}\t{row['provider']}\t"
              f"{row['identifier']}\t{row['default_taxonomy']}\t"
              f"{row['access']}\t{row['provider_status']}\t"
              f"{row['channel'] or '-'}\t{row['degree']}\t{row['issuers']}")
    return 0


def cmd_import(args) -> int:
    """Ручной импорт (ADR-0011 ①-③, ТЗ-20 L6): файл -> страницы ->
    записи (модель по API) -> детерминированный контроль -> факты.

    --dry-run — только ступень ①: исход печатается, ничего не пишется
    (B21). Ключа модели нет — команда останавливается после ① с
    внятным сообщением, ничего не записывая (ADR-0011 ②). Эмитент
    должен существовать: импорт не создаёт эмитентов (ADR-0011)."""
    from rusterm.manual.pipeline import import_document
    from rusterm.providers.base import ProviderError
    from rusterm.providers.budget import ConfigError, RequestGate
    from rusterm.providers.llm_api import LlmApiClient

    paths, conn = _open(args.root)
    if current_schema_version(conn) is None:
        print("база не создана; выполните rusterm init", file=sys.stderr)
        conn.close()
        return 1
    repos = RepoRegistry(conn, paths)
    instrument_id = (f"{args.market}-{args.issuer.upper()}"
                     if args.market else args.issuer.upper())
    instrument = repos.instrument.get_instrument(instrument_id)
    if instrument is None:
        print(f"инструмент {instrument_id!r} не найден; импорт не создаёт "
              f"эмитентов — сначала rusterm add (ТЗ-20 L6)",
              file=sys.stderr)
        conn.close()
        return 1

    client = LlmApiClient.from_env(gate=RequestGate())
    exit_code = 0
    near_miss_total = 0
    for path in args.path:
        outcome = import_document(conn, paths, path, instrument.issuer_id,
                                  client, dry_run=args.dry_run)
        if isinstance(outcome, ProviderError):
            print(f"{path}: {outcome.reason} (ТЗ-20 L6)", file=sys.stderr)
            exit_code = 1
            continue
        if not isinstance(outcome, (ProviderError, ConfigError)) \
                and getattr(outcome, "records_near_miss", 0):
            near_miss_total += outcome.records_near_miss
        if isinstance(outcome, ConfigError):
            print(f"{path}: файл прочитан (ступень ①), но ключ "
                  f"RUSTERM_LLM_API_KEY не задан — ступень ② не "
                  f"выполняется, ничего не записано ({outcome.reason}; "
                  f"ТЗ-20 L6)", file=sys.stderr)
            exit_code = 1
            continue
        if args.dry_run:
            print(f"{path}: извлечено, sha {outcome.document_sha[:12]}… "
                  f"(dry-run: ничего не записано)")
            continue
        if outcome.replay:
            print(f"{path}: уже импортирован ({outcome.document_sha[:12]}…), "
                  f"строки не дублировались; записей в документе: "
                  f"{outcome.records_total} "
                  f"(подтверждено {outcome.records_verified})")
            continue
        print(f"{path}: записей от модели: {outcome.records_total}; "
              f"отброшено без цитаты: {outcome.dropped_no_quote}, "
              f"с чужой категорией: {outcome.dropped_bad_category}; "
              f"подтверждено контролем: {outcome.records_verified}; "
              f"не подтверждено (manual_unverified, в меры не идут): "
              f"{outcome.records_unverified}; фактов записано: "
              f"{outcome.facts_stored}")
    if near_miss_total:
        print(f"near-miss записей: {near_miss_total} "
              f"(manual_near_miss — в меры не попадают)")
    conn.close()
    return exit_code


def _build_parser() -> argparse.ArgumentParser:
    """Построить парсер CLI (ТЗ-64 J3): извлечено из main, чтобы
    тесты могли проверять советы разбором, не исполняя команду.
    """
    parser = argparse.ArgumentParser(
        prog="rusterm", description="EquityLab: локальный терминал (ядро)")
    parser.add_argument(
        "--root", default=None,
        help="каталог данных (по умолчанию — правила 2-4 из "
             "store/paths.resolve_root: $RUSTERM_DATA, ./rusterm.db, "
             "~/.rusterm)")
    sub = parser.add_subparsers(dest="command", required=False)
    sub.add_parser("init", help="создать каталог данных и применить миграции")
    p_ing = sub.add_parser("ingest", help="сбор; реальный источник — не дефолт")
    p_ing.add_argument("--instrument", default=None)
    p_ing.add_argument("--ticker", default=None)
    p_ing.add_argument("--market", default=None)
    p_ing.add_argument("--watchlist", default=None)
    p_ing.add_argument("--source", choices=("synthetic", "edgar", "cvm",
                                            "asx", "twelvedata",
                                            "ownership"),
                       default="synthetic")
    sub.add_parser("demo", help="создать синтетический демо-инструмент")
    p_add = sub.add_parser("add", help="добавить настоящую компанию")
    p_add.add_argument("--fye", default=None,
                       help="конец финансового года эмитента, MM-DD "
                            "(например 06-30 для австралийского июня)")
    p_add.add_argument("--ticker", required=True)
    p_add.add_argument("--market", required=True)
    p_add.add_argument("--cik", type=int, default=None)
    p_add.add_argument("--name", default=None)
    p_add.add_argument("--instrument-id", dest="instrument_id", default=None)
    p_add.add_argument("--class", dest="class_", default="common")
    p_follow = sub.add_parser(
        "follow", help="один вызов: поиск в SEC → отчётность → цены → "
                       "снапшот (ТЗ-96 R2)")
    p_follow.add_argument("ticker", help="тикер, например AAPL")
    p_follow.add_argument("--market", default="US",
                          help="рынок из реестра (по умолчанию US)")
    p_snap = sub.add_parser("snapshot", help="собрать снапшот")
    p_snap.add_argument("--instrument", default=None)
    p_snap.add_argument("--ticker", default=None)
    p_snap.add_argument("--market", default=None)
    p_snap.add_argument("--watchlist", default=None)
    p_snap.add_argument("--as-of", default=None)
    p_exp = sub.add_parser("export", help="экспорт последнего снапшота")
    p_exp.add_argument("--instrument", required=False, default=None)
    p_exp.add_argument("--chat", default=None,
                       help="экспорт расшифровки разговора (ТЗ-36 H2)")
    p_exp.add_argument("--format", choices=("json", "csv", "md"),
                       default="json")
    p_exp.add_argument("--out", default=None)
    p_ver = sub.add_parser("verify", help="ручное исправление факта")
    p_ver.add_argument("--fact", required=True,
                       help="id факта, который неверен")
    p_ver.add_argument("--expected", required=True, help="правильное значение")
    p_ver.add_argument("--document", default="",
                       help="ссылка на документ (секреты из URL стираются)")
    p_doc = sub.add_parser("doctor", help="самопроверка базы и store")
    p_doc.add_argument("--fix", action="store_true",
                       help="применить ожидающие миграции (ТЗ-51 U2); "
                            "без флага doctor — только диагностика")
    p_bak = sub.add_parser("backup",
                           help="резервная копия каталога данных (ТЗ-22 J4)")
    p_bak.add_argument("archive", help="путь zip-архива")
    p_res = sub.add_parser("restore",
                           help="развернуть резервную копию (ТЗ-22 J4)")
    p_res.add_argument("archive", help="путь zip-архива")
    p_res.add_argument("--force", action="store_true",
                       help="разрешить запись в непустой каталог")
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
    p_desk = sub.add_parser(
        "desktop",
        help="десктопное окно (только чтение; ADR-0023), "
             "как python3 -m rusterm.desktop")
    p_desk.add_argument(
        "--root", default=argparse.SUPPRESS,
        help="каталог данных (по умолчанию — те же правила, что у "
             "CLI: $RUSTERM_DATA, ./rusterm.db, ~/.rusterm)")
    p_desk.add_argument("--watchlist", default=None)
    p_ref = sub.add_parser("refresh",
                           help="инкрементальный проход по списку наблюдения (для cron)")
    p_ref.add_argument("--watchlist", required=True)
    p_ref.add_argument("--dry-run", dest="dry_run", action="store_true")
    p_ref.add_argument("--json", action="store_true")
    p_ops = sub.add_parser(
        "ops",
        help="массовая операция: предложение -> показ -> подтверждение")
    p_ops.add_argument("--watchlist", required=True)
    p_ops.add_argument("--request", required=True,
                       help="текст запроса на естественном языке")
    p_ops.add_argument("--confirm", action="store_true",
                       help="применить показанное (без флага — dry-run)")
    p_ops.add_argument("--json", action="store_true")
    p_imp = sub.add_parser("import",
                           help="ручной импорт отчётов (ADR-0011; ТЗ-20)")
    p_imp.add_argument("path", nargs="+", help="файлы отчётов")
    p_imp.add_argument("--issuer", required=True)
    p_imp.add_argument("--market", default=None)
    p_imp.add_argument("--dry-run", dest="dry_run", action="store_true",
                       help="извлечь и проверить, ничего не записывая")
    p_chat = sub.add_parser("chat",
                            help="чат с цитатами (ТЗ-26 Q1); нужен ключ "
                                 "модели")
    # ТЗ-90 A2: у chat не было ни одного аргумента, а cmd_chat читал
    # args.max_calls — AttributeError до первого вопроса.
    from rusterm.core.chat import MAX_TOOL_CALLS_PER_SESSION
    p_chat.add_argument("--max-calls", dest="max_calls", type=int,
                        default=MAX_TOOL_CALLS_PER_SESSION,
                        help="потолок вызовов модели и инструментов за "
                             f"сессию (по умолчанию "
                             f"{MAX_TOOL_CALLS_PER_SESSION})")
    p_chat.add_argument("--instrument", dest="instrument", default=None,
                        help="к какому инструменту относим расшифровку")
    sub.add_parser("reparse",
                   help="заново разобрать сохранённые companyfacts и "
                        "выровнять basis фактов (без сети)")
    p_cad = sub.add_parser("cadence",
                           help="кадентность котировок: состояние, дыры,"
                                " срок опроса (ТЗ-31 C5)")
    p_cad.add_argument("--json", action="store_true",
                       help="машиночитаемая форма с закреплёнными ключами")
    p_cad.add_argument("--as-of", dest="as_of", default=None,
                       help="дата расчёта (по умолчанию сегодня)")
    p_census = sub.add_parser("census",
                              help="перепись отказов: мера × значение × "
                                   "причина (ТЗ-49 R1)")
    p_census.add_argument("--instrument", required=True)
    p_census.add_argument("--as-of", dest="as_of", default=None)
    p_census.add_argument("--rebuild", action="store_true",
                          help="пересобрать снапшот перед переписью")
    p_census.add_argument("--json", action="store_true")
    p_mkt = sub.add_parser("markets",
                           help="реестр рынков: коды, провайдеры, доступ")
    p_mkt.add_argument("--json", action="store_true")
    p_ind = sub.add_parser(
        "industry", help="агрегат по сектору на дату (M7)")
    p_ind.add_argument("--sector", required=True)
    p_ind.add_argument("--as-of", dest="as_of", default=None)
    p_ind.add_argument("--json", action="store_true")

    return parser

def main(argv: list[str] | None = None) -> int:
    from rusterm import env as env_module
    env_module.load_env()  # RUSTERM_* из ~/.rusterm.env, если не в окружении
    parser = _build_parser()
    args = parser.parse_args(argv)
    # ТЗ-90 A5: каталог выбирает одна функция, а не дефолт парсера. До
    # этого CLI молчал про «.», а окно и .app смотрели только в
    # $RUSTERM_DATA/~/.rusterm — `rusterm add` в каталоге проекта и
    # `rusterm desktop` из него же открывали две разные базы.
    # `load_env` выше уже положил RUSTERM_DATA из ~/.rusterm.env в
    # окружение, поэтому правило 2 работает и для запуска из Finder.
    args.root, args.root_rule = resolve_root(args.root)

    commands = {
        "init": cmd_init, "ingest": cmd_ingest, "snapshot": cmd_snapshot,
        "export": cmd_export, "verify": cmd_verify, "doctor": cmd_doctor,
        "backup": cmd_backup, "restore": cmd_restore,
        "chat": cmd_chat,
        "demo": cmd_demo,
        "watchlist": cmd_watchlist, "coverage": cmd_coverage,
        "metrics": cmd_metrics, "budget": cmd_budget,
        "status": cmd_status, "tui": cmd_tui, "add": cmd_add,
        "follow": cmd_follow,
        "desktop": cmd_desktop,
        "refresh": cmd_refresh,
        "ops": cmd_ops,
        "industry": cmd_industry,
        "markets": cmd_markets,
        "import": cmd_import,
        "cadence": cmd_cadence,
        "reparse": cmd_reparse,
        "census": cmd_census,
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
