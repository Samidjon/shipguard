import json
import os
import time
import logging

import streamlit as st
from google import genai


MODEL = "gemini-3.5-flash-lite"

logger = logging.getLogger(__name__)


def get_gemini_api_key():
    """
    Get Gemini API key.

    Priority:
    1. Environment variable - useful for local development
    2. Streamlit Secrets - required for Streamlit Cloud
    """

    # Local development
    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        return api_key.strip()

    # Streamlit Cloud
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")

        if api_key:
            return str(api_key).strip()

    except Exception as error:
        logger.warning(
            "Could not read GEMINI_API_KEY from Streamlit secrets: %s",
            error,
        )

    return None


def get_client():
    api_key = get_gemini_api_key()

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY was not found in environment variables "
            "or Streamlit secrets."
        )

    return genai.Client(api_key=api_key)


def clean_json_response(text):
    """
    Remove Markdown code fences if Gemini returns JSON inside
    ```json ... ```.
    """

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return text


def generate_with_retry(client, prompt, attempts=3):
    """
    Retry temporary Gemini 503/unavailable errors.
    """

    last_error = None

    for attempt in range(attempts):
        try:
            logger.info(
                "Calling Gemini model %s (attempt %s/%s)",
                MODEL,
                attempt + 1,
                attempts,
            )

            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )

            logger.info("Gemini request completed successfully.")

            return response

        except Exception as error:
            last_error = error

            error_text = str(error)

            logger.exception(
                "Gemini request failed on attempt %s/%s: %s",
                attempt + 1,
                attempts,
                error,
            )

            # Retry temporary server / availability errors
            if (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "high demand" in error_text.lower()
            ):
                if attempt < attempts - 1:
                    time.sleep(2 ** attempt)
                    continue

            raise

    raise last_error


def analyze_shipping_email(subject, body):
    """
    Analyze the shipping email and classify its intent.
    """

    client = get_client()

    prompt = f"""
You are an AI assistant for a shipping document verification system called ShipGuard.

Analyze the following shipping email.

EMAIL SUBJECT:
{subject}

EMAIL BODY:
{body}

Classify the email into exactly one of these categories:

- BL_COMPARISON
- SI_REQUEST
- INVOICE_QUERY
- GENERAL
- SPAM

Definitions:

BL_COMPARISON:
The email asks to compare, verify, confirm, check, amend, or reconcile
shipping documents such as Shipping Instruction and Bill of Lading.

SI_REQUEST:
The email primarily requests a Shipping Instruction or asks someone to
prepare, submit, or send an SI.

INVOICE_QUERY:
The email concerns invoices, billing, freight charges, local charges,
or payment-related shipping charges.

GENERAL:
Normal shipping communication that does not fit the other categories.

SPAM:
Marketing, phishing, fraudulent, unsolicited promotional, or clearly
irrelevant messages.

Return ONLY valid JSON:

{{
    "category": "BL_COMPARISON",
    "summary": "Short explanation of what the email is asking for.",
    "confidence": 0.98
}}

Do not include Markdown.
"""

    try:
        response = generate_with_retry(client, prompt)

        text = clean_json_response(response.text)

        return json.loads(text)

    except json.JSONDecodeError as error:
        logger.exception("Gemini returned invalid JSON: %s", error)

        return {
            "category": "ERROR",
            "summary": "Gemini returned an invalid JSON response.",
            "confidence": 0.0,
        }

    except Exception as error:
        logger.exception(
            "AI email analysis failed: %s",
            error,
        )

        return {
            "category": "ERROR",
            "summary": "AI analysis could not be completed.",
            "confidence": 0.0,
        }


def analyze_document_discrepancies(
    subject,
    body,
    comparison_rows,
    status,
):
    """
    Ask Gemini to explain discrepancies found by the deterministic
    ShipGuard document validation engine.

    Gemini does NOT decide whether the documents match.
    The deterministic pipeline already made that decision.

    Gemini's role is to explain the result in human-readable language.
    """

    client = get_client()

    rows_text = ""

    for row in comparison_rows:
        field = row.get("field", "")
        si_value = row.get("si", "N/A")
        bl_value = row.get("bl", "N/A")
        result = row.get("result", "")

        rows_text += f"""
Field: {field}
Shipping Instruction: {si_value}
Bill of Lading: {bl_value}
Validation Result: {result}
---
"""

    prompt = f"""
You are an AI assistant inside ShipGuard, a shipping document verification system.

The deterministic ShipGuard validation engine has already compared a
Shipping Instruction (SI) and Bill of Lading (BL).

Your job is NOT to change the validation result.

Your job is to explain the result clearly to a human shipping operator.

EMAIL SUBJECT:
{subject}

EMAIL BODY:
{body}

FINAL VALIDATION STATUS:
{status}

DOCUMENT COMPARISON:
{rows_text}

Rules:

1. Do not invent information.
2. Only discuss values explicitly provided above.
3. If a field matches, do not describe it as a discrepancy.
4. If a field differs, clearly state both values.
5. If there are no discrepancies, explain that the required fields match.
6. Keep the explanation concise and professional.
7. The explanation should be understandable to a shipping operations employee.

Return ONLY valid JSON in exactly this structure:

{{
    "headline": "Short result headline",
    "summary": "One or two sentence explanation.",
    "discrepancies": [
        {{
            "field": "port_of_loading",
            "explanation": "SI shows X while BL shows Y."
        }}
    ],
    "recommendation": "Short recommended next step."
}}

If there are no discrepancies, return an empty discrepancies array.

Do not include Markdown.
"""

    try:
        response = generate_with_retry(client, prompt)

        text = clean_json_response(response.text)

        return json.loads(text)

    except json.JSONDecodeError as error:
        logger.exception(
            "Gemini returned invalid JSON for discrepancy explanation: %s",
            error,
        )

        return {
            "headline": "AI explanation unavailable",
            "summary": "Gemini returned an invalid response.",
            "discrepancies": [],
            "recommendation": "Review the deterministic validation result.",
        }

    except Exception as error:
        logger.exception(
            "AI discrepancy explanation failed: %s",
            error,
        )

        return {
            "headline": "AI explanation unavailable",
            "summary": "Gemini could not generate an explanation.",
            "discrepancies": [],
            "recommendation": "Review the deterministic SI/BL comparison below.",
        }