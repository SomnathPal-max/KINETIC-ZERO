import sys
sys.path.insert(0, ".")
import json
from app.extractor import extract_invoice
from app.rag.company_auditor import audit_invoice_with_company_rules

print("--- Testing Clean Invoice with Company Rules RAG ---")
ext_clean = extract_invoice("demo_clean", pdf_path="data/fixtures/invoices/demo_clean.pdf")
res_clean = audit_invoice_with_company_rules(ext_clean.model_dump(), vendor_registry_status="Active")
print("Clean Invoice Policy Score:", res_clean.get("policy_score"))
print("Verdict:", res_clean.get("verdict"))
print("Summary:", res_clean.get("audit_summary"))
print("Rules evaluated count:", len(res_clean.get("rule_evaluations", [])))
print("Rule CR-01:", json.dumps(res_clean.get("rule_evaluations", [])[0], indent=2))

print("\n--- Testing Math Error Invoice with Company Rules RAG ---")
ext_err = extract_invoice("demo_math_error", pdf_path="data/fixtures/invoices/demo_math_error.pdf")
res_err = audit_invoice_with_company_rules(ext_err.model_dump(), vendor_registry_status="Active")
print("Math Error Policy Score:", res_err.get("policy_score"))
print("Verdict:", res_err.get("verdict"))
print("Summary:", res_err.get("audit_summary"))
