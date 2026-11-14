"""
Policy Retrieval Interface.
Follows SPEC.txt Section 8.
"""

from typing import List
from app.policy.index import policy_index, Clause


def retrieve(query: str, k: int = 3) -> List[Clause]:
    return policy_index.retrieve(query, k=k)


def exists(clause_id: str) -> bool:
    return policy_index.exists(clause_id)


def numbers_in(clause_id: str) -> List[str]:
    return policy_index.numbers_in(clause_id)
