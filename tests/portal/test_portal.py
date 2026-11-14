"""
Unit & Oracle Tests for Meridian Vendor Claim Portal & Chaos Mutator.
Follows SPEC.txt Section 6.1 and M1 Portal Acceptance Criteria.
"""

import pytest
from app.portal.routes import (
    portal_state,
    mutation_config,
    api_reset_portal,
    api_submit_claim,
    api_get_vendor,
    set_mutation,
    get_portal_state,
)


def setup_function():
    api_reset_portal()


def test_portal_state_lifecycle():
    assert get_portal_state()["status"] == "IDLE"

    # Simulate submission
    res = api_submit_claim({
        "vendor_gstin": "27AAPFU0939F1ZV",
        "vendor_name": "Apex Industrial Supplies",
        "invoice_no": "INV-2026-TEST",
        "total": "3540.00",
    })
    assert res["status"] == "ok"
    assert "claim_id" in res
    assert res["claim_id"].startswith("CLM-2026-")

    state = get_portal_state()
    assert state["status"] == "SUBMITTED"
    assert state["last_claim"]["invoice_no"] == "INV-2026-TEST"

    # Reset
    reset_res = api_reset_portal()
    assert reset_res["status"] == "ok"
    assert get_portal_state()["status"] == "IDLE"


def test_mock_registry_api():
    # Active vendor
    v1 = api_get_vendor("27AAPFU0939F1ZV")
    assert v1["status"] == "active"
    assert v1["vendor"]["name"] == "Apex Industrial Supplies"

    # Suspended vendor
    v2 = api_get_vendor("27XYZAB5678C1Z6")
    assert v2["status"] == "suspended"

    # Cancelled vendor
    v3 = api_get_vendor("29ABCDE1122G1ZZ")
    assert v3["status"] == "cancelled"

    # Not found
    v4 = api_get_vendor("27INVALID9999Z0")
    assert v4["status"] == "not_found"


@pytest.mark.parametrize("m_type", ["M1", "M2", "M3", "M4", "M5", "M6"])
def test_chaos_mutator_oracle_solvability(m_type):
    """
    Verifies that for each mutation M1-M6, the active configuration is correctly set,
    and the portal state engine maintains pristine data-k0 plumbing so an oracle
    can always resolve and complete the claim.
    """
    res = set_mutation({"type": m_type, "seed": 100})
    assert res["status"] == "ok"
    assert res["mutation"]["type"] == m_type

    # Oracle completes claim using backend contract
    claim_payload = {
        "vendor_gstin": "27AAPFU0939F1ZV",
        "vendor_name": "Apex Industrial Supplies",
        "invoice_no": f"INV-{m_type}-ORACLE",
        "total": "5000.00",
    }
    submit_res = api_submit_claim(claim_payload)
    assert submit_res["status"] == "ok"
    assert get_portal_state()["status"] == "SUBMITTED"
    assert get_portal_state()["last_claim"]["invoice_no"] == f"INV-{m_type}-ORACLE"
