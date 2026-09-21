from collections import Counter

from loader import Inbox
from classifier import classify_email
from document_reader import read_document
from extractor import extract_document
from comparator import compare_documents


DATA_SOURCE = r"C:\Users\suley\Documents\hackathon\sdoc-hackathon-bundle"

FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]


def find_attachment(attachments, document_type):

    document_type = document_type.lower()

    for attachment in attachments:

        filename = attachment.lower()
        filename = filename.split("/")[-1]

        filename_without_extension = filename.rsplit(".", 1)[0]

        if filename_without_extension.endswith(
            "_" + document_type
        ):
            return attachment

    return None


def main():

    inbox = Inbox(DATA_SOURCE)

    emails = list(inbox)

    stats = Counter()

    missing_fields = Counter()

    mismatch_fields = Counter()

    examples = []

    for email in emails:

        category = classify_email(email)

        if category != "DOCUMENT_COMPARISON":
            continue

        stats["DOCUMENT_COMPARISON"] += 1

        attachments = email.get("attachments", [])

        si_path = find_attachment(
            attachments,
            "SI"
        )

        bl_path = find_attachment(
            attachments,
            "BL"
        )

        # =====================================================
        # ATTACHMENT CHECK
        # =====================================================

        if not si_path and not bl_path:

            stats["NO_SI_AND_BL"] += 1
            continue

        if not si_path:

            stats["NO_SI"] += 1
            continue

        if not bl_path:

            stats["NO_BL"] += 1
            continue

        stats["HAS_SI_AND_BL"] += 1

        # =====================================================
        # READ DOCUMENTS
        # =====================================================

        try:

            si_text = read_document(
                inbox,
                si_path
            )

            bl_text = read_document(
                inbox,
                bl_path
            )

        except Exception as error:

            stats["READ_ERROR"] += 1

            if len(examples) < 10:

                examples.append(
                    (
                        email["email_id"],
                        "READ_ERROR",
                        str(error),
                    )
                )

            continue

        # =====================================================
        # EXTRACT
        # =====================================================

        si_data = extract_document(si_text, "SI")
        bl_data = extract_document(bl_text, "BL")

        missing = []

        for field in FIELDS:

            if si_data.get(field) is None:

                missing.append(
                    f"SI:{field}"
                )

                missing_fields[
                    f"SI:{field}"
                ] += 1

            if bl_data.get(field) is None:

                missing.append(
                    f"BL:{field}"
                )

                missing_fields[
                    f"BL:{field}"
                ] += 1

        # =====================================================
        # MISSING FIELD
        # =====================================================

        if missing:

            stats["MISSING_FIELDS"] += 1

            if len(examples) < 10:

                examples.append(
                    (
                        email["email_id"],
                        "MISSING_FIELDS",
                        missing,
                    )
                )

            continue

        # =====================================================
        # FULLY EXTRACTED
        # =====================================================

        stats["FULLY_EXTRACTED"] += 1

        comparison = compare_documents(
            si_data,
            bl_data
        )

        # =====================================================
        # MATCH
        # =====================================================

        if comparison["match"]:

            stats["MATCH"] += 1

        # =====================================================
        # MISMATCH
        # =====================================================

        else:

            stats["MISMATCH"] += 1

            for mismatch in comparison["mismatches"]:

                mismatch_fields[
                    mismatch["field"]
                ] += 1

            if len(examples) < 10:

                examples.append(
                    (
                        email["email_id"],
                        "MISMATCH",
                        comparison["mismatches"],
                    )
                )

    # =========================================================
    # PRINT RESULTS
    # =========================================================

    print()
    print("=" * 80)
    print("PIPELINE DIAGNOSTIC")
    print("=" * 80)

    print()

    print(
        f"Document comparison: {stats['DOCUMENT_COMPARISON']}"
    )

    print(
        f"Has SI + BL:         {stats['HAS_SI_AND_BL']}"
    )

    print(
        f"No SI + no BL:       {stats['NO_SI_AND_BL']}"
    )

    print(
        f"No SI:               {stats['NO_SI']}"
    )

    print(
        f"No BL:               {stats['NO_BL']}"
    )

    print(
        f"Read errors:         {stats['READ_ERROR']}"
    )

    print(
        f"Missing fields:      {stats['MISSING_FIELDS']}"
    )

    print(
        f"Fully extracted:     {stats['FULLY_EXTRACTED']}"
    )

    print(
        f"MATCH:               {stats['MATCH']}"
    )

    print(
        f"MISMATCH:            {stats['MISMATCH']}"
    )

    # =========================================================
    # MISSING FIELD COUNTS
    # =========================================================

    print()
    print("=" * 80)
    print("MISSING FIELD COUNTS")
    print("=" * 80)

    for field, count in missing_fields.most_common():

        print(
            f"{field:<35} {count}"
        )

    # =========================================================
    # MISMATCH FIELD COUNTS
    # =========================================================

    print()
    print("=" * 80)
    print("MISMATCH FIELD COUNTS")
    print("=" * 80)

    for field, count in mismatch_fields.most_common():

        print(
            f"{field:<35} {count}"
        )

    # =========================================================
    # EXAMPLES
    # =========================================================

    print()
    print("=" * 80)
    print("EXAMPLES")
    print("=" * 80)

    for email_id, problem_type, details in examples:

        print()
        print(
            f"{email_id} -> {problem_type}"
        )

        print(details)


if __name__ == "__main__":
    main()