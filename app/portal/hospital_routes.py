"""
Routes for Target Portal B (Healthcare Insurer Pre-Authorization Portal).
Follows KINETIC-ZERO v2 Domain Pack specification.
"""

import os
import random
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(prefix="/portal_b")

# Portal B State
portal_b_state = {
    "submitted": False,
    "last_submission": {},
    "mutation": {"type": "none", "params": {}},
}


@router.get("/preauth", response_class=HTMLResponse)
def get_preauth_page(request: Request):
    """Renders Portal B preauth entry page."""
    return templates.TemplateResponse(
        request=request,
        name="hospital_preauth.html",
        context={
            "fields": portal_b_state.get("last_submission", {}),
            "mutation": portal_b_state.get("mutation", {"type": "none"}),
        },
    )


@router.post("/preauth", response_class=HTMLResponse)
def post_preauth_page(
    request: Request,
    patient_id: str = Form(""),
    patient_name: str = Form(""),
    policy_number: str = Form(""),
    insurer_id: str = Form(""),
    diagnosis_code: str = Form(""),
    treatment_type: str = Form(""),
    hospital_id: str = Form(""),
    admission_date: str = Form(""),
    estimated_cost: str = Form(""),
):
    """Processes Portal B pre-auth submission and redirects to done."""
    submission = {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "policy_number": policy_number,
        "insurer_id": insurer_id,
        "diagnosis_code": diagnosis_code,
        "treatment_type": treatment_type,
        "hospital_id": hospital_id,
        "admission_date": admission_date,
        "estimated_cost": estimated_cost,
    }
    portal_b_state["submitted"] = True
    portal_b_state["last_submission"] = submission
    ref_id = f"AUTH-2026-{random.randint(10000, 99999)}"

    return templates.TemplateResponse(
        request=request,
        name="hospital_done.html",
        context={
            "ref_id": ref_id,
            "patient_id": patient_id,
            "policy_number": policy_number,
            "estimated_cost": estimated_cost,
        },
    )


@router.get("/done", response_class=HTMLResponse)
def get_done_page(request: Request):
    sub = portal_b_state.get("last_submission", {})
    return templates.TemplateResponse(
        request=request,
        name="hospital_done.html",
        context={
            "ref_id": f"AUTH-2026-{random.randint(10000, 99999)}",
            "patient_id": sub.get("patient_id", "PT-10492"),
            "policy_number": sub.get("policy_number", "POL-88219"),
            "estimated_cost": sub.get("estimated_cost", "38500.00"),
        },
    )


@router.post("/reset")
def reset_portal_b():
    portal_b_state["submitted"] = False
    portal_b_state["last_submission"] = {}
    portal_b_state["mutation"] = {"type": "none", "params": {}}
    return {"status": "ok", "portal": "portal_b"}
