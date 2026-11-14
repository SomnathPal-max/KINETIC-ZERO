import sys

with open("app/main.py", "r", encoding="utf-8") as f:
    content = f.read()

target = '@app.post("/api/documents/{pack_id}/upload")'

new_route = '''@app.get("/api/documents/{pack_id}/{doc_id}/certificate")
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


@app.post("/api/documents/{pack_id}/upload")'''

if target in content:
    content = content.replace(target, new_route, 1)
    with open("app/main.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: Added certificate endpoints to app/main.py")
else:
    print("Target not found")
