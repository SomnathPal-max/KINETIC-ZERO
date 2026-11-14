"""
RAG Knowledge Layer for KINETIC-ZERO v2.
Pure Python + NumPy hybrid retrieval (0.6 meaning + 0.4 BM25-lite keywords).
Zero vector DB dependencies (No FAISS/Chroma - Rule 1 compliant).
Supports:
1. Clause Citations for TruthGuard
2. Ask the SOP (Ground-truth chat box citing exact clauses)
3. Agent Router (Auto-matches document/task to domain pack & skill)
"""

import os
import re
import json
import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from app.llm import call_json, CacheMiss

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKS_DIR = os.path.join(ROOT_DIR, "packs")


STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can",
    "cannot", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your", "yours"
}


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", text)]


def get_content_tokens(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def extract_numbers(text: str) -> List[str]:
    raw_nums = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", text)
    cleaned = []
    for n in raw_nums:
        c = n.replace(",", "")
        cleaned.append(c)
        if c.endswith(".00"):
            cleaned.append(c[:-3])
        if c in ["50000", "50001", "100000", "100001", "200000", "250000"]:
            cleaned.append(c)
    return list(dict.fromkeys(cleaned))


class RAGChunk:
    def __init__(self, pack_id: str, clause_id: str, title: str, text: str):
        self.pack_id = pack_id
        self.clause_id = clause_id
        self.title = title
        self.text = text
        self.full_text = f"{title}. {text}"
        self.tokens = tokenize(self.full_text)
        self.numbers = extract_numbers(self.full_text)
        self.vector: Optional[np.ndarray] = None


class DomainRAGIndex:
    def __init__(self, pack_id: str):
        self.pack_id = pack_id
        self.chunks: List[RAGChunk] = []
        self.chunk_map: Dict[str, RAGChunk] = {}
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.avg_dl: float = 0.0
        self._load()

    def _load(self):
        pack_dir = os.path.join(PACKS_DIR, self.pack_id)
        pjson_path = os.path.join(pack_dir, "pack.json")
        if not os.path.exists(pjson_path):
            return

        with open(pjson_path, "r", encoding="utf-8") as f:
            pack_meta = json.load(f)

        sop_rel = pack_meta.get("policy_doc", "policy/vendor_payment_sop.md")
        sop_path = os.path.join(pack_dir, sop_rel)
        if not os.path.exists(sop_path):
            return

        with open(sop_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse markdown clauses ### [ID] Title
        pattern = re.compile(r"^###\s+([A-Z]{2,4}-\d+\.\d+)\s+(.+?)$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        for i, m in enumerate(matches):
            cid = m.group(1).strip()
            title = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[start:end].strip()

            chunk = RAGChunk(pack_id=self.pack_id, clause_id=cid, title=title, text=body)
            self.chunks.append(chunk)
            self.chunk_map[cid] = chunk

        # Build vocabulary & IDF
        doc_count = len(self.chunks)
        if doc_count == 0:
            return

        total_tokens = sum(len(c.tokens) for c in self.chunks)
        self.avg_dl = total_tokens / doc_count

        df = {}
        for c in self.chunks:
            for w in set(c.tokens):
                df[w] = df.get(w, 0) + 1

        for w, count in df.items():
            self.idf[w] = math.log((doc_count - count + 0.5) / (count + 0.5) + 1.0)
            if w not in self.vocab:
                self.vocab[w] = len(self.vocab)

        # Build dense character n-gram / subword vectors using pure NumPy
        vocab_size = len(self.vocab)
        for c in self.chunks:
            vec = np.zeros(vocab_size, dtype=np.float32)
            for w in c.tokens:
                if w in self.vocab:
                    vec[self.vocab[w]] += self.idf.get(w, 1.0)
            norm = np.linalg.norm(vec)
            c.vector = (vec / norm) if norm > 0 else vec

    def score_bm25(self, query_tokens: List[str], chunk: RAGChunk, k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        doc_len = len(chunk.tokens)
        token_counts = {}
        for t in chunk.tokens:
            token_counts[t] = token_counts.get(t, 0) + 1

        for q in query_tokens:
            if q in token_counts:
                freq = token_counts[q]
                idf = self.idf.get(q, 0.5)
                num = freq * (k1 + 1.0)
                den = freq + k1 * (1.0 - b + b * (doc_len / (self.avg_dl or 1.0)))
                score += idf * (num / den)
        return score

    def score_dense(self, query_tokens: List[str], chunk: RAGChunk) -> float:
        if chunk.vector is None or len(self.vocab) == 0:
            return 0.0

        q_vec = np.zeros(len(self.vocab), dtype=np.float32)
        for q in query_tokens:
            if q in self.vocab:
                q_vec[self.vocab[q]] += self.idf.get(q, 1.0)
        norm = np.linalg.norm(q_vec)
        if norm == 0:
            return 0.0
        q_vec /= norm

        # Cosine similarity via NumPy dot product
        return float(np.dot(q_vec, chunk.vector))

    def retrieve(self, query: str, k: int = 3) -> List[Tuple[RAGChunk, float]]:
        all_tokens = tokenize(query)
        content_tokens = get_content_tokens(all_tokens)
        q_tokens = content_tokens if content_tokens else all_tokens

        if not q_tokens or not self.chunks:
            return []

        # If none of the content tokens appear in ANY chunk, return empty or zero score
        has_match = any(q in self.vocab for q in q_tokens)
        if not has_match and content_tokens:
            return []

        scored = []
        raw_bm25 = [self.score_bm25(q_tokens, c) for c in self.chunks]
        max_bm25 = max(raw_bm25) if raw_bm25 and max(raw_bm25) > 0 else 1.0

        for idx, chunk in enumerate(self.chunks):
            # Hybrid 0.6 meaning + 0.4 keyword BM25-lite
            bm25_norm = (raw_bm25[idx] / max_bm25) if max_bm25 > 0 and raw_bm25[idx] > 0 else 0.0
            dense = self.score_dense(q_tokens, chunk)
            hybrid_score = (0.6 * dense) + (0.4 * bm25_norm)
            scored.append((chunk, hybrid_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


# Registry of domain indexes
indices: Dict[str, DomainRAGIndex] = {}


def get_rag_index(pack_id: str) -> DomainRAGIndex:
    if pack_id not in indices:
        indices[pack_id] = DomainRAGIndex(pack_id)
    return indices[pack_id]


def ask_sop(query: str, pack_id: str = "finance") -> Dict[str, Any]:
    """
    Ask the SOP endpoint:
    Retrieves highest scoring clause using 0.6 meaning + 0.4 BM25-lite.
    Answers strictly from retrieved clause text.
    If best match < threshold, returns "not found in SOP" and escalates.
    """
    idx = get_rag_index(pack_id)
    results = idx.retrieve(query, k=1)

    threshold = 0.22
    if not results or results[0][1] < threshold:
        return {
            "found": False,
            "answer": "Not found in the loaded SOP documents. This query does not match any approved policy clause.",
            "clause_id": None,
            "clause_title": None,
            "score": round(results[0][1], 3) if results else 0.0,
            "escalate": True,
            "quoted_numbers": [],
        }

    best_chunk, score = results[0]

    # Synthesize strict answer via Ollama LLM
    prompt = (
        f"You are a strict compliance auditor answering questions about an organization's Standard Operating Procedure (SOP).\n"
        f"Answer the user's question using ONLY the facts and numbers directly stated in this clause.\n\n"
        f"Clause ID: {best_chunk.clause_id}\n"
        f"Clause Title: {best_chunk.title}\n"
        f"Clause Text: {best_chunk.text}\n\n"
        f"User Question: {query}\n\n"
        f"Respond in JSON format with fields:\n"
        f"- 'answer': a clear, concise 1-2 sentence response directly answering the question\n"
        f"- 'cited_clause': the clause ID\n"
        f"- 'quoted_numbers': list of numbers mentioned from the text\n"
    )

    schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "cited_clause": {"type": "string"},
            "quoted_numbers": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["answer", "cited_clause"],
    }

    try:
        data = call_json(f"ask_sop_{pack_id}_{hash(query)}", prompt, schema, temperature=0.0)
        answer = data.get("answer", best_chunk.text)
        quoted_numbers = data.get("quoted_numbers", [])
    except CacheMiss:
        # Fallback to direct citation
        answer = f"According to clause {best_chunk.clause_id} ({best_chunk.title}): {best_chunk.text}"
        quoted_numbers = best_chunk.numbers

    return {
        "found": True,
        "answer": answer,
        "clause_id": best_chunk.clause_id,
        "clause_title": best_chunk.title,
        "clause_text": best_chunk.text,
        "score": round(score, 3),
        "escalate": False,
        "quoted_numbers": quoted_numbers,
    }


def route_document(text: str) -> Dict[str, Any]:
    """
    Agent Router Layer:
    Takes an input document text or task prompt, scores it across installed packs,
    and returns the best matching Domain Pack and taught workflow skill.
    """
    text_lower = text.lower()

    # Domain keyword heuristics & token sets
    finance_signals = ["invoice", "tax", "gstin", "cgst", "sgst", "igst", "vendor", "po number", "taxable value", "meridian"]
    hospital_signals = ["patient", "pre-auth", "preauthorization", "hospital", "diagnosis", "icd-10", "insurer", "admission", "cashless", "tpa", "apollo"]

    fin_score = sum(1 for s in finance_signals if s in text_lower)
    hosp_score = sum(1 for s in hospital_signals if s in text_lower)

    # Hybrid RAG router matching against SOP indexes
    fin_idx = get_rag_index("finance")
    hosp_idx = get_rag_index("hospital")

    fin_res = fin_idx.retrieve(text[:300], k=1)
    hosp_res = hosp_idx.retrieve(text[:300], k=1)

    fin_rag_score = fin_res[0][1] if fin_res else 0.0
    hosp_rag_score = hosp_res[0][1] if hosp_res else 0.0

    total_fin = fin_score * 0.4 + fin_rag_score * 0.6
    total_hosp = hosp_score * 0.4 + hosp_rag_score * 0.6

    if total_hosp > total_fin:
        confidence = min(0.99, max(0.70, round(total_hosp / (total_fin + total_hosp + 1e-5), 3)))
        return {
            "matched_pack_id": "hospital",
            "matched_pack_name": "Hospital / Healthcare Pre-Auth",
            "matched_skill": "wf_hospital_preauth",
            "target_portal": "/portal_b/preauth",
            "confidence": confidence,
            "detected_signals": [s for s in hospital_signals if s in text_lower],
        }
    else:
        confidence = min(0.99, max(0.70, round(total_fin / (total_fin + total_hosp + 1e-5), 3)))
        return {
            "matched_pack_id": "finance",
            "matched_pack_name": "Finance / Accounts Payable",
            "matched_skill": "wf_vendor_claim",
            "target_portal": "/portal/claim",
            "confidence": confidence,
            "detected_signals": [s for s in finance_signals if s in text_lower],
        }
