"""
Tier 2 LLM Selection for Disambiguation.
Follows SPEC.txt Section 6.6 and Appendix B.3.
"""

import json
from typing import List, Optional, Tuple, Dict, Any
from contracts.models import Fingerprint
from app.prompts import HEAL_SELECTION_PROMPT
from app.llm import call_json, CacheMiss


def select_tier2_candidate(
    intent: str,
    action: str,
    url: str,
    title: str,
    recorded_fp: Fingerprint,
    candidates: List[Fingerprint],
    top_k: int = 8,
) -> Tuple[Optional[Fingerprint], float, str]:
    """
    Calls Gemini model at temperature 0 to select the correct healed element from top-8 candidates.
    Returns (selected_fp, confidence, reason).
    If confidence < 0.70 or choice is None, returns (None, confidence, reason) to fail safe.
    """
    compact_recorded = {
        "tag": recorded_fp.tag,
        "text": recorded_fp.text,
        "label": recorded_fp.label_text,
        "role": recorded_fp.role,
        "type": recorded_fp.type,
        "id": recorded_fp.id,
        "name": recorded_fp.name,
    }

    compact_candidates = []
    top_candidates = candidates[:top_k]
    for i, c in enumerate(top_candidates):
        compact_candidates.append({
            "i": i,
            "tag": c.tag,
            "text": c.text,
            "label": c.label_text,
            "role": c.role,
            "type": c.type,
            "attrs": {"id": c.id, "name": c.name, "placeholder": c.placeholder},
            "center": [round(c.bbox[0] + c.bbox[2]/2.0, 2), round(c.bbox[1] + c.bbox[3]/2.0, 2)],
        })

    prompt = HEAL_SELECTION_PROMPT.format(
        intent=intent,
        action=action,
        url=url,
        title=title,
        recorded_fingerprint_compact=json.dumps(compact_recorded),
        candidates_json=json.dumps(compact_candidates),
    )

    schema = {
        "type": "object",
        "properties": {
            "choice": {"type": ["integer", "null"]},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["choice", "confidence", "reason"],
    }

    try:
        res = call_json("heal_select", prompt, schema, temperature=0.0)
        choice_idx = res.get("choice")
        confidence = float(res.get("confidence", 0.0))
        reason = res.get("reason", "LLM selection")

        if choice_idx is not None and 0 <= choice_idx < len(top_candidates):
            if confidence >= 0.70:
                return top_candidates[choice_idx], confidence, reason
            else:
                return None, confidence, f"Confidence {confidence:.2f} below 0.70 threshold: {reason}"
        return None, confidence, reason
    except CacheMiss:
        # Offline mode without cached response: fail safe
        return None, 0.0, "CacheMiss in offline mode; failing safe to human gate"
    except Exception as e:
        return None, 0.0, f"Tier 2 LLM error: {e}"
