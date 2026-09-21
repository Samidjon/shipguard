import sys

sys.path.append("../sdoc-hackathon-bundle")

from loader import Inbox
from document_reader import read_document


DATASET = "../sdoc-hackathon-bundle"

inbox = Inbox(DATASET)


test_files = [
    "attachments/email_001_SI.txt",
    "attachments/email_005_SI.xlsx",
]


for attachment in test_files:

    print("=" * 70)
    print(attachment)
    print("=" * 70)

    try:
        text = read_document(inbox, attachment)

        print(text[:2000])

        print("\nCharacters:", len(text))

    except Exception as e:
        print("ERROR:", e)