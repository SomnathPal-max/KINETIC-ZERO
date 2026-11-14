"""
Unit Tests for Guard Engine Hard Gates G1-G7.
Satisfies M1 Guard Acceptance Test criteria (>= 25 tests).
"""

from decimal import Decimal
from datetime import date, timedelta
import pytest
from contracts.models import (
    InvoiceExtraction,
    InvoiceFields,
    FieldExtraction,
    LineItem,
    AgentProposal,
    ProposalClaim,
)
from app.guard.gstin import gstin_ok, gstin_checksum
from app.guard.gates import (
    check_g1_gstin,
    check_g2_arithmetic,
    check_g3_tax_split,
    check_g4_registry,
    check_g5_amount_policy,
    check_g6_duplicate,
    check_g7_dates,
)
from app.guard.engine import verify, GuardContext


def make_test_extraction(
    vendor_gstin="27AAPFU0939F1ZV",
    buyer_gstin="27AAAPL1234F1Z8",
    invoice_no="INV-100",
    invoice_date="2026-11-01",
    taxable="1000.00",
    cgst="90.00",
    sgst="90.00",
    igst="0.00",
    total="1180.00",
    line_items=None,
    source_text="",
) -> InvoiceExtraction:
    if line_items is None:
        line_items = [LineItem(desc="Widget", qty="10", rate="100.00", amount="1000.00")]
    if not source_text:
        source_text = f"INV {invoice_no} {vendor_gstin} {buyer_gstin} {invoice_date} {taxable} {cgst} {sgst} {igst} {total}"

    return InvoiceExtraction(
        doc_id="test_doc",
        source_type="pdf_text",
        passes=1,
        source_text=source_text,
        fields=InvoiceFields(
            vendor_name=FieldExtraction(value="Test Vendor", evidence="Test Vendor"),
            vendor_gstin=FieldExtraction(value=vendor_gstin, evidence=vendor_gstin),
            buyer_gstin=FieldExtraction(value=buyer_gstin, evidence=buyer_gstin),
            invoice_no=FieldExtraction(value=invoice_no, evidence=invoice_no),
            invoice_date=FieldExtraction(value=invoice_date, evidence=invoice_date),
            po_number=FieldExtraction(value="PO-1", evidence="PO-1"),
            taxable_value=FieldExtraction(value=taxable, evidence=taxable),
            cgst=FieldExtraction(value=cgst, evidence=cgst),
            sgst=FieldExtraction(value=sgst, evidence=sgst),
            igst=FieldExtraction(value=igst, evidence=igst),
            total=FieldExtraction(value=total, evidence=total),
        ),
        line_items=line_items,
    )


# --- Gate G1 Tests ---

def test_g1_valid_test_vector():
    assert gstin_ok("27AAPFU0939F1ZV") is True
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV")
    claim = check_g1_gstin(ext)
    assert claim.status == "PASS"


def test_g1_flipped_last_char_fails():
    assert gstin_ok("27AAPFU0939F1ZX") is False
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZX")
    claim = check_g1_gstin(ext)
    assert claim.status == "FAIL"


def test_g1_invalid_length():
    assert gstin_ok("27AAPFU0939F1Z") is False
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1Z")
    assert check_g1_gstin(ext).status == "FAIL"


def test_g1_invalid_state_code():
    # 00 is not a valid Indian GST state code
    assert gstin_ok("00AAPFU0939F1ZV") is False
    ext = make_test_extraction(vendor_gstin="00AAPFU0939F1ZV")
    assert check_g1_gstin(ext).status == "FAIL"


def test_g1_invalid_regex_format():
    # 14th char must be 'Z'
    assert gstin_ok("27AAPFU0939F1AV") is False
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1AV")
    assert check_g1_gstin(ext).status == "FAIL"


# --- Gate G2 Tests ---

def test_g2_arithmetic_exact_match():
    ext = make_test_extraction(taxable="1000.00", cgst="90.00", sgst="90.00", igst="0.00", total="1180.00")
    claim = check_g2_arithmetic(ext)
    assert claim.status == "PASS"


def test_g2_line_qty_rate_mismatch():
    lines = [LineItem(desc="Widget", qty="10", rate="100.00", amount="1050.00")]  # 10*100 != 1050
    ext = make_test_extraction(line_items=lines, taxable="1050.00", total="1230.00")
    claim = check_g2_arithmetic(ext)
    assert claim.status == "FAIL"
    assert "Line item" in claim.statement


