from loader import Inbox
from document_reader import read_document
from pathlib import Path


DATA_SOURCE = r"C:\Users\suley\Documents\hackathon\sdoc-hackathon-bundle"


def detect_wrong_doc_type(text):
    text_lower = text.lower()

    if "commercial invoice" in text_lower:
        return "commercial_invoice"

    if "packing list" in text_lower:
        return "packing_list"

    if "certificate of origin" in text_lower:
        return "certificate_of_origin"

    if "not a shipping instruction" in text_lower:
        return "not_si"

    if "not an si or bl" in text_lower:
        return "not_si_or_bl"

    return None


def main():
    inbox = Inbox(DATA_SOURCE)

    print("=" * 80)
    print("CHECKING BL ATTACHMENTS FOR WRONG DOCUMENT TYPES")
    print("=" * 80)

    found = []

    for email in inbox:
        email_id = email["email_id"]

        for attachment in email.get("attachments", []):
            filename = Path(attachment).name.lower()

            if not filename.endswith("_bl.txt"):
                continue

            try:
                text = read_document(inbox, attachment)
            except Exception:
                continue

            doc_type = detect_wrong_doc_type(text)

            if doc_type:
                found.append({
                    "email_id": email_id,
                    "attachment": attachment,
                    "doc_type": doc_type,
                })

    print()
    print(f"Found: {len(found)}")
    print()

    for item in found:
        print(
            item["email_id"],
            "|",
            item["doc_type"],
            "|",
            item["attachment"],
        )


if __name__ == "__main__":
    main()