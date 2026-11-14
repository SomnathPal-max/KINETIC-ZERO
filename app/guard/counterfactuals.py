"""
Preflight Counterfactual Evaluation (Policy Twin / Shadow Sandbox).
Follows SPEC.txt Section 6.7 and Feature F10 (P1).
Derives 7 perturbations from a PROCEED extraction to verify that all unsafe variants are blocked.
"""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from contracts.models import InvoiceExtraction, FieldExtraction, GuardReport
from app.guard.engine import verify, GuardContext
from app.guard.gstin import make_valid_gstin


def run_preflight_counterfactuals(
    clean_extraction: InvoiceExtraction,
    ctx: GuardContext,
) -> Dict[str, Any]:
    """
    Evaluates 7 counterfactual perturbations against the Guard rule engine:
    1. Vendor suspended
    2. Date in future (tomorrow)
    3. Date expired (120 days old)
    4. Total above manager limit (scaled to Rs 3,20,000)
    5. GSTIN checksum corrupted (last char flipped)
    6. Duplicate invoice in ledger
    7. Tax split flipped (intra-state charging IGST)

    Returns test results for each variant and aggregate catch rate.
    """
    variants: List[Dict[str, Any]] = []
    today = ctx.today or date.today()

    # Variant 1: Vendor suspended in registry
    v1_ext = clean_extraction.model_copy(deep=True)
    v1_ctx = GuardContext(
        registry={
            "buyer": ctx.registry.get("buyer", {}),
            "vendors": {
                v1_ext.fields.vendor_gstin.value: {
                    "name": v1_ext.fields.vendor_name.value,
                    "status": "suspended",
                }
            },
        },
        ledger=ctx.ledger,
        policy=ctx.policy,
        today=today,
    )
    v1_rep = verify(v1_ext, None, v1_ctx)
    variants.append({
        "id": "CF1",
        "name": "Vendor Suspended",
        "description": "Vendor GSTIN status marked 'suspended' in mock registry",
        "expected": "BLOCK",
        "actual": v1_rep.verdict,
        "failed_gates": v1_rep.failed_gates,
        "passed": (v1_rep.verdict == "BLOCK"),
    })

    # Variant 2: Future Date
    v2_ext = clean_extraction.model_copy(deep=True)
    v2_ext.fields.invoice_date = FieldExtraction(
        value=(today + timedelta(days=1)).isoformat(),
        evidence="Future date",
    )
    v2_rep = verify(v2_ext, None, ctx)
    variants.append({
        "id": "CF2",
        "name": "Future Date",
        "description": "Invoice date shifted 1 day into the future",
        "expected": "BLOCK",
        "actual": v2_rep.verdict,
        "failed_gates": v2_rep.failed_gates,
        "passed": (v2_rep.verdict == "BLOCK"),
    })

    # Variant 3: Expired Date (> 90 days)
    v3_ext = clean_extraction.model_copy(deep=True)
    v3_ext.fields.invoice_date = FieldExtraction(
        value=(today - timedelta(days=120)).isoformat(),
        evidence="120 days old",
    )
    v3_rep = verify(v3_ext, None, ctx)
    variants.append({
        "id": "CF3",
        "name": "Invoice Expired",
        "description": "Invoice date 120 days old (> 90-day allowable window)",
        "expected": "BLOCK",
        "actual": v3_rep.verdict,
        "failed_gates": v3_rep.failed_gates,
        "passed": (v3_rep.verdict == "BLOCK"),
    })

    # Variant 4: Total scaled above manager limit (> Rs 2,50,000)
    v4_ext = clean_extraction.model_copy(deep=True)
    v4_ext.fields.total = FieldExtraction(value="320000.00", evidence="Rs 320000.00")
    v4_ext.fields.taxable_value = FieldExtraction(value="271186.44", evidence="Rs 271186.44")
    v4_ext.fields.cgst = FieldExtraction(value="24406.78", evidence="Rs 24406.78")
    v4_ext.fields.sgst = FieldExtraction(value="24406.78", evidence="Rs 24406.78")
    v4_ext.source_text += " 320000.00 271186.44 24406.78"
    v4_rep = verify(v4_ext, None, ctx)
    variants.append({
        "id": "CF4",
        "name": "Above Manager Limit",
        "description": "Total scaled to Rs 3,20,000 (exceeds Rs 2,50,000 limit)",
        "expected": "BLOCK",
        "actual": v4_rep.verdict,
        "failed_gates": v4_rep.failed_gates,
        "passed": (v4_rep.verdict == "BLOCK"),
    })

    # Variant 5: Corrupt GSTIN Checksum
    v5_ext = clean_extraction.model_copy(deep=True)
    old_gstin = v5_ext.fields.vendor_gstin.value
    bad_gstin = old_gstin[:-1] + ("X" if old_gstin[-1] != "X" else "Y")
    v5_ext.fields.vendor_gstin = FieldExtraction(value=bad_gstin, evidence=bad_gstin)
    v5_rep = verify(v5_ext, None, ctx)
    variants.append({
        "id": "CF5",
        "name": "Corrupt GSTIN Checksum",
        "description": f"Last check character flipped to '{bad_gstin[-1]}'",
        "expected": "BLOCK",
        "actual": v5_rep.verdict,
        "failed_gates": v5_rep.failed_gates,
        "passed": (v5_rep.verdict == "BLOCK"),
    })

    # Variant 6: Duplicate Invoice in Ledger
    v6_ext = clean_extraction.model_copy(deep=True)
    dup_ledger = list(ctx.ledger) + [{
        "claim_id": "CLM-DUP-TEST",
        "vendor_gstin": v6_ext.fields.vendor_gstin.value,
        "invoice_no": v6_ext.fields.invoice_no.value,
        "amount": v6_ext.fields.total.value,
    }]
    v6_ctx = GuardContext(registry=ctx.registry, ledger=dup_ledger, policy=ctx.policy, today=today)
    v6_rep = verify(v6_ext, None, v6_ctx)
    variants.append({
        "id": "CF6",
        "name": "Duplicate Invoice",
        "description": "Same (vendor_gstin, invoice_no) already recorded in ledger",
        "expected": "BLOCK",
        "actual": v6_rep.verdict,
        "failed_gates": v6_rep.failed_gates,
        "passed": (v6_rep.verdict == "BLOCK"),
    })

    # Variant 7: Tax Split Flipped (Intra-state charging IGST)
    v7_ext = clean_extraction.model_copy(deep=True)
    # Vendor state 27, buyer 27 -> intra-state, but zero CGST/SGST and full IGST
    tot_tax = (Decimal(v7_ext.fields.cgst.value or "0") + Decimal(v7_ext.fields.sgst.value or "0"))
    v7_ext.fields.cgst = FieldExtraction(value="0.00", evidence="0.00")
    v7_ext.fields.sgst = FieldExtraction(value="0.00", evidence="0.00")
    v7_ext.fields.igst = FieldExtraction(value=str(tot_tax), evidence=str(tot_tax))
    v7_ext.source_text += f" {tot_tax}"
    v7_rep = verify(v7_ext, None, ctx)
    variants.append({
        "id": "CF7",
        "name": "Tax Split Inverted",
        "description": "Intra-state supply charging IGST instead of CGST/SGST",
        "expected": "BLOCK",
        "actual": v7_rep.verdict,
        "failed_gates": v7_rep.failed_gates,
        "passed": (v7_rep.verdict == "BLOCK"),
    })

    passed_count = sum(1 for v in variants if v["passed"])
    return {
        "total_variants": len(variants),
        "blocked_variants": passed_count,
        "banner": f"Preflight: {passed_count}/{len(variants)} unsafe variants blocked",
        "all_blocked": (passed_count == len(variants)),
        "variants": variants,
    }
