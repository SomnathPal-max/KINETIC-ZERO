"""
Tier 1 Fingerprint Scoring Formula for KINETIC-ZERO.
Follows SPEC.txt Section 6.6 exactly.
"""

import math
import re
from typing import List, Tuple, Optional, Set
from rapidfuzz import fuzz
from contracts.models import Fingerprint


def _tokenize(s: str) -> Set[str]:
    if not s:
        return set()
    tokens = re.findall(r"[a-zA-Z0-9]+", s.lower())
    return set(tokens)


def _jaccard(set1: Set[str], set2: Set[str]) -> float:
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return float(intersection) / float(union) if union > 0 else 0.0


def _bbox_center(bbox: List[float]) -> Tuple[float, float]:
    if len(bbox) < 4:
        return (0.0, 0.0)
    x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
    return (x + w / 2.0, y + h / 2.0)


def compute_tier1_score(candidate: Fingerprint, recorded: Fingerprint) -> float:
    """
    Computes weighted multi-feature similarity score (0.0 to 1.0) between
    a live DOM candidate and the recorded baseline fingerprint.
    """
    # 1. text_sim (weight 0.30): max token_set_ratio across candidate text/aria/placeholder vs recorded text
    cand_texts = [candidate.text, candidate.aria_label, candidate.placeholder]
    recorded_target = recorded.text or recorded.aria_label or recorded.placeholder
    if not recorded_target:
        text_sim = 1.0 if not any(cand_texts) else 0.5
    else:
        ratios = [fuzz.token_set_ratio(t.lower(), recorded_target.lower()) for t in cand_texts if t]
        text_sim = (max(ratios) / 100.0) if ratios else 0.0

    # 2. label_sim (weight 0.20): candidate label/nearby text vs recorded label/nearby text
    cand_label = (candidate.label_text + " " + candidate.nearby_text).strip()
    rec_label = (recorded.label_text + " " + recorded.nearby_text).strip()
    if not rec_label:
        label_sim = 1.0 if not cand_label else 0.5
    else:
        label_sim = fuzz.token_set_ratio(cand_label.lower(), rec_label.lower()) / 100.0

    # 3. role_tag_match (weight 0.10): tag and role alignment
    tag_match = 1.0 if candidate.tag and candidate.tag == recorded.tag else 0.0
    role_match = 1.0 if candidate.role and candidate.role == recorded.role else 0.0
    role_tag_match = 0.5 * tag_match + 0.5 * role_match

    # 4. type_match (weight 0.10): input/button type attribute match
    type_match = 1.0 if candidate.type and candidate.type == recorded.type else (0.5 if not recorded.type else 0.0)

    # 5. attr_overlap (weight 0.10): Jaccard over tokens of id, name, classes, placeholder
    cand_attrs = _tokenize(f"{candidate.id} {candidate.name} {' '.join(candidate.classes)} {candidate.placeholder}")
    rec_attrs = _tokenize(f"{recorded.id} {recorded.name} {' '.join(recorded.classes)} {recorded.placeholder}")
    attr_overlap = _jaccard(cand_attrs, rec_attrs)

    # 6. dom_path_sim (weight 0.10): token ratio of DOM parent paths
    if not recorded.dom_path:
        dom_path_sim = 1.0 if not candidate.dom_path else 0.5
    else:
        dom_path_sim = fuzz.token_set_ratio(candidate.dom_path.lower(), recorded.dom_path.lower()) / 100.0

    # 7. pos_proximity (weight 0.10): 1 - min(1, euclidean(bbox centres) / 0.5)
    c_center = _bbox_center(candidate.bbox)
    r_center = _bbox_center(recorded.bbox)
    dist = math.sqrt((c_center[0] - r_center[0]) ** 2 + (c_center[1] - r_center[1]) ** 2)
    pos_proximity = max(0.0, 1.0 - min(1.0, dist / 0.5))

    # Total weighted score
    score = (
        0.30 * text_sim
        + 0.20 * label_sim
        + 0.10 * role_tag_match
        + 0.10 * type_match
        + 0.10 * attr_overlap
        + 0.10 * dom_path_sim
        + 0.10 * pos_proximity
    )
    return round(float(score), 4)


def select_tier1_candidate(
    candidates: List[Fingerprint],
    recorded: Fingerprint,
    negative_terms: List[str] = ["cancel", "clear", "back", "reject", "delete"],
    min_score: float = 0.62,
    min_margin: float = 0.12,
) -> Tuple[Optional[Fingerprint], float, float, float]:
    """
    Ranks candidates using Tier 1 formula.
    Filters out candidates matching negative terms unless recorded node intended it.
    Returns (selected_fp, top_score, second_score, margin).
    """
    if not candidates:
        return None, 0.0, 0.0, 0.0

    # Check if recorded element itself was a negative term (e.g. intentional cancel)
    rec_text_lower = (recorded.text + " " + recorded.label_text).lower()
    recorded_is_negative = any(neg in rec_text_lower for neg in negative_terms)

    scored: List[Tuple[Fingerprint, float]] = []
    for cand in candidates:
        cand_text_lower = (cand.text + " " + cand.label_text + " " + cand.aria_label).lower()
        # Exclude decoys/negative buttons if recorded wasn't negative
        if not recorded_is_negative and any(neg in cand_text_lower for neg in negative_terms):
            continue
        s = compute_tier1_score(cand, recorded)
        scored.append((cand, s))

    if not scored:
        return None, 0.0, 0.0, 0.0

    scored.sort(key=lambda x: x[1], reverse=True)
    top_cand, top_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    margin = top_score - second_score

    if top_score >= min_score and margin >= min_margin:
        return top_cand, top_score, second_score, margin

    return None, top_score, second_score, margin
