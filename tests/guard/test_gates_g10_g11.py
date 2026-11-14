from datetime import date
from contracts.models import InvoiceExtraction, AgentProposal
from app.guard.engine import verify, GuardContext
from tests.guard.test_gates_g1_g7 import make_test_extraction

def test_g10_msme_within_window_passes():
    today = date(2026, 11, 14)
    registry = {
        'buyer': {'gstin': '27AAAPL1234F1Z5'},
        'vendors': {
            '27AAPFU0939F1ZV': {
                'name': 'Apex Industrial',
                'status': 'active',
                'msme_category': 'Micro',
                'udyam_reg_no': 'UDYAM-MH-01-0028491',
                'credit_days_allowed': 45
            }
        }
    }
    ctx = GuardContext(registry=registry, ledger=[], today=today)
    # Invoice 14 days old (Nov 01 vs Nov 14) -> within 45 days
    ext = make_test_extraction(vendor_gstin='27AAPFU0939F1ZV', invoice_date='2026-11-01')
    proposal = AgentProposal(doc_id='test', decision='APPROVE', claims=[])
    report = verify(ext, proposal, ctx)
    g10 = [c for c in report.claims if c.gate == 'G10'][0]
    assert g10.status == 'PASS'
    assert 'Payment due in 32 days' in g10.evidence

def test_g10_msme_overdue_escalates():
    today = date(2026, 11, 14)
    registry = {
        'buyer': {'gstin': '27AAAPL1234F1Z5'},
        'vendors': {
            '27AAPFU0939F1ZV': {
                'name': 'Apex Industrial',
                'status': 'active',
                'msme_category': 'Micro',
                'udyam_reg_no': 'UDYAM-MH-01-0028491',
                'credit_days_allowed': 45
            }
        }
    }
    ctx = GuardContext(registry=registry, ledger=[], today=today)
    # Invoice 60 days old (Sep 15 vs Nov 14) -> exceeds 45 days
    ext = make_test_extraction(vendor_gstin='27AAPFU0939F1ZV', invoice_date='2026-09-15')
    proposal = AgentProposal(doc_id='test', decision='APPROVE', claims=[])
    report = verify(ext, proposal, ctx)
    g10 = [c for c in report.claims if c.gate == 'G10'][0]
    assert g10.status == 'ESCALATE'
    assert 'exceeds 45-day limit' in g10.evidence
    assert report.verdict == 'ESCALATE'

def test_g11_einvoice_detected():
    today = date(2026, 11, 14)
    ctx = GuardContext(registry={}, ledger=[], today=today)
    irn = 'a' * 64
    ext = make_test_extraction(source_text=f'TAX INVOICE IRN: {irn} Total: Rs 1180.00')
    proposal = AgentProposal(doc_id='test', decision='APPROVE', claims=[])
    report = verify(ext, proposal, ctx)
    g11 = [c for c in report.claims if c.gate == 'G11'][0]
    assert g11.status == 'PASS'
    assert 'NIC E-Invoice IRN verified' in g11.evidence
