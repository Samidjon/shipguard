"""
Email classification.

Design note: in this inbox the SUBJECT is deliberately unreliable — a routing
code like ``AFEMY - MOMBASA_KENYA - ...`` or a thread subject like
``TO CONFIRM DOCS`` says little about what the message actually asks for. The
INTENT lives in the body. Rules therefore match the full text (subject + body)
and are ordered so that the strongest evidence wins.
"""

import re


CATEGORIES = [
    "BL_COMPARISON",
    "SI_REQUEST",
    "INVOICE_QUERY",
    "GENERAL",
    "SPAM",
]


# =============================================================
# PHRASE MATCHING
# =============================================================


def _compile(phrase):
    """
    Compile a phrase into a word-boundary pattern.

    Plain substring matching produced false positives (a passing mention of
    "invoice" inside an unrelated sentence decided the category).

    Boundaries are expressed as "not adjacent to a letter or digit" rather than
    with ``\\b``, because these subjects use the underscore as a separator
    ("SI NEEDED_ 5RMY-69379", "CUST SI _ MEA"). ``\\b`` and ``\\w`` treat "_"
    as part of a word, so a plain word-boundary pattern would silently fail on
    exactly the traffic this inbox contains. Internal separators are flexible
    for the same reason, and phrases may contain punctuation such as
    "d & d charges".
    """

    escaped = r"[\s_]+".join(re.escape(part) for part in phrase.split())

    return re.compile(
        r"(?<![0-9A-Za-z])" + escaped + r"(?![0-9A-Za-z])",
        re.IGNORECASE,
    )


def _compile_all(phrases):
    return [_compile(phrase) for phrase in phrases]


def _contains(text, patterns):
    return any(pattern.search(text) for pattern in patterns)


# =============================================================
# 1. DOCUMENT COMPARISON
# =============================================================

# Asking someone to check a draft Bill of Lading against the Shipping
# Instruction. Both the "documents are attached" and the "please send the
# draft for checking" halves of the workflow belong here.
COMPARISON_PHRASES = _compile_all([
    # explicit check/compare requests
    "confirm docs",
    "confirm documents",
    "check docs",
    "check documents",
    "verify docs",
    "verify documents",
    "compare documents",
    "compare docs",
    "document discrepancy",
    "docs discrepancy",
    "discrepancy between",
    "please compare",
    "please verify",
    # the draft-BL review workflow
    "draft bl",
    "bl draft",
    "draft bill of lading",
    "amend bl",
    "for checking",
    "check the details",
    "bl matches the si",
])


# =============================================================
# 2. SPAM
# =============================================================

SPAM_PHRASES = _compile_all([
    "unsubscribe",
    "winner",
    "congratulations",
    "promotion",
    "advertisement",
    "casino",
    "free money",
    "bitcoin investment",
    "guaranteed 300%",
    "exclusive offer",
    "increase your shipping revenue",
    "one weird trick",
    "undelivered messages",
    # phishing and consumer-spam constructions seen in this inbox
    "email storage is full",
    "update your account",
    "avoid suspension",
    "verify your account",
    "hot singles",
    "gift card",
    "you have won",
    "click here",
    # advance-fee fraud: these arrive under a plausible billing subject
    # ("Invoice payment - kindly confirm your bank details"), so the giveaway
    # has to come from the body.
    "hello dear",
    "business proposal",
    "bank officer",
])


# =============================================================
# OPERATIONAL REPORTS
# =============================================================

# Recurring operational traffic: berthing reports, vessel update summaries,
# lists of outstanding BLs. Their SUBJECTS are misleading — a standing
# reminder titled "Submit SI & AED" or an RPA notice titled "Billing Process
# Completed" carries a berthing report in the body and asks nothing of a
# document checker. The body is therefore what decides, and this rule is
# evaluated before the weaker SI and billing keywords.
OPERATIONAL_PHRASES = _compile_all([
    "berthing report",
    "update summary",
    "outstanding bl",
    "loading completed",
    # A broadcast reminder covering the whole backlog ("please submit SI & AED
    # for all pending shipments by end of day") is a standing SLA notice to the
    # team, not a request for one shipment's document.
    "all pending shipments",
])


# =============================================================
# 3. SHIPPING INSTRUCTION REQUEST / TRANSMITTAL
# =============================================================

# An SI transmittal hands over the Shipping Instruction so a Bill of Lading
# can be drawn up. Such messages routinely reference the BL as well ("HOUSE
# BL", "draft BL to follow"), so they must be recognised BEFORE the comparison
# rules or they would be misread as document checks.
#
# Both signals below are template-level and unambiguous: a subject of the form
# "SI - <booking> - ..." and the body line "Please find Shipping instruction
# for <ref>". Comparison emails phrase it differently ("the shipping
# instruction AND the draft bill of lading"), so they do not collide.
SI_TRANSMITTAL_PHRASES = _compile_all([
    "find shipping instruction for",
])

