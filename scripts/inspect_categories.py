#!/usr/bin/env python3
"""
Browse emails by classification result.

Prints a category breakdown for the whole inbox, then a sample of emails per
category so classification rules can be eyeballed against real subjects.

    python scripts/inspect_categories.py                 # default categories
    python scripts/inspect_categories.py SPAM GENERAL
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shipguard.classifier import CATEGORIES, classify_email
from shipguard.config import get_data_source
from shipguard.loader import Inbox


# Subjects and bodies contain non-ASCII characters; keep printing them safe
# on the default Windows console encoding.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_CATEGORIES = ["GENERAL", "INVOICE_QUERY", "SPAM"]

SAMPLES_PER_CATEGORY = 10

BODY_PREVIEW = 500


def main(categories_to_show):

    inbox = Inbox(get_data_source())

    emails = inbox.emails()

    classified = [(email, classify_email(email)) for email in emails]

    counts = Counter(category for _, category in classified)

    print("=" * 80)
    print(f"CATEGORY BREAKDOWN ({len(emails)} emails)")
    print("=" * 80)

    for category in CATEGORIES:
        print(f"{category:<20} {counts.get(category, 0)}")

    for category in categories_to_show:

        if category not in CATEGORIES:
            print()
            print(f"Unknown category: {category}")
            continue

        print()
        print("=" * 80)
        print(f"{category} — showing up to {SAMPLES_PER_CATEGORY}")
        print("=" * 80)

        shown = 0

        for email, result in classified:

            if result != category:
                continue

            print()
            print(f"ID: {email['email_id']}")
            print(f"SUBJECT: {email.get('subject', '')}")
            print(f"BODY: {email.get('body', '')[:BODY_PREVIEW]}")
            print(f"ATTACHMENTS: {email.get('attachments', [])}")

            shown += 1

            if shown >= SAMPLES_PER_CATEGORY:
                break


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_CATEGORIES)
