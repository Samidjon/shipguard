"""
Display formatting for the comparison table.

The bug these tests guard against: the seven compared fields mix types, and
handing a mixed-type column to Streamlit made pyarrow raise
"Expected bytes, got a 'int' object" on every single render.
"""

import pandas as pd
import pyarrow as pa
import pytest

from shipguard.config import FIELDS
from shipguard.ui.formatting import MISSING, format_value


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, MISSING),
        ("ACME EXPORTS PTE LTD", "ACME EXPORTS PTE LTD"),
        (5, "5"),
        (100445.0, "100445"),
        (12500.5, "12500.5"),
        (0, "0"),
    ],
)
def test_values_render_as_expected_text(value, expected):
    assert format_value(value) == expected


@pytest.mark.parametrize(
    "value",
    [None, "text", 5, 100445.0, 12500.5, 0, True],
)
def test_every_rendered_value_is_a_string(value):
    assert isinstance(format_value(value), str)


def test_whole_floats_lose_the_trailing_zero():
    """A gross weight of 100445.0 kg should not read as "100445.0"."""

    assert format_value(100445.0) == "100445"
    assert format_value(12500.5) == "12500.5"


def test_mixed_field_types_survive_arrow_conversion():
    """
    The regression itself: a row holding a string, an int and a float must
    convert to an Arrow table without a dtype error.
    """

    si_values = {
        "shipper": "ACME EXPORTS PTE LTD",
        "consignee": "GLOBAL PAPER LLC",
        "notify_party": None,
        "port_of_loading": "SINGAPORE",
        "port_of_discharge": "MOMBASA, KENYA",
        "container_count": 5,
        "gross_weight_kg": 100445.0,
    }

    frame = pd.DataFrame(
        [
            {
                "Field": field.replace("_", " ").title(),
                "Shipping Instruction": format_value(si_values[field]),
                "Bill of Lading": format_value(si_values[field]),
                "Result": "✓ Match",
            }
            for field in FIELDS
        ]
    )

    table = pa.Table.from_pandas(frame)

    assert table.num_rows == len(FIELDS)


def test_raw_mixed_types_would_have_failed():
    """
    Documents why the conversion is needed: without format_value the same
    data raises inside pyarrow.
    """

    frame = pd.DataFrame(
        [
            {"Shipping Instruction": "ACME"},
            {"Shipping Instruction": 5},
            {"Shipping Instruction": 100445.0},
        ]
    )

    with pytest.raises(pa.ArrowTypeError):
        pa.Table.from_pandas(frame)
