"""
Synthetic Invoice Generator for KINETIC-ZERO.
Follows SPEC.txt Appendix C and Section 6.8.
Generates 60 synthetic invoice PDFs with reportlab (containing text layer)
plus ground truth in data/fixtures/ground_truth.json.
Includes fixed demo set: demo_clean, demo_manager, demo_suspended, demo_overlimit.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from decimal import Decimal
from datetime import date, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.guard.gstin import make_valid_gstin

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fixtures", "invoices")
GROUND_TRUTH_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fixtures", "ground_truth.json")


def create_invoice_pdf(filepath: str, data: dict):
    """Draws a clean, professional invoice with ReportLab so a PDF text layer exists."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "TAX INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, f"Vendor: {data['vendor_name']}")
    c.drawString(50, height - 85, f"Vendor GSTIN: {data['vendor_gstin']}")
    c.drawString(50, height - 100, f"Buyer: {data['buyer_name']}")
    c.drawString(50, height - 115, f"Buyer GSTIN: {data['buyer_gstin']}")

    c.drawString(350, height - 70, f"Invoice No: {data['invoice_no']}")
    c.drawString(350, height - 85, f"Invoice Date: {data['invoice_date']}")
    c.drawString(350, height - 100, f"PO Number: {data['po_number']}")

    # Line item table header
    y = height - 150
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Description")
    c.drawString(250, y, "Qty")
    c.drawString(320, y, "Rate (Rs)")
    c.drawString(420, y, "Amount (Rs)")
    c.line(50, y - 5, 500, y - 5)

    y -= 25
    c.setFont("Helvetica", 10)
    for item in data.get("line_items", []):
        c.drawString(50, y, item["desc"])
        c.drawString(250, y, str(item["qty"]))
        c.drawString(320, y, f"{item['rate']}")
        c.drawString(420, y, f"{item['amount']}")
        y -= 20

    c.line(50, y - 5, 500, y - 5)
    y -= 25

    # Totals
    c.drawString(300, y, "Taxable Value:")
    c.drawString(420, y, f"Rs {data['taxable_value']}")
    y -= 18

    c.drawString(300, y, f"CGST: Rs {data['cgst']}")
    y -= 18
    c.drawString(300, y, f"SGST: Rs {data['sgst']}")
    y -= 18
    c.drawString(300, y, f"IGST: Rs {data['igst']}")
    y -= 20

    c.setFont("Helvetica-Bold", 11)
    c.drawString(300, y, "Grand Total:")
    c.drawString(420, y, f"Rs {data['total']}")

    c.save()


