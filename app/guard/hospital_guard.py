"""
TruthGuard Safety Gates for Hospital Domain Pack (Healthcare Pre-Authorization).
Pure Python, zero network calls, zero LLMs.
Evaluates HP_G1 through HP_G9.
"""

from datetime import date, datetime
from typing import Dict, Any, List, Optional
from contracts.models import GuardReport, GuardClaim, TrustComponents, AgentProposal
from app.packs.loader import get_pack_registry, get_pack_ledger
from app.rag.engine import get_rag_index


def verify_hospital_preauth(
    extraction_data: Dict[str, Any],
    proposal: Optional[AgentProposal] = None,
    today: Optional[date] = None,
) -> GuardReport:
    """
    Evaluates TruthGuard rules for Hospital Pre-Authorization.
    """
    today = today or date.today()
    fields = extraction_data.get("fields", {})
    source_text = extraction_data.get("source_text", "")
    doc_id = extraction_data.get("doc_id", "hospital_doc")

    policies = get_pack_registry("hospital")
    claims_ledger = get_pack_ledger("hospital")
    hospitals = {
        "HSP-001": {"status": "EMPANELLED"},
        "HSP-002": {"status": "EMPANELLED"},
        "HSP-003": {"status": "EMPANELLED"},
        "HSP-999": {"status": "NON_EMPANELLED"},
    }

    claims: List[GuardClaim] = []

    # Helper to get field value
    def gv(f_name: str) -> str:
        f = fields.get(f_name, {})
        if isinstance(f, dict):
            return str(f.get("value", "")).strip()
        return str(f).strip()

    pat_name = gv("patient_name")
    pat_id = gv("patient_id")
    policy_no = gv("policy_number")
    diagnosis = gv("diagnosis_code").upper()
    hosp_id = gv("hospital_id").upper()
    adm_date_str = gv("admission_date")
    cost_str = gv("estimated_cost")

    try:
        cost = float(cost_str) if cost_str else 0.0
    except ValueError:
        cost = 0.0

    # 1. Gate HP_G1: Policy Active Status (HP-1.1)
    pol_info = policies.get(policy_no)
    if not pol_info:
        claims.append(GuardClaim(
            id="HP_C1", statement=f"Policy {policy_no} not found in insurer central registry",
            kind="hard", gate="HP_G1", status="FAIL", evidence=f"Policy: {policy_no}", clause_id="HP-1.1"
        ))
    elif pol_info.get("status") != "ACTIVE":
        claims.append(GuardClaim(
            id="HP_C1", statement=f"Policy {policy_no} status is {pol_info.get('status')} (must be ACTIVE)",
            kind="hard", gate="HP_G1", status="FAIL", evidence=f"Policy: {policy_no} ({pol_info.get('status')})", clause_id="HP-1.1"
        ))
    else:
        claims.append(GuardClaim(
            id="HP_C1", statement=f"Policy {policy_no} is ACTIVE with valid coverage",
            kind="hard", gate="HP_G1", status="PASS", evidence=f"Policy: {policy_no} [ACTIVE]", clause_id="HP-1.1"
        ))

    # 2. Gate HP_G2: Covered Diagnosis Code (HP-2.1)
    covered_codes = ["J18", "K35", "M16", "I20", "S72", "E11"]
    if not diagnosis or diagnosis not in covered_codes:
        claims.append(GuardClaim(
            id="HP_C2", statement=f"Diagnosis code {diagnosis} is not an authorized cashless admission category (cosmetic/uncovered)",
            kind="hard", gate="HP_G2", status="FAIL", evidence=f"Diagnosis: {diagnosis}", clause_id="HP-2.1"
        ))
    else:
        claims.append(GuardClaim(
            id="HP_C2", statement=f"Diagnosis code {diagnosis} is authorized for inpatient cashless pre-authorization",
            kind="hard", gate="HP_G2", status="PASS", evidence=f"Diagnosis: {diagnosis}", clause_id="HP-2.1"
        ))

    # 3. Gate HP_G3: Cost Limits & Escalation (HP-3.1, HP-3.2, HP-3.3)
    if cost > 200000.0:
        claims.append(GuardClaim(
            id="HP_C3", statement=f"Estimated procedure cost Rs {cost:,.2f} exceeds standard portal ceiling of Rs 200,000.00",
            kind="hard", gate="HP_G3", status="FAIL", evidence=f"Cost: Rs {cost:,.2f}", clause_id="HP-3.3"
        ))
    elif cost > 50000.0:
        claims.append(GuardClaim(
            id="HP_C3", statement=f"Estimated procedure cost Rs {cost:,.2f} requires Medical Director escalation (> Rs 50,000.00)",
            kind="hard", gate="HP_G3", status="ESCALATE", evidence=f"Cost: Rs {cost:,.2f}", clause_id="HP-3.2"
        ))
    elif cost <= 0:
        claims.append(GuardClaim(
            id="HP_C3", statement="Estimated cost must be greater than zero",
            kind="hard", gate="HP_G3", status="FAIL", evidence=f"Cost: Rs {cost:,.2f}", clause_id="HP-3.1"
        ))
    else:
        claims.append(GuardClaim(
            id="HP_C3", statement=f"Estimated cost Rs {cost:,.2f} is within auto-approval threshold of Rs 50,000.00",
            kind="hard", gate="HP_G3", status="PASS", evidence=f"Cost: Rs {cost:,.2f}", clause_id="HP-3.1"
        ))

    # 4. Gate HP_G4: Empanelled Hospital Network (HP-4.1)
    hosp_info = hospitals.get(hosp_id)
    if not hosp_info or hosp_info.get("status") != "EMPANELLED":
        claims.append(GuardClaim(
            id="HP_C4", statement=f"Hospital {hosp_id} is not an empanelled provider in insurer network",
            kind="hard", gate="HP_G4", status="FAIL", evidence=f"Hospital ID: {hosp_id}", clause_id="HP-4.1"
        ))
    else:
        claims.append(GuardClaim(
            id="HP_C4", statement=f"Hospital {hosp_id} is credentialed and empanelled in cashless network",
            kind="hard", gate="HP_G4", status="PASS", evidence=f"Hospital ID: {hosp_id} [EMPANELLED]", clause_id="HP-4.1"
        ))

    # 5. Gate HP_G5: Duplicate Pre-auth Request (HP-1.2)
    if pat_id in claims_ledger:
        claims.append(GuardClaim(
            id="HP_C5", statement=f"Duplicate request: Patient {pat_id} already has a submitted pre-auth in ledger",
            kind="hard", gate="HP_G5", status="FAIL", evidence=f"Patient ID: {pat_id}", clause_id="HP-1.2"
        ))
    else:
        claims.append(GuardClaim(
            id="HP_C5", statement=f"Patient {pat_id} pre-authorization is unique (no duplicate found)",
            kind="hard", gate="HP_G5", status="PASS", evidence=f"Patient ID: {pat_id}", clause_id="HP-1.2"
        ))

    # 6. Gate HP_G6: Admission Date Window (HP-5.1)
    date_valid = True
    try:
        adm_date = datetime.strptime(adm_date_str, "%Y-%m-%d").date()
        if adm_date < today:
            claims.append(GuardClaim(
                id="HP_C6", statement=f"Proposed admission date {adm_date_str} is in the past",
                kind="hard", gate="HP_G6", status="FAIL", evidence=f"Date: {adm_date_str}", clause_id="HP-5.1"
            ))
            date_valid = False
        else:
            claims.append(GuardClaim(
                id="HP_C6", statement=f"Proposed admission date {adm_date_str} is valid and prospective",
                kind="hard", gate="HP_G6", status="PASS", evidence=f"Date: {adm_date_str}", clause_id="HP-5.1"
            ))
    except Exception:
        claims.append(GuardClaim(
            id="HP_C6", statement=f"Invalid admission date format: {adm_date_str}",
            kind="hard", gate="HP_G6", status="FAIL", evidence=f"Date: {adm_date_str}", clause_id="HP-5.1"
        ))
        date_valid = False

    # 7. Gate HP_G9: Substring Grounding in Source Document (HP-5.2)
    src_clean = source_text.replace("\n", " ").lower()
    grounding_failures = []
    for k in ["patient_name", "patient_id", "policy_number", "diagnosis_code", "hospital_id"]:
        val = gv(k).lower()
        if val and val not in src_clean:
            grounding_failures.append(k)

    if grounding_failures:
        claims.append(GuardClaim(
            id="HP_C9", statement=f"Grounding failure: Extracted field(s) {grounding_failures} not found verbatim in intake document",
            kind="hard", gate="HP_G9", status="FAIL", evidence=f"Missing in source: {grounding_failures}", clause_id="HP-5.2"
        ))
    else:
        claims.append(GuardClaim(
            id="HP_C9", statement="All extracted fields verified verbatim against source document text layer",
            kind="hard", gate="HP_G9", status="PASS", evidence="100% Substring Grounded", clause_id="HP-5.2"
        ))

    # Compute verdict
    failed_gates = [c.gate for c in claims if c.status == "FAIL" and c.gate]
    escalate_gates = [c.gate for c in claims if c.status == "ESCALATE" and c.gate]

    if failed_gates:
        verdict = "BLOCK"
        score = 0
    elif escalate_gates:
        verdict = "ESCALATE"
        score = 80
    else:
        verdict = "PROCEED"
        score = 100

    ai_decision = proposal.decision if proposal else "APPROVE"
    ai_overruled = (ai_decision == "APPROVE" and verdict != "PROCEED")

    explanation = (
        f"TruthGuard Hospital Policy Engine: {len(failed_gates)} gate(s) failed, "
        f"{len(escalate_gates)} gate(s) escalated. Final Verdict: {verdict}."
    )

    return GuardReport(
        doc_id=doc_id,
        verdict=verdict,
        data_trust_score=score,
        components=TrustComponents(S=1.0 if not grounding_failures else 0.0, A=1.0, P=1.0 if not failed_gates else 0.0),
        ai_overruled=ai_overruled,
        claims=claims,
        failed_gates=failed_gates,
        explanation=explanation,
    )
