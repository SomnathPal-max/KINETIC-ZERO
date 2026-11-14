"""
Autonomous Document Classifier for KINETIC-ZERO.
Powered by local Ollama (llama3.2) with hybrid RAG/heuristic fallback.
Classifies unstructured business/medical documents into either 'finance' or 'health'
and automatically binds them to domain packs, target portals, and workflow skills.
"""

import os
import json
import time
import urllib.request
from typing import Dict, Any, Optional, List
from app.llm import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT, call_json, CacheMiss
from app.extractor import extract_text_from_pdf
from app.rag.engine import route_document


def classify_document_text_with_ollama(text: str) -> Dict[str, Any]:
    """
    Invokes local Ollama model to classify document text into 'finance' or 'health'.
    """
    prompt = f"""You are an autonomous AI enterprise document classifier for KINETIC-ZERO.
Analyze the following document text and classify it into exactly one of two enterprise categories:
1. "finance" - Accounts payable invoices, vendor bills, commercial tax invoices, B2B procurement receipts, GSTIN documents.
2. "health" - Hospital patient admission forms, health insurance pre-authorization requests, medical treatment estimates, diagnostic bills, TPA cashless claims.

Document text excerpt:
\"\"\"
{text[:1200]}
\"\"\"

Output ONLY valid JSON matching this schema:
{{
  "category": "finance" or "health",
  "confidence": float between 0.0 and 1.0,
  "reason": "concise explanation of signals detected",
  "detected_entities": ["list", "of", "key", "entities"]
}}
"""
    host = os.environ.get("OLLAMA_HOST", OLLAMA_HOST)
    model = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)
    timeout = float(os.environ.get("OLLAMA_TIMEOUT", str(OLLAMA_TIMEOUT)))

    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0}
    }

    req = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        ans = json.loads(res.get("response", "{}"))
        cat = ans.get("category", "").lower().strip()
        if "health" in cat or "hospital" in cat or "medical" in cat:
            ans["category"] = "health"
        else:
            ans["category"] = "finance"
        ans["provider"] = "ollama"
        ans["model"] = model
        return ans


def classify_document(
    pdf_path: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    raw_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full pipeline to classify any document into 'health' or 'finance' domain.
    Attempts Ollama inference first; falls back to deterministic hybrid RAG if unavailable.
    """
    t0 = time.time()
    
    # 1. Extract text
    if raw_text:
        text = raw_text
    elif pdf_path and os.path.exists(pdf_path):
        text = extract_text_from_pdf(pdf_path)
    elif pdf_bytes:
        import io
        text = extract_text_from_pdf(io.BytesIO(pdf_bytes))
    else:
        text = ""

    if not text.strip():
        # Empty text fallback
        return {
            "category": "finance",
            "pack_id": "finance",
            "pack_name": "Finance / Accounts Payable",
            "matched_skill": "wf_vendor_claim",
            "target_portal": "/portal/claim",
            "confidence": 0.50,
            "reason": "Empty document text; defaulting to finance pack",
            "detected_entities": [],
            "provider": "default_fallback",
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "text_snippet": "",
        }

    # 2. Attempt Ollama classification
    ollama_error = None
    try:
        ans = classify_document_text_with_ollama(text)
        category = ans.get("category", "finance")
        confidence = float(ans.get("confidence", 0.95))
        reason = ans.get("reason", "Classified by local Ollama model")
        entities = ans.get("detected_entities", [])
        provider = ans.get("provider", "ollama")
        model = ans.get("model", OLLAMA_MODEL)
    except Exception as e:
        ollama_error = str(e)
        # Fallback to hybrid RAG router in app.rag.engine
        rag_res = route_document(text)
        matched_pack = rag_res.get("matched_pack_id", "finance")
        category = "health" if matched_pack == "hospital" else "finance"
        confidence = float(rag_res.get("confidence", 0.85))
        reason = f"RAG router match based on {', '.join(rag_res.get('detected_signals', []))} (Ollama fallback: {e})"
        entities = rag_res.get("detected_signals", [])
        provider = "hybrid_rag_fallback"
        model = "rag_router_heuristic"

    # 3. Map category to pack metadata
    if category == "health":
        pack_id = "hospital"
        pack_name = "Hospital / Healthcare Pre-Auth"
        matched_skill = "wf_hospital_preauth"
        target_portal = "/portal_b/preauth"
    else:
        pack_id = "finance"
        pack_name = "Finance / Accounts Payable"
        matched_skill = "wf_vendor_claim"
        target_portal = "/portal/claim"

    return {
        "category": category,
        "pack_id": pack_id,
        "pack_name": pack_name,
        "matched_skill": matched_skill,
        "target_portal": target_portal,
        "confidence": round(confidence, 3),
        "reason": reason,
        "detected_entities": entities,
        "provider": provider,
        "model": model,
        "latency_ms": round((time.time() - t0) * 1000, 1),
        "text_snippet": text[:300].strip(),
    }
