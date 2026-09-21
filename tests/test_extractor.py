"""
Extraction is where SI/BL differences in wording are reconciled, so these
tests pin down label aliasing, placeholder handling and numeric parsing.
"""

import pytest

from shipguard.extractor import (
    canonical_field,
    clean_value,
    extract_container_count,
    extract_document,
    extract_weight,
)


# =============================================================
# LABEL ALIASING — align by meaning, not by header text
# =============================================================


@pytest.mark.parametrize(
    "label",
    [
        "Port of Loading",
        "port of loading",
        "Load Port",
        "POL",
        "pol",
        "POL (Port of Loading)",
    ],
)
def test_loading_port_labels_map_to_one_field(label):
    assert canonical_field(label) == "port_of_loading"


@pytest.mark.parametrize(
    "label",
    [
        "Port of Discharge",
        "Discharge Port",
        "POD",
        "POD (Final Destination)",
    ],
)
def test_discharge_port_labels_map_to_one_field(label):
    assert canonical_field(label) == "port_of_discharge"


@pytest.mark.parametrize(
    "label",
    [
        "Container Count",
        "No. of Containers",
        "No of Containers",
        "Total Containers",
        "Container Quantity",
    ],
)
def test_container_count_labels_map_to_one_field(label):
    assert canonical_field(label) == "container_count"


@pytest.mark.parametrize(
    "label",
    [
        "Gross Weight",
        "Gross Wt",
        "Total Gross Weight",
        "Total Gross Wt (KG)",
    ],
)
def test_gross_weight_labels_map_to_one_field(label):
    assert canonical_field(label) == "gross_weight_kg"


@pytest.mark.parametrize(
    "label, expected",
    [
        ("Shipper", "shipper"),
        ("Exporter", "shipper"),
        ("Consignee", "consignee"),
        ("Notify Party", "notify_party"),
        ("Notify", "notify_party"),
        ("To the Order of", "to_the_order_of"),
    ],
)
def test_party_labels_map_by_meaning(label, expected):
    assert canonical_field(label) == expected


def test_unrelated_labels_are_ignored():
    assert canonical_field("Vessel") is None
    assert canonical_field("Booking No") is None
    assert canonical_field("") is None
    assert canonical_field(None) is None


# =============================================================
# PLACEHOLDERS MUST BECOME None, NEVER A VALUE
# =============================================================


@pytest.mark.parametrize(
    "raw",
    [
        "N/A",
        "n/a",
        "NA",
        "TBA",
        "TBC",
        "nil",
        "NONE",
        "-",
        "--",
        "____MT",
        "___ KG",
        "_____",
        "   ",
        "",
    ],
)
def test_placeholders_are_treated_as_missing(raw):
    assert clean_value(raw) is None


def test_clean_value_keeps_real_values_and_collapses_whitespace():
    assert clean_value("  ACME   EXPORTS  PTE LTD ") == "ACME EXPORTS PTE LTD"


def test_clean_value_of_none_is_none():
    assert clean_value(None) is None


# =============================================================
# NUMERIC PARSING
# =============================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("5", 5),
        ("5 x 40HC", 5),
        ("12 containers", 12),
        ("no digits", None),
        (None, None),
    ],
)
def test_container_count_is_parsed_as_int(raw, expected):
    result = extract_container_count(raw)

    assert result == expected

    if expected is not None:
        assert isinstance(result, int)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("12500 KG", 12500.0),
        ("235,550", 235550.0),
        ("1,234.56 KGS", 1234.56),
        ("no digits", None),
        (None, None),
    ],
)
def test_weight_is_parsed_as_float_ignoring_commas(raw, expected):
    result = extract_weight(raw)

    assert result == expected

    if expected is not None:
        assert isinstance(result, float)


# =============================================================
# THE THREE EXTRACTION PASSES
# =============================================================


def test_colon_separated_pairs_are_extracted():
    text = "\n".join(
        [
            "Shipper: ACME EXPORTS PTE LTD",
            "Consignee: GLOBAL PAPER LLC",
            "Port of Loading: SINGAPORE",
            "Container Count: 5",
            "Gross Weight: 12500 KG",
        ]
    )

    data = extract_document(text)

    assert data["shipper"] == "ACME EXPORTS PTE LTD"
    assert data["consignee"] == "GLOBAL PAPER LLC"
    assert data["port_of_loading"] == "SINGAPORE"
    assert data["container_count"] == 5
    assert data["gross_weight_kg"] == 12500.0


def test_pipe_separated_rows_keep_only_the_company_name():
    text = "\n".join(
        [
            "Shipper | ACME EXPORTS PTE LTD | 12 Harbour Road, Singapore",
            "Notify Party | GLOBAL PAPER LLC | PO Box 9, Mombasa",
        ]
    )

    data = extract_document(text)

    assert data["shipper"] == "ACME EXPORTS PTE LTD"
    assert data["notify_party"] == "GLOBAL PAPER LLC"


def test_label_on_one_line_with_value_on_the_next():
    text = "\n".join(
        [
            "Shipper",
            "APRIL FINE PAPER TRADING",
            "",
            "Discharge Port",
            "MOMBASA, KENYA",
        ]
    )

    data = extract_document(text)

    assert data["shipper"] == "APRIL FINE PAPER TRADING"
    assert data["port_of_discharge"] == "MOMBASA, KENYA"


def test_separator_lines_are_not_mistaken_for_data():
    text = "\n".join(
        [
            "==============================",
            "Shipper: ACME EXPORTS PTE LTD",
            "------------------------------",
        ]
    )

    data = extract_document(text)

    assert data["shipper"] == "ACME EXPORTS PTE LTD"


def test_placeholder_in_a_document_leaves_the_field_missing():
    text = "\n".join(
        [
            "Shipper: ACME EXPORTS PTE LTD",
            "Gross Weight: ____MT",
        ]
    )

    data = extract_document(text)

    assert data["shipper"] == "ACME EXPORTS PTE LTD"
    assert data["gross_weight_kg"] is None


def test_every_field_is_present_in_the_result_even_when_empty():
    data = extract_document("")

    assert set(data) == {
        "shipper",
        "consignee",
        "notify_party",
        "port_of_loading",
        "port_of_discharge",
        "container_count",
        "gross_weight_kg",
    }
    assert all(value is None for value in data.values())


def test_si_and_bl_wordings_produce_the_same_extraction(si_text, bl_text):
    """
    The whole point of canonical_field: different labels, same result.
    """

    si_data = extract_document(si_text(), "SI")
    bl_data = extract_document(bl_text(), "BL")

    assert si_data == bl_data
