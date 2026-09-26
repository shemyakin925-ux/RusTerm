"""ТЗ-B1 B1.2: перепись причин и страж словаря.

Перепись (способ сбора одной фразой): AST-обход всех модулей rusterm/,
собирающий строковые литералы (включая статические префиксы f-строк),
попадающие в позиции причин — keyword-аргументы *reason*, присваивания
именам и подпискам *reason*, значения словарей с ключами *reason*;
первый токен до ':' сравнивается со словарём reasons.NULL_REASONS.

Токен вне словаря обязан числиться в ALLOWLIST с обоснованием области:
это причины ДРУГИХ подсистем (провайдерские отказы, chat/LLM, ручной
импорт, отчёты watchlist/industry), которые никогда не попадают в
null_reason меры и потому не входят в словарь мер B15. Новый канал с
новой причиной не числится нигде — тест краснеет: страж ловит новые
каналы, а не только старые (демо красного/зелёного — REPORT-B1).

Токен peer_set_not_confirmed (aggregate.py, null_reason агрегата;
страж IndustryRepo.store_aggregates валидирует его is_known_reason)
заведён в словарь этим же пунктом — раньше он жил в коде, но не в
reasons.py, и запись такого агрегата падала бы ValueError.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from rusterm.reasons import NULL_REASONS

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "rusterm"

_TOKEN_SHAPE = re.compile(r"^[a-z][a-z0-9_]*$")


def _collect(path: Path) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []

    def note(lineno: int, value: object) -> None:
        if isinstance(value, str) and value:
            first = value.split(":", 1)[0]
            if _TOKEN_SHAPE.match(first):
                out.append((lineno, first))

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg \
                and "reason" in node.arg:
            if isinstance(node.value, ast.Constant):
                note(node.lineno, node.value.value)
            elif isinstance(node.value, ast.JoinedStr) and node.value.values \
                    and isinstance(node.value.values[0], ast.Constant):
                note(node.lineno, node.value.values[0].value)
        elif isinstance(node, ast.Assign):
            names: list[str] = []
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.append(t.id)
                elif isinstance(t, ast.Attribute):
                    names.append(t.attr)
                elif isinstance(t, ast.Subscript):
                    base = t.value
                    if isinstance(base, ast.Name):
                        names.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        names.append(base.attr)
            if any("reason" in n for n in names):
                if isinstance(node.value, ast.Constant):
                    note(node.lineno, node.value.value)
                elif isinstance(node.value, ast.JoinedStr) \
                        and node.value.values \
                        and isinstance(node.value.values[0], ast.Constant):
                    note(node.lineno, node.value.values[0].value)
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) \
                and len(node.value.elts) == 2:
            # позиция формульного отказа: return значение, "причина"
            # (пара; тройки-метки period_type/кодека — не причины)
            elt = node.value.elts[1]
            if isinstance(elt, ast.Constant):
                note(node.lineno, elt.value)
        elif isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) \
                        and isinstance(k.value, str) \
                        and "reason" in k.value \
                        and isinstance(v, ast.Constant):
                    note(node.lineno, v.value)
    return out


# Причины вне словаря мер: область (не null_reason меры) и место.
ALLOWED_NON_MEASURE: dict[str, str] = {
    # провайдерские каналы: отказы добычи, живут в coverage/логах
    "asx_bad_response": "provider channel refusal (providers/asx.py)",
    "asx_no_marketwide_index": "provider channel refusal (providers/asx.py)",
    "cvm_index_needs_dataset": "provider channel refusal (providers/cvm.py)",
    "cvm_no_consolidated_members": "coverage label (cli, cvm dfp)",
    "dart_bad_response": "provider channel refusal (providers/dart.py)",
    "dart_key_unset": "provider channel refusal (providers/dart.py)",
    "otc_bad_response": "provider channel refusal (providers/otcmarkets.py)",
    "twelvedata_bad_response": "provider channel refusal (providers/twelvedata.py)",
    "twelvedata_key_unset": "provider channel refusal (providers/twelvedata.py)",
    "vendor_rate_limited": "provider channel refusal (providers/twelvedata.py)",
    "source_has_no_disclosure": "coverage label (cli ownership)",
    "paid_channel_refused": "coverage label (cli, ADR-0018)",
    # chat/LLM: свои отказы, в меры не попадают
    "llm_bad_response": "chat/LLM subsystem (core/llm_api.py)",
    "llm_http_unknown": "chat/LLM subsystem (core/llm_api.py)",
    "llm_key_unset": "chat/LLM subsystem (core/llm_api.py)",
    "llm_model_unset": "chat/LLM subsystem (core/llm_api.py)",
    "llm_provider_requires_gate": "chat/LLM subsystem (core/llm_api.py)",
    "session_call_ceiling_reached": "chat/LLM subsystem (core/chat.py)",
    "guard_rejected_uncited_number": "chat/LLM subsystem (core/chat.py)",
    # ручной импорт: ProviderError-метки, не null_reason мер
    "extract_docx_refused": "manual import ProviderError (manual/extract.py)",
    "extract_xlsx_refused": "manual import ProviderError (manual/extract.py)",
    "extract_timeout": "manual import ProviderError (manual/extract.py)",
    "extract_too_many_rows": "manual import ProviderError (manual/extract.py)",
    "parse_failed": "manual import ProviderError (manual/records.py)",
    # отчёты чтения (watchlist/industry/refresh): метки строк отчёта
    "companyfacts": "refresh log label (core/refresh.py)",
    "industry_no_sector": "read-only report label (core/industry/inputs.py)",
    "industry_no_module": "read-only report label (core/industry/inputs.py)",
    "no_contributors": "read-only report label (core/industry/aggregate.py)",
    "no_version_at_date": "read-only report label (core/industry/aggregate.py)",
    "member_of_current_version": "watchlist import report (core/watchlist_io.py)",
    "row_missing_ticker_or_market": "watchlist import report (core/watchlist_io.py)",
    "no_instrument_for_": "watchlist import report f-string prefix",
    "schema_not_ready": "cadence report label (cli, sqlite not migrated)",
    "no_data_dir": "cadence report label (cli, data catalog absent)",
    # десктоп (полоса C): отказы действий окна, в меры не попадают
    "synthetic_demo_only": "desktop collect refusal (desktop/actions.py)",
    "unexpected_error": "desktop action refusal prefix (desktop/actions.py)",
    "index_unavailable": "desktop collect refusal (desktop/actions.py)",
    "fetch_failed": "desktop collect refusal (desktop/actions.py)",
    # расширенная перепись (сканер возвратов-пар и f-строк)
    "asx_bad_url": "provider channel refusal (providers/asx.py)",
    "dart_bad_url": "provider channel refusal (providers/dart.py)",
    "otc_bad_url": "provider channel refusal (providers/otcmarkets.py)",
    "cvm_not_found": "provider channel refusal (providers/cvm.py)",
    "cvm_not_a_document": "provider channel refusal (providers/cvm.py)",
    "twelvedata_error": "provider channel refusal (providers/twelvedata.py)",
    "extract_too_large": "manual import ProviderError (manual/extract.py)",
    "extract_unreadable": "manual import ProviderError (manual/extract.py)",
    "extract_zip_bomb": "manual import ProviderError (manual/extract.py)",
    "llm_failed": "chat/LLM subsystem (core/llm_api.py)",
    "llm_timeout": "chat/LLM subsystem (core/llm_api.py)",
    "llm_http_": "chat/LLM f-string prefix (core/llm_api.py)",
    "network_provider_requires_gate": "ingest gate label (cli, ADR-0021)",
    "provider_declares_no_host": "ingest gate label (cli, provider registry)",
    "provider_declares_no_tier": "ingest gate label (cli, ADR-0018)",
    "provider_not_implemented": "ingest gate label (cli, provider registry)",
    "incomplete": "price-history cadence report (core/cadence.py)",
    "complete": "price-history cadence report (core/cadence.py)",
    "closed": "price-history cadence report (core/cadence.py)",
    "no_history": "price-history cadence report (core/cadence.py)",
    "gap": "cadence report f-string prefix (core/cadence.py)",
    "stale_history": "cadence report f-string prefix (core/cadence.py)",
    "suspect": "coverage reason: suspect facts (pipeline.py)",
    "unparsed": "coverage reason: unparsed elements (pipeline.py)",
    "parser_degraded": "coverage reason: degraded parse (core/verification.py)",
    # слой конфигурации: отказ правки лимита при битом config.toml
    "config_broken": "config layer refusal (store/config.py)",
}


def test_every_reason_token_is_dictionary_or_allowlisted():
    """Полная перепись: каждый токен в позиции причины — в словаре мер
    или в allowlist'е чужих областей. Новый канал с новой причиной
    краснит этот тест."""
    unknown: dict[str, list[str]] = {}
    for path in sorted(PKG.rglob("*.py")):
        for lineno, token in _collect(path):
            if token not in NULL_REASONS \
                    and token not in ALLOWED_NON_MEASURE:
                unknown.setdefault(token, []).append(f"{path.name}:{lineno}")
    assert not unknown, (
        "причины вне словаря и вне allowlist (заведи в reasons.py с "
        f"смыслом для пользователя или обоснуй область): {unknown}")


def test_guard_catches_a_made_up_reason(tmp_path):
    """Красная демонстрация: выдуманная причина в позиции null_reason
    обязана быть поймана сканером (механика, а не память)."""
    fake = tmp_path / "fake_channel.py"
    fake.write_text(
        "def refuse():\n"
        "    return None, 'totally_made_up_reason'\n"
        "def build(**kw):\n"
        "    return dict(null_reason='another_made_up_one')\n",
        encoding="utf-8")
    tokens = {token for _, token in _collect(fake)}
    assert "totally_made_up_reason" in tokens
    assert "another_made_up_one" in tokens
    assert not (tokens - {"totally_made_up_reason",
                          "another_made_up_one"})


def test_aggregate_reason_peer_set_not_confirmed_is_in_dictionary():
    """B1.2: причина отказа агрегата по неподтверждённому набору пиров
    заведена в словарь — страж IndustryRepo.store_aggregates больше не
    отвергнет честный отказ (раньше токен жил только в aggregate.py)."""
    from rusterm.reasons import is_known_reason
    assert "peer_set_not_confirmed" in NULL_REASONS
    assert is_known_reason("peer_set_not_confirmed")
