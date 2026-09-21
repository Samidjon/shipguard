import sys

sys.path.append("../sdoc-hackathon-bundle")

from loader import Inbox
from extractor import extract_document
from comparator import compare_documents


DATASET = "../sdoc-hackathon-bundle"


def process_email(inbox, email):
    """
    Process one email.

    Currently we only process emails that have
    exactly two attachments: SI and BL.
    """

    attachments = email.get("attachments", [])

    si_attachment = None
    bl_attachment = None

    for attachment in attachments:
        attachment_lower = attachment.lower()

        if "_si." in attachment_lower:
            si_attachment = attachment

        elif "_bl." in attachment_lower:
            bl_attachment = attachment

    # Not a document comparison email
    if not si_attachment or not bl_attachment:
        return {
            "email_id": email["email_id"],
            "status": "SKIPPED",
            "reason": "SI/BL pair not found",
        }

    # Currently only process TXT files
    if not si_attachment.endswith(".txt") or not bl_attachment.endswith(".txt"):
        return {
            "email_id": email["email_id"],
            "status": "NEEDS_REVIEW",
            "reason": "Non-TXT documents",
            "si": si_attachment,
            "bl": bl_attachment,
        }

    # Read documents
    si_text = inbox.read_text(si_attachment)
    bl_text = inbox.read_text(bl_attachment)

    # Extract fields
    si_data = extract_document(si_text)
    bl_data = extract_document(bl_text)

    # Compare
    comparison = compare_documents(si_data, bl_data)

    return {
        "email_id": email["email_id"],
        "status": "MATCH" if comparison["match"] else "MISMATCH",
        "si": si_attachment,
        "bl": bl_attachment,
        "mismatches": comparison["mismatches"],
    }


def process_all():

    inbox = Inbox(DATASET)

    emails = inbox.emails()

    print(f"Processing {len(emails)} emails...")
    print()

    results = []

    for index, email in enumerate(emails, start=1):

        result = process_email(inbox, email)

        results.append(result)

        print(
            f"[{index}/{len(emails)}] "
            f"{result['email_id']} → {result['status']}"
        )

    return results


if __name__ == "__main__":

    results = process_all()

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total = len(results)

    match = sum(
        1 for r in results
        if r["status"] == "MATCH"
    )

    mismatch = sum(
        1 for r in results
        if r["status"] == "MISMATCH"
    )

    skipped = sum(
        1 for r in results
        if r["status"] == "SKIPPED"
    )

    review = sum(
        1 for r in results
        if r["status"] == "NEEDS_REVIEW"
    )

    print("Total:", total)
    print("Match:", match)
    print("Mismatch:", mismatch)
    print("Skipped:", skipped)
    print("Needs review:", review)