def generate_all_fixtures():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = date(2026, 11, 14)
    buyer_gstin = "27AAAPL1234F1Z8"
    buyer_name = "Meridian Traders Pvt Ltd"

    # Known valid vendor GSTINs
    active_intra = "27AAPFU0939F1ZV"  # Maharashtra (active)
    active_inter = "29PQRST3456E1ZN"  # Karnataka (active)
    suspended_vendor = "27XYZAB5678C1Z6"  # Maharashtra (suspended)
    cancelled_vendor = "29ABCDE1122G1ZZ"  # Karnataka (cancelled)

    invoices = []

    # --- 1. Fixed Demo Set ---
    demo_set = [
        {
            "doc_id": "demo_clean",
            "fault": None,
            "expected_verdict": "PROCEED",
            "vendor_name": "Apex Industrial Supplies",
            "vendor_gstin": active_intra,
            "buyer_name": buyer_name,
            "buyer_gstin": buyer_gstin,
            "invoice_no": "INV-DEMO-01",
            "invoice_date": (today - timedelta(days=10)).isoformat(),
            "po_number": "PO-9001",
            "taxable_value": "71610.17",
            "cgst": "6444.91",
            "sgst": "6444.92",
            "igst": "0.00",
            "total": "84500.00",
            "line_items": [{"desc": "Precision Components", "qty": "1", "rate": "71610.17", "amount": "71610.17"}],
        },
        {
            "doc_id": "demo_manager",
            "fault": "manager_limit",
            "expected_verdict": "ESCALATE",
            "vendor_name": "Apex Industrial Supplies",
            "vendor_gstin": active_intra,
            "buyer_name": buyer_name,
            "buyer_gstin": buyer_gstin,
            "invoice_no": "INV-DEMO-02",
            "invoice_date": (today - timedelta(days=15)).isoformat(),
            "po_number": "PO-9002",
            "taxable_value": "156779.66",
            "cgst": "14110.17",
            "sgst": "14110.17",
            "igst": "0.00",
            "total": "185000.00",
            "line_items": [{"desc": "Heavy Machine Assemblies", "qty": "1", "rate": "156779.66", "amount": "156779.66"}],
        },
        {
            "doc_id": "demo_suspended",
            "fault": "suspended_vendor",
            "expected_verdict": "BLOCK",
            "vendor_name": "Western Logistics Corp",
            "vendor_gstin": suspended_vendor,
            "buyer_name": buyer_name,
            "buyer_gstin": buyer_gstin,
            "invoice_no": "INV-DEMO-03",
            "invoice_date": (today - timedelta(days=5)).isoformat(),
            "po_number": "PO-9003",
            "taxable_value": "40000.00",
            "cgst": "3600.00",
            "sgst": "3600.00",
            "igst": "0.00",
            "total": "47200.00",
            "line_items": [{"desc": "Freight Delivery", "qty": "1", "rate": "40000.00", "amount": "40000.00"}],
        },
        {
            "doc_id": "demo_overlimit",
            "fault": "over_manager_limit",
            "expected_verdict": "BLOCK",
            "vendor_name": "Apex Industrial Supplies",
            "vendor_gstin": active_intra,
            "buyer_name": buyer_name,
            "buyer_gstin": buyer_gstin,
            "invoice_no": "INV-DEMO-04",
            "invoice_date": (today - timedelta(days=8)).isoformat(),
            "po_number": "PO-9004",
            "taxable_value": "271186.44",
            "cgst": "24406.78",
            "sgst": "24406.78",
            "igst": "0.00",
            "total": "320000.00",
            "line_items": [{"desc": "Factory Generator Unit", "qty": "1", "rate": "271186.44", "amount": "271186.44"}],
        },
    ]

    for d in demo_set:
        invoices.append(d)

    # --- 2. Clean Invoices (20 total, covering intra & inter-state, amounts 8k to 240k) ---
    clean_amounts = [
        8000, 12000, 18500, 24000, 35000, 48000, 52000, 65000, 72000, 84000,
        92000, 98000, 110000, 125000, 140000, 160000, 175000, 195000, 210000, 240000
    ]
    for i, amt in enumerate(clean_amounts):
        is_inter = (i % 2 == 1)
        v_gstin = active_inter if is_inter else active_intra
        v_name = "Silicon Silicones Bengaluru" if is_inter else "Apex Industrial Supplies"

        # 18% GST calculation
        taxable = Decimal(amt) / Decimal("1.18")
        taxable_round = round(taxable, 2)
        tot_tax = Decimal(amt) - taxable_round

        if is_inter:
            cgst = "0.00"
            sgst = "0.00"
            igst = str(round(tot_tax, 2))
        else:
            half = round(tot_tax / Decimal(2), 2)
            cgst = str(half)
            sgst = str(round(tot_tax - half, 2))
            igst = "0.00"

        doc_id = f"inv_clean_{i+1:02d}"
        inv_data = {
            "doc_id": doc_id,
            "fault": None,
            "expected_verdict": "PROCEED" if amt <= 100000 else "ESCALATE",
            "vendor_name": v_name,
            "vendor_gstin": v_gstin,
            "buyer_name": buyer_name,
            "buyer_gstin": buyer_gstin,
            "invoice_no": f"INV-CLN-{i+1:03d}",
            "invoice_date": (today - timedelta(days=(i * 3 + 2))).isoformat(),
            "po_number": f"PO-CLN-{i+1:03d}",
            "taxable_value": str(taxable_round),
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total": f"{amt:.2f}",
            "line_items": [{"desc": "Standard Supplies", "qty": "1", "rate": str(taxable_round), "amount": str(taxable_round)}],
        }
        invoices.append(inv_data)

    # --- 3. Faulty Invoices (40 total, 9 fault types) ---
    fault_types = [
        ("F1", "bad_checksum"),
        ("F2", "line_sum_mismatch"),
        ("F3", "wrong_tax_split"),
        ("F4", "suspended_vendor"),
        ("F5", "expired_invoice"),
        ("F6", "future_date"),
        ("F7", "duplicate_invoice"),
        ("F8", "over_manager_limit"),
        ("F9", "disallowed_rate"),
    ]

    for idx in range(40):
        code, fault_name = fault_types[idx % len(fault_types)]
        doc_id = f"inv_faulty_{idx+1:02d}"

        # Base clean template
        taxable_dec = Decimal("20000.00")
        cgst_dec = Decimal("1800.00")
        sgst_dec = Decimal("1800.00")
        igst_dec = Decimal("0.00")
        total_dec = Decimal("23600.00")
        inv_date = today - timedelta(days=12)
        v_gstin = active_intra
        v_name = "Apex Industrial Supplies"
        inv_no = f"INV-FLT-{idx+1:03d}"
        lines = [{"desc": "Base Supplies", "qty": "2", "rate": "10000.00", "amount": "20000.00"}]

        # Inject specific fault
        if fault_name == "bad_checksum":
            v_gstin = "27AAPFU0939F1ZX"  # Bad check char
        elif fault_name == "line_sum_mismatch":
            lines = [{"desc": "Item 1", "qty": "1", "rate": "15000.00", "amount": "15000.00"}]  # Sum 15k != taxable 20k
        elif fault_name == "wrong_tax_split":
            # Intra-state charging IGST
            cgst_dec = Decimal("0.00")
            sgst_dec = Decimal("0.00")
            igst_dec = Decimal("3600.00")
        elif fault_name == "suspended_vendor":
            v_gstin = suspended_vendor
            v_name = "Western Logistics Corp"
        elif fault_name == "expired_invoice":
            inv_date = today - timedelta(days=120)  # > 90 days
        elif fault_name == "future_date":
            inv_date = today + timedelta(days=5)  # Future
        elif fault_name == "duplicate_invoice":
            inv_no = "INV-OLD-999"  # Already in ledger
            v_gstin = "27BCDFG1234A1Z0"
        elif fault_name == "over_manager_limit":
            taxable_dec = Decimal("260000.00")
            cgst_dec = Decimal("23400.00")
            sgst_dec = Decimal("23400.00")
            total_dec = Decimal("306800.00")
            lines = [{"desc": "Bulk Equipment", "qty": "1", "rate": "260000.00", "amount": "260000.00"}]
        elif fault_name == "disallowed_rate":
            # 12% rate (2400 / 20000 = 12%)
            cgst_dec = Decimal("1200.00")
            sgst_dec = Decimal("1200.00")
            total_dec = Decimal("22400.00")

        f_data = {
            "doc_id": doc_id,
            "fault": fault_name,
            "expected_verdict": "BLOCK",
            "vendor_name": v_name,
            "vendor_gstin": v_gstin,
            "buyer_name": buyer_name,
            "buyer_gstin": buyer_gstin,
            "invoice_no": inv_no,
            "invoice_date": inv_date.isoformat(),
            "po_number": f"PO-FLT-{idx+1:03d}",
            "taxable_value": str(taxable_dec),
            "cgst": str(cgst_dec),
            "sgst": str(sgst_dec),
            "igst": str(igst_dec),
            "total": str(total_dec),
            "line_items": lines,
        }
        invoices.append(f_data)

    # Write all PDFs
    for inv in invoices:
        pdf_path = os.path.join(OUTPUT_DIR, f"{inv['doc_id']}.pdf")
        create_invoice_pdf(pdf_path, inv)

    # Write ground truth JSON
    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(invoices, f, indent=2)

    print(f"Generated {len(invoices)} invoices in {OUTPUT_DIR}")
    print(f"Ground truth saved to {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    generate_all_fixtures()
