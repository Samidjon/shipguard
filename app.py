import json
from pathlib import Path

import pandas as pd
import streamlit as st

from loader import Inbox
from pipeline import process_email, DATA_SOURCE
from document_reader import read_document
from extractor import extract_document
from ai_service import (
    analyze_shipping_email,
    analyze_document_discrepancies,
)


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="ShipGuard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(59,130,246,0.10), transparent 30%),
            radial-gradient(circle at top right, rgba(139,92,246,0.08), transparent 30%),
            #0b1020;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1450px;
    }

    /* Header */

    .sg-header {
        padding: 1.4rem 1.6rem;
        border-radius: 18px;
        background: linear-gradient(
            135deg,
            rgba(30,41,59,0.95),
            rgba(15,23,42,0.95)
        );
        border: 1px solid rgba(148,163,184,0.15);
        margin-bottom: 1.5rem;
        box-shadow: 0 12px 40px rgba(0,0,0,0.20);
    }

    .sg-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0;
        color: #f8fafc;
        letter-spacing: -0.03em;
    }

    .sg-subtitle {
        margin-top: 0.35rem;
        color: #94a3b8;
        font-size: 0.95rem;
    }

    /* Cards */

    .sg-card {
        padding: 1.2rem;
        border-radius: 16px;
        background: rgba(15,23,42,0.82);
        border: 1px solid rgba(148,163,184,0.13);
        box-shadow: 0 8px 25px rgba(0,0,0,0.16);
        margin-bottom: 1rem;
    }

    .sg-card-title {
        font-size: 0.78rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.35rem;
    }

    .sg-card-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fafc;
    }

    /* AI */

    .sg-ai {
        padding: 1.25rem;
        border-radius: 16px;
        background:
            linear-gradient(
                135deg,
                rgba(30,41,59,0.95),
                rgba(49,46,129,0.22)
            );
        border: 1px solid rgba(129,140,248,0.28);
        margin-bottom: 1rem;
    }

    .sg-ai-title {
        font-size: 1.1rem;
        font-weight: 750;
        color: #f8fafc;
        margin-bottom: 0.8rem;
    }

    .sg-ai-label {
        color: #94a3b8;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
    }

    .sg-ai-value {
        color: #e2e8f0;
        font-size: 1rem;
        font-weight: 650;
    }

    .sg-confidence {
        font-size: 1.5rem;
        font-weight: 800;
        color: #a5b4fc;
    }

    /* Status */

    .sg-status-ok {
        padding: 1rem 1.2rem;
        border-radius: 14px;
        background: rgba(22,163,74,0.10);
        border: 1px solid rgba(74,222,128,0.22);
        color: #bbf7d0;
        margin-bottom: 1rem;
    }

    .sg-status-warning {
        padding: 1rem 1.2rem;
        border-radius: 14px;
        background: rgba(234,179,8,0.10);
        border: 1px solid rgba(250,204,21,0.22);
        color: #fef08a;
        margin-bottom: 1rem;
    }

    .sg-status-danger {
        padding: 1rem 1.2rem;
        border-radius: 14px;
        background: rgba(220,38,38,0.10);
        border: 1px solid rgba(248,113,113,0.22);
        color: #fecaca;
        margin-bottom: 1rem;
    }

    /* Small labels */

    .sg-label {
        color: #94a3b8;
        font-size: 0.82rem;
        margin-bottom: 0.25rem;
    }

    .sg-value {
        color: #f8fafc;
        font-weight: 600;
    }

    /* Sidebar */

    section[data-testid="stSidebar"] {
        background: #0a0f1d;
        border-right: 1px solid rgba(148,163,184,0.10);
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

@st.cache_resource
def load_inbox():
    return Inbox(DATA_SOURCE)

def is_ai_temporary_error(error):
    """
    Detect temporary Gemini/API availability problems.
    """

    error_text = str(error).lower()

    return any(
        phrase in error_text
        for phrase in [
            "503",
            "unavailable",
            "high demand",
            "temporarily",
            "service unavailable",
        ]
    )


def get_attachment_paths(email):
    si_path = None
    bl_path = None

    for attachment in email.get("attachments", []):
        name = str(attachment).lower()

        if "_si." in name:
            si_path = attachment

        if "_bl." in name:
            bl_path = attachment

    return si_path, bl_path


def safe_read_document(inbox, path):
    if not path:
        return None

    try:
        return read_document(inbox, path)
    except Exception:
        return None


def get_comparison_data(inbox, email):
    """
    Read SI and BL again for display purposes.
    The actual final result still comes from pipeline.py.
    """

    si_path, bl_path = get_attachment_paths(email)

    si_data = {}
    bl_data = {}

    if si_path:
        try:
            si_text = read_document(inbox, si_path)
            si_data = extract_document(si_text, "SI")
        except Exception:
            si_data = {}

    if bl_path:
        try:
            bl_text = read_document(inbox, bl_path)
            bl_data = extract_document(bl_text, "BL")
        except Exception:
            bl_data = {}

    fields = [
        "shipper",
        "consignee",
        "notify_party",
        "port_of_loading",
        "port_of_discharge",
        "container_count",
        "gross_weight_kg",
    ]

    rows = []

    result = st.session_state.get("result", {})
    defect_fields = result.get("defect_fields", []) or []

    for field in fields:

        si_value = si_data.get(field)
        bl_value = bl_data.get(field)

        if field in defect_fields:
            comparison = "⚠ Mismatch"
        elif si_value is None or bl_value is None:
            comparison = "— Not available"
        else:
            comparison = "✓ Match"

        rows.append(
            {
                "Field": field.replace("_", " ").title(),
                "Shipping Instruction": si_value if si_value is not None else "—",
                "Bill of Lading": bl_value if bl_value is not None else "—",
                "Result": comparison,
            }
        )

    return pd.DataFrame(rows)

def get_ai_comparison_rows(inbox, email, result):
    """
    Prepare SI/BL comparison data for Gemini.

    The deterministic pipeline remains responsible for the actual
    validation result. Gemini only explains the result.
    """

    si_path, bl_path = get_attachment_paths(email)

    si_data = {}
    bl_data = {}

    if si_path:
        try:
            si_text = read_document(inbox, si_path)
            si_data = extract_document(si_text, "SI")
        except Exception:
            si_data = {}

    if bl_path:
        try:
            bl_text = read_document(inbox, bl_path)
            bl_data = extract_document(bl_text, "BL")
        except Exception:
            bl_data = {}

    fields = [
        "shipper",
        "consignee",
        "notify_party",
        "port_of_loading",
        "port_of_discharge",
        "container_count",
        "gross_weight_kg",
    ]

    defect_fields = result.get("defect_fields", []) or []

    rows = []

    for field in fields:

        si_value = si_data.get(field)
        bl_value = bl_data.get(field)

        if field in defect_fields:
            validation_result = "MISMATCH"
        elif si_value is None or bl_value is None:
            validation_result = "NOT_AVAILABLE"
        else:
            validation_result = "MATCH"

        rows.append(
            {
                "field": field,
                "si": si_value if si_value is not None else "N/A",
                "bl": bl_value if bl_value is not None else "N/A",
                "result": validation_result,
            }
        )

    return rows


def render_status(result):
    status = result.get("status", "UNKNOWN")
    review_reason = result.get("review_reason")

    if status == "OK":
        st.markdown(
            """
            <div class="sg-status-ok">
                <strong>✓ Documents verified</strong><br>
                No discrepancies were detected in the required fields.
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif status == "MISMATCH":
        st.markdown(
            """
            <div class="sg-status-danger">
                <strong>⚠ Document mismatch detected</strong><br>
                One or more required fields differ between the SI and BL.
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif status == "NEEDS_REVIEW":
        reason_text = {
            "wrong_doc_type": "Wrong document type",
            "missing_attachment": "Required attachment is missing",
            "unreadable": "Document could not be read",
            "missing_value": "Required value is missing",
        }.get(review_reason, "Manual review required")

        st.markdown(
            f"""
            <div class="sg-status-warning">
                <strong>⚠ Manual review required</strong><br>
                Reason: {reason_text}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# LOAD DATA
# ============================================================

inbox = load_inbox()
emails = list(inbox)

email_ids = [
    email.get("email_id", f"email_{i + 1}")
    for i, email in enumerate(emails)
]


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="sg-header">
        <div class="sg-title">🛡️ ShipGuard</div>
        <div class="sg-subtitle">
            AI-powered shipping document verification
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown("## 📩 Email Analysis")
st.sidebar.caption(f"{len(emails)} emails available")

default_index = 0

if "email_243" in email_ids:
    default_index = email_ids.index("email_243")

selected_id = st.sidebar.selectbox(
    "Select email",
    email_ids,
    index=default_index,
)

analyze_button = st.sidebar.button(
    "🔍 Analyze Email",
    type="primary",
    width="stretch",
)


# ============================================================
# FIND SELECTED EMAIL
# ============================================================

selected_email = next(
    (
        email
        for email in emails
        if email.get("email_id") == selected_id
    ),
    None,
)

if selected_email is None:
    st.error("Selected email could not be found.")
    st.stop()


# ============================================================
# ANALYZE
# ============================================================

if analyze_button:

    with st.spinner("Running ShipGuard analysis..."):

        st.session_state.pop("ai_explanation", None)

        # ----------------------------------------------------
        # 1. Deterministic validation
        # ----------------------------------------------------

        result = process_email(
            inbox,
            selected_email,
        )

        st.session_state["result"] = result
        st.session_state["selected_email"] = selected_email

        # ----------------------------------------------------
        # 2. Gemini AI
        # ----------------------------------------------------

        try:
            ai_result = analyze_shipping_email(
                selected_email.get("subject", ""),
                selected_email.get("body", ""),
            )

            st.session_state["ai_result"] = ai_result

        except Exception as e:

            if is_ai_temporary_error(e):

                st.session_state["ai_result"] = {
                    "category": "TEMPORARILY_UNAVAILABLE",
                    "summary": (
                        "Gemini is temporarily unavailable. "
                        "ShipGuard deterministic verification "
                        "continues to operate normally."
                    ),
                    "confidence": 0.0,
                    "temporary_error": True,
                }

            else:

                st.session_state["ai_result"] = {
                    "category": "ERROR",
                    "summary": (
                        "AI analysis could not be completed. "
                        "The deterministic ShipGuard verification "
                        "is still available."
                    ),
                    "confidence": 0.0,
                    "temporary_error": False,
                }


# ============================================================
# USE LAST RESULT
# ============================================================

result = st.session_state.get("result")

if not result:

    st.info(
        "Select an email and click **Analyze Email** to start the ShipGuard analysis."
    )
    st.stop()


# ============================================================
# EMAIL INFORMATION
# ============================================================

st.markdown("## 📧 Email")

email_col1, email_col2, email_col3 = st.columns(3)

with email_col1:
    st.markdown(
        f"""
        <div class="sg-card">
            <div class="sg-card-title">Email ID</div>
            <div class="sg-card-value">
                {selected_email.get("email_id", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with email_col2:
    st.markdown(
        f"""
        <div class="sg-card">
            <div class="sg-card-title">From</div>
            <div class="sg-card-value">
                {selected_email.get("from", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with email_col3:
    st.markdown(
        f"""
        <div class="sg-card">
            <div class="sg-card-title">Category</div>
            <div class="sg-card-value">
                {result.get("category", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    f"""
    <div class="sg-card">
        <div class="sg-card-title">Subject</div>
        <div class="sg-value">
            {selected_email.get("subject", "—")}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.expander("📨 Email body", expanded=False):
    st.write(selected_email.get("body", ""))


# ============================================================
# AI ANALYSIS
# ============================================================

ai_result = st.session_state.get("ai_result")

if ai_result:

    st.markdown("## 🤖 AI Analysis")

    ai_category = ai_result.get("category", "GENERAL")
    ai_summary = ai_result.get("summary", "No summary available.")
    ai_confidence = ai_result.get("confidence", 0)
    ai_temporary_error = ai_result.get("temporary_error",False, )

    try:
        confidence_percent = float(ai_confidence) * 100
    except Exception:
        confidence_percent = 0

    pipeline_category = result.get("category", "—")

if ai_temporary_error:

    agreement_text = (
        "ShipGuard pipeline remains active and provides "
        "the authoritative validation result."
    )

elif ai_category == pipeline_category:

    agreement_text = (
        "✓ AI classification agrees with ShipGuard pipeline"
    )

else:

    agreement_text = (
        f"⚠ AI classification differs from pipeline "
        f"({pipeline_category})"
    )

    ai_col1, ai_col2 = st.columns([2, 1])

    with ai_col1:

        st.markdown("**AI Category**")

        if ai_temporary_error:

            st.warning("⚠️ Temporarily unavailable")

        else:

            st.markdown(f"### `{ai_category}`")

    with ai_col2:
        st.markdown("**Confidence**")
        st.markdown(f"### {confidence_percent:.0f}%")

    st.markdown("**AI Summary**")

    if ai_temporary_error:

        st.warning(ai_summary)

    else:

        st.info(ai_summary)

    if ai_temporary_error:

        st.info(agreement_text)

    elif ai_category == pipeline_category:

        st.success(agreement_text)

    else:

        st.warning(agreement_text)


# ============================================================
# FINAL RESULT
# ============================================================

st.markdown("## 🔎 Analysis Result")

render_status(result)

# ============================================================
# AI DOCUMENT EXPLANATION
# ============================================================

if result.get("category") == "BL_COMPARISON":

    st.markdown("## 🤖 AI Verification Explanation")

    if "ai_explanation" not in st.session_state:

        with st.spinner("Gemini is explaining the document verification result..."):

            try:
                comparison_rows = get_ai_comparison_rows(
                    inbox,
                    selected_email,
                    result,
                )

                ai_explanation = analyze_document_discrepancies(
                    subject=selected_email.get("subject", ""),
                    body=selected_email.get("body", ""),
                    comparison_rows=comparison_rows,
                    status=result.get("status", "UNKNOWN"),
                )

                st.session_state["ai_explanation"] = ai_explanation

            except Exception as error:

                if is_ai_temporary_error(error):

                    st.session_state["ai_explanation"] = {
                        "headline": "AI explanation temporarily unavailable",
                        "summary": (
                            "Gemini is currently experiencing high demand. "
                            "The document validation result below remains "
                            "available and was generated by the ShipGuard "
                            "validation engine."
                        ),
                        "discrepancies": [],
                        "recommendation": (
                            "Review the deterministic SI/BL comparison below."
                        ),
                        "temporary_error": True,
                    }

                else:

                    st.session_state["ai_explanation"] = {
                        "headline": "AI explanation unavailable",
                        "summary": (
                            "Gemini could not generate an explanation. "
                            "The deterministic ShipGuard verification "
                            "remains available."
                        ),
                        "discrepancies": [],
                        "recommendation": (
                            "Review the deterministic SI/BL comparison below."
                        ),
                        "temporary_error": False,
                    }

    ai_explanation = st.session_state.get("ai_explanation", {})

    headline = ai_explanation.get(
        "headline",
        "Document verification analysis",
    )

    summary = ai_explanation.get(
        "summary",
        "No AI explanation available.",
    )

    recommendation = ai_explanation.get(
        "recommendation",
        "Review the validation result.",
    )

    st.markdown(f"### {headline}")

    st.info(summary)

    discrepancies = ai_explanation.get(
        "discrepancies",
        [],
    )

    if discrepancies:

        st.markdown("### ⚠️ Detected discrepancies")

        for discrepancy in discrepancies:

            field = discrepancy.get(
                "field",
                "unknown",
            )

            explanation = discrepancy.get(
                "explanation",
                "",
            )

            st.markdown(
                f"""
                **{field.replace("_", " ").title()}**

                {explanation}
                """
            )

    st.markdown("### 💡 Recommendation")

    st.success(recommendation)


# ============================================================
# RESULT METRICS
# ============================================================

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        "Category",
        result.get("category", "—"),
    )

with metric2:
    st.metric(
        "Status",
        result.get("status", "—"),
    )

with metric3:
    st.metric(
        "Defect",
        "Yes" if result.get("has_defect") else "No",
    )


# ============================================================
# DEFECT FIELDS
# ============================================================

defect_fields = result.get("defect_fields", []) or []

if defect_fields:

    st.markdown("### ⚠️ Detected discrepancies")

    for field in defect_fields:
        st.markdown(
            f"- **{field.replace('_', ' ').title()}**"
        )


# ============================================================
# DOCUMENTS
# ============================================================

st.markdown("## 📄 Documents")

si_path, bl_path = get_attachment_paths(selected_email)

doc_col1, doc_col2 = st.columns(2)

with doc_col1:

    st.markdown(
        f"""
        <div class="sg-card">
            <div class="sg-card-title">Shipping Instruction</div>
            <div class="sg-value">
                {"📎 " + Path(si_path).name if si_path else "⚠ Missing"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with doc_col2:

    st.markdown(
        f"""
        <div class="sg-card">
            <div class="sg-card-title">Bill of Lading</div>
            <div class="sg-value">
                {"📎 " + Path(bl_path).name if bl_path else "⚠ Missing"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# COMPARISON TABLE
# ============================================================

if result.get("category") == "BL_COMPARISON":

    st.markdown("## 📊 Document Comparison")

    comparison_df = get_comparison_data(
        inbox,
        selected_email,
    )

    st.dataframe(
        comparison_df,
        width="stretch",
        hide_index=True,
        column_config={
            "Field": st.column_config.TextColumn(
                "Field",
                width="medium",
            ),
            "Shipping Instruction": st.column_config.TextColumn(
                "Shipping Instruction",
                width="large",
            ),
            "Bill of Lading": st.column_config.TextColumn(
                "Bill of Lading",
                width="large",
            ),
            "Result": st.column_config.TextColumn(
                "Result",
                width="medium",
            ),
        },
    )


# ============================================================
# REVIEW DETAILS
# ============================================================

if result.get("status") == "NEEDS_REVIEW":

    st.markdown("## 🧑‍💻 Review Details")

    reason = result.get("review_reason", "unknown")

    reason_names = {
        "missing_attachment": "Missing attachment",
        "wrong_doc_type": "Wrong document type",
        "unreadable": "Unreadable document",
        "missing_value": "Missing required value",
    }

    st.info(
        f"Reason: **{reason_names.get(reason, reason)}**"
    )


# ============================================================
# RAW RESULT
# ============================================================

with st.expander("🔧 Technical result"):

    st.json(result)