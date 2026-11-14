import sys
sys.path.insert(0, ".")
import os
import json
import time
import urllib.request
from app.extractor import extract_text_from_pdf

fin_text = extract_text_from_pdf("data/fixtures/invoices/demo_clean.pdf")
hosp_text = extract_text_from_pdf("packs/hospital/fixtures/preauth_clean.pdf")

def classify_with_ollama(text):
    prompt = f"""You are an autonomous AI enterprise document classifier.
Analyze the following document text and classify it into exactly one of two categories:
1. "finance" - Accounts payable invoices, vendor bills, commercial tax invoices, B2B procurement receipts.
2. "health" - Hospital patient claims, health insurance pre-authorization requests, medical treatment estimates, diagnostic bills.

Document text excerpt:
\"\"\"
{text[:800]}
\"\"\"

Output ONLY valid JSON matching this schema:
{{
  "category": "finance" or "health",
  "confidence": float between 0.0 and 1.0,
  "reason": "concise explanation of signals detected",
  "detected_entities": ["list", "of", "key", "entities"]
}}
"""
    payload = {
        "model": "llama3.2:latest",
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0}
    }
    t0 = time.time()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        ans = json.loads(res.get("response", "{}"))
        ans["_latency_sec"] = round(time.time() - t0, 2)
        return ans

print("Testing Finance Document Classification with Ollama...")
res_fin = classify_with_ollama(fin_text)
print("Finance Result:", json.dumps(res_fin, indent=2))

print("\nTesting Hospital Document Classification with Ollama...")
res_hosp = classify_with_ollama(hosp_text)
print("Hospital Result:", json.dumps(res_hosp, indent=2))
