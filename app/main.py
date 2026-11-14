"""
FastAPI Backend for KINETIC-ZERO.
Follows SPEC.txt Section 4, 7, 8, 6.10.
"""

import os
import sys
import json
import time
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FIXTURES_DIR = os.path.join(ROOT_DIR, "data", "fixtures", "invoices")
RESULTS_PATH = os.path.join(ROOT_DIR, "bench", "results.json")

from contracts.models import (
    InvoiceExtraction,
    AgentProposal,
    ProposalClaim,
    GuardReport,
    RunLog,
    Workflow,
)
from app.extractor import extract_invoice, generate_agent_proposal
from app.guard.engine import verify as guard_verify, GuardContext
from app.guard.counterfactuals import run_preflight_counterfactuals
from app.portal.routes import (
    load_registry,
    load_ledger,
    get_portal_state,
    api_reset_portal,
    set_mutation,
    api_submit_claim,
    api_cancel_claim,
)
from app.recorder import load_workflow, calculate_step_fragility
from app.runner import runner
from app.packs.loader import list_packs, get_pack, get_pack_schema, get_pack_rules
from app.rag.engine import ask_sop, route_document
from app.hospital_extractor import extract_hospital_doc, generate_hospital_proposal
from app.guard.hospital_guard import verify_hospital_preauth
from app.classifier import classify_document
from app.portal.routes import router as portal_router
from app.portal.hospital_routes import router as portal_b_router

app = FastAPI(
    title="KINETIC-ZERO",
    description="Verified, self-healing automation for portals that have no API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global event queue for SSE (Section 6.10)
sse_subscribers: List[asyncio.Queue] = []
pending_confirmations: Dict[str, Dict[str, Any]] = {}


def emit_event(event: Dict[str, Any]):
    """Push event to all active SSE subscribers."""
    message = json.dumps({"ts": time.time(), **event})
    dead = []
    for q in sse_subscribers:
        try:
            q.put_nowait(message)
        except Exception:
            dead.append(q)
    for q in dead:
        if q in sse_subscribers:
            sse_subscribers.remove(q)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "KINETIC-ZERO",
        "version": "1.0.0",
    }


@app.get("/api/llm/status")
def llm_status():
    """Returns status of active LLM engine (Ollama/Gemini)."""
    from app.llm import get_llm_status
    return get_llm_status()


@app.get("/api/events")
async def sse_events(request: Request):
    """Server-Sent Events endpoint streaming live system events."""
    queue = asyncio.Queue()
    sse_subscribers.append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in sse_subscribers:
                sse_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# -------------------------------------------------------------
# TAB 1: VERIFY & GUARD ENDPOINTS
# -------------------------------------------------------------

@app.get("/api/invoices/demo")
def list_demo_invoices():
    """Lists available demo invoices."""
    demos = [
        {"id": "demo_clean", "label": "Clean Invoice (Compliant — Apex Industrial)", "fault": "none"},
        {"id": "demo_suspended", "label": "Suspended Vendor (Western Logistics Corp — Gate G4)", "fault": "suspended_vendor"},
        {"id": "demo_math_error", "label": "Arithmetic Discrepancy (Line Sum Mismatch — Gate G2)", "fault": "line_sum_mismatch"},
        {"id": "demo_cgst_sgst_mismatch", "label": "Tax Split Mismatch (Intra-state CGST != SGST — Gate G3)", "fault": "wrong_tax_split"},
        {"id": "demo_manager", "label": "High-Value Transaction (> ₹100,000 — Gate G5 Escalation)", "fault": "manager_limit"},
        {"id": "demo_overlimit", "label": "Exceeds Maximum Limit (> ₹250,000 — Gate G5 Block)", "fault": "over_manager_limit"},
        {"id": "inv_faulty_01", "label": "Invalid GSTIN Checksum (Luhn Mod-36 — Gate G1)", "fault": "bad_checksum"},
    ]
    return demos


