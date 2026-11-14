"""
Patch Verifier and Safety Gate for KINETIC-ZERO Healer.
Follows SPEC.txt Section 6.6.
"""

from typing import Dict, Any, List, Optional
from contracts.models import Fingerprint, ExpectCondition, WorkflowStep


class PatchVerificationResult:
    def __init__(self, verified: bool, reason: str = "", needs_human_confirm: bool = False):
        self.verified = verified
        self.reason = reason
        self.needs_human_confirm = needs_human_confirm


def verify_candidate_pre_action(
    candidate: Fingerprint,
    step: WorkflowStep,
    tier: int,
    margin: float = 0.0,
) -> PatchVerificationResult:
    """
    Validates candidate element compatibility before attempting action.
    Enforces negative terms filter and detects when the irreversible human gate is triggered.
    """
    # 1. Action compatibility
    if step.action == "fill":
        if candidate.tag not in ["input", "textarea", "select"]:
            return PatchVerificationResult(
                verified=False,
                reason=f"Action 'fill' incompatible with tag '{candidate.tag}'",
            )
    elif step.action == "click":
        if candidate.tag not in ["button", "a", "input", "div", "span"]:
            return PatchVerificationResult(
                verified=False,
                reason=f"Action 'click' target tag '{candidate.tag}' not interactive",
            )

    # 2. Negative terms check (e.g. accidental Cancel/Delete click)
    cand_text_lower = (candidate.text + " " + candidate.label_text + " " + candidate.aria_label).lower()
    rec_text_lower = (step.fingerprint.text + " " + step.fingerprint.label_text).lower()
    rec_was_negative = any(neg in rec_text_lower for neg in step.negative_terms)

    if not rec_was_negative:
        for neg in step.negative_terms:
            if neg in cand_text_lower:
                return PatchVerificationResult(
                    verified=False,
                    reason=f"Safety block: Candidate text contains negative term '{neg}'",
                )

    # 3. Irreversible human gate (Section 6.6)
    # If irreversible and (tier == 2, or tier == 1 with margin < 0.20): pause for human
    if step.irreversible:
        if tier == 2 or (tier == 1 and margin < 0.20):
            return PatchVerificationResult(
                verified=True,
                reason=f"Irreversible step requires human approval (Tier {tier}, margin {margin:.2f})",
                needs_human_confirm=True,
            )

    return PatchVerificationResult(verified=True, reason="Pre-action checks passed")


def verify_post_condition(
    expect: Optional[ExpectCondition],
    actual_value: Optional[str] = None,
    current_url: Optional[str] = None,
    page_text: Optional[str] = None,
) -> bool:
    """
    Validates expect condition after action executes (within 3 seconds).
    Expect kinds: value_equals, url_contains, text_visible, element_visible.
    """
    if not expect:
        return True

    if expect.kind == "value_equals":
        if actual_value is None:
            return False
        return actual_value.strip().lower() == expect.arg.strip().lower()

    elif expect.kind == "url_contains":
        if current_url is None:
            return False
        return expect.arg in current_url

    elif expect.kind == "text_visible":
        if page_text is None:
            return False
        return expect.arg.lower() in page_text.lower()

    return True
