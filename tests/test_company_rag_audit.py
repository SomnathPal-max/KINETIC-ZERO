import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_company_rules_handbook():
    """Verify endpoint serves official corporate rules handbook."""
    res = client.get("/api/policy/company_rules")
    assert res.status_code == 200
    data = res.json()
    assert "handbook_title" in data
    assert "CR-01" in data["content"]
    assert "CR-03" in data["content"]
    assert "CR-07" in data["content"]
    assert data["company_details"]["gstin"] == "27AAAPL1234F1Z8"


def test_clean_invoice_company_rag_audit():
    """Verify clean invoice achieves high score (>= 90) on company policy audit."""
    res = client.get("/api/invoices/demo_clean")
    assert res.status_code == 200
    data = res.json()
    assert "company_rag_audit" in data
    audit = data["company_rag_audit"]
    assert audit["policy_score"] >= 90
    assert audit["verdict"] == "APPROVE"
    assert len(audit["rule_evaluations"]) >= 6
    assert any(r["rule_id"] == "CR-01" and r["status"] == "PASS" for r in audit["rule_evaluations"])


def test_math_error_invoice_company_rag_audit():
    """Verify arithmetic mismatch trips CR-03 and lowers score."""
    res = client.get("/api/invoices/demo_math_error")
    assert res.status_code == 200
    data = res.json()
    assert "company_rag_audit" in data
    audit = data["company_rag_audit"]
    assert audit["policy_score"] < 100
    assert audit["verdict"] == "REJECT"
    cr3 = next((r for r in audit["rule_evaluations"] if r["rule_id"] == "CR-03"), None)
    assert cr3 is not None
    assert cr3["status"] == "FAIL"


def test_suspended_vendor_company_rag_audit():
    """Verify suspended vendor trips CR-02 and is rejected."""
    res = client.get("/api/invoices/demo_suspended")
    assert res.status_code == 200
    data = res.json()
    assert "company_rag_audit" in data
    audit = data["company_rag_audit"]
    assert audit["policy_score"] < 100
    assert audit["verdict"] == "REJECT"
    cr2 = next((r for r in audit["rule_evaluations"] if r["rule_id"] == "CR-02"), None)
    assert cr2 is not None
    assert cr2["status"] == "FAIL"
