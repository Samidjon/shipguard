#!/usr/bin/env python3
"""
Where does the pipeline lose document comparisons?

Counts every stage of the BL_COMPARISON path — attachments found, read
errors, missing fields, matches and mismatches — and prints the most common
missing/mismatching fields plus a handful of examples.

    python scripts/diagnose_pipeline.py
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shipguard.classifier import classify_email
from shipguard.comparator import compare_documents
from shipguard.config import FIELDS, get_data_source
from shipguard.document_reader import read_document
from shipguard.extractor import extract_document
from shipguard.loader import Inbox
from shipguard.pipeline import find_attachment


# Example values printed below come from the documents themselves and can be
# non-ASCII; keep output safe on the default Windows console encoding.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():

    inbox = Inbox(get_data_source())

    emails = list(inbox)

    stats = Counter()
    missing_fields = Counter()
    mismatch_fields = Counter()
    examples = []

    for email in emails:

        if classify_email(email) != "BL_COMPARISON":
            continue

        stats["BL_COMPARISON"] += 1

        attachments = email.get("attachments", [])

        si_path = find_attachment(attachments, "SI")
        bl_path = find_attachment(attachments, "BL")

        # -----------------------------------------------------
        # ATTACHMENT CHECK
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # READ DOCUMENTS
        # -----------------------------------------------------

        try:
            si_text = read_document(inbox, si_path)
            bl_text = read_document(inbox, bl_path)

        except Exception as error:

            stats["READ_ERROR"] += 1

            if len(examples) < 10:
                examples.append(
                    (email["email_id"], "READ_ERROR", str(error))
                )

            continue

        # -----------------------------------------------------
        # EXTRACT
        # -----------------------------------------------------

        si_data = extract_document(si_text, "SI")
        bl_data = extract_document(bl_text, "BL")

        missing = []

        for field in FIELDS:

            if si_data.get(field) is None:
                missing.append(f"SI:{field}")
                missing_fields[f"SI:{field}"] += 1

            if bl_data.get(field) is None:
                missing.append(f"BL:{field}")
                missing_fields[f"BL:{field}"] += 1

        if missing:

            stats["MISSING_FIELDS"] += 1

            if len(examples) < 10:
                examples.append(
                    (email["email_id"], "MISSING_FIELDS", missing)
                )

            continue

        # -----------------------------------------------------
        # COMPARE
        # -----------------------------------------------------

        stats["FULLY_EXTRACTED"] += 1

        comparison = compare_documents(si_data, bl_data)

        if comparison["match"]:
            stats["MATCH"] += 1
            continue

        stats["MISMATCH"] += 1

        for mismatch in comparison["mismatches"]:
            mismatch_fields[mismatch["field"]] += 1

        if len(examples) < 10:
            examples.append(
                (
                    email["email_id"],
                    "MISMATCH",
                    comparison["mismatches"],
                )
            )

    # =========================================================
    # REPORT
    # =========================================================

    print()
    print("=" * 80)
    print("PIPELINE DIAGNOSTIC")
    print("=" * 80)
    print()

    print(f"Total emails:        {len(emails)}")
    print(f"BL comparison:       {stats['BL_COMPARISON']}")
    print(f"Has SI + BL:         {stats['HAS_SI_AND_BL']}")
    print(f"No SI + no BL:       {stats['NO_SI_AND_BL']}")
    print(f"No SI:               {stats['NO_SI']}")
    print(f"No BL:               {stats['NO_BL']}")
    print(f"Read errors:         {stats['READ_ERROR']}")
    print(f"Missing fields:      {stats['MISSING_FIELDS']}")
    print(f"Fully extracted:     {stats['FULLY_EXTRACTED']}")
    print(f"MATCH:               {stats['MATCH']}")
    print(f"MISMATCH:            {stats['MISMATCH']}")

    print()
    print("=" * 80)
    print("MISSING FIELD COUNTS")
    print("=" * 80)

    for field, count in missing_fields.most_common():
        print(f"{field:<35} {count}")

    print()
    print("=" * 80)
    print("MISMATCH FIELD COUNTS")
    print("=" * 80)

    for field, count in mismatch_fields.most_common():
        print(f"{field:<35} {count}")

    print()
    print("=" * 80)
    print("EXAMPLES")
    print("=" * 80)

    for email_id, problem_type, details in examples:
        print()
        print(f"{email_id} -> {problem_type}")
        print(details)


if __name__ == "__main__":
    main()
