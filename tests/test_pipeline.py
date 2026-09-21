"""
End-to-end status rules for a single email.

These run against synthetic documents rather than the organizer dataset so
each verdict path is exercised deliberately and in isolation.
"""

import pytest

from shipguard import pipeline
from shipguard.pipeline import (
    detect_wrong_doc_type,
    find_attachment,
    get_missing_fields,
    process_email,
)
from shipguard.config import FIELDS


SI_PATH = "attachments/email_test_SI.txt"
BL_PATH = "attachments/email_test_BL.txt"


def make_email(attachments, subject="TO CONFIRM DOCS _ test", body=""):
    return {
        "email_id": "email_test",
        "subject": subject,
        "body": body,
        "attachments": attachments,
    }


@pytest.fixture
def run_comparison(monkeypatch):
    """
    Run process_email with document contents supplied in memory.
    """

    def run(si_content, bl_content, attachments=None, email=None):

        documents = {}

        if si_content is not None:
            documents[SI_PATH] = si_content

        if bl_content is not None:
            documents[BL_PATH] = bl_content

        def fake_read_document(inbox, path):
            if isinstance(documents.get(path), Exception):
                raise documents[path]
            return documents[path]

        monkeypatch.setattr(pipeline, "read_document", fake_read_document)

        if attachments is None:
            attachments = [SI_PATH, BL_PATH]

        if email is None:
            email = make_email(attachments)

        return process_email(object(), email)

    return run


# =============================================================
# HELPERS
# =============================================================


def test_find_attachment_matches_the_document_suffix():
    attachments = [SI_PATH, BL_PATH]

    assert find_attachment(attachments, "SI") == SI_PATH
    assert find_attachment(attachments, "BL") == BL_PATH


def test_find_attachment_returns_none_when_absent():
    assert find_attachment([SI_PATH], "BL") is None


def test_find_attachment_ignores_the_file_extension():
    attachments = ["attachments/e_SI.xlsx", "attachments/e_BL.pdf"]

    assert find_attachment(attachments, "SI") == "attachments/e_SI.xlsx"
    assert find_attachment(attachments, "BL") == "attachments/e_BL.pdf"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("COMMERCIAL INVOICE\nTotal due", "commercial_invoice"),
        ("PACKING LIST\nCartons", "packing_list"),
        ("CERTIFICATE OF ORIGIN", "certificate_of_origin"),
        ("BILL OF LADING\nShipper: ACME", None),
    ],
)
def test_wrong_document_types_are_detected(text, expected):
    assert detect_wrong_doc_type(text) == expected


def test_missing_fields_are_reported_per_document():
    complete = {field: "value" for field in FIELDS}

    incomplete = dict(complete)
    incomplete["gross_weight_kg"] = None

    assert get_missing_fields(complete, complete) == []
    assert get_missing_fields(incomplete, complete) == ["SI:gross_weight_kg"]
    assert get_missing_fields(complete, incomplete) == ["BL:gross_weight_kg"]


# =============================================================
# STATUS RULE: non-comparison email
# =============================================================


def test_non_comparison_email_is_ok_without_defects():
    email = make_email(
        attachments=[],
        subject="Delivery planning Jan 2026",
        body="Schedule for next month.",
    )

    result = process_email(object(), email)

    assert result["category"] == "GENERAL"
    assert result["status"] == "OK"
    assert result["review_reason"] is None
    assert result["has_defect"] is False
    assert result["defect_fields"] == []


# =============================================================
# STATUS RULE: missing_attachment
# =============================================================


def test_missing_bill_of_lading_needs_review(run_comparison, si_text):
    """An SI arrived but its counterpart did not — a person must chase it."""

    result = run_comparison(
        si_text(),
        None,
        attachments=[SI_PATH],
    )

    assert result["category"] == "BL_COMPARISON"
    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "missing_attachment"
    assert result["has_defect"] is False


def test_missing_shipping_instruction_needs_review(run_comparison, bl_text):
    result = run_comparison(
        None,
        bl_text(),
        attachments=[BL_PATH],
    )

    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "missing_attachment"


def test_unrelated_attachment_without_the_pair_needs_review(run_comparison):
    """
    Something was attached, but neither half of the comparison — still a
    genuine missing-attachment case.
    """

    result = run_comparison(
        None,
        None,
        attachments=["attachments/email_test_invoice.pdf"],
    )

    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "missing_attachment"


def test_comparison_request_with_no_attachments_is_ok(run_comparison):
    """
    "Please send the draft BL for checking" — nothing was attached, so there is
    nothing to compare and nothing has gone wrong. Escalating every such thread
    reply would bury a reviewer in false alarms.
    """

    result = run_comparison(None, None, attachments=[])

    assert result["category"] == "BL_COMPARISON"
    assert result["status"] == "OK"
    assert result["review_reason"] is None
    assert result["has_defect"] is False
    assert result["defect_fields"] == []