def test_g2_sum_lines_taxable_mismatch():
    lines = [
        LineItem(desc="W1", qty="5", rate="100.00", amount="500.00"),
        LineItem(desc="W2", qty="5", rate="100.00", amount="500.00"),
    ]
    ext = make_test_extraction(line_items=lines, taxable="1200.00", total="1380.00")
    claim = check_g2_arithmetic(ext)
    assert claim.status == "FAIL"


def test_g2_total_mismatch():
    ext = make_test_extraction(taxable="1000.00", cgst="90.00", sgst="90.00", igst="0.00", total="1500.00")
    claim = check_g2_arithmetic(ext)
    assert claim.status == "FAIL"


def test_g2_within_one_rupee_tolerance():
    # 1000 + 90 + 90 = 1180.00. Total is 1180.50 (diff 0.50 <= 1.00 tolerance)
    ext = make_test_extraction(taxable="1000.00", cgst="90.00", sgst="90.00", igst="0.00", total="1180.50")
    claim = check_g2_arithmetic(ext, tolerance=Decimal("1.00"))
    assert claim.status == "PASS"


def test_g2_outside_one_rupee_tolerance():
    # Diff is 1.20 (> 1.00)
    ext = make_test_extraction(taxable="1000.00", cgst="90.00", sgst="90.00", igst="0.00", total="1181.20")
    claim = check_g2_arithmetic(ext, tolerance=Decimal("1.00"))
    assert claim.status == "FAIL"


# --- Gate G3 Tests ---

def test_g3_intra_state_correct():
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV", cgst="90.00", sgst="90.00", igst="0.00", taxable="1000.00")
    claim = check_g3_tax_split(ext, buyer_gstin="27AAAPL1234F1Z8")
    assert claim.status == "PASS"


def test_g3_intra_state_cgst_sgst_inequality():
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV", cgst="90.00", sgst="80.00", igst="0.00", taxable="1000.00")
    claim = check_g3_tax_split(ext, buyer_gstin="27AAAPL1234F1Z8")
    assert claim.status == "FAIL"


def test_g3_intra_state_with_igst_fails():
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV", cgst="0.00", sgst="0.00", igst="180.00", taxable="1000.00")
    claim = check_g3_tax_split(ext, buyer_gstin="27AAAPL1234F1Z8")
    assert claim.status == "FAIL"


def test_g3_inter_state_correct():
    ext = make_test_extraction(vendor_gstin="29PQRST3456E1ZN", cgst="0.00", sgst="0.00", igst="180.00", taxable="1000.00")
    claim = check_g3_tax_split(ext, buyer_gstin="27AAAPL1234F1Z8")
    assert claim.status == "PASS"


def test_g3_inter_state_with_cgst_fails():
    ext = make_test_extraction(vendor_gstin="29PQRST3456E1ZN", cgst="90.00", sgst="90.00", igst="0.00", taxable="1000.00")
    claim = check_g3_tax_split(ext, buyer_gstin="27AAAPL1234F1Z8")
    assert claim.status == "FAIL"


def test_g3_disallowed_effective_gst_rate():
    # 12% is not in [5, 18]
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV", cgst="60.00", sgst="60.00", igst="0.00", taxable="1000.00", total="1120.00")
    claim = check_g3_tax_split(ext, buyer_gstin="27AAAPL1234F1Z8", allowed_rates=[5, 18])
    assert claim.status == "FAIL"


# --- Gate G4 Tests ---

def test_g4_vendor_active(tmp_path):
    registry = {"vendors": {"27AAPFU0939F1ZV": {"name": "Apex", "status": "active"}}}
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV")
    claim = check_g4_registry(ext, registry)
    assert claim.status == "PASS"


def test_g4_vendor_suspended():
    registry = {"vendors": {"27XYZAB5678C1Z6": {"name": "Western", "status": "suspended"}}}
    ext = make_test_extraction(vendor_gstin="27XYZAB5678C1Z6")
    claim = check_g4_registry(ext, registry)
    assert claim.status == "FAIL"


def test_g4_vendor_cancelled():
    registry = {"vendors": {"29ABCDE1122G1ZZ": {"name": "Southern", "status": "cancelled"}}}
    ext = make_test_extraction(vendor_gstin="29ABCDE1122G1ZZ")
    claim = check_g4_registry(ext, registry)
    assert claim.status == "FAIL"


def test_g4_vendor_not_in_registry():
    registry = {"vendors": {}}
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV")
    claim = check_g4_registry(ext, registry)
    assert claim.status == "FAIL"


