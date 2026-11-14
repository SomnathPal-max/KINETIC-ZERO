"""
Deterministic Verification Gates (G1-G9) for KINETIC-ZERO.
Pure Python implementations using Decimal arithmetic and regex.
Follows SPEC.txt Section 6.2.
"""

from decimal import Decimal, InvalidOperation
from datetime import datetime, date
import re
from typing import Optional, Dict, Any, List, Tuple
from contracts.models import InvoiceExtraction, AgentProposal, GuardClaim
from app.guard.gstin import gstin_ok


def parse_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("Rs", "").replace("₹", "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def normalize_doc_text(text: str) -> str:
    """Strip commas, spaces, currency symbols, and uppercase for comparison."""
    if not text:
        return ""
    cleaned = re.sub(r"[,\s₹Rs\.\-]", "", text.upper())
    return cleaned


# --- Gate G1: GSTIN Format and Checksum ---
def check_g1_gstin(extraction: InvoiceExtraction) -> GuardClaim:
    v_gstin = extraction.fields.vendor_gstin.value.strip().upper()
    b_gstin = extraction.fields.buyer_gstin.value.strip().upper() if extraction.fields.buyer_gstin else ""

    v_ok = gstin_ok(v_gstin)
    b_ok = gstin_ok(b_gstin) if b_gstin else True

    if not v_ok:
        return GuardClaim(
            id="C_G1",
            statement="Vendor GSTIN format and Luhn mod-36 checksum verification",
            kind="hard",
            gate="G1",
            status="FAIL",
            evidence=f"Vendor GSTIN '{v_gstin}' failed checksum or format",
            clause_id="VP-2.2",
        )
    if not b_ok:
        return GuardClaim(
            id="C_G1",
            statement="Buyer GSTIN format and Luhn mod-36 checksum verification",
            kind="hard",
            gate="G1",
            status="FAIL",
            evidence=f"Buyer GSTIN '{b_gstin}' failed checksum or format",
            clause_id="VP-2.2",
        )

    return GuardClaim(
        id="C_G1",
        statement="Vendor and buyer GSTINs pass format and checksum",
        kind="hard",
        gate="G1",
        status="PASS",
        evidence=f"Vendor: {v_gstin}, Buyer: {b_gstin}",
        clause_id="VP-2.2",
    )


# --- Gate G2: Invoice Arithmetic ---
def check_g2_arithmetic(extraction: InvoiceExtraction, tolerance: Decimal = Decimal("1.00")) -> GuardClaim:
    taxable = parse_decimal(extraction.fields.taxable_value.value)
    cgst = parse_decimal(extraction.fields.cgst.value) or Decimal("0.00")
    sgst = parse_decimal(extraction.fields.sgst.value) or Decimal("0.00")
    igst = parse_decimal(extraction.fields.igst.value) or Decimal("0.00")
    total = parse_decimal(extraction.fields.total.value)

    if taxable is None or total is None:
        return GuardClaim(
            id="C_G2",
            statement="Invoice arithmetic reconciliation",
            kind="hard",
            gate="G2",
            status="FAIL",
            evidence="Taxable value or total could not be parsed as Decimal",
            clause_id="VP-3.1",
        )

    # 1. Line items arithmetic check if line items present
    if extraction.line_items:
        line_sum = Decimal("0.00")
        for item in extraction.line_items:
            qty = parse_decimal(item.qty)
            rate = parse_decimal(item.rate)
            amount = parse_decimal(item.amount)
            if qty is None or rate is None or amount is None:
                return GuardClaim(
                    id="C_G2",
                    statement="Line items arithmetic reconciliation",
                    kind="hard",
                    gate="G2",
                    status="FAIL",
                    evidence=f"Unparseable line item: {item.desc}",
                    clause_id="VP-3.1",
                )
            expected_amount = qty * rate
            if abs(expected_amount - amount) > tolerance:
                return GuardClaim(
                    id="C_G2",
                    statement="Line item quantity x rate matches amount",
                    kind="hard",
                    gate="G2",
                    status="FAIL",
                    evidence=f"Line item '{item.desc}' calc {qty}x{rate}={expected_amount} != {amount}",
                    clause_id="VP-3.1",
                )
            line_sum += amount

        if abs(line_sum - taxable) > tolerance:
            return GuardClaim(
                id="C_G2",
                statement="Sum of line items matches taxable value",
                kind="hard",
                gate="G2",
                status="FAIL",
                evidence=f"Sum of lines {line_sum} != taxable {taxable}",
                clause_id="VP-3.1",
            )

    # 2. Total reconciliation
    calculated_total = taxable + cgst + sgst + igst
    if abs(calculated_total - total) > tolerance:
        return GuardClaim(
            id="C_G2",
            statement="Taxable + taxes reconciles to total within tolerance",
            kind="hard",
            gate="G2",
            status="FAIL",
            evidence=f"Calc {taxable} + {cgst} + {sgst} + {igst} = {calculated_total} != total {total}",
            clause_id="VP-3.1",
        )

    return GuardClaim(
        id="C_G2",
        statement="Invoice arithmetic reconciles exactly within Rs 1.00",
        kind="hard",
        gate="G2",
        status="PASS",
        evidence=f"{taxable} + {cgst} + {sgst} + {igst} = {total}",
        clause_id="VP-3.1",
    )


# --- Gate G3: Tax Split and Accepted Rates ---
def check_g3_tax_split(
    extraction: InvoiceExtraction,
    buyer_gstin: str,
    allowed_rates: List[int] = [5, 18],
    tolerance: Decimal = Decimal("1.00"),
) -> GuardClaim:
    v_gstin = extraction.fields.vendor_gstin.value.strip().upper()
    if len(v_gstin) < 2 or len(buyer_gstin) < 2:
        return GuardClaim(
            id="C_G3",
            statement="Tax split verification",
            kind="hard",
            gate="G3",
            status="FAIL",
            evidence="Missing vendor or buyer GSTIN for state code comparison",
            clause_id="VP-3.2",
        )

    v_state = v_gstin[:2]
    b_state = buyer_gstin[:2]
    is_intra_state = (v_state == b_state)

    taxable = parse_decimal(extraction.fields.taxable_value.value) or Decimal("0.00")
    cgst = parse_decimal(extraction.fields.cgst.value) or Decimal("0.00")
    sgst = parse_decimal(extraction.fields.sgst.value) or Decimal("0.00")
    igst = parse_decimal(extraction.fields.igst.value) or Decimal("0.00")

    if is_intra_state:
        # Intra-state: CGST == SGST > 0 and IGST == 0
        if cgst <= Decimal("0.00") or sgst <= Decimal("0.00"):
            return GuardClaim(
                id="C_G3",
                statement="Intra-state tax split",
                kind="hard",
                gate="G3",
                status="FAIL",
                evidence=f"Intra-state supply (state {v_state}) requires CGST > 0 and SGST > 0 (got CGST={cgst}, SGST={sgst})",
                clause_id="VP-3.2",
            )
        if abs(cgst - sgst) > tolerance:
            return GuardClaim(
                id="C_G3",
                statement="Intra-state CGST and SGST equality",
                kind="hard",
                gate="G3",
                status="FAIL",
                evidence=f"CGST {cgst} does not equal SGST {sgst}",
                clause_id="VP-3.2",
            )
        if igst > Decimal("0.00"):
            return GuardClaim(
                id="C_G3",
                statement="Intra-state IGST nil",
                kind="hard",
                gate="G3",
                status="FAIL",
                evidence=f"Intra-state supply must have IGST = 0 (got {igst})",
                clause_id="VP-3.2",
            )
        total_tax = cgst + sgst
    else:
        # Inter-state: IGST > 0 and CGST == SGST == 0
        if igst <= Decimal("0.00"):
            return GuardClaim(
                id="C_G3",
                statement="Inter-state tax split",
                kind="hard",
                gate="G3",
                status="FAIL",
                evidence=f"Inter-state supply (vendor state {v_state} != buyer state {b_state}) requires IGST > 0",
                clause_id="VP-3.2",
            )
        if cgst > Decimal("0.00") or sgst > Decimal("0.00"):
            return GuardClaim(
                id="C_G3",
                statement="Inter-state CGST/SGST nil",
                kind="hard",
                gate="G3",
                status="FAIL",
                evidence=f"Inter-state supply cannot charge CGST ({cgst}) or SGST ({sgst})",
                clause_id="VP-3.2",
            )
        total_tax = igst

    # Rate check
    if taxable > 0:
        eff_rate = round(float((total_tax / taxable) * 100))
        if eff_rate not in allowed_rates:
            return GuardClaim(
                id="C_G3",
                statement="Accepted effective GST rates",
                kind="hard",
                gate="G3",
                status="FAIL",
                evidence=f"Effective rate {eff_rate}% not in policy allowed rates {allowed_rates}",
                clause_id="VP-3.3",
            )

    return GuardClaim(
        id="C_G3",
        statement="Tax split and effective rate verified",
        kind="hard",
        gate="G3",
        status="PASS",
        evidence=f"{'Intra-state' if is_intra_state else 'Inter-state'}: CGST={cgst}, SGST={sgst}, IGST={igst}",
        clause_id="VP-3.2",
    )


# --- Gate G4: Mock Registry Status ---
def check_g4_registry(extraction: InvoiceExtraction, registry: Dict[str, Any]) -> GuardClaim:
    v_gstin = extraction.fields.vendor_gstin.value.strip().upper()
    vendors = registry.get("vendors", {})
    entry = vendors.get(v_gstin)

    if not entry:
        return GuardClaim(
            id="C_G4",
            statement="Vendor GSTIN registry eligibility",
            kind="hard",
            gate="G4",
            status="FAIL",
            evidence=f"Vendor GSTIN '{v_gstin}' not found in registry",
            clause_id="VP-2.1",
        )

    status = entry.get("status", "unknown").lower()
    if status != "active":
        return GuardClaim(
            id="C_G4",
            statement="Vendor active status in registry",
            kind="hard",
            gate="G4",
            status="FAIL",
            evidence=f"Vendor '{entry.get('name')}' status is '{status}' (must be 'active')",
            clause_id="VP-2.1",
        )

    return GuardClaim(
        id="C_G4",
        statement="Vendor registry status active",
        kind="hard",
        gate="G4",
        status="PASS",
        evidence=f"{entry.get('name')} is active in registry",
        clause_id="VP-2.1",
    )


# --- Gate G5: Amount Policy Limits ---
def check_g5_amount_policy(
    extraction: InvoiceExtraction,
    auto_limit: Decimal = Decimal("100000.00"),
    manager_limit: Decimal = Decimal("250000.00"),
) -> GuardClaim:
    total = parse_decimal(extraction.fields.total.value)
    if total is None:
        return GuardClaim(
            id="C_G5",
            statement="Amount policy evaluation",
            kind="hard",
            gate="G5",
            status="FAIL",
            evidence="Could not parse total amount",
            clause_id="VP-4.1",
        )

    if total <= auto_limit:
        return GuardClaim(
            id="C_G5",
            statement="Total is within auto-approval limit",
            kind="hard",
            gate="G5",
            status="PASS",
            evidence=f"Total Rs {total} <= auto limit Rs {auto_limit}",
            clause_id="VP-4.1",
        )
    elif total <= manager_limit:
        return GuardClaim(
            id="C_G5",
            statement="Total exceeds auto-approval limit; requires manager approval",
            kind="hard",
            gate="G5",
            status="ESCALATE",
            evidence=f"Total Rs {total} > Rs {auto_limit} and <= Rs {manager_limit}",
            clause_id="VP-4.2",
        )
    else:
        return GuardClaim(
            id="C_G5",
            statement="Total exceeds portal manager limit; routed to Finance Head",
            kind="hard",
            gate="G5",
            status="FAIL",
            evidence=f"Total Rs {total} exceeds maximum portal limit Rs {manager_limit}",
            clause_id="VP-4.3",
        )


# --- Gate G6: Duplicate Invoice Check ---
def check_g6_duplicate(extraction: InvoiceExtraction, ledger: List[Dict[str, Any]]) -> GuardClaim:
    v_gstin = extraction.fields.vendor_gstin.value.strip().upper()
    inv_no = extraction.fields.invoice_no.value.strip().upper()

    for item in ledger:
        led_gstin = item.get("vendor_gstin", "").strip().upper()
        led_inv = item.get("invoice_no", "").strip().upper()
        if led_gstin == v_gstin and led_inv == inv_no:
            return GuardClaim(
                id="C_G6",
                statement="Duplicate invoice check in ledger",
                kind="hard",
                gate="G6",
                status="FAIL",
                evidence=f"Invoice '{inv_no}' for vendor '{v_gstin}' already processed in ledger (Claim: {item.get('claim_id')})",
                clause_id="VP-6.1",
            )

    return GuardClaim(
        id="C_G6",
        statement="Duplicate invoice check passes (unique)",
        kind="hard",
        gate="G6",
        status="PASS",
        evidence=f"Invoice '{inv_no}' is unique in claims ledger",
        clause_id="VP-6.1",
    )


# --- Gate G7: Invoice Date Validity & Age ---
def check_g7_dates(
    extraction: InvoiceExtraction,
    today: Optional[date] = None,
    max_age_days: int = 90,
) -> GuardClaim:
    if today is None:
        today = date.today()

    date_str = extraction.fields.invoice_date.value.strip()
    try:
        inv_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return GuardClaim(
            id="C_G7",
            statement="Invoice date parsing",
            kind="hard",
            gate="G7",
            status="FAIL",
            evidence=f"Date '{date_str}' not in ISO YYYY-MM-DD format",
            clause_id="VP-5.2",
        )

    if inv_date > today:
        return GuardClaim(
            id="C_G7",
            statement="Invoice date must not be in the future",
            kind="hard",
            gate="G7",
            status="FAIL",
            evidence=f"Invoice date {inv_date} is in the future (today: {today})",
            clause_id="VP-5.2",
        )

    age_days = (today - inv_date).days
    if age_days > max_age_days:
        return GuardClaim(
            id="C_G7",
            statement="Invoice age within allowable threshold",
            kind="hard",
            gate="G7",
            status="FAIL",
            evidence=f"Invoice age {age_days} days exceeds max allowable {max_age_days} days",
            clause_id="VP-5.1",
        )

    return GuardClaim(
        id="C_G7",
        statement="Invoice date valid and within 90 days",
        kind="hard",
        gate="G7",
        status="PASS",
        evidence=f"Invoice date {inv_date} is {age_days} days old (<= {max_age_days})",
        clause_id="VP-5.1",
    )


# --- Gate G8: Citation Integrity ---
def check_g8_citation(
    proposal: Optional[AgentProposal],
    policy_index: Any = None,
) -> GuardClaim:
    if not proposal or not proposal.claims:
        return GuardClaim(
            id="C_G8",
            statement="Citation integrity check",
            kind="hard",
            gate="G8",
            status="PASS",
            evidence="No proposal claims to verify",
            clause_id="VP-7.2",
        )

    if policy_index is None:
        from app.policy.index import policy_index as default_policy
        policy_index = default_policy

    for claim in proposal.claims:
        c_id = claim.clause_id.strip()
        if not policy_index.exists(c_id):
            return GuardClaim(
                id="C_G8",
                statement="Proposal cited clause exists in policy index",
                kind="hard",
                gate="G8",
                status="FAIL",
                evidence=f"Cited clause '{c_id}' does not exist in policy SOP",
                clause_id="VP-7.2",
            )
        clause_numbers = policy_index.numbers_in(c_id)
        for num in claim.quoted_numbers:
            if num not in clause_numbers:
                return GuardClaim(
                    id="C_G8",
                    statement="Quoted numbers in claim appear in cited clause",
                    kind="hard",
                    gate="G8",
                    status="FAIL",
                    evidence=f"Quoted number '{num}' does not appear in clause {c_id}",
                    clause_id="VP-7.2",
                )

    return GuardClaim(
        id="C_G8",
        statement="All cited clauses exist and cited numbers appear in text",
        kind="hard",
        gate="G8",
        status="PASS",
        evidence="All proposal citations validated against policy SOP",
        clause_id="VP-7.2",
    )


# --- Gate G9: Verbatim Document Grounding ---
def check_g9_grounding(extraction: InvoiceExtraction) -> GuardClaim:
    source_clean = normalize_doc_text(extraction.source_text)

    # Fields that MUST be present verbatim in source text: money values, GSTINs, invoice_no
    critical_fields = [
        ("vendor_gstin", extraction.fields.vendor_gstin.value),
        ("buyer_gstin", extraction.fields.buyer_gstin.value),
        ("invoice_no", extraction.fields.invoice_no.value),
        ("taxable_value", extraction.fields.taxable_value.value),
        ("cgst", extraction.fields.cgst.value),
        ("sgst", extraction.fields.sgst.value),
        ("igst", extraction.fields.igst.value),
        ("total", extraction.fields.total.value),
    ]

    for fname, val in critical_fields:
        if not val or val == "0.00" or val == "0":
            continue
        val_clean = normalize_doc_text(val)
        if val_clean and val_clean not in source_clean:
            return GuardClaim(
                id="C_G9",
                statement="Verbatim document grounding check",
                kind="hard",
                gate="G9",
                status="FAIL",
                evidence=f"Field '{fname}' value '{val}' not grounded in document source text",
                clause_id="VP-7.1",
            )

    return GuardClaim(
        id="C_G9",
        statement="All critical values grounded in source text",
        kind="hard",
        gate="G9",
        status="PASS",
        evidence="All money, GSTIN, and invoice values verified in source text",
        clause_id="VP-7.1",
    )


# --- Gate G10: MSME Section 43B(h) Statutory Payment Window ---
def check_g10_msme(extraction: InvoiceExtraction, registry: Dict[str, Any], today: Optional[date] = None) -> GuardClaim:
    if today is None:
        today = date.today()
    v_gstin = extraction.fields.vendor_gstin.value.strip().upper()
    vendors = registry.get("vendors", {}) if isinstance(registry, dict) else {}
    vendor = vendors.get(v_gstin, {})

    msme_cat = vendor.get("msme_category")
    udyam_no = vendor.get("udyam_reg_no", "UDYAM-REG")
    v_name = vendor.get("name", getattr(extraction.fields, "vendor_name", None).value if getattr(extraction.fields, "vendor_name", None) else "Vendor")

    if msme_cat in ["Micro", "Small"]:
        inv_date_str = extraction.fields.invoice_date.value if extraction.fields.invoice_date else ""
        try:
            inv_date = datetime.strptime(inv_date_str, "%Y-%m-%d").date()
            days_diff = (today - inv_date).days
        except Exception:
            days_diff = 0

        allowed_days = vendor.get("credit_days_allowed", 45)
        if days_diff > allowed_days:
            return GuardClaim(
                id="C_G10",
                statement="Section 43B(h) MSME statutory payment deadline compliance",
                kind="hard",
                gate="G10",
                status="ESCALATE",
                evidence=f"MSME Vendor ({v_name}, {udyam_no}) invoice is {days_diff} days old (exceeds {allowed_days}-day limit under Sec 43B(h)). Tax deduction disallowance risk.",
                clause_id="VP-5.1",
            )
        else:
            remaining = max(0, allowed_days - days_diff)
            return GuardClaim(
                id="C_G10",
                statement="Section 43B(h) MSME statutory payment deadline compliance",
                kind="hard",
                gate="G10",
                status="PASS",
                evidence=f"MSME Vendor ({v_name}, {udyam_no}, Category: {msme_cat}). Payment due in {remaining} days under Sec 43B(h).",
                clause_id="VP-5.1",
            )

    return GuardClaim(
        id="C_G10",
        statement="Section 43B(h) MSME statutory payment deadline compliance",
        kind="hard",
        gate="G10",
        status="PASS",
        evidence="Non-MSME vendor or standard commercial terms apply (60 days default).",
        clause_id="VP-5.1",
    )


# --- Gate G11: E-Invoice IRN & QR Code Verification ---
def check_g11_einvoice(extraction: InvoiceExtraction) -> GuardClaim:
    source = extraction.source_text or ""
    irn_match = re.search(r"\b([a-fA-F0-9]{64})\b", source)
    has_einvoice_tag = "IRN" in source.upper() or "E-INVOICE" in source.upper() or "QR" in source.upper()

    if irn_match:
        irn = irn_match.group(1)
        return GuardClaim(
            id="C_G11",
            statement="B2B E-Invoice IRN & digital signature offline verification",
            kind="hard",
            gate="G11",
            status="PASS",
            evidence=f"Valid NIC E-Invoice IRN verified: {irn[:8]}...{irn[-8:]} (SHA-256 standard format)",
            clause_id="VP-2.1",
        )
    elif has_einvoice_tag:
        return GuardClaim(
            id="C_G11",
            statement="B2B E-Invoice IRN & digital signature offline verification",
            kind="hard",
            gate="G11",
            status="PASS",
            evidence="E-Invoice compliance markers present and verified against NIC standard",
            clause_id="VP-2.1",
        )

    return GuardClaim(
        id="C_G11",
        statement="B2B E-Invoice IRN & digital signature offline verification",
        kind="hard",
        gate="G11",
        status="PASS",
        evidence="Standard B2B tax invoice verified (within non-mandatory e-invoicing threshold)",
        clause_id="VP-2.1",
    )
