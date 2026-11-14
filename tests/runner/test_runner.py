"""
Acceptance Tests for Workflow Runner, 4-Tier Self-Healing & Memory Cache.
Follows SPEC.txt Section 10 M2 Healer Pass Criteria:
- Heals M1-M4 to SUCCESS
- Decoy test (M5) never produces WRONG_ACTION (SUCCESS or ESCALATED only)
- Second run after a heal shows 0 LLM calls and tier 3 (memory cache hit)
"""

import pytest
from contracts.models import (
    Workflow,
    InvoiceExtraction,
    InvoiceFields,
    FieldExtraction,
    LineItem,
)
from app.recorder import load_workflow
from app.runner import runner
from app.portal.routes import api_reset_portal
from app.memory import clear_memory


@pytest.fixture(autouse=True)
def clean_environment():
    api_reset_portal()
    clear_memory()


def get_clean_invoice() -> InvoiceExtraction:
    return InvoiceExtraction(
        doc_id="inv_clean",
        source_type="pdf_text",
        passes=1,
        source_text="Apex Industrial Supplies 27AAPFU0939F1ZV 27AAAPL1234F1Z8 INV-001 2026-11-01 1000.00 90.00 90.00 0.00 1180.00",
        fields=InvoiceFields(
            vendor_name=FieldExtraction(value="Apex Industrial Supplies", evidence="Apex Industrial Supplies"),
            vendor_gstin=FieldExtraction(value="27AAPFU0939F1ZV", evidence="27AAPFU0939F1ZV"),
            buyer_gstin=FieldExtraction(value="27AAAPL1234F1Z8", evidence="27AAAPL1234F1Z8"),
            invoice_no=FieldExtraction(value="INV-001", evidence="INV-001"),
            invoice_date=FieldExtraction(value="2026-11-01", evidence="2026-11-01"),
            po_number=FieldExtraction(value="PO-1", evidence="PO-1"),
            taxable_value=FieldExtraction(value="1000.00", evidence="1000.00"),
            cgst=FieldExtraction(value="90.00", evidence="90.00"),
            sgst=FieldExtraction(value="90.00", evidence="90.00"),
            igst=FieldExtraction(value="0.00", evidence="0.00"),
            total=FieldExtraction(value="1180.00", evidence="1180.00"),
        ),
        line_items=[LineItem(desc="Bearing", qty="10", rate="100.00", amount="1000.00")],
    )


def test_baseline_fails_on_mutation():
    """Baseline naive replay fails immediately when portal is mutated."""
    wf = load_workflow("wf_vendor_claim")
    inv = get_clean_invoice()
    log = runner.run_workflow(wf, inv, mode="baseline", mutation="M1")
    assert log.outcome in ["CRASH", "WRONG_ACTION"]
    assert any(s.status == "failed" for s in log.steps)


@pytest.mark.parametrize("m_type", ["M1", "M2", "M3", "M4"])
def test_healer_solves_m1_to_m4(m_type):
    """KINETIC-ZERO heals mutations M1-M4 to SUCCESS."""
    wf = load_workflow("wf_vendor_claim")
    inv = get_clean_invoice()
    log = runner.run_workflow(wf, inv, mode="k0_full", mutation=m_type)
    assert log.outcome == "SUCCESS"
    assert any(s.status == "healed" for s in log.steps)


def test_decoy_m5_never_produces_wrong_action():
    """
    Decoy test (M5): Negative terms filter prevents clicking deceptive Cancel button.
    Must never produce WRONG_ACTION. Must be SUCCESS or ESCALATED.
    """
    wf = load_workflow("wf_vendor_claim")
    inv = get_clean_invoice()
    log = runner.run_workflow(wf, inv, mode="k0_full", mutation="M5")
    assert log.outcome != "WRONG_ACTION"
    assert log.outcome in ["SUCCESS", "ESCALATED"]


def test_memory_tier3_zero_llm_calls_on_rerun():
    """
    Second run after a heal uses Tier 3 memory cache: 0 LLM calls, resolved at tier 3.
    """
    wf = load_workflow("wf_vendor_claim")
    inv = get_clean_invoice()

    # First run heals and caches in SQLite
    log1 = runner.run_workflow(wf, inv, mode="k0_full", mutation="M1")
    assert log1.outcome == "SUCCESS"

    # Reset portal for second run under identical mutation
    api_reset_portal()

    # Second run
    log2 = runner.run_workflow(wf, inv, mode="k0_full", mutation="M1")
    assert log2.outcome == "SUCCESS"
    assert log2.llm_calls == 0
    # Steps must have hit tier 3 memory
    healed_steps = [s for s in log2.steps if s.status == "healed"]
    assert any(s.tier == 3 for s in healed_steps)
