"""ТЗ-83 F1: мусор внутрь — отказ наружу, по одной property на строку таблицы
контрактов ТЗ-83.

Каждая запись разбирает чужие байты, а тесты до сих пор кормили её только
записанным ответом. Здесь исход обязан быть РОВНО из колонки «Declared
contract»: любое другое исключение — дефект границы, и ловится он здесь, а не у
пользователя.

Корпус (фиксирующие решения ТЗ-83): мутация настоящих файлов из tests/data/ и
fixtures/ — обрезок по нарисованному смещению, переворот нарисованных байтов,
сшивка двух файлов, вставка случайных байтов, — плюс st.binary(). Ни одного
skip: свойство на пустом корпусе было бы воображаемым, поэтому перепись корпуса
закреплена тестом ниже.

Профили — те же, что завёл ТЗ-82: default (derandomize, 200 примеров) идёт в
обычном прогоне и обязан уложиться в 30 s на файл; тяжёлые варианты помечены
`slow` и собираются только по `-m slow` (глубокий прогон — ТЗ-83 F5).
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import hypothesis.strategies as st
import pytest
from hypothesis import given

from rusterm.manual import Document
from rusterm.manual.extract import extract_text
from rusterm.parsers import CompanyFactsParser, ParseResult, parse_auto
from rusterm.parsers.cvm_dfp import CvmDfpParser
from rusterm.parsers.ownership import OwnershipFiling, parse_form4
from rusterm.providers.base import ProviderError

_ROOT = Path(__file__).resolve().parent.parent

# ── корпус: те файлы, которые парсеры видят в настоящем разборе ──────────

_XML = tuple(sorted(p.read_bytes() for p in
                    (_ROOT / "tests" / "data" / "edgar" / "ownership")
                    .glob("*.xml")))
_CF = tuple(sorted(p.read_bytes() for p in
                   (_ROOT / "tests" / "data" / "edgar")
                   .glob("companyfacts*.json")))
_SYN = tuple(sorted(p.read_bytes() for p in
                    (_ROOT / "fixtures").glob("synthetic_*.json")))


def _dfp_rows() -> tuple[dict, ...]:
    """Строки настоящих DFP-срезов (кадам-срез — другая схема, он не вход
    parse_rows). Разделитель — ';' (замер по заголовку файла)."""
    rows: list[dict] = []
    for path in sorted((_ROOT / "tests" / "data" / "cvm")
                       .glob("dfp_*.csv")):
        # latin-1 — как в CvmProvider.rows_for (providers/cvm.py:221):
        # бразильский заголовок не проходит как utf-8.
        with path.open(newline="", encoding="latin-1") as fh:
            rows.extend(csv.DictReader(fh, delimiter=";"))
    return tuple(rows)


_CVM_ROWS = _dfp_rows()

# parse_rows смотрит на эти поля; без них строка не может стать фактом.
_CVM_KEYS = ("CD_CONTA", "VL_CONTA", "DT_FIM_EXERC", "DT_INI_EXERC",
             "ORDEM_EXERC", "VERSAO", "MOEDA", "ESCALA_MOEDA")


def test_corpus_matches_the_contract_table():
    """Перепись корпуса: пустой список файлов сделал бы свойства молчанием.

    Числа — фактический состав tests/data и fixtures на 24.09 (замерено
    здесь, а не выдумано): 5 документов владения, 22 companyfacts,
    8 синтетических фикстур, 40+ строк DFP.
    """
    assert len(_XML) >= 5, f"XML-корпус: {len(_XML)}"
    assert len(_CF) >= 20, f"companyfacts-корпус: {len(_CF)}"
    assert len(_SYN) >= 8, f"синтетический корпус: {len(_SYN)}"
    assert len(_CVM_ROWS) >= 40, f"DFP-строки: {len(_CVM_ROWS)}"
    usable = [r for r in _CVM_ROWS
              if all(r.get(k) for k in ("CD_CONTA", "VL_CONTA",
                                         "DT_FIM_EXERC"))]
    assert usable, "ни одна строка DFP не даёт факта — тест был бы пустым"


# ── мутации ──────────────────────────────────────────────────────────────

_OPS = ("truncate", "flip", "splice", "insert")


@st.composite
def mutated_bytes(draw, corpus: tuple[bytes, ...], max_ops: int = 3):
    """Байты корпуса, пропущенные через нарисованное число мутаций."""
    payload = bytearray(draw(st.sampled_from(corpus)))
    for _ in range(draw(st.integers(0, max_ops))):
        if not payload:
            break
        op = draw(st.sampled_from(_OPS))
        if op == "truncate":
            payload = payload[:draw(st.integers(0, len(payload)))]
        elif op == "flip":
            index = draw(st.integers(0, len(payload) - 1))
            payload[index] ^= draw(st.integers(1, 255))
        elif op == "splice":
            other = draw(st.sampled_from(corpus))
            if other:
                cut = draw(st.integers(0, len(payload)))
                here = draw(st.integers(0, len(other)))
                payload = bytearray(payload[:cut] + other[here:])
        else:  # insert
            index = draw(st.integers(0, len(payload)))
            payload[index:index] = draw(st.binary(max_size=24))
    return bytes(payload)


def hostile_bytes(corpus: tuple[bytes, ...], max_ops: int = 3):
    """Мутации корпуса и случайные байты: и то и другое парсер обязан
    пережить без чужого исключения."""
    return st.one_of(mutated_bytes(corpus, max_ops=max_ops),
                     st.binary(max_size=512))


# Узел, на который меняем настоящий фрагмент JSON: «не словарь там, где
# ждали словарь» — ровно то, что строка 2 таблицы ТЗ-83 подозревает как
# «wrong shapes». NaN/inf проходят json.loads (Python пишет их как NaN)
# и обязан не пропустить их ни один парсер.
_HOSTILE_NODE = st.one_of(
    st.none(),
    st.integers(-3, 3),
    st.text(max_size=4),
    st.just([]),
    st.just({}),
    st.just(True),
    st.sampled_from([float("nan"), float("inf"), float("-inf"), 1e309]),
)


@st.composite
def json_shape_mutated(draw, corpus: tuple[bytes, ...]) -> bytes:
    """Настоящий JSON, в котором нарисованный узел заменён мусором.

    Байтовые мутации до такой формы доходят редко (файл чаще перестаёт
    быть валидным JSON), а дыра wrong shapes — именно про неё.
    """
    src = draw(st.sampled_from(corpus))
    try:
        doc = json.loads(src.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return src
    node = doc
    path: list = []
    for _ in range(draw(st.integers(0, 3))):
        if not isinstance(node, dict) or not node:
            break
        key = draw(st.sampled_from(sorted(node, key=str)))
        path.append(key)
        node = node[key]
    hostile = draw(_HOSTILE_NODE)
    if not path:
        # Ни одного шага: мусором становится весь документ.
        return json.dumps(hostile, ensure_ascii=False).encode("utf-8")
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = hostile
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")


def hostile_corpus(corpus: tuple[bytes, ...], max_ops: int = 3):
    """Полное множество враждебных входов корпуса: байтовые мутации,
    случайные байты и порча формы настоящего JSON."""
    return st.one_of(hostile_bytes(corpus, max_ops=max_ops),
                     json_shape_mutated(corpus))


# Значения ячеек DFP: вендорский мусор, границы float() и пустоты.
_CVM_CELL = st.one_of(
    st.none(),
    st.text(max_size=10),
    st.sampled_from(["NaN", "nan", "Infinity", "-Infinity", "1e309",
                     "1e-323", "1_000", "0x10", "", " ", "-", "1,5",
                     "2024-13-45", "9" * 400]),
    st.integers(-10 ** 6, 10 ** 6).map(str),
    st.floats(allow_nan=True).map(repr),
)


@st.composite
def cvm_rows(draw, max_rows: int = 6):
    """Список строк одного эмитента: настоящие строки DFP, испорченные
    нарисованным числом полей."""
    rows = []
    for _ in range(draw(st.integers(0, max_rows))):
        row = dict(draw(st.sampled_from(_CVM_ROWS)))
        for key in tuple(row):
            if draw(st.integers(0, 3)) == 0:
                row[key] = draw(_CVM_CELL)
        if draw(st.integers(0, 5)) == 0 and row:
            row.pop(draw(st.sampled_from(sorted(row))), None)
        rows.append(row)
    return rows


# ── проверки по колонке «Declared contract» ──────────────────────────────

def _hex(payload: bytes, limit: int = 80) -> str:
    return payload[:limit].hex()


_CONTEXT = {"issuer_id": "issuer:test", "listing_id": "listing:test",
            "source_ref": "sha256:0000", "csv_member": "dfp.csv",
            "endpoint": "https://example.invalid/companyfacts"}

_META = st.fixed_dictionaries({
    "doc_kind": st.one_of(
        st.sampled_from(["xbrl", "table", "companyfacts", "dei"]),
        st.text(max_size=8)),
    "doc_type": st.one_of(
        st.sampled_from(["10-K", "10-Q", "INSIDER", "PRICES"]),
        st.text(max_size=6)),
})


def _check_fact_value(fact: dict) -> None:
    """Значение факта конечное, если вообще читается числом."""
    value = fact.get("value")
    assert value is not None, f"факт без значения: {fact.get('concept')!r}"
    try:
        number = float(str(value))
    except ValueError:
        return  # вендорская запись числа — не вопрос этой строки контракта
    assert math.isfinite(number), (
        f"неконечное значение в факте {fact.get('concept')!r}: {value!r}")


def _check_parse_result(result, entry: str, raw: bytes) -> None:
    assert isinstance(result, ParseResult), (
        f"{entry} вернул {type(result).__name__}, hex={_hex(raw)}")
    assert isinstance(result.facts, list)
    assert isinstance(result.unparsed, int) and result.unparsed >= 0, (
        f"unparsed={result.unparsed}")
    for fact in result.facts:
        _check_fact_value(fact)


def check_form4_contract(raw: bytes) -> None:
    """parse_form4: OwnershipFiling или ValueError — и ничего больше."""
    try:
        filing = parse_form4(raw)
    except ValueError:
        return
    except Exception as exc:  # noqa: BLE001 - нарушен контракт, тип важен
        raise AssertionError(
            f"parse_form4 бросил {type(exc).__name__} вместо ValueError: "
            f"{exc!r}; вход hex={_hex(raw)}") from exc
    assert isinstance(filing, OwnershipFiling), type(filing).__name__
    assert isinstance(filing.transactions, list)


def check_companyfacts_contract(raw: bytes) -> None:
    """CompanyFactsParser().parse: ParseResult на любом входе."""
    try:
        result = CompanyFactsParser().parse(raw, _CONTEXT)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"CompanyFactsParser.parse бросил {type(exc).__name__}: "
            f"{exc!r}; вход hex={_hex(raw)}") from exc
    _check_parse_result(result, "CompanyFactsParser.parse", raw)


def check_parse_auto_contract(raw: bytes, metadata: dict) -> None:
    """parse_auto: ParseResult или None (парсера нет) — без исключений."""
    try:
        result = parse_auto(raw, metadata, _CONTEXT)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"parse_auto бросил {type(exc).__name__} на metadata="
            f"{metadata!r}: {exc!r}; вход hex={_hex(raw)}") from exc
    if result is None:
        return
    _check_parse_result(result, "parse_auto", raw)


def check_cvm_contract(rows: list[dict], statement: str) -> None:
    """parse_rows: (факты, неразобрано); факт конечен и их не больше строк."""
    try:
        facts, unparsed = CvmDfpParser().parse_rows(rows, statement, _CONTEXT)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"parse_rows бросил {type(exc).__name__} на {statement}: "
            f"{exc!r}; вход {rows!r}") from exc
    assert isinstance(facts, list)
    assert isinstance(unparsed, int) and unparsed >= 0, f"unparsed={unparsed}"
    assert len(facts) <= len(rows), (
        f"фактов {len(facts)} больше, чем строк {len(rows)}")
    for fact in facts:
        _check_fact_value(fact)


def check_extract_contract(path: Path) -> None:
    """extract_text: Document или ProviderError, никогда не бросает."""
    try:
        out = extract_text(path)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"extract_text бросил {type(exc).__name__}: {exc!r}; "
            f"файл {path.name}") from exc
    assert isinstance(out, (Document, ProviderError)), type(out).__name__


# ── F1: по одному свойству на строку таблицы ─────────────────────────────

@given(raw=hostile_corpus(_XML))
def test_form4_refuses_or_returns_filing(raw):
    check_form4_contract(raw)


@given(raw=hostile_corpus(_CF))
def test_companyfacts_returns_parse_result(raw):
    check_companyfacts_contract(raw)


@given(raw=st.one_of(hostile_corpus(_CF), hostile_corpus(_SYN)), meta=_META)
def test_parse_auto_returns_result_or_none(raw, meta):
    check_parse_auto_contract(raw, meta)


@given(rows=cvm_rows(), statement=st.sampled_from(["DRE", "BPP"]))
def test_cvm_rows_never_yield_non_finite_fact(rows, statement):
    check_cvm_contract(rows, statement)


@given(raw=st.one_of(hostile_corpus(_SYN, max_ops=2),
                     hostile_corpus(_CF, max_ops=2)))
def test_extract_text_never_raises(raw, tmp_path_factory):
    # tmp_path_factory, не tmp_path: Hypothesis запретил функционную
    # фикстуру в property-тесте (FailedHealthCheck), а писать надо вне
    # дерева репозитория (P3).
    path = tmp_path_factory.mktemp("fuzz-extract") / "document.bin"
    path.write_bytes(raw)
    check_extract_contract(path)


# ── фиксированный случай, которого property-генератор не рисует ──────────

def test_deeply_nested_json_refused_by_every_json_entry():
    """100 000 открывающих скобок: рекурсивный сканер json тонет стеком и
    поднимает RecursionError — не ValueError, не ParseResult (замер на
    неразобранных парсерах).

    Это не property-случай: Hypothesis нарисовал бы мегабайты на пример и
    не уложился бы в бюджет, а дыра от числа примеров не зависит.
    """
    deep = b"[" * 400_000
    cases = [("CompanyFactsParser.parse",
              lambda: CompanyFactsParser().parse(deep, _CONTEXT)),
             ("parse_auto/companyfacts",
              lambda: parse_auto(deep, {"doc_kind": "companyfacts"},
                                 _CONTEXT)),
             ("parse_auto/xbrl",
              lambda: parse_auto(deep, {"doc_kind": "xbrl"}, _CONTEXT)),
             ("parse_auto/table",
              lambda: parse_auto(deep, {"doc_kind": "table"}, _CONTEXT))]
    for entry, call in cases:
        try:
            result = call()
        except Exception as exc:  # noqa: BLE001 - тип важен по контракту
            raise AssertionError(
                f"{entry} бросил {type(exc).__name__} на входе из "
                f"{len(deep)} байт") from exc
        _check_parse_result(result, entry, deep[:80])
        assert result.facts == [] and result.unparsed >= 1, (
            f"{entry}: глубокий вход обязан отказать значением, а не "
            f"молча разобшаться: facts={len(result.facts)} "
            f"unparsed={result.unparsed}")


# ── тяжёлые варианты: собираются только по `-m slow` (ТЗ-83 F5) ──────────

@pytest.mark.slow
@given(raw=mutated_bytes(_XML, max_ops=8))
def test_form4_refuses_or_returns_filing_deep(raw):
    check_form4_contract(raw)


@pytest.mark.slow
@given(raw=st.one_of(mutated_bytes(_CF, max_ops=8),
                     json_shape_mutated(_CF)))
def test_companyfacts_returns_parse_result_deep(raw):
    check_companyfacts_contract(raw)


@pytest.mark.slow
@given(raw=st.one_of(mutated_bytes(_CF + _SYN, max_ops=8),
                     json_shape_mutated(_CF + _SYN)), meta=_META)
def test_parse_auto_returns_result_or_none_deep(raw, meta):
    check_parse_auto_contract(raw, meta)


@pytest.mark.slow
@given(rows=cvm_rows(max_rows=24), statement=st.sampled_from(["DRE", "BPP"]))
def test_cvm_rows_never_yield_non_finite_fact_deep(rows, statement):
    check_cvm_contract(rows, statement)


@pytest.mark.slow
@given(raw=mutated_bytes(_SYN + _CF, max_ops=8))
def test_extract_text_never_raises_deep(raw, tmp_path_factory):
    # та же причина, что у обычного варианта: фикстура функционной
    # области Hypothesis в property-тесте запрещена.
    path = tmp_path_factory.mktemp("fuzz-extract-deep") / "document.bin"
    path.write_bytes(raw)
    check_extract_contract(path)
