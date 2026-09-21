import json

from loader import Inbox
from classifier import classify_email
from document_reader import read_document
from extractor import extract_document
from comparator import compare_documents


from pathlib import Path

DATA_SOURCE = Path(__file__).resolve().parent / "sdoc-hackathon-bundle"


FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]


def find_attachment(attachments, document_type):
    """
    Find an attachment ending with _SI or _BL.
    """

    document_type = document_type.lower()

    for attachment in attachments:
        name = attachment.lower()
        filename = name.split("/")[-1]

        # Remove extension
        filename_without_extension = filename.rsplit(".", 1)[0]

        if filename_without_extension.endswith("_" + document_type):
            return attachment

    return None


def get_missing_fields(si_data, bl_data):

    """
    Return missing required fields.
    """

    missing = []

    for field in FIELDS:

        if si_data.get(field) is None:
            missing.append(f"SI:{field}")

        if bl_data.get(field) is None:
            missing.append(f"BL:{field}")

    return missing


def detect_wrong_doc_type(text):
    text_lower = text.lower()

    if "commercial invoice" in text_lower:
        return "commercial_invoice"

    if "packing list" in text_lower:
        return "packing_list"

    if "certificate of origin" in text_lower:
        return "certificate_of_origin"

    return None


def process_email(inbox, email):

    email_id = email["email_id"]

    # =========================================================
    # 1. CLASSIFY EMAIL
    # =========================================================

    category = classify_email(email)

    # =========================================================
    # 2. NON-BL-COMPARISON EMAIL
    # =========================================================

    if category != "BL_COMPARISON":

        return {
            "email_id": email_id,
            "category": category,
            "status": "OK",
            "review_reason": None,
            "has_defect": False,
            "defect_fields": [],
        }

    # =========================================================
    # 3. FIND SI / BL
    # =========================================================

    attachments = email.get("attachments", [])

    si_path = find_attachment(attachments, "SI")
    bl_path = find_attachment(attachments, "BL")

    if not si_path or not bl_path:

        return {
            "email_id": email_id,
            "category": "BL_COMPARISON",
            "status": "NEEDS_REVIEW",
            "review_reason": "missing_attachment",
            "has_defect": False,
            "defect_fields": [],
        }

    # =========================================================
    # 4. READ DOCUMENTS
    # =========================================================

    try:
        si_text = read_document(inbox, si_path)
        bl_text = read_document(inbox, bl_path)
    except Exception:
        return {
            "email_id": email_id,
            "category": "BL_COMPARISON",
            "status": "NEEDS_REVIEW",
            "review_reason": "unreadable",
            "has_defect": False,
            "defect_fields": [],
        }

    # Check whether the attachment labelled as BL
    # is actually a different document type.
    wrong_doc_type = detect_wrong_doc_type(bl_text)
    
    if wrong_doc_type:
        return {
            "email_id": email_id,
            "category": "BL_COMPARISON",
            "status": "NEEDS_REVIEW",
            "review_reason": "wrong_doc_type",
            "has_defect": False,
            "defect_fields": [],
        }
    
    try:
        si_data = extract_document(si_text, "SI")
        bl_data = extract_document(bl_text, "BL")
    
    except Exception:
    
        return {
            "email_id": email_id,
            "category": "BL_COMPARISON",
            "status": "NEEDS_REVIEW",
            "review_reason": "unreadable",
            "has_defect": False,
            "defect_fields": [],
        }

    # =========================================================
    # 6. CHECK MISSING FIELDS
    # =========================================================

    missing = get_missing_fields(si_data, bl_data)

    if missing:

        return {
            "email_id": email_id,
            "category": "BL_COMPARISON",
            "status": "NEEDS_REVIEW",
            "review_reason": "missing_value",
            "has_defect": False,
            "defect_fields": [],

            # Diagnostic information.
            # This stays in results.json and is NOT included
            # in the official submission.json.
            "missing": missing,
            "si": si_data,
            "bl": bl_data,
        }   

    # =========================================================
    # 7. COMPARE SI VS BL
    # =========================================================

    comparison = compare_documents(
        si_data,
        bl_data
    )

    # =========================================================
    # 8. ALL FIELDS MATCH
    # =========================================================

    if comparison["match"]:

        return {
            "email_id": email_id,
            "category": "BL_COMPARISON",
            "status": "OK",
            "review_reason": None,
            "has_defect": False,
            "defect_fields": [],
        }

    # =========================================================
    # 9. MISMATCH
    # =========================================================

    defect_fields = []

    for mismatch in comparison["mismatches"]:

        field = mismatch["field"]

        if field not in defect_fields:
            defect_fields.append(field)

    return {
        "email_id": email_id,
        "category": "BL_COMPARISON",
        "status": "MISMATCH",
        "review_reason": None,
        "has_defect": True,
        "defect_fields": defect_fields,
    }


def main():

    print("Loading dataset...")

    inbox = Inbox(DATA_SOURCE)

    emails = list(inbox)

    print(f"Total emails: {len(emails)}")

    print()

    print("=" * 80)
    print("PROCESSING")
    print("=" * 80)

    results = []

    for index, email in enumerate(emails, start=1):

        result = process_email(
            inbox,
            email
        )

        results.append(result)

        if index % 50 == 0:
            print(
                f"Processed {index}/{len(emails)}"
            )

    # =========================================================
    # STATISTICS
    # =========================================================

    counts = {
        "OK": 0,
        "MISMATCH": 0,
        "NEEDS_REVIEW": 0,
    }

    category_counts = {
        "BL_COMPARISON": 0,
        "SI_REQUEST": 0,
        "INVOICE_QUERY": 0,
        "GENERAL": 0,
        "SPAM": 0,
    }

    for result in results:

        status = result["status"]

        if status in counts:
            counts[status] += 1

        category = result["category"]

        if category in category_counts:
            category_counts[category] += 1

    # =========================================================
    # SAVE FULL RESULTS
    # =========================================================

    with open(
        "results.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # =========================================================
    # CREATE OFFICIAL SUBMISSION
    # =========================================================

    submission = {}

    for result in results:

        email_id = result["email_id"]

        submission[email_id] = {
            "category": result["category"],
            "status": result["status"],
            "review_reason": result["review_reason"],
            "has_defect": result["has_defect"],
            "defect_fields": result["defect_fields"],
        }

    with open(
        "submission.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            submission,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # =========================================================
    # PRINT RESULTS
    # =========================================================

    print()

    print("=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"OK:             {counts['OK']}")
    print(f"MISMATCH:       {counts['MISMATCH']}")
    print(f"NEEDS_REVIEW:   {counts['NEEDS_REVIEW']}")

    print()

    print("CATEGORIES")
    print("=" * 80)

    for category, count in category_counts.items():
        print(f"{category}: {count}")

    print()

    print(f"Processed:      {len(results)}")

    print()

    print("Created:")
    print("  results.json")
    print("  submission.json")


if __name__ == "__main__":
    main()