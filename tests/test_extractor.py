"""
Unit test for PDF Text Extraction and Grounding.
"""

import os
import pytest
from app.extractor import extract_invoice, extract_text_from_pdf, generate_agent_proposal
from app.guard.gates import check_g9_grounding

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures", "invoices")


def test_pdf_text_layer_extraction():
    demo_pdf = os.path.join(FIXTURES_DIR, "demo_clean.pdf")
    assert os.path.exists(demo_pdf)
    text = extract_text_from_pdf(demo_pdf)
    assert "TAX INVOICE" in text
    assert "27AAPFU0939F1ZV" in text
    assert "84500.00" in text


def test_extractor_grounding_verification():
    demo_pdf = os.path.join(FIXTURES_DIR, "demo_clean.pdf")
    ext = extract_invoice(doc_id="demo_clean", pdf_path=demo_pdf)
    assert ext.doc_id == "demo_clean"
    assert ext.fields.vendor_gstin.value == "27AAPFU0939F1ZV"

    # Verify G9 grounding
    claim = check_g9_grounding(ext)
    assert claim.status == "PASS"


def test_agent_proposal_generation():
    demo_pdf = os.path.join(FIXTURES_DIR, "demo_clean.pdf")
    ext = extract_invoice(doc_id="demo_clean", pdf_path=demo_pdf)
    prop = generate_agent_proposal(ext)
    assert prop.doc_id == "demo_clean"
    assert prop.decision in ["APPROVE", "HOLD", "REJECT"]
    assert len(prop.claims) > 0
