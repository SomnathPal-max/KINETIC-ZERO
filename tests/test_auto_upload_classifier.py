import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIN_PDF = os.path.join(ROOT_DIR, "data", "fixtures", "invoices", "demo_clean.pdf")
HOSP_PDF = os.path.join(ROOT_DIR, "packs", "hospital", "fixtures", "preauth_clean.pdf")


def test_auto_upload_finance_invoice():
    """Verify that uploading a finance invoice auto-classifies as finance and computes score."""
    with open(FIN_PDF, "rb") as f:
        response = client.post(
            "/api/documents/auto_upload",
            files={"file": ("test_invoice.pdf", f, "application/pdf")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "classifier" in data
    assert data["classifier"]["category"] == "finance"
    assert data["pack_id"] == "finance"
    assert data["guard"]["data_trust_score"] == 100
    assert data["guard"]["verdict"] == "PROCEED"
    assert data["workflow"]["workflow_id"] == "wf_vendor_claim"
    assert data["workflow"]["target_portal"] == "/portal/claim"


def test_auto_upload_hospital_preauth():
    """Verify that uploading a hospital pre-auth auto-classifies as health and computes score."""
    with open(HOSP_PDF, "rb") as f:
        response = client.post(
            "/api/documents/auto_upload",
            files={"file": ("test_preauth.pdf", f, "application/pdf")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "classifier" in data
    assert data["classifier"]["category"] == "health"
    assert data["pack_id"] == "hospital"
    assert data["guard"]["data_trust_score"] == 100
    assert data["guard"]["verdict"] == "PROCEED"
    assert data["workflow"]["workflow_id"] == "wf_hospital_preauth"
    assert data["workflow"]["target_portal"] == "/portal_b/preauth"
