"""
Meridian Vendor Claim Portal and Chaos Mutator Routes.
Follows SPEC.txt Section 6.1 and Section 7.
"""

import os
import json
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Response, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/portal", tags=["portal"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
REGISTRY_PATH = os.path.join(BASE_DIR, "data", "registry", "vendors.json")
LEDGER_PATH = os.path.join(BASE_DIR, "data", "ledger.json")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# In-memory session state for demo
portal_state: Dict[str, Any] = {
    "status": "IDLE",  # IDLE, REVIEW, SUBMITTED, CANCELLED
    "fields": {},
    "last_claim_id": None,
    "last_claim": None,
}

# Chaos Mutator active config
mutation_config: Dict[str, Any] = {
    "type": "none",  # none, M1, M2, M3, M4, M5, M6
    "seed": 42,
}


def load_registry() -> Dict[str, Any]:
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"buyer": {}, "vendors": {}}


def load_ledger() -> list:
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_ledger(ledger: list):
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)


# --- Portal Pages ---

@router.get("/claim", response_class=HTMLResponse)
def get_claim_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="claim.html",
        context={
            "fields": portal_state.get("fields", {}),
            "mutation": mutation_config,
        },
    )


@router.post("/claim")
async def post_claim_form(
    request: Request,
    vendor_gstin: str = Form(""),
    vendor_name: str = Form(""),
    invoice_no: str = Form(""),
    invoice_date: str = Form(""),
    po_number: str = Form(""),
    taxable_value: str = Form(""),
    cgst: str = Form(""),
    sgst: str = Form(""),
    igst: str = Form(""),
    total: str = Form(""),
    remarks: str = Form(""),
):
    portal_state["status"] = "REVIEW"
    portal_state["fields"] = {
        "vendor_gstin": vendor_gstin,
        "vendor_name": vendor_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "po_number": po_number,
        "taxable_value": taxable_value,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total": total,
        "remarks": remarks,
    }
    return RedirectResponse(url="/portal/review", status_code=303)


@router.get("/review", response_class=HTMLResponse)
def get_review_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "fields": portal_state.get("fields", {}),
            "mutation": mutation_config,
        },
    )


@router.get("/done", response_class=HTMLResponse)
def get_done_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="done.html",
        context={
            "claim": portal_state.get("last_claim", {}),
            "claim_id": portal_state.get("last_claim_id", "CLM-NONE"),
        },
    )


# --- Portal APIs ---

@router.get("/api/state")
def get_portal_state():
    return {
        "status": portal_state.get("status", "IDLE"),
        "fields": portal_state.get("fields", {}),
        "last_claim_id": portal_state.get("last_claim_id"),
        "last_claim": portal_state.get("last_claim"),
    }


@router.post("/api/claims")
def api_submit_claim(payload: Optional[Dict[str, Any]] = Body(None)):
    """Finalizes submission for payment, appending to claims ledger."""
    fields = payload if (isinstance(payload, dict) and "vendor_gstin" in payload) else portal_state.get("fields", {})
    if not fields:
        return JSONResponse({"error": "No claim data"}, status_code=400)

    import uuid
    claim_id = f"CLM-2026-{uuid.uuid4().hex[:6].upper()}"
    claim_entry = {
        "claim_id": claim_id,
        "vendor_gstin": fields.get("vendor_gstin", ""),
        "vendor_name": fields.get("vendor_name", ""),
        "invoice_no": fields.get("invoice_no", ""),
        "total": fields.get("total", ""),
        "status": "SUBMITTED",
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    portal_state["status"] = "SUBMITTED"
    portal_state["last_claim_id"] = claim_id
    portal_state["last_claim"] = claim_entry

    ledger = load_ledger()
    ledger.append(claim_entry)
    save_ledger(ledger)

    return {"status": "ok", "claim_id": claim_id, "claim": claim_entry}


@router.post("/api/cancel")
def api_cancel_claim():
    """Cancels the in-progress claim."""
    portal_state["status"] = "CANCELLED"
    return {"status": "ok", "message": "Claim cancelled"}


@router.post("/api/reset")
def api_reset_portal():
    """Resets portal session state and restores default seed ledger."""
    portal_state["status"] = "IDLE"
    portal_state["fields"] = {}
    portal_state["last_claim_id"] = None
    portal_state["last_claim"] = None
    mutation_config["type"] = "none"
    mutation_config["seed"] = 42

    # Restore clean ledger
    clean_ledger = [
        {
            "claim_id": "CLM-2026-0001",
            "vendor_gstin": "27BCDFG1234A1Z0",
            "invoice_no": "INV-OLD-999",
            "amount": "12500.00",
            "status": "PAID",
            "submitted_at": "2026-10-15T11:20:00Z",
        }
    ]
    save_ledger(clean_ledger)
    return {"status": "ok", "message": "Portal state and ledger reset"}


@router.get("/api/vendor/{gstin}")
def api_get_vendor(gstin: str):
    """Mock GSTN registry lookup."""
    registry = load_registry()
    vendors = registry.get("vendors", {})
    entry = vendors.get(gstin.strip().upper())
    if not entry:
        return {"status": "not_found", "message": "GSTIN not in registry"}
    return {
        "status": entry.get("status", "unknown"),
        "vendor": entry,
    }


# --- Chaos Mutator Controls ---

@router.post("/_k0/mutate")
def set_mutation(payload: Dict[str, Any] = Body(...)):
    """Sets active mutation type: none, M1, M2, M3, M4, M5, M6."""
    m_type = payload.get("type", "none")
    seed = payload.get("seed", 42)
    mutation_config["type"] = m_type
    mutation_config["seed"] = seed
    return {"status": "ok", "mutation": mutation_config}


@router.get("/_k0/config")
def get_mutation_config():
    return mutation_config
