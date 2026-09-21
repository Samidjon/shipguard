"""
Document reading against the real organizer attachments, plus the failure
modes that feed the NEEDS_REVIEW / unreadable verdict.
"""

import pytest

from shipguard.document_reader import read_document
from shipguard.loader import Inbox


@pytest.fixture(scope="module")
def inbox(dataset_dir):
    return Inbox(dataset_dir)


def test_plain_text_attachment_is_read(inbox):
    text = read_document(inbox, "attachments/email_001_SI.txt")

    assert text.strip()
    assert "shipper" in text.lower()


def test_spreadsheet_attachment_is_flattened_to_text(inbox):
    text = read_document(inbox, "attachments/email_005_SI.xlsx")

    assert text.strip()
    # Sheets are announced and cells are joined with a pipe separator.
    assert "--- SHEET:" in text
    assert "|" in text


def test_spreadsheet_content_is_extractable(inbox):
    """
    A spreadsheet must yield the same kind of field data as a text file,
    otherwise the comparison would silently degrade to NEEDS_REVIEW.
    """

    from shipguard.extractor import extract_document

    text = read_document(inbox, "attachments/email_005_SI.xlsx")
    data = extract_document(text, "SI")

    assert any(value is not None for value in data.values())


def test_unsupported_format_raises(inbox):
    with pytest.raises(ValueError):
        read_document(inbox, "attachments/email_001_SI.rtf")


def test_unsupported_format_message_names_the_extension(inbox):
    with pytest.raises(ValueError, match=r"\.rtf"):
        read_document(inbox, "attachments/email_001_SI.rtf")
