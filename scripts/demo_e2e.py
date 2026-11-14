"""
End-to-End Integration Script for KINETIC-ZERO.
Follows SPEC.txt Section 10 (Milestone M3 Acceptance Criteria):
(a) Clean invoice -> PROCEED -> Mutate M6 -> Self-heal -> Portal state SUCCESS
(b) Suspended-vendor invoice -> BLOCK with zero browser actions
(c) Injected hallucination -> Grounding G9 BLOCK with ai_overruled=True
"""

import os
import sys

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app.extractor import extract_invoice, generate_agent_proposal
from app.guard.engine import verify as guard_verify, GuardContext
from app.recorder import load_workflow
from app.runner import runner
from app.portal.routes import (
    load_registry,
    load_ledger,
    get_portal_state,
    api_reset_portal,
    set_mutation,
)
from contracts.models import AgentProposal, ProposalClaim, FieldExtraction


def run_e2e_demo():
    print("=" * 60)
    print("🚀 STARTING KINETIC-ZERO E2E INTEGRATION SUITE")
    print("=" * 60)

    fixtures_dir = os.path.join(ROOT_DIR, "data", "fixtures", "invoices")

    # -------------------------------------------------------------
    # Scenario A: Clean invoice -> PROCEED -> Mutate M6 -> Self-heal -> SUCCESS
    # -------------------------------------------------------------
    print("\n--- [Scenario A] Clean Invoice Self-Healing under Chaos Mutation M6 ---")
    api_reset_portal()
    clean_pdf = os.path.join(fixtures_dir, "demo_clean.pdf")
    ext_a = extract_invoice("demo_clean", pdf_path=clean_pdf)
    prop_a = generate_agent_proposal(ext_a)

    ctx_a = GuardContext(registry=load_registry(), ledger=load_ledger())
    report_a = guard_verify(ext_a, prop_a, ctx_a)

    print(f"1. Guard Evaluation: Verdict = {report_a.verdict}, Trust Score = {report_a.data_trust_score}/100")
    assert report_a.verdict == "PROCEED", f"Expected PROCEED, got {report_a.verdict}"

    print("2. Applying Chaos Mutation M6 (combo: rename_ids + relabel + reorder + decoy)...")
    set_mutation({"type": "M6", "seed": 42})

    print("3. Executing workflow replay via KINETIC-ZERO 4-tier self-healing...")
    wf = load_workflow("wf_vendor_claim")
    log_a = runner.run_workflow(wf, ext_a, mode="k0_full", mutation="M6", auto_confirm_human=True)

    print(f"4. Workflow Run Finished: Outcome = {log_a.outcome}, Total Time = {log_a.total_ms}ms")
    healed_steps = [s for s in log_a.steps if s.status == "healed"]
    print(f"   Healed {len(healed_steps)} steps dynamically across tiers.")
    assert log_a.outcome == "SUCCESS", f"Expected SUCCESS, got {log_a.outcome}"

    state_a = get_portal_state()
    assert state_a["status"] == "SUBMITTED", "Expected portal state SUBMITTED"
    print("✅ Scenario A PASSED: Portal claim successfully submitted under extreme mutation M6!")

    # -------------------------------------------------------------
    # Scenario B: Suspended Vendor -> Guard BLOCK with Zero Browser Actions
    # -------------------------------------------------------------
    print("\n--- [Scenario B] Suspended-Vendor Invoice Safety Gate ---")
    api_reset_portal()
    susp_pdf = os.path.join(fixtures_dir, "demo_suspended.pdf")
    ext_b = extract_invoice("demo_suspended", pdf_path=susp_pdf)
    prop_b = AgentProposal(doc_id=ext_b.doc_id, decision="APPROVE", claims=[])

    ctx_b = GuardContext(registry=load_registry(), ledger=load_ledger())
    report_b = guard_verify(ext_b, prop_b, ctx_b)

    print(f"1. Guard Evaluation: Verdict = {report_b.verdict}, Failed Gates = {report_b.failed_gates}")
    assert report_b.verdict == "BLOCK", f"Expected BLOCK, got {report_b.verdict}"
    assert "G4" in report_b.failed_gates, "Expected Gate G4 in failed gates"

    print("2. Attempting runner execution...")
    log_b = runner.run_workflow(wf, ext_b, mode="k0_full")
    print(f"3. Runner Outcome = {log_b.outcome}, Browser Actions Executed = {len(log_b.steps)}")
    assert log_b.outcome == "BLOCKED"
    assert len(log_b.steps) == 0, "Zero browser actions must be executed on BLOCK"

    state_b = get_portal_state()
    assert state_b["status"] == "IDLE", "Portal state must remain completely unacted upon (IDLE)"
    print("✅ Scenario B PASSED: Blocked suspended vendor before any portal interaction!")

    # -------------------------------------------------------------
    # Scenario C: Injected Hallucination -> Grounding G9 BLOCK with AI Overruled
    # -------------------------------------------------------------
    print("\n--- [Scenario C] Injected Hallucination & Grounding Gate G9 ---")
    api_reset_portal()
    # Deep copy clean extraction and corrupt total to a hallucinated value absent from document
    ext_c = ext_a.model_copy(deep=True)
    hallucinated_total = "99999.00"
    ext_c.fields.total = FieldExtraction(value=hallucinated_total, evidence="Hallucinated total")

    # AI is tricked into proposing APPROVE
    prop_c = AgentProposal(
        doc_id=ext_c.doc_id,
        decision="APPROVE",
        claims=[ProposalClaim(text="Total under limit", clause_id="VP-4.1", quoted_numbers=["100000"])],
    )

    ctx_c = GuardContext(registry=load_registry(), ledger=load_ledger())
    report_c = guard_verify(ext_c, prop_c, ctx_c)

    print(f"1. Guard Evaluation: Verdict = {report_c.verdict}, Failed Gates = {report_c.failed_gates}")
    print(f"   AI Proposed = {prop_c.decision}, AI Overruled = {report_c.ai_overruled}")
    assert report_c.verdict == "BLOCK", f"Expected BLOCK, got {report_c.verdict}"
    assert "G9" in report_c.failed_gates or "G2" in report_c.failed_gates
    assert report_c.ai_overruled is True, "AI proposal must be explicitly overruled by Guard"

    print("✅ Scenario C PASSED: Grounding gate caught hallucinated total and overruled AI decision!")

    print("\n" + "=" * 60)
    print("🎉 ALL M3 END-TO-END DEMO SCENARIOS PASSED WITH 100% SUCCESS!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_e2e_demo()
    sys.exit(0 if success else 1)
