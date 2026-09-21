#!/usr/bin/env python3
"""
Show SI vs BL field values for emails the pipeline flags as MISMATCH.

Only emails where every required field was extracted from both documents
are shown, so the differences printed here are real defects rather than
extraction gaps.

    python scripts/inspect_mismatches.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shipguard.classifier import classify_email
from shipguard.comparator import compare_documents
from shipguard.config import FIELDS, get_data_source
from shipguard.document_reader import read_document
from shipguard.extractor import extract_document
from shipguard.loader import Inbox
from shipguard.pipeline import find_attachment


# Document values contain non-ASCII characters; keep printing them safe on
# the default Windows console encoding.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


LIMIT = 20


def main():

    inbox = Inbox(get_data_source())

    count = 0

    for email in inbox:

        if classify_email(email) != "BL_COMPARISON":
            continue

        attachments = email.get("attachments", [])

        si_path = find_attachment(attachments, "SI")
        bl_path = find_attachment(attachments, "BL")

        if not si_path or not bl_path:
            continue

        try:
            si_data = extract_document(read_document(inbox, si_path), "SI")
            bl_data = extract_document(read_document(inbox, bl_path), "BL")

        except Exception:
            continue

        incomplete = any(
            si_data.get(field) is None or bl_data.get(field) is None
            for field in FIELDS
        )

        if incomplete:
            continue

        result = compare_documents(si_data, bl_data)

        if result["match"]:
            continue

        count += 1

        print()
        print("=" * 80)
        print(email["email_id"])
        print("=" * 80)

        print()
        print("SI:")
        for field in FIELDS:
            print(f"{field:<25}: {si_data.get(field)}")

        print()
        print("BL:")
        for field in FIELDS:
            print(f"{field:<25}: {bl_data.get(field)}")

        print()
        print("MISMATCHES:")

        for mismatch in result["mismatches"]:
            print(mismatch)

        if count >= LIMIT:
            break

    print()
    print(f"Shown: {count} (limit {LIMIT})")


if __name__ == "__main__":
    main()