# --- Gate G5 Tests ---

def test_g5_auto_approval_limit():
    ext = make_test_extraction(total="84500.00")
    claim = check_g5_amount_policy(ext, auto_limit=Decimal("100000"), manager_limit=Decimal("250000"))
    assert claim.status == "PASS"


def test_g5_manager_approval_limit():
    ext = make_test_extraction(total="185000.00")
    claim = check_g5_amount_policy(ext, auto_limit=Decimal("100000"), manager_limit=Decimal("250000"))
    assert claim.status == "ESCALATE"


def test_g5_exceeds_manager_limit():
    ext = make_test_extraction(total="310000.00")
    claim = check_g5_amount_policy(ext, auto_limit=Decimal("100000"), manager_limit=Decimal("250000"))
    assert claim.status == "FAIL"


# --- Gate G6 Tests ---

def test_g6_unique_invoice_passes():
    ledger = [{"vendor_gstin": "27AAPFU0939F1ZV", "invoice_no": "INV-001"}]
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV", invoice_no="INV-002")
    claim = check_g6_duplicate(ext, ledger)
    assert claim.status == "PASS"


def test_g6_duplicate_invoice_fails():
    ledger = [{"vendor_gstin": "27AAPFU0939F1ZV", "invoice_no": "INV-001", "claim_id": "CLM-1"}]
    ext = make_test_extraction(vendor_gstin="27AAPFU0939F1ZV", invoice_no="INV-001")
    claim = check_g6_duplicate(ext, ledger)
    assert claim.status == "FAIL"


# --- Gate G7 Tests ---

def test_g7_valid_recent_date():
    today = date(2026, 11, 14)
    ext = make_test_extraction(invoice_date="2026-11-01")
    claim = check_g7_dates(ext, today=today, max_age_days=90)
    assert claim.status == "PASS"


def test_g7_future_date_fails():
    today = date(2026, 11, 14)
    ext = make_test_extraction(invoice_date="2026-11-15")
    claim = check_g7_dates(ext, today=today, max_age_days=90)
    assert claim.status == "FAIL"
    assert "future" in claim.evidence


def test_g7_date_older_than_90_days_fails():
    today = date(2026, 11, 14)
    old_date = (today - timedelta(days=120)).strftime("%Y-%m-%d")
    ext = make_test_extraction(invoice_date=old_date)
    claim = check_g7_dates(ext, today=today, max_age_days=90)
    assert claim.status == "FAIL"
    assert "exceeds" in claim.evidence


def test_g7_invalid_date_format_fails():
    ext = make_test_extraction(invoice_date="14/11/2026")
    claim = check_g7_dates(ext)
    assert claim.status == "FAIL"


# --- Guard Engine Integration Tests ---

def test_guard_engine_proceed_on_clean_invoice():
    today = date(2026, 11, 14)
    registry = {
        "buyer": {"gstin": "27AAAPL1234F1Z8"},
        "vendors": {"27AAPFU0939F1ZV": {"name": "Apex", "status": "active"}},
    }
    ledger = []
    ctx = GuardContext(registry=registry, ledger=ledger, today=today)

    ext = make_test_extraction(
        vendor_gstin="27AAPFU0939F1ZV",
        buyer_gstin="27AAAPL1234F1Z8",
        invoice_no="INV-101",
        invoice_date="2026-11-01",
        taxable="1000.00",
        cgst="90.00",
        sgst="90.00",
        igst="0.00",
        total="1180.00",
    )
    proposal = AgentProposal(doc_id="test_doc", decision="APPROVE", claims=[])
    report = verify(ext, proposal, ctx)
    assert report.verdict == "PROCEED"
    assert report.ai_overruled is False
    assert len(report.failed_gates) == 0


def test_guard_engine_blocks_and_overrules_ai():
    today = date(2026, 11, 14)
    # Suspended vendor
    registry = {
        "buyer": {"gstin": "27AAAPL1234F1Z5"},
        "vendors": {"27XYZAB5678C1Z6": {"name": "Western", "status": "suspended"}},
    }
    ctx = GuardContext(registry=registry, ledger=[], today=today)
    ext = make_test_extraction(vendor_gstin="27XYZAB5678C1Z6")
    # AI proposed APPROVE
    proposal = AgentProposal(doc_id="test_doc", decision="APPROVE", claims=[])

    report = verify(ext, proposal, ctx)
    assert report.verdict == "BLOCK"
    assert report.ai_overruled is True
    assert "G4" in report.failed_gates
