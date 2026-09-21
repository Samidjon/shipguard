"""
Classification decides whether a document comparison runs at all, so both
the individual rules and their precedence order matter.
"""

import pytest

from shipguard.classifier import (
    CATEGORIES,
    _compile,
    classifier_has_si_bl,
    classify_email,
)


def make_email(subject="", body="", attachments=None):
    return {
        "email_id": "email_test",
        "subject": subject,
        "body": body,
        "attachments": attachments or [],
    }


# =============================================================
# SI / BL ATTACHMENT DETECTION
# =============================================================


def test_si_and_bl_attachments_are_detected():
    assert classifier_has_si_bl(
        ["attachments/email_001_SI.txt", "attachments/email_001_BL.txt"]
    )


def test_detection_is_case_insensitive_and_format_agnostic():
    assert classifier_has_si_bl(
        ["attachments/email_005_si.xlsx", "attachments/email_005_bl.pdf"]
    )


@pytest.mark.parametrize(
    "attachments",
    [
        [],
        ["attachments/email_001_SI.txt"],
        ["attachments/email_001_BL.txt"],
        ["attachments/email_001_invoice.pdf"],
    ],
)
def test_incomplete_attachment_pairs_are_not_detected(attachments):
    assert not classifier_has_si_bl(attachments)


# =============================================================
# CATEGORY RULES
# =============================================================


def test_si_and_bl_pair_classifies_as_comparison():
    email = make_email(
        subject="Delivery planning",
        attachments=[
            "attachments/email_001_SI.txt",
            "attachments/email_001_BL.txt",
        ],
    )

    assert classify_email(email) == "BL_COMPARISON"


@pytest.mark.parametrize(
    "subject",
    [
        "TO CONFIRM DOCS _ 5RSG-00133",
        "Please verify the draft",
        "Document discrepancy found",
        "Please compare the attached",
    ],
)
def test_comparison_phrases_classify_as_comparison(subject):
    assert classify_email(make_email(subject=subject)) == "BL_COMPARISON"


@pytest.mark.parametrize(
    "subject",
    [
        "Increase your shipping revenue with this ONE weird trick",
        "Congratulations, you are our winner",
        "Exclusive offer inside",
        "Click here to unsubscribe",
    ],
)
def test_promotional_mail_classifies_as_spam(subject):
    assert classify_email(make_email(subject=subject)) == "SPAM"


@pytest.mark.parametrize(
    "subject",
    [
        "REQUEST SI _ 5SUS-88442",
        "SI NEEDED_ 5RMY-69379",
        "CUST SI _ MEA _ 5RCY-52735",
        "Please send shipping instruction",
    ],
)
def test_si_requests_are_recognised_from_the_subject(subject):
    assert classify_email(make_email(subject=subject)) == "SI_REQUEST"


@pytest.mark.parametrize(
    "subject",
    [
        "REQUEST TO CANCEL INVOICE -5250070084",
        "Total Freight - INDIA - 5RSG-70551",
        "LOCAL CHARGES FOB",
        "TELEX RELEASE CHARGES",
    ],
)
def test_billing_mail_classifies_as_invoice_query(subject):
    assert classify_email(make_email(subject=subject)) == "INVOICE_QUERY"


def test_ordinary_shipping_mail_falls_back_to_general():
    email = make_email(
        subject="Delivery planning Jan 2026",
        body="Please find the schedule for next month attached.",
    )

    assert classify_email(email) == "GENERAL"


def test_missing_subject_and_body_do_not_crash():
    assert classify_email({"email_id": "x"}) == "GENERAL"


# =============================================================
# PRECEDENCE
# =============================================================


def test_attachment_pair_wins_over_promotional_wording():
    """
    A real SI/BL pair must be compared even if the text looks like spam.
    """

    email = make_email(
        subject="Congratulations, exclusive offer",
        attachments=[
            "attachments/email_001_SI.txt",
            "attachments/email_001_BL.txt",
        ],
    )

    assert classify_email(email) == "BL_COMPARISON"


def test_spam_is_checked_before_invoice_wording():
    email = make_email(
        subject="Exclusive offer",
        body="Reduce your invoice charges today. Unsubscribe here.",
    )

    assert classify_email(email) == "SPAM"


