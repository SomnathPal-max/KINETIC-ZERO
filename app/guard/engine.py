"""
Guard Engine for KINETIC-ZERO.
Pure verification function: pure Python, zero network calls, zero LLMs.
Follows SPEC.txt Section 6.2 and Section 8.
"""

from datetime import date
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict
from contracts.models import InvoiceExtraction, AgentProposal, GuardReport, GuardClaim
from app.guard.gates import (
    check_g1_gstin,
    check_g2_arithmetic,
    check_g3_tax_split,
    check_g4_registry,
    check_g5_amount_policy,
    check_g6_duplicate,
    check_g7_dates,
    check_g8_citation,
    check_g9_grounding,
    check_g10_msme,
    check_g11_einvoice,
)
from app.guard.score import compute_trust_score


class GuardContext:
    def __init__(
        self,
        registry: Dict[str, Any],
        ledger: List[Dict[str, Any]],
        policy: Any = None,
        today: Optional[date] = None,
    ):
        self.registry = registry
        self.ledger = ledger
        if policy is None:
            from app.policy.index import policy_index
            policy = policy_index
        self.policy = policy
        self.today = today or date.today()


def verify(
    extraction: InvoiceExtraction,
    proposal: Optional[AgentProposal] = None,
    ctx: Optional[GuardContext] = None,
) -> GuardReport:
    """
    Pure deterministic guard function.
    Evaluates hard gates G1-G9, computes soft data trust score, determines verdict,
    and flags AI overruling without using any LLM.
    """
    if ctx is None:
        ctx = GuardContext(registry={}, ledger=[], policy=None)

    buyer_gstin = ctx.registry.get("buyer", {}).get("gstin", "27AAAPL1234F1Z5")

    # Run hard gates G1-G9
    claims: List[GuardClaim] = [
        check_g1_gstin(extraction),
        check_g2_arithmetic(extraction),
        check_g3_tax_split(extraction, buyer_gstin=buyer_gstin),
        check_g4_registry(extraction, ctx.registry),
        check_g5_amount_policy(extraction),
        check_g6_duplicate(extraction, ctx.ledger),
        check_g7_dates(extraction, today=ctx.today),
        check_g8_citation(proposal, ctx.policy),
        check_g9_grounding(extraction),
        check_g10_msme(extraction, ctx.registry, today=ctx.today),
        check_g11_einvoice(extraction),
    ]

    failed_gates = [c.gate for c in claims if c.status == "FAIL" and c.gate]
    escalate_gates = [c.gate for c in claims if c.status == "ESCALATE" and c.gate]

    # Compute soft Data Trust Score
    trust_score, components = compute_trust_score(extraction, proposal, ctx.policy)

    # Determine verdict
    has_unsupported = any(c.status == "UNSUPPORTED" for c in claims)
    if failed_gates:
        verdict = "BLOCK"
    elif escalate_gates or trust_score < 70 or has_unsupported:
        verdict = "ESCALATE"
    else:
        verdict = "PROCEED"

    # AI overruled check
    ai_decision = proposal.decision if proposal else "APPROVE"
    ai_overruled = (ai_decision == "APPROVE" and verdict != "PROCEED")

    # Template-generated explanation (never by LLM)
    explanation = _build_explanation(verdict, claims, failed_gates, escalate_gates, trust_score)

    return GuardReport(
        doc_id=extraction.doc_id,
        verdict=verdict,
        data_trust_score=trust_score,
        components=components,
        ai_overruled=ai_overruled,
        claims=claims,
        failed_gates=failed_gates,
        explanation=explanation,
    )


def _build_explanation(
    verdict: str,
    claims: List[GuardClaim],
    failed_gates: List[str],
    escalate_gates: List[str],
    trust_score: int,
) -> str:
    """Build concise explanation template (<= 3 sentences) from failed claims."""
    if verdict == "BLOCK":
        failed_reasons = [c.evidence for c in claims if c.status == "FAIL"]
        first_two = "; ".join(failed_reasons[:2])
        return f"Automation blocked by Guard hard gates ({', '.join(failed_gates)}). Violations: {first_two}. Run aborted before any browser action."
    elif verdict == "ESCALATE":
        if escalate_gates:
            reasons = [c.evidence for c in claims if c.status == "ESCALATE"]
            return f"Action requires human approval ({', '.join(escalate_gates)}): {reasons[0]}. Data Trust Score is {trust_score}/100."
        else:
            return f"Data Trust Score ({trust_score}/100) below threshold 70 or contains unverified evidence. Escalated for human review before action."
    else:
        return f"All 9 verification gates passed successfully with Data Trust Score {trust_score}/100. Certified safe to proceed with automated execution."
