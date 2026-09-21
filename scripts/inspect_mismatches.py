from loader import Inbox
from classifier import classify_email
from document_reader import read_document
from extractor import extract_document
from comparator import compare_documents

DATA_SOURCE = r"C:\Users\suley\Documents\hackathon\sdoc-hackathon-bundle"


def find_attachment(attachments, document_type):
    document_type = document_type.lower()

    for attachment in attachments:
        filename = attachment.lower()
        filename = filename.split("/")[-1]
        filename_without_extension = filename.rsplit(".", 1)[0]

        if filename_without_extension.endswith("_" + document_type):
            return attachment

    return None


def main():

    inbox = Inbox(DATA_SOURCE)

    count = 0

    for email in inbox:

        if classify_email(email) != "DOCUMENT_COMPARISON":
            continue

        attachments = email.get("attachments", [])

        si_path = find_attachment(attachments, "SI")
        bl_path = find_attachment(attachments, "BL")

        if not si_path or not bl_path:
            continue

        try:
            si_text = read_document(inbox, si_path)
            bl_text = read_document(inbox, bl_path)

            si_data = extract_document(si_text, "SI")
            bl_data = extract_document(bl_text, "BL")

        except Exception:
            continue

        fields = [
            "shipper",
            "consignee",
            "notify_party",
            "port_of_loading",
            "port_of_discharge",
            "container_count",
            "gross_weight_kg",
        ]

        if any(
            si_data.get(field) is None or bl_data.get(field) is None
            for field in fields
        ):
            continue

        result = compare_documents(si_data, bl_data)

        if not result["match"]:

            count += 1

            print()
            print("=" * 80)
            print(f"{email['email_id']}")
            print("=" * 80)

            print()
            print("SI:")
            for field in fields:
                print(f"{field:<25}: {si_data.get(field)}")

            print()
            print("BL:")
            for field in fields:
                print(f"{field:<25}: {bl_data.get(field)}")

            print()
            print("MISMATCHES:")

            for mismatch in result["mismatches"]:
                print(mismatch)

            print()

            if count >= 20:
                break


if __name__ == "__main__":
    main()