def test_comparison_request_wins_over_invoice_wording():
    email = make_email(
        subject="Please verify documents",
        body="The invoice is attached as well.",
    )

    assert classify_email(email) == "BL_COMPARISON"


def test_every_result_is_a_known_category():
    emails = [
        make_email(subject="TO CONFIRM DOCS"),
        make_email(subject="REQUEST SI _ 123"),
        make_email(subject="Total Freight"),
        make_email(subject="Congratulations winner"),
        make_email(subject="Delivery planning"),
    ]

    for email in emails:
        assert classify_email(email) in CATEGORIES


# =============================================================
# WHOLE-DATASET SANITY (replaces the old print-only script)
# =============================================================


def test_real_inbox_classifies_into_a_sane_distribution(dataset_dir):
    """
    Guards against a rule change that quietly collapses everything into one
    bucket — the failure mode a print-only script could not catch.
    """

    from shipguard.loader import Inbox

    emails = Inbox(dataset_dir).emails()

    assert emails

    counts = {}

    for email in emails:
        category = classify_email(email)
        counts[category] = counts.get(category, 0) + 1

    # Every category must be represented in this dataset.
    assert set(counts) == set(CATEGORIES), counts

    # No single category may swallow the whole inbox.
    assert max(counts.values()) < len(emails) * 0.9, counts

    # Document comparisons are the core workload and must be found.
    assert counts["BL_COMPARISON"] > 0


# =============================================================
# PHRASE MATCHING
# =============================================================


def test_matcher_treats_underscore_as_a_separator():
    """
    These subjects separate words with underscores ("SI NEEDED_ 5RMY-69379").
    Regex \\b and \\w count "_" as part of a word, so a naive word-boundary
    pattern would silently fail on exactly this traffic.
    """

    pattern = _compile("si needed")

    assert pattern.search("SI NEEDED_ 5RMY-69379")
    assert pattern.search("si_needed")
    assert pattern.search("... SI NEEDED ...")


def test_matcher_requires_whole_words():
    pattern = _compile("invoice")

    assert pattern.search("Query on invoice 123")
    assert not pattern.search("prepaidinvoice")
    assert not pattern.search("invoiced2")


def test_matcher_tolerates_punctuation_in_the_phrase():
    pattern = _compile("d & d charges")

    assert pattern.search("Mill D & D charges - 6437419879")


# =============================================================
# COMPARISON DETECTION
# =============================================================


@pytest.mark.parametrize(
    "body",
    [
        "Please assist to send the draft BL for SIN513709859 for checking asap.",
        "Kindly verify the BL matches the SI before we release to the line.",
        "Attached are the SI and draft BL. Please check the details and confirm.",
        "Please find attached the draft bill of lading for your confirmation.",
        "Draft BL MMSS 2507 - amend BL 058",
    ],
)
def test_draft_bl_review_requests_are_comparisons(body):
    """
    The dominant missed pattern: a routing-code subject with the real intent
    stated in the body.
    """

    email = make_email(
        subject="AFEMY - ASHDOD_ISRAEL - EVER(EGLV332003791769) - 5RAE-20163",
        body=body,
    )

    assert classify_email(email) == "BL_COMPARISON"


def test_request_bl_draft_subject_is_a_comparison():
    email = make_email(subject="REQUEST BL DRAFT _ PO 26067_ COATED IVORY BOARD")

    assert classify_email(email) == "BL_COMPARISON"


def test_comparison_wins_over_promotional_wording():
    """Comparison is evaluated before spam, by design."""

    email = make_email(
        subject="Exclusive offer",
        body="Please check the details of the draft BL and confirm.",
    )

    assert classify_email(email) == "BL_COMPARISON"


# =============================================================
# SI TRANSMITTAL
# =============================================================


def test_si_transmittal_subject_template_is_an_si_request():
    email = make_email(
        subject="SI - OOLU5310033092 - DIRECT(OOCL) - 5AAT-45299 - HOUSE BL",
        body="Hi Teo Please find Shipping instruction for 5AAT-45299. POL: ...",
    )

    assert classify_email(email) == "SI_REQUEST"


