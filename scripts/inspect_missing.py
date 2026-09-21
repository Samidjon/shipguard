#!/usr/bin/env python3
"""
Dump extracted data and raw text for specific emails.

Use this when an email lands on NEEDS_REVIEW / missing_value and you need to
see which label the document actually used.

    python scripts/inspect_missing.py                    # a default sample
    python scripts/inspect_missing.py email_004 email_032
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shipguard.config import get_data_source
from shipguard.document_reader import read_document
from shipguard.extractor import extract_document
from shipguard.loader import Inbox
from shipguard.pipeline import find_attachment


# Shipping documents contain non-ASCII characters; without this the default
# Windows console encoding raises UnicodeEncodeError while printing them.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_EMAILS = [
    "email_004",
    "email_032",
    "email_040",
    "email_051",
    "email_055",
]

RAW_TEXT_LIMIT = 5000


def print_document(label, path, text, data):
    print()
    print("=" * 80)
    print(label)
    print("=" * 80)

    print(f"FILE: {path}")

    print()
    print("--- EXTRACTED DATA ---")

    for key, value in data.items():
        print(f"{key:<25}: {value}")

    print()
    print("--- RAW TEXT ---")
    print(text[:RAW_TEXT_LIMIT])


def main(wanted_emails):

    inbox = Inbox(get_data_source())

    wanted = set(wanted_emails)

    for email in inbox:

        if email["email_id"] not in wanted:
            continue

        print()
        print("#" * 80)
        print(f"EMAIL: {email['email_id']}")
        print("#" * 80)

        print(f"Subject: {email.get('subject', '')}")

        attachments = email.get("attachments", [])

        print()
        print("Attachments:")

        for attachment in attachments:
            print(f"  {attachment}")

        si_path = find_attachment(attachments, "SI")
        bl_path = find_attachment(attachments, "BL")

        print()
        print(f"SI: {si_path}")
        print(f"BL: {bl_path}")

        for label, path, document_type in [
            ("SHIPPING INSTRUCTION", si_path, "SI"),
            ("BILL OF LADING", bl_path, "BL"),
        ]:

            if not path:
                continue

            # Only the read/extract step is guarded, so a printing problem
            # is never misreported as a document read failure.
            try:
                text = read_document(inbox, path)
                data = extract_document(text, document_type)

            except Exception as error:
                print()
                print(f"{document_type} READ ERROR: {error}")
                continue

            print_document(label, path, text, data)


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_EMAILS)
