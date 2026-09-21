CATEGORIES = [
    "BL_COMPARISON",
    "SI_REQUEST",
    "INVOICE_QUERY",
    "GENERAL",
    "SPAM",
]


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


def classify_email(email):
    subject = email.get("subject", "")
    body = email.get("body", "")
    text = f"{subject} {body}".lower()
    attachments = email.get("attachments", [])

    # --------------------------------------------------
    # 1. BL COMPARISON
    # --------------------------------------------------
    if classifier_has_si_bl(attachments):
        return "BL_COMPARISON"

    comparison_phrases = [
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
        "please confirm docs",
    ]

    if any(phrase in text for phrase in comparison_phrases):
        return "BL_COMPARISON"

    # --------------------------------------------------
    # 2. SPAM
    # --------------------------------------------------
    spam_phrases = [
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
    ]

    if any(phrase in text for phrase in spam_phrases):
        return "SPAM"

    # --------------------------------------------------
    # 3. SI REQUEST
    # --------------------------------------------------
    si_subject_phrases = [
        "request si",
        "si needed",
        "cust si",
        "submit si",
        "request shipping instruction",
        "shipping instruction needed",
        "shipping instructions needed",
        "prepare si",
        "prepare shipping instruction",
        "send si",
        "send shipping instruction",
    ]

    if any(phrase in subject.lower() for phrase in si_subject_phrases):
        return "SI_REQUEST"

    # --------------------------------------------------
    # 4. INVOICE / BILLING
    # --------------------------------------------------
    invoice_phrases = [
        "invoice",
        "billing",
        "bill amount",
        "local charges",
        "freight charges",
        "total freight",
        "mill d & d charges",
        "telex release charges",
    ]

    if any(phrase in text for phrase in invoice_phrases):
        return "INVOICE_QUERY"

    # --------------------------------------------------
    # 5. GENERAL
    # --------------------------------------------------
    return "GENERAL"