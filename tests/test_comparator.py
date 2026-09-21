"""
Comparison rules: normalization must absorb cosmetic differences, and a
missing value must never be reported as a mismatch.
"""

import pytest

from shipguard.comparator import (
    compare_documents,
    normalize_field,
    normalize_port,
    normalize_text,
)
from shipguard.config import FIELDS


def make_data(**overrides):
    data = {field: None for field in FIELDS}
    data.update(overrides)
    return data


# =============================================================
# NORMALIZATION
# =============================================================


def test_port_normalization_strips_trailing_locode():
    assert normalize_port("NHAVA SHEVA, INDIA (INNSA)") == "nhava sheva, india"
    assert normalize_port("SINGAPORE (SGSIN)") == "singapore"
    assert normalize_port("BUSAN (KRPUS)") == "busan"


def test_port_normalization_keeps_other_parentheses():
    assert normalize_port("PORT KLANG (WESTPORT)") == "port klang (westport)"


def test_text_normalization_is_case_and_whitespace_insensitive():
    assert normalize_text("  ACME   Exports  ") == "acme exports"


def test_normalize_field_only_strips_locode_for_ports():
    assert normalize_field("port_of_loading", "SINGAPORE (SGSIN)") == "singapore"
    assert normalize_field("shipper", "ACME (SGSIN)") == "acme (sgsin)"


def test_normalize_field_leaves_numbers_untouched():
    assert normalize_field("container_count", 5) == 5
    assert normalize_field("gross_weight_kg", 12500.0) == 12500.0


def test_normalize_helpers_pass_none_through():
    assert normalize_text(None) is None
    assert normalize_port(None) is None
    assert normalize_field("shipper", None) is None


# =============================================================
# COMPARISON
# =============================================================


def test_identical_documents_match():
    data = make_data(shipper="ACME", container_count=5)

    result = compare_documents(data, dict(data))

    assert result["match"] is True
    assert result["mismatches"] == []


def test_case_and_spacing_differences_still_match():
    si = make_data(shipper="ACME  EXPORTS")
    bl = make_data(shipper="acme exports")

    assert compare_documents(si, bl)["match"] is True


def test_locode_suffix_does_not_create_a_mismatch():
    si = make_data(port_of_discharge="NHAVA SHEVA, INDIA (INNSA)")
    bl = make_data(port_of_discharge="NHAVA SHEVA, INDIA")

    assert compare_documents(si, bl)["match"] is True


def test_differing_value_is_reported_as_a_mismatch():
    si = make_data(port_of_loading="SINGAPORE")
    bl = make_data(port_of_loading="PORT KLANG")

    result = compare_documents(si, bl)

    assert result["match"] is False
    assert [m["field"] for m in result["mismatches"]] == ["port_of_loading"]


def test_mismatch_reports_original_unnormalized_values():
    si = make_data(port_of_loading="SINGAPORE (SGSIN)")
    bl = make_data(port_of_loading="PORT KLANG, MALAYSIA")

    mismatch = compare_documents(si, bl)["mismatches"][0]

    assert mismatch["si"] == "SINGAPORE (SGSIN)"
    assert mismatch["bl"] == "PORT KLANG, MALAYSIA"


@pytest.mark.parametrize(
    "si_value, bl_value",
    [
        (None, "ACME"),
        ("ACME", None),
        (None, None),
    ],
)
def test_a_missing_value_is_skipped_not_flagged(si_value, bl_value):
    """
    Absent data is handled upstream as NEEDS_REVIEW / missing_value, so the
    comparator must not turn it into a defect.
    """

    si = make_data(shipper=si_value)
    bl = make_data(shipper=bl_value)

    result = compare_documents(si, bl)

    assert result["match"] is True
    assert result["mismatches"] == []


def test_multiple_differing_fields_are_all_reported():
    si = make_data(
        port_of_loading="SINGAPORE",
        port_of_discharge="MOMBASA",
        container_count=5,
    )
    bl = make_data(
        port_of_loading="PORT KLANG",
        port_of_discharge="HOUSTON",
        container_count=5,
    )

    fields = [m["field"] for m in compare_documents(si, bl)["mismatches"]]

    assert fields == ["port_of_loading", "port_of_discharge"]


def test_numeric_fields_compare_by_value():
    assert compare_documents(
        make_data(container_count=5, gross_weight_kg=12500.0),
        make_data(container_count=5, gross_weight_kg=12500.0),
    )["match"] is True

    assert compare_documents(
        make_data(container_count=5),
        make_data(container_count=6),
    )["match"] is False


def test_comparison_covers_all_seven_fields():
    si = make_data(**{field: "same" for field in FIELDS})
    bl = make_data(**{field: "different" for field in FIELDS})

    fields = [m["field"] for m in compare_documents(si, bl)["mismatches"]]

    assert fields == FIELDS
