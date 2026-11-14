"""
Data Trust Score and Soft Evidence Evaluator.
Follows SPEC.txt Section 6.2.
"""

from typing import Dict, Any, Optional
from rapidfuzz import fuzz
from contracts.models import InvoiceExtraction, AgentProposal, TrustComponents


def compute_trust_score(
    extraction: InvoiceExtraction,
    proposal: Optional[AgentProposal] = None,
    policy_index: Any = None,
) -> tuple[int, TrustComponents]:
    """
    Computes heuristic Data Trust Score (0-100) and its components S, A, P.
    S = Source Grounding Evidence Agreement (rapidfuzz partial_ratio >= 95)
    A = Dual-Pass Extraction Agreement
    P = Policy Grounding Ratio
    """
    # 1. S component: Field evidence agreement
    fields = [
        extraction.fields.vendor_name,
        extraction.fields.vendor_gstin,
        extraction.fields.buyer_gstin,
        extraction.fields.invoice_no,
        extraction.fields.invoice_date,
        extraction.fields.po_number,
        extraction.fields.taxable_value,
        extraction.fields.cgst,
        extraction.fields.sgst,
        extraction.fields.igst,
        extraction.fields.total,
    ]
    non_empty_fields = [f for f in fields if f.value]
    if not non_empty_fields:
        S = 0.0
    else:
        grounded_count = 0
        for f in non_empty_fields:
            if not f.evidence:
                continue
            ratio = fuzz.partial_ratio(f.evidence.lower(), extraction.source_text.lower())
            val_in_ev = (f.value.lower() in f.evidence.lower())
            if ratio >= 95 and val_in_ev:
                grounded_count += 1
        S = grounded_count / len(non_empty_fields)

    # 2. A component: Pass agreement
    if extraction.passes == 2:
        agree_count = 0
        for f in non_empty_fields:
            if f.pass2_value and f.value.strip().lower() == f.pass2_value.strip().lower():
                agree_count += 1
        A = agree_count / len(non_empty_fields) if non_empty_fields else 1.0
    else:
        A = 1.0 if extraction.source_type == "pdf_text" else 0.5

    # 3. P component: Policy claim grounding
    if proposal and proposal.claims and policy_index:
        p_count = 0
        for claim in proposal.claims:
            top_clauses = policy_index.retrieve(claim.text, k=3)
            clause_ids = [c.clause_id for c in top_clauses]
            if claim.clause_id in clause_ids:
                p_count += 1
        P = p_count / len(proposal.claims)
    else:
        P = 1.0 if (proposal and not proposal.claims) else 0.8

    # Heuristic weights: S=0.45, A=0.35, P=0.20
    score = round(100 * (0.45 * S + 0.35 * A + 0.20 * P))
    score = max(0, min(100, score))

    components = TrustComponents(
        S=round(float(S), 2),
        A=round(float(A), 2),
        P=round(float(P), 2),
    )
    return score, components
