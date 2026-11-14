"""
GSTIN format and Luhn mod-36 checksum verification.
Follows SPEC.txt Appendix A and Gate G1.
"""

import re

CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Valid Indian state/UT GST codes (01-38, 97, 99)
VALID_STATE_CODES = {
    f"{i:02d}" for i in range(1, 39)
} | {"97", "99"}

GSTIN_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def gstin_checksum(first14: str) -> str:
    """Computes the 15th check character using Luhn mod-36 over the first 14 characters."""
    total = 0
    for i, c in enumerate(first14.upper()):
        v = CH.index(c)
        prod = v * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return CH[(36 - total % 36) % 36]


def gstin_ok(g: str) -> bool:
    """Validates GSTIN length, state code, regex pattern, and Luhn mod-36 checksum."""
    if not g or not isinstance(g, str):
        return False
    g = g.strip().upper()
    if len(g) != 15:
        return False
    if not GSTIN_REGEX.match(g):
        return False
    state_code = g[:2]
    if state_code not in VALID_STATE_CODES:
        return False
    if g[13] != "Z":
        return False
    return gstin_checksum(g[:14]) == g[14]


def make_valid_gstin(first14: str) -> str:
    """Helper to append correct check character to a valid 14-char GSTIN prefix."""
    first14 = first14.strip().upper()
    assert len(first14) == 14
    return first14 + gstin_checksum(first14)
