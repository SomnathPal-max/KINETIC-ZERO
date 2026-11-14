"""
Domain Pack Loader for KINETIC-ZERO v2.
Loads swappable Domain Packs (Finance, Hospital, etc.)
"""

import os
import json
from typing import Dict, Any, List, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKS_DIR = os.path.join(ROOT_DIR, "packs")


def list_packs() -> List[Dict[str, Any]]:
    """Lists all installed domain packs."""
    packs = []
    if not os.path.exists(PACKS_DIR):
        return packs

    for entry in os.listdir(PACKS_DIR):
        pdir = os.path.join(PACKS_DIR, entry)
        pjson = os.path.join(pdir, "pack.json")
        if os.path.isdir(pdir) and os.path.exists(pjson):
            try:
                with open(pjson, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    packs.append(data)
            except Exception:
                pass
    return sorted(packs, key=lambda x: 0 if x.get("id") == "finance" else 1)


def get_pack(pack_id: str) -> Optional[Dict[str, Any]]:
    """Loads a specific domain pack definition."""
    pdir = os.path.join(PACKS_DIR, pack_id)
    pjson = os.path.join(pdir, "pack.json")
    if not os.path.exists(pjson):
        return None

    with open(pjson, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Attach paths
    meta["pack_dir"] = pdir
    meta["schema_path"] = os.path.join(pdir, "schema.json")
    meta["rules_path"] = os.path.join(pdir, "rules.json")
    meta["policy_path"] = os.path.join(pdir, meta.get("policy_doc", "policy/vendor_payment_sop.md"))
    return meta


def get_pack_schema(pack_id: str) -> Dict[str, Any]:
    pdir = os.path.join(PACKS_DIR, pack_id)
    spath = os.path.join(pdir, "schema.json")
    if os.path.exists(spath):
        with open(spath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"doc_type": "generic", "fields": []}


def get_pack_rules(pack_id: str) -> List[Dict[str, Any]]:
    pdir = os.path.join(PACKS_DIR, pack_id)
    rpath = os.path.join(pdir, "rules.json")
    if os.path.exists(rpath):
        with open(rpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("rules", [])
    return []


def get_pack_registry(pack_id: str) -> Dict[str, Any]:
    pdir = os.path.join(PACKS_DIR, pack_id)
    pack = get_pack(pack_id)
    reg_rel = pack.get("registry", "registry/vendors.json") if pack else "registry/vendors.json"
    rpath = os.path.join(pdir, reg_rel)
    if os.path.exists(rpath):
        with open(rpath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_pack_ledger(pack_id: str) -> Dict[str, Any]:
    pdir = os.path.join(PACKS_DIR, pack_id)
    pack = get_pack(pack_id)
    led_rel = pack.get("ledger", "registry/ledger.json") if pack else "registry/ledger.json"
    lpath = os.path.join(pdir, led_rel)
    if os.path.exists(lpath):
        with open(lpath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
