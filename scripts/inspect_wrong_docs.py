#!/usr/bin/env python3
"""
Find attachments labelled as a Bill of Lading that are actually some other
document type.

Reports two groups:

1. what the pipeline already detects (``pipeline.detect_wrong_doc_type``),
   which drives NEEDS_REVIEW / wrong_doc_type;
2. extra phrases the pipeline does NOT currently look for — a candidate list
   for widening the detection, printed separately so the difference between
   current and potential behaviour stays visible.

    python scripts/inspect_wrong_docs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shipguard.config import get_data_source
from shipguard.document_reader import read_document
from shipguard.loader import Inbox
from shipguard.pipeline import detect_wrong_doc_type, find_attachment


# Phrases the pipeline does not check for (yet).
EXTRA_PATTERNS = {
    "not a shipping instruction": "not_si",
    "not an si or bl": "not_si_or_bl",
}


def detect_extra(text):
    lowered = text.lower()

    for phrase, label in EXTRA_PATTERNS.items():
        if phrase in lowered:
            return label

    return None


def main():

    inbox = Inbox(get_data_source())

    print("=" * 80)
    print("CHECKING BL ATTACHMENTS FOR WRONG DOCUMENT TYPES")
    print("=" * 80)

    detected = []
    undetected = []
    unreadable = []

    for email in inbox:

        bl_path = find_attachment(email.get("attachments", []), "BL")

        if not bl_path:
            continue

        try:
            text = read_document(inbox, bl_path)

        except Exception as error:
            unreadable.append((email["email_id"], bl_path, str(error)))
            continue

        doc_type = detect_wrong_doc_type(text)

        if doc_type:
            detected.append((email["email_id"], doc_type, bl_path))
            continue

        extra = detect_extra(text)

        if extra:
            undetected.append((email["email_id"], extra, bl_path))

    print()
    print(f"Detected by the pipeline: {len(detected)}")
    print()

    for email_id, doc_type, path in detected:
        print(f"{email_id} | {doc_type} | {path}")

    print()
    print("=" * 80)
    print(f"NOT detected by the pipeline: {len(undetected)}")
    print("=" * 80)
    print()

    if undetected:
        print(
            "These BL attachments announce they are not an SI/BL but do not "
            "match the pipeline's current wrong_doc_type patterns:"
        )
        print()

    for email_id, doc_type, path in undetected:
        print(f"{email_id} | {doc_type} | {path}")

    print()
    print(f"Unreadable BL attachments: {len(unreadable)}")

    for email_id, path, error in unreadable:
        print(f"{email_id} | {path} | {error}")


if __name__ == "__main__":
    main()
