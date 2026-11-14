"""
Workflow Recorder and Compiler for KINETIC-ZERO (Teach Mode).
Follows SPEC.txt Section 6.5.
Rule 10: Workflow JSON must never contain data-k0 strings.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
from contracts.models import Workflow, WorkflowStep, Locator, Fingerprint, ExpectCondition, InvoiceExtraction
from app.healer.fingerprint import generate_locators, create_fingerprint_from_dict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS_DIR = os.path.join(ROOT_DIR, "data", "workflows")


def normalize_val(val: str) -> str:
    if not val:
        return ""
    return re.sub(r"[,\s₹Rs\.\-]", "", str(val).upper())


def bind_variable(typed_value: str, invoice: Optional[InvoiceExtraction]) -> Optional[str]:
    """
    Checks if typed value matches any field of the loaded invoice after normalisation.
    Returns the field name (e.g. 'vendor_gstin', 'total') if matched, else None.
    """
    if not invoice or not typed_value:
        return None

    typed_norm = normalize_val(typed_value)
    if not typed_norm:
        return None

    fields_dict = invoice.fields.model_dump()
    for field_name, f_data in fields_dict.items():
        inv_val = f_data.get("value", "")
        if inv_val and normalize_val(inv_val) == typed_norm:
            return field_name

    return None


def is_irreversible_action(action: str, text: str) -> bool:
    """Detects irreversible final submission actions."""
    if action != "click":
        return False
    t_lower = text.lower()
    return bool(re.search(r"\b(submit|pay|payment|confirm|send|approve)\b", t_lower))


def compile_recorded_steps(
    raw_events: List[Dict[str, Any]],
    workflow_id: str = "wf_vendor_claim",
    name: str = "Vendor claim entry",
    invoice: Optional[InvoiceExtraction] = None,
) -> Workflow:
    """
    Compiles raw browser recorded events into a validated Workflow model.
    Deduplicates events, binds variables to invoice fields, derives negative terms,
    marks irreversible steps, and derives post-conditions.
    """
    os.makedirs(WORKFLOWS_DIR, exist_ok=True)
    steps: List[WorkflowStep] = []

    for idx, ev in enumerate(raw_events):
        step_id = f"s{idx + 1}"
        action = ev.get("action", "click")
        raw_fp = ev.get("fingerprint", {})
        fp = create_fingerprint_from_dict(raw_fp)

        # Build prioritized locators
        loc_candidates = generate_locators(fp)
        primary_locator = loc_candidates[0] if loc_candidates else Locator(strategy="css", value=fp.tag or "button")
        alt_locators = loc_candidates[1:]

        # Variable binding or literal
        typed_val = ev.get("value", "")
        value_from = None
        literal = None
        if action == "fill":
            bound = bind_variable(typed_val, invoice)
            if bound:
                value_from = bound
            else:
                literal = typed_val

        # Irreversible check (last click with submit/pay keywords)
        text_for_irrev = fp.text or fp.label_text or fp.aria_label
        irreversible = is_irreversible_action(action, text_for_irrev) and (idx == len(raw_events) - 1 or "submit" in text_for_irrev.lower())

        # Expect condition
        expect = None
        if action == "fill":
            expected_arg = typed_val or (invoice.fields.model_dump().get(value_from, {}).get("value") if value_from and invoice else "")
            if expected_arg:
                expect = ExpectCondition(kind="value_equals", arg=expected_arg)
        elif action == "click":
            if "review" in text_for_irrev.lower():
                expect = ExpectCondition(kind="url_contains", arg="/portal/review")
            elif irreversible:
                expect = ExpectCondition(kind="url_contains", arg="/portal/done")

        # Intent
        intent = ev.get("intent") or (f"Enter {value_from}" if value_from else (f"Click {fp.text}" if fp.text else f"Perform {action}"))

        step = WorkflowStep(
            id=step_id,
            action=action,
            intent=intent,
            value_from=value_from,
            literal=literal,
            irreversible=irreversible,
            negative_terms=["cancel", "clear", "back", "reject", "delete"],
            locator=primary_locator,
            alt_locators=alt_locators,
            fingerprint=fp,
            expect=expect,
            screenshot=ev.get("screenshot"),
            narration=ev.get("narration"),
        )
        steps.append(step)

    # Ensure the last step is marked irreversible if it's the final submission click
    if steps and steps[-1].action == "click":
        steps[-1].irreversible = True

    wf = Workflow(
        workflow_id=workflow_id,
        name=name,
        version=1,
        start_url="/portal/claim",
        steps=steps,
    )

    # Verify no data-k0 strings leaked
    wf_json_str = json.dumps(wf.model_dump())
    assert "data-k0" not in wf_json_str, "Workflow must never contain data-k0 strings (Rule 10 violation)"

    save_path = os.path.join(WORKFLOWS_DIR, f"{workflow_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(wf.model_dump(), f, indent=2)

    return wf


def load_workflow(workflow_id: str) -> Optional[Workflow]:
    path = os.path.join(WORKFLOWS_DIR, f"{workflow_id}.json")
    if not os.path.exists(path):
        # Fall back to example workflow if not yet recorded
        example_path = os.path.join(ROOT_DIR, "contracts", "examples", "workflow.json")
        if os.path.exists(example_path):
            with open(example_path, "r", encoding="utf-8") as f:
                return Workflow.model_validate(json.load(f))
        return None
    with open(path, "r", encoding="utf-8") as f:
        return Workflow.model_validate(json.load(f))


def calculate_step_fragility(step: WorkflowStep) -> Dict[str, Any]:
    """
    Step Fragility Forecast (Feature F11).
    Estimates the probability that the baseline locator will break under common DOM mutations.
    """
    loc_val = step.locator.value if step.locator else ""
    fp = step.fingerprint

    score = 0.50
    reasons = []

    if loc_val.startswith("#"):
        score += 0.35
        reasons.append("Relies on raw ID selector (brittle to ID regeneration)")
    elif "nth-child" in loc_val or ">" in loc_val:
        score += 0.25
        reasons.append("Structural CSS path vulnerable to DOM tree reordering")
    
    if fp.label_text or fp.aria_label:
        score -= 0.20
        reasons.append("Has strong semantic label/aria anchor")
    elif not fp.text:
        score += 0.15
        reasons.append("Lacks text content or accessible name")

    if not step.alt_locators or len(step.alt_locators) == 0:
        score += 0.15
        reasons.append("No fallback locators recorded")
    else:
        score -= min(0.20, len(step.alt_locators) * 0.05)

    fragility = max(0.10, min(0.95, round(score, 2)))
    level = "HIGH" if fragility >= 0.70 else ("MED" if fragility >= 0.40 else "LOW")

    return {
        "score": fragility,
        "level": level,
        "reasons": reasons,
    }
