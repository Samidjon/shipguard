import sys

sys.path.append("../sdoc-hackathon-bundle")

from loader import Inbox
from classifier import classify_email


DATASET = "../sdoc-hackathon-bundle"

inbox = Inbox(DATASET)

emails = inbox.emails()

print("=" * 70)
print("EMAIL CLASSIFICATION")
print("=" * 70)

counts = {}

for email in emails:

    category = classify_email(email)

    counts[category] = counts.get(category, 0) + 1

    print(
        f"{email['email_id']:>10} → {category}"
    )


print()
print("=" * 70)
print("CLASSIFICATION SUMMARY")
print("=" * 70)

for category, count in counts.items():

    print(f"{category:<25} {count}")