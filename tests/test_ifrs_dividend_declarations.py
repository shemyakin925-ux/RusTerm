"""22.10 (KSPI): дивиденд на акцию эмитента IFRS, поданный объявлениями
месячными периодами, — в карте (ifrs-full.v4) и в сумме за год."""
from rusterm.core.ttm import declared_by_year, declared_window
from rusterm.normalize.concepts import CONCEPT_MAP_IFRS


def test_ifrs_dps_tag_is_mapped():
    assert CONCEPT_MAP_IFRS["dps"] == (
        "DividendsRecognisedAsDistributionsToOwnersPerShare",)


KSPI_2024 = [
    (850, "2024-11-01", "2024-11-30", "f4"),
    (850, "2024-08-01", "2024-08-31", "f3"),
    (850, "2024-04-01", "2024-04-30", "f2"),
    (850, "2024-02-01", "2024-02-29", "f1"),
    (850, "2024-02-01", "2024-02-29", "f1-dup"),  # та же подача дважды
]


def test_month_period_declarations_sum_by_year():
    total, ids = declared_by_year(KSPI_2024)["2024"]
    assert total == 3400 and len(ids) == 4


def test_quarter_and_year_periods_are_not_declarations():
    rows = [(1.0, "2024-01-01", "2024-03-31", "q"),
            (4.0, "2024-01-01", "2024-12-31", "y")]
    assert declared_by_year(rows) == {}
    assert declared_window(rows, "2025-01-15") is None


def test_declared_window_takes_month_periods():
    window = declared_window(KSPI_2024, "2025-01-15")
    assert window is not None and window.value == 3400
