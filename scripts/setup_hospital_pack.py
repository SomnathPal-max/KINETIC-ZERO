"""
Sets up Hospital Pack:
- Workflow JSON
- Fixtures and PDFs (Clean, Lapsed, Uncovered Code, Escalated, Overlimit, Duplicate, Non-network)
"""

import os
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

os.makedirs("packs/hospital/skills", exist_ok=True)
os.makedirs("data/workflows", exist_ok=True)
os.makedirs("packs/hospital/fixtures", exist_ok=True)
os.makedirs("data/fixtures/hospital", exist_ok=True)

# 1. Hospital Workflow
wf_hosp = {
    "workflow_id": "wf_hospital_preauth",
    "name": "Patient Cashless Insurance Pre-Authorization",
    "version": 1,
    "start_url": "/portal_b/preauth",
    "steps": [
        {
            "id": "s1",
            "action": "fill",
            "intent": "Enter Patient Identification Number",
            "value_from": "patient_id",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "patient_id"},
            "alt_locators": [
                {"strategy": "name", "value": "patient_id"},
                {"strategy": "css", "value": "input[name='patient_id']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "patient_id",
                "name": "patient_id",
                "type": "text",
                "label_text": "Patient ID",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s2",
            "action": "fill",
            "intent": "Enter Patient Full Name",
            "value_from": "patient_name",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "patient_name"},
            "alt_locators": [
                {"strategy": "name", "value": "patient_name"},
                {"strategy": "css", "value": "input[name='patient_name']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "patient_name",
                "name": "patient_name",
                "type": "text",
                "label_text": "Patient Name",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s3",
            "action": "fill",
            "intent": "Enter Health Insurance Policy Number",
            "value_from": "policy_number",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "policy_number"},
            "alt_locators": [
                {"strategy": "name", "value": "policy_number"},
                {"strategy": "css", "value": "input[name='policy_number']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "policy_number",
                "name": "policy_number",
                "type": "text",
                "label_text": "Policy Number",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s4",
            "action": "fill",
            "intent": "Enter Insurer / TPA ID",
            "value_from": "insurer_id",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "insurer_id"},
            "alt_locators": [
                {"strategy": "name", "value": "insurer_id"},
                {"strategy": "css", "value": "input[name='insurer_id']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "insurer_id",
                "name": "insurer_id",
                "type": "text",
                "label_text": "Insurer ID",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s5",
            "action": "fill",
            "intent": "Enter ICD-10 Primary Diagnosis Code",
            "value_from": "diagnosis_code",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "diagnosis_code"},
            "alt_locators": [
                {"strategy": "name", "value": "diagnosis_code"},
                {"strategy": "css", "value": "input[name='diagnosis_code']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "diagnosis_code",
                "name": "diagnosis_code",
                "type": "text",
                "label_text": "Diagnosis Code",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s6",
            "action": "fill",
            "intent": "Enter Surgical / Medical Treatment Type",
            "value_from": "treatment_type",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "treatment_type"},
            "alt_locators": [
                {"strategy": "name", "value": "treatment_type"},
                {"strategy": "css", "value": "input[name='treatment_type']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "treatment_type",
                "name": "treatment_type",
                "type": "text",
                "label_text": "Treatment Type",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s7",
            "action": "fill",
            "intent": "Enter Empanelled Hospital Provider ID",
            "value_from": "hospital_id",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "hospital_id"},
            "alt_locators": [
                {"strategy": "name", "value": "hospital_id"},
                {"strategy": "css", "value": "input[name='hospital_id']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "hospital_id",
                "name": "hospital_id",
                "type": "text",
                "label_text": "Hospital ID",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s8",
            "action": "fill",
            "intent": "Enter Proposed Admission Date",
            "value_from": "admission_date",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "admission_date"},
            "alt_locators": [
                {"strategy": "name", "value": "admission_date"},
                {"strategy": "css", "value": "input[name='admission_date']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "admission_date",
                "name": "admission_date",
                "type": "text",
                "label_text": "Admission Date",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s9",
            "action": "fill",
            "intent": "Enter Estimated Procedure / Hospitalization Cost",
            "value_from": "estimated_cost",
            "literal": None,
            "irreversible": False,
            "negative_terms": ["cancel", "clear", "reset"],
            "locator": {"strategy": "id", "value": "estimated_cost"},
            "alt_locators": [
                {"strategy": "name", "value": "estimated_cost"},
                {"strategy": "css", "value": "input[name='estimated_cost']"},
            ],
            "fingerprint": {
                "tag": "input",
                "id": "estimated_cost",
                "name": "estimated_cost",
                "type": "text",
                "label_text": "Estimated Cost",
                "classes": ["form-control"],
            },
        },
        {
            "id": "s10",
            "action": "click",
            "intent": "Submit Pre-Authorization to Insurer Clearinghouse",
            "value_from": None,
            "literal": None,
            "irreversible": True,
            "negative_terms": ["cancel", "abort", "discard", "back"],
            "locator": {"strategy": "id", "value": "submit-preauth-btn"},
            "alt_locators": [
                {"strategy": "role", "value": "button"},
                {"strategy": "css", "value": "button.btn-primary"},
            ],
            "fingerprint": {
                "tag": "button",
                "id": "submit-preauth-btn",
                "text": "Submit Pre-Authorization",
                "classes": ["btn", "btn-primary"],
            },
        },
    ],
}

with open("packs/hospital/skills/wf_hospital_preauth.json", "w") as f:
    json.dump(wf_hosp, f, indent=2)

with open("data/workflows/wf_hospital_preauth.json", "w") as f:
    json.dump(wf_hosp, f, indent=2)


# 2. Helper to generate realistic Patient Intake PDFs
def make_patient_pdf(filename, fields, title="PATIENT PRE-AUTHORIZATION REQUEST FORM"):
    c = canvas.Canvas(filename, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, title)
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "Apollo-Care Healthcare Network | TPA Cashless Desk")
    c.setLineWidth(1)
    c.line(50, 725, 550, 725)

    y = 690
    c.setFont("Helvetica", 11)
    for k, v in fields.items():
        label = k.replace("_", " ").title()
        c.setFont("Helvetica-Bold", 11)
        c.drawString(60, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(240, y, str(v))
        y -= 25

    c.line(50, y - 10, 550, y - 10)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, y - 25, "Certified accurate by Attending Physician and Hospital Administration.")
    c.save()


patient_cases = [
    {
        "id": "preauth_clean",
        "title": "Clean Pre-Authorization (Compliant — Anita Sharma)",
        "fields": {
            "patient_name": "Anita Sharma",
            "patient_id": "PT-10492",
            "policy_number": "POL-88219",
            "insurer_id": "TPA-STAR-01",
            "diagnosis_code": "J18",
            "treatment_type": "Inpatient Antibiotic Therapy & Bronchoscopy",
            "hospital_id": "HSP-001",
            "admission_date": "2026-11-25",
            "estimated_cost": "38500.00",
        },
        "fault": "none",
    },
    {
        "id": "preauth_lapsed_policy",
        "title": "Lapsed Policy Status (Vikram Singh — Gate HP_G1)",
        "fields": {
            "patient_name": "Vikram Singh",
            "patient_id": "PT-33201",
            "policy_number": "POL-99402",
            "insurer_id": "TPA-STAR-01",
            "diagnosis_code": "K35",
            "treatment_type": "Laparoscopic Appendectomy",
            "hospital_id": "HSP-001",
            "admission_date": "2026-11-26",
            "estimated_cost": "45000.00",
        },
        "fault": "lapsed_policy",
    },
    {
        "id": "preauth_uncovered_code",
        "title": "Uncovered Cosmetic Code (Z41 Elective — Gate HP_G2)",
        "fields": {
            "patient_name": "Rajesh Kumar",
            "patient_id": "PT-55102",
            "policy_number": "POL-44109",
            "insurer_id": "TPA-STAR-01",
            "diagnosis_code": "Z41",
            "treatment_type": "Elective Rhinoplasty Reconstruction",
            "hospital_id": "HSP-002",
            "admission_date": "2026-11-28",
            "estimated_cost": "42000.00",
        },
        "fault": "uncovered_code",
    },
    {
        "id": "preauth_manager_review",
        "title": "Medical Director Escalation (> Rs 50,000 — Gate HP_G3)",
        "fields": {
            "patient_name": "Priya Patel",
            "patient_id": "PT-77114",
            "policy_number": "POL-77301",
            "insurer_id": "TPA-STAR-01",
            "diagnosis_code": "M16",
            "treatment_type": "Total Knee Arthroplasty",
            "hospital_id": "HSP-003",
            "admission_date": "2026-11-27",
            "estimated_cost": "85000.00",
        },
        "fault": "high_cost_escalation",
    },
    {
        "id": "preauth_overlimit",
        "title": "Exceeds Policy Ceiling (> Rs 200,000 — Gate HP_G3)",
        "fields": {
            "patient_name": "Anita Sharma",
            "patient_id": "PT-10492",
            "policy_number": "POL-88219",
            "insurer_id": "TPA-STAR-01",
            "diagnosis_code": "I20",
            "treatment_type": "Coronary Bypass Graft Surgery",
            "hospital_id": "HSP-001",
            "admission_date": "2026-12-01",
            "estimated_cost": "240000.00",
        },
        "fault": "over_ceiling_block",
    },
    {
        "id": "preauth_duplicate",
        "title": "Duplicate Admission Request (Already Processed — Gate HP_G5)",
        "fields": {
            "patient_name": "Sunita Mehta",
            "patient_id": "PT-9901",
            "policy_number": "POL-11029",
            "insurer_id": "TPA-STAR-01",
            "diagnosis_code": "E11",
            "treatment_type": "Diabetic Ketoacidosis Stabilization",
            "hospital_id": "HSP-001",
            "admission_date": "2026-11-20",
            "estimated_cost": "32000.00",
        },
        "fault": "duplicate_claim",
    },
    {
        "id": "preauth_nonnetwork",
        "title": "Non-Empanelled Facility (City Community — Gate HP_G4)",
        "fields": {
            "patient_name": "Anita Sharma",
            "patient_id": "PT-10492",
            "policy_number": "POL-88219",
            "insurer_id": "TPA-STAR-01",
            "diagnosis_code": "K35",
            "treatment_type": "Emergency Appendectomy",
            "hospital_id": "HSP-999",
            "admission_date": "2026-11-26",
            "estimated_cost": "41000.00",
        },
        "fault": "non_network_hospital",
    },
]

for case in patient_cases:
    fpath1 = os.path.join("packs/hospital/fixtures", f"{case['id']}.pdf")
    fpath2 = os.path.join("data/fixtures/hospital", f"{case['id']}.pdf")
    make_patient_pdf(fpath1, case["fields"])
    make_patient_pdf(fpath2, case["fields"])

with open("packs/hospital/fixtures/cases.json", "w") as f:
    json.dump(patient_cases, f, indent=2)

print("Hospital pack workflow and PDF fixtures created successfully!")
