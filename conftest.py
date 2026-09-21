"""
Shared pytest fixtures for the ShipGuard test suite.

Keeping this file at the repository root also puts the root on sys.path,
so tests can import the project modules without any installation step.
"""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent


# =============================================================
# PATHS
# =============================================================


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT


@pytest.fixture(scope="session")
def dataset_dir():
    """
    The organizer-provided data bundle.

    Skips rather than fails when the bundle is absent, so the rest of the
    suite stays useful without the dataset.
    """

    path = REPO_ROOT / "sdoc-hackathon-bundle"

    if not path.is_dir():
        pytest.skip("organizer dataset bundle is not present")

    return path


# =============================================================
# SYNTHETIC SI / BL DOCUMENTS
# =============================================================

# Values keyed by canonical field name so tests can override by meaning.
DEFAULT_VALUES = {
    "shipper": "ACME EXPORTS PTE LTD",
    "consignee": "GLOBAL PAPER LLC",
    "notify_party": "GLOBAL PAPER LLC",
    "port_of_loading": "SINGAPORE",
    "port_of_discharge": "MOMBASA, KENYA",
    "container_count": "5",
    "gross_weight_kg": "12500 KG",
}

# The same seven fields labelled the way a Shipping Instruction does.
SI_LABELS = {
    "shipper": "Shipper",
    "consignee": "Consignee",
    "notify_party": "Notify Party",
    "port_of_loading": "Port of Loading",
    "port_of_discharge": "Port of Discharge",
    "container_count": "Container Count",
    "gross_weight_kg": "Gross Weight",
}

# Deliberately different labels with identical meaning, mirroring how
# draft Bills of Lading name the same fields.
BL_LABELS = {
    "shipper": "Shipper",
    "consignee": "Consignee",
    "notify_party": "Notify Party",
    "port_of_loading": "Load Port",
    "port_of_discharge": "Discharge Port",
    "container_count": "No. of Containers",
    "gross_weight_kg": "Total Gross Wt",
}


def _build_document(labels, **overrides):
    """
    Render a document body. Pass ``field=None`` to omit a field entirely.
    """

    values = dict(DEFAULT_VALUES)
    values.update(overrides)

    lines = []

    for field, label in labels.items():

        value = values[field]

        if value is None:
            continue

        lines.append(f"{label}: {value}")

    return "\n".join(lines)


@pytest.fixture
def si_text():
    def build(**overrides):
        return _build_document(SI_LABELS, **overrides)

    return build


@pytest.fixture
def bl_text():
    def build(**overrides):
        return _build_document(BL_LABELS, **overrides)

    return build
