import re

from .config import FIELDS


def clean_value(value):
    if value is None:
        return None

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)

    if not value:
        return None

    # Values that explicitly mean "not provided"
    lower = value.lower().strip()

    if lower in {
        "n/a",
        "na",
        "tba",
        "tbc",
        "nil",
        "none",
        "-",
        "--",
    }:
        return None

    # Placeholder values such as "____", "____MT", "___ KG"
    if re.fullmatch(r"[_\-\s]*(?:mt|kg)?[_\-\s]*", lower):
        return None

    return value


def normalize_key(key):
    if key is None:
        return ""

    key = str(key).strip().lower()
    key = re.sub(r"\s+", " ", key)

    return key


def extract_container_count(value):
    if value is None:
        return None

    match = re.search(r"(\d+)", str(value))

    if match:
        return int(match.group(1))

    return None


def extract_weight(value):
    if value is None:
        return None

    value = str(value).replace(",", "")

    match = re.search(r"(\d+(?:\.\d+)?)", value)

    if match:
        return float(match.group(1))

    return None


def canonical_field(key):
    """
    Convert many document-specific field labels into one
    canonical field name.
    """

    key = normalize_key(key)

    # Remove common punctuation/noise.
    key = key.replace("：", ":")
    key = key.strip()

    # ---------------------------------------------------------
    # SHIPPER
    # ---------------------------------------------------------

    if (
        key.startswith("shipper")
        or key.startswith("exporter")
    ):
        return "shipper"

    # ---------------------------------------------------------
    # CONSIGNEE
    # ---------------------------------------------------------

    if key.startswith("consignee"):
        return "consignee"

    # "To the Order of" is handled separately because it is
    # document-type dependent.
    if key.startswith("to the order of"):
        return "to_the_order_of"

    # ---------------------------------------------------------
    # NOTIFY PARTY
    # ---------------------------------------------------------

    if (
        key.startswith("notify")
        or key.startswith("notify party")
    ):
        return "notify_party"

    # ---------------------------------------------------------
    # PORT OF LOADING
    # ---------------------------------------------------------

    if (
        key == "pol"
        or key.startswith("pol ")
        or key.startswith("pol(")
        or key.startswith("port of loading")
        or key.startswith("load port")
    ):
        return "port_of_loading"

    # ---------------------------------------------------------
    # PORT OF DISCHARGE
    # ---------------------------------------------------------

    if (
        key == "pod"
        or key.startswith("pod ")
        or key.startswith("pod(")
        or key.startswith("port of discharge")
        or key.startswith("discharge port")
    ):
        return "port_of_discharge"

    # ---------------------------------------------------------
    # CONTAINER COUNT
    # ---------------------------------------------------------

    if (
        key.startswith("container count")
        or key.startswith("no. of containers")
        or key.startswith("no of containers")
        or key.startswith("no. of container")
        or key.startswith("total containers")
        or key.startswith("container quantity")
    ):
        return "container_count"

    # ---------------------------------------------------------
    # GROSS WEIGHT
    # ---------------------------------------------------------

    if (
        key.startswith("gross weight")
        or key.startswith("gross wt")
        or key.startswith("total gross weight")
        or key.startswith("total gross wt")
    ):
        return "gross_weight_kg"

    return None


