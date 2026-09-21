import sys

sys.path.append("../sdoc-hackathon-bundle")

from loader import Inbox
from extractor import extract_document
from comparator import compare_documents


DATASET = "../sdoc-hackathon-bundle"

inbox = Inbox(DATASET)

email = inbox.get("email_001")

si_data = None
bl_data = None

for attachment in email["attachments"]:

    if attachment.endswith(".txt"):

        text = inbox.read_text(attachment)
        data = extract_document(text)

        if "_SI." in attachment:
            si_data = data

        elif "_BL." in attachment:
            bl_data = data


print("=" * 70)
print("DOCUMENT COMPARISON")
print("=" * 70)

result = compare_documents(si_data, bl_data)

if result["match"]:

    print("✅ NO MISMATCH DETECTED")

else:

    print("❌ MISMATCH DETECTED")

    for mismatch in result["mismatches"]:

        print()
        print("Field:", mismatch["field"])
        print("SI:", mismatch["si"])
        print("BL:", mismatch["bl"])