SI_SUBJECT_PATTERN = re.compile(
    r"^\s*(?:(?:re|fw|fwd)[_:\s]+)*si\s*[-_:]",
    re.IGNORECASE,
)

# Explicit requests for an SI. These are unambiguous on their own but are
# checked after the comparison rules, where they have always sat.
#
# "submit si" is deliberately absent: in this traffic it only ever appears in
# the recurring "Submit SI & AED" SLA reminder, which is addressed to the whole
# team about every pending shipment. Treating it as a request produced only
# false positives.
SI_PHRASES = _compile_all([
    "request si",
    "si needed",
    "cust si",
    "request shipping instruction",
    "shipping instruction needed",
    "shipping instructions needed",
    "prepare si",
    "prepare shipping instruction",
    "send si",
    "send shipping instruction",
])


# =============================================================
# 4. AUTOMATED OPERATIONAL NOTIFICATIONS
# =============================================================

# Bot notices such as "The India HSS SD Billing Process ... completed
# successfully. No action required. -- RPA Bot" mention billing but ask
# nothing. They are operational noise, not a billing query, so they are
# recognised before the billing rules run.
AUTOMATED_PHRASES = _compile_all([
    "automated notification",
    "no action required",
    "rpa bot",
])


# =============================================================
# 5. INVOICE / BILLING
# =============================================================

# Billing intent, not a passing mention of the word "invoice".
BILLING_PHRASES = _compile_all([
    "cancel invoice",
    "invoice payment",
    "local charges",
    "freight charges",
    "total freight",
    "d & d charges",
    "telex release",
    "bill amount",
    "rak billing",
    "proceed with billing",
])
# Note "billing process" is deliberately absent: it only occurs in the RPA
# subject "India HSS SD Billing Process Completed", which reports on a finished
# job and asks nothing.

# An invoice carrying a reference number is a concrete billing matter.
INVOICE_REFERENCE_PATTERN = re.compile(
    r"(?<!\w)invoice\s*(?:no\.?|number|#)?\s*\d",
    re.IGNORECASE,
)


# =============================================================
# ATTACHMENTS
# =============================================================


def classifier_has_si_bl(attachments):
    """
    Check whether the email contains both
    Shipping Instruction (SI) and Bill of Lading (BL).
    """

    has_si = False
    has_bl = False

    for attachment in attachments:

        filename = attachment.lower()
        filename = filename.split("/")[-1]

        filename_without_extension = filename.rsplit(".", 1)[0]

        if filename_without_extension.endswith("_si"):
            has_si = True

        if filename_without_extension.endswith("_bl"):
            has_bl = True

    return has_si and has_bl


# =============================================================
# CLASSIFICATION
# =============================================================


def classify_email(email):
    """
    Assign one of CATEGORIES to an email.

    Order matters and is deliberate:

    1. An attached SI + BL pair is the strongest possible evidence of a
       comparison request — nothing may preempt it.
    2. An SI transmittal, identified by its own template. These messages
       mention the BL in passing, so they must be settled before the
       comparison rules look at the text.
    3. Comparison intent in the text, so a document check is never
       reclassified as billing or as general correspondence.
    4. Spam, before the remaining business categories, so promotional mail
       that happens to mention charges is not read as a billing query.
    5. Operational reports, before the weaker SI and billing keywords, so a
       misleading subject cannot hijack a berthing report.
    6. Explicit SI requests.
    7. Automated bot notices before billing, so "billing process completed,
       no action required" is not treated as a billing query.
    8. Billing intent.
    9. Everything else is general correspondence.
    """

    subject = email.get("subject", "") or ""
    body = email.get("body", "") or ""
    text = f"{subject} {body}"
    attachments = email.get("attachments", [])

    # 1. Documents are attached.
    if classifier_has_si_bl(attachments):
        return "BL_COMPARISON"

    # 2. Shipping instruction transmittal.
    if SI_SUBJECT_PATTERN.search(subject) or _contains(
        text, SI_TRANSMITTAL_PHRASES
    ):
        return "SI_REQUEST"

    # 3. Comparison intent.
    if _contains(text, COMPARISON_PHRASES):
        return "BL_COMPARISON"

    # 4. Spam.
    if _contains(text, SPAM_PHRASES):
        return "SPAM"

    # 5. Operational report.
    if _contains(text, OPERATIONAL_PHRASES):
        return "GENERAL"

    # 6. Explicit shipping instruction request.
    if _contains(text, SI_PHRASES):
        return "SI_REQUEST"

    # 7. Automated operational notification.
    if _contains(text, AUTOMATED_PHRASES):
        return "GENERAL"

    # 8. Invoice / billing.
    if _contains(text, BILLING_PHRASES) or INVOICE_REFERENCE_PATTERN.search(text):
        return "INVOICE_QUERY"

    # 9. General correspondence.
    return "GENERAL"
