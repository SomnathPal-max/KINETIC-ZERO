"""
DOM Fingerprint extraction and locator candidate generation.
Follows SPEC.txt Section 5.4 and Section 6.5.
Rule 10: Never read or emit data-k0 attributes.
"""

from typing import Dict, Any, List, Optional
from contracts.models import Fingerprint, Locator


def sanitize_attribute_value(val: str) -> str:
    """Ensure no data-k0 strings leak into fingerprints or locators."""
    if not val:
        return ""
    if "data-k0" in val:
        return ""
    return val


def create_fingerprint_from_dict(d: Dict[str, Any]) -> Fingerprint:
    """Converts a raw DOM element inspection dictionary into a validated Fingerprint model."""
    classes = [c for c in d.get("classes", []) if "data-k0" not in c]
    bbox = d.get("bbox", [0.0, 0.0, 0.0, 0.0])
    if len(bbox) != 4:
        bbox = [0.0, 0.0, 0.0, 0.0]

    return Fingerprint(
        tag=sanitize_attribute_value(d.get("tag", "").lower()),
        id=sanitize_attribute_value(d.get("id", "")),
        name=sanitize_attribute_value(d.get("name", "")),
        classes=classes,
        text=sanitize_attribute_value(d.get("text", "")),
        aria_label=sanitize_attribute_value(d.get("aria_label", "")),
        role=sanitize_attribute_value(d.get("role", "")),
        type=sanitize_attribute_value(d.get("type", "")),
        placeholder=sanitize_attribute_value(d.get("placeholder", "")),
        label_text=sanitize_attribute_value(d.get("label_text", "")),
        nearby_text=sanitize_attribute_value(d.get("nearby_text", "")),
        dom_path=sanitize_attribute_value(d.get("dom_path", "")),
        bbox=bbox,
        form_id=sanitize_attribute_value(d.get("form_id", "")),
        index_in_form=int(d.get("index_in_form", 0)),
    )


def generate_locators(fp: Fingerprint) -> List[Locator]:
    """
    Generates locator candidates in frozen priority order:
    testid > id > name > role > css.
    Excludes any data-k0 locators.
    """
    locators: List[Locator] = []

    # 1. ID
    if fp.id and "data-k0" not in fp.id:
        locators.append(Locator(strategy="id", value=f"#{fp.id}"))

    # 2. Name
    if fp.name and "data-k0" not in fp.name:
        locators.append(Locator(strategy="name", value=fp.name))

    # 3. Role / Label
    if fp.role and fp.aria_label:
        locators.append(Locator(strategy="role", value=f"{fp.role}[name='{fp.aria_label}']"))
    elif fp.role and fp.text:
        locators.append(Locator(strategy="role", value=f"{fp.role}[name='{fp.text}']"))

    # 4. CSS (tag + classes or dom path)
    if fp.tag:
        if fp.classes:
            valid_classes = [c for c in fp.classes if "data-k0" not in c and "mut" not in c]
            if valid_classes:
                css_sel = f"{fp.tag}." + ".".join(valid_classes)
                locators.append(Locator(strategy="css", value=css_sel))

        if fp.dom_path and "data-k0" not in fp.dom_path:
            locators.append(Locator(strategy="css", value=fp.dom_path))

    # Default fallback if empty
    if not locators and fp.tag:
        locators.append(Locator(strategy="css", value=fp.tag))

    return locators
