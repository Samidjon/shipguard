import sys
sys.path.append("../sdoc-hackathon-bundle")

from loader import Inbox
from classifier import classify_email

DATASET = "../sdoc-hackathon-bundle"
inbox = Inbox(DATASET)

emails = inbox.emails()

categories_to_show = [
    "GENERAL",
    "INVOICE_QUERY",
    "SPAM",
]

for category in categories_to_show:
    print("\n" + "=" * 80)
    print(category)
    print("=" * 80)

    count = 0

    for email in emails:
        result = classify_email(email)

        if result == category:
            print(f"\nID: {email['email_id']}")
            print(f"SUBJECT: {email.get('subject', '')}")
            print(f"BODY: {email.get('body', '')[:500]}")
            print(f"ATTACHMENTS: {email.get('attachments', [])}")

            count += 1

            if count >= 10:
                break