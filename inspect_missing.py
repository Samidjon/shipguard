from loader import Inbox
from classifier import classify_email
from document_reader import read_document
from extractor import extract_document

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

    print(text[:5000])


def main():
    inbox = Inbox(DATA_SOURCE)

    wanted_emails = [
        "email_004",
        "email_032",
        "email_040",
        "email_051",
        "email_055",
        "email_058",
        "email_059",
        "email_065",
        "email_068",
        "email_091",
    ]

    for email in inbox:

        if email["email_id"] not in wanted_emails:
            continue

        if classify_email(email) != "DOCUMENT_COMPARISON":
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

        if si_path:
            try:
                si_text = read_document(inbox, si_path)
                si_data = extract_document(si_text)

                print_document(
                    "SHIPPING INSTRUCTION",
                    si_path,
                    si_text,
                    si_data
                )

            except Exception as error:
                print()
                print(f"SI READ ERROR: {error}")

        if bl_path:
            try:
                bl_text = read_document(inbox, bl_path)
                bl_data = extract_document(bl_text)

                print_document(
                    "BILL OF LADING",
                    bl_path,
                    bl_text,
                    bl_data
                )

            except Exception as error:
                print()
                print(f"BL READ ERROR: {error}")


if __name__ == "__main__":
    main()