def test_si_transmittal_is_not_mistaken_for_a_comparison():
    """
    An SI transmittal routinely names the BL ("HOUSE BL", "SURR BL"), so it
    must be settled before the comparison rules read the text.
    """

    email = make_email(
        subject="RE_ SI - SIN706562729 - DIRECT(PIL) - 5RCY-72046 - SURR BL",
        body="Please find Shipping instruction for 5RCY-72046. POL: SINGAPORE",
    )

    assert classify_email(email) == "SI_REQUEST"


def test_si_transmittal_detected_from_the_body_alone():
    email = make_email(
        subject="AFPTME - SAVANNAH_US - MONTER(MCLSIN2316658)",
        body="Hi Lee Please find Shipping instruction for 5RCY-72046. POL: ...",
    )

    assert classify_email(email) == "SI_REQUEST"


# =============================================================
# BILLING NARROWED TO REAL INTENT
# =============================================================


def test_passing_mention_of_invoice_is_not_a_billing_query():
    """
    The bare word "invoice" used to decide the category and produced 67 false
    positives.
    """

    email = make_email(
        subject="Delivery planning Jan 2026",
        body="The invoice will follow separately once loading completes.",
    )

    assert classify_email(email) != "INVOICE_QUERY"


@pytest.mark.parametrize(
    "subject, body",
    [
        ("REQUEST TO CANCEL INVOICE -5250070084", "Requesting to cancel invoice."),
        ("Total Freight - INDIA - 5ALT-38425", "Query on the freight breakdown."),
        ("2115 RAK BILLING 5070146244 MISSING GR", "GR missing, cannot bill."),
        ("Mill D & D charges - 6437419879", "Please confirm the amount."),
        ("Charges query", "Query on invoice 5250075931: is the THC included?"),
    ],
)
def test_real_billing_intent_is_an_invoice_query(subject, body):
    assert classify_email(make_email(subject=subject, body=body)) == "INVOICE_QUERY"


# =============================================================
# OPERATIONAL REPORTS BEAT MISLEADING SUBJECTS
# =============================================================


@pytest.mark.parametrize(
    "body",
    [
        "Kindly find the daily berthing report attached. Vessel berthed on schedule.",
        "Please find attached the update summary for SOLID 16 V.044NW2.",
        "Please find attached the list of outstanding BL (BDP SG).",
        "Reminder: Please submit SI & AED for all pending shipments by end of day.",
    ],
)
def test_operational_reports_are_general_despite_the_subject(body):
    """
    A standing reminder titled "Submit SI & AED" or an RPA notice titled
    "Billing Process Completed" carries an operational report in the body and
    asks nothing of a document checker.
    """

    email = make_email(
        subject="_Reminder_Paper - Submit SI & AED_13-01-2026",
        body=body,
    )

    assert classify_email(email) == "GENERAL"


def test_automated_bot_notice_is_general_not_billing():
    email = make_email(
        subject="_RPA_ India HSS SD Billing Process Completed - LE HAVRE",
        body=(
            "This is an automated notification. The India HSS SD Billing "
            "Process has completed successfully. No action required. -- RPA Bot"
        ),
    )

    assert classify_email(email) == "GENERAL"


# =============================================================
# SPAM COVERAGE
# =============================================================


@pytest.mark.parametrize(
    "subject, body",
    [
        ("Urgent: your email storage is full", "Click here to keep your mailbox."),
        ("Dear valued customer", "Update your account to avoid suspension."),
        ("Hot singles in your area want to connect", ""),
        ("Congratulations! You have won a $1,000 gift card", ""),
    ],
)
def test_additional_spam_constructions_are_detected(subject, body):
    assert classify_email(make_email(subject=subject, body=body)) == "SPAM"


def test_advance_fee_fraud_under_a_billing_subject_is_spam():
    """
    Arrives as "Invoice payment - kindly confirm your bank details"; only the
    body gives it away.
    """

    email = make_email(
        subject="Re: Invoice payment - kindly confirm your bank details",
        body=(
            "Hello Dear, I am a bank officer with an urgent business proposal "
            "involving USD 4.5 million. Please reply with your bank details."
        ),
    )

    assert classify_email(email) == "SPAM"
