"""
Unit & CI Tests for Policy Index and Retrieval.
Follows SPEC.txt Section 6.3 and M2 Policy Acceptance Criteria.
"""

import os
import json
import pytest
from app.policy.index import PolicyIndex, SOP_PATH, POLICY_JSON_PATH
from app.policy.retrieve import retrieve, exists, numbers_in
from contracts.models import AgentProposal, ProposalClaim
from app.guard.gates import check_g8_citation


def test_sop_clauses_parsed_count():
    p = PolicyIndex(SOP_PATH)
    # Must parse exactly 14 clauses: VP-1.1 to VP-7.2
    assert len(p.clause_list) == 14
    assert exists("VP-1.1")
    assert exists("VP-4.2")
    assert exists("VP-7.2")


def test_manager_approval_limit_retrieves_vp42_in_top1():
    """SPEC criteria: query 'manager approval limit' returns VP-4.2 in top 1."""
    results = retrieve("manager approval limit", k=3)
    assert len(results) > 0
    assert results[0].clause_id == "VP-4.2"
    assert "Manager approval" in results[0].title


def test_ci_policy_json_numbers_appear_in_clause_text():
    """
    CI test: every number in policy.json must appear in its clause text.
    This guarantees that machine-readable rules and cited SOP text never drift apart.
    """
    with open(POLICY_JSON_PATH, "r", encoding="utf-8") as f:
        policy_cfg = json.load(f)

    p = PolicyIndex(SOP_PATH)
    clause_for = policy_cfg.get("clause_for", {})

    for key, c_id in clause_for.items():
        val = policy_cfg.get(key)
        assert exists(c_id), f"Clause {c_id} referenced in policy.json not in SOP"
        clause_numbers = numbers_in(c_id)

        if isinstance(val, list):
            for item in val:
                assert str(item) in clause_numbers, f"Number {item} from policy.json not found in clause {c_id} text"
        elif isinstance(val, (int, float)):
            assert str(val) in clause_numbers, f"Number {val} from policy.json not found in clause {c_id} text"


def test_fabricated_clause_fails_g8():
    """SPEC criteria: fabricated clause VP-9.9 fails G8."""
    p = PolicyIndex(SOP_PATH)
    proposal = AgentProposal(
        doc_id="test",
        decision="APPROVE",
        claims=[ProposalClaim(text="Fabricated rule", clause_id="VP-9.9", quoted_numbers=[])],
    )
    claim = check_g8_citation(proposal, p)
    assert claim.status == "FAIL"
    assert "VP-9.9" in claim.evidence


def test_fabricated_quoted_number_fails_g8():
    """Citing real clause but hallucinating numbers not in text fails G8."""
    p = PolicyIndex(SOP_PATH)
    proposal = AgentProposal(
        doc_id="test",
        decision="APPROVE",
        claims=[ProposalClaim(text="Limit claim", clause_id="VP-4.1", quoted_numbers=["9999999"])],
    )
    claim = check_g8_citation(proposal, p)
    assert claim.status == "FAIL"
    assert "9999999" in claim.evidence
