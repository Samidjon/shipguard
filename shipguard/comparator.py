import re

from .config import FIELDS


def normalize_text(value):
    if value is None:
        return None

    value = str(value).strip().lower()
    value = " ".join(value.split())

    return value


def normalize_port(value):
    if value is None:
        return None

    value = normalize_text(value)

    # Remove final UN/LOCODE such as (INNSA), (SGSIN), (KRPUS)
    value = re.sub(r"\s*\([a-z]{5}\)\s*$", "", value)

    return value.strip()


def normalize_field(field, value):
    if value is None:
        return None

    if field in {"port_of_loading", "port_of_discharge"}:
        return normalize_port(value)

    if isinstance(value, str):
        return normalize_text(value)

    return value


def compare_documents(si_data, bl_data):
    mismatches = []

    for field in FIELDS:
        si_value = normalize_field(field, si_data.get(field))
        bl_value = normalize_field(field, bl_data.get(field))

        if si_value is None or bl_value is None:
            continue

        if si_value != bl_value:
            mismatches.append({
                "field": field,
                "si": si_data.get(field),
                "bl": bl_data.get(field),
            })

    return {
        "match": len(mismatches) == 0,
        "mismatches": mismatches,
    }
