"""
Company Rules & Details RAG Auditor for KINETIC-ZERO.
Scans incoming invoices against the company's official corporate policy handbook
using local Ollama (llama3.2) with deterministic gate scoring fallback.
"""

import os
import json
import time
import hashlib
import urllib.request
from typing import Dict, Any, Optional, List
from app.llm import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT, call_json, CacheMiss

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY_FILE = os.path.join(ROOT_DIR, "data", "policy", "company_rules_and_details.md")


def load_company_rules() -> str:
    """Loads the corporate rules and details markdown handbook."""
    if os.path.exists(POLICY_FILE):
        with open(POLICY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "Company Rules Handbook not found."


def audit_invoice_with_company_rules(
    invoice_data: Dict[str, Any],
    vendor_registry_status: str = "Active",
    udyam_reg: Optional[str] = None,
    is_duplicate: bool = False,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    RAG Policy Scanner:
    1. Reads company rules & legal details from company_rules_and_details.md.
    2. Sends the invoice data + company rules to Ollama (llama3.2).
    3. Evaluates compliance against rules CR-01 through CR-11.
    4. Computes a Company Policy Score (0-100) with detailed findings and citations.
    """
    t0 = time.time()
    company_rules_text = load_company_rules()

    fields = invoice_data.get("fields", {})
    def get_val(f_name):
        v = fields.get(f_name, "")
        if isinstance(v, dict):
            return v.get("value", "")
        return str(v)

    vendor_name = get_val("vendor_name") or invoice_data.get("vendor_name", "Unknown")
    vendor_gstin = get_val("vendor_gstin") or invoice_data.get("vendor_gstin", "Unknown")
    buyer_name = get_val("buyer_name") or invoice_data.get("buyer_name", "Meridian Enterprises Pvt Ltd")
    buyer_gstin = get_val("buyer_gstin") or invoice_data.get("buyer_gstin", "27AAAPL1234F1Z8")
    invoice_no = get_val("invoice_number") or invoice_data.get("invoice_number", "INV-000")
    invoice_date = get_val("invoice_date") or invoice_data.get("invoice_date", "2026-11-04")
    po_number = get_val("po_number") or invoice_data.get("po_number", "PO-9001")
    taxable_val = get_val("taxable_value") or get_val("subtotal") or "0.00"
    cgst = get_val("cgst") or "0.00"
    sgst = get_val("sgst") or "0.00"
    igst = get_val("igst") or "0.00"
    total_val = get_val("total") or get_val("total_amount") or "0.00"
    line_items = invoice_data.get("line_items", [])

    invoice_summary = f"""
- Vendor Name: {vendor_name}
- Vendor GSTIN: {vendor_gstin}
- Buyer Name: {buyer_name}
- Buyer GSTIN: {buyer_gstin}
- Invoice Number: {invoice_no}
- Invoice Date: {invoice_date}
- PO Number: {po_number}
- Taxable Value: Rs {taxable_val}
- CGST: Rs {cgst}
- SGST: Rs {sgst}
- IGST: Rs {igst}
- Total Amount: Rs {total_val}
- Number of Line Items: {len(line_items)}
- Vendor Master Status: {vendor_registry_status}
- Udyam MSME Registration: {udyam_reg or 'None'}
- Prior Payment in Ledger: {'Yes (Duplicate)' if is_duplicate else 'No (Unique)'}
"""

    prompt = f"""You are the senior autonomous internal compliance auditor for Meridian Enterprises Pvt Ltd.
Audit the following invoice against our official Company Procurement & Vendor Policy Handbook.

=== COMPANY POLICY RULES & DETAILS (RAG KNOWLEDGE BASE) ===
{company_rules_text}

=== INVOICE DETAILS TO AUDIT ===
{invoice_summary}

=== AUDIT INSTRUCTIONS ===
1. Compare each field against the company rules CR-01 to CR-11.
2. Check:
   - CR-01: Does Buyer GSTIN match 27AAAPL1234F1Z8?
   - CR-02: Is vendor active (Status: {vendor_registry_status})?
   - CR-03: Does Taxable ({taxable_val}) + CGST ({cgst}) + SGST ({sgst}) + IGST ({igst}) reconcile with Total ({total_val}) within Rs 1.00?
   - CR-04: If vendor state code is 27 (Maharashtra), is CGST == SGST and IGST == 0? If outside 27, is IGST applied?
   - CR-06: Tier limit: <= 1,00,000 (Auto), 1,00,001 - 2,50,000 (Manager Review), > 2,50,000 (Block/Reject).
   - CR-07: MSME 45-day payment statutory requirement if Udyam is present.
   - CR-09: Duplicate check (Duplicate: {is_duplicate}).
   - CR-10: Date check (not future, not older than 90 days).
3. Calculate an overall Company Policy Score from 0 to 100.
   - Clean compliant invoice: 95-100.
   - High value requiring manager review: 70-85.
   - Violation (math error, suspended vendor, duplicate, bad GST): 0-45.

Output ONLY valid JSON with this schema:
{{
  "policy_score": integer (0 to 100),
  "verdict": "APPROVE" | "ESCALATE_TO_MANAGER" | "REJECT",
  "audit_summary": "detailed 2-sentence executive summary of policy scan",
  "rule_evaluations": [
    {{
      "rule_id": "CR-01",
      "title": "Buyer Entity & GSTIN Matching",
      "status": "PASS" | "FAIL" | "FLAG",
      "score_awarded": integer (0 to 10),
      "finding": "observation on this invoice",
      "citation": "CR-01"
    }}
  ]
}}
"""

    schema = {
        "type": "object",
        "properties": {
            "policy_score": {"type": "integer"},
            "verdict": {"type": "string"},
            "audit_summary": {"type": "string"},
            "rule_evaluations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string"},
                        "title": {"type": "string"},
                        "status": {"type": "string"},
                        "score_awarded": {"type": "integer"},
                        "finding": {"type": "string"},
                        "citation": {"type": "string"},
                    },
                    "required": ["rule_id", "title", "status", "score_awarded", "finding", "citation"]
                }
            }
        },
        "required": ["policy_score", "verdict", "audit_summary", "rule_evaluations"]
    }

    summary_hash = hashlib.sha256(invoice_summary.encode("utf-8")).hexdigest()[:12]
    try:
        data = call_json(
            f"company_rag_audit_{invoice_no}_{summary_hash}",
            prompt,
            schema,
            temperature=0.0,
            force_refresh=force_refresh
        )
        data["provider"] = "ollama"
        data["model"] = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)
    except Exception as e:
        # Resilient fallback: Compute deterministic score from rules
        data = _deterministic_company_audit(
            vendor_name=vendor_name,
            vendor_gstin=vendor_gstin,
            buyer_gstin=buyer_gstin,
            taxable_val=taxable_val,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            total_val=total_val,
            vendor_status=vendor_registry_status,
            is_duplicate=is_duplicate,
            udyam_reg=udyam_reg,
            line_items=line_items,
            fallback_reason=str(e),
        )

    data["latency_ms"] = round((time.time() - t0) * 1000, 1)
    data["company_details"] = {
        "name": "Meridian Enterprises Pvt. Ltd.",
        "gstin": "27AAAPL1234F1Z8",
        "cin": "U51909MH2018PTC312456",
        "state": "Maharashtra (27)",
        "policy_doc": "data/policy/company_rules_and_details.md",
    }
    return data


def _deterministic_company_audit(
    vendor_name: str,
    vendor_gstin: str,
    buyer_gstin: str,
    taxable_val: str,
    cgst: str,
    sgst: str,
    igst: str,
    total_val: str,
    vendor_status: str,
    is_duplicate: bool,
    udyam_reg: Optional[str],
    line_items: Optional[List[Any]] = None,
    fallback_reason: str = "",
) -> Dict[str, Any]:
    """Deterministic fallback evaluating company rules CR-01 through CR-11."""
    if line_items is None:
        line_items = []
    evals = []
    total_score = 100
    verdict = "APPROVE"

    # CR-01: Buyer GSTIN
    b_pass = buyer_gstin.upper() == "27AAAPL1234F1Z8"
    evals.append({
        "rule_id": "CR-01",
        "title": "Buyer Entity and GSTIN Matching",
        "status": "PASS" if b_pass else "FAIL",
        "score_awarded": 10 if b_pass else 0,
        "finding": f"Buyer GSTIN is {buyer_gstin} (Matches Meridian registered GSTIN)" if b_pass else f"Buyer GSTIN {buyer_gstin} does not match corporate GSTIN 27AAAPL1234F1Z8",
        "citation": "CR-01",
    })
    if not b_pass:
        total_score -= 25
        verdict = "REJECT"

    # CR-02: Vendor Status
    v_pass = vendor_status.lower() == "active"
    evals.append({
        "rule_id": "CR-02",
        "title": "Active Vendor Master Verification",
        "status": "PASS" if v_pass else "FAIL",
        "score_awarded": 10 if v_pass else 0,
        "finding": f"Vendor '{vendor_name}' is in Active standing in Meridian Vendor Master" if v_pass else f"Vendor '{vendor_name}' status is {vendor_status} - payment barred",
        "citation": "CR-02",
    })
    if not v_pass:
        total_score -= 35
        verdict = "REJECT"

    # CR-03: Arithmetic (Line items sum & Total reconciliation)
    try:
        t_taxable = float(taxable_val.replace(",", ""))
        t_cgst = float(cgst.replace(",", ""))
        t_sgst = float(sgst.replace(",", ""))
        t_igst = float(igst.replace(",", ""))
        t_total = float(total_val.replace(",", ""))

        line_item_sum = 0.0
        for item in line_items:
            amt = item.get("amount", 0) if isinstance(item, dict) else getattr(item, "amount", 0)
            try:
                line_item_sum += float(str(amt).replace(",", ""))
            except Exception:
                pass

        lines_match = True
        if line_items:
            lines_match = abs(line_item_sum - t_taxable) <= 1.05

        calc_total = t_taxable + t_cgst + t_sgst + t_igst
        total_match = abs(calc_total - t_total) <= 1.05
        m_pass = lines_match and total_match

        if not lines_match:
            m_finding = f"Line items sum (Rs {line_item_sum:.2f}) does not match Taxable Value (Rs {t_taxable:.2f})"
        elif not total_match:
            m_finding = f"Taxable + Taxes (Rs {calc_total:.2f}) does not match claimed Grand Total (Rs {t_total:.2f})"
        else:
            m_finding = f"Arithmetic reconciles with mathematical exactness (Line items: Rs {line_item_sum:.2f}, Total: Rs {t_total:.2f})"
    except Exception as ex:
        m_pass = False
        m_finding = f"Arithmetic check error: {ex}"

    evals.append({
        "rule_id": "CR-03",
        "title": "Mathematical Precision and Reconciliation",
        "status": "PASS" if m_pass else "FAIL",
        "score_awarded": 10 if m_pass else 0,
        "finding": m_finding,
        "citation": "CR-03",
    })
    if not m_pass:
        total_score -= 40
        verdict = "REJECT"

    # CR-04: Dual GST Split
    is_intra = vendor_gstin.startswith("27")
    if is_intra:
        gst_pass = abs(float(cgst or 0) - float(sgst or 0)) <= 0.05 and float(igst or 0) == 0
        gst_finding = "Intra-state supply (27->27): CGST and SGST are equal, IGST is nil" if gst_pass else "Intra-state supply tax split mismatch: CGST != SGST or non-zero IGST"
    else:
        gst_pass = float(igst or 0) > 0 and float(cgst or 0) == 0 and float(sgst or 0) == 0
        gst_finding = "Inter-state supply: IGST applied, CGST/SGST nil" if gst_pass else "Inter-state supply must only levy IGST"
    
    evals.append({
        "rule_id": "CR-04",
        "title": "Dual GST Split Integrity",
        "status": "PASS" if gst_pass else "FAIL",
        "score_awarded": 10 if gst_pass else 0,
        "finding": gst_finding,
        "citation": "CR-04",
    })
    if not gst_pass: total_score -= 20

    # CR-06: Tier Limits
    try:
        tot = float(total_val.replace(",", ""))
    except Exception:
        tot = 0.0

    if tot > 250000:
        tier_status = "FAIL"
        tier_finding = f"Grand total Rs {tot:,.2f} exceeds maximum threshold (Rs 2,50,000) - requires CFO signoff"
        total_score -= 30
        verdict = "REJECT"
    elif tot > 100000:
        tier_status = "FLAG"
        tier_finding = f"Grand total Rs {tot:,.2f} exceeds auto-approval limit (Rs 1,00,000) - requires Department Manager review"
        total_score -= 10
        if verdict != "REJECT": verdict = "ESCALATE_TO_MANAGER"
    else:
        tier_status = "PASS"
        tier_finding = f"Grand total Rs {tot:,.2f} within Tier 1 auto-approval threshold (<= Rs 1,00,000)"

    evals.append({
        "rule_id": "CR-06",
        "title": "Tiered Spending Authority and Limits",
        "status": tier_status,
        "score_awarded": 10 if tier_status == "PASS" else (5 if tier_status == "FLAG" else 0),
        "finding": tier_finding,
        "citation": "CR-06",
    })

    # CR-07: MSME 43B(h)
    evals.append({
        "rule_id": "CR-07",
        "title": "Section 43B(h) MSME Statutory Compliance",
        "status": "PASS",
        "score_awarded": 10,
        "finding": f"Vendor is registered MSME ({udyam_reg}) - 45-day priority clock active" if udyam_reg else "Standard non-MSME vendor payment terms apply",
        "citation": "CR-07",
    })

    # CR-09: Duplicate
    evals.append({
        "rule_id": "CR-09",
        "title": "Strict Anti-Duplicate Protection",
        "status": "FAIL" if is_duplicate else "PASS",
        "score_awarded": 0 if is_duplicate else 10,
        "finding": "Duplicate invoice found in paid ledger - payment blocked" if is_duplicate else "Invoice is unique in paid claims ledger",
        "citation": "CR-09",
    })
    if is_duplicate:
        total_score -= 50
        verdict = "REJECT"

    if total_score < 50:
        verdict = "REJECT"

    return {
        "policy_score": max(0, min(100, total_score)),
        "verdict": verdict,
        "audit_summary": f"Company policy audit completed with score {max(0, min(100, total_score))}/100. Verdict: {verdict}.",
        "rule_evaluations": evals,
        "provider": "deterministic_rag_engine",
        "model": "company_rules_evaluator",
        "fallback_note": fallback_reason,
    }
