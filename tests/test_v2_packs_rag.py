"""
Tests for KINETIC-ZERO v2 Domain Packs, RAG Knowledge Layer, and Portal B.
Direct function calls (avoids anyio socket sandbox constraints on Windows).
"""

import pytest
from app.main import (
    api_list_packs,
    api_get_pack,
    api_list_documents,
    api_get_document_details,
    api_ask_sop,
    api_route_document,
)


def test_list_packs():
    packs = api_list_packs()
    assert len(packs) >= 2
    pack_ids = [p["id"] for p in packs]
    assert "finance" in pack_ids
    assert "hospital" in pack_ids


def test_get_pack_details():
    pack = api_get_pack("hospital")
    assert pack["id"] == "hospital"
    assert pack["default_workflow"] == "wf_hospital_preauth"
    assert len(pack["schema"]["fields"]) >= 6
    assert len(pack["rules"]) >= 6


def test_hospital_documents_list_and_verify():
    # 1. List
    docs = api_list_documents("hospital")
    assert len(docs) >= 5
    doc_ids = [d["id"] for d in docs]
    assert "preauth_clean" in doc_ids
    assert "preauth_lapsed_policy" in doc_ids

    # 2. Verify clean hospital form -> PROCEED
    clean_data = api_get_document_details("hospital", "preauth_clean")
    assert clean_data["guard"]["verdict"] == "PROCEED"
    assert clean_data["guard"]["data_trust_score"] == 100

    # 3. Verify lapsed policy -> BLOCK (HP_G1)
    lapsed_data = api_get_document_details("hospital", "preauth_lapsed_policy")
    assert lapsed_data["guard"]["verdict"] == "BLOCK"
    assert "HP_G1" in lapsed_data["guard"]["failed_gates"]


def test_rag_ask_sop_endpoint():
    # Ask Finance SOP
    data_fin = api_ask_sop({"query": "What is the manager approval limit?", "pack_id": "finance"})
    assert data_fin["found"] is True
    assert data_fin["clause_id"] == "VP-4.2"

    # Ask Hospital SOP
    data_hosp = api_ask_sop({"query": "What is the pre-auth approval limit?", "pack_id": "hospital"})
    assert data_hosp["found"] is True
    assert data_hosp["clause_id"] == "HP-3.1"

    # Ask Out-of-domain question
    data_mars = api_ask_sop({"query": "How do I build a spaceship to Mars?", "pack_id": "finance"})
    assert data_mars["found"] is False
    assert data_mars["escalate"] is True


def test_agent_router_endpoint():
    # Route Invoice
    inv_data = api_route_document({"text": "TAX INVOICE Vendor: Apex Supplies GSTIN: 27AAPFU0939F1ZV Total: Rs 50000"})
    assert inv_data["matched_pack_id"] == "finance"
    assert inv_data["matched_skill"] == "wf_vendor_claim"
    assert inv_data["confidence"] >= 0.70

    # Route Patient Pre-Auth
    pt_data = api_route_document({"text": "PATIENT PRE-AUTHORIZATION REQUEST FORM Patient ID: PT-10492 Diagnosis ICD-10 J18 Apollo Hospital"})
    assert pt_data["matched_pack_id"] == "hospital"
    assert pt_data["matched_skill"] == "wf_hospital_preauth"
    assert pt_data["confidence"] >= 0.70