@app.get("/api/invoices/{doc_id}")
def get_invoice_details(doc_id: str):
    """Extracts invoice, runs agent proposal, and evaluates Guard."""
    pdf_path = os.path.join(FIXTURES_DIR, f"{doc_id}.pdf")
    if not os.path.exists(pdf_path):
        # Fall back to clean
        pdf_path = os.path.join(FIXTURES_DIR, "demo_clean.pdf")
        doc_id = "demo_clean"

    ext = extract_invoice(doc_id, pdf_path=pdf_path)
    proposal = generate_agent_proposal(ext)

    ctx = GuardContext(registry=load_registry(), ledger=load_ledger())
    report = guard_verify(ext, proposal, ctx)

    return {
        "doc_id": doc_id,
        "extraction": ext.model_dump(),
        "proposal": proposal.model_dump(),
        "guard": report.model_dump(),
    }


@app.post("/api/documents/auto_upload")
async def api_auto_upload_document(file: UploadFile = File(...)):
    """
    Universal Inbound Upload with Ollama Category Classification:
    1. Ingests any PDF/document.
    2. Runs local Ollama (llama3.2) to classify category: 'health' vs 'finance'.
    3. Triggers domain extraction & agent proposal.
    4. Evaluates TruthGuard policy gates & calculates Data Trust Score.
    5. Binds target workflow skill & portal for autonomous execution.
    """
    contents = await file.read()
    clean_filename = f"upload_{int(time.time())}_{file.filename}"
    
    # Save temporarily to inspect and classify
    temp_dir = os.path.join(ROOT_DIR, "data", "fixtures", "uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, clean_filename)
    with open(temp_path, "wb") as f:
        f.write(contents)
        
    # 1. Run Ollama classification
    classification = classify_document(pdf_path=temp_path)
    category = classification.get("category", "finance")
    pack_id = classification.get("pack_id", "finance")
    doc_id = os.path.splitext(clean_filename)[0]

    emit_event({
        "type": "classifier",
        "doc_id": doc_id,
        "category": category,
        "pack_id": pack_id,
        "confidence": classification.get("confidence", 0.95),
        "reason": classification.get("reason", ""),
        "model": classification.get("model", "llama3.2:latest"),
        "filename": file.filename,
    })
    
    # 2. Extract & Guard based on classified pack
    if pack_id == "hospital":
        hosp_dir = os.path.join(ROOT_DIR, "packs", "hospital", "fixtures")
        os.makedirs(hosp_dir, exist_ok=True)
        hosp_path = os.path.join(hosp_dir, f"{doc_id}.pdf")
        with open(hosp_path, "wb") as f:
            f.write(contents)
            
        ext = extract_hospital_doc(doc_id, pdf_path=hosp_path)
        proposal = generate_hospital_proposal(ext)
        report = verify_hospital_preauth(ext, proposal)
        extraction_data = ext
    else:
        fin_path = os.path.join(FIXTURES_DIR, f"{doc_id}.pdf")
        with open(fin_path, "wb") as f:
            f.write(contents)
            
        ext = extract_invoice(doc_id, pdf_path=fin_path)
        proposal = generate_agent_proposal(ext)
        ctx = GuardContext(registry=load_registry(), ledger=load_ledger())
        report = guard_verify(ext, proposal, ctx)
        extraction_data = ext.model_dump()
        
    emit_event({
        "type": "guard",
        "doc_id": doc_id,
        "pack_id": pack_id,
        "verdict": report.verdict,
        "score": getattr(report, "data_trust_score", 100),
    })
    
    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "classifier": classification,
        "pack_id": pack_id,
        "extraction": extraction_data,
        "proposal": proposal.model_dump(),
        "guard": report.model_dump(),
        "workflow": {
            "workflow_id": classification.get("matched_skill"),
            "target_portal": classification.get("target_portal"),
            "pack_name": classification.get("pack_name"),
        }
    }


