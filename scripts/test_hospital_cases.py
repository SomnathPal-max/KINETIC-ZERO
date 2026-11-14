import json
from app.guard.hospital_guard import verify_hospital_preauth
from pypdf import PdfReader

with open("packs/hospital/fixtures/cases.json", "r") as f:
    cases = json.load(f)

print(f"{'Case ID':25} | {'Expected':15} | {'Verdict':8} | {'Failed Gates'}")
print("-" * 75)
for c in cases:
    pdf_path = f"packs/hospital/fixtures/{c['id']}.pdf"
    reader = PdfReader(pdf_path)
    text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
    extraction = {
        "doc_id": c["id"],
        "source_text": text,
        "fields": {k: {"value": v} for k, v in c["fields"].items()},
    }
    rep = verify_hospital_preauth(extraction)
    print(f"{c['id']:25} | {c['fault']:15} | {rep.verdict:8} | {rep.failed_gates}")
