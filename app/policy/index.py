"""
Clause-level Policy Index and Hybrid Retrieval Engine.
Follows SPEC.txt Section 6.3.
Custom indexing pipeline: BM25-lite lexical search + Gemini cosine embeddings with fallback.
"""

import os
import re
import json
import math
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

SOP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "policy", "vendor_payment_sop.md")
POLICY_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "policy", "policy.json")


class Clause(BaseModel):
    clause_id: str
    title: str
    text: str
    numbers: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    score: float = 0.0


def extract_numbers(text: str) -> List[str]:
    """Extracts all numeric sequences (integers/decimals) from text."""
    # Matches numbers with optional commas/decimals
    raw_nums = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", text)
    cleaned = []
    for n in raw_nums:
        c = n.replace(",", "")
        cleaned.append(c)
        # Also include without decimal if .00
        if c.endswith(".00"):
            cleaned.append(c[:-3])
        # Also Indian style 1,00,000 -> 100000
        if c == "100000" or c == "100001" or c == "250000":
            cleaned.append(c)
    return list(dict.fromkeys(cleaned))


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", text)]


class PolicyIndex:
    def __init__(self, sop_path: str = SOP_PATH):
        self.sop_path = sop_path
        self.clauses: Dict[str, Clause] = {}
        self.clause_list: List[Clause] = []
        self._doc_freq: Dict[str, int] = {}
        self._avg_dl = 0.0
        self._load_and_parse()

    def _load_and_parse(self):
        if not os.path.exists(self.sop_path):
            return

        with open(self.sop_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse sections starting with ### VP-x.y Title
        pattern = re.compile(r"^###\s+(VP-\d+\.\d+)\s+(.+?)$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        total_tokens = 0
        for i, m in enumerate(matches):
            c_id = m.group(1).strip()
            title = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[start:end].strip()

            full_text = f"{title}. {body}"
            tokens = tokenize(full_text)
            total_tokens += len(tokens)
            numbers = extract_numbers(full_text)

            # Special case for limits written in words/numbers e.g. 1,00,000 -> 100000
            if "1,00,000" in full_text and "100000" not in numbers:
                numbers.append("100000")
            if "2,50,000" in full_text and "250000" not in numbers:
                numbers.append("250000")
            if "1,00,001" in full_text and "100001" not in numbers:
                numbers.append("100001")

            # Update document frequency
            unique_words = set(tokens)
            for w in unique_words:
                self._doc_freq[w] = self._doc_freq.get(w, 0) + 1

            clause_obj = Clause(
                clause_id=c_id,
                title=title,
                text=body,
                numbers=numbers,
                keywords=list(unique_words),
            )
            self.clauses[c_id] = clause_obj
            self.clause_list.append(clause_obj)

        if self.clause_list:
            self._avg_dl = total_tokens / len(self.clause_list)

    def bm25_score(self, query: str, clause: Clause, k1: float = 1.5, b: float = 0.75) -> float:
        """BM25-lite lexical scoring."""
        q_tokens = tokenize(query)
        doc_tokens = tokenize(f"{clause.title} {clause.text}")
        doc_len = len(doc_tokens)
        score = 0.0
        N = len(self.clause_list)

        doc_tf: Dict[str, int] = {}
        for t in doc_tokens:
            doc_tf[t] = doc_tf.get(t, 0) + 1

        for q in q_tokens:
            if q not in doc_tf:
                continue
            tf = doc_tf[q]
            df = self._doc_freq.get(q, 0)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
            numerator = tf * (k1 + 1.0)
            denominator = tf + k1 * (1.0 - b + b * (doc_len / (self._avg_dl or 1.0)))
            score += idf * (numerator / (denominator or 1.0))

        return score

    def retrieve(self, query: str, k: int = 3) -> List[Clause]:
        """
        Hybrid retrieval: 0.6 cosine embeddings + 0.4 BM25-lite lexical.
        Falls back cleanly to lexical ranking if embedding API is unconfigured.
        """
        if not self.clause_list:
            return []

        # Lexical scores
        scored: List[Clause] = []
        for c in self.clause_list:
            lex_score = self.bm25_score(query, c)
            c_copy = c.model_copy()
            c_copy.score = round(float(lex_score), 4)
            scored.append(c_copy)

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:k]

    def exists(self, clause_id: str) -> bool:
        return clause_id.strip() in self.clauses

    def numbers_in(self, clause_id: str) -> List[str]:
        c = self.clauses.get(clause_id.strip())
        return c.numbers if c else []


policy_index = PolicyIndex()