def extract_document(text, document_type=None):

    data = {field: None for field in FIELDS}

    if not text:
        return data

    lines = [line.strip() for line in text.splitlines()]

    seen_fields = set()

    # =========================================================
    # FIRST PASS
    # Key | Value
    # Key: Value
    # =========================================================

    for raw_line in lines:

        line = raw_line.strip()

        if not line:
            continue

        # Ignore separator lines.
        if set(line) <= {"=", "-", "_"}:
            continue

        key = None
        value = None

        if "|" in line:
            key, value = line.split("|", 1)

        elif ":" in line:
            key, value = line.split(":", 1)

        else:
            continue

        key = normalize_key(key)
        value = clean_value(value)

        if not value:
            continue

        field = canonical_field(key)

        if field is None:
            continue

        seen_fields.add(field)
        # -----------------------------------------------------
        # CONSIGNEE
        # -----------------------------------------------------

        if field == "to_the_order_of":
        
            if data["consignee"] is None:
                data["consignee"] = value.split("|", 1)[0].strip()

            continue

        if field == "consignee":
            data["consignee"] = value.split("|", 1)[0].strip()
            continue

        # -----------------------------------------------------
        # IDENTITY FIELDS
        # -----------------------------------------------------

        if field in [
            "shipper",
            "consignee",
            "notify_party",
        ]:

            # For spreadsheet rows such as:
            #
            # Shipper | COMPANY | ADDRESS
            #
            # Keep only the company name.
            value = value.split("|", 1)[0].strip()

            if data[field] is None:
                data[field] = value

            continue

        # -----------------------------------------------------
        # PORTS
        # -----------------------------------------------------

        if field == "port_of_loading":

            if data[field] is None:
                data[field] = value

            continue

        if field == "port_of_discharge":

            if data[field] is None:
                data[field] = value

            continue

        # -----------------------------------------------------
        # CONTAINER COUNT
        # -----------------------------------------------------

        if field == "container_count":

            if data[field] is None:
                data[field] = extract_container_count(value)

            continue

        # -----------------------------------------------------
        # GROSS WEIGHT
        # -----------------------------------------------------

        if field == "gross_weight_kg":

            if data[field] is None:
                data[field] = extract_weight(value)

            continue

    # =========================================================
    # SECOND PASS
    #
    # Label on one line
    # Value on the next line
    #
    # Example:
    #
    # Shipper
    # APRIL FINE PAPER TRADING
    # =========================================================

    def is_field_label(line):

        normalized = normalize_key(line)

        if canonical_field(normalized) is not None:
            return True

        return False

    def next_value(index):

        for j in range(index + 1, min(index + 6, len(lines))):

            candidate = lines[j].strip()

            if not candidate:
                continue

            if is_field_label(candidate):
                return None

            # Avoid obvious document metadata.
            candidate_lower = candidate.lower()

            if candidate_lower.startswith(
                (
                    "vessel",
                    "booking",
                    "booking ref",
                    "booking no",
                    "description",
                    "hs code",
                    "freight",
                    "incoterms",
                )
            ):
                return None

            return clean_value(candidate)

        return None

    for i, raw_line in enumerate(lines):

        line = raw_line.strip()

        if not line:
            continue

        key = normalize_key(line)

        field = canonical_field(key)

        if field is None:
            continue

        if field in seen_fields:
            continue

        # -----------------------------------------------------
        # TO THE ORDER OF
        # -----------------------------------------------------

        if (
            field == "to_the_order_of"
            and document_type == "SI"
            and data["consignee"] is None
        ):

            value = next_value(i)

            if value:
                data["consignee"] = value

            continue

        # -----------------------------------------------------
        # NORMAL FIELDS
        # -----------------------------------------------------

        if field in [
            "shipper",
            "consignee",
            "notify_party",
            "port_of_loading",
            "port_of_discharge",
        ]:

            if data[field] is None:

                value = next_value(i)

                if value:
                    data[field] = value

            continue

        # -----------------------------------------------------
        # CONTAINER COUNT
        # -----------------------------------------------------

        if field == "container_count":

            if data["container_count"] is None:

                value = next_value(i)

                if value:
                    data["container_count"] = extract_container_count(
                        value
                    )

            continue

        # -----------------------------------------------------
        # GROSS WEIGHT
        # -----------------------------------------------------

        if field == "gross_weight_kg":

            if data["gross_weight_kg"] is None:

                value = next_value(i)

                if value:
                    data["gross_weight_kg"] = extract_weight(value)

            continue

    # =========================================================
    # THIRD PASS
    #
    # Explicit total values.
    #
    # These override table-header ambiguity.
    # =========================================================

    for raw_line in lines:

        line = raw_line.strip()
        normalized = normalize_key(line)

        # -----------------------------------------------------
        # CONTAINER COUNT
        # -----------------------------------------------------

        if data["container_count"] is None:

            if (
                normalized.startswith("no. of containers")
                or normalized.startswith("no of containers")
                or normalized.startswith("container count")
                or normalized.startswith("total containers")
            ):

                match = re.search(r"(\d+)", line)

                if match:
                    data["container_count"] = int(match.group(1))

        # -----------------------------------------------------
        # TOTAL GROSS WEIGHT
        # -----------------------------------------------------

        if (
            "total gross wt" in normalized
            or "total gross weight" in normalized
        ):

            if ":" in line:
                value = line.split(":", 1)[1]
            elif "|" in line:
                value = line.split("|", 1)[1]
            else:
                value = line

            weight = extract_weight(value)

            if weight is not None:
                data["gross_weight_kg"] = weight

    return data