# =============================================================
# STATUS RULE: unreadable
# =============================================================


def test_unreadable_document_needs_review(run_comparison, si_text):
    result = run_comparison(
        si_text(),
        ValueError("PDF contains no extractable text"),
    )

    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "unreadable"
    assert result["has_defect"] is False


# =============================================================
# STATUS RULE: wrong_doc_type
# =============================================================


def test_invoice_sent_as_bill_of_lading_needs_review(run_comparison, si_text):
    result = run_comparison(
        si_text(),
        "COMMERCIAL INVOICE\nAmount due: 1000 USD",
    )

    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "wrong_doc_type"
    assert result["has_defect"] is False


# =============================================================
# STATUS RULE: missing_value (never guess)
# =============================================================


def test_field_absent_from_the_si_needs_review(run_comparison, si_text, bl_text):
    result = run_comparison(
        si_text(gross_weight_kg=None),
        bl_text(),
    )

    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "missing_value"
    assert result["has_defect"] is False
    assert "SI:gross_weight_kg" in result["missing"]


def test_placeholder_value_counts_as_missing(run_comparison, si_text, bl_text):
    result = run_comparison(
        si_text(gross_weight_kg="____MT"),
        bl_text(),
    )

    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "missing_value"


# =============================================================
# STATUS RULE: OK
# =============================================================


def test_matching_documents_are_ok(run_comparison, si_text, bl_text):
    result = run_comparison(si_text(), bl_text())

    assert result["category"] == "BL_COMPARISON"
    assert result["status"] == "OK"
    assert result["review_reason"] is None
    assert result["has_defect"] is False
    assert result["defect_fields"] == []


def test_locode_difference_alone_is_still_ok(run_comparison, si_text, bl_text):
    result = run_comparison(
        si_text(port_of_discharge="MOMBASA, KENYA (KEMBA)"),
        bl_text(port_of_discharge="MOMBASA, KENYA"),
    )

    assert result["status"] == "OK"


def test_case_difference_alone_is_still_ok(run_comparison, si_text, bl_text):
    result = run_comparison(
        si_text(shipper="acme exports pte ltd"),
        bl_text(shipper="ACME EXPORTS PTE LTD"),
    )

    assert result["status"] == "OK"


# =============================================================
# STATUS RULE: MISMATCH
# =============================================================


def test_single_differing_field_is_a_mismatch(run_comparison, si_text, bl_text):
    result = run_comparison(
        si_text(),
        bl_text(port_of_discharge="HOUSTON, US"),
    )

    assert result["status"] == "MISMATCH"
    assert result["review_reason"] is None
    assert result["has_defect"] is True
    assert result["defect_fields"] == ["port_of_discharge"]


def test_several_differing_fields_are_all_listed(
    run_comparison, si_text, bl_text
):
    result = run_comparison(
        si_text(),
        bl_text(
            consignee="OTHER CONSIGNEE LLC",
            port_of_loading="PORT KLANG",
            container_count="9",
        ),
    )

    assert result["status"] == "MISMATCH"
    assert result["defect_fields"] == [
        "consignee",
        "port_of_loading",
        "container_count",
    ]


def test_weight_difference_is_a_mismatch(run_comparison, si_text, bl_text):
    result = run_comparison(
        si_text(gross_weight_kg="12500 KG"),
        bl_text(gross_weight_kg="23555 KG"),
    )

    assert result["status"] == "MISMATCH"
    assert result["defect_fields"] == ["gross_weight_kg"]


# =============================================================
# SUBMISSION SHAPE
# =============================================================


def test_result_always_carries_the_submission_keys(
    run_comparison, si_text, bl_text
):
    required = {
        "email_id",
        "category",
        "status",
        "review_reason",
        "has_defect",
        "defect_fields",
    }

    results = [
        run_comparison(si_text(), bl_text()),
        run_comparison(si_text(), bl_text(port_of_loading="PORT KLANG")),
        run_comparison(si_text(gross_weight_kg=None), bl_text()),
        run_comparison(si_text(), "COMMERCIAL INVOICE"),
    ]

    for result in results:
        assert required.issubset(result)


def test_defect_flag_and_fields_stay_consistent(
    run_comparison, si_text, bl_text
):
    ok = run_comparison(si_text(), bl_text())
    mismatch = run_comparison(si_text(), bl_text(shipper="OTHER LTD"))

    assert ok["has_defect"] is False and ok["defect_fields"] == []
    assert mismatch["has_defect"] is True and mismatch["defect_fields"]