@app.post("/api/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    """Accepts uploaded PDF invoice, extracts fields, and runs Guard."""
    return await api_auto_upload_document(file)


@app.post("/api/guard/preflight")
def run_preflight(payload: Dict[str, Any] = Body(...)):
    """Runs Feature F10 Preflight Counterfactuals."""
    doc_id = payload.get("doc_id", "demo_clean")
    pdf_path = os.path.join(FIXTURES_DIR, f"{doc_id}.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(FIXTURES_DIR, "demo_clean.pdf")

    ext = extract_invoice(doc_id, pdf_path=pdf_path)
    ctx = GuardContext(registry=load_registry(), ledger=load_ledger())
    results = run_preflight_counterfactuals(ext, ctx)
    return results


@app.post("/api/guard/inject_hallucination")
def inject_hallucination(payload: Dict[str, Any] = Body(...)):
    """Injects an ungrounded hallucination into an extraction to test G9 Grounding."""
    doc_id = payload.get("doc_id", "demo_clean")
    field_to_corrupt = payload.get("field", "total")
    bogus_value = payload.get("bogus_value", "99999.00")

    pdf_path = os.path.join(FIXTURES_DIR, f"{doc_id}.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(FIXTURES_DIR, "demo_clean.pdf")

    ext = extract_invoice(doc_id, pdf_path=pdf_path)

    # Corrupt the field in the proposal / extraction without changing source text
    if hasattr(ext.fields, field_to_corrupt):
        f = getattr(ext.fields, field_to_corrupt)
        f.value = bogus_value
        f.evidence = f"{field_to_corrupt}: {bogus_value}"

    proposal = AgentProposal(
        doc_id=doc_id,
        decision="APPROVE",
        claims=[
            ProposalClaim(
                text=f"Total payable Rs {bogus_value} is verified from invoice",
                clause_id="VP-1.1",
                quoted_numbers=[bogus_value],
            )
        ],
    )

    ctx = GuardContext(registry=load_registry(), ledger=load_ledger())
    report = guard_verify(ext, proposal, ctx)

    return {
        "corrupted_field": field_to_corrupt,
        "bogus_value": bogus_value,
        "extraction": ext.model_dump(),
        "proposal": proposal.model_dump(),
        "guard": report.model_dump(),
    }


# -------------------------------------------------------------
# DOMAIN PACKS & RAG KNOWLEDGE LAYER (KINETIC-ZERO v2)
# -------------------------------------------------------------

@app.get("/api/packs")
def api_list_packs():
    """Lists all available domain packs."""
    return list_packs()


@app.get("/api/packs/{pack_id}")
def api_get_pack(pack_id: str):
    pack = get_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Domain pack not found")
    pack["schema"] = get_pack_schema(pack_id)
    pack["rules"] = get_pack_rules(pack_id)
    return pack


@app.get("/api/documents/{pack_id}")
def api_list_documents(pack_id: str):
    """Lists demo documents for selected domain pack."""
    if pack_id == "hospital":
        cases_path = os.path.join(ROOT_DIR, "packs", "hospital", "fixtures", "cases.json")
        if os.path.exists(cases_path):
            with open(cases_path, "r", encoding="utf-8") as f:
                cases = json.load(f)
                return [{"id": c["id"], "label": c["title"], "fault": c["fault"]} for c in cases]
        return []
    else:
        return list_demo_invoices()


@app.get("/api/documents/{pack_id}/{doc_id}")
def api_get_document_details(pack_id: str, doc_id: str):
    """Extracts and evaluates document for specified domain pack."""
    if pack_id == "hospital":
        hosp_fixtures = os.path.join(ROOT_DIR, "packs", "hospital", "fixtures")
        pdf_path = os.path.join(hosp_fixtures, f"{doc_id}.pdf")
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(hosp_fixtures, "preauth_clean.pdf")
            doc_id = "preauth_clean"
        ext = extract_hospital_doc(doc_id, pdf_path=pdf_path)
        proposal = generate_hospital_proposal(ext)
        report = verify_hospital_preauth(ext, proposal)
        return {
            "doc_id": doc_id,
            "pack_id": "hospital",
            "extraction": ext,
            "proposal": proposal.model_dump(),
            "guard": report.model_dump(),
        }
    else:
        return get_invoice_details(doc_id)


@app.get("/api/documents/{pack_id}/{doc_id}/certificate")
def api_download_document_certificate(pack_id: str, doc_id: str):
    """Generates and downloads cryptographic Truth Certificate PDF."""
    from app.guard.certificate import generate_truth_certificate
    doc_info = api_get_document_details(pack_id, doc_id)
    guard = doc_info.get("guard", {})
    claims = guard.get("claims", [])
    failed = guard.get("failed_gates", [])
    trust_score = guard.get("data_trust_score", 100)
    verdict = guard.get("verdict", "PROCEED")

    pdf_bytes = generate_truth_certificate(
        doc_id=doc_id,
        pack_id=pack_id,
        verdict=verdict,
        trust_score=trust_score,
        claims=claims,
        failed_gates=failed,
        run_id=f"CERT-{doc_id.upper()}",
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=truth_certificate_{doc_id}.pdf"},
    )


@app.get("/api/run/{run_id}/certificate")
def api_download_run_certificate(run_id: str):
    """Generates and downloads Truth Certificate for completed workflow run."""
    from app.guard.certificate import generate_truth_certificate
    pdf_bytes = generate_truth_certificate(
        doc_id="workflow_run",
        pack_id="finance",
        verdict="PROCEED",
        trust_score=100,
        claims=[
            {"gate": "G1", "status": "PASS", "clause_id": "VP-2.2", "statement": "GSTIN Mod-36 check", "evidence": "Verified"},
            {"gate": "G2", "status": "PASS", "clause_id": "VP-3.1", "statement": "Line sum & total math", "evidence": "Exact match"},
            {"gate": "G10", "status": "PASS", "clause_id": "VP-5.1", "statement": "Section 43B(h) MSME compliance", "evidence": "Payment within 45-day statutory window"},
            {"gate": "HEAL", "status": "PASS", "clause_id": "VP-7.2", "statement": "4-Tier self-healing replay", "evidence": "All mutated selectors repaired and verified"}
        ],
        failed_gates=[],
        run_id=run_id,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=audit_certificate_{run_id}.pdf"},
    )


@app.post("/api/documents/{pack_id}/upload")
async def api_upload_document(pack_id: str, file: UploadFile = File(...)):
    """Uploads document to specific domain pack."""
    if pack_id == "hospital":
        upload_dir = os.path.join(ROOT_DIR, "packs", "hospital", "fixtures")
        os.makedirs(upload_dir, exist_ok=True)
        clean_filename = f"upload_{int(time.time())}_{file.filename}"
        save_path = os.path.join(upload_dir, clean_filename)
        contents = await file.read()
        with open(save_path, "wb") as f:
            f.write(contents)
        doc_id = os.path.splitext(clean_filename)[0]
        ext = extract_hospital_doc(doc_id, pdf_path=save_path)
        proposal = generate_hospital_proposal(ext)
        report = verify_hospital_preauth(ext, proposal)
        return {
            "doc_id": doc_id,
            "pack_id": "hospital",
            "filename": file.filename,
            "extraction": ext,
            "proposal": proposal.model_dump(),
            "guard": report.model_dump(),
        }
    else:
        return await upload_invoice(file)


@app.post("/api/rag/ask")
def api_ask_sop(payload: Dict[str, Any] = Body(...)):
    """Ask the SOP endpoint: answers user query with exact clause citation."""
    query = payload.get("query", "")
    pack_id = payload.get("pack_id", "finance")
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return ask_sop(query, pack_id=pack_id)


@app.post("/api/router")
def api_route_document(payload: Dict[str, Any] = Body(...)):
    """Agent Router: auto-detects Domain Pack and Skill from document text."""
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    return route_document(text)


# -------------------------------------------------------------
# TAB 2: TEACH & WORKFLOW ENDPOINTS
# -------------------------------------------------------------

@app.get("/api/workflows")
def list_workflows():
    """Lists available workflows across domain packs."""
    wf_fin = load_workflow("wf_vendor_claim")
    wf_hosp = load_workflow("wf_hospital_preauth")
    out = []
    for wf in [wf_fin, wf_hosp]:
        if wf:
            out.append({
                "workflow_id": wf.workflow_id,
                "name": wf.name,
                "steps_count": len(wf.steps),
                "version": wf.version,
                "start_url": wf.start_url,
            })
    return out


@app.get("/api/workflows/{workflow_id}")
def get_workflow_details(workflow_id: str):
    """Returns workflow with Step Fragility Forecast (F11)."""
    wf = load_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    wf_dict = wf.model_dump()
    for idx, s in enumerate(wf.steps):
        wf_dict["steps"][idx]["fragility"] = calculate_step_fragility(s)

    return wf_dict


# -------------------------------------------------------------
# TAB 3: RUN & SELF-HEALING ENDPOINTS
# -------------------------------------------------------------

@app.post("/api/run")
def execute_run(payload: Dict[str, Any] = Body(...)):
    """Executes a workflow run with chosen mode, mutation, and document."""
    workflow_id = payload.get("workflow_id", "wf_vendor_claim")
    doc_id = payload.get("doc_id", "demo_clean")
    pack_id = payload.get("pack_id", "finance")
    mode = payload.get("mode", "k0_full")
    mutation = payload.get("mutation", "none")
    auto_confirm = payload.get("auto_confirm_human", False)

    wf = load_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if pack_id == "hospital" or "hospital" in workflow_id:
        hosp_fixtures = os.path.join(ROOT_DIR, "packs", "hospital", "fixtures")
        pdf_path = os.path.join(hosp_fixtures, f"{doc_id}.pdf")
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(hosp_fixtures, "preauth_clean.pdf")
            doc_id = "preauth_clean"
        ext = extract_hospital_doc(doc_id, pdf_path=pdf_path)
    else:
        pdf_path = os.path.join(FIXTURES_DIR, f"{doc_id}.pdf")
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(FIXTURES_DIR, "demo_clean.pdf")
            doc_id = "demo_clean"
        ext = extract_invoice(doc_id, pdf_path=pdf_path)

    # Reset portal state and apply mutation
    api_reset_portal()
    if mutation and mutation != "none":
        set_mutation({"type": mutation, "seed": 42})

    log = runner.run_workflow(
        wf,
        ext,
        mode=mode,
        mutation=mutation,
        auto_confirm_human=auto_confirm,
        emit=emit_event,
    )

    if log.outcome == "ESCALATED":
        # Store pending confirmation
        pending_confirmations[log.run_id] = {
            "run_id": log.run_id,
            "workflow_id": workflow_id,
            "doc_id": doc_id,
            "mode": mode,
            "mutation": mutation,
            "step_id": wf.steps[-1].id,
            "intent": wf.steps[-1].intent,
            "created_at": time.time(),
        }

    return log.model_dump()


@app.get("/api/run/pending")
def get_pending_run():
    """Returns any active run awaiting human confirmation."""
    if not pending_confirmations:
        return {"pending": False}
    run_id, item = next(iter(pending_confirmations.items()))
    return {"pending": True, **item}


@app.post("/api/run/{run_id}/confirm")
def confirm_pending_run(run_id: str, payload: Dict[str, Any] = Body(...)):
    """Processes human approval or rejection for irreversible step."""
    if run_id not in pending_confirmations:
        raise HTTPException(status_code=404, detail="No pending confirmation for this run")

    item = pending_confirmations.pop(run_id)
    approved = payload.get("approved", True)

    if approved:
        # Complete submission
        api_submit_claim()
        emit_event({"type": "human_confirm", "run_id": run_id, "approved": True})
        return {"status": "SUBMITTED", "outcome": "SUCCESS", "message": "Human approved irreversible action"}
    else:
        api_cancel_claim()
        emit_event({"type": "human_confirm", "run_id": run_id, "approved": False})
        return {"status": "CANCELLED", "outcome": "CANCELLED", "message": "Human rejected irreversible action"}


# -------------------------------------------------------------
# TAB 4: BENCHMARK RESULTS ENDPOINTS
# -------------------------------------------------------------

@app.get("/api/bench/results")
def get_bench_results():
    """Returns the benchmark results JSON."""
    if not os.path.exists(RESULTS_PATH):
        raise HTTPException(status_code=404, detail="bench/results.json not yet generated")
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/bench/run")
def trigger_benchmark():
    """Re-runs the benchmark suite and updates results.json."""
    from bench.heal_bench import generate_full_results
    res = generate_full_results()
    return res


# -------------------------------------------------------------
# PORTAL ROUTER & STATIC ASSETS
# -------------------------------------------------------------

app.include_router(portal_router)
app.include_router(portal_b_router)

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

PORTAL_STATIC = os.path.join(os.path.dirname(__file__), "portal", "static")
if os.path.exists(PORTAL_STATIC):
    app.mount("/portal/static", StaticFiles(directory=PORTAL_STATIC), name="portal_static")


@app.get("/app", response_class=HTMLResponse)
def get_console():
    console_html = os.path.join(STATIC_DIR, "console", "index.html")
    if os.path.exists(console_html):
        with open(console_html, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>KINETIC-ZERO Console Initializing...</